"""
Test Execution Engine - Execution Trace Model

Implements smart partitioning architecture for execution traces:
- Embedded traces for executions with <50 steps  
- Normalized traces for executions with >=50 steps
- Automatic threshold management and partitioning decision

Based on creative phase architectural decisions for optimal performance
and scalability across different execution complexity levels.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from bson import ObjectId
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict

from ...config.logging import get_logger

logger = get_logger(__name__)


class BaseMongoModel(BaseModel):
    """
    Base model for MongoDB documents with common fields and utilities.
    
    Implements DRY principles for timestamps, schema versioning, and
    datetime serialization handling across all MongoDB models.
    """
    
    # Document identity
    id: Optional[str] = Field(None, alias="_id", description="MongoDB document ID")
    
    # Schema versioning for migrations (stored as _schema_version in MongoDB)
    schema_version: str = Field(
        default="1.0",
        alias="_schema_version",
        description="Schema version for forward compatibility"
    )
    
    # Audit trail with UTC-aware timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp (UTC)"
    )
    updated_at: Optional[datetime] = Field(
        None,
        description="Last update timestamp (UTC)"
    )
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        use_enum_values=True,
        json_encoders={
            ObjectId: str,
            datetime: lambda v: v.isoformat() if v else None,
        }
    )
    
    @field_validator('created_at', 'updated_at', mode='before')
    @classmethod
    def validate_datetime_utc(cls, v):
        """Ensure datetime fields are UTC-aware with fallback handling."""
        if v is None:
            return v
        
        if isinstance(v, str):
            try:
                # Parse ISO string with fallback
                if v.endswith('Z'):
                    v = v[:-1] + '+00:00'
                return datetime.fromisoformat(v)
            except ValueError:
                logger.warning(f"Failed to parse datetime string: {v}, using current UTC time")
                return datetime.now(timezone.utc)
        
        if isinstance(v, datetime):
            # Ensure timezone awareness
            if v.tzinfo is None:
                logger.debug("Converting naive datetime to UTC")
                return v.replace(tzinfo=timezone.utc)
            return v
        
        logger.warning(f"Invalid datetime value: {v}, using current UTC time")
        return datetime.now(timezone.utc)
    
    def update_timestamp(self) -> None:
        """Update the updated_at timestamp to current UTC time."""
        self.updated_at = datetime.now(timezone.utc)
    
    @classmethod
    def from_mongo(cls, data: Dict[str, Any]) -> Optional["BaseMongoModel"]:
        """Create model instance from MongoDB document."""
        if not data:
            return None
        
        try:
            # Handle ObjectId conversion
            if "_id" in data and isinstance(data["_id"], ObjectId):
                data["_id"] = str(data["_id"])
            
            # Handle datetime fields
            for field in ["created_at", "updated_at"]:
                if field in data and data[field]:
                    if isinstance(data[field], datetime):
                        # Ensure UTC timezone
                        if data[field].tzinfo is None:
                            data[field] = data[field].replace(tzinfo=timezone.utc)
            
            return cls(**data)
        except Exception as e:
            logger.error(f"Failed to create {cls.__name__} from MongoDB data: {e}")
            return None
    
    def to_mongo(self) -> Dict[str, Any]:
        """Convert model to MongoDB document format."""
        data = self.model_dump(by_alias=True, exclude_none=True)
        
        # Convert string ID back to ObjectId for MongoDB
        if "_id" in data and data["_id"]:
            try:
                data["_id"] = ObjectId(data["_id"])
            except Exception:
                # If conversion fails, remove the field to let MongoDB generate new ID
                del data["_id"]
        
        # Ensure UTC datetime storage
        for field in ["created_at", "updated_at"]:
            if field in data and data[field]:
                if isinstance(data[field], str):
                    try:
                        data[field] = datetime.fromisoformat(data[field])
                    except ValueError:
                        logger.warning(f"Invalid datetime string for {field}: {data[field]}")
                        data[field] = datetime.now(timezone.utc)
        
        return data


class ExecutionStatus(str, Enum):
    """
    Execution status enumeration following state machine design.
    Supports hybrid state-event architecture from creative phase.
    """
    PENDING = "pending"
    QUEUED = "queued" 
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    RETRYING = "retrying"
    ABORTED = "aborted"
    
    @classmethod
    def get_valid_transitions(cls) -> Dict[str, List[str]]:
        """Get valid state transitions for state machine validation"""
        return {
            cls.PENDING: [cls.QUEUED, cls.CANCELLED],
            cls.QUEUED: [cls.RUNNING, cls.CANCELLED],
            cls.RUNNING: [cls.PASSED, cls.FAILED, cls.CANCELLED, cls.TIMEOUT],
            cls.PASSED: [],
            cls.FAILED: [cls.RETRYING],
            cls.RETRYING: [cls.QUEUED, cls.ABORTED],
            cls.CANCELLED: [],
            cls.TIMEOUT: [cls.RETRYING], 
            cls.ABORTED: []
        }
    
    def can_transition_to(self, new_status: 'ExecutionStatus') -> bool:
        """Check if transition to new status is valid"""
        valid_transitions = self.get_valid_transitions()
        return new_status in valid_transitions.get(self, [])


class StepStatus(str, Enum):
    """Step execution status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"
    WARNING = "warning"


class ExecutionType(str, Enum):
    """Type of execution being performed"""
    TEST_CASE = "test_case"
    TEST_SUITE = "test_suite"
    MANUAL_EXECUTION = "manual_execution"
    BATCH_EXECUTION = "batch_execution"
    CI_CD_EXECUTION = "ci_cd_execution"


class ResourceUsageMetrics(BaseModel):
    """Resource usage metrics for execution monitoring"""
    cpu_usage_percent: Optional[float] = Field(None, ge=0, le=100, description="CPU usage percentage")
    memory_usage_mb: Optional[float] = Field(None, ge=0, description="Memory usage in MB")
    disk_io_mb: Optional[float] = Field(None, ge=0, description="Disk I/O in MB")
    network_io_mb: Optional[float] = Field(None, ge=0, description="Network I/O in MB")
    execution_environment: Optional[str] = Field(None, description="Execution environment identifier")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "cpu_usage_percent": 25.5,
                "memory_usage_mb": 512.0,
                "disk_io_mb": 10.2,
                "network_io_mb": 5.1,
                "execution_environment": "local-runner-01"
            }
        }
    )


class StepErrorDetails(BaseModel):
    """Detailed error information for failed steps"""
    error_type: str = Field(..., description="Type of error that occurred")
    error_message: str = Field(..., description="Human-readable error message")
    error_code: Optional[str] = Field(None, description="Machine-readable error code")
    stack_trace: Optional[str] = Field(None, description="Full stack trace if available")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional error context")
    retry_attempted: bool = Field(False, description="Whether retry was attempted")
    recovery_suggestion: Optional[str] = Field(None, description="Suggested recovery action")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error_type": "AssertionError",
                "error_message": "Expected value '200' but got '404'",
                "error_code": "ASSERT_001",
                "stack_trace": "Traceback (most recent call last)...",
                "context": {"expected": "200", "actual": "404", "url": "/api/users"},
                "retry_attempted": True,
                "recovery_suggestion": "Check API endpoint availability"
            }
        }
    )


class StepResultModel(BaseModel):
    """
    Individual step execution result model.
    
    Supports both embedded (for <50 steps) and normalized (for >=50 steps)
    storage patterns based on smart partitioning architecture.
    """
    step_id: str = Field(..., description="Unique identifier for the step")
    step_name: str = Field(..., description="Human-readable step name")
    step_order: int = Field(..., ge=0, description="Order of step in execution sequence")
    status: StepStatus = Field(..., description="Current status of step execution")
    
    # Timing Information
    started_at: Optional[datetime] = Field(None, description="Step execution start time")
    completed_at: Optional[datetime] = Field(None, description="Step execution completion time")
    duration_ms: Optional[int] = Field(None, ge=0, description="Step duration in milliseconds")
    timeout_ms: Optional[int] = Field(None, ge=0, description="Step timeout in milliseconds")
    
    # Execution Data
    input_data: Dict[str, Any] = Field(default_factory=dict, description="Step input parameters")
    output_data: Optional[Dict[str, Any]] = Field(None, description="Step output/result data")
    expected_result: Optional[Dict[str, Any]] = Field(None, description="Expected step result")
    actual_result: Optional[Dict[str, Any]] = Field(None, description="Actual step result")
    
    # Error Handling
    error_details: Optional[StepErrorDetails] = Field(None, description="Error details if step failed")
    warnings: List[str] = Field(default_factory=list, description="Step execution warnings")
    
    # Retry Information
    retry_count: int = Field(0, ge=0, description="Number of retry attempts")
    max_retries: int = Field(0, ge=0, description="Maximum allowed retries")
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional step metadata")
    execution_environment: Optional[str] = Field(None, description="Environment where step executed")
    step_type: Optional[str] = Field(None, description="Type of step (action, assertion, etc.)")
    
    @model_validator(mode='after')
    def validate_step_consistency(self):
        """Validate overall step data consistency"""
        # Ensure completion time is after start time
        if self.completed_at and self.started_at:
            if self.completed_at < self.started_at:
                raise ValueError("Completion time cannot be before start time")
        
        # Auto-calculate duration if not provided but times are available
        if self.duration_ms is None and self.started_at and self.completed_at:
            duration = (self.completed_at - self.started_at).total_seconds() * 1000
            self.duration_ms = int(duration)
        
        # Failed steps should have error details
        if self.status == StepStatus.FAILED and not self.error_details:
            raise ValueError("Failed steps must include error details")
            
        # Completed steps should have completion time
        if self.status in [StepStatus.PASSED, StepStatus.FAILED] and not self.completed_at:
            raise ValueError("Completed steps must have completion time")
            
        return self
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "step_id": "step_001",
                "step_name": "Login to application",
                "step_order": 1,
                "status": "passed",
                "started_at": "2025-01-05T22:30:00Z",
                "completed_at": "2025-01-05T22:30:02Z",
                "duration_ms": 2000,
                "timeout_ms": 30000,
                "input_data": {"username": "testuser", "password": "***"},
                "output_data": {"session_id": "abc123", "login_time": "2025-01-05T22:30:02Z"},
                "retry_count": 0,
                "max_retries": 3,
                "metadata": {"browser": "chrome", "page_url": "/login"},
                "step_type": "action"
            }
        }
    )


class ExecutionStatistics(BaseModel):
    """
    Real-time and historical execution statistics.
    Supports progressive observability architecture from creative phase.
    """
    # Basic Counts
    total_steps: int = Field(0, ge=0, description="Total number of steps")
    completed_steps: int = Field(0, ge=0, description="Number of completed steps")
    passed_steps: int = Field(0, ge=0, description="Number of passed steps")
    failed_steps: int = Field(0, ge=0, description="Number of failed steps")
    skipped_steps: int = Field(0, ge=0, description="Number of skipped steps")
    
    # Progress Metrics
    progress_percentage: float = Field(0.0, ge=0, le=100, description="Execution progress percentage")
    estimated_remaining_ms: Optional[int] = Field(None, ge=0, description="Estimated remaining time in ms")
    average_step_duration_ms: Optional[float] = Field(None, ge=0, description="Average step duration")
    
    # Performance Metrics
    total_duration_ms: Optional[int] = Field(None, ge=0, description="Total execution duration")
    actual_vs_estimated_ratio: Optional[float] = Field(None, description="Actual vs estimated time ratio")
    
    # Reliability Metrics
    retry_rate: float = Field(0.0, ge=0, le=1, description="Step retry rate (0-1)")
    error_rate: float = Field(0.0, ge=0, le=1, description="Step error rate (0-1)")
    success_rate: float = Field(0.0, ge=0, le=1, description="Step success rate (0-1)")
    
    # Resource Usage
    resource_usage: Optional[ResourceUsageMetrics] = Field(None, description="Resource usage metrics")
    
    @model_validator(mode='after')
    def calculate_metrics(self):
        """Auto-calculate progress and success rate if not provided"""
        # Auto-calculate progress if not provided
        if self.progress_percentage == 0.0 and self.total_steps > 0:
            self.progress_percentage = (self.completed_steps / self.total_steps) * 100
        
        # Auto-calculate success rate if not provided
        if self.success_rate == 0.0 and self.completed_steps > 0:
            self.success_rate = self.passed_steps / self.completed_steps
            
        return self
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_steps": 10,
                "completed_steps": 7,
                "passed_steps": 6,
                "failed_steps": 1,
                "skipped_steps": 0,
                "progress_percentage": 70.0,
                "estimated_remaining_ms": 15000,
                "average_step_duration_ms": 2500.0,
                "total_duration_ms": 17500,
                "retry_rate": 0.1,
                "error_rate": 0.14,
                "success_rate": 0.86
            }
        }
    )


class ExecutionTraceModel(BaseMongoModel):
    """
    Main execution trace model implementing smart partitioning architecture.
    
    For executions with <50 steps: Embedded storage for optimal performance
    For executions with >=50 steps: Normalized storage with references
    
    Supports hybrid state-event execution pattern with comprehensive 
    audit trail and real-time progress tracking.
    """
    
    # Core Identification
    execution_id: str = Field(..., description="Unique execution identifier")
    parent_execution_id: Optional[str] = Field(None, description="Parent execution ID for nested executions")
    
    # Execution Context
    test_case_id: Optional[str] = Field(None, description="Test case ID if single case execution")
    test_suite_id: Optional[str] = Field(None, description="Test suite ID if suite execution")
    execution_type: ExecutionType = Field(..., description="Type of execution")
    execution_context: Dict[str, Any] = Field(default_factory=dict, description="Execution context data")
    
    # Execution Lifecycle
    status: ExecutionStatus = Field(ExecutionStatus.PENDING, description="Current execution status")
    triggered_by: str = Field(..., description="User or system that triggered execution")
    triggered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Execution trigger time")
    started_at: Optional[datetime] = Field(None, description="Execution start time")
    completed_at: Optional[datetime] = Field(None, description="Execution completion time")
    
    # Smart Partitioning Decision
    is_partitioned: bool = Field(False, description="Whether execution uses partitioned storage")
    step_count_threshold: int = Field(50, description="Threshold for partitioning decision")
    estimated_step_count: int = Field(0, ge=0, description="Estimated number of steps")
    
    # Embedded Steps (for <50 steps)
    embedded_steps: List[StepResultModel] = Field(default_factory=list, description="Embedded step results")
    
    # Normalized References (for >=50 steps)
    step_results_collection: Optional[str] = Field(None, description="Collection name for step results")
    step_results_query: Optional[Dict[str, Any]] = Field(None, description="Query for retrieving step results")
    
    # Execution Summary
    statistics: ExecutionStatistics = Field(default_factory=ExecutionStatistics, description="Execution statistics")
    overall_result: Optional[str] = Field(None, description="Overall execution result summary")
    
    # Performance and Resource Tracking
    total_duration_ms: Optional[int] = Field(None, ge=0, description="Total execution duration")
    resource_usage: Optional[ResourceUsageMetrics] = Field(None, description="Resource usage during execution")
    
    # Configuration
    execution_config: Dict[str, Any] = Field(default_factory=dict, description="Execution configuration")
    timeout_ms: Optional[int] = Field(None, ge=0, description="Execution timeout in milliseconds")
    retry_config: Dict[str, Any] = Field(default_factory=dict, description="Retry configuration")
    
    # State Management
    state_history: List[Dict[str, Any]] = Field(default_factory=list, description="State transition history")
    last_state_change: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last state change time")
    
    # Observability and Debugging
    execution_log: List[str] = Field(default_factory=list, description="Execution log entries")
    debug_data: Dict[str, Any] = Field(default_factory=dict, description="Debug information")
    trace_level: str = Field("INFO", description="Tracing level for debugging")
    
    # Metadata
    tags: List[str] = Field(default_factory=list, description="Execution tags for organization")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional execution metadata")
    
    @model_validator(mode='after')
    def validate_execution_consistency(self):
        """Validate execution data consistency"""
        # Validate smart partitioning logic consistency
        if not self.is_partitioned:
            if self.estimated_step_count >= self.step_count_threshold:
                raise ValueError(f"Estimated step count {self.estimated_step_count} exceeds threshold {self.step_count_threshold} but is_partitioned is False")
            if self.step_results_collection:
                raise ValueError("Non-partitioned executions should not have step_results_collection")
        else:
            # For partitioned executions  
            if self.estimated_step_count < self.step_count_threshold:
                raise ValueError(f"Estimated step count {self.estimated_step_count} below threshold {self.step_count_threshold} but is_partitioned is True")
            if self.embedded_steps:
                raise ValueError("Partitioned executions should not have embedded_steps")
            if not self.step_results_collection:
                raise ValueError("Partitioned executions must have step_results_collection")
        
        # Validate execution reference consistency
        if self.execution_type == ExecutionType.TEST_CASE and not self.test_case_id:
            raise ValueError("TEST_CASE execution must have test_case_id")
        if self.execution_type == ExecutionType.TEST_SUITE and not self.test_suite_id:
            raise ValueError("TEST_SUITE execution must have test_suite_id")
        if self.test_case_id and self.test_suite_id:
            raise ValueError("Execution cannot reference both test_case_id and test_suite_id")
            
        return self
    
    def should_partition(self) -> bool:
        """Determine if execution should use partitioned storage"""
        return self.estimated_step_count >= self.step_count_threshold
    
    def transition_state(self, new_status: ExecutionStatus, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Perform state transition with validation.
        Returns True if transition successful, False otherwise.
        """
        if not self.status.can_transition_to(new_status):
            return False
        
        # Record state change in history
        state_change = {
            "from_status": self.status,
            "to_status": new_status,
            "timestamp": datetime.now(timezone.utc),
            "context": context or {}
        }
        self.state_history.append(state_change)
        
        # Update status and timestamp
        self.status = new_status
        self.last_state_change = state_change["timestamp"]
        
        return True
    
    def add_step_result(self, step_result: StepResultModel) -> None:
        """Add step result using appropriate storage strategy"""
        if self.is_partitioned:
            # For partitioned storage, this would typically interact with
            # a separate step results collection - placeholder for now
            self.statistics.total_steps += 1
            self.statistics.completed_steps += 1
            if step_result.status == StepStatus.PASSED:
                self.statistics.passed_steps += 1
            elif step_result.status == StepStatus.FAILED:
                self.statistics.failed_steps += 1
            elif step_result.status == StepStatus.SKIPPED:
                self.statistics.skipped_steps += 1
        else:
            # For embedded storage
            self.embedded_steps.append(step_result)
            self.statistics.total_steps = len(self.embedded_steps)
            self.statistics.completed_steps = len([s for s in self.embedded_steps if s.status in [StepStatus.PASSED, StepStatus.FAILED, StepStatus.SKIPPED]])
            self.statistics.passed_steps = len([s for s in self.embedded_steps if s.status == StepStatus.PASSED])
            self.statistics.failed_steps = len([s for s in self.embedded_steps if s.status == StepStatus.FAILED])
            self.statistics.skipped_steps = len([s for s in self.embedded_steps if s.status == StepStatus.SKIPPED])
    
    model_config = ConfigDict(
        collection_name="execution_traces",
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "execution_id": "exec_20250105_223000_001",
                "test_case_id": "507f1f77bcf86cd799439011",
                "execution_type": "test_case",
                "status": "running",
                "triggered_by": "user@example.com",
                "triggered_at": "2025-01-05T22:30:00Z",
                "started_at": "2025-01-05T22:30:01Z",
                "is_partitioned": False,
                "step_count_threshold": 50,
                "estimated_step_count": 10,
                "embedded_steps": [],
                "statistics": {
                    "total_steps": 10,
                    "completed_steps": 3,
                    "passed_steps": 3,
                    "failed_steps": 0,
                    "skipped_steps": 0,
                    "progress_percentage": 30.0
                },
                "execution_config": {"timeout_ms": 1800000, "retry_enabled": True},
                "tags": ["regression", "api"],
                "metadata": {"environment": "staging", "build": "v1.2.3"}
            }
        }
    )


# Exception Classes for Error Hierarchy
class ExecutionError(Exception):
    """Base exception for execution-related errors"""
    pass


class StepExecutionError(ExecutionError):
    """Exception raised during step execution"""
    def __init__(self, step_id: str, message: str, error_details: Optional[StepErrorDetails] = None):
        self.step_id = step_id
        self.error_details = error_details
        super().__init__(f"Step {step_id}: {message}")


class ExecutionTimeoutError(ExecutionError):
    """Exception raised when execution exceeds timeout"""
    def __init__(self, execution_id: str, timeout_ms: int):
        self.execution_id = execution_id
        self.timeout_ms = timeout_ms
        super().__init__(f"Execution {execution_id} timed out after {timeout_ms}ms")


class StateTransitionError(ExecutionError):
    """Exception raised for invalid state transitions"""
    def __init__(self, execution_id: str, from_status: ExecutionStatus, to_status: ExecutionStatus):
        self.execution_id = execution_id
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(f"Invalid state transition for {execution_id}: {from_status} -> {to_status}")


class ResourceAllocationError(ExecutionError):
    """Exception raised when resources cannot be allocated for execution"""
    def __init__(self, execution_id: str, resource_type: str, reason: str):
        self.execution_id = execution_id
        self.resource_type = resource_type
        self.reason = reason
        super().__init__(f"Resource allocation failed for {execution_id}: {resource_type} - {reason}")


class ExecutionTraceModelOperations:
    """
    MongoDB operations and indexing for ExecutionTraceModel.
    Implements optimized indexing strategy for smart partitioning architecture.
    """
    
    @staticmethod
    def get_indexes() -> List[Dict[str, Any]]:
        """
        Define MongoDB indexes for optimal query performance.
        Supports both embedded and partitioned storage patterns.
        """
        return [
            # Primary lookup indexes
            {
                "keys": {"execution_id": 1},
                "unique": True,
                "name": "execution_id_unique",
                "background": True
            },
            {
                "keys": {"test_case_id": 1, "status": 1, "triggered_at": -1},
                "name": "test_case_status_time_idx",
                "background": True,
                "sparse": True
            },
            {
                "keys": {"test_suite_id": 1, "status": 1, "triggered_at": -1},
                "name": "test_suite_status_time_idx", 
                "background": True,
                "sparse": True
            },
            
            # Performance and monitoring indexes
            {
                "keys": {"status": 1, "triggered_at": -1},
                "name": "status_time_idx",
                "background": True
            },
            {
                "keys": {"triggered_by": 1, "triggered_at": -1},
                "name": "user_time_idx",
                "background": True
            },
            {
                "keys": {"execution_type": 1, "status": 1},
                "name": "type_status_idx",
                "background": True
            },
            
            # Smart partitioning support
            {
                "keys": {"is_partitioned": 1, "step_count_threshold": 1},
                "name": "partitioning_strategy_idx",
                "background": True
            },
            
            # Tags and metadata
            {
                "keys": {"tags": 1},
                "name": "tags_idx",
                "background": True
            },
            
            # Compound query optimization
            {
                "keys": {"triggered_by": 1, "execution_type": 1, "triggered_at": -1},
                "name": "user_type_time_compound_idx",
                "background": True
            }
        ]
    
    @staticmethod 
    async def ensure_indexes(database):
        """Ensure all required indexes exist with proper configuration"""
        collection = database[ExecutionTraceModel.Config.collection_name]
        
        for index_spec in ExecutionTraceModelOperations.get_indexes():
            await collection.create_index(
                index_spec["keys"],
                unique=index_spec.get("unique", False),
                name=index_spec["name"],
                background=index_spec.get("background", True),
                sparse=index_spec.get("sparse", False)
            )
        
        print(f"✅ ExecutionTraceModel indexes ensured: {len(ExecutionTraceModelOperations.get_indexes())} indexes created") 
"""
Orchestration & Recovery Engine - Core Models

Implements the foundation data models for orchestration jobs, execution nodes,
retry policies, and recovery audit trails. Designed for MongoDB storage with
optimized indexing for graph queries and time-series operations.

Key Models:
- OrchestrationJobModel: Core execution metadata and lifecycle management
- OrchestrationNodeModel: Test flow DAG node definition and execution state
- RetryPolicyModel: Policy document for job resubmission and failure handling
- RecoveryAuditModel: Recovery trail for observability and compliance
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


class JobStatus(str, Enum):
    """
    Job execution status enumeration following state machine design.
    Supports comprehensive lifecycle management with recovery states.
    """
    PENDING = "pending"
    QUEUED = "queued"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    RETRYING = "retrying"
    RECOVERING = "recovering"
    ABORTED = "aborted"
    
    @classmethod
    def get_valid_transitions(cls) -> Dict[str, List[str]]:
        """Get valid state transitions for state machine validation"""
        return {
            cls.PENDING: [cls.QUEUED, cls.CANCELLED],
            cls.QUEUED: [cls.SCHEDULED, cls.CANCELLED],
            cls.SCHEDULED: [cls.RUNNING, cls.CANCELLED, cls.PAUSED],
            cls.RUNNING: [cls.COMPLETED, cls.FAILED, cls.CANCELLED, cls.TIMEOUT, cls.PAUSED],
            cls.PAUSED: [cls.RUNNING, cls.CANCELLED],
            cls.COMPLETED: [],
            cls.FAILED: [cls.RETRYING, cls.RECOVERING, cls.ABORTED],
            cls.RETRYING: [cls.QUEUED, cls.ABORTED],
            cls.RECOVERING: [cls.QUEUED, cls.ABORTED],
            cls.CANCELLED: [],
            cls.TIMEOUT: [cls.RETRYING, cls.RECOVERING],
            cls.ABORTED: []
        }
    
    def can_transition_to(self, new_status: 'JobStatus') -> bool:
        """Check if transition to new status is valid"""
        valid_transitions = self.get_valid_transitions()
        return new_status in valid_transitions.get(self, [])


class NodeType(str, Enum):
    """DAG node types for execution flow organization"""
    TEST_CASE = "test_case"
    TEST_SUITE = "test_suite"
    CONDITION = "condition"
    PARALLEL_GROUP = "parallel_group"
    SEQUENTIAL_GROUP = "sequential_group"
    CHECKPOINT = "checkpoint"
    NOTIFICATION = "notification"
    CLEANUP = "cleanup"


class RetryStrategy(str, Enum):
    """Retry strategy enumeration for intelligent failure recovery"""
    IMMEDIATE = "immediate"
    LINEAR_BACKOFF = "linear_backoff"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    FIBONACCI_BACKOFF = "fibonacci_backoff"
    CUSTOM_BACKOFF = "custom_backoff"
    CIRCUIT_BREAKER = "circuit_breaker"
    NONE = "none"


class RecoveryAction(str, Enum):
    """Recovery action types for automated failure handling"""
    RETRY_JOB = "retry_job"
    ROLLBACK_STATE = "rollback_state"
    SKIP_NODE = "skip_node"
    ESCALATE_MANUAL = "escalate_manual"
    ABORT_EXECUTION = "abort_execution"
    REQUEUE_JOB = "requeue_job"
    FALLBACK_STRATEGY = "fallback_strategy"


class OrchestrationJobModel(BaseMongoModel):
    """
    Core orchestration job model with execution metadata and lifecycle management.
    
    Manages the complete lifecycle of test execution jobs including scheduling,
    execution tracking, retry management, and recovery coordination.
    Collection: orchestration_jobs
    """
    
    # Core identification
    job_id: str = Field(..., description="Unique job identifier")
    parent_job_id: Optional[str] = Field(None, description="Parent job ID for hierarchical execution")
    job_name: str = Field(..., description="Human-readable job name")
    job_description: Optional[str] = Field(None, description="Detailed job description")
    
    # Job classification
    job_type: str = Field(..., description="Type of orchestration job")
    priority: int = Field(default=5, ge=1, le=10, description="Job priority (1=highest, 10=lowest)")
    tags: List[str] = Field(default_factory=list, description="Job tags for organization and filtering")
    
    # Execution context
    execution_context: Dict[str, Any] = Field(default_factory=dict, description="Job execution context")
    test_suite_id: Optional[str] = Field(None, description="Associated test suite ID")
    test_case_ids: List[str] = Field(default_factory=list, description="Associated test case IDs")
    
    # Job lifecycle
    status: JobStatus = Field(JobStatus.PENDING, description="Current job status")
    triggered_by: str = Field(..., description="User or system that triggered the job")
    triggered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Job trigger timestamp")
    scheduled_at: Optional[datetime] = Field(None, description="Job scheduled execution time")
    started_at: Optional[datetime] = Field(None, description="Job execution start time")
    completed_at: Optional[datetime] = Field(None, description="Job completion time")
    
    # Execution graph reference
    execution_graph_id: Optional[str] = Field(None, description="Associated execution graph ID")
    current_node_id: Optional[str] = Field(None, description="Currently executing node ID")
    node_execution_path: List[str] = Field(default_factory=list, description="Execution path through nodes")
    
    # Resource allocation
    allocated_resources: Dict[str, Any] = Field(default_factory=dict, description="Allocated execution resources")
    resource_requirements: Dict[str, Any] = Field(default_factory=dict, description="Required execution resources")
    execution_environment: Optional[str] = Field(None, description="Target execution environment")
    
    # Retry and recovery
    retry_count: int = Field(0, ge=0, description="Number of retry attempts")
    max_retries: int = Field(3, ge=0, description="Maximum allowed retries")
    retry_policy_id: Optional[str] = Field(None, description="Associated retry policy ID")
    last_failure_reason: Optional[str] = Field(None, description="Last failure reason")
    recovery_attempts: int = Field(0, ge=0, description="Number of recovery attempts")
    
    # Timing and performance
    estimated_duration_ms: Optional[int] = Field(None, ge=0, description="Estimated execution duration")
    actual_duration_ms: Optional[int] = Field(None, ge=0, description="Actual execution duration")
    timeout_ms: Optional[int] = Field(None, ge=0, description="Execution timeout")
    
    # State management
    state_history: List[Dict[str, Any]] = Field(default_factory=list, description="Job state transition history")
    last_state_change: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last state change timestamp")
    checkpoint_data: Dict[str, Any] = Field(default_factory=dict, description="Job checkpoint data for recovery")
    
    # Results and metrics
    execution_results: Dict[str, Any] = Field(default_factory=dict, description="Job execution results")
    performance_metrics: Dict[str, Any] = Field(default_factory=dict, description="Performance metrics")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Error details if job failed")
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional job metadata")
    configuration: Dict[str, Any] = Field(default_factory=dict, description="Job configuration parameters")
    
    # Collection configuration
    _collection_name: str = "orchestration_jobs"
    
    @model_validator(mode='after')
    def validate_job_consistency(self):
        """Validate job data consistency and business rules"""
        # Validate timing consistency
        if self.completed_at and self.started_at:
            if self.completed_at < self.started_at:
                raise ValueError("Completion time cannot be before start time")
        
        if self.started_at and self.scheduled_at:
            if self.started_at < self.scheduled_at:
                logger.warning(f"Job {self.job_id} started before scheduled time")
        
        # Auto-calculate duration if not provided
        if self.actual_duration_ms is None and self.started_at and self.completed_at:
            duration = (self.completed_at - self.started_at).total_seconds() * 1000
            self.actual_duration_ms = int(duration)
        
        # Validate retry limits
        if self.retry_count > self.max_retries:
            raise ValueError("Retry count cannot exceed max retries")
        
        # Failed jobs should have error details
        if self.status == JobStatus.FAILED and not self.error_details:
            logger.warning(f"Failed job {self.job_id} missing error details")
        
        # Completed jobs should have completion time
        if self.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.ABORTED] and not self.completed_at:
            raise ValueError("Completed jobs must have completion time")
        
        return self
    
    def can_transition_to(self, new_status: JobStatus) -> bool:
        """Check if job can transition to new status"""
        return self.status.can_transition_to(new_status)
    
    def transition_state(self, new_status: JobStatus, reason: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Perform state transition with validation and history tracking.
        Returns True if transition successful, False otherwise.
        """
        if not self.can_transition_to(new_status):
            logger.error(f"Invalid state transition from {self.status} to {new_status} for job {self.job_id}")
            return False
        
        # Record state change in history
        state_change = {
            "from_status": self.status,
            "to_status": new_status,
            "timestamp": datetime.now(timezone.utc),
            "reason": reason,
            "context": context or {}
        }
        self.state_history.append(state_change)
        
        # Update status and timestamp
        old_status = self.status
        self.status = new_status
        self.last_state_change = state_change["timestamp"]
        self.update_timestamp()
        
        logger.info(f"Job {self.job_id} transitioned from {old_status} to {new_status}", extra={
            "job_id": self.job_id,
            "from_status": old_status,
            "to_status": new_status,
            "reason": reason
        })
        
        return True
    
    def increment_retry(self) -> bool:
        """Increment retry count if under limit"""
        if self.retry_count >= self.max_retries:
            return False
        
        self.retry_count += 1
        self.update_timestamp()
        return True


class OrchestrationNodeModel(BaseMongoModel):
    """
    Test flow DAG node definition with execution state management.
    
    Represents individual nodes in the execution graph with dependency
    management, conditional logic, and parallel execution support.
    Collection: orchestration_nodes
    """
    
    # Core identification
    node_id: str = Field(..., description="Unique node identifier")
    job_id: str = Field(..., description="Associated job ID")
    node_name: str = Field(..., description="Human-readable node name")
    node_description: Optional[str] = Field(None, description="Node description")
    
    # Node classification
    node_type: NodeType = Field(..., description="Type of DAG node")
    node_order: int = Field(..., ge=0, description="Execution order within the graph")
    node_level: int = Field(default=0, ge=0, description="Depth level in the execution graph")
    
    # Dependencies
    parent_nodes: List[str] = Field(default_factory=list, description="Parent node IDs (dependencies)")
    child_nodes: List[str] = Field(default_factory=list, description="Child node IDs")
    dependency_condition: str = Field(default="all", description="Dependency condition (all, any, conditional)")
    
    # Execution configuration
    execution_config: Dict[str, Any] = Field(default_factory=dict, description="Node execution configuration")
    test_case_id: Optional[str] = Field(None, description="Associated test case ID")
    test_suite_id: Optional[str] = Field(None, description="Associated test suite ID")
    action_type: str = Field(..., description="Action type to execute")
    action_parameters: Dict[str, Any] = Field(default_factory=dict, description="Action parameters")
    
    # Conditional logic
    condition_expression: Optional[str] = Field(None, description="Conditional execution expression")
    condition_context: Dict[str, Any] = Field(default_factory=dict, description="Condition evaluation context")
    skip_on_failure: bool = Field(False, description="Skip node if dependencies fail")
    
    # Parallel execution
    parallel_group: Optional[str] = Field(None, description="Parallel execution group ID")
    max_parallel_instances: int = Field(1, ge=1, description="Maximum parallel instances")
    current_parallel_instances: int = Field(0, ge=0, description="Current parallel instances")
    
    # Execution state
    execution_status: JobStatus = Field(JobStatus.PENDING, description="Node execution status")
    started_at: Optional[datetime] = Field(None, description="Node execution start time")
    completed_at: Optional[datetime] = Field(None, description="Node execution completion time")
    duration_ms: Optional[int] = Field(None, ge=0, description="Node execution duration")
    
    # Resource requirements
    resource_requirements: Dict[str, Any] = Field(default_factory=dict, description="Resource requirements")
    allocated_resources: Dict[str, Any] = Field(default_factory=dict, description="Allocated resources")
    
    # Results and error handling
    execution_results: Dict[str, Any] = Field(default_factory=dict, description="Node execution results")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Error details if node failed")
    retry_count: int = Field(0, ge=0, description="Node retry count")
    max_retries: int = Field(1, ge=0, description="Maximum node retries")
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional node metadata")
    tags: List[str] = Field(default_factory=list, description="Node tags")
    
    # Collection configuration
    _collection_name: str = "orchestration_nodes"
    
    @model_validator(mode='after')
    def validate_node_consistency(self):
        """Validate node data consistency"""
        # Validate timing consistency
        if self.completed_at and self.started_at:
            if self.completed_at < self.started_at:
                raise ValueError("Completion time cannot be before start time")
        
        # Auto-calculate duration
        if self.duration_ms is None and self.started_at and self.completed_at:
            duration = (self.completed_at - self.started_at).total_seconds() * 1000
            self.duration_ms = int(duration)
        
        # Validate parallel execution limits
        if self.current_parallel_instances > self.max_parallel_instances:
            raise ValueError("Current parallel instances cannot exceed maximum")
        
        # Validate dependency condition
        valid_conditions = ["all", "any", "conditional"]
        if self.dependency_condition not in valid_conditions:
            raise ValueError(f"Dependency condition must be one of {valid_conditions}")
        
        # Conditional nodes must have condition expression
        if self.node_type == NodeType.CONDITION and not self.condition_expression:
            raise ValueError("Condition nodes must have condition expression")
        
        return self
    
    def can_execute(self, parent_results: Dict[str, JobStatus]) -> bool:
        """Check if node can execute based on parent node results"""
        if not self.parent_nodes:
            return True  # No dependencies
        
        if self.dependency_condition == "all":
            return all(parent_results.get(pid) == JobStatus.COMPLETED for pid in self.parent_nodes)
        elif self.dependency_condition == "any":
            return any(parent_results.get(pid) == JobStatus.COMPLETED for pid in self.parent_nodes)
        elif self.dependency_condition == "conditional":
            # Custom conditional logic would be evaluated here
            return True  # Placeholder for conditional logic
        
        return False


class RetryPolicyModel(BaseMongoModel):
    """
    Retry policy configuration for intelligent failure recovery.
    
    Defines retry strategies, backoff algorithms, circuit breaker patterns,
    and failure escalation procedures for robust failure handling.
    Collection: retry_policies
    """
    
    # Core identification
    policy_id: str = Field(..., description="Unique policy identifier")
    policy_name: str = Field(..., description="Human-readable policy name")
    policy_description: Optional[str] = Field(None, description="Policy description")
    
    # Policy configuration
    strategy: RetryStrategy = Field(..., description="Retry strategy type")
    max_attempts: int = Field(3, ge=1, le=10, description="Maximum retry attempts")
    base_delay_ms: int = Field(1000, ge=100, description="Base delay between retries in milliseconds")
    max_delay_ms: int = Field(60000, ge=1000, description="Maximum delay between retries")
    
    # Backoff configuration
    backoff_multiplier: float = Field(2.0, ge=1.0, le=10.0, description="Backoff multiplier for exponential strategy")
    jitter_enabled: bool = Field(True, description="Enable jitter to prevent thundering herd")
    jitter_range: float = Field(0.1, ge=0.0, le=1.0, description="Jitter range as fraction of delay")
    
    # Circuit breaker configuration
    circuit_breaker_enabled: bool = Field(False, description="Enable circuit breaker pattern")
    failure_threshold: int = Field(5, ge=1, description="Failures before opening circuit")
    success_threshold: int = Field(3, ge=1, description="Successes needed to close circuit")
    circuit_timeout_ms: int = Field(30000, ge=1000, description="Circuit breaker timeout")
    
    # Failure classification
    retryable_error_types: List[str] = Field(default_factory=list, description="Error types eligible for retry")
    non_retryable_error_types: List[str] = Field(default_factory=list, description="Error types not eligible for retry")
    escalation_conditions: List[str] = Field(default_factory=list, description="Conditions triggering escalation")
    
    # Context-aware retry
    context_conditions: Dict[str, Any] = Field(default_factory=dict, description="Context-based retry conditions")
    resource_constraints: Dict[str, Any] = Field(default_factory=dict, description="Resource-based retry constraints")
    time_window_constraints: Dict[str, Any] = Field(default_factory=dict, description="Time window retry constraints")
    
    # Escalation and fallback
    escalation_policy: Optional[str] = Field(None, description="Escalation policy ID")
    fallback_strategy: Optional[str] = Field(None, description="Fallback strategy")
    manual_intervention_required: bool = Field(False, description="Require manual intervention after max attempts")
    
    # Effectiveness tracking
    success_rate: float = Field(0.0, ge=0.0, le=1.0, description="Historical success rate")
    average_attempts: float = Field(0.0, ge=0.0, description="Average attempts to success")
    last_effectiveness_update: Optional[datetime] = Field(None, description="Last effectiveness calculation")
    
    # Metadata
    applicable_job_types: List[str] = Field(default_factory=list, description="Job types this policy applies to")
    tags: List[str] = Field(default_factory=list, description="Policy tags")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional policy metadata")
    
    # Collection configuration
    _collection_name: str = "retry_policies"
    
    @model_validator(mode='after')
    def validate_policy_consistency(self):
        """Validate retry policy configuration"""
        # Validate delay constraints
        if self.base_delay_ms >= self.max_delay_ms:
            raise ValueError("Base delay must be less than max delay")
        
        # Validate circuit breaker configuration
        if self.circuit_breaker_enabled:
            if self.failure_threshold <= 0 or self.success_threshold <= 0:
                raise ValueError("Circuit breaker thresholds must be positive")
        
        # Validate backoff multiplier for exponential strategy
        if self.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            if self.backoff_multiplier <= 1.0:
                raise ValueError("Exponential backoff multiplier must be greater than 1.0")
        
        # Validate jitter range
        if self.jitter_range < 0 or self.jitter_range > 1.0:
            raise ValueError("Jitter range must be between 0.0 and 1.0")
        
        return self
    
    def calculate_delay(self, attempt: int) -> int:
        """Calculate retry delay for given attempt number"""
        if attempt <= 0:
            return 0
        
        delay = self.base_delay_ms
        
        if self.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.base_delay_ms * attempt
        elif self.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.base_delay_ms * (self.backoff_multiplier ** (attempt - 1))
        elif self.strategy == RetryStrategy.FIBONACCI_BACKOFF:
            fib_sequence = [1, 1]
            for i in range(2, attempt + 1):
                fib_sequence.append(fib_sequence[i-1] + fib_sequence[i-2])
            delay = self.base_delay_ms * fib_sequence[min(attempt, len(fib_sequence) - 1)]
        
        # Apply maximum delay limit
        delay = min(delay, self.max_delay_ms)
        
        # Apply jitter if enabled
        if self.jitter_enabled:
            import random
            jitter = random.uniform(-self.jitter_range, self.jitter_range)
            delay = int(delay * (1 + jitter))
        
        return max(delay, 0)


class RecoveryAuditModel(BaseMongoModel):
    """
    Recovery audit trail for observability and compliance tracking.
    
    Records all recovery actions, state changes, and intervention points
    for comprehensive audit trails and compliance reporting.
    Collection: recovery_audits
    """
    
    # Core identification
    audit_id: str = Field(..., description="Unique audit record identifier")
    job_id: str = Field(..., description="Associated job ID")
    node_id: Optional[str] = Field(None, description="Associated node ID if applicable")
    recovery_session_id: str = Field(..., description="Recovery session identifier")
    
    # Recovery context
    recovery_action: RecoveryAction = Field(..., description="Type of recovery action taken")
    trigger_reason: str = Field(..., description="Reason that triggered recovery")
    failure_classification: str = Field(..., description="Classification of the original failure")
    recovery_strategy: str = Field(..., description="Recovery strategy applied")
    
    # State information
    state_before: Dict[str, Any] = Field(default_factory=dict, description="System state before recovery")
    state_after: Dict[str, Any] = Field(default_factory=dict, description="System state after recovery")
    affected_components: List[str] = Field(default_factory=list, description="Components affected by recovery")
    
    # Recovery execution
    recovery_started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Recovery start time")
    recovery_completed_at: Optional[datetime] = Field(None, description="Recovery completion time")
    recovery_duration_ms: Optional[int] = Field(None, ge=0, description="Recovery duration in milliseconds")
    recovery_success: Optional[bool] = Field(None, description="Recovery success status")
    
    # Actions taken
    actions_performed: List[Dict[str, Any]] = Field(default_factory=list, description="Detailed recovery actions")
    rollback_operations: List[Dict[str, Any]] = Field(default_factory=list, description="Rollback operations performed")
    manual_interventions: List[Dict[str, Any]] = Field(default_factory=list, description="Manual interventions required")
    
    # Impact assessment
    data_integrity_verified: bool = Field(False, description="Data integrity verification status")
    resource_cleanup_completed: bool = Field(False, description="Resource cleanup completion status")
    downstream_impact: List[str] = Field(default_factory=list, description="Downstream systems impacted")
    
    # Escalation and notifications
    escalated_to: Optional[str] = Field(None, description="Escalation target (user/team)")
    escalation_reason: Optional[str] = Field(None, description="Reason for escalation")
    notifications_sent: List[Dict[str, Any]] = Field(default_factory=list, description="Notifications sent during recovery")
    
    # Performance and metrics
    recovery_metrics: Dict[str, Any] = Field(default_factory=dict, description="Recovery performance metrics")
    resource_usage: Dict[str, Any] = Field(default_factory=dict, description="Resource usage during recovery")
    effectiveness_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Recovery effectiveness score")
    
    # Compliance and audit
    compliance_requirements: List[str] = Field(default_factory=list, description="Compliance requirements addressed")
    audit_trail: List[Dict[str, Any]] = Field(default_factory=list, description="Detailed audit trail")
    evidence_preserved: List[str] = Field(default_factory=list, description="Evidence preserved for analysis")
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional audit metadata")
    tags: List[str] = Field(default_factory=list, description="Audit tags")
    
    # Collection configuration
    _collection_name: str = "recovery_audits"
    
    @model_validator(mode='after')
    def validate_audit_consistency(self):
        """Validate recovery audit data consistency"""
        # Validate timing consistency
        if self.recovery_completed_at and self.recovery_started_at:
            if self.recovery_completed_at < self.recovery_started_at:
                raise ValueError("Recovery completion time cannot be before start time")
        
        # Auto-calculate duration
        if self.recovery_duration_ms is None and self.recovery_started_at and self.recovery_completed_at:
            duration = (self.recovery_completed_at - self.recovery_started_at).total_seconds() * 1000
            self.recovery_duration_ms = int(duration)
        
        # Completed recovery should have success status
        if self.recovery_completed_at and self.recovery_success is None:
            logger.warning(f"Completed recovery {self.audit_id} missing success status")
        
        return self
    
    def mark_completed(self, success: bool, metrics: Optional[Dict[str, Any]] = None):
        """Mark recovery as completed with success status and metrics"""
        self.recovery_completed_at = datetime.now(timezone.utc)
        self.recovery_success = success
        if metrics:
            self.recovery_metrics.update(metrics)
        
        # Calculate duration
        if self.recovery_started_at:
            duration = (self.recovery_completed_at - self.recovery_started_at).total_seconds() * 1000
            self.recovery_duration_ms = int(duration)
        
        self.update_timestamp()


# Exception Classes
class OrchestrationException(Exception):
    """Base exception for orchestration-related errors"""
    
    def __init__(self, message: str, job_id: Optional[str] = None, error_code: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.job_id = job_id
        self.error_code = error_code
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/API response"""
        return {
            "exception_type": self.__class__.__name__,
            "message": self.message,
            "job_id": self.job_id,
            "error_code": self.error_code,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


class InvalidJobStateError(OrchestrationException):
    """Exception for invalid job state transitions"""
    
    def __init__(self, job_id: str, current_state: JobStatus, attempted_state: JobStatus):
        message = f"Invalid state transition from {current_state} to {attempted_state} for job {job_id}"
        super().__init__(message, job_id, "INVALID_STATE_TRANSITION")
        self.current_state = current_state
        self.attempted_state = attempted_state


class RetryPolicyError(OrchestrationException):
    """Exception for retry policy configuration or execution errors"""
    
    def __init__(self, message: str, policy_id: Optional[str] = None, job_id: Optional[str] = None):
        super().__init__(message, job_id, "RETRY_POLICY_ERROR")
        self.policy_id = policy_id


class RecoveryProcessError(OrchestrationException):
    """Exception for recovery process errors"""
    
    def __init__(self, message: str, recovery_session_id: Optional[str] = None, job_id: Optional[str] = None):
        super().__init__(message, job_id, "RECOVERY_PROCESS_ERROR")
        self.recovery_session_id = recovery_session_id


# MongoDB Index Definitions
class OrchestrationModelOperations:
    """
    Helper class for MongoDB operations on orchestration documents.
    Provides database interaction methods with proper error handling and indexing.
    """
    
    @staticmethod
    def get_orchestration_job_indexes() -> List[Dict[str, Any]]:
        """Get MongoDB indexes for orchestration_jobs collection"""
        return [
            # Primary query indexes
            {"keys": [("job_id", 1)], "unique": True, "name": "idx_job_id"},
            {"keys": [("status", 1)], "name": "idx_status"},
            {"keys": [("priority", 1), ("triggered_at", 1)], "name": "idx_priority_triggered"},
            
            # Scheduling and execution indexes
            {"keys": [("scheduled_at", 1)], "name": "idx_scheduled_at"},
            {"keys": [("triggered_by", 1), ("triggered_at", -1)], "name": "idx_triggered_by_time"},
            {"keys": [("job_type", 1), ("status", 1)], "name": "idx_type_status"},
            
            # Retry and recovery indexes
            {"keys": [("retry_count", 1), ("max_retries", 1)], "name": "idx_retry_limits"},
            {"keys": [("retry_policy_id", 1)], "name": "idx_retry_policy"},
            
            # Hierarchical job indexes
            {"keys": [("parent_job_id", 1)], "name": "idx_parent_job"},
            {"keys": [("test_suite_id", 1)], "name": "idx_test_suite"},
            
            # Performance optimization indexes
            {"keys": [("execution_graph_id", 1)], "name": "idx_execution_graph"},
            {"keys": [("status", 1), ("priority", 1), ("triggered_at", 1)], "name": "idx_status_priority_time"},
            
            # Audit and monitoring indexes
            {"keys": [("created_at", -1)], "name": "idx_created_at_desc"},
            {"keys": [("updated_at", -1)], "name": "idx_updated_at_desc"},
            {"keys": [("tags", 1)], "name": "idx_tags"},
        ]
    
    @staticmethod
    def get_orchestration_node_indexes() -> List[Dict[str, Any]]:
        """Get MongoDB indexes for orchestration_nodes collection"""
        return [
            # Primary query indexes
            {"keys": [("node_id", 1)], "unique": True, "name": "idx_node_id"},
            {"keys": [("job_id", 1), ("node_order", 1)], "name": "idx_job_node_order"},
            {"keys": [("job_id", 1), ("execution_status", 1)], "name": "idx_job_status"},
            
            # Graph traversal indexes
            {"keys": [("parent_nodes", 1)], "name": "idx_parent_nodes"},
            {"keys": [("child_nodes", 1)], "name": "idx_child_nodes"},
            {"keys": [("node_level", 1), ("node_order", 1)], "name": "idx_level_order"},
            
            # Parallel execution indexes
            {"keys": [("parallel_group", 1)], "name": "idx_parallel_group"},
            {"keys": [("job_id", 1), ("parallel_group", 1)], "name": "idx_job_parallel_group"},
            
            # Type and classification indexes
            {"keys": [("node_type", 1)], "name": "idx_node_type"},
            {"keys": [("action_type", 1)], "name": "idx_action_type"},
            
            # Test reference indexes
            {"keys": [("test_case_id", 1)], "name": "idx_test_case"},
            {"keys": [("test_suite_id", 1)], "name": "idx_test_suite"},
        ]
    
    @staticmethod
    def get_retry_policy_indexes() -> List[Dict[str, Any]]:
        """Get MongoDB indexes for retry_policies collection"""
        return [
            # Primary query indexes
            {"keys": [("policy_id", 1)], "unique": True, "name": "idx_policy_id"},
            {"keys": [("policy_name", 1)], "name": "idx_policy_name"},
            {"keys": [("strategy", 1)], "name": "idx_strategy"},
            
            # Application indexes
            {"keys": [("applicable_job_types", 1)], "name": "idx_applicable_job_types"},
            {"keys": [("tags", 1)], "name": "idx_tags"},
            
            # Effectiveness tracking indexes
            {"keys": [("success_rate", -1)], "name": "idx_success_rate"},
            {"keys": [("last_effectiveness_update", -1)], "name": "idx_effectiveness_update"},
        ]
    
    @staticmethod
    def get_recovery_audit_indexes() -> List[Dict[str, Any]]:
        """Get MongoDB indexes for recovery_audits collection"""
        return [
            # Primary query indexes
            {"keys": [("audit_id", 1)], "unique": True, "name": "idx_audit_id"},
            {"keys": [("job_id", 1), ("recovery_started_at", -1)], "name": "idx_job_recovery_time"},
            {"keys": [("recovery_session_id", 1)], "name": "idx_recovery_session"},
            
            # Recovery analysis indexes
            {"keys": [("recovery_action", 1)], "name": "idx_recovery_action"},
            {"keys": [("recovery_success", 1)], "name": "idx_recovery_success"},
            {"keys": [("failure_classification", 1)], "name": "idx_failure_classification"},
            
            # Compliance and audit indexes
            {"keys": [("compliance_requirements", 1)], "name": "idx_compliance_requirements"},
            {"keys": [("escalated_to", 1)], "name": "idx_escalated_to"},
            
            # Performance indexes
            {"keys": [("recovery_started_at", -1)], "name": "idx_recovery_started_desc"},
            {"keys": [("effectiveness_score", -1)], "name": "idx_effectiveness_score"},
        ] 
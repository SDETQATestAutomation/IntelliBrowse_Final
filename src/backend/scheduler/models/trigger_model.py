"""
Scheduled Task Runner Engine - Core Models

Implements the foundation data models for scheduled triggers, job execution tracking,
and distributed locking. Designed for MongoDB storage with optimized indexing
strategies for time-series operations and concurrent execution scenarios.

Key Models:
- ScheduledTriggerModel: Cron expression, timezone, trigger type definitions  
- ScheduledJobModel: Job execution metadata with retry tracking
- ExecutionLockModel: TTL-based distributed locking for multi-instance coordination

Features:
- UTC-aware datetime handling with timezone support
- Comprehensive validation with Pydantic
- Optimized MongoDB indexing for performance at scale
- State machine validation for job lifecycle
- Automatic TTL cleanup for locks and historical data
"""

from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from bson import ObjectId
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict

from ...config.logging import get_logger
from ...orchestration.models.orchestration_models import BaseMongoModel

logger = get_logger(__name__)


class TriggerType(str, Enum):
    """
    Trigger type enumeration for comprehensive scheduling support.
    Supports time-based, event-driven, and dependency-based triggers.
    """
    TIME_BASED = "time_based"          # Cron expressions and intervals
    EVENT_DRIVEN = "event_driven"      # System/external event triggers
    DEPENDENT = "dependent"            # Job dependency triggers
    MANUAL = "manual"                  # On-demand execution
    CONDITIONAL = "conditional"        # Conditional logic triggers
    WEBHOOK = "webhook"                # HTTP webhook triggers


class TaskStatus(str, Enum):
    """
    Task status enumeration following state machine design.
    Supports comprehensive lifecycle management with validation.
    """
    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled" 
    ARCHIVED = "archived"
    
    @classmethod
    def get_valid_transitions(cls) -> Dict[str, List[str]]:
        """Get valid state transitions for state machine validation"""
        return {
            cls.ACTIVE: [cls.PAUSED, cls.DISABLED, cls.ARCHIVED],
            cls.PAUSED: [cls.ACTIVE, cls.DISABLED, cls.ARCHIVED],
            cls.DISABLED: [cls.ACTIVE, cls.ARCHIVED],
            cls.ARCHIVED: []  # Terminal state
        }
    
    def can_transition_to(self, new_status: 'TaskStatus') -> bool:
        """Check if transition to new status is valid"""
        valid_transitions = self.get_valid_transitions()
        return new_status in valid_transitions.get(self, [])


class ExecutionStatus(str, Enum):
    """
    Execution status enumeration for job lifecycle tracking.
    Provides granular status tracking with recovery support.
    """
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    RETRYING = "retrying"
    ABORTED = "aborted"
    
    @classmethod
    def get_terminal_statuses(cls) -> List[str]:
        """Get statuses that represent terminal execution states"""
        return [cls.COMPLETED, cls.ABORTED, cls.CANCELLED]
    
    @classmethod
    def get_active_statuses(cls) -> List[str]:
        """Get statuses that represent active execution states"""
        return [cls.PENDING, cls.QUEUED, cls.RUNNING, cls.RETRYING]
    
    def is_terminal(self) -> bool:
        """Check if this status represents a terminal state"""
        return self in self.get_terminal_statuses()
    
    def is_active(self) -> bool:
        """Check if this status represents an active execution"""
        return self in self.get_active_statuses()


class ScheduledTriggerModel(BaseMongoModel):
    """
    Core model for scheduled task trigger definitions.
    
    Manages trigger configuration including cron expressions, timezone handling,
    event-driven triggers, and dependency relationships. Optimized for scalable
    task scheduling with comprehensive validation and error handling.
    
    Collection: scheduled_triggers
    """
    
    # Core identification  
    trigger_id: str = Field(..., description="Unique trigger identifier")
    name: str = Field(..., max_length=200, description="Human-readable trigger name")
    description: Optional[str] = Field(None, max_length=1000, description="Trigger description")
    
    # Trigger configuration
    trigger_type: TriggerType = Field(..., description="Type of trigger mechanism")
    status: TaskStatus = Field(TaskStatus.ACTIVE, description="Current trigger status")
    
    # Time-based configuration (for TIME_BASED triggers)
    cron_expression: Optional[str] = Field(None, description="Cron expression for time-based triggers")
    timezone: str = Field("UTC", description="Timezone for cron expression evaluation")
    interval_seconds: Optional[int] = Field(None, ge=1, description="Interval in seconds for simple recurring tasks")
    
    # Event-driven configuration (for EVENT_DRIVEN triggers)
    event_types: List[str] = Field(default_factory=list, description="Event types that trigger execution")
    event_filters: Dict[str, Any] = Field(default_factory=dict, description="Event filtering criteria")
    webhook_config: Dict[str, Any] = Field(default_factory=dict, description="Webhook configuration for HTTP triggers")
    
    # Dependency configuration (for DEPENDENT triggers)
    dependency_job_ids: List[str] = Field(default_factory=list, description="Job IDs this trigger depends on")
    dependency_condition: str = Field("all_success", description="Dependency condition (all_success, any_success, all_complete)")
    
    # Conditional logic
    condition_expression: Optional[str] = Field(None, description="Boolean expression for conditional triggers")
    condition_context: Dict[str, Any] = Field(default_factory=dict, description="Context for condition evaluation")
    
    # Execution timing
    next_execution: Optional[datetime] = Field(None, description="Next scheduled execution time")
    last_execution: Optional[datetime] = Field(None, description="Last execution time")
    execution_window_start: Optional[str] = Field(None, description="Execution window start time (HH:MM format)")
    execution_window_end: Optional[str] = Field(None, description="Execution window end time (HH:MM format)")
    
    # Task configuration  
    task_type: str = Field(..., description="Type of task to execute")
    task_config: Dict[str, Any] = Field(default_factory=dict, description="Task execution configuration")
    task_parameters: Dict[str, Any] = Field(default_factory=dict, description="Task execution parameters")
    
    # Resource and execution limits
    max_execution_time_seconds: int = Field(default=3600, ge=1, description="Maximum execution time limit")
    max_concurrent_executions: int = Field(default=1, ge=1, description="Maximum concurrent executions")
    current_executions: int = Field(default=0, ge=0, description="Current active executions")
    
    # Retry configuration
    max_retries: int = Field(default=3, ge=0, description="Maximum retry attempts")
    retry_interval_seconds: int = Field(default=60, ge=1, description="Interval between retries")
    retry_backoff_multiplier: float = Field(default=2.0, ge=1.0, description="Backoff multiplier for retries")
    
    # User context and permissions
    created_by: str = Field(..., description="User who created the trigger")
    organization_id: str = Field(..., description="Organization scope")
    team_id: Optional[str] = Field(None, description="Team scope")
    permissions: Dict[str, Any] = Field(default_factory=dict, description="Access control permissions")
    
    # Execution history tracking
    total_executions: int = Field(default=0, ge=0, description="Total number of executions")
    successful_executions: int = Field(default=0, ge=0, description="Number of successful executions")
    failed_executions: int = Field(default=0, ge=0, description="Number of failed executions")
    average_execution_time_seconds: Optional[float] = Field(None, ge=0, description="Average execution time")
    
    # Metadata and tags
    tags: List[str] = Field(default_factory=list, description="Trigger tags for organization")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional trigger metadata")
    
    # Collection configuration
    _collection_name: str = "scheduled_triggers"
    
    @field_validator('cron_expression')
    @classmethod
    def validate_cron_expression(cls, v, info):
        """Validate cron expression format"""
        if v is None:
            return v
        
        # Basic cron validation - 5 or 6 fields
        fields = v.strip().split()
        if len(fields) not in [5, 6]:
            raise ValueError("Cron expression must have 5 or 6 fields")
        
        # TODO: Add croniter validation for production
        logger.debug(f"Cron expression validated: {v}")
        return v
    
    @field_validator('timezone')
    @classmethod  
    def validate_timezone(cls, v):
        """Validate timezone string"""
        # Basic timezone validation
        try:
            # This would use pytz in production
            if v not in ['UTC', 'America/New_York', 'Europe/London', 'Asia/Tokyo']:
                logger.warning(f"Timezone {v} not in common list, using as-is")
            return v
        except Exception as e:
            logger.error(f"Invalid timezone {v}: {e}")
            raise ValueError(f"Invalid timezone: {v}")
    
    @model_validator(mode='after')
    def validate_trigger_configuration(self):
        """Validate trigger configuration consistency"""
        if self.trigger_type == TriggerType.TIME_BASED:
            if not self.cron_expression and not self.interval_seconds:
                raise ValueError("TIME_BASED triggers must have either cron_expression or interval_seconds")
        
        elif self.trigger_type == TriggerType.EVENT_DRIVEN:
            if not self.event_types and not self.webhook_config:
                raise ValueError("EVENT_DRIVEN triggers must have event_types or webhook_config")
        
        elif self.trigger_type == TriggerType.DEPENDENT:
            if not self.dependency_job_ids:
                raise ValueError("DEPENDENT triggers must have dependency_job_ids")
        
        if self.execution_window_start and self.execution_window_end:
            # Validate time format (HH:MM)
            try:
                start_parts = self.execution_window_start.split(':')
                end_parts = self.execution_window_end.split(':')
                
                if len(start_parts) != 2 or len(end_parts) != 2:
                    raise ValueError("Execution window times must be in HH:MM format")
                
                start_hour, start_min = int(start_parts[0]), int(start_parts[1])
                end_hour, end_min = int(end_parts[0]), int(end_parts[1])
                
                if not (0 <= start_hour <= 23 and 0 <= start_min <= 59):
                    raise ValueError("Invalid execution window start time")
                if not (0 <= end_hour <= 23 and 0 <= end_min <= 59):
                    raise ValueError("Invalid execution window end time")
                    
            except (ValueError, IndexError):
                raise ValueError("Execution window times must be valid HH:MM format")
        
        return self
    
    def can_execute_now(self) -> bool:
        """Check if trigger can execute at current time"""
        if self.status != TaskStatus.ACTIVE:
            return False
        
        if self.current_executions >= self.max_concurrent_executions:
            return False
        
        # Check execution window
        if self.execution_window_start and self.execution_window_end:
            current_time = datetime.now(timezone.utc).strftime("%H:%M")
            if not (self.execution_window_start <= current_time <= self.execution_window_end):
                return False
        
        return True
    
    def increment_execution_stats(self, success: bool, execution_time_seconds: float):
        """Update execution statistics"""
        self.total_executions += 1
        if success:
            self.successful_executions += 1
        else:
            self.failed_executions += 1
        
        # Update average execution time
        if self.average_execution_time_seconds is None:
            self.average_execution_time_seconds = execution_time_seconds
        else:
            # Weighted average with recent executions having more weight
            weight = 0.8  # Weight for existing average
            self.average_execution_time_seconds = (
                weight * self.average_execution_time_seconds + 
                (1 - weight) * execution_time_seconds
            )
        
        self.update_timestamp()


class ScheduledJobModel(BaseMongoModel):
    """
    Model for tracking individual scheduled job executions.
    
    Records execution lifecycle, retry attempts, resource usage, and performance
    metrics for comprehensive job monitoring and debugging. Optimized for 
    time-series analysis and operational observability.
    
    Collection: scheduled_jobs
    """
    
    # Core identification
    job_id: str = Field(..., description="Unique job execution identifier")
    trigger_id: str = Field(..., description="Associated trigger ID")
    execution_id: str = Field(..., description="Unique execution instance ID")
    
    # Execution context
    job_type: str = Field(..., description="Type of job being executed")
    task_parameters: Dict[str, Any] = Field(default_factory=dict, description="Task execution parameters")
    execution_context: Dict[str, Any] = Field(default_factory=dict, description="Job execution context")
    
    # Scheduling information
    scheduled_time: datetime = Field(..., description="When job was scheduled to run")
    trigger_type: TriggerType = Field(..., description="Type of trigger that initiated job")
    trigger_source: str = Field(..., description="Source that triggered the execution")
    
    # Execution lifecycle
    status: ExecutionStatus = Field(ExecutionStatus.PENDING, description="Current execution status")
    queued_at: Optional[datetime] = Field(None, description="When job was queued")
    started_at: Optional[datetime] = Field(None, description="Execution start time")
    completed_at: Optional[datetime] = Field(None, description="Execution completion time")
    duration_seconds: Optional[float] = Field(None, ge=0, description="Total execution duration")
    
    # Execution environment
    worker_instance_id: str = Field(..., description="Worker instance executing the job")
    execution_environment: Dict[str, Any] = Field(default_factory=dict, description="Execution environment details")
    resource_allocation: Dict[str, Any] = Field(default_factory=dict, description="Allocated resources")
    
    # Results and output
    execution_result: Optional[Dict[str, Any]] = Field(None, description="Job execution results")
    output_data: Optional[Dict[str, Any]] = Field(None, description="Job output data")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Error details if execution failed")
    exit_code: Optional[int] = Field(None, description="Job exit code")
    
    # Retry management
    retry_attempt: int = Field(default=0, ge=0, description="Current retry attempt number")
    max_retries: int = Field(default=3, ge=0, description="Maximum allowed retries")
    retry_reason: Optional[str] = Field(None, description="Reason for retry if applicable")
    next_retry_at: Optional[datetime] = Field(None, description="Scheduled time for next retry")
    retry_history: List[Dict[str, Any]] = Field(default_factory=list, description="History of retry attempts")
    
    # Performance metrics
    cpu_usage_percent: Optional[float] = Field(None, ge=0, le=100, description="CPU usage percentage")
    memory_usage_mb: Optional[float] = Field(None, ge=0, description="Memory usage in MB")
    disk_io_mb: Optional[float] = Field(None, ge=0, description="Disk I/O in MB")
    network_io_mb: Optional[float] = Field(None, ge=0, description="Network I/O in MB")
    performance_metrics: Dict[str, Any] = Field(default_factory=dict, description="Additional performance metrics")
    
    # Lock and concurrency
    execution_lock_id: Optional[str] = Field(None, description="Associated execution lock ID")
    concurrent_execution_group: Optional[str] = Field(None, description="Concurrent execution group")
    lock_acquired_at: Optional[datetime] = Field(None, description="When execution lock was acquired")
    
    # User and organizational context
    triggered_by: str = Field(..., description="User or system that triggered execution")
    organization_id: str = Field(..., description="Organization scope")
    team_id: Optional[str] = Field(None, description="Team scope")
    
    # Metadata and debugging
    debug_info: Dict[str, Any] = Field(default_factory=dict, description="Debug information")
    logs: List[Dict[str, Any]] = Field(default_factory=list, description="Execution logs")
    tags: List[str] = Field(default_factory=list, description="Job tags")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional job metadata")
    
    # Collection configuration
    _collection_name: str = "scheduled_jobs"
    
    @model_validator(mode='after')
    def validate_job_timing(self):
        """Validate job timing consistency"""
        if self.started_at and self.queued_at:
            if self.started_at < self.queued_at:
                raise ValueError("Start time cannot be before queue time")
        
        if self.completed_at and self.started_at:
            if self.completed_at < self.started_at:
                raise ValueError("Completion time cannot be before start time")
            
            # Calculate duration if not set
            if self.duration_seconds is None:
                delta = self.completed_at - self.started_at
                self.duration_seconds = delta.total_seconds()
        
        return self
    
    def mark_started(self, worker_instance_id: str):
        """Mark job as started"""
        self.status = ExecutionStatus.RUNNING
        self.started_at = datetime.now(timezone.utc)
        self.worker_instance_id = worker_instance_id
        self.update_timestamp()
    
    def mark_completed(self, success: bool, result_data: Optional[Dict[str, Any]] = None, 
                      error_details: Optional[Dict[str, Any]] = None):
        """Mark job as completed"""
        self.completed_at = datetime.now(timezone.utc)
        self.status = ExecutionStatus.COMPLETED if success else ExecutionStatus.FAILED
        
        if result_data:
            self.execution_result = result_data
        
        if error_details:
            self.error_details = error_details
        
        if self.started_at:
            self.duration_seconds = (self.completed_at - self.started_at).total_seconds()
        
        self.update_timestamp()
    
    def should_retry(self) -> bool:
        """Check if job should be retried"""
        return (self.status == ExecutionStatus.FAILED and 
                self.retry_attempt < self.max_retries)
    
    def schedule_retry(self, delay_seconds: int = 60):
        """Schedule next retry attempt"""
        if not self.should_retry():
            return False
        
        self.retry_attempt += 1
        self.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
        self.status = ExecutionStatus.RETRYING
        
        # Add to retry history
        self.retry_history.append({
            "attempt": self.retry_attempt,
            "scheduled_at": self.next_retry_at.isoformat(),
            "reason": self.retry_reason or "Automatic retry",
            "delay_seconds": delay_seconds
        })
        
        self.update_timestamp()
        return True


class ExecutionLockModel(BaseMongoModel):
    """
    Model for distributed execution locking using MongoDB TTL.
    
    Implements distributed locking mechanism to prevent duplicate executions
    across multiple worker instances. Uses MongoDB TTL for automatic cleanup
    and dead lock prevention.
    
    Collection: execution_locks
    """
    
    # Core identification - Using compound key for uniqueness
    lock_id: str = Field(..., description="Unique lock identifier")
    resource_type: str = Field(..., description="Type of resource being locked")
    resource_id: str = Field(..., description="ID of resource being locked")
    
    # Lock ownership
    owner_instance_id: str = Field(..., description="Worker instance that owns the lock")
    owner_process_id: str = Field(..., description="Process ID of lock owner")
    owner_thread_id: Optional[str] = Field(None, description="Thread ID of lock owner")
    
    # Lock timing with TTL support
    acquired_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Lock acquisition time")
    expires_at: datetime = Field(..., description="Lock expiration time (TTL)")
    lock_duration_seconds: int = Field(..., ge=1, description="Lock duration in seconds")
    
    # Lock configuration
    lock_type: str = Field(default="exclusive", description="Type of lock (exclusive, shared)")
    auto_extend: bool = Field(default=False, description="Automatically extend lock before expiration")
    max_extensions: int = Field(default=5, ge=0, description="Maximum number of automatic extensions")
    current_extensions: int = Field(default=0, ge=0, description="Current number of extensions")
    
    # Associated execution context
    job_id: Optional[str] = Field(None, description="Associated job ID")
    trigger_id: Optional[str] = Field(None, description="Associated trigger ID")
    execution_context: Dict[str, Any] = Field(default_factory=dict, description="Lock context information")
    
    # Lock status and health
    is_active: bool = Field(default=True, description="Lock active status")
    heartbeat_interval_seconds: int = Field(default=30, ge=1, description="Heartbeat interval")
    last_heartbeat: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last heartbeat time")
    heartbeat_failures: int = Field(default=0, ge=0, description="Number of consecutive heartbeat failures")
    
    # Performance and debugging
    acquisition_latency_ms: Optional[float] = Field(None, ge=0, description="Lock acquisition latency")
    contention_count: int = Field(default=0, ge=0, description="Number of lock contention events")
    lock_metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional lock metadata")
    
    # Collection configuration
    _collection_name: str = "execution_locks"
    
    @model_validator(mode='after')
    def validate_lock_timing(self):
        """Validate lock timing configuration"""
        if self.expires_at <= self.acquired_at:
            raise ValueError("Lock expiration time must be after acquisition time")
        
        # Validate lock duration matches calculated duration
        calculated_duration = (self.expires_at - self.acquired_at).total_seconds()
        if abs(calculated_duration - self.lock_duration_seconds) > 1:  # 1 second tolerance
            logger.warning(f"Lock duration mismatch: calculated={calculated_duration}, specified={self.lock_duration_seconds}")
        
        return self
    
    def is_expired(self) -> bool:
        """Check if lock has expired"""
        return datetime.now(timezone.utc) >= self.expires_at
    
    def time_until_expiry(self) -> float:
        """Get time until lock expiry in seconds"""
        delta = self.expires_at - datetime.now(timezone.utc)
        return max(0, delta.total_seconds())
    
    def can_extend(self) -> bool:
        """Check if lock can be extended"""
        return (self.auto_extend and 
                self.current_extensions < self.max_extensions and
                self.is_active)
    
    def extend_lock(self, additional_seconds: int = None) -> bool:
        """Extend lock expiration time"""
        if not self.can_extend():
            return False
        
        extend_duration = additional_seconds or self.lock_duration_seconds
        self.expires_at = datetime.now(timezone.utc) + timedelta(seconds=extend_duration)
        self.current_extensions += 1
        self.last_heartbeat = datetime.now(timezone.utc)
        self.update_timestamp()
        
        logger.debug(f"Extended lock {self.lock_id} until {self.expires_at}")
        return True
    
    def send_heartbeat(self) -> bool:
        """Send heartbeat to indicate lock is still active"""
        if self.is_expired():
            return False
        
        self.last_heartbeat = datetime.now(timezone.utc)
        self.heartbeat_failures = 0  # Reset failure count on successful heartbeat
        self.update_timestamp()
        return True
    
    def is_healthy(self) -> bool:
        """Check if lock is healthy based on heartbeat"""
        if not self.is_active or self.is_expired():
            return False
        
        # Check heartbeat freshness
        time_since_heartbeat = (datetime.now(timezone.utc) - self.last_heartbeat).total_seconds()
        max_heartbeat_age = self.heartbeat_interval_seconds * 3  # Allow 3 missed heartbeats
        
        return time_since_heartbeat <= max_heartbeat_age


# Exception classes for scheduler module
class SchedulerException(Exception):
    """Base exception for scheduler operations"""
    
    def __init__(self, message: str, trigger_id: Optional[str] = None, 
                 job_id: Optional[str] = None, error_code: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.trigger_id = trigger_id
        self.job_id = job_id
        self.error_code = error_code
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/API responses"""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "trigger_id": self.trigger_id,
            "job_id": self.job_id,
            "error_code": self.error_code
        }


class InvalidTriggerConfigError(SchedulerException):
    """Exception for invalid trigger configuration"""
    
    def __init__(self, message: str, trigger_id: Optional[str] = None, config_field: Optional[str] = None):
        super().__init__(message, trigger_id=trigger_id, error_code="INVALID_TRIGGER_CONFIG")
        self.config_field = config_field


class LockAcquisitionError(SchedulerException):
    """Exception for lock acquisition failures"""
    
    def __init__(self, message: str, lock_id: Optional[str] = None, resource_id: Optional[str] = None):
        super().__init__(message, error_code="LOCK_ACQUISITION_FAILED")
        self.lock_id = lock_id
        self.resource_id = resource_id


class SchedulerModelOperations:
    """
    Helper class for MongoDB operations on scheduler collections.
    Provides indexing strategies and collection management utilities.
    """
    
    @staticmethod
    def get_scheduled_trigger_indexes() -> List[Dict[str, Any]]:
        """Get MongoDB indexes for scheduled_triggers collection"""
        return [
            # Core query patterns
            {"key": [("status", 1), ("next_execution", 1)], "name": "status_next_execution"},
            {"key": [("organization_id", 1), ("status", 1)], "name": "org_status"},
            {"key": [("trigger_type", 1), ("status", 1)], "name": "type_status"},
            {"key": [("created_by", 1), ("created_at", -1)], "name": "creator_created"},
            
            # Time-based scheduling
            {"key": [("trigger_type", 1), ("next_execution", 1)], "name": "type_next_execution"},
            {"key": [("last_execution", -1)], "name": "last_execution_desc"},
            
            # Event-driven triggers
            {"key": [("trigger_type", 1), ("event_types", 1)], "name": "type_events"},
            
            # Dependency triggers
            {"key": [("trigger_type", 1), ("dependency_job_ids", 1)], "name": "type_dependencies"},
            
            # Performance and monitoring
            {"key": [("current_executions", 1), ("max_concurrent_executions", 1)], "name": "concurrency_limits"},
            {"key": [("tags", 1)], "name": "tags"},
            
            # TTL for archived triggers
            {"key": [("updated_at", 1)], "expireAfterSeconds": 7776000, "name": "ttl_archived", 
             "partialFilterExpression": {"status": "archived"}}
        ]
    
    @staticmethod
    def get_scheduled_job_indexes() -> List[Dict[str, Any]]:
        """Get MongoDB indexes for scheduled_jobs collection"""
        return [
            # Core query patterns
            {"key": [("trigger_id", 1), ("status", 1)], "name": "trigger_status"},
            {"key": [("status", 1), ("scheduled_time", 1)], "name": "status_scheduled"},
            {"key": [("worker_instance_id", 1), ("status", 1)], "name": "worker_status"},
            {"key": [("organization_id", 1), ("scheduled_time", -1)], "name": "org_scheduled_desc"},
            
            # Time-series queries
            {"key": [("scheduled_time", -1)], "name": "scheduled_desc"},
            {"key": [("started_at", -1)], "name": "started_desc"},
            {"key": [("completed_at", -1)], "name": "completed_desc"},
            
            # Retry management
            {"key": [("status", 1), ("next_retry_at", 1)], "name": "status_retry"},
            {"key": [("retry_attempt", 1), ("max_retries", 1)], "name": "retry_limits"},
            
            # Performance monitoring
            {"key": [("job_type", 1), ("duration_seconds", 1)], "name": "type_duration"},
            {"key": [("trigger_type", 1), ("completed_at", -1)], "name": "trigger_type_completed"},
            
            # Lock management
            {"key": [("execution_lock_id", 1)], "name": "lock_id", "sparse": True},
            
            # TTL for job history cleanup
            {"key": [("completed_at", 1)], "expireAfterSeconds": 7776000, "name": "ttl_jobs_90d",
             "partialFilterExpression": {"status": {"$in": ["completed", "failed", "aborted"]}}}
        ]
    
    @staticmethod
    def get_execution_lock_indexes() -> List[Dict[str, Any]]:
        """Get MongoDB indexes for execution_locks collection"""
        return [
            # Unique compound key for resource locking
            {"key": [("resource_type", 1), ("resource_id", 1)], "name": "resource_unique", "unique": True},
            
            # Lock management
            {"key": [("owner_instance_id", 1), ("is_active", 1)], "name": "owner_active"},
            {"key": [("expires_at", 1)], "name": "expires_at"},
            {"key": [("is_active", 1), ("expires_at", 1)], "name": "active_expires"},
            
            # TTL for automatic lock cleanup
            {"key": [("expires_at", 1)], "expireAfterSeconds": 0, "name": "ttl_locks"},
            
            # Lock health monitoring
            {"key": [("last_heartbeat", 1)], "name": "heartbeat"},
            {"key": [("heartbeat_failures", 1), ("is_active", 1)], "name": "failures_active"},
            
            # Job association
            {"key": [("job_id", 1)], "name": "job_id", "sparse": True},
            {"key": [("trigger_id", 1)], "name": "trigger_id", "sparse": True}
        ] 
"""
Orchestration & Recovery Engine - API Schemas

Implements Pydantic schemas for request/response validation including:
- Job creation and management schemas
- Node definition and status schemas
- Retry policy configuration schemas
- Recovery audit and reporting schemas
- Common response patterns with standardized error handling
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, field_validator, ConfigDict

from ..models.orchestration_models import (
    JobStatus, NodeType, RetryStrategy, RecoveryAction
)


class BaseOrchestrationSchema(BaseModel):
    """Base schema with common configuration for all orchestration schemas."""
    
    model_config = ConfigDict(
        use_enum_values=True,
        validate_assignment=True,
        str_strip_whitespace=True,
        frozen=False
    )


# Job Management Schemas
class CreateOrchestrationJobRequest(BaseOrchestrationSchema):
    """Request schema for creating new orchestration jobs."""
    
    job_name: str = Field(..., min_length=1, max_length=255, description="Human-readable job name")
    job_description: Optional[str] = Field(None, max_length=1000, description="Detailed job description")
    job_type: str = Field(..., min_length=1, max_length=100, description="Type of orchestration job")
    priority: int = Field(default=5, ge=1, le=10, description="Job priority (1=highest, 10=lowest)")
    tags: List[str] = Field(default_factory=list, description="Job tags for organization")
    
    # Execution context
    execution_context: Dict[str, Any] = Field(default_factory=dict, description="Job execution context")
    test_suite_id: Optional[str] = Field(None, description="Associated test suite ID")
    test_case_ids: List[str] = Field(default_factory=list, description="Associated test case IDs")
    
    # Scheduling
    scheduled_at: Optional[datetime] = Field(None, description="Scheduled execution time")
    
    # Retry configuration
    max_retries: int = Field(default=3, ge=0, le=10, description="Maximum allowed retries")
    retry_policy_id: Optional[str] = Field(None, description="Retry policy to use")
    
    # Resource requirements
    resource_requirements: Dict[str, Any] = Field(default_factory=dict, description="Required execution resources")
    execution_environment: Optional[str] = Field(None, description="Target execution environment")
    
    # Timing
    timeout_ms: Optional[int] = Field(None, ge=1000, le=3600000, description="Execution timeout (1s-1h)")
    estimated_duration_ms: Optional[int] = Field(None, ge=100, description="Estimated execution duration")
    
    # Configuration
    configuration: Dict[str, Any] = Field(default_factory=dict, description="Job configuration parameters")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional job metadata")
    
    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v):
        """Validate job tags are not empty and within limits."""
        if len(v) > 20:
            raise ValueError("Maximum 20 tags allowed")
        for tag in v:
            if not tag.strip():
                raise ValueError("Tags cannot be empty")
            if len(tag) > 50:
                raise ValueError("Tag length cannot exceed 50 characters")
        return v
    
    @field_validator('test_case_ids')
    @classmethod
    def validate_test_case_ids(cls, v):
        """Validate test case IDs are not empty."""
        if len(v) > 1000:
            raise ValueError("Maximum 1000 test cases allowed per job")
        return v


class UpdateOrchestrationJobRequest(BaseOrchestrationSchema):
    """Request schema for updating existing orchestration jobs."""
    
    job_name: Optional[str] = Field(None, min_length=1, max_length=255, description="Updated job name")
    job_description: Optional[str] = Field(None, max_length=1000, description="Updated job description")
    priority: Optional[int] = Field(None, ge=1, le=10, description="Updated job priority")
    tags: Optional[List[str]] = Field(None, description="Updated job tags")
    
    # Status management
    status: Optional[JobStatus] = Field(None, description="Updated job status")
    
    # Scheduling updates
    scheduled_at: Optional[datetime] = Field(None, description="Updated scheduled execution time")
    
    # Configuration updates
    configuration: Optional[Dict[str, Any]] = Field(None, description="Updated configuration parameters")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Updated metadata")


class JobStatusResponse(BaseOrchestrationSchema):
    """Response schema for job status information."""
    
    job_id: str = Field(..., description="Unique job identifier")
    job_name: str = Field(..., description="Human-readable job name")
    job_type: str = Field(..., description="Type of orchestration job")
    status: JobStatus = Field(..., description="Current job status")
    priority: int = Field(..., description="Job priority")
    
    # Timing information
    triggered_at: datetime = Field(..., description="Job trigger timestamp")
    scheduled_at: Optional[datetime] = Field(None, description="Scheduled execution time")
    started_at: Optional[datetime] = Field(None, description="Execution start time")
    completed_at: Optional[datetime] = Field(None, description="Execution completion time")
    
    # Progress information
    progress_percentage: Optional[float] = Field(None, ge=0, le=100, description="Execution progress")
    current_node_id: Optional[str] = Field(None, description="Currently executing node")
    
    # Retry information
    retry_count: int = Field(..., description="Number of retry attempts")
    max_retries: int = Field(..., description="Maximum allowed retries")
    
    # Results
    execution_results: Dict[str, Any] = Field(default_factory=dict, description="Job execution results")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Error details if failed")
    
    # Metadata
    triggered_by: str = Field(..., description="User or system that triggered the job")
    tags: List[str] = Field(default_factory=list, description="Job tags")
    
    # Timestamps
    created_at: datetime = Field(..., description="Job creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")


class JobListResponse(BaseOrchestrationSchema):
    """Response schema for job list queries."""
    
    jobs: List[JobStatusResponse] = Field(..., description="List of jobs")
    total_count: int = Field(..., ge=0, description="Total number of jobs")
    page: int = Field(default=1, ge=1, description="Current page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")
    has_next: bool = Field(..., description="Whether there are more pages")


# Node Management Schemas
class CreateOrchestrationNodeRequest(BaseOrchestrationSchema):
    """Request schema for creating orchestration nodes."""
    
    node_name: str = Field(..., min_length=1, max_length=255, description="Human-readable node name")
    node_description: Optional[str] = Field(None, max_length=1000, description="Node description")
    node_type: NodeType = Field(..., description="Type of DAG node")
    node_order: int = Field(..., ge=0, description="Execution order within the graph")
    
    # Dependencies
    parent_nodes: List[str] = Field(default_factory=list, description="Parent node IDs")
    dependency_condition: str = Field(default="all", description="Dependency condition")
    
    # Execution configuration
    test_case_id: Optional[str] = Field(None, description="Associated test case ID")
    test_suite_id: Optional[str] = Field(None, description="Associated test suite ID")
    action_type: str = Field(..., min_length=1, description="Action type to execute")
    action_parameters: Dict[str, Any] = Field(default_factory=dict, description="Action parameters")
    
    # Conditional logic
    condition_expression: Optional[str] = Field(None, description="Conditional execution expression")
    skip_on_failure: bool = Field(False, description="Skip node if dependencies fail")
    
    # Parallel execution
    parallel_group: Optional[str] = Field(None, description="Parallel execution group ID")
    max_parallel_instances: int = Field(1, ge=1, le=10, description="Maximum parallel instances")
    
    # Resource requirements
    resource_requirements: Dict[str, Any] = Field(default_factory=dict, description="Resource requirements")
    
    # Retry configuration
    max_retries: int = Field(1, ge=0, le=5, description="Maximum node retries")
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional node metadata")
    tags: List[str] = Field(default_factory=list, description="Node tags")
    
    @field_validator('dependency_condition')
    @classmethod
    def validate_dependency_condition(cls, v):
        """Validate dependency condition is valid."""
        valid_conditions = ["all", "any", "conditional"]
        if v not in valid_conditions:
            raise ValueError(f"Dependency condition must be one of {valid_conditions}")
        return v


class NodeStatusResponse(BaseOrchestrationSchema):
    """Response schema for node status information."""
    
    node_id: str = Field(..., description="Unique node identifier")
    job_id: str = Field(..., description="Associated job ID")
    node_name: str = Field(..., description="Human-readable node name")
    node_type: NodeType = Field(..., description="Type of DAG node")
    node_order: int = Field(..., description="Execution order")
    
    # Dependencies
    parent_nodes: List[str] = Field(default_factory=list, description="Parent node IDs")
    child_nodes: List[str] = Field(default_factory=list, description="Child node IDs")
    
    # Execution state
    execution_status: JobStatus = Field(..., description="Node execution status")
    started_at: Optional[datetime] = Field(None, description="Execution start time")
    completed_at: Optional[datetime] = Field(None, description="Execution completion time")
    duration_ms: Optional[int] = Field(None, description="Execution duration")
    
    # Results
    execution_results: Dict[str, Any] = Field(default_factory=dict, description="Node execution results")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Error details if failed")
    
    # Retry information
    retry_count: int = Field(..., description="Number of retries")
    max_retries: int = Field(..., description="Maximum retries allowed")
    
    # Metadata
    action_type: str = Field(..., description="Action type")
    tags: List[str] = Field(default_factory=list, description="Node tags")
    
    # Timestamps
    created_at: datetime = Field(..., description="Node creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")


class NodeListResponse(BaseOrchestrationSchema):
    """Response schema for node list queries."""
    
    nodes: List[NodeStatusResponse] = Field(..., description="List of nodes")
    total_count: int = Field(..., ge=0, description="Total number of nodes")
    page: int = Field(default=1, ge=1, description="Current page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")
    has_next: bool = Field(..., description="Whether there are more pages")


# Retry Policy Schemas
class CreateRetryPolicyRequest(BaseOrchestrationSchema):
    """Request schema for creating retry policies."""
    
    policy_name: str = Field(..., min_length=1, max_length=255, description="Human-readable policy name")
    policy_description: Optional[str] = Field(None, max_length=1000, description="Policy description")
    
    # Policy configuration
    strategy: RetryStrategy = Field(..., description="Retry strategy type")
    max_attempts: int = Field(3, ge=1, le=10, description="Maximum retry attempts")
    base_delay_ms: int = Field(1000, ge=100, le=60000, description="Base delay between retries")
    max_delay_ms: int = Field(60000, ge=1000, le=300000, description="Maximum delay between retries")
    
    # Backoff configuration
    backoff_multiplier: float = Field(2.0, ge=1.0, le=10.0, description="Backoff multiplier")
    jitter_enabled: bool = Field(True, description="Enable jitter")
    
    # Failure classification
    retryable_error_types: List[str] = Field(default_factory=list, description="Retryable error types")
    non_retryable_error_types: List[str] = Field(default_factory=list, description="Non-retryable error types")
    
    # Application scope
    applicable_job_types: List[str] = Field(default_factory=list, description="Applicable job types")
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional policy metadata")
    
    @field_validator('base_delay_ms', 'max_delay_ms')
    @classmethod
    def validate_delays(cls, v, info):
        """Validate delay configurations."""
        if info.field_name == 'max_delay_ms' and 'base_delay_ms' in info.data:
            if v <= info.data['base_delay_ms']:
                raise ValueError("Maximum delay must be greater than base delay")
        return v


class UpdateRetryPolicyRequest(BaseOrchestrationSchema):
    """Request schema for updating retry policies."""
    
    policy_name: Optional[str] = Field(None, min_length=1, max_length=255, description="Updated policy name")
    policy_description: Optional[str] = Field(None, max_length=1000, description="Updated description")
    strategy: Optional[RetryStrategy] = Field(None, description="Updated retry strategy")
    max_attempts: Optional[int] = Field(None, ge=1, le=10, description="Updated max attempts")
    base_delay_ms: Optional[int] = Field(None, ge=100, le=60000, description="Updated base delay")
    max_delay_ms: Optional[int] = Field(None, ge=1000, le=300000, description="Updated max delay")
    backoff_multiplier: Optional[float] = Field(None, ge=1.0, le=10.0, description="Updated backoff multiplier")
    jitter_enabled: Optional[bool] = Field(None, description="Updated jitter setting")
    
    # Updated classifications
    retryable_error_types: Optional[List[str]] = Field(None, description="Updated retryable error types")
    non_retryable_error_types: Optional[List[str]] = Field(None, description="Updated non-retryable error types")
    applicable_job_types: Optional[List[str]] = Field(None, description="Updated applicable job types")
    
    # Updated metadata
    metadata: Optional[Dict[str, Any]] = Field(None, description="Updated metadata")


class RetryPolicyResponse(BaseOrchestrationSchema):
    """Response schema for retry policy information."""
    
    policy_id: str = Field(..., description="Unique policy identifier")
    policy_name: str = Field(..., description="Human-readable policy name")
    policy_description: Optional[str] = Field(None, description="Policy description")
    
    # Configuration
    strategy: RetryStrategy = Field(..., description="Retry strategy type")
    max_attempts: int = Field(..., description="Maximum retry attempts")
    base_delay_ms: int = Field(..., description="Base delay between retries")
    max_delay_ms: int = Field(..., description="Maximum delay between retries")
    backoff_multiplier: float = Field(..., description="Backoff multiplier")
    jitter_enabled: bool = Field(..., description="Jitter enabled")
    
    # Classifications
    retryable_error_types: List[str] = Field(default_factory=list, description="Retryable error types")
    non_retryable_error_types: List[str] = Field(default_factory=list, description="Non-retryable error types")
    applicable_job_types: List[str] = Field(default_factory=list, description="Applicable job types")
    
    # Effectiveness metrics
    success_rate: Optional[float] = Field(None, description="Historical success rate")
    average_attempts: Optional[float] = Field(None, description="Average attempts to success")
    
    # Timestamps
    created_at: datetime = Field(..., description="Policy creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")


class RetryPolicyListResponse(BaseOrchestrationSchema):
    """Response schema for retry policy list queries."""
    
    policies: List[RetryPolicyResponse] = Field(..., description="List of retry policies")
    total_count: int = Field(..., ge=0, description="Total number of policies")
    page: int = Field(default=1, ge=1, description="Current page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")
    has_next: bool = Field(..., description="Whether there are more pages")


# Recovery Audit Schemas
class RecoveryAuditResponse(BaseOrchestrationSchema):
    """Response schema for recovery audit information."""
    
    audit_id: str = Field(..., description="Unique audit record identifier")
    job_id: str = Field(..., description="Associated job ID")
    node_id: Optional[str] = Field(None, description="Associated node ID")
    recovery_session_id: str = Field(..., description="Recovery session identifier")
    
    # Recovery context
    recovery_action: RecoveryAction = Field(..., description="Recovery action taken")
    trigger_reason: str = Field(..., description="Recovery trigger reason")
    failure_classification: str = Field(..., description="Failure classification")
    
    # Recovery execution
    recovery_started_at: datetime = Field(..., description="Recovery start time")
    recovery_completed_at: Optional[datetime] = Field(None, description="Recovery completion time")
    recovery_duration_ms: Optional[int] = Field(None, description="Recovery duration")
    recovery_success: Optional[bool] = Field(None, description="Recovery success status")
    
    # Actions taken
    actions_performed: List[Dict[str, Any]] = Field(default_factory=list, description="Recovery actions")
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional audit metadata")
    
    # Timestamps
    created_at: datetime = Field(..., description="Audit creation timestamp")


class RecoveryAuditListResponse(BaseOrchestrationSchema):
    """Response schema for recovery audit list queries."""
    
    audits: List[RecoveryAuditResponse] = Field(..., description="List of recovery audits")
    total_count: int = Field(..., ge=0, description="Total number of audits")
    page: int = Field(default=1, ge=1, description="Current page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")
    has_next: bool = Field(..., description="Whether there are more pages")


# Common Response Schemas
class OrchestrationResponse(BaseOrchestrationSchema):
    """Standard response schema for orchestration operations."""
    
    success: bool = Field(..., description="Operation success status")
    message: str = Field(..., description="Response message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")
    request_id: Optional[str] = Field(None, description="Request correlation ID")


class ErrorResponse(BaseOrchestrationSchema):
    """Standard error response schema."""
    
    success: bool = Field(False, description="Operation success status")
    error_code: str = Field(..., description="Error code")
    error_message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.now, description="Error timestamp")
    request_id: Optional[str] = Field(None, description="Request correlation ID")


class ValidationErrorResponse(BaseOrchestrationSchema):
    """Validation error response schema."""
    
    success: bool = Field(False, description="Operation success status")
    error_code: str = Field("VALIDATION_ERROR", description="Error code")
    error_message: str = Field("Validation failed", description="Error message")
    validation_errors: List[Dict[str, Any]] = Field(..., description="Detailed validation errors")
    timestamp: datetime = Field(default_factory=datetime.now, description="Error timestamp")
    request_id: Optional[str] = Field(None, description="Request correlation ID") 
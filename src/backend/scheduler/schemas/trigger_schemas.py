"""
Scheduled Task Runner Engine - Request/Response Schemas

Implements comprehensive Pydantic schemas for all scheduler API endpoints with
full validation, OpenAPI documentation, and type safety. Provides detailed 
examples and error handling for robust API contracts.

Key Features:
- Complete CRUD schemas for triggers and jobs
- Validation with detailed error messages
- OpenAPI documentation examples
- Type-safe request/response handling
- Configuration validation schemas
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, field_validator, ConfigDict

from ..models.trigger_model import TriggerType, TaskStatus, ExecutionStatus


class BaseResponseSchema(BaseModel):
    """Base response schema with common fields"""
    
    success: bool = Field(..., description="Request success status")
    message: str = Field(..., description="Response message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    
    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )


# Configuration Schemas
class TriggerConfigSchema(BaseModel):
    """Schema for trigger configuration validation"""
    
    trigger_type: TriggerType = Field(..., description="Type of trigger mechanism")
    
    # Time-based configuration
    cron_expression: Optional[str] = Field(None, description="Cron expression for time-based triggers")
    timezone: str = Field("UTC", description="Timezone for cron expression evaluation")
    interval_seconds: Optional[int] = Field(None, ge=1, description="Interval in seconds for simple recurring tasks")
    
    # Event-driven configuration
    event_types: List[str] = Field(default_factory=list, description="Event types that trigger execution")
    event_filters: Dict[str, Any] = Field(default_factory=dict, description="Event filtering criteria")
    webhook_config: Dict[str, Any] = Field(default_factory=dict, description="Webhook configuration")
    
    # Dependency configuration
    dependency_job_ids: List[str] = Field(default_factory=list, description="Job IDs this trigger depends on")
    dependency_condition: str = Field("all_success", description="Dependency condition")
    
    # Conditional logic
    condition_expression: Optional[str] = Field(None, description="Boolean expression for conditional triggers")
    condition_context: Dict[str, Any] = Field(default_factory=dict, description="Context for condition evaluation")
    
    # Execution window
    execution_window_start: Optional[str] = Field(None, description="Execution window start time (HH:MM)")
    execution_window_end: Optional[str] = Field(None, description="Execution window end time (HH:MM)")
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "trigger_type": "time_based",
                    "cron_expression": "0 9 * * MON-FRI",
                    "timezone": "America/New_York",
                    "execution_window_start": "09:00",
                    "execution_window_end": "17:00"
                },
                {
                    "trigger_type": "event_driven",
                    "event_types": ["test_suite_completed", "build_finished"],
                    "event_filters": {"status": "success", "branch": "main"}
                }
            ]
        }
    )


class ExecutionConfigSchema(BaseModel):
    """Schema for execution configuration validation"""
    
    task_type: str = Field(..., description="Type of task to execute")
    task_parameters: Dict[str, Any] = Field(default_factory=dict, description="Task execution parameters")
    
    # Resource limits
    max_execution_time_seconds: int = Field(default=3600, ge=1, description="Maximum execution time limit")
    max_concurrent_executions: int = Field(default=1, ge=1, description="Maximum concurrent executions")
    
    # Environment configuration
    execution_environment: Optional[str] = Field(None, description="Target execution environment")
    resource_requirements: Dict[str, Any] = Field(default_factory=dict, description="Resource requirements")
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "task_type": "test_suite_execution",
                    "task_parameters": {
                        "suite_id": "suite_123",
                        "environment": "staging",
                        "parallel": True
                    },
                    "max_execution_time_seconds": 1800,
                    "max_concurrent_executions": 2
                }
            ]
        }
    )


class RetryPolicySchema(BaseModel):
    """Schema for retry policy configuration"""
    
    max_retries: int = Field(default=3, ge=0, description="Maximum retry attempts")
    retry_interval_seconds: int = Field(default=60, ge=1, description="Interval between retries")
    retry_backoff_multiplier: float = Field(default=2.0, ge=1.0, description="Backoff multiplier for retries")
    
    # Advanced retry configuration
    retryable_error_types: List[str] = Field(default_factory=list, description="Error types eligible for retry")
    max_retry_interval_seconds: int = Field(default=3600, ge=1, description="Maximum retry interval")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "max_retries": 3,
                "retry_interval_seconds": 60,
                "retry_backoff_multiplier": 2.0,
                "retryable_error_types": ["TIMEOUT", "NETWORK_ERROR", "TEMPORARY_FAILURE"],
                "max_retry_interval_seconds": 1800
            }
        }
    )


# Trigger Management Schemas
class CreateScheduledTriggerRequest(BaseModel):
    """Schema for creating new scheduled triggers"""
    
    name: str = Field(..., max_length=200, description="Human-readable trigger name")
    description: Optional[str] = Field(None, max_length=1000, description="Trigger description")
    
    # Configuration
    trigger_config: TriggerConfigSchema = Field(..., description="Trigger configuration")
    execution_config: ExecutionConfigSchema = Field(..., description="Execution configuration")
    retry_policy: Optional[RetryPolicySchema] = Field(None, description="Retry policy configuration")
    
    # Metadata
    tags: List[str] = Field(default_factory=list, description="Trigger tags for organization")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional trigger metadata")
    
    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v):
        """Validate tags format"""
        if len(v) > 10:
            raise ValueError("Maximum 10 tags allowed")
        
        for tag in v:
            if not isinstance(tag, str) or len(tag) > 50:
                raise ValueError("Tags must be strings with max length 50")
        
        return v
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Daily Test Suite Execution",
                "description": "Runs regression test suite daily at 9 AM EST",
                "trigger_config": {
                    "trigger_type": "time_based",
                    "cron_expression": "0 9 * * *",
                    "timezone": "America/New_York"
                },
                "execution_config": {
                    "task_type": "test_suite_execution",
                    "task_parameters": {
                        "suite_id": "regression_suite_v1",
                        "environment": "staging"
                    },
                    "max_execution_time_seconds": 3600
                },
                "retry_policy": {
                    "max_retries": 2,
                    "retry_interval_seconds": 300
                },
                "tags": ["regression", "daily", "automated"]
            }
        }
    )


class UpdateScheduledTriggerRequest(BaseModel):
    """Schema for updating existing scheduled triggers"""
    
    name: Optional[str] = Field(None, max_length=200, description="Updated trigger name")
    description: Optional[str] = Field(None, max_length=1000, description="Updated trigger description")
    status: Optional[TaskStatus] = Field(None, description="Updated trigger status")
    
    # Configuration updates
    trigger_config: Optional[TriggerConfigSchema] = Field(None, description="Updated trigger configuration")
    execution_config: Optional[ExecutionConfigSchema] = Field(None, description="Updated execution configuration")
    retry_policy: Optional[RetryPolicySchema] = Field(None, description="Updated retry policy")
    
    # Metadata updates
    tags: Optional[List[str]] = Field(None, description="Updated trigger tags")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Updated trigger metadata")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "paused",
                "trigger_config": {
                    "trigger_type": "time_based",
                    "cron_expression": "0 10 * * *"
                },
                "tags": ["regression", "daily", "automated", "updated"]
            }
        }
    )


class ScheduledTriggerResponse(BaseResponseSchema):
    """Schema for scheduled trigger response"""
    
    data: Dict[str, Any] = Field(..., description="Trigger data")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Trigger retrieved successfully",
                "timestamp": "2024-01-07T10:00:00Z",
                "data": {
                    "trigger_id": "trigger_123",
                    "name": "Daily Test Suite Execution",
                    "description": "Runs regression test suite daily at 9 AM EST",
                    "status": "active",
                    "trigger_type": "time_based",
                    "next_execution": "2024-01-08T14:00:00Z",
                    "last_execution": "2024-01-07T14:00:00Z",
                    "total_executions": 45,
                    "successful_executions": 42,
                    "failed_executions": 3,
                    "created_at": "2024-01-01T10:00:00Z",
                    "updated_at": "2024-01-07T10:00:00Z"
                }
            }
        }
    )


class ScheduledTriggerListResponse(BaseResponseSchema):
    """Schema for trigger list response with pagination"""
    
    data: List[Dict[str, Any]] = Field(..., description="List of triggers")
    pagination: Dict[str, Any] = Field(..., description="Pagination information")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Triggers retrieved successfully",
                "timestamp": "2024-01-07T10:00:00Z",
                "data": [
                    {
                        "trigger_id": "trigger_123",
                        "name": "Daily Test Suite",
                        "status": "active",
                        "trigger_type": "time_based",
                        "next_execution": "2024-01-08T14:00:00Z",
                        "total_executions": 45
                    }
                ],
                "pagination": {
                    "page": 1,
                    "page_size": 20,
                    "total_items": 1,
                    "total_pages": 1,
                    "has_next": False,
                    "has_previous": False
                }
            }
        }
    )


# Job Management Schemas
class JobExecutionRequest(BaseModel):
    """Schema for manual job execution requests"""
    
    trigger_id: Optional[str] = Field(None, description="Trigger ID for scheduled execution")
    execution_parameters: Dict[str, Any] = Field(default_factory=dict, description="Override execution parameters")
    priority: int = Field(default=5, ge=1, le=10, description="Execution priority (1=highest)")
    
    # Override configurations
    override_config: Optional[ExecutionConfigSchema] = Field(None, description="Override execution configuration")
    override_retry_policy: Optional[RetryPolicySchema] = Field(None, description="Override retry policy")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "trigger_id": "trigger_123",
                "execution_parameters": {
                    "environment": "production",
                    "test_branch": "release/v2.1"
                },
                "priority": 2,
                "override_config": {
                    "max_execution_time_seconds": 7200
                }
            }
        }
    )


class JobStatusUpdateRequest(BaseModel):
    """Schema for job status update requests"""
    
    status: ExecutionStatus = Field(..., description="New execution status")
    result_data: Optional[Dict[str, Any]] = Field(None, description="Execution result data")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Error details if applicable")
    performance_metrics: Optional[Dict[str, Any]] = Field(None, description="Performance metrics")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "completed",
                "result_data": {
                    "tests_run": 150,
                    "tests_passed": 148,
                    "tests_failed": 2,
                    "coverage_percent": 92.5
                },
                "performance_metrics": {
                    "duration_seconds": 1247,
                    "memory_usage_mb": 512,
                    "cpu_usage_percent": 65
                }
            }
        }
    )


class ScheduledJobResponse(BaseResponseSchema):
    """Schema for scheduled job response"""
    
    data: Dict[str, Any] = Field(..., description="Job execution data")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Job retrieved successfully",
                "timestamp": "2024-01-07T10:00:00Z",
                "data": {
                    "job_id": "job_456",
                    "trigger_id": "trigger_123",
                    "status": "running",
                    "scheduled_time": "2024-01-07T14:00:00Z",
                    "started_at": "2024-01-07T14:00:05Z",
                    "worker_instance_id": "worker-01",
                    "retry_attempt": 0,
                    "max_retries": 3,
                    "duration_seconds": 120.5
                }
            }
        }
    )


class ScheduledJobListResponse(BaseResponseSchema):
    """Schema for job list response with pagination and filtering"""
    
    data: List[Dict[str, Any]] = Field(..., description="List of job executions")
    pagination: Dict[str, Any] = Field(..., description="Pagination information")
    filters: Dict[str, Any] = Field(..., description="Applied filters")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Jobs retrieved successfully",
                "timestamp": "2024-01-07T10:00:00Z",
                "data": [
                    {
                        "job_id": "job_456",
                        "trigger_id": "trigger_123",
                        "status": "completed",
                        "scheduled_time": "2024-01-07T14:00:00Z",
                        "duration_seconds": 1247.2,
                        "retry_attempt": 0
                    }
                ],
                "pagination": {
                    "page": 1,
                    "page_size": 20,
                    "total_items": 1,
                    "total_pages": 1
                },
                "filters": {
                    "status": "completed",
                    "date_range": "last_7_days"
                }
            }
        }
    )


# Lock Management Schemas
class LockAcquisitionRequest(BaseModel):
    """Schema for lock acquisition requests"""
    
    resource_type: str = Field(..., description="Type of resource to lock")
    resource_id: str = Field(..., description="ID of resource to lock")
    lock_duration_seconds: int = Field(default=300, ge=1, le=3600, description="Lock duration in seconds")
    
    # Lock configuration
    auto_extend: bool = Field(default=False, description="Automatically extend lock")
    max_extensions: int = Field(default=5, ge=0, description="Maximum automatic extensions")
    owner_context: Dict[str, Any] = Field(default_factory=dict, description="Lock owner context")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "resource_type": "scheduled_trigger",
                "resource_id": "trigger_123",
                "lock_duration_seconds": 600,
                "auto_extend": True,
                "max_extensions": 3,
                "owner_context": {
                    "worker_instance": "worker-01",
                    "job_id": "job_456"
                }
            }
        }
    )


class LockAcquisitionResponse(BaseResponseSchema):
    """Schema for lock acquisition response"""
    
    data: Dict[str, Any] = Field(..., description="Lock acquisition data")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Lock acquired successfully",
                "timestamp": "2024-01-07T10:00:00Z",
                "data": {
                    "lock_id": "lock_789",
                    "resource_type": "scheduled_trigger",
                    "resource_id": "trigger_123",
                    "acquired_at": "2024-01-07T10:00:00Z",
                    "expires_at": "2024-01-07T10:10:00Z",
                    "owner_instance_id": "worker-01"
                }
            }
        }
    )


class LockStatusResponse(BaseResponseSchema):
    """Schema for lock status response"""
    
    data: Dict[str, Any] = Field(..., description="Lock status data")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Lock status retrieved successfully",
                "timestamp": "2024-01-07T10:00:00Z",
                "data": {
                    "lock_id": "lock_789",
                    "is_active": True,
                    "is_expired": False,
                    "time_until_expiry_seconds": 298.5,
                    "heartbeat_healthy": True,
                    "current_extensions": 1,
                    "can_extend": True
                }
            }
        }
    )


# Statistics and Health Schemas
class TriggerStatsResponse(BaseResponseSchema):
    """Schema for trigger statistics response"""
    
    data: Dict[str, Any] = Field(..., description="Trigger statistics data")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Trigger statistics retrieved successfully",
                "timestamp": "2024-01-07T10:00:00Z",
                "data": {
                    "total_triggers": 25,
                    "active_triggers": 20,
                    "paused_triggers": 3,
                    "disabled_triggers": 2,
                    "triggers_by_type": {
                        "time_based": 18,
                        "event_driven": 5,
                        "dependent": 2
                    },
                    "avg_success_rate": 0.956,
                    "total_executions_last_24h": 89,
                    "failed_executions_last_24h": 4
                }
            }
        }
    )


class ExecutionStatusResponse(BaseResponseSchema):
    """Schema for execution status response (manual trigger execution)"""
    
    data: Dict[str, Any] = Field(..., description="Execution status data")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Trigger execution initiated successfully",
                "timestamp": "2024-01-07T10:00:00Z",
                "data": {
                    "job_id": "job_abc123",
                    "trigger_id": "trigger_456",
                    "status": "running",
                    "started_at": "2024-01-07T10:00:00Z",
                    "estimated_completion": "2024-01-07T10:30:00Z",
                    "priority": 5,
                    "worker_instance": "worker-01",
                    "execution_parameters": {
                        "suite_id": "regression_suite_v1",
                        "environment": "staging"
                    }
                }
            }
        }
    )


class ExecutionHistoryResponse(BaseResponseSchema):
    """Schema for execution history response (trigger history list)"""
    
    data: List[Dict[str, Any]] = Field(..., description="List of execution history records")
    pagination: Dict[str, Any] = Field(..., description="Pagination information")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Trigger execution history retrieved successfully",
                "timestamp": "2024-01-07T10:00:00Z",
                "data": [
                    {
                        "job_id": "job_abc123",
                        "trigger_id": "trigger_456",
                        "status": "completed",
                        "scheduled_time": "2024-01-07T09:00:00Z",
                        "started_at": "2024-01-07T09:00:05Z",
                        "completed_at": "2024-01-07T09:25:30Z",
                        "execution_time_seconds": 1525,
                        "result_summary": "All tests passed",
                        "success": True,
                        "retry_count": 0
                    },
                    {
                        "job_id": "job_def789",
                        "trigger_id": "trigger_456",
                        "status": "failed",
                        "scheduled_time": "2024-01-06T09:00:00Z",
                        "started_at": "2024-01-06T09:00:02Z",
                        "completed_at": "2024-01-06T09:15:45Z",
                        "execution_time_seconds": 943,
                        "error_summary": "Network timeout",
                        "success": False,
                        "retry_count": 2
                    }
                ],
                "pagination": {
                    "page": 1,
                    "page_size": 20,
                    "total_records": 125,
                    "total_pages": 7,
                    "has_next": True,
                    "has_previous": False
                }
            }
        }
    )


class ExecutionStatsResponse(BaseResponseSchema):
    """Schema for execution statistics response"""
    
    data: Dict[str, Any] = Field(..., description="Execution statistics data")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Execution statistics retrieved successfully",
                "timestamp": "2024-01-07T10:00:00Z",
                "data": {
                    "total_jobs_last_24h": 89,
                    "completed_jobs": 85,
                    "failed_jobs": 4,
                    "success_rate": 0.955,
                    "avg_execution_time_seconds": 245.7,
                    "jobs_by_status": {
                        "completed": 85,
                        "failed": 4,
                        "running": 2,
                        "queued": 1
                    },
                    "performance_metrics": {
                        "avg_cpu_usage_percent": 45.2,
                        "avg_memory_usage_mb": 384.6,
                        "total_execution_time_hours": 6.1
                    }
                }
            }
        }
    )


class SystemHealthResponse(BaseResponseSchema):
    """Schema for system health response"""
    
    data: Dict[str, Any] = Field(..., description="System health data")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "System health retrieved successfully",
                "timestamp": "2024-01-07T10:00:00Z",
                "data": {
                    "overall_health": "healthy",
                    "active_workers": 3,
                    "queue_size": 12,
                    "active_locks": 5,
                    "expired_locks": 0,
                    "database_health": "healthy",
                    "recent_errors": [],
                    "system_metrics": {
                        "scheduler_uptime_seconds": 86400,
                        "triggers_processed_per_minute": 2.3,
                        "avg_lock_acquisition_time_ms": 15.2
                    }
                }
            }
        }
    )


# Query parameter schemas for API endpoints
class TriggerListParams(BaseModel):
    """Query parameters for trigger list endpoint"""
    
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")
    status: Optional[TaskStatus] = Field(None, description="Filter by trigger status")
    trigger_type: Optional[TriggerType] = Field(None, description="Filter by trigger type")
    tags: Optional[str] = Field(None, description="Filter by tags (comma-separated)")
    search: Optional[str] = Field(None, description="Search in name and description")
    sort_by: str = Field(default="created_at", description="Sort field")
    sort_order: str = Field(default="desc", description="Sort order (asc/desc)")


class JobListParams(BaseModel):
    """Query parameters for job list endpoint"""
    
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")
    trigger_id: Optional[str] = Field(None, description="Filter by trigger ID")
    status: Optional[ExecutionStatus] = Field(None, description="Filter by execution status")
    date_from: Optional[datetime] = Field(None, description="Filter jobs from date")
    date_to: Optional[datetime] = Field(None, description="Filter jobs to date")
    worker_instance: Optional[str] = Field(None, description="Filter by worker instance")
    sort_by: str = Field(default="scheduled_time", description="Sort field")
    sort_order: str = Field(default="desc", description="Sort order (asc/desc)") 
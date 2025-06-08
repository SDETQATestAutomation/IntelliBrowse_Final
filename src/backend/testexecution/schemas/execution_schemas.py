"""
Test Execution Engine - Execution Schemas

Comprehensive Pydantic schemas for execution operations including:
- Request schemas for starting and controlling executions
- Response schemas with flexible field inclusion
- Validation and business rule enforcement
- OpenAPI documentation integration

Follows the progressive observability architecture from creative phase
with performance-optimized field inclusion patterns.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Set
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict

from ..models.execution_trace_model import (
    ExecutionStatus,
    StepStatus,
    ExecutionType,
    ResourceUsageMetrics,
    StepErrorDetails,
    ExecutionStatistics
)


class ExecutionFieldInclusion(str, Enum):
    """Field inclusion control for execution responses"""
    CORE = "core"                    # Basic execution info only
    SUMMARY = "summary"              # Core + statistics
    DETAILED = "detailed"            # Summary + steps/configuration
    FULL = "full"                    # All fields including debug data


class StepFieldInclusion(str, Enum):
    """Field inclusion control for step responses"""
    BASIC = "basic"                  # Step ID, name, status only
    STANDARD = "standard"            # Basic + timing and results
    DETAILED = "detailed"            # Standard + error details and metadata
    FULL = "full"                    # All fields including debug data


class SortDirection(str, Enum):
    """Sort direction enumeration"""
    ASC = "asc"
    DESC = "desc"


class ExecutionSortField(str, Enum):
    """Available fields for sorting executions"""
    TRIGGERED_AT = "triggered_at"
    STARTED_AT = "started_at"
    COMPLETED_AT = "completed_at"
    STATUS = "status"
    EXECUTION_TYPE = "execution_type"
    DURATION = "total_duration_ms"


class ReportFormat(str, Enum):
    """Available report formats for execution reporting"""
    JSON = "json"
    HTML = "html"
    PDF = "pdf"
    XML = "xml"
    CSV = "csv"


class ResultSeverity(str, Enum):
    """Result severity levels for notifications"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Supporting Schemas

class PaginationMeta(BaseModel):
    """Pagination metadata for list responses"""
    page: int = Field(1, ge=1, description="Current page number")
    page_size: int = Field(20, ge=1, le=100, description="Items per page")
    total_items: int = Field(0, ge=0, description="Total number of items")
    total_pages: int = Field(0, ge=0, description="Total number of pages")
    has_next: bool = Field(False, description="Whether there are more pages")
    has_previous: bool = Field(False, description="Whether there are previous pages")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "page": 1,
                "page_size": 20,
                "total_items": 150,
                "total_pages": 8,
                "has_next": True,
                "has_previous": False
            }
        }
    )


class FilterMeta(BaseModel):
    """Filter metadata for list responses"""
    applied_filters: Dict[str, Any] = Field(default_factory=dict, description="Applied filter criteria")
    available_filters: List[str] = Field(default_factory=list, description="Available filter fields")
    filter_count: int = Field(0, ge=0, description="Number of active filters")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "applied_filters": {
                    "status": ["running", "pending"],
                    "execution_type": "test_case",
                    "triggered_by": "user@example.com"
                },
                "available_filters": ["status", "execution_type", "triggered_by", "test_case_id"],
                "filter_count": 3
            }
        }
    )


class SortMeta(BaseModel):
    """Sort metadata for list responses"""
    sort_field: ExecutionSortField = Field(ExecutionSortField.TRIGGERED_AT, description="Field used for sorting")
    sort_direction: SortDirection = Field(SortDirection.DESC, description="Sort direction")
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "sort_field": "triggered_at",
                "sort_direction": "desc"
            }
        }
    )


class ExecutionContextSchema(BaseModel):
    """Execution context data schema"""
    environment: Optional[str] = Field(None, description="Execution environment")
    browser: Optional[str] = Field(None, description="Browser for web tests")
    platform: Optional[str] = Field(None, description="Platform/OS information")
    build_version: Optional[str] = Field(None, description="Application build version")
    test_data_set: Optional[str] = Field(None, description="Test data set identifier")
    parallel_execution: bool = Field(False, description="Whether execution is part of parallel run")
    execution_agent: Optional[str] = Field(None, description="Agent executing the test")
    custom_properties: Dict[str, Any] = Field(default_factory=dict, description="Custom context properties")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "environment": "staging",
                "browser": "chrome",
                "platform": "linux",
                "build_version": "v1.2.3",
                "test_data_set": "regression_data",
                "parallel_execution": False,
                "execution_agent": "local-runner-01",
                "custom_properties": {
                    "feature_flags": ["new_ui", "api_v2"],
                    "test_suite_run_id": "run_20250105_001"
                }
            }
        }
    )


class ExecutionConfigSchema(BaseModel):
    """Execution configuration schema"""
    timeout_ms: int = Field(1800000, ge=1000, description="Execution timeout in milliseconds (default 30 min)")
    step_timeout_ms: int = Field(300000, ge=1000, description="Individual step timeout in milliseconds (default 5 min)")
    retry_enabled: bool = Field(True, description="Whether retry is enabled for failed steps")
    max_retries: int = Field(3, ge=0, le=10, description="Maximum number of retries per step")
    fail_fast: bool = Field(False, description="Whether to stop execution on first failure")
    capture_screenshots: bool = Field(True, description="Whether to capture screenshots on failures")
    capture_logs: bool = Field(True, description="Whether to capture detailed logs")
    parallel_steps: bool = Field(False, description="Whether to execute steps in parallel where possible")
    resource_limits: Optional[ResourceUsageMetrics] = Field(None, description="Resource usage limits")
    custom_config: Dict[str, Any] = Field(default_factory=dict, description="Custom configuration properties")
    
    @field_validator('timeout_ms', 'step_timeout_ms')
    @classmethod
    def validate_timeouts(cls, v):
        """Validate timeout values are reasonable"""
        if v > 7200000:  # 2 hours
            raise ValueError("Timeout cannot exceed 2 hours")
        return v
    
    @model_validator(mode='after')
    def validate_timeout_relationship(self):
        """Ensure step timeout is less than total timeout"""
        if self.step_timeout_ms >= self.timeout_ms:
            raise ValueError("Step timeout must be less than total execution timeout")
        return self
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timeout_ms": 1800000,
                "step_timeout_ms": 300000,
                "retry_enabled": True,
                "max_retries": 3,
                "fail_fast": False,
                "capture_screenshots": True,
                "capture_logs": True,
                "parallel_steps": False,
                "custom_config": {
                    "notification_webhook": "https://api.example.com/webhooks/test-results",
                    "slack_channel": "#test-results"
                }
            }
        }
    )


# Request Schemas

class StartExecutionRequest(BaseModel):
    """Base schema for starting executions"""
    execution_context: ExecutionContextSchema = Field(default_factory=ExecutionContextSchema, description="Execution context")
    execution_config: ExecutionConfigSchema = Field(default_factory=ExecutionConfigSchema, description="Execution configuration")
    tags: List[str] = Field(default_factory=list, max_length=20, description="Execution tags")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    priority: int = Field(5, ge=1, le=10, description="Execution priority (1=highest, 10=lowest)")
    
    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v):
        """Validate and normalize tags"""
        if not v:
            return v
        
        # Normalize tags
        normalized = []
        for tag in v:
            if not isinstance(tag, str):
                raise ValueError("Tags must be strings")
            normalized_tag = tag.strip().lower()
            if len(normalized_tag) < 1:
                continue
            if len(normalized_tag) > 50:
                raise ValueError("Tag length cannot exceed 50 characters")
            if normalized_tag not in normalized:
                normalized.append(normalized_tag)
        
        return normalized
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "execution_context": {
                    "environment": "staging",
                    "browser": "chrome"
                },
                "execution_config": {
                    "timeout_ms": 1800000,
                    "retry_enabled": True
                },
                "tags": ["regression", "api"],
                "metadata": {"suite_run_id": "run_001"},
                "priority": 5
            }
        }
    )


class StartTestCaseExecutionRequest(StartExecutionRequest):
    """Schema for starting test case execution"""
    test_case_id: str = Field(..., min_length=1, description="Test case ID to execute")
    
    @field_validator('test_case_id')
    @classmethod
    def validate_test_case_id(cls, v):
        """Validate test case ID format"""
        if not v or not v.strip():
            raise ValueError("Test case ID cannot be empty")
        return v.strip()
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "test_case_id": "507f1f77bcf86cd799439011",
                "execution_context": {
                    "environment": "staging",
                    "browser": "chrome"
                },
                "tags": ["smoke", "critical"],
                "priority": 3
            }
        }
    )


class StartTestSuiteExecutionRequest(StartExecutionRequest):
    """Schema for starting test suite execution"""
    test_suite_id: str = Field(..., min_length=1, description="Test suite ID to execute")
    parallel_execution: bool = Field(False, description="Whether to execute test cases in parallel")
    max_parallel_cases: int = Field(5, ge=1, le=20, description="Maximum parallel test cases")
    continue_on_failure: bool = Field(True, description="Whether to continue suite execution on test case failure")
    
    @field_validator('test_suite_id')
    @classmethod
    def validate_test_suite_id(cls, v):
        """Validate test suite ID format"""
        if not v or not v.strip():
            raise ValueError("Test suite ID cannot be empty")
        return v.strip()
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "test_suite_id": "507f1f77bcf86cd799439012",
                "parallel_execution": True,
                "max_parallel_cases": 3,
                "continue_on_failure": True,
                "execution_context": {
                    "environment": "production",
                    "test_data_set": "prod_smoke_data"
                },
                "tags": ["smoke", "production"],
                "priority": 1
            }
        }
    )


class UpdateExecutionStatusRequest(BaseModel):
    """Schema for updating execution status"""
    new_status: ExecutionStatus = Field(..., description="New execution status")
    reason: Optional[str] = Field(None, max_length=500, description="Reason for status change")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional status change metadata")
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "new_status": "cancelled",
                "reason": "User requested cancellation",
                "metadata": {"cancelled_by": "user@example.com", "cancelled_at": "2025-01-05T22:30:00Z"}
            }
        }
    )


class FilterExecutionsRequest(BaseModel):
    """Schema for filtering execution list requests"""
    # Pagination
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(20, ge=1, le=100, description="Items per page")
    
    # Sorting
    sort_field: ExecutionSortField = Field(ExecutionSortField.TRIGGERED_AT, description="Field to sort by")
    sort_direction: SortDirection = Field(SortDirection.DESC, description="Sort direction")
    
    # Filters
    status: Optional[List[ExecutionStatus]] = Field(None, description="Filter by execution status")
    execution_type: Optional[List[ExecutionType]] = Field(None, description="Filter by execution type")
    triggered_by: Optional[str] = Field(None, description="Filter by user who triggered execution")
    test_case_id: Optional[str] = Field(None, description="Filter by test case ID")
    test_suite_id: Optional[str] = Field(None, description="Filter by test suite ID")
    tags: Optional[List[str]] = Field(None, description="Filter by tags (OR logic)")
    
    # Date range filters
    triggered_after: Optional[datetime] = Field(None, description="Filter executions triggered after this date")
    triggered_before: Optional[datetime] = Field(None, description="Filter executions triggered before this date")
    completed_after: Optional[datetime] = Field(None, description="Filter executions completed after this date")
    completed_before: Optional[datetime] = Field(None, description="Filter executions completed before this date")
    
    # Field inclusion
    include_fields: ExecutionFieldInclusion = Field(ExecutionFieldInclusion.SUMMARY, description="Fields to include in response")
    include_steps: StepFieldInclusion = Field(StepFieldInclusion.BASIC, description="Step fields to include")
    
    @model_validator(mode='after')
    def validate_date_ranges(self):
        """Validate date range consistency"""
        if self.triggered_after and self.triggered_before:
            if self.triggered_after >= self.triggered_before:
                raise ValueError("triggered_after must be before triggered_before")
        
        if self.completed_after and self.completed_before:
            if self.completed_after >= self.completed_before:
                raise ValueError("completed_after must be before completed_before")
        
        return self
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "page": 1,
                "page_size": 20,
                "sort_field": "triggered_at",
                "sort_direction": "desc",
                "status": ["running", "pending"],
                "execution_type": ["test_case"],
                "triggered_by": "user@example.com",
                "tags": ["regression", "api"],
                "triggered_after": "2025-01-05T00:00:00Z",
                "include_fields": "summary",
                "include_steps": "basic"
            }
        }
    )


# Response Schemas

class StepResultResponse(BaseModel):
    """Response schema for step results"""
    step_id: str = Field(..., description="Step identifier")
    step_name: str = Field(..., description="Step name")
    step_order: int = Field(..., description="Step order in execution")
    status: StepStatus = Field(..., description="Step status")
    
    # Conditional fields based on inclusion level
    started_at: Optional[datetime] = Field(None, description="Step start time")
    completed_at: Optional[datetime] = Field(None, description="Step completion time")
    duration_ms: Optional[int] = Field(None, description="Step duration in milliseconds")
    
    # Standard level fields
    input_data: Optional[Dict[str, Any]] = Field(None, description="Step input data")
    output_data: Optional[Dict[str, Any]] = Field(None, description="Step output data")
    expected_result: Optional[Dict[str, Any]] = Field(None, description="Expected result")
    actual_result: Optional[Dict[str, Any]] = Field(None, description="Actual result")
    
    # Detailed level fields
    error_details: Optional[StepErrorDetails] = Field(None, description="Error details if failed")
    warnings: Optional[List[str]] = Field(None, description="Step warnings")
    retry_count: Optional[int] = Field(None, description="Number of retries")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Step metadata")
    
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
                "input_data": {"username": "testuser"},
                "output_data": {"session_id": "abc123"},
                "retry_count": 0
            }
        }
    )


class ExecutionTraceResponse(BaseModel):
    """Response schema for execution traces with flexible field inclusion"""
    # Core fields (always included)
    execution_id: str = Field(..., description="Execution identifier")
    status: ExecutionStatus = Field(..., description="Current execution status")
    execution_type: ExecutionType = Field(..., description="Type of execution")
    triggered_by: str = Field(..., description="User who triggered execution")
    triggered_at: datetime = Field(..., description="Execution trigger time")
    
    # Summary level fields
    test_case_id: Optional[str] = Field(None, description="Test case ID if applicable")
    test_suite_id: Optional[str] = Field(None, description="Test suite ID if applicable")
    started_at: Optional[datetime] = Field(None, description="Execution start time")
    completed_at: Optional[datetime] = Field(None, description="Execution completion time")
    total_duration_ms: Optional[int] = Field(None, description="Total execution duration")
    statistics: Optional[ExecutionStatistics] = Field(None, description="Execution statistics")
    
    # Detailed level fields
    execution_context: Optional[ExecutionContextSchema] = Field(None, description="Execution context")
    execution_config: Optional[ExecutionConfigSchema] = Field(None, description="Execution configuration")
    embedded_steps: Optional[List[StepResultResponse]] = Field(None, description="Embedded step results")
    tags: Optional[List[str]] = Field(None, description="Execution tags")
    overall_result: Optional[str] = Field(None, description="Overall result summary")
    
    # Full level fields
    state_history: Optional[List[Dict[str, Any]]] = Field(None, description="State transition history")
    execution_log: Optional[List[str]] = Field(None, description="Execution log entries")
    debug_data: Optional[Dict[str, Any]] = Field(None, description="Debug information")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    resource_usage: Optional[ResourceUsageMetrics] = Field(None, description="Resource usage metrics")
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "execution_id": "exec_20250105_223000_001",
                "status": "running",
                "execution_type": "test_case",
                "triggered_by": "user@example.com",
                "triggered_at": "2025-01-05T22:30:00Z",
                "test_case_id": "507f1f77bcf86cd799439011",
                "started_at": "2025-01-05T22:30:01Z",
                "statistics": {
                    "total_steps": 10,
                    "completed_steps": 3,
                    "progress_percentage": 30.0
                },
                "tags": ["regression", "api"]
            }
        }
    )


class ExecutionProgressResponse(BaseModel):
    """Real-time execution progress response"""
    execution_id: str = Field(..., description="Execution identifier")
    status: ExecutionStatus = Field(..., description="Current execution status")
    progress_percentage: float = Field(..., ge=0, le=100, description="Execution progress percentage")
    current_step: Optional[str] = Field(None, description="Currently executing step")
    estimated_remaining_ms: Optional[int] = Field(None, description="Estimated remaining time")
    last_update: datetime = Field(..., description="Last progress update time")
    statistics: ExecutionStatistics = Field(..., description="Current execution statistics")
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "execution_id": "exec_20250105_223000_001",
                "status": "running",
                "progress_percentage": 45.0,
                "current_step": "Verify API response",
                "estimated_remaining_ms": 120000,
                "last_update": "2025-01-05T22:35:00Z",
                "statistics": {
                    "total_steps": 10,
                    "completed_steps": 4,
                    "passed_steps": 4,
                    "failed_steps": 0
                }
            }
        }
    )


class ExecutionListResponse(BaseModel):
    """Response schema for execution list with pagination"""
    executions: List[ExecutionTraceResponse] = Field(..., description="List of executions")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")
    filters: FilterMeta = Field(..., description="Applied filters metadata")
    sorting: SortMeta = Field(..., description="Sorting metadata")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "executions": [
                    {
                        "execution_id": "exec_001",
                        "status": "passed",
                        "execution_type": "test_case",
                        "triggered_by": "user@example.com",
                        "triggered_at": "2025-01-05T22:30:00Z"
                    }
                ],
                "pagination": {
                    "page": 1,
                    "page_size": 20,
                    "total_items": 150,
                    "total_pages": 8
                },
                "filters": {
                    "applied_filters": {"status": ["passed"]},
                    "filter_count": 1
                },
                "sorting": {
                    "sort_field": "triggered_at",
                    "sort_direction": "desc"
                }
            }
        }
    )


class ExecutionStatsResponse(BaseModel):
    """Response schema for execution statistics and analytics"""
    total_executions: int = Field(..., ge=0, description="Total number of executions")
    executions_by_status: Dict[str, int] = Field(..., description="Execution count by status")
    executions_by_type: Dict[str, int] = Field(..., description="Execution count by type")
    average_duration_ms: Optional[float] = Field(None, description="Average execution duration")
    success_rate: float = Field(..., ge=0, le=1, description="Overall success rate")
    most_common_tags: List[Dict[str, Any]] = Field(..., description="Most frequently used tags")
    recent_activity: List[Dict[str, Any]] = Field(..., description="Recent execution activity")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_executions": 1250,
                "executions_by_status": {
                    "passed": 1000,
                    "failed": 200,
                    "running": 30,
                    "pending": 20
                },
                "executions_by_type": {
                    "test_case": 800,
                    "test_suite": 450
                },
                "average_duration_ms": 45000,
                "success_rate": 0.85,
                "most_common_tags": [
                    {"tag": "regression", "count": 500},
                    {"tag": "api", "count": 300}
                ],
                "recent_activity": [
                    {"date": "2025-01-05", "executions": 45},
                    {"date": "2025-01-04", "executions": 38}
                ]
            }
        }
    ) 
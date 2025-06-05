"""
Test Case Request and Response Schemas

Pydantic models for test case management API endpoints.
Implements flexible response system with field inclusion control and
standardized BaseResponse patterns following existing codebase conventions.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Set
from pydantic import BaseModel, Field, field_validator

from ...schemas.response import BaseResponse
from ..models.test_case_model import (
    TestCaseStatus, 
    TestCasePriority, 
    StepType, 
    StepFormatHint
)
from ...testtypes.enums import TestType


# ============================================================================
# REQUEST SCHEMAS
# ============================================================================

class TestCaseStepRequest(BaseModel):
    """Request schema for test case step creation/update."""
    
    action: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Step action description",
        example="Navigate to login page"
    )
    expected: Optional[str] = Field(
        None,
        max_length=500,
        description="Expected result for this step",
        example="Login page should be displayed"
    )
    step_type: StepType = Field(
        default=StepType.ACTION,
        description="Step classification",
        example="action"
    )
    parameters: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Parameterized inputs",
        example={"username": "test@example.com", "password": "password123"}
    )
    preconditions: Optional[List[str]] = Field(
        default_factory=list,
        description="Prerequisites for this step",
        example=["User is logged out", "Browser is open"]
    )
    postconditions: Optional[List[str]] = Field(
        default_factory=list,
        description="State after step execution",
        example=["User is on login page"]
    )
    notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Additional context or hints",
        example="Ensure page loads completely before proceeding"
    )
    test_item_ref: Optional[str] = Field(
        None,
        description="Reference to reusable TestItem step",
        example="60f7b1b9e4b0c8a4f8e6d1a4"
    )
    external_refs: Optional[List[str]] = Field(
        default_factory=list,
        description="External tool or documentation links",
        example=["https://docs.example.com/login"]
    )
    format_hint: StepFormatHint = Field(
        default=StepFormatHint.PLAIN,
        description="Rendering format",
        example="plain"
    )
    is_template: bool = Field(
        default=False,
        description="Whether this step serves as a template",
        example=False
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Type-specific or custom data",
        example={"automation_id": "login_step_001"}
    )


class AttachmentRefRequest(BaseModel):
    """Request schema for attachment references."""
    
    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Attachment name",
        example="Login Test Screenshot"
    )
    url: str = Field(
        ...,
        min_length=1,
        description="Attachment URL or file path",
        example="https://example.com/screenshots/login_test.png"
    )
    type: str = Field(
        ...,
        description="Attachment type",
        example="image"
    )
    size: Optional[int] = Field(
        None,
        ge=0,
        description="File size in bytes",
        example=1024000
    )


class CreateTestCaseRequest(BaseModel):
    """Request schema for creating a new test case."""
    
    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Test case title (unique per user)",
        example="Login with valid credentials"
    )
    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Test case description",
        example="Verify that users can successfully log in with valid credentials"
    )
    steps: List[TestCaseStepRequest] = Field(
        default_factory=list,
        description="Test case steps",
        max_length=100
    )
    expected_result: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Clear expected outcome",
        example="User is successfully logged in and redirected to dashboard"
    )
    preconditions: Optional[List[str]] = Field(
        default_factory=list,
        description="Setup requirements",
        max_length=20,
        example=["User account exists", "Application is running"]
    )
    postconditions: Optional[List[str]] = Field(
        default_factory=list,
        description="Cleanup requirements",
        max_length=20,
        example=["User is logged out", "Session is cleared"]
    )
    test_type: TestType = Field(
        default=TestType.GENERIC,
        description="Test type classification",
        example="generic"
    )
    priority: TestCasePriority = Field(
        default=TestCasePriority.MEDIUM,
        description="Test case priority",
        example="high"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Categorization tags",
        max_length=50,
        example=["authentication", "smoke", "critical"]
    )
    related_test_items: List[str] = Field(
        default_factory=list,
        description="ObjectId references to TestItem",
        max_length=50,
        example=["60f7b1b9e4b0c8a4f8e6d1a5"]
    )
    references: Optional[List[str]] = Field(
        default_factory=list,
        description="External links, requirements IDs",
        max_length=20,
        example=["REQ-AUTH-001", "https://docs.example.com/auth"]
    )
    attachments: Optional[List[AttachmentRefRequest]] = Field(
        default_factory=list,
        description="File references",
        max_length=10
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extensible metadata",
        example={"automation_framework": "selenium", "browser": "chrome"}
    )


class UpdateTestCaseRequest(BaseModel):
    """Request schema for updating an existing test case."""
    
    title: Optional[str] = Field(
        None,
        min_length=1,
        max_length=200,
        description="Test case title",
        example="Login with valid credentials - Updated"
    )
    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Test case description"
    )
    expected_result: Optional[str] = Field(
        None,
        min_length=1,
        max_length=1000,
        description="Expected outcome"
    )
    preconditions: Optional[List[str]] = Field(
        None,
        description="Setup requirements",
        max_length=20
    )
    postconditions: Optional[List[str]] = Field(
        None,
        description="Cleanup requirements",
        max_length=20
    )
    test_type: Optional[TestType] = Field(
        None,
        description="Test type classification"
    )
    priority: Optional[TestCasePriority] = Field(
        None,
        description="Test case priority"
    )
    tags: Optional[List[str]] = Field(
        None,
        description="Categorization tags",
        max_length=50
    )
    related_test_items: Optional[List[str]] = Field(
        None,
        description="ObjectId references to TestItem",
        max_length=50
    )
    references: Optional[List[str]] = Field(
        None,
        description="External links, requirements IDs",
        max_length=20
    )
    attachments: Optional[List[AttachmentRefRequest]] = Field(
        None,
        description="File references",
        max_length=10
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Extensible metadata"
    )


class UpdateStepsRequest(BaseModel):
    """Request schema for updating test case steps."""
    
    steps: List[TestCaseStepRequest] = Field(
        ...,
        description="Updated test case steps",
        max_length=100
    )
    reorder: bool = Field(
        default=True,
        description="Whether to automatically reorder steps",
        example=True
    )


class UpdateStatusRequest(BaseModel):
    """Request schema for updating test case status."""
    
    status: TestCaseStatus = Field(
        ...,
        description="New test case status",
        example="active"
    )
    reason: Optional[str] = Field(
        None,
        max_length=500,
        description="Reason for status change",
        example="Test case reviewed and approved"
    )


class BulkTagRequest(BaseModel):
    """Request schema for bulk tag operations."""
    
    test_case_ids: List[str] = Field(
        ...,
        description="List of test case IDs",
        max_length=100,
        example=["60f7b1b9e4b0c8a4f8e6d1a1", "60f7b1b9e4b0c8a4f8e6d1a2"]
    )
    operation: str = Field(
        ...,
        description="Tag operation (add, remove, replace)",
        example="add"
    )
    tags: List[str] = Field(
        ...,
        description="Tags to apply",
        max_length=20,
        example=["regression", "automated"]
    )
    
    @field_validator('operation')
    @classmethod
    def validate_operation(cls, v):
        """Validate tag operation."""
        allowed_operations = {"add", "remove", "replace"}
        if v not in allowed_operations:
            raise ValueError(f"Operation must be one of: {allowed_operations}")
        return v


class FilterTestCasesRequest(BaseModel):
    """Request schema for filtering test cases."""
    
    # Pagination
    page: int = Field(
        default=1,
        ge=1,
        description="Page number (1-based)",
        example=1
    )
    page_size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Items per page",
        example=20
    )
    
    # Filters
    status: Optional[TestCaseStatus] = Field(
        None,
        description="Filter by status",
        example="active"
    )
    priority: Optional[TestCasePriority] = Field(
        None,
        description="Filter by priority",
        example="high"
    )
    test_type: Optional[TestType] = Field(
        None,
        description="Filter by test type",
        example="generic"
    )
    tags: Optional[List[str]] = Field(
        None,
        description="Filter by tags (AND operation)",
        max_length=10,
        example=["authentication", "smoke"]
    )
    title_search: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Search in title",
        example="login"
    )
    has_steps: Optional[bool] = Field(
        None,
        description="Filter by presence of steps",
        example=True
    )
    created_after: Optional[datetime] = Field(
        None,
        description="Filter by creation date (after)",
        example="2024-01-01T00:00:00Z"
    )
    created_before: Optional[datetime] = Field(
        None,
        description="Filter by creation date (before)",
        example="2024-12-31T23:59:59Z"
    )
    
    # Sorting
    sort_by: str = Field(
        default="updated_at",
        description="Sort field",
        example="updated_at"
    )
    sort_order: str = Field(
        default="desc",
        description="Sort order (asc, desc)",
        example="desc"
    )
    
    # Field inclusion
    include_steps: bool = Field(
        default=False,
        description="Include step details",
        example=False
    )
    include_statistics: bool = Field(
        default=False,
        description="Include computed statistics",
        example=False
    )
    include_references: bool = Field(
        default=False,
        description="Include reference data",
        example=False
    )
    
    @field_validator('sort_order')
    @classmethod
    def validate_sort_order(cls, v):
        """Validate sort order."""
        if v not in ["asc", "desc"]:
            raise ValueError("Sort order must be 'asc' or 'desc'")
        return v


# ============================================================================
# RESPONSE SCHEMAS
# ============================================================================

class TestCaseStepResponse(BaseModel):
    """Response schema for test case steps."""
    
    order: int = Field(
        ...,
        description="Step order",
        example=1
    )
    action: str = Field(
        ...,
        description="Step action description",
        example="Navigate to login page"
    )
    expected: Optional[str] = Field(
        None,
        description="Expected result",
        example="Login page should be displayed"
    )
    step_type: str = Field(
        ...,
        description="Step classification",
        example="action"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameterized inputs"
    )
    preconditions: List[str] = Field(
        default_factory=list,
        description="Prerequisites"
    )
    postconditions: List[str] = Field(
        default_factory=list,
        description="Postconditions"
    )
    notes: Optional[str] = Field(
        None,
        description="Additional context"
    )
    test_item_ref: Optional[str] = Field(
        None,
        description="TestItem reference"
    )
    external_refs: List[str] = Field(
        default_factory=list,
        description="External references"
    )
    format_hint: str = Field(
        default="plain",
        description="Rendering format"
    )
    is_template: bool = Field(
        default=False,
        description="Template flag"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Custom metadata"
    )


class AttachmentRefResponse(BaseModel):
    """Response schema for attachment references."""
    
    name: str = Field(
        ...,
        description="Attachment name",
        example="Login Test Screenshot"
    )
    url: str = Field(
        ...,
        description="Attachment URL",
        example="https://example.com/screenshots/login_test.png"
    )
    type: str = Field(
        ...,
        description="Attachment type",
        example="image"
    )
    size: Optional[int] = Field(
        None,
        description="File size in bytes",
        example=1024000
    )


class TestCaseCore(BaseModel):
    """
    Core test case data included in all responses.
    
    Contains essential fields always returned for consistency
    and performance optimization.
    """
    
    id: str = Field(
        ...,
        description="Test case unique identifier",
        example="60f7b1b9e4b0c8a4f8e6d1a1"
    )
    title: str = Field(
        ...,
        description="Test case title",
        example="Login with valid credentials"
    )
    description: Optional[str] = Field(
        None,
        description="Test case description",
        example="Verify that users can successfully log in with valid credentials"
    )
    status: str = Field(
        ...,
        description="Test case status",
        example="active"
    )
    priority: str = Field(
        ...,
        description="Test case priority",
        example="high"
    )
    test_type: str = Field(
        ...,
        description="Test type classification",
        example="generic"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Categorization tags",
        example=["authentication", "smoke", "critical"]
    )
    expected_result: str = Field(
        ...,
        description="Expected outcome",
        example="User is successfully logged in and redirected to dashboard"
    )
    owner_id: str = Field(
        ...,
        description="Owner user ID",
        example="60f7b1b9e4b0c8a4f8e6d1a3"
    )
    created_by: str = Field(
        ...,
        description="Creator user ID",
        example="60f7b1b9e4b0c8a4f8e6d1a3"
    )
    created_at: datetime = Field(
        ...,
        description="Creation timestamp",
        example="2024-01-15T10:30:00Z"
    )
    updated_at: Optional[datetime] = Field(
        None,
        description="Last update timestamp",
        example="2024-01-20T14:45:00Z"
    )
    step_count: int = Field(
        default=0,
        description="Number of steps",
        example=5
    )
    complexity_score: float = Field(
        default=0.0,
        description="Computed complexity score",
        example=2.5
    )


class TestCaseSteps(BaseModel):
    """Test case steps collection with metadata."""
    
    steps: List[TestCaseStepResponse] = Field(
        default_factory=list,
        description="Test case steps"
    )
    step_count: int = Field(
        ...,
        description="Total number of steps",
        example=5
    )
    bdd_structure: bool = Field(
        default=False,
        description="Has BDD Given-When-Then structure",
        example=False
    )
    step_types_summary: Dict[str, int] = Field(
        default_factory=dict,
        description="Step types count",
        example={"action": 3, "verification": 2}
    )


class TestCaseStatistics(BaseModel):
    """Computed test case statistics."""
    
    execution_time_estimate: Optional[int] = Field(
        None,
        description="Estimated execution time in seconds",
        example=180
    )
    automation_readiness: float = Field(
        default=0.0,
        description="Automation readiness score (0-1)",
        example=0.85
    )
    last_activity: Optional[str] = Field(
        None,
        description="Human-readable last activity",
        example="Updated 2 days ago"
    )
    reference_count: int = Field(
        default=0,
        description="Number of external references",
        example=3
    )
    attachment_count: int = Field(
        default=0,
        description="Number of attachments",
        example=2
    )


class TestCaseReferences(BaseModel):
    """Test case reference data."""
    
    related_test_items: List[str] = Field(
        default_factory=list,
        description="Related TestItem IDs"
    )
    suite_references: List[str] = Field(
        default_factory=list,
        description="TestSuite references"
    )
    references: List[str] = Field(
        default_factory=list,
        description="External references"
    )
    attachments: List[AttachmentRefResponse] = Field(
        default_factory=list,
        description="File attachments"
    )
    preconditions: List[str] = Field(
        default_factory=list,
        description="Setup requirements"
    )
    postconditions: List[str] = Field(
        default_factory=list,
        description="Cleanup requirements"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Custom metadata"
    )


class TestCaseResponse(BaseModel):
    """
    Flexible test case response with optional detailed fields.
    
    Supports field inclusion control for performance optimization.
    Core fields are always included, detailed fields are optional.
    """
    
    # Always included core data
    core: TestCaseCore = Field(
        ...,
        description="Core test case information"
    )
    
    # Optional detailed fields (included based on request)
    steps: Optional[TestCaseSteps] = Field(
        None,
        description="Test case steps (if requested)"
    )
    statistics: Optional[TestCaseStatistics] = Field(
        None,
        description="Computed statistics (if requested)"
    )
    references: Optional[TestCaseReferences] = Field(
        None,
        description="Reference data (if requested)"
    )
    
    # Computed fields for UI optimization
    computed: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional computed fields"
    )


# ============================================================================
# PAGINATION AND LIST RESPONSES
# ============================================================================

class PaginationMeta(BaseModel):
    """Pagination metadata for list responses."""
    
    page: int = Field(..., description="Current page number (1-based)")
    page_size: int = Field(..., description="Items per page")
    total_items: int = Field(..., description="Total number of items")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Has next page")
    has_previous: bool = Field(..., description="Has previous page")


class FilterMeta(BaseModel):
    """Applied filters metadata."""
    
    status: Optional[str] = Field(None, description="Filtered status")
    priority: Optional[str] = Field(None, description="Filtered priority")
    test_type: Optional[str] = Field(None, description="Filtered test type")
    tags: Optional[List[str]] = Field(None, description="Filtered tags")
    title_search: Optional[str] = Field(None, description="Search query")
    has_steps: Optional[bool] = Field(None, description="Steps filter")


class SortMeta(BaseModel):
    """Sorting metadata."""
    
    sort_by: str = Field(default="updated_at", description="Sort field")
    sort_order: str = Field(default="desc", description="Sort order")


class TestCaseListData(BaseModel):
    """Test case list response data."""
    
    test_cases: List[TestCaseResponse] = Field(
        ...,
        description="Test cases"
    )
    pagination: PaginationMeta = Field(
        ...,
        description="Pagination information"
    )
    filters: FilterMeta = Field(
        ...,
        description="Applied filters"
    )
    sorting: SortMeta = Field(
        ...,
        description="Sort configuration"
    )
    summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Summary statistics"
    )


class TestCaseStatsData(BaseModel):
    """Test case statistics data."""
    
    total_count: int = Field(
        ...,
        description="Total test cases",
        example=150
    )
    status_breakdown: Dict[str, int] = Field(
        ...,
        description="Count by status",
        example={"draft": 20, "active": 100, "deprecated": 20, "archived": 10}
    )
    priority_breakdown: Dict[str, int] = Field(
        ...,
        description="Count by priority",
        example={"high": 30, "medium": 80, "low": 40}
    )
    test_type_breakdown: Dict[str, int] = Field(
        ...,
        description="Count by test type",
        example={"generic": 100, "bdd": 30, "manual": 20}
    )
    tag_usage: Dict[str, int] = Field(
        default_factory=dict,
        description="Tag usage counts",
        example={"authentication": 25, "smoke": 40, "regression": 60}
    )
    complexity_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="Complexity score distribution",
        example={"low": 50, "medium": 70, "high": 30}
    )
    recent_activity: Dict[str, int] = Field(
        default_factory=dict,
        description="Recent activity counts",
        example={"created_today": 5, "updated_today": 12, "created_this_week": 25}
    )


# ============================================================================
# TYPED RESPONSE WRAPPERS
# ============================================================================

class TestCaseCreateResponse(BaseResponse[TestCaseResponse]):
    """Response for test case creation."""
    
    @classmethod
    def create_success(
        cls,
        test_case: TestCaseResponse,
        message: str = "Test case created successfully"
    ) -> "TestCaseCreateResponse":
        """Create a successful test case creation response."""
        return cls(
            success=True,
            data=test_case,
            message=message
        )


class TestCaseDetailResponse(BaseResponse[TestCaseResponse]):
    """Response for test case detail retrieval."""
    
    @classmethod
    def create_success(
        cls,
        test_case: TestCaseResponse,
        message: str = "Test case retrieved successfully"
    ) -> "TestCaseDetailResponse":
        """Create a successful test case detail response."""
        return cls(
            success=True,
            data=test_case,
            message=message
        )


class TestCaseListResponse(BaseResponse[TestCaseListData]):
    """Response for test case list retrieval."""
    
    @classmethod
    def create_success(
        cls,
        test_cases: List[TestCaseResponse],
        pagination: PaginationMeta,
        filters: FilterMeta,
        sorting: SortMeta,
        summary: Optional[Dict[str, Any]] = None,
        message: str = "Test cases retrieved successfully"
    ) -> "TestCaseListResponse":
        """Create a successful test case list response."""
        list_data = TestCaseListData(
            test_cases=test_cases,
            pagination=pagination,
            filters=filters,
            sorting=sorting,
            summary=summary or {}
        )
        return cls(
            success=True,
            data=list_data,
            message=message
        )


class TestCaseUpdateResponse(BaseResponse[TestCaseResponse]):
    """Response for test case update."""
    
    @classmethod
    def create_success(
        cls,
        test_case: TestCaseResponse,
        message: str = "Test case updated successfully"
    ) -> "TestCaseUpdateResponse":
        """Create a successful test case update response."""
        return cls(
            success=True,
            data=test_case,
            message=message
        )


class TestCaseStatsResponse(BaseResponse[TestCaseStatsData]):
    """Response for test case statistics."""
    
    @classmethod
    def create_success(
        cls,
        stats: TestCaseStatsData,
        message: str = "Test case statistics retrieved successfully"
    ) -> "TestCaseStatsResponse":
        """Create a successful test case statistics response."""
        return cls(
            success=True,
            data=stats,
            message=message
        )


# Re-export base schemas for convenience
from ...schemas.response import BaseResponse
PaginatedResponse = TestCaseListResponse  # Alias for backward compatibility 
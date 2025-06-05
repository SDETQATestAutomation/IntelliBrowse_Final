"""
Test Item Pydantic Schemas

Request and response models for test item API endpoints.
Implements the flexible unified response system from creative design.
Includes multi-test type support for GENERIC, BDD, and MANUAL test types.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List, Set
from enum import Enum
from pydantic import BaseModel, Field, validator, model_validator

from ...schemas.response import BaseResponse
from ..models.test_item_model import TestItemStatus, StepType, CreatedSource
# Import multi-test type support
from ...testtypes import TestType, TestTypeValidatorFactory, ValidationError as TypeValidationError


# Request Schemas
class CreateTestItemStepsRequest(BaseModel):
    """Request schema for test steps."""
    type: StepType = Field(..., description="Type of test steps")
    content: List[str] = Field(..., min_items=1, description="List of test step content")
    
    @validator('content')
    def validate_content(cls, v):
        if not v or not all(step.strip() for step in v):
            raise ValueError("All test steps must be non-empty")
        return v
    
    class Config:
        use_enum_values = True


class CreateTestItemSelectorsRequest(BaseModel):
    """Request schema for selectors."""
    primary: Dict[str, str] = Field(..., min_items=1, description="Primary selectors for UI elements")
    fallback: Optional[Dict[str, str]] = Field(None, description="Fallback selectors")
    reliability_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Selector reliability score")
    
    @validator('primary')
    def validate_primary_selectors(cls, v):
        if not v:
            raise ValueError("At least one primary selector is required")
        for key, selector in v.items():
            if not selector.strip():
                raise ValueError(f"Selector for '{key}' cannot be empty")
        return v


class CreateTestItemRequest(BaseModel):
    """Request schema for creating a new test item with multi-test type support."""
    title: str = Field(..., min_length=1, max_length=200, description="Test item title")
    feature_id: str = Field(..., min_length=1, description="Associated feature identifier")
    scenario_id: str = Field(..., min_length=1, description="Associated scenario identifier")
    steps: CreateTestItemStepsRequest = Field(..., description="Test steps information")
    selectors: CreateTestItemSelectorsRequest = Field(..., description="UI element selectors")
    tags: Optional[List[str]] = Field(default_factory=list, description="Test item tags")
    ai_confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="AI confidence score")
    auto_healing_enabled: Optional[bool] = Field(False, description="Enable auto-healing for this test")
    dom_snapshot_id: Optional[str] = Field(None, description="Reference to DOM snapshot")
    
    # Multi-test type support
    test_type: TestType = Field(default=TestType.GENERIC, description="Test type classification")
    type_data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Type-specific data")
    
    @validator('title')
    def validate_title(cls, v):
        if not v.strip():
            raise ValueError("Title cannot be empty or only whitespace")
        return v.strip()
    
    @validator('tags')
    def validate_tags(cls, v):
        if v:
            # Remove duplicates and empty tags
            v = list(set(tag.strip() for tag in v if tag.strip()))
        return v
    
    @model_validator(mode='before')
    @classmethod
    def validate_type_data(cls, values):
        """Validate type_data against the specified test_type using TestTypeValidatorFactory."""
        test_type_raw = values.get('test_type', TestType.GENERIC)
        type_data = values.get('type_data', {})
        
        # Convert string to TestType enum if needed
        if isinstance(test_type_raw, str):
            try:
                test_type = TestType(test_type_raw)
            except ValueError:
                raise ValueError(f"Invalid test_type: {test_type_raw}. Valid options: {[t.value for t in TestType]}")
        else:
            test_type = test_type_raw
        
        # Skip validation if no type_data provided (backward compatibility)
        if not type_data:
            return values
        
        try:
            # Validate type-specific data using the factory
            validated_type_data = TestTypeValidatorFactory.validate_type_data(test_type, type_data)
            values['type_data'] = validated_type_data
            return values
            
        except TypeValidationError as e:
            raise ValueError(f"Type-specific validation failed for {test_type}: {e.message}")
        except Exception as e:
            raise ValueError(f"Unexpected error validating {test_type} type data: {str(e)}")
    
    class Config:
        use_enum_values = True
        json_schema_extra = {
            "examples": {
                "generic_test": {
                    "summary": "Generic AI-based test item",
                    "value": {
                        "title": "Login with valid credentials",
                        "feature_id": "authentication",
                        "scenario_id": "user_login",
                        "steps": {
                            "type": "natural",
                            "content": ["Navigate to login page", "Enter credentials", "Click login"]
                        },
                        "selectors": {
                            "primary": {
                                "username_field": "#username",
                                "password_field": "#password",
                                "login_button": "button[type='submit']"
                            }
                        },
                        "test_type": "generic",
                        "type_data": {
                            "ai_confidence_score": 0.95,
                            "natural_language_steps": ["Navigate to login", "Enter valid credentials"],
                            "selector_hints": {"username": "#username", "password": "#password"}
                        }
                    }
                },
                "bdd_test": {
                    "summary": "BDD Cucumber-style test item",
                    "value": {
                        "title": "User can login successfully",
                        "feature_id": "authentication",
                        "scenario_id": "successful_login",
                        "steps": {
                            "type": "gherkin",
                            "content": ["Given I am on login page", "When I enter valid credentials", "Then I should be logged in"]
                        },
                        "selectors": {
                            "primary": {
                                "login_form": "form#login"
                            }
                        },
                        "test_type": "bdd",
                        "type_data": {
                            "feature_name": "User Authentication",
                            "scenario_name": "Successful login with valid credentials",
                            "bdd_blocks": [
                                {"type": "Given", "content": "I am on the login page", "keyword": "Given"},
                                {"type": "When", "content": "I enter valid credentials", "keyword": "When"},
                                {"type": "Then", "content": "I should be logged in", "keyword": "Then"}
                            ]
                        }
                    }
                },
                "manual_test": {
                    "summary": "Manual test item with documentation",
                    "value": {
                        "title": "Manual verification of login flow",
                        "feature_id": "authentication",
                        "scenario_id": "manual_login_check",
                        "steps": {
                            "type": "structured",
                            "content": ["Open application", "Navigate to login", "Test with various credentials"]
                        },
                        "selectors": {
                            "primary": {
                                "login_page": "/login"
                            }
                        },
                        "test_type": "manual",
                        "type_data": {
                            "manual_notes": "Manually verify login flow with different user types",
                            "expected_outcomes": "User should successfully authenticate and access dashboard",
                            "execution_time_estimate": 15,
                            "prerequisites": ["Test user accounts available", "Application running"]
                        }
                    }
                }
            }
        }


class FilterTestItemsRequest(BaseModel):
    """Request schema for filtering test items with multi-test type support."""
    feature_id: Optional[str] = Field(None, description="Filter by feature ID")
    scenario_id: Optional[str] = Field(None, description="Filter by scenario ID")
    status: Optional[TestItemStatus] = Field(None, description="Filter by status")
    test_type: Optional[TestType] = Field(None, description="Filter by test type")
    tags: Optional[List[str]] = Field(None, description="Filter by tags (AND operation)")
    created_after: Optional[datetime] = Field(None, description="Filter items created after this date")
    created_before: Optional[datetime] = Field(None, description="Filter items created before this date")
    search_query: Optional[str] = Field(None, min_length=1, description="Search in title and steps")
    
    # Pagination parameters
    page: int = Field(default=1, ge=1, description="Page number (1-based)")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")
    
    # Sorting parameters
    sort_by: str = Field(default="created_at", description="Sort field")
    sort_order: str = Field(default="desc", description="Sort order (asc/desc)")
    
    # Field inclusion parameters
    include_fields: Optional[str] = Field(None, description="Comma-separated fields to include")
    
    @validator('sort_order')
    def validate_sort_order(cls, v):
        if v not in ['asc', 'desc']:
            raise ValueError("Sort order must be 'asc' or 'desc'")
        return v
    
    @validator('sort_by')
    def validate_sort_by(cls, v):
        allowed_fields = ['created_at', 'updated_at', 'title', 'feature_id', 'scenario_id', 'test_type']
        if v not in allowed_fields:
            raise ValueError(f"Sort field must be one of: {', '.join(allowed_fields)}")
        return v
    
    class Config:
        use_enum_values = True


# Response Schemas (Flexible Unified Response System)
class TestItemCore(BaseModel):
    """Core test item data included in all responses with multi-test type support."""
    id: str = Field(..., description="Test item unique identifier")
    title: str = Field(..., description="Test item title")
    feature_id: str = Field(..., description="Associated feature ID")
    scenario_id: str = Field(..., description="Associated scenario ID")
    status: str = Field(..., description="Test item status")
    test_type: str = Field(..., description="Test type classification")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    created_by_user_id: str = Field(..., description="User ID who created the item")


class TestItemSteps(BaseModel):
    """Test steps information."""
    type: str = Field(..., description="Step type (gherkin/natural/structured)")
    content: List[str] = Field(..., description="Step content list")
    step_count: int = Field(..., description="Number of steps")


class TestItemSelectors(BaseModel):
    """Selector information."""
    primary: Dict[str, str] = Field(..., description="Primary selectors")
    fallback: Optional[Dict[str, str]] = Field(None, description="Fallback selectors")
    reliability_score: Optional[float] = Field(None, description="Selector reliability (0-1)")


class TestItemMetadata(BaseModel):
    """Test item metadata."""
    tags: List[str] = Field(default_factory=list, description="Test tags")
    ai_confidence_score: Optional[float] = Field(None, description="AI confidence (0-1)")
    auto_healing_enabled: bool = Field(default=False, description="Auto-healing enabled")


class TestItemExecutionStats(BaseModel):
    """Execution statistics."""
    count: int = Field(default=0, description="Total execution count")
    last_executed: Optional[datetime] = Field(None, description="Last execution time")
    success_rate: Optional[float] = Field(None, description="Success rate (0-1)")


class TestItemTypeData(BaseModel):
    """Type-specific data for multi-test type support."""
    type_data: Optional[Dict[str, Any]] = Field(None, description="Raw type-specific data")
    typed_data: Optional[Dict[str, Any]] = Field(None, description="Structured type-specific data")


class TestItemResponse(BaseModel):
    """
    Flexible test item response with optional detailed fields and multi-test type support.
    Based on the flexible unified response system from creative design.
    """
    
    # Always included
    core: TestItemCore = Field(..., description="Core test item information")
    
    # Optional detailed fields (included based on request parameters)
    steps: Optional[TestItemSteps] = Field(None, description="Test steps (if requested)")
    selectors: Optional[TestItemSelectors] = Field(None, description="Selectors (if requested)")
    metadata: Optional[TestItemMetadata] = Field(None, description="Metadata (if requested)")
    execution_stats: Optional[TestItemExecutionStats] = Field(None, description="Execution stats (if requested)")
    type_data: Optional[TestItemTypeData] = Field(None, description="Type-specific data (if requested)")
    
    # Computed fields for UI optimization
    computed: Optional[Dict[str, Any]] = Field(None, description="Computed fields for UI")
    
    class Config:
        json_schema_extra = {
            "example": {
                "core": {
                    "id": "60f7b1b9e4b0c8a4f8e6d1a2",
                    "title": "Login with valid credentials",
                    "feature_id": "authentication",
                    "scenario_id": "user_login",
                    "status": "active",
                    "test_type": "bdd",
                    "created_at": "2024-01-15T10:30:00Z",
                    "updated_at": "2024-01-20T14:45:00Z",
                    "created_by_user_id": "60f7b1b9e4b0c8a4f8e6d1a1"
                },
                "steps": {
                    "type": "gherkin",
                    "content": ["Given I am on the login page", "When I enter valid credentials"],
                    "step_count": 2
                },
                "type_data": {
                    "type_data": {"feature_name": "Authentication", "scenario_name": "Login"},
                    "typed_data": {"bdd_blocks": [{"type": "Given", "content": "I am on the login page"}]}
                },
                "computed": {
                    "display_status": "Active",
                    "last_activity": "2 hours ago",
                    "complexity_score": "medium"
                }
            }
        }


class PaginationMeta(BaseModel):
    """Pagination metadata."""
    page: int = Field(..., description="Current page number (1-based)")
    page_size: int = Field(..., description="Items per page")
    total_items: int = Field(..., description="Total number of items")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Has next page")
    has_previous: bool = Field(..., description="Has previous page")


class FilterMeta(BaseModel):
    """Applied filters metadata."""
    feature_id: Optional[str] = Field(None, description="Filtered feature ID")
    scenario_id: Optional[str] = Field(None, description="Filtered scenario ID")
    status: Optional[str] = Field(None, description="Filtered status")
    test_type: Optional[str] = Field(None, description="Filtered test type")
    tags: Optional[List[str]] = Field(None, description="Filtered tags")
    created_after: Optional[datetime] = Field(None, description="Created after date")
    created_before: Optional[datetime] = Field(None, description="Created before date")
    search_query: Optional[str] = Field(None, description="Search query")


class SortMeta(BaseModel):
    """Sorting metadata."""
    sort_by: str = Field(default="created_at", description="Sort field")
    sort_order: str = Field(default="desc", description="Sort order (asc/desc)")


class TestItemListData(BaseModel):
    """Test item list response data."""
    items: List[TestItemResponse] = Field(..., description="Test items")
    pagination: PaginationMeta = Field(..., description="Pagination information")
    filters: FilterMeta = Field(..., description="Applied filters")
    sorting: SortMeta = Field(..., description="Sort configuration")
    summary: Dict[str, Any] = Field(default_factory=dict, description="List summary stats")


class TestItemListResponse(BaseResponse[TestItemListData]):
    """Paginated test item list response."""
    
    @classmethod
    def create_success(
        cls,
        items: List[TestItemResponse],
        pagination: PaginationMeta,
        filters: FilterMeta,
        sorting: SortMeta,
        summary: Optional[Dict[str, Any]] = None,
        message: str = "Test items retrieved successfully"
    ) -> "TestItemListResponse":
        """Create successful list response."""
        return cls(
            success=True,
            data=TestItemListData(
                items=items,
                pagination=pagination,
                filters=filters,
                sorting=sorting,
                summary=summary or {}
            ),
            message=message,
            timestamp=datetime.utcnow()
        )


class TestItemDetailResponse(BaseResponse[TestItemResponse]):
    """Single test item detail response."""
    
    @classmethod  
    def create_success(
        cls,
        test_item: TestItemResponse,
        message: str = "Test item retrieved successfully"
    ) -> "TestItemDetailResponse":
        """Create successful detail response."""
        return cls(
            success=True,
            data=test_item,
            message=message,
            timestamp=datetime.utcnow()
        )


class TestItemCreateResponse(BaseResponse[TestItemResponse]):
    """Test item creation response."""
    
    @classmethod
    def create_success(
        cls,
        test_item: TestItemResponse,
        message: str = "Test item created successfully"
    ) -> "TestItemCreateResponse":
        """Create successful creation response."""
        return cls(
            success=True,
            data=test_item,
            message=message,
            timestamp=datetime.utcnow()
        )


# Response Builder Helper
class TestItemResponseBuilder:
    """
    Builder for constructing TestItemResponse with selective fields.
    Implements the response builder pattern from creative design.
    """
    
    def __init__(self, test_item_model):
        """Initialize builder with test item model."""
        self.model = test_item_model
        self._response = TestItemResponse(core=self._build_core())
    
    def _build_core(self) -> TestItemCore:
        """Build core data (always included)."""
        # Handle enum or string status
        status = self.model.metadata.status
        status_value = status.value if hasattr(status, 'value') else str(status)
        
        return TestItemCore(
            id=self.model.id,
            title=self.model.title,
            feature_id=self.model.feature_id,
            scenario_id=self.model.scenario_id,
            status=status_value,
            test_type=self.model.test_type.value if hasattr(self.model.test_type, 'value') else str(self.model.test_type),
            created_at=self.model.audit.created_at,
            updated_at=self.model.audit.updated_at,
            created_by_user_id=self.model.audit.created_by_user_id
        )
    
    def include_steps(self) -> "TestItemResponseBuilder":
        """Include steps in response."""
        # Handle enum or string type
        step_type = self.model.steps.type
        type_value = step_type.value if hasattr(step_type, 'value') else str(step_type)
        
        self._response.steps = TestItemSteps(
            type=type_value,
            content=self.model.steps.content,
            step_count=self.model.steps.step_count
        )
        return self
    
    def include_selectors(self) -> "TestItemResponseBuilder":
        """Include selectors in response."""
        self._response.selectors = TestItemSelectors(
            primary=self.model.selectors.primary,
            fallback=self.model.selectors.fallback,
            reliability_score=self.model.selectors.reliability_score
        )
        return self
    
    def include_metadata(self) -> "TestItemResponseBuilder":
        """Include metadata in response."""
        self._response.metadata = TestItemMetadata(
            tags=self.model.metadata.tags,
            ai_confidence_score=self.model.metadata.ai_confidence_score,
            auto_healing_enabled=self.model.metadata.auto_healing_enabled
        )
        return self
    
    def include_execution_stats(self) -> "TestItemResponseBuilder":
        """Include execution stats in response."""
        if self.model.metadata.execution_stats:
            stats = self.model.metadata.execution_stats
            self._response.execution_stats = TestItemExecutionStats(
                count=stats.get("count", 0),
                last_executed=stats.get("last_executed"),
                success_rate=stats.get("success_rate")
            )
        return self
    
    def include_type_data(self) -> "TestItemResponseBuilder":
        """Include type-specific data in response."""
        try:
            # Get structured type data if available
            typed_data = self.model.get_typed_data()
            typed_data_dict = typed_data.model_dump() if typed_data else None
        except Exception:
            # If typed data conversion fails, just use None
            typed_data_dict = None
        
        self._response.type_data = TestItemTypeData(
            type_data=self.model.type_data,
            typed_data=typed_data_dict
        )
        return self
    
    def include_computed_fields(self) -> "TestItemResponseBuilder":
        """Add computed fields for UI optimization."""
        # Handle enum or string status
        status = self.model.metadata.status
        status_value = status.value if hasattr(status, 'value') else str(status)
        
        self._response.computed = {
            "display_status": status_value.title(),
            "step_summary": f"{self.model.steps.step_count} steps",
            "tag_summary": f"{len(self.model.metadata.tags)} tags",
            "has_fallback_selectors": bool(self.model.selectors.fallback),
            "last_activity": self._format_last_activity(),
            "complexity_score": self._calculate_complexity()
        }
        return self
    
    def _format_last_activity(self) -> str:
        """Format last activity for display."""
        if self.model.audit.updated_at:
            return f"Updated {self._time_ago(self.model.audit.updated_at)}"
        return f"Created {self._time_ago(self.model.audit.created_at)}"
    
    def _time_ago(self, dt: datetime) -> str:
        """Calculate time ago string."""
        now = datetime.utcnow()
        diff = now - dt
        
        if diff.days > 0:
            return f"{diff.days} days ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hours ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minutes ago"
        else:
            return "Just now"
    
    def _calculate_complexity(self) -> str:
        """Calculate complexity score based on steps and selectors."""
        step_count = self.model.steps.step_count
        selector_count = len(self.model.selectors.primary)
        
        total_complexity = step_count + selector_count
        
        if total_complexity <= 5:
            return "simple"
        elif total_complexity <= 15:
            return "medium"
        else:
            return "complex"
    
    def build(self) -> TestItemResponse:
        """Return constructed response."""
        return self._response
    
    @classmethod
    def build_from_include_fields(
        cls, 
        test_item_model, 
        include_fields: Optional[Set[str]] = None
    ) -> TestItemResponse:
        """
        Build response based on include_fields parameter.
        
        Args:
            test_item_model: TestItemModel instance
            include_fields: Set of fields to include
            
        Returns:
            TestItemResponse with selected fields
        """
        builder = cls(test_item_model)
        
        if not include_fields:
            # Default includes for backward compatibility
            include_fields = {"core", "metadata"}
        
        if "steps" in include_fields:
            builder.include_steps()
        
        if "selectors" in include_fields:
            builder.include_selectors()
        
        if "metadata" in include_fields:
            builder.include_metadata()
        
        if "execution_stats" in include_fields:
            builder.include_execution_stats()
        
        if "type_data" in include_fields:
            builder.include_type_data()
        
        if "computed" in include_fields:
            builder.include_computed_fields()
        
        return builder.build() 
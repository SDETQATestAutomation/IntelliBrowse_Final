"""
Test Suite Response Schemas

Pydantic response models for test suite management API endpoints.
Implements flexible response system with field inclusion control and
standardized BaseResponse patterns following existing codebase conventions.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from ...schemas.response import BaseResponse
from .test_suite_requests import TestSuitePriority, TestSuiteStatus


# Core data models for responses
class TestSuiteCore(BaseModel):
    """
    Core test suite data included in all responses.
    
    Contains essential fields always returned for consistency
    and performance optimization.
    """
    
    id: str = Field(
        ...,
        description="Test suite unique identifier (MongoDB ObjectId)",
        example="60f7b1b9e4b0c8a4f8e6d1a2"
    )
    title: str = Field(
        ...,
        description="Test suite title",
        example="Authentication Test Suite"
    )
    description: Optional[str] = Field(
        None,
        description="Suite description",
        example="Comprehensive authentication flow tests"
    )
    status: str = Field(
        ...,
        description="Suite status (draft, active, archived)",
        example="active"
    )
    priority: str = Field(
        ...,
        description="Suite priority (high, medium, low)",
        example="high"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Suite tags for categorization",
        example=["authentication", "smoke", "critical"]
    )
    owner_id: str = Field(
        ...,
        description="Owner user ID",
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
    total_items: int = Field(
        default=0,
        description="Total number of test items in the suite",
        example=5
    )
    active_items: int = Field(
        default=0,
        description="Number of active (non-skipped) test items",
        example=4
    )


class SuiteItemConfig(BaseModel):
    """
    Test item configuration within a suite.
    
    Contains per-suite item configuration including order,
    skip flags, custom tags, and notes.
    """
    
    test_item_id: str = Field(
        ...,
        description="Reference to test item",
        example="67890abcdef123456789"
    )
    order: int = Field(
        ...,
        description="Execution order within suite",
        example=1
    )
    skip: bool = Field(
        default=False,
        description="Skip flag for conditional execution",
        example=False
    )
    custom_tags: List[str] = Field(
        default_factory=list,
        description="Additional tags specific to this item in the suite",
        example=["critical", "login"]
    )
    note: Optional[str] = Field(
        None,
        description="Optional note for execution context",
        example="Core login functionality - always run first"
    )
    
    # Optional enriched data (when available)
    test_item_title: Optional[str] = Field(
        None,
        description="Test item title (if enriched)",
        example="Login with valid credentials"
    )
    test_item_status: Optional[str] = Field(
        None,
        description="Test item status (if enriched)",
        example="active"
    )


class TestSuiteItems(BaseModel):
    """
    Test suite items collection with metadata.
    
    Contains all test items in the suite with their configurations
    and optional enrichment data.
    """
    
    items: List[SuiteItemConfig] = Field(
        default_factory=list,
        description="Test items in the suite"
    )
    items_count: int = Field(
        ...,
        description="Total number of items",
        example=5
    )
    active_count: int = Field(
        ...,
        description="Number of active (non-skipped) items",
        example=4
    )
    order_range: Dict[str, int] = Field(
        default_factory=dict,
        description="Order value range (min, max)",
        example={"min": 1, "max": 5}
    )


class TestSuiteStatistics(BaseModel):
    """
    Computed suite statistics for UI optimization.
    
    Pre-computed fields to reduce client-side processing
    and improve UI responsiveness.
    """
    
    completion_percentage: float = Field(
        default=0.0,
        description="Suite completion percentage (0-100)",
        example=80.0
    )
    execution_time_estimate: Optional[int] = Field(
        None,
        description="Estimated execution time in seconds",
        example=300
    )
    complexity_score: Optional[float] = Field(
        None,
        description="Suite complexity score (0-1)",
        example=0.75
    )
    last_activity: Optional[str] = Field(
        None,
        description="Human-readable last activity",
        example="Updated 2 days ago"
    )
    tag_summary: Dict[str, int] = Field(
        default_factory=dict,
        description="Tag usage counts",
        example={"critical": 3, "smoke": 2, "integration": 1}
    )


class TestSuiteResponse(BaseModel):
    """
    Flexible test suite response with optional detailed fields.
    
    Supports field inclusion control for performance optimization.
    Core fields are always included, detailed fields are optional.
    """
    
    # Always included core data
    core: TestSuiteCore = Field(
        ...,
        description="Core suite information"
    )
    
    # Optional detailed fields (included based on request)
    items: Optional[TestSuiteItems] = Field(
        None,
        description="Suite items with configurations (if requested)"
    )
    statistics: Optional[TestSuiteStatistics] = Field(
        None,
        description="Computed statistics (if requested)"
    )
    
    # Computed fields for UI optimization
    computed: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional computed fields for UI"
    )
    
    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "examples": {
                "core_only": {
                    "summary": "Core suite data only",
                    "value": {
                        "core": {
                            "id": "60f7b1b9e4b0c8a4f8e6d1a2",
                            "title": "Authentication Test Suite",
                            "description": "Comprehensive authentication flow tests",
                            "status": "active",
                            "priority": "high",
                            "tags": ["authentication", "smoke", "critical"],
                            "owner_id": "60f7b1b9e4b0c8a4f8e6d1a3",
                            "created_at": "2024-01-15T10:30:00Z",
                            "updated_at": "2024-01-20T14:45:00Z",
                            "total_items": 5,
                            "active_items": 4
                        }
                    }
                },
                "with_items": {
                    "summary": "Suite with item details",
                    "value": {
                        "core": {
                            "id": "60f7b1b9e4b0c8a4f8e6d1a2",
                            "title": "Authentication Test Suite",
                            "status": "active",
                            "priority": "high",
                            "tags": ["authentication", "smoke"],
                            "owner_id": "60f7b1b9e4b0c8a4f8e6d1a3",
                            "created_at": "2024-01-15T10:30:00Z",
                            "total_items": 2,
                            "active_items": 2
                        },
                        "items": {
                            "items": [
                                {
                                    "test_item_id": "67890abcdef123456789",
                                    "order": 1,
                                    "skip": False,
                                    "custom_tags": ["critical", "login"],
                                    "note": "Core login functionality",
                                    "test_item_title": "Login with valid credentials",
                                    "test_item_status": "active"
                                }
                            ],
                            "items_count": 2,
                            "active_count": 2,
                            "order_range": {"min": 1, "max": 2}
                        }
                    }
                }
            }
        }


# Pagination and metadata models (reuse from test items pattern)
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
    tags: Optional[List[str]] = Field(None, description="Filtered tags")
    title_search: Optional[str] = Field(None, description="Search query")
    has_items: Optional[bool] = Field(None, description="Items filter")


class SortMeta(BaseModel):
    """Sorting metadata."""
    
    sort_by: str = Field(default="updated_at", description="Sort field")
    sort_order: str = Field(default="desc", description="Sort order")


class TestSuiteListData(BaseModel):
    """Test suite list response data."""
    
    suites: List[TestSuiteResponse] = Field(
        ...,
        description="Test suites"
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
        description="List summary statistics"
    )


# Response classes extending BaseResponse
class TestSuiteCreateResponse(BaseResponse[TestSuiteResponse]):
    """Response for test suite creation."""
    
    @classmethod
    def create_success(
        cls,
        test_suite: TestSuiteResponse,
        message: str = "Test suite created successfully"
    ) -> "TestSuiteCreateResponse":
        """Create successful creation response."""
        return cls(
            success=True,
            data=test_suite,
            message=message,
            timestamp=datetime.utcnow()
        )
    
    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {
                    "core": {
                        "id": "60f7b1b9e4b0c8a4f8e6d1a2",
                        "title": "Authentication Test Suite",
                        "description": "Comprehensive authentication flow tests",
                        "status": "draft",
                        "priority": "high",
                        "tags": ["authentication", "smoke"],
                        "owner_id": "60f7b1b9e4b0c8a4f8e6d1a3",
                        "created_at": "2024-01-15T10:30:00Z",
                        "updated_at": "2024-01-15T10:30:00Z",
                        "total_items": 2,
                        "active_items": 2
                    }
                },
                "message": "Test suite created successfully",
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }


class TestSuiteDetailResponse(BaseResponse[TestSuiteResponse]):
    """Response for test suite detail retrieval."""
    
    @classmethod
    def create_success(
        cls,
        test_suite: TestSuiteResponse,
        message: str = "Test suite retrieved successfully"
    ) -> "TestSuiteDetailResponse":
        """Create successful detail response."""
        return cls(
            success=True,
            data=test_suite,
            message=message,
            timestamp=datetime.utcnow()
        )
    
    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {
                    "core": {
                        "id": "60f7b1b9e4b0c8a4f8e6d1a2",
                        "title": "Authentication Test Suite",
                        "status": "active",
                        "priority": "high",
                        "tags": ["authentication", "smoke"],
                        "owner_id": "60f7b1b9e4b0c8a4f8e6d1a3",
                        "created_at": "2024-01-15T10:30:00Z",
                        "updated_at": "2024-01-20T14:45:00Z",
                        "total_items": 3,
                        "active_items": 3
                    },
                    "items": {
                        "items": [
                            {
                                "test_item_id": "67890abcdef123456789",
                                "order": 1,
                                "skip": False,
                                "custom_tags": ["critical"],
                                "note": "Core login functionality",
                                "test_item_title": "Login with valid credentials",
                                "test_item_status": "active"
                            }
                        ],
                        "items_count": 3,
                        "active_count": 3,
                        "order_range": {"min": 1, "max": 3}
                    },
                    "statistics": {
                        "completion_percentage": 100.0,
                        "execution_time_estimate": 180,
                        "complexity_score": 0.8,
                        "last_activity": "Updated 3 hours ago",
                        "tag_summary": {"critical": 2, "smoke": 1}
                    }
                },
                "message": "Test suite retrieved successfully",
                "timestamp": "2024-01-20T14:45:00Z"
            }
        }


class TestSuiteListResponse(BaseResponse[TestSuiteListData]):
    """Response for test suite list with pagination."""
    
    @classmethod
    def create_success(
        cls,
        suites: List[TestSuiteResponse],
        pagination: PaginationMeta,
        filters: FilterMeta,
        sorting: SortMeta,
        summary: Optional[Dict[str, Any]] = None,
        message: str = "Test suites retrieved successfully"
    ) -> "TestSuiteListResponse":
        """Create successful list response."""
        return cls(
            success=True,
            data=TestSuiteListData(
                suites=suites,
                pagination=pagination,
                filters=filters,
                sorting=sorting,
                summary=summary or {}
            ),
            message=message,
            timestamp=datetime.utcnow()
        )
    
    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {
                    "suites": [
                        {
                            "core": {
                                "id": "60f7b1b9e4b0c8a4f8e6d1a2",
                                "title": "Authentication Test Suite",
                                "status": "active",
                                "priority": "high",
                                "tags": ["authentication", "smoke"],
                                "owner_id": "60f7b1b9e4b0c8a4f8e6d1a3",
                                "created_at": "2024-01-15T10:30:00Z",
                                "updated_at": "2024-01-20T14:45:00Z",
                                "total_items": 5,
                                "active_items": 4
                            }
                        }
                    ],
                    "pagination": {
                        "page": 1,
                        "page_size": 20,
                        "total_items": 1,
                        "total_pages": 1,
                        "has_next": False,
                        "has_previous": False
                    },
                    "filters": {
                        "status": "active",
                        "priority": "high"
                    },
                    "sorting": {
                        "sort_by": "updated_at",
                        "sort_order": "desc"
                    },
                    "summary": {
                        "total_suites": 1,
                        "active_suites": 1,
                        "total_test_items": 5
                    }
                },
                "message": "Test suites retrieved successfully",
                "timestamp": "2024-01-20T14:45:00Z"
            }
        }


class TestSuiteUpdateResponse(BaseResponse[TestSuiteResponse]):
    """Response for test suite update operations."""
    
    @classmethod
    def create_success(
        cls,
        test_suite: TestSuiteResponse,
        message: str = "Test suite updated successfully"
    ) -> "TestSuiteUpdateResponse":
        """Create successful update response."""
        return cls(
            success=True,
            data=test_suite,
            message=message,
            timestamp=datetime.utcnow()
        )
    
    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {
                    "core": {
                        "id": "60f7b1b9e4b0c8a4f8e6d1a2",
                        "title": "Enhanced Authentication Test Suite",
                        "description": "Updated comprehensive authentication flow tests",
                        "status": "active",
                        "priority": "high",
                        "tags": ["authentication", "smoke", "regression"],
                        "owner_id": "60f7b1b9e4b0c8a4f8e6d1a3",
                        "created_at": "2024-01-15T10:30:00Z",
                        "updated_at": "2024-01-20T15:00:00Z",
                        "total_items": 5,
                        "active_items": 4
                    }
                },
                "message": "Test suite updated successfully",
                "timestamp": "2024-01-20T15:00:00Z"
            }
        }


# Bulk operation response models
class BulkOperationItem(BaseModel):
    """Individual item result in bulk operations."""
    
    test_item_id: str = Field(
        ...,
        description="Test item ID",
        example="67890abcdef123456789"
    )
    status: str = Field(
        ...,
        description="Operation status (success, invalid, duplicate, not_found)",
        example="success"
    )
    message: Optional[str] = Field(
        None,
        description="Result message or error description",
        example="Item added successfully"
    )


class BulkOperationResult(BaseModel):
    """Bulk operation result summary."""
    
    total_requested: int = Field(
        ...,
        description="Total items requested for operation",
        example=5
    )
    successful: int = Field(
        ...,
        description="Number of successful operations",
        example=3
    )
    failed: int = Field(
        ...,
        description="Number of failed operations",
        example=2
    )
    success_items: List[BulkOperationItem] = Field(
        default_factory=list,
        description="Successfully processed items"
    )
    failed_items: List[BulkOperationItem] = Field(
        default_factory=list,
        description="Failed items with error details"
    )
    overall_success: bool = Field(
        ...,
        description="True if all operations succeeded",
        example=False
    )


class BulkOperationResponse(BaseResponse[BulkOperationResult]):
    """Response for bulk operations (add/remove items)."""
    
    @classmethod
    def create_success(
        cls,
        result: BulkOperationResult,
        message: str = "Bulk operation completed"
    ) -> "BulkOperationResponse":
        """Create bulk operation response."""
        return cls(
            success=True,
            data=result,
            message=message,
            timestamp=datetime.utcnow()
        )
    
    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {
                    "total_requested": 3,
                    "successful": 2,
                    "failed": 1,
                    "success_items": [
                        {
                            "test_item_id": "67890abcdef123456791",
                            "status": "success",
                            "message": "Item added successfully"
                        },
                        {
                            "test_item_id": "67890abcdef123456792",
                            "status": "success",
                            "message": "Item added successfully"
                        }
                    ],
                    "failed_items": [
                        {
                            "test_item_id": "67890abcdef123456793",
                            "status": "invalid",
                            "message": "Test item not found or access denied"
                        }
                    ],
                    "overall_success": False
                },
                "message": "Bulk operation completed with partial success",
                "timestamp": "2024-01-20T15:30:00Z"
            }
        }


# Response builder utility (following test item pattern)
class TestSuiteResponseBuilder:
    """
    Builder for constructing TestSuiteResponse with selective field inclusion.
    
    Implements the flexible response system pattern from creative phase
    for performance optimization through field control.
    """
    
    def __init__(self, suite_document: Dict[str, Any]):
        """Initialize builder with suite document data."""
        self.document = suite_document
        self._response = TestSuiteResponse(core=self._build_core())
    
    def _build_core(self) -> TestSuiteCore:
        """Build core suite data from document."""
        return TestSuiteCore(
            id=str(self.document.get("_id")),
            title=self.document.get("title", ""),
            description=self.document.get("description"),
            status=self.document.get("status", "draft"),
            priority=self.document.get("priority", "medium"),
            tags=self.document.get("tags", []),
            owner_id=str(self.document.get("owner_id", "")),
            created_at=self.document.get("created_at"),
            updated_at=self.document.get("updated_at"),
            total_items=len(self.document.get("suite_items", [])),
            active_items=len([
                item for item in self.document.get("suite_items", [])
                if not item.get("skip", False)
            ])
        )
    
    def include_items(self, enrich_test_items: bool = False) -> "TestSuiteResponseBuilder":
        """Include suite items with optional test item enrichment."""
        suite_items = self.document.get("suite_items", [])
        
        items = []
        for item in suite_items:
            item_config = SuiteItemConfig(
                test_item_id=item.get("test_item_id", ""),
                order=item.get("order", 0),
                skip=item.get("skip", False),
                custom_tags=item.get("custom_tags", []),
                note=item.get("note")
            )
            
            # Add enriched data if available
            if enrich_test_items and "test_item_data" in item:
                item_config.test_item_title = item["test_item_data"].get("title")
                item_config.test_item_status = item["test_item_data"].get("status")
            
            items.append(item_config)
        
        # Calculate order range
        orders = [item.order for item in items] if items else [0]
        order_range = {"min": min(orders), "max": max(orders)}
        
        self._response.items = TestSuiteItems(
            items=items,
            items_count=len(items),
            active_count=len([item for item in items if not item.skip]),
            order_range=order_range
        )
        
        return self
    
    def include_statistics(self) -> "TestSuiteResponseBuilder":
        """Include computed statistics."""
        suite_items = self.document.get("suite_items", [])
        total_items = len(suite_items)
        active_items = len([item for item in suite_items if not item.get("skip", False)])
        
        # Calculate completion percentage
        completion_percentage = (active_items / max(total_items, 1)) * 100
        
        # Calculate tag summary
        tag_summary = {}
        for item in suite_items:
            for tag in item.get("custom_tags", []):
                tag_summary[tag] = tag_summary.get(tag, 0) + 1
        
        # Format last activity
        updated_at = self.document.get("updated_at")
        last_activity = self._format_last_activity(updated_at) if updated_at else None
        
        self._response.statistics = TestSuiteStatistics(
            completion_percentage=completion_percentage,
            execution_time_estimate=total_items * 60,  # Estimate 1 minute per item
            complexity_score=min(total_items / 10.0, 1.0),  # Simple complexity scoring
            last_activity=last_activity,
            tag_summary=tag_summary
        )
        
        return self
    
    def include_computed_fields(self) -> "TestSuiteResponseBuilder":
        """Include additional computed fields for UI optimization."""
        computed = {
            "can_execute": self._response.core.status == "active" and self._response.core.active_items > 0,
            "priority_weight": {"high": 3, "medium": 2, "low": 1}.get(self._response.core.priority, 2),
            "status_color": {"draft": "gray", "active": "green", "archived": "red"}.get(self._response.core.status, "gray"),
            "items_summary": f"{self._response.core.active_items}/{self._response.core.total_items} active"
        }
        
        self._response.computed = computed
        return self
    
    def _format_last_activity(self, dt: datetime) -> str:
        """Format last activity timestamp for human readability."""
        if not dt:
            return "Never"
        
        now = datetime.utcnow()
        diff = now - dt
        
        if diff.days > 0:
            return f"Updated {diff.days} day{'s' if diff.days != 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"Updated {hours} hour{'s' if hours != 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"Updated {minutes} minute{'s' if minutes != 1 else ''} ago"
        else:
            return "Updated just now"
    
    def build(self) -> TestSuiteResponse:
        """Build the final response."""
        return self._response
    
    @classmethod
    def build_from_document(
        cls,
        document: Dict[str, Any],
        include_items: bool = False,
        include_statistics: bool = False,
        include_computed: bool = False,
        enrich_test_items: bool = False
    ) -> TestSuiteResponse:
        """
        Build response from document with optional field inclusion.
        
        Args:
            document: MongoDB document
            include_items: Include suite items
            include_statistics: Include computed statistics
            include_computed: Include computed fields
            enrich_test_items: Enrich items with test item data
            
        Returns:
            TestSuiteResponse with requested fields
        """
        builder = cls(document)
        
        if include_items:
            builder.include_items(enrich_test_items)
        
        if include_statistics:
            builder.include_statistics()
        
        if include_computed:
            builder.include_computed_fields()
        
        return builder.build() 
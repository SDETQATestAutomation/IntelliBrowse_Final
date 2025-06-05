"""
Test Suite Request Schemas

Pydantic request models for test suite management API endpoints.
Implements comprehensive validation, OpenAPI examples, and clean separation of concerns.
Follows architectural decisions from creative phase for bulk operations and validation.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, validator, model_validator

# Import enums that will be defined in models layer
# These will be imported from the models layer once it's implemented
from enum import Enum as PyEnum

class TestSuitePriority(str, PyEnum):
    """Test suite priority levels."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class TestSuiteStatus(str, PyEnum):
    """Test suite status values."""
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


# Base models for reuse (DRY principle)
class BaseSuiteItemConfig(BaseModel):
    """Base model for suite item configuration."""
    test_item_id: str = Field(
        ...,
        description="Reference to existing test item (MongoDB ObjectId format)",
        min_length=24,
        max_length=24,
        pattern=r"^[0-9a-fA-F]{24}$"
    )
    order: int = Field(
        default=0,
        description="Execution order within suite (0-based indexing)",
        ge=0
    )
    skip: bool = Field(
        default=False,
        description="Skip flag for conditional execution"
    )
    custom_tags: List[str] = Field(
        default_factory=list,
        description="Additional tags specific to this item in the suite"
    )
    note: Optional[str] = Field(
        None,
        description="Optional note for execution context",
        max_length=500
    )


class CreateTestSuiteRequest(BaseModel):
    """
    Request schema for creating a new test suite.
    
    Supports optional initial test items with configuration and validation.
    Implements batch validation strategy from creative phase decisions.
    """
    
    title: str = Field(
        ...,
        description="Descriptive name for the suite (must be unique per user)",
        min_length=1,
        max_length=200
    )
    description: Optional[str] = Field(
        None,
        description="Detailed description of the suite's purpose",
        max_length=1000
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Labels for categorization and filtering"
    )
    priority: TestSuitePriority = Field(
        default=TestSuitePriority.MEDIUM,
        description="Suite priority level (high, medium, low)"
    )
    suite_items: List[BaseSuiteItemConfig] = Field(
        default_factory=list,
        description="Initial test items with configuration",
        max_items=100  # Bulk operation limit from creative phase
    )
    
    @validator('title')
    def validate_title(cls, v):
        """Validate title is not empty or whitespace-only."""
        if not v.strip():
            raise ValueError("Title cannot be empty or only whitespace")
        return v.strip()
    
    @validator('tags')
    def validate_tags(cls, v):
        """Validate and normalize tags."""
        if v:
            # Remove duplicates, empty tags, and normalize
            normalized_tags = []
            seen = set()
            for tag in v:
                normalized = tag.strip().lower()
                if normalized and normalized not in seen:
                    normalized_tags.append(tag.strip())  # Keep original case
                    seen.add(normalized)
            return normalized_tags
        return v
    
    @validator('suite_items')
    def validate_suite_items(cls, v):
        """Validate suite items for duplicates and constraints."""
        if not v:
            return v
            
        # Check for duplicate test item IDs
        item_ids = [item.test_item_id for item in v]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("Duplicate test items are not allowed within the same suite")
        
        # Validate order values are sequential and non-negative
        orders = [item.order for item in v]
        if any(order < 0 for order in orders):
            raise ValueError("Order values must be non-negative")
            
        return v
    
    class Config:
        """Pydantic model configuration."""
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "title": "Authentication Test Suite",
                "description": "Comprehensive authentication flow tests covering login, logout, and password management",
                "tags": ["authentication", "smoke", "critical"],
                "priority": "high",
                "suite_items": [
                    {
                        "test_item_id": "67890abcdef123456789",
                        "order": 1,
                        "skip": False,
                        "custom_tags": ["login", "critical"],
                        "note": "Core login functionality - always run first"
                    },
                    {
                        "test_item_id": "67890abcdef123456790", 
                        "order": 2,
                        "skip": False,
                        "custom_tags": ["password", "security"],
                        "note": "Password reset flow validation"
                    }
                ]
            }
        }


class UpdateTestSuiteRequest(BaseModel):
    """
    Request schema for updating test suite metadata.
    
    Supports partial updates with null field handling.
    Does not affect test item configurations - use bulk operations for those.
    """
    
    title: Optional[str] = Field(
        None,
        description="Updated suite title (must remain unique per user)",
        min_length=1,
        max_length=200
    )
    description: Optional[str] = Field(
        None,
        description="Updated suite description",
        max_length=1000
    )
    tags: Optional[List[str]] = Field(
        None,
        description="Updated suite tags (replaces existing tags)"
    )
    priority: Optional[TestSuitePriority] = Field(
        None,
        description="Updated priority level (high, medium, low)"
    )
    status: Optional[TestSuiteStatus] = Field(
        None,
        description="Updated suite status (draft, active, archived)"
    )
    
    @validator('title')
    def validate_title(cls, v):
        """Validate title if provided."""
        if v is not None and not v.strip():
            raise ValueError("Title cannot be empty or only whitespace")
        return v.strip() if v else v
    
    @validator('tags')
    def validate_tags(cls, v):
        """Validate and normalize tags if provided."""
        if v is not None:
            # Same normalization logic as create request
            normalized_tags = []
            seen = set()
            for tag in v:
                normalized = tag.strip().lower()
                if normalized and normalized not in seen:
                    normalized_tags.append(tag.strip())
                    seen.add(normalized)
            return normalized_tags
        return v
    
    @model_validator(mode='before')
    @classmethod
    def validate_at_least_one_field(cls, values):
        """Ensure at least one field is provided for update."""
        provided_fields = [k for k, v in values.items() if v is not None]
        if not provided_fields:
            raise ValueError("At least one field must be provided for update")
        return values
    
    class Config:
        """Pydantic model configuration."""
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "title": "Enhanced Authentication Test Suite",
                "description": "Updated comprehensive authentication flow tests with additional edge cases",
                "tags": ["authentication", "smoke", "regression", "security"],
                "priority": "high",
                "status": "active"
            }
        }


class BulkAddItemsRequest(BaseModel):
    """
    Request schema for bulk adding test items to a suite.
    
    Implements validated bulk operations pattern from creative phase with
    comprehensive validation and partial success handling.
    """
    
    items: List[BaseSuiteItemConfig] = Field(
        ...,
        description="Test items to add to the suite",
        min_items=1,
        max_items=100  # Performance limit from creative phase
    )
    
    @validator('items')
    def validate_items(cls, v):
        """Validate items for duplicates and constraints."""
        if not v:
            raise ValueError("At least one item must be provided")
        
        # Check for duplicate test item IDs within the request
        item_ids = [item.test_item_id for item in v]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("Duplicate test items are not allowed within the same bulk operation")
        
        return v
    
    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "items": [
                    {
                        "test_item_id": "67890abcdef123456791",
                        "order": 10,
                        "skip": False,
                        "custom_tags": ["integration", "api"],
                        "note": "API integration test - requires valid API key"
                    },
                    {
                        "test_item_id": "67890abcdef123456792",
                        "order": 11,
                        "skip": True,
                        "custom_tags": ["flaky", "performance"],
                        "note": "Currently unstable - skip in CI until fixed"
                    }
                ]
            }
        }


class BulkRemoveItemsRequest(BaseModel):
    """
    Request schema for bulk removing test items from a suite.
    
    Supports removal by test item ID list with optional order rebalancing.
    """
    
    test_item_ids: List[str] = Field(
        ...,
        description="List of test item IDs to remove from the suite",
        min_items=1,
        max_items=100
    )
    rebalance_order: bool = Field(
        default=True,
        description="Automatically rebalance order values after removal"
    )
    
    @validator('test_item_ids')
    def validate_test_item_ids(cls, v):
        """Validate test item IDs format and uniqueness."""
        if not v:
            raise ValueError("At least one test item ID must be provided")
        
        # Check for duplicates
        if len(v) != len(set(v)):
            raise ValueError("Duplicate test item IDs are not allowed")
        
        # Validate ObjectId format
        for item_id in v:
            if not isinstance(item_id, str) or len(item_id) != 24:
                raise ValueError(f"Invalid test item ID format: {item_id}")
        
        return v
    
    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "test_item_ids": [
                    "67890abcdef123456791",
                    "67890abcdef123456792"
                ],
                "rebalance_order": True
            }
        }


class FilterTestSuitesRequest(BaseModel):
    """
    Request schema for filtering and paginating test suites.
    
    Supports comprehensive filtering, pagination, and sorting options
    as defined in the routes layer.
    """
    
    # Filtering parameters
    status: Optional[TestSuiteStatus] = Field(
        None,
        description="Filter by suite status"
    )
    priority: Optional[TestSuitePriority] = Field(
        None,
        description="Filter by priority level"
    )
    tags: Optional[List[str]] = Field(
        None,
        description="Filter by tags (AND operation - suite must have all specified tags)"
    )
    title_search: Optional[str] = Field(
        None,
        description="Search in suite titles (case-insensitive)",
        min_length=1,
        max_length=100
    )
    has_items: Optional[bool] = Field(
        None,
        description="Filter suites with/without test items"
    )
    
    # Pagination parameters
    page: int = Field(
        default=1,
        description="Page number (1-based)",
        ge=1
    )
    page_size: int = Field(
        default=20,
        description="Items per page",
        ge=1,
        le=100
    )
    
    # Sorting parameters
    sort_by: str = Field(
        default="updated_at",
        description="Field to sort by"
    )
    sort_order: str = Field(
        default="desc",
        description="Sort order (asc, desc)"
    )
    
    @validator('tags')
    def validate_tags(cls, v):
        """Validate tags for filtering."""
        if v:
            # Remove empty tags and normalize
            return [tag.strip() for tag in v if tag.strip()]
        return v
    
    @validator('sort_order')
    def validate_sort_order(cls, v):
        """Validate sort order values."""
        if v not in ['asc', 'desc']:
            raise ValueError("Sort order must be 'asc' or 'desc'")
        return v
    
    @validator('sort_by')
    def validate_sort_by(cls, v):
        """Validate sort field options."""
        allowed_fields = [
            'created_at', 'updated_at', 'title', 'priority', 'total_items'
        ]
        if v not in allowed_fields:
            raise ValueError(f"Sort field must be one of: {', '.join(allowed_fields)}")
        return v
    
    class Config:
        """Pydantic model configuration."""
        use_enum_values = True
        json_schema_extra = {
            "examples": {
                "all_suites": {
                    "summary": "List all suites with default pagination",
                    "value": {
                        "page": 1,
                        "page_size": 20,
                        "sort_by": "updated_at",
                        "sort_order": "desc"
                    }
                },
                "active_high_priority": {
                    "summary": "Filter active high-priority suites",
                    "value": {
                        "status": "active",
                        "priority": "high",
                        "page": 1,
                        "page_size": 10,
                        "sort_by": "updated_at",
                        "sort_order": "desc"
                    }
                },
                "tagged_suites": {
                    "summary": "Filter suites by tags",
                    "value": {
                        "tags": ["smoke", "regression"],
                        "page": 1,
                        "page_size": 20,
                        "sort_by": "title",
                        "sort_order": "asc"
                    }
                },
                "search_authentication": {
                    "summary": "Search for authentication-related suites",
                    "value": {
                        "title_search": "authentication",
                        "has_items": True,
                        "page": 1,
                        "page_size": 20,
                        "sort_by": "updated_at",
                        "sort_order": "desc"
                    }
                }
            }
        } 
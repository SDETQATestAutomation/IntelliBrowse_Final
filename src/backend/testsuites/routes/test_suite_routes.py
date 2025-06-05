"""
Test Suite FastAPI Routes

RESTful API endpoints for test suite management with comprehensive functionality including:
- Suite creation with optional initial test items
- Metadata updates (title, tags, priority, status)
- Bulk test item operations (add/remove with partial success handling)
- Soft deletion and archiving
- Performance monitoring and observability
- Advanced filtering and pagination

Follows Clean Architecture with dependency injection, observability integration,
and the architectural decisions finalized in the creative phase.
"""

from typing import Optional, List, Annotated
from fastapi import APIRouter, Depends, Query, Path, Body, status, Request, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from ...config.env import get_settings
from ...config.logging import get_logger
from ...auth.dependencies.auth_dependencies import get_current_user
from ...auth.schemas.auth_responses import UserResponse
from ..services.test_suite_service import TestSuiteService
from ..services.validation_service import TestItemValidationService
from ..services.bulk_operation_service import BulkOperationService
from ..services.observability_service import SuiteObservabilityService
from ..controllers.test_suite_controller import TestSuiteController, TestSuiteControllerFactory
from ..schemas.test_suite_requests import (
    CreateTestSuiteRequest,
    UpdateTestSuiteRequest,
    BulkAddItemsRequest,
    BulkRemoveItemsRequest,
    FilterTestSuitesRequest
)
from ..schemas.test_suite_responses import (
    TestSuiteCreateResponse,
    TestSuiteDetailResponse,
    TestSuiteListResponse,
    TestSuiteUpdateResponse,
    BulkOperationResponse
)
from ..models.test_suite_model import TestSuitePriority, TestSuiteStatus

logger = get_logger(__name__)

# Create router with prefix and tags
router = APIRouter(
    prefix="/suites",
    tags=["Test Suites"],
    responses={
        401: {"description": "Unauthorized - Invalid or missing authentication"},
        403: {"description": "Forbidden - Insufficient permissions"},
        500: {"description": "Internal Server Error"}
    }
)


# Dependency injection for services
async def get_test_suite_service(request: Request) -> TestSuiteService:
    """
    Get TestSuiteService dependency from FastAPI app state.
    
    Args:
        request: FastAPI request object containing app state
        
    Returns:
        TestSuiteService instance with database connection
    """
    db = request.app.state.db
    return TestSuiteService(db)


async def get_validation_service(request: Request) -> TestItemValidationService:
    """Get TestItemValidationService dependency."""
    db = request.app.state.db
    return TestItemValidationService(db)


async def get_bulk_operation_service(
    suite_service: TestSuiteService = Depends(get_test_suite_service),
    validation_service: TestItemValidationService = Depends(get_validation_service)
) -> BulkOperationService:
    """Get BulkOperationService dependency."""
    return BulkOperationService(suite_service, validation_service)


async def get_observability_service() -> SuiteObservabilityService:
    """Get SuiteObservabilityService dependency."""
    return SuiteObservabilityService()


async def get_test_suite_controller(
    suite_service: TestSuiteService = Depends(get_test_suite_service),
    bulk_service: BulkOperationService = Depends(get_bulk_operation_service),
    observability_service: SuiteObservabilityService = Depends(get_observability_service)
) -> TestSuiteController:
    """Get TestSuiteController dependency."""
    return TestSuiteControllerFactory.create(suite_service, bulk_service, observability_service)


@router.post(
    "/",
    response_model=TestSuiteCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new test suite",
    description="""
    Create a new test suite with metadata and optional initial test items.
    
    Test suites enable organized grouping of test items into executable units with:
    - Suite-level metadata (title, description, tags, priority)
    - Owner-based access control (scoped to authenticated user)
    - Optional initial test items with configuration (order, skip flags, notes)
    - Automatic validation of test item references
    - Status tracking (draft by default)
    
    **Required fields:**
    - title: Descriptive name for the suite (must be unique per user)
    
    **Optional fields:**
    - description: Detailed description of the suite's purpose
    - tags: Labels for categorization and filtering
    - priority: Suite priority level (high, medium, low) - defaults to 'medium'
    - suite_items: Initial test items with configuration
    
    **Suite Item Configuration:**
    - test_item_id: Reference to existing test item (validated)
    - order: Execution order within suite (0-based indexing)
    - skip: Skip flag for conditional execution
    - custom_tags: Additional tags specific to this item in the suite
    - note: Optional note for execution context
    
    **Validation:**
    - All test_item_id references are validated against user's test items
    - Duplicate test items within the same suite are prevented
    - Title uniqueness is enforced per user
    
    **Performance:**
    - Batch validation for multiple test items
    - Single atomic operation for suite creation
    - Optimized MongoDB indexing for fast queries
    """,
    responses={
        201: {
            "description": "Test suite created successfully",
            "model": TestSuiteCreateResponse
        },
        400: {
            "description": "Validation error in request data",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": None,
                        "message": "Validation error: Invalid test item references found",
                        "errors": ["test_item_123: Item not found", "test_item_456: Access denied"],
                        "timestamp": "2024-01-15T10:30:00Z"
                    }
                }
            }
        },
        409: {
            "description": "Suite title conflict",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": None,
                        "message": "Suite with title 'Authentication Tests' already exists",
                        "timestamp": "2024-01-15T10:30:00Z"
                    }
                }
            }
        }
    }
)
async def create_test_suite(
    request: CreateTestSuiteRequest = Body(
        ...,
        description="Test suite creation data",
        example={
            "title": "Authentication Test Suite",
            "description": "Comprehensive authentication flow tests",
            "tags": ["authentication", "smoke"],
            "priority": "high",
            "suite_items": [
                {
                    "test_item_id": "67890abcdef123456789",
                    "order": 1,
                    "skip": False,
                    "custom_tags": ["critical"],
                    "note": "Core login functionality"
                },
                {
                    "test_item_id": "67890abcdef123456790",
                    "order": 2,
                    "skip": False,
                    "custom_tags": ["password"],
                    "note": "Password reset flow"
                }
            ]
        }
    ),
    current_user: UserResponse = Depends(get_current_user),
    controller: TestSuiteController = Depends(get_test_suite_controller)
) -> TestSuiteCreateResponse:
    """
    Create a new test suite.
    
    Creates a test suite with the provided metadata and optional test items.
    All test item references are validated before creation.
    """
    logger.info(
        f"Create test suite endpoint called: {request.title}",
        extra={
            "user_id": current_user.id,
            "suite_title": request.title,
            "initial_items_count": len(request.suite_items) if request.suite_items else 0,
            "endpoint": "POST /suites/"
        }
    )
    
    return await controller.create_test_suite(request, current_user.id)


@router.get(
    "/{suite_id}",
    response_model=TestSuiteDetailResponse,
    summary="Get test suite by ID",
    description="""
    Retrieve a specific test suite by its ID with complete details.
    
    Returns comprehensive suite information including:
    - Core metadata (title, description, tags, priority, status)
    - All test items with their configurations
    - Computed statistics (total items, active items)
    - Audit information (creation/update timestamps, owner)
    
    **Access Control:**
    - Only the suite owner can access the suite
    - Soft-deleted suites are not accessible unless explicitly requested
    
    **Field Inclusion:**
    The response includes all suite data by default. For performance optimization
    in list views, use the list endpoint with selective field inclusion.
    
    **Performance:**
    - Single MongoDB query with embedded item configurations
    - Optimized for suites with up to 1000 test items
    - Sub-50ms response time target for typical suites
    """,
    responses={
        200: {
            "description": "Test suite retrieved successfully",
            "model": TestSuiteDetailResponse
        },
        404: {
            "description": "Test suite not found or access denied",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": None,
                        "message": "Test suite not found",
                        "timestamp": "2024-01-15T10:30:00Z"
                    }
                }
            }
        }
    }
)
async def get_test_suite(
    suite_id: Annotated[str, Path(
        description="Test suite ID (MongoDB ObjectId format)",
        example="60f7b1b9e4b0c8a4f8e6d1a2"
    )],
    current_user: UserResponse = Depends(get_current_user),
    controller: TestSuiteController = Depends(get_test_suite_controller)
) -> TestSuiteDetailResponse:
    """
    Get a test suite by ID.
    
    Retrieves complete information about a specific test suite including
    all test items and their configurations.
    """
    logger.debug(
        f"Get test suite endpoint called: {suite_id}",
        extra={
            "user_id": current_user.id,
            "suite_id": suite_id,
            "endpoint": "GET /suites/{suite_id}"
        }
    )
    
    return await controller.get_test_suite(suite_id, current_user.id)


@router.get(
    "/",
    response_model=TestSuiteListResponse,
    summary="List test suites with filtering and pagination",
    description="""
    Retrieve a paginated list of test suites with comprehensive filtering and sorting options.
    
    All test suites are scoped to the authenticated user. The response includes
    pagination metadata, applied filters, and summary statistics.
    
    **Filtering Options:**
    - status: Filter by suite status (draft, active, archived)
    - priority: Filter by priority level (high, medium, low)
    - tags: Filter by tags (AND operation - suite must have all specified tags)
    - title_search: Search in suite titles (case-insensitive)
    - created_after/created_before: Date range filtering
    - has_items: Filter suites with/without test items
    
    **Pagination:**
    - page: Page number (1-based, default: 1)
    - page_size: Items per page (1-100, default: 20)
    
    **Sorting:**
    - sort_by: Field to sort by (created_at, updated_at, title, priority, total_items)
    - sort_order: Sort direction (asc, desc, default: desc)
    
    **Performance Optimization:**
    - Core fields only by default (excludes test item details)
    - Efficient MongoDB compound indexes
    - Supports large collections with consistent performance
    
    **Examples:**
    - All suites: `/suites/`
    - Active high-priority: `/suites/?status=active&priority=high`
    - Tagged suites: `/suites/?tags=smoke,regression`
    - Search: `/suites/?title_search=authentication`
    - Recent suites: `/suites/?sort_by=updated_at&sort_order=desc&page_size=10`
    """,
    responses={
        200: {
            "description": "Test suites retrieved successfully",
            "model": TestSuiteListResponse
        }
    }
)
async def list_test_suites(
    # Filtering parameters
    status: Annotated[Optional[TestSuiteStatus], Query(
        description="Filter by suite status"
    )] = None,
    priority: Annotated[Optional[TestSuitePriority], Query(
        description="Filter by priority level"
    )] = None,
    tags: Annotated[Optional[str], Query(
        description="Filter by tags (comma-separated, AND operation)",
        example="smoke,critical"
    )] = None,
    title_search: Annotated[Optional[str], Query(
        description="Search in suite titles (case-insensitive)",
        example="authentication"
    )] = None,
    has_items: Annotated[Optional[bool], Query(
        description="Filter suites with/without test items"
    )] = None,
    
    # Pagination parameters
    page: Annotated[int, Query(
        description="Page number (1-based)",
        ge=1,
        example=1
    )] = 1,
    page_size: Annotated[int, Query(
        description="Items per page",
        ge=1,
        le=100,
        example=20
    )] = 20,
    
    # Sorting parameters
    sort_by: Annotated[str, Query(
        description="Field to sort by",
        example="updated_at"
    )] = "updated_at",
    sort_order: Annotated[str, Query(
        description="Sort order (asc, desc)",
        example="desc"
    )] = "desc",
    
    # Dependencies
    current_user: UserResponse = Depends(get_current_user),
    controller: TestSuiteController = Depends(get_test_suite_controller)
) -> TestSuiteListResponse:
    """
    List test suites with filtering and pagination.
    
    Returns a paginated list of the user's test suites with applied filters
    and sorting options.
    """
    logger.debug(
        "List test suites endpoint called",
        extra={
            "user_id": current_user.id,
            "filters": {
                "status": status,
                "priority": priority,
                "tags": tags,
                "title_search": title_search,
                "has_items": has_items
            },
            "pagination": {"page": page, "page_size": page_size},
            "sorting": {"sort_by": sort_by, "sort_order": sort_order},
            "endpoint": "GET /suites/"
        }
    )
    
    # Build filter request
    filter_request = FilterTestSuitesRequest(
        status=status,
        priority=priority,
        tags=tags.split(",") if tags else None,
        title_search=title_search,
        has_items=has_items,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order
    )
    
    return await controller.list_test_suites(filter_request, current_user.id)


@router.put(
    "/{suite_id}",
    response_model=TestSuiteUpdateResponse,
    summary="Update test suite metadata",
    description="""
    Update test suite metadata including title, description, tags, priority, and status.
    
    This endpoint allows updating suite-level information without affecting the
    test item configurations. For test item management, use the dedicated
    bulk operation endpoints.
    
    **Updatable Fields:**
    - title: Suite title (must remain unique per user)
    - description: Suite description
    - tags: Suite tags (replaces existing tags)
    - priority: Priority level (high, medium, low)
    - status: Suite status (draft, active, archived)
    
    **Business Rules:**
    - Title uniqueness is enforced per user
    - Status changes to 'archived' implement soft deletion
    - All updates are atomic operations
    - Update timestamp is automatically maintained
    
    **Access Control:**
    - Only the suite owner can update the suite
    - Soft-deleted suites cannot be updated
    
    **Performance:**
    - Optimized MongoDB updates with selective field changes
    - Concurrent update protection with optimistic locking
    """,
    responses={
        200: {
            "description": "Test suite updated successfully",
            "model": TestSuiteUpdateResponse
        },
        400: {
            "description": "Validation error in request data",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": None,
                        "message": "Validation error: Title cannot be empty",
                        "timestamp": "2024-01-15T10:30:00Z"
                    }
                }
            }
        },
        404: {
            "description": "Test suite not found or access denied",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": None,
                        "message": "Test suite not found",
                        "timestamp": "2024-01-15T10:30:00Z"
                    }
                }
            }
        },
        409: {
            "description": "Title conflict or concurrent modification",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": None,
                        "message": "Suite with title 'Authentication Tests' already exists",
                        "timestamp": "2024-01-15T10:30:00Z"
                    }
                }
            }
        }
    }
)
async def update_test_suite(
    suite_id: Annotated[str, Path(
        description="Test suite ID (MongoDB ObjectId format)",
        example="60f7b1b9e4b0c8a4f8e6d1a2"
    )],
    request: UpdateTestSuiteRequest = Body(
        ...,
        description="Test suite update data",
        example={
            "title": "Enhanced Authentication Test Suite",
            "description": "Updated comprehensive authentication flow tests",
            "tags": ["authentication", "smoke", "regression"],
            "priority": "high",
            "status": "active"
        }
    ),
    current_user: UserResponse = Depends(get_current_user),
    controller: TestSuiteController = Depends(get_test_suite_controller)
) -> TestSuiteUpdateResponse:
    """
    Update test suite metadata.
    
    Updates the provided fields for the test suite. Only non-null fields
    in the request will be updated.
    """
    logger.info(
        f"Update test suite endpoint called: {suite_id}",
        extra={
            "user_id": current_user.id,
            "suite_id": suite_id,
            "updated_fields": [field for field, value in request.dict(exclude_unset=True).items() if value is not None],
            "endpoint": "PUT /suites/{suite_id}"
        }
    )
    
    return await controller.update_test_suite(suite_id, request, current_user.id)


@router.patch(
    "/{suite_id}/items/add",
    response_model=BulkOperationResponse,
    summary="Bulk add test items to suite",
    description="""
    Add multiple test items to a suite with comprehensive validation and partial success handling.
    
    This endpoint enables efficient addition of multiple test items with:
    - Batch validation of test item references
    - Duplicate detection within the suite
    - Partial success reporting (some items succeed, others fail)
    - Atomic operations for data consistency
    - Performance optimization for large batches
    
    **Validation Process:**
    1. Validate all test_item_id references exist and belong to user
    2. Check for duplicates within the suite
    3. Validate item configurations (order, tags, notes)
    4. Perform atomic addition of valid items
    
    **Bulk Operation Features:**
    - Maximum 100 items per operation (performance limit)
    - Partial success handling with detailed breakdown
    - Order management with automatic gaps handling
    - Custom tags and notes per suite item
    - Skip flags for conditional execution
    
    **Response Details:**
    - Success count and list of successfully added items
    - Invalid count and list of failed items with reasons
    - Duplicate count and list of already existing items
    - Overall operation success status
    
    **Performance:**
    - Single MongoDB query for validation
    - Atomic array updates for consistency
    - Sub-2-second response time for 100 items
    """,
    responses={
        200: {
            "description": "Bulk add operation completed (may include partial failures)",
            "model": BulkOperationResponse
        },
        400: {
            "description": "Request validation error or payload too large",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": None,
                        "message": "Bulk operation limited to 100 items. Received: 150",
                        "timestamp": "2024-01-15T10:30:00Z"
                    }
                }
            }
        },
        404: {
            "description": "Test suite not found or access denied",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": None,
                        "message": "Test suite not found",
                        "timestamp": "2024-01-15T10:30:00Z"
                    }
                }
            }
        }
    }
)
async def bulk_add_items(
    suite_id: Annotated[str, Path(
        description="Test suite ID (MongoDB ObjectId format)",
        example="60f7b1b9e4b0c8a4f8e6d1a2"
    )],
    request: BulkAddItemsRequest = Body(
        ...,
        description="Bulk add items request data",
        example={
            "items": [
                {
                    "test_item_id": "67890abcdef123456791",
                    "order": 10,
                    "skip": False,
                    "custom_tags": ["integration"],
                    "note": "API integration test"
                },
                {
                    "test_item_id": "67890abcdef123456792",
                    "order": 11,
                    "skip": True,
                    "custom_tags": ["flaky"],
                    "note": "Currently unstable - skip in CI"
                }
            ]
        }
    ),
    current_user: UserResponse = Depends(get_current_user),
    controller: TestSuiteController = Depends(get_test_suite_controller)
) -> BulkOperationResponse:
    """
    Bulk add test items to suite.
    
    Adds multiple test items to the suite with validation and partial
    success handling. Invalid items are reported but don't prevent
    valid items from being added.
    """
    logger.info(
        f"Bulk add items endpoint called: {suite_id}",
        extra={
            "user_id": current_user.id,
            "suite_id": suite_id,
            "items_count": len(request.items),
            "endpoint": "PATCH /suites/{suite_id}/items/add"
        }
    )
    
    return await controller.bulk_add_items(suite_id, request, current_user.id)


@router.patch(
    "/{suite_id}/items/remove",
    response_model=BulkOperationResponse,
    summary="Bulk remove test items from suite",
    description="""
    Remove multiple test items from a suite with partial success handling.
    
    This endpoint enables efficient removal of multiple test items with:
    - Validation of removal requests
    - Partial success reporting
    - Order rebalancing after removal
    - Atomic operations for data consistency
    
    **Removal Process:**
    1. Validate suite exists and user has access
    2. Identify items to remove (by test_item_id)
    3. Perform atomic removal operation
    4. Update suite statistics (total_items, active_items)
    
    **Features:**
    - Remove by test_item_id list
    - Automatic order rebalancing (optional)
    - Partial success handling for non-existent items
    - Statistics update for suite metadata
    
    **Response Details:**
    - Success count and list of removed items
    - Not found count for items that weren't in the suite
    - Overall operation success status
    """,
    responses={
        200: {
            "description": "Bulk remove operation completed",
            "model": BulkOperationResponse
        },
        404: {
            "description": "Test suite not found or access denied",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": None,
                        "message": "Test suite not found",
                        "timestamp": "2024-01-15T10:30:00Z"
                    }
                }
            }
        }
    }
)
async def bulk_remove_items(
    suite_id: Annotated[str, Path(
        description="Test suite ID (MongoDB ObjectId format)",
        example="60f7b1b9e4b0c8a4f8e6d1a2"
    )],
    request: BulkRemoveItemsRequest = Body(
        ...,
        description="Bulk remove items request data",
        example={
            "test_item_ids": [
                "67890abcdef123456791",
                "67890abcdef123456792"
            ],
            "rebalance_order": True
        }
    ),
    current_user: UserResponse = Depends(get_current_user),
    controller: TestSuiteController = Depends(get_test_suite_controller)
) -> BulkOperationResponse:
    """
    Bulk remove test items from suite.
    
    Removes multiple test items from the suite. Items not found in the
    suite are reported but don't cause the operation to fail.
    """
    logger.info(
        f"Bulk remove items endpoint called: {suite_id}",
        extra={
            "user_id": current_user.id,
            "suite_id": suite_id,
            "items_count": len(request.test_item_ids),
            "rebalance_order": request.rebalance_order,
            "endpoint": "PATCH /suites/{suite_id}/items/remove"
        }
    )
    
    return await controller.bulk_remove_items(suite_id, request, current_user.id)


@router.delete(
    "/{suite_id}",
    status_code=status.HTTP_200_OK,
    summary="Soft delete test suite",
    description="""
    Soft delete a test suite by marking it as archived.
    
    This operation implements soft deletion by changing the suite status to 'archived'
    rather than physically removing the data. This approach:
    
    **Benefits:**
    - Enables data recovery if deletion was accidental
    - Maintains audit trails and historical data
    - Prevents cascade deletion issues
    - Supports compliance requirements
    
    **Behavior:**
    - Suite status is changed to 'archived'
    - Suite becomes invisible in normal listing operations
    - All test item configurations are preserved
    - Update timestamp reflects the archival time
    
    **Access Control:**
    - Only the suite owner can delete the suite
    - Already archived suites return success (idempotent)
    
    **Recovery:**
    - Archived suites can be recovered by updating status back to 'active'
    - All data and configurations remain intact
    """,
    responses={
        200: {
            "description": "Test suite soft deleted successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "data": {
                            "suite_id": "60f7b1b9e4b0c8a4f8e6d1a2",
                            "previous_status": "active",
                            "new_status": "archived",
                            "archived_at": "2024-01-15T10:30:00Z"
                        },
                        "message": "Test suite archived successfully",
                        "timestamp": "2024-01-15T10:30:00Z"
                    }
                }
            }
        },
        404: {
            "description": "Test suite not found or access denied",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": None,
                        "message": "Test suite not found",
                        "timestamp": "2024-01-15T10:30:00Z"
                    }
                }
            }
        }
    }
)
async def delete_test_suite(
    suite_id: Annotated[str, Path(
        description="Test suite ID (MongoDB ObjectId format)",
        example="60f7b1b9e4b0c8a4f8e6d1a2"
    )],
    current_user: UserResponse = Depends(get_current_user),
    controller: TestSuiteController = Depends(get_test_suite_controller)
) -> dict:
    """
    Soft delete test suite.
    
    Archives the test suite by changing its status to 'archived'.
    The suite data is preserved for potential recovery.
    """
    logger.info(
        f"Delete test suite endpoint called: {suite_id}",
        extra={
            "user_id": current_user.id,
            "suite_id": suite_id,
            "endpoint": "DELETE /suites/{suite_id}"
        }
    )
    
    return await controller.delete_test_suite(suite_id, current_user.id)


@router.get(
    "/health",
    summary="Test suite service health check",
    description="""
    Check the health status of the test suite service and its dependencies.
    
    This endpoint provides comprehensive health information about:
    - Database connectivity and performance
    - Collection statistics and storage usage
    - Index status and optimization
    - Service dependencies (validation, bulk operations, observability)
    - Performance metrics and thresholds
    
    **Health Checks:**
    - MongoDB connection and response time
    - Test suite collection accessibility
    - Test item collection (for validation)
    - Index performance and usage
    - Service component availability
    
    **Performance Metrics:**
    - Average query response times
    - Recent operation success rates
    - Current active suites count
    - Storage utilization
    
    Useful for monitoring, debugging, and operational maintenance.
    """,
    responses={
        200: {
            "description": "Service health information",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "database": {
                            "connected": True,
                            "response_time_ms": 15.2,
                            "collection_exists": True
                        },
                        "collections": {
                            "test_suites": {
                                "document_count": 45,
                                "storage_size_mb": 12.5,
                                "avg_document_size_kb": 8.7
                            }
                        },
                        "indexes": {
                            "total_indexes": 6,
                            "index_usage": "optimal"
                        },
                        "services": {
                            "validation_service": "healthy",
                            "bulk_operation_service": "healthy",
                            "observability_service": "healthy"
                        },
                        "performance": {
                            "avg_query_time_ms": 25.3,
                            "success_rate_24h": 99.8
                        }
                    }
                }
            }
        }
    }
)
async def get_test_suite_service_health(
    controller: TestSuiteController = Depends(get_test_suite_controller)
) -> dict:
    """
    Get test suite service health status.
    
    Returns comprehensive health information about the test suite service
    and its dependencies.
    """
    logger.debug(
        "Test suite health check endpoint called",
        extra={"endpoint": "GET /suites/health"}
    )
    
    return await controller.get_service_health() 
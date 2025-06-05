"""
Test Item FastAPI Routes

API endpoints for test item management with full OpenAPI documentation,
authentication integration, dependency injection, and multi-test type support.
"""

from typing import Optional, Annotated
from fastapi import APIRouter, Depends, Query, Path, status, Request
from motor.motor_asyncio import AsyncIOMotorDatabase

from ...config.env import get_settings
from ...config.logging import get_logger
from ...auth.dependencies.auth_dependencies import get_current_user
from ...auth.schemas.auth_responses import UserResponse
from ...testtypes import TestType
from ..services.test_item_service import TestItemService
from ..controllers.test_item_controller import TestItemController, TestItemControllerFactory
from ..schemas.test_item_schemas import (
    CreateTestItemRequest,
    FilterTestItemsRequest,
    TestItemCreateResponse,
    TestItemDetailResponse,
    TestItemListResponse,
    TestItemStatus
)

logger = get_logger(__name__)

# Create router with prefix and tags
router = APIRouter(
    prefix="/test-items",
    tags=["Test Items"],
    responses={
        401: {"description": "Unauthorized - Invalid or missing authentication"},
        403: {"description": "Forbidden - Insufficient permissions"},
        500: {"description": "Internal Server Error"}
    }
)


# Dependency injection for services
async def get_test_item_service(request: Request) -> TestItemService:
    """
    Get TestItemService dependency from FastAPI app state.
    
    Args:
        request: FastAPI request object containing app state
        
    Returns:
        TestItemService instance with database connection
    """
    db = request.app.state.db
    return TestItemService(db)


async def get_test_item_controller(
    test_item_service: TestItemService = Depends(get_test_item_service)
) -> TestItemController:
    """Get TestItemController dependency."""
    return TestItemControllerFactory.create(test_item_service)


@router.post(
    "/create",
    response_model=TestItemCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new test item",
    description="""
    Create a new test item with test steps, selectors, metadata, and multi-test type support.
    
    The test item will be created with status 'draft' by default and can be updated later.
    All test items are scoped to the authenticated user.
    
    **Required fields:**
    - title: Descriptive name for the test
    - feature_id: Associated feature identifier
    - scenario_id: Associated scenario identifier
    - steps: Test steps with type and content
    - selectors: UI element selectors (primary required, fallback optional)
    
    **Optional fields:**
    - test_type: Test type classification (generic, bdd, manual) - defaults to 'generic'
    - type_data: Type-specific structured data (validated based on test_type)
    - tags: Labels for categorization
    - ai_confidence_score: AI confidence rating (0.0-1.0)
    - auto_healing_enabled: Enable automatic selector healing
    - dom_snapshot_id: Reference to DOM snapshot document
    
    **Multi-Test Type Support:**
    - Generic: AI/rule-based tests with natural language steps and selector hints
    - BDD: Cucumber-style tests with Gherkin syntax and BDD blocks
    - Manual: Human-authored tests with documentation and execution metadata
    
    **Examples:**
    See the request schema examples for detailed type-specific data structures.
    """,
    responses={
        201: {
            "description": "Test item created successfully",
            "model": TestItemCreateResponse
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
        }
    }
)
async def create_test_item(
    request: CreateTestItemRequest,
    current_user: UserResponse = Depends(get_current_user),
    controller: TestItemController = Depends(get_test_item_controller)
) -> TestItemCreateResponse:
    """
    Create a new test item.
    
    Creates a test item with the provided metadata, steps, and selectors.
    The item is automatically associated with the authenticated user.
    """
    logger.info(
        f"Create test item endpoint called: {request.title}",
        extra={
            "user_id": current_user.id,
            "feature_id": request.feature_id,
            "endpoint": "POST /test-items/create"
        }
    )
    
    return await controller.create_test_item(request, current_user.id)


@router.get(
    "/{item_id}",
    response_model=TestItemDetailResponse,
    summary="Get test item by ID",
    description="""
    Retrieve a specific test item by its ID.
    
    Only the owner of the test item can access it. The response includes
    core information by default, with optional detailed fields controlled
    by the include_fields parameter.
    
    **Field inclusion options:**
    - core: Always included (id, title, feature_id, test_type, status, dates)
    - steps: Test step information
    - selectors: UI element selectors
    - metadata: Tags, AI confidence, auto-healing settings
    - type_data: Type-specific structured data (based on test_type)
    - execution_stats: Execution history and statistics
    - computed: UI-optimized computed fields
    - all: Include all available fields
    
    **Examples:**
    - Default: `/test-items/{id}` (core + metadata)
    - Full details: `/test-items/{id}?include_fields=all`
    - Specific fields: `/test-items/{id}?include_fields=core,steps,selectors,type_data`
    """,
    responses={
        200: {
            "description": "Test item retrieved successfully",
            "model": TestItemDetailResponse
        },
        404: {
            "description": "Test item not found",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": None,
                        "message": "Test item not found",
                        "timestamp": "2024-01-15T10:30:00Z"
                    }
                }
            }
        }
    }
)
async def get_test_item(
    item_id: Annotated[str, Path(
        description="Test item ID (MongoDB ObjectId format)",
        example="60f7b1b9e4b0c8a4f8e6d1a2"
    )],
    include_fields: Annotated[Optional[str], Query(
        description="Comma-separated list of fields to include (core,steps,selectors,metadata,execution_stats,computed,all)",
        example="core,steps,metadata"
    )] = None,
    current_user: UserResponse = Depends(get_current_user),
    controller: TestItemController = Depends(get_test_item_controller)
) -> TestItemDetailResponse:
    """
    Get a test item by ID.
    
    Retrieves detailed information about a specific test item.
    Field inclusion can be controlled for performance optimization.
    """
    logger.debug(
        f"Get test item endpoint called: {item_id}",
        extra={
            "user_id": current_user.id,
            "test_item_id": item_id,
            "include_fields": include_fields,
            "endpoint": "GET /test-items/{item_id}"
        }
    )
    
    return await controller.get_test_item(item_id, current_user.id, include_fields)


@router.get(
    "/",
    response_model=TestItemListResponse,
    summary="List test items with filtering and pagination",
    description="""
    Retrieve a paginated list of test items with optional filtering and sorting.
    
    All test items are scoped to the authenticated user. The response includes
    pagination metadata, applied filters, and summary statistics.
    
    **Filtering options:**
    - feature_id: Filter by feature identifier
    - scenario_id: Filter by scenario identifier
    - status: Filter by test item status (draft, active, archived)
    - test_type: Filter by test type (generic, bdd, manual)
    - tags: Filter by tags (AND operation - item must have all specified tags)
    - created_after/created_before: Date range filtering
    - search_query: Full-text search in title and steps
    
    **Pagination:**
    - page: Page number (1-based, default: 1)
    - page_size: Items per page (1-100, default: 20)
    
    **Sorting:**
    - sort_by: Field to sort by (created_at, updated_at, title, feature_id, scenario_id, test_type)
    - sort_order: Sort direction (asc, desc, default: desc)
    
    **Field inclusion:**
    - include_fields: Control response payload size (same options as single item endpoint)
    
    **Examples:**
    - All items: `/test-items/`
    - Feature filter: `/test-items/?feature_id=authentication`
    - Active items: `/test-items/?status=active`
    - BDD tests: `/test-items/?test_type=bdd`
    - Search: `/test-items/?search_query=login`
    - Pagination: `/test-items/?page=2&page_size=10`
    - Combined: `/test-items/?feature_id=auth&test_type=bdd&status=active&page=1&page_size=20&include_fields=core,metadata,type_data`
    """,
    responses={
        200: {
            "description": "Test items retrieved successfully",
            "model": TestItemListResponse
        }
    }
)
async def list_test_items(
    # Filtering parameters
    feature_id: Annotated[Optional[str], Query(
        description="Filter by feature ID",
        example="authentication"
    )] = None,
    scenario_id: Annotated[Optional[str], Query(
        description="Filter by scenario ID", 
        example="user_login"
    )] = None,
    status: Annotated[Optional[TestItemStatus], Query(
        description="Filter by test item status"
    )] = None,
    test_type: Annotated[Optional[TestType], Query(
        description="Filter by test type (generic, bdd, manual)",
        example="bdd"
    )] = None,
    tags: Annotated[Optional[str], Query(
        description="Filter by tags (comma-separated, AND operation)",
        example="smoke,critical"
    )] = None,
    search_query: Annotated[Optional[str], Query(
        description="Search in title and steps content",
        example="login"
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
        example="created_at"
    )] = "created_at",
    sort_order: Annotated[str, Query(
        description="Sort order",
        example="desc"
    )] = "desc",
    
    # Field inclusion
    include_fields: Annotated[Optional[str], Query(
        description="Comma-separated list of fields to include",
        example="core,metadata"
    )] = None,
    
    # Dependencies
    current_user: UserResponse = Depends(get_current_user),
    controller: TestItemController = Depends(get_test_item_controller)
) -> TestItemListResponse:
    """
    List test items with filtering and pagination.
    
    Provides comprehensive filtering, sorting, and pagination capabilities
    for retrieving test items efficiently.
    """
    logger.debug(
        f"List test items endpoint called for user: {current_user.id}",
        extra={
            "user_id": current_user.id,
            "page": page,
            "page_size": page_size,
            "feature_id": feature_id,
            "status": status,
            "endpoint": "GET /test-items/"
        }
    )
    
    # Parse tags parameter
    parsed_tags = None
    if tags:
        parsed_tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
    
    # Create filter request
    filters = FilterTestItemsRequest(
        feature_id=feature_id,
        scenario_id=scenario_id,
        status=status,
        tags=parsed_tags,
        search_query=search_query,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
        include_fields=include_fields
    )
    
    return await controller.list_test_items(current_user.id, filters)


@router.get(
    "/health",
    summary="Test item service health check",
    description="""
    Check the health status of the test item service.
    
    This endpoint provides information about:
    - Database connectivity
    - Collection statistics
    - Index status
    - Service availability
    
    Useful for monitoring and debugging purposes.
    """,
    responses={
        200: {
            "description": "Service health information",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "collection_exists": True,
                        "document_count": 150,
                        "storage_size": 2048576,
                        "indexes": 5
                    }
                }
            }
        }
    }
)
async def get_test_item_service_health(
    controller: TestItemController = Depends(get_test_item_controller)
) -> dict:
    """
    Get test item service health status.
    
    Returns health information about the test item service and database.
    This endpoint does not require authentication for monitoring purposes.
    """
    logger.debug("Test item service health check endpoint called")
    
    return await controller.get_health_status()


# Export router for main app integration
__all__ = ["router"] 
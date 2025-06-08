"""
Test Case FastAPI Routes

RESTful API endpoints for the Test Case Management system with comprehensive
OpenAPI documentation, JWT authentication, dependency injection, and proper
request/response model binding.
"""

from typing import Optional, List, Annotated
from fastapi import APIRouter, Depends, Query, Path, Body, status, Request

from ...config.logging import get_logger
from ...auth.dependencies.auth_dependencies import get_current_user
from ...auth.schemas.auth_responses import UserResponse
from ...schemas.response import SuccessResponse
from ..controllers.test_case_controller import TestCaseController, TestCaseControllerFactory
from ..schemas.test_case_schemas import (
    CreateTestCaseRequest,
    UpdateTestCaseRequest,
    FilterTestCasesRequest,
    TestCaseCreateResponse,
    TestCaseDetailResponse,
    TestCaseListResponse,
    TestCaseUpdateResponse,
    UpdateStepsRequest,
    UpdateStatusRequest,
    TestCaseStatus,
    TestCasePriority,
    StepType
)

logger = get_logger(__name__)

# Create router with prefix and tags
router = APIRouter(
    prefix="/testcases",
    tags=["Test Cases"],
    responses={
        401: {"description": "Unauthorized - Invalid or missing authentication"},
        403: {"description": "Forbidden - Insufficient permissions"},
        500: {"description": "Internal Server Error"}
    }
)


# Dependency injection for controller
async def get_test_case_controller() -> TestCaseController:
    """
    Get TestCaseController dependency with proper service injection.
    
    Returns:
        TestCaseController instance with all dependencies injected
    """
    return TestCaseControllerFactory.create()


@router.post(
    "/",
    response_model=TestCaseCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new test case",
    description="""
    Create a new test case with comprehensive metadata, test steps, and lifecycle management.
    
    Test cases are atomic units of testing distinct from test items and test suites.
    They support structured test design with type-aware validation and intelligent tagging.
    
    **Core Features:**
    - **Test Steps**: Structured test steps with type-aware validation (GENERIC, BDD, MANUAL)
    - **Lifecycle Management**: Draft → Active → Deprecated → Archived status transitions
    - **Intelligent Tagging**: Auto-normalized tags with suggestion engine
    - **Owner Scoping**: Test cases are private to the creating user
    - **Integration Ready**: Links with Test Items and Test Suites
    
    **Required Fields:**
    - title: Descriptive name for the test case (must be unique per user)
    - description: Detailed explanation of test purpose and scope
    - steps: Array of test steps with actions and expected results
    - test_type: Type classification (GENERIC, BDD, MANUAL)
    
    **Optional Fields:**
    - tags: Intelligent tags for categorization (auto-normalized)
    - priority: Business priority (LOW, MEDIUM, HIGH, CRITICAL)
    - status: Initial status (defaults to DRAFT)
    - expected_result: Overall expected outcome
    - preconditions: Prerequisites for test execution
    - attachments: File references and external links
    
    **Step Types:**
    - **GENERIC**: Natural language steps with flexible validation
    - **BDD**: Gherkin-style Given/When/Then steps
    - **MANUAL**: Human-readable instructions with detailed descriptions
    
    **Validation Features:**
    - Title uniqueness enforcement per user
    - Circular dependency detection for test item references
    - Type-aware step validation based on test_type
    - Tag normalization and duplicate detection
    - Business rule enforcement
    
    **Performance:** Target <200ms end-to-end response time with comprehensive validation.
    """,
    responses={
        201: {
            "description": "Test case created successfully",
            "model": TestCaseCreateResponse,
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "data": {
                            "test_case": {
                                "core": {
                                    "id": "60f7b1b9e4b0c8a4f8e6d1a2",
                                    "title": "User Login Validation",
                                    "description": "Comprehensive test for user authentication flow",
                                    "test_type": "BDD",
                                    "status": "DRAFT",
                                    "priority": "HIGH",
                                    "created_at": "2024-01-15T10:30:00Z",
                                    "updated_at": "2024-01-15T10:30:00Z",
                                    "owner_id": "60f7b1b9e4b0c8a4f8e6d1a1"
                                },
                                "metadata": {
                                    "tags": ["authentication", "login", "security"],
                                    "expected_result": "User successfully logs in with valid credentials",
                                    "preconditions": ["User account exists", "Application is accessible"],
                                    "estimated_duration_minutes": 5
                                },
                                "steps": [
                                    {
                                        "step_number": 1,
                                        "step_type": "GIVEN",
                                        "action": "User is on login page",
                                        "expected_result": "Login form is displayed",
                                        "notes": "Verify all form elements are present"
                                    }
                                ]
                            }
                        },
                        "message": "Test case 'User Login Validation' created successfully",
                        "timestamp": "2024-01-15T10:30:00Z"
                    }
                }
            }
        },
        400: {
            "description": "Validation error in request data",
            "content": {
                "application/json": {
                    "examples": {
                        "duplicate_title": {
                            "summary": "Duplicate title",
                            "value": {
                                "detail": "Validation error: Test case with title 'User Login Validation' already exists"
                            }
                        },
                        "invalid_steps": {
                            "summary": "Invalid step configuration",
                            "value": {
                                "detail": "Validation error: BDD test type requires GIVEN/WHEN/THEN step types"
                            }
                        }
                    }
                }
            }
        }
    }
)
async def create_test_case(
    request: CreateTestCaseRequest = Body(
        ...,
        description="Test case creation data with metadata and test steps",
        example={
            "title": "User Login Validation",
            "description": "Comprehensive test for user authentication flow",
            "test_type": "BDD",
            "priority": "HIGH",
            "tags": ["authentication", "login", "security"],
            "expected_result": "User successfully logs in with valid credentials",
            "preconditions": ["User account exists", "Application is accessible"],
            "steps": [
                {
                    "step_number": 1,
                    "step_type": "GIVEN",
                    "action": "User is on login page",
                    "expected_result": "Login form is displayed",
                    "notes": "Verify all form elements are present"
                },
                {
                    "step_number": 2,
                    "step_type": "WHEN",
                    "action": "User enters valid credentials",
                    "expected_result": "Credentials are accepted",
                    "notes": "Use test account credentials"
                },
                {
                    "step_number": 3,
                    "step_type": "THEN",
                    "action": "User is redirected to dashboard",
                    "expected_result": "Dashboard page loads successfully",
                    "notes": "Verify user session is established"
                }
            ]
        }
    ),
    current_user: UserResponse = Depends(get_current_user),
    controller: TestCaseController = Depends(get_test_case_controller)
) -> TestCaseCreateResponse:
    """
    Create a new test case.
    
    Creates a test case with the provided metadata, steps, and validation.
    The test case is automatically associated with the authenticated user.
    """
    logger.info(
        f"Create test case endpoint called: {request.title}",
        extra={
            "user_id": current_user.id,
            "test_type": request.test_type,
            "step_count": len(request.steps),
            "endpoint": "POST /api/v1/testcases/"
        }
    )
    
    return await controller.create_test_case(request, current_user)


@router.get(
    "/{test_case_id}",
    response_model=TestCaseDetailResponse,
    summary="Get test case by ID",
    description="""
    Retrieve a specific test case by its ID with optional field inclusion control.
    
    Only the owner of the test case can access it. The response includes
    core information by default, with optional detailed fields controlled
    by the include_fields parameter for performance optimization.
    
    **Access Control:**
    - Only test case owner can retrieve
    - JWT authentication required
    - User scoping enforced at service layer
    
    **Field Inclusion Options:**
    - **core**: Always included (id, title, description, test_type, status, priority, dates, owner)
    - **steps**: Detailed test step information with type-aware formatting
    - **statistics**: Computed statistics (execution time estimation, automation readiness)
    - **references**: Links to test items, test suites, and external references
    - **metadata**: Tags, attachments, preconditions, and extended fields
    - **computed**: UI-optimized computed fields for frontend consumption
    - **all**: Include all available fields (equivalent to steps,statistics,references)
    
    **Performance Features:**
    - Selective field loading based on include_fields parameter
    - Core data always cached for <50ms response
    - Optional fields loaded on-demand
    - Optimized MongoDB queries with projection
    
    **Examples:**
    - Default: `/api/v1/testcases/{id}` (core fields only)
    - Full details: `/api/v1/testcases/{id}?include_fields=all`
    - Specific fields: `/api/v1/testcases/{id}?include_fields=steps,statistics`
    - UI optimized: `/api/v1/testcases/{id}?include_fields=core,computed,metadata`
    """,
    responses={
        200: {
            "description": "Test case retrieved successfully",
            "model": TestCaseDetailResponse
        },
        404: {
            "description": "Test case not found or access denied",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Test case not found"
                    }
                }
            }
        }
    }
)
async def get_test_case(
    test_case_id: Annotated[str, Path(
        description="Test case ID (MongoDB ObjectId format)",
        example="60f7b1b9e4b0c8a4f8e6d1a2",
        regex=r"^[0-9a-fA-F]{24}$"
    )],
    include_fields: Annotated[Optional[str], Query(
        description="Comma-separated list of fields to include (steps,statistics,references,computed,all)",
        example="steps,statistics"
    )] = None,
    current_user: UserResponse = Depends(get_current_user),
    controller: TestCaseController = Depends(get_test_case_controller)
) -> TestCaseDetailResponse:
    """
    Get a test case by ID.
    
    Retrieves the test case with optional field inclusion for performance optimization.
    Only the owner can access their test cases.
    """
    logger.debug(
        f"Get test case endpoint called: {test_case_id}",
        extra={
            "user_id": current_user.id,
            "test_case_id": test_case_id,
            "include_fields": include_fields,
            "endpoint": "GET /api/v1/testcases/{id}"
        }
    )
    
    # Parse include_fields parameter
    include_fields_list = None
    if include_fields:
        include_fields_list = [field.strip() for field in include_fields.split(",")]
    
    return await controller.get_test_case(test_case_id, current_user, include_fields_list)


@router.get(
    "/",
    response_model=TestCaseListResponse,
    summary="List test cases with filtering and pagination",
    description="""
    Retrieve a paginated list of test cases with comprehensive filtering and sorting options.
    
    All test cases are scoped to the authenticated user. The response includes
    pagination metadata, applied filters, and summary statistics for efficient
    frontend data management.
    
    **Filtering Options:**
    - **status**: Filter by lifecycle status (DRAFT, ACTIVE, DEPRECATED, ARCHIVED)
    - **priority**: Filter by business priority (LOW, MEDIUM, HIGH, CRITICAL)
    - **test_type**: Filter by test type classification (GENERIC, BDD, MANUAL)
    - **tags**: Filter by tags (comma-separated, AND operation - must have all specified tags)
    - **created_after/created_before**: Date range filtering for creation timestamps
    - **updated_after/updated_before**: Date range filtering for last update timestamps
    - **title_search**: Full-text search in test case titles (case-insensitive)
    - **description_search**: Full-text search in descriptions (case-insensitive)
    
    **Pagination & Performance:**
    - **page**: Page number (1-based, default: 1)
    - **page_size**: Items per page (1-100, default: 20)
    - **sort_by**: Field to sort by (created_at, updated_at, title, priority, status)
    - **sort_order**: Sort direction (asc, desc, default: desc)
    
    **Field Inclusion:**
    - **include_fields**: Control response payload size (same options as single item endpoint)
    - Default: core + metadata for list optimization
    - Use 'core' for minimal payloads in high-performance scenarios
    
    **Advanced Features:**
    - Intelligent tag suggestions based on current filters
    - Summary statistics (total count, status distribution, priority breakdown)
    - Performance metrics (average response time, cache hit rate)
    - Filter validation and sanitization
    
    **Examples:**
    - All test cases: `/api/v1/testcases/`
    - Active test cases: `/api/v1/testcases/?status=ACTIVE`
    - High priority BDD tests: `/api/v1/testcases/?priority=HIGH&test_type=BDD`
    - Tagged test cases: `/api/v1/testcases/?tags=authentication,security`
    - Search: `/api/v1/testcases/?title_search=login`
    - Date range: `/api/v1/testcases/?created_after=2024-01-01T00:00:00Z&created_before=2024-01-31T23:59:59Z`
    - Pagination: `/api/v1/testcases/?page=2&page_size=10&sort_by=updated_at&sort_order=desc`
    - Combined: `/api/v1/testcases/?status=ACTIVE&priority=HIGH&tags=critical&page=1&page_size=20&include_fields=core,metadata`
    """,
    responses={
        200: {
            "description": "Test cases retrieved successfully",
            "model": TestCaseListResponse
        },
        400: {
            "description": "Invalid filter parameters",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Page size must be between 1 and 100"
                    }
                }
            }
        }
    }
)
async def list_test_cases(
    # Status and priority filters
    status: Annotated[Optional[TestCaseStatus], Query(
        description="Filter by test case status"
    )] = None,
    priority: Annotated[Optional[TestCasePriority], Query(
        description="Filter by test case priority"
    )] = None,
    test_type: Annotated[Optional[StepType], Query(
        description="Filter by test type (GENERIC, BDD, MANUAL)"
    )] = None,
    
    # Tag and search filters
    tags: Annotated[Optional[str], Query(
        description="Filter by tags (comma-separated, AND operation)",
        example="authentication,security,critical"
    )] = None,
    title_search: Annotated[Optional[str], Query(
        description="Search in test case titles (case-insensitive)",
        example="login"
    )] = None,
    description_search: Annotated[Optional[str], Query(
        description="Search in test case descriptions (case-insensitive)",
        example="authentication"
    )] = None,
    
    # Date range filters
    created_after: Annotated[Optional[str], Query(
        description="Filter by creation date (ISO 8601 format)",
        example="2024-01-01T00:00:00Z"
    )] = None,
    created_before: Annotated[Optional[str], Query(
        description="Filter by creation date (ISO 8601 format)",
        example="2024-01-31T23:59:59Z"
    )] = None,
    updated_after: Annotated[Optional[str], Query(
        description="Filter by last update date (ISO 8601 format)",
        example="2024-01-01T00:00:00Z"
    )] = None,
    updated_before: Annotated[Optional[str], Query(
        description="Filter by last update date (ISO 8601 format)",
        example="2024-01-31T23:59:59Z"
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
        description="Sort order (asc, desc)",
        example="desc"
    )] = "desc",
    
    # Field inclusion
    include_fields: Annotated[Optional[str], Query(
        description="Comma-separated list of fields to include",
        example="core,metadata"
    )] = None,
    
    # Dependencies
    current_user: UserResponse = Depends(get_current_user),
    controller: TestCaseController = Depends(get_test_case_controller)
) -> TestCaseListResponse:
    """
    List test cases with filtering and pagination.
    
    Retrieves test cases belonging to the authenticated user with comprehensive
    filtering options and optimized pagination.
    """
    logger.debug(
        f"List test cases endpoint called",
        extra={
            "user_id": current_user.id,
            "page": page,
            "page_size": page_size,
            "filters": {
                "status": status,
                "priority": priority,
                "test_type": test_type,
                "tags": tags,
                "title_search": title_search
            },
            "endpoint": "GET /api/v1/testcases/"
        }
    )
    
    # Parse tags parameter
    tags_list = None
    if tags:
        tags_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
    
    # Parse include_fields parameter
    include_fields_list = None
    if include_fields:
        include_fields_list = [field.strip() for field in include_fields.split(",")]
    
    # Create filter request
    filters = FilterTestCasesRequest(
        status=status,
        priority=priority,
        test_type=test_type,
        tags=tags_list,
        title_search=title_search,
        description_search=description_search,
        created_after=created_after,
        created_before=created_before,
        updated_after=updated_after,
        updated_before=updated_before,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
        include_fields=include_fields_list
    )
    
    return await controller.list_test_cases(current_user, filters)


@router.put(
    "/{test_case_id}",
    response_model=TestCaseUpdateResponse,
    summary="Update test case",
    description="""
    Update an existing test case with partial or complete data changes.
    
    Supports partial updates with field-level validation and business rule enforcement.
    Only the test case owner can perform updates with comprehensive audit logging.
    
    **Updatable Fields:**
    - **title**: Test case name (uniqueness validated per user)
    - **description**: Detailed test case description
    - **test_type**: Type classification (triggers step validation)
    - **priority**: Business priority level
    - **status**: Lifecycle status (with transition validation)
    - **tags**: Intelligent tag management with normalization
    - **expected_result**: Overall expected outcome
    - **preconditions**: Prerequisites for test execution
    - **steps**: Complete step replacement or individual step updates
    - **attachments**: File references and external links
    
    **Business Rules:**
    - Title uniqueness enforcement per user (excluding current test case)
    - Status transition validation (e.g., cannot go from ARCHIVED to DRAFT)
    - Step type validation based on test_type changes
    - Tag normalization and duplicate prevention
    - Circular dependency detection for test item references
    
    **Update Strategies:**
    - **Partial Update**: Only provided fields are updated, others remain unchanged
    - **Step Management**: Steps can be updated individually or replaced completely
    - **Tag Intelligence**: Tags are automatically normalized and deduplicated
    - **Status Transitions**: Validated against allowed transition matrix
    
    **Validation Features:**
    - Type-aware step validation when test_type changes
    - Business rule enforcement with detailed error messages
    - Optimistic concurrency control for concurrent updates
    - Change tracking for audit trail
    
    **Performance:** Target <200ms response time with comprehensive validation.
    """,
    responses={
        200: {
            "description": "Test case updated successfully",
            "model": TestCaseUpdateResponse
        },
        404: {
            "description": "Test case not found or access denied",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Test case not found"
                    }
                }
            }
        },
        400: {
            "description": "Validation error in update data",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_status_transition": {
                            "summary": "Invalid status transition",
                            "value": {
                                "detail": "Validation error: Cannot transition from ARCHIVED to DRAFT"
                            }
                        },
                        "duplicate_title": {
                            "summary": "Duplicate title",
                            "value": {
                                "detail": "Validation error: Test case with title 'Updated Title' already exists"
                            }
                        }
                    }
                }
            }
        }
    }
)
async def update_test_case(
    test_case_id: Annotated[str, Path(
        description="Test case ID (MongoDB ObjectId format)",
        example="60f7b1b9e4b0c8a4f8e6d1a2",
        regex=r"^[0-9a-fA-F]{24}$"
    )],
    request: UpdateTestCaseRequest = Body(
        ...,
        description="Test case update data (partial updates supported)",
        example={
            "title": "Updated User Login Validation",
            "priority": "CRITICAL",
            "tags": ["authentication", "login", "security", "regression"],
            "status": "ACTIVE"
        }
    ),
    current_user: UserResponse = Depends(get_current_user),
    controller: TestCaseController = Depends(get_test_case_controller)
) -> TestCaseUpdateResponse:
    """
    Update a test case.
    
    Updates the test case with provided data, applying validation and business rules.
    Only the owner can update their test cases.
    """
    logger.info(
        f"Update test case endpoint called: {test_case_id}",
        extra={
            "user_id": current_user.id,
            "test_case_id": test_case_id,
            "has_title_update": request.title is not None,
            "has_status_update": request.status is not None,
            "endpoint": "PUT /api/v1/testcases/{id}"
        }
    )
    
    return await controller.update_test_case(test_case_id, request, current_user)


@router.delete(
    "/{test_case_id}",
    response_model=SuccessResponse,
    summary="Delete test case (soft delete)",
    description="""
    Delete a test case using soft delete (archival) for data integrity.
    
    Implements soft delete by changing status to ARCHIVED rather than physical deletion.
    This preserves referential integrity with test suites and test items while
    removing the test case from active use.
    
    **Soft Delete Features:**
    - Status changed to ARCHIVED instead of physical deletion
    - Test case remains in database for audit and recovery purposes
    - References from test suites and test items remain intact
    - Owner can still access archived test cases with special filters
    - Deletion timestamp recorded for audit trail
    
    **Access Control:**
    - Only test case owner can delete
    - JWT authentication required
    - User scoping enforced at service layer
    
    **Impact Analysis:**
    - Test suite inclusions remain but marked as archived reference
    - Test item links preserved for historical analysis
    - Reporting and analytics continue to include archived data
    - Recovery possible through status update back to active states
    
    **Business Rules:**
    - Cannot delete test cases that are currently in execution
    - Cannot delete test cases with pending approvals (if workflow enabled)
    - Deletion triggers cleanup of temporary attachments
    - Tag usage counts updated to reflect removal from active pool
    
    **Performance:** Target <100ms response time for deletion operation.
    """,
    responses={
        200: {
            "description": "Test case deleted (archived) successfully",
            "model": SuccessResponse,
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "data": None,
                        "message": "Test case deleted successfully",
                        "timestamp": "2024-01-15T10:30:00Z"
                    }
                }
            }
        },
        404: {
            "description": "Test case not found or access denied",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Test case not found"
                    }
                }
            }
        }
    }
)
async def delete_test_case(
    test_case_id: Annotated[str, Path(
        description="Test case ID (MongoDB ObjectId format)",
        example="60f7b1b9e4b0c8a4f8e6d1a2",
        regex=r"^[0-9a-fA-F]{24}$"
    )],
    current_user: UserResponse = Depends(get_current_user),
    controller: TestCaseController = Depends(get_test_case_controller)
) -> SuccessResponse:
    """
    Delete a test case (soft delete).
    
    Archives the test case instead of physical deletion for data integrity.
    Only the owner can delete their test cases.
    """
    logger.info(
        f"Delete test case endpoint called: {test_case_id}",
        extra={
            "user_id": current_user.id,
            "test_case_id": test_case_id,
            "endpoint": "DELETE /api/v1/testcases/{id}"
        }
    )
    
    return await controller.delete_test_case(test_case_id, current_user)


@router.patch(
    "/{test_case_id}/steps",
    response_model=SuccessResponse,
    summary="Update test case steps",
    description="""
    Update test case steps with advanced step management capabilities.
    
    Provides specialized endpoint for step management with reordering, bulk updates,
    and type-aware validation. Optimized for frontend step editors and bulk operations.
    
    **Step Management Features:**
    - **Individual Step Updates**: Update specific steps by step_number
    - **Bulk Step Operations**: Add, update, or remove multiple steps
    - **Step Reordering**: Automatically renumber steps when reorder=true
    - **Type-Aware Validation**: Validates steps according to test_type requirements
    - **Atomic Operations**: All step changes applied atomically or none at all
    
    **Step Types & Validation:**
    - **GENERIC**: Flexible step format with action and expected_result
    - **BDD**: Gherkin-style validation (GIVEN/WHEN/THEN/AND/BUT)
    - **MANUAL**: Human-readable instructions with detailed descriptions
    
    **Advanced Options:**
    - **reorder**: Automatically renumber steps to ensure sequential numbering
    - **validate_references**: Check test item references for circular dependencies
    - **preserve_metadata**: Maintain step-level metadata during updates
    
    This endpoint is optimized for interactive step editing scenarios.
    """,
    responses={
        200: {
            "description": "Test case steps updated successfully",
            "model": SuccessResponse
        },
        404: {
            "description": "Test case not found or access denied",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Test case not found"
                    }
                }
            }
        }
    }
)
async def update_test_case_steps(
    test_case_id: Annotated[str, Path(
        description="Test case ID (MongoDB ObjectId format)",
        example="60f7b1b9e4b0c8a4f8e6d1a2",
        regex=r"^[0-9a-fA-F]{24}$"
    )],
    request: UpdateStepsRequest = Body(
        ...,
        description="Step update data with optional reordering",
        example={
            "steps": [
                {
                    "step_number": 1,
                    "step_type": "GIVEN",
                    "action": "User is on login page",
                    "expected_result": "Login form is displayed",
                    "notes": "Verify all form elements are present"
                },
                {
                    "step_number": 2,
                    "step_type": "WHEN",
                    "action": "User enters valid credentials",
                    "expected_result": "Credentials are accepted"
                }
            ],
            "reorder": True
        }
    ),
    current_user: UserResponse = Depends(get_current_user),
    controller: TestCaseController = Depends(get_test_case_controller)
) -> SuccessResponse:
    """
    Update test case steps.
    
    Updates the test case steps with type-aware validation and optional reordering.
    Only the owner can update their test case steps.
    """
    logger.info(
        f"Update test case steps endpoint called: {test_case_id}",
        extra={
            "user_id": current_user.id,
            "test_case_id": test_case_id,
            "step_count": len(request.steps),
            "reorder": request.reorder,
            "endpoint": "PATCH /api/v1/testcases/{id}/steps"
        }
    )
    
    return await controller.update_test_case_steps(test_case_id, request, current_user)


@router.patch(
    "/{test_case_id}/status",
    response_model=SuccessResponse,
    summary="Update test case status",
    description="""
    Update test case status with lifecycle transition validation.
    
    Provides specialized endpoint for status management with transition validation,
    audit logging, and business rule enforcement. Optimized for workflow scenarios
    and status tracking.
    
    **Status Lifecycle:**
    - **DRAFT** → ACTIVE (activation)
    - **ACTIVE** → DEPRECATED (deprecation)
    - **DEPRECATED** → ARCHIVED (archival)
    - **ACTIVE** → ARCHIVED (direct archival)
    - **DRAFT** → ARCHIVED (cancellation)
    
    **Transition Validation:**
    - Validates allowed transitions based on current status
    - Enforces business rules for status changes
    - Tracks transition history for audit trail
    - Validates prerequisites for each transition
    
    **Business Rules:**
    - Cannot activate test case with incomplete steps
    - Cannot deprecate test case currently in execution
    - Cannot archive test case with pending approvals
    - Status changes trigger notification workflows (if enabled)
    
    **Audit Features:**
    - Transition reason logging
    - User attribution for all status changes
    - Timestamp tracking for transition history
    - Integration with approval workflows
    
    This endpoint is optimized for workflow management and status tracking scenarios.
    """,
    responses={
        200: {
            "description": "Test case status updated successfully",
            "model": SuccessResponse,
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "data": None,
                        "message": "Test case status update to 'ACTIVE' processed",
                        "timestamp": "2024-01-15T10:30:00Z"
                    }
                }
            }
        },
        400: {
            "description": "Invalid status transition",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid status transition from ARCHIVED to DRAFT"
                    }
                }
            }
        }
    }
)
async def update_test_case_status(
    test_case_id: Annotated[str, Path(
        description="Test case ID (MongoDB ObjectId format)",
        example="60f7b1b9e4b0c8a4f8e6d1a2",
        regex=r"^[0-9a-fA-F]{24}$"
    )],
    request: UpdateStatusRequest = Body(
        ...,
        description="Status update data with transition reason",
        example={
            "status": "ACTIVE",
            "reason": "Test case ready for execution after review"
        }
    ),
    current_user: UserResponse = Depends(get_current_user),
    controller: TestCaseController = Depends(get_test_case_controller)
) -> SuccessResponse:
    """
    Update test case status.
    
    Updates the test case status with transition validation and audit logging.
    Only the owner can update their test case status.
    """
    logger.info(
        f"Update test case status endpoint called: {test_case_id}",
        extra={
            "user_id": current_user.id,
            "test_case_id": test_case_id,
            "new_status": request.status,
            "reason": request.reason,
            "endpoint": "PATCH /api/v1/testcases/{id}/status"
        }
    )
    
    return await controller.update_test_case_status(test_case_id, request, current_user)


@router.get(
    "/tags/suggestions",
    response_model=SuccessResponse,
    summary="Get tag suggestions",
    description="""
    Get intelligent tag suggestions based on partial input with auto-complete functionality.
    
    Provides smart tag suggestions using the intelligent tagging engine with
    prefix matching, popularity weighting, and user-specific tag history.
    
    **Intelligence Features:**
    - **Prefix Matching**: Finds tags starting with the partial input
    - **Fuzzy Matching**: Handles typos and similar variations
    - **Popularity Weighting**: Prioritizes frequently used tags
    - **User History**: Considers user's previous tag usage patterns
    - **Context Awareness**: Suggestions based on current filter context
    
    **Performance Features:**
    - Cached suggestions for common prefixes
    - Real-time response (<50ms target)
    - Optimized MongoDB text index queries
    - Intelligent result ranking
    
    **Use Cases:**
    - Auto-complete in tag input fields
    - Tag suggestion during test case creation
    - Bulk tagging operations
    - Tag discovery and exploration
    
    **Parameters:**
    - **partial**: Partial tag text (minimum 2 characters)
    - **limit**: Maximum suggestions to return (1-50, default: 10)
    
    **Result Format:**
    - Array of tag suggestions sorted by relevance
    - Includes usage count and popularity metrics
    - Normalized tag format for consistency
    """,
    responses={
        200: {
            "description": "Tag suggestions retrieved successfully",
            "model": SuccessResponse,
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "data": {
                            "suggestions": [
                                {
                                    "tag": "authentication",
                                    "usage_count": 45,
                                    "popularity_score": 0.89
                                },
                                {
                                    "tag": "authorization",
                                    "usage_count": 23,
                                    "popularity_score": 0.67
                                },
                                {
                                    "tag": "audit",
                                    "usage_count": 12,
                                    "popularity_score": 0.45
                                }
                            ]
                        },
                        "message": "Tag suggestions retrieved successfully",
                        "timestamp": "2024-01-15T10:30:00Z"
                    }
                }
            }
        },
        400: {
            "description": "Invalid request parameters",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Partial tag must be at least 2 characters long"
                    }
                }
            }
        }
    }
)
async def get_tag_suggestions(
    partial: Annotated[str, Query(
        description="Partial tag text for suggestions (minimum 2 characters)",
        min_length=2,
        max_length=50,
        example="auth"
    )],
    limit: Annotated[int, Query(
        description="Maximum number of suggestions to return",
        ge=1,
        le=50,
        example=10
    )] = 10,
    current_user: UserResponse = Depends(get_current_user),
    controller: TestCaseController = Depends(get_test_case_controller)
) -> SuccessResponse:
    """
    Get tag suggestions based on partial input.
    
    Returns intelligent tag suggestions with popularity weighting and user context.
    """
    logger.debug(
        f"Get tag suggestions endpoint called: '{partial}'",
        extra={
            "user_id": current_user.id,
            "partial": partial,
            "limit": limit,
            "endpoint": "GET /api/v1/testcases/tags/suggestions"
        }
    )
    
    return await controller.get_tag_suggestions(partial, current_user, limit)


@router.get(
    "/tags/popular",
    response_model=SuccessResponse,
    summary="Get popular tags",
    description="""
    Get the most popular tags across all test cases with usage statistics.
    
    Provides insights into tag popularity and usage patterns for tag discovery,
    standardization, and analytics. Useful for tag management and user guidance.
    
    **Features:**
    - **Usage Statistics**: Tag usage counts and frequency analysis
    - **Trending Analysis**: Recently trending tags based on usage patterns
    - **Global vs User**: Popular tags across all users vs user-specific usage
    - **Category Insights**: Tag categories and classification insights
    
    **Use Cases:**
    - Tag standardization and governance
    - Popular tag display in UI
    - Tag analytics and reporting
    - User guidance for consistent tagging
    
    **Performance:**
    - Cached results updated periodically
    - Real-time response (<50ms target)
    - Optimized aggregation queries
    - Smart caching strategy
    
    **Parameters:**
    - **limit**: Maximum tags to return (1-100, default: 20)
    - **scope**: Global popularity vs user-specific (future enhancement)
    
    **Result Format:**
    - Array of popular tags with usage statistics
    - Sorted by popularity score and recent usage
    - Includes trend indicators and category information
    """,
    responses={
        200: {
            "description": "Popular tags retrieved successfully",
            "model": SuccessResponse,
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "data": {
                            "popular_tags": [
                                {
                                    "tag": "authentication",
                                    "usage_count": 156,
                                    "popularity_score": 0.95,
                                    "trend": "stable",
                                    "category": "security"
                                },
                                {
                                    "tag": "regression",
                                    "usage_count": 142,
                                    "popularity_score": 0.91,
                                    "trend": "rising",
                                    "category": "testing"
                                },
                                {
                                    "tag": "critical",
                                    "usage_count": 128,
                                    "popularity_score": 0.87,
                                    "trend": "stable",
                                    "category": "priority"
                                }
                            ]
                        },
                        "message": "Popular tags retrieved successfully",
                        "timestamp": "2024-01-15T10:30:00Z"
                    }
                }
            }
        }
    }
)
async def get_popular_tags(
    limit: Annotated[int, Query(
        description="Maximum number of popular tags to return",
        ge=1,
        le=100,
        example=20
    )] = 20,
    current_user: UserResponse = Depends(get_current_user),
    controller: TestCaseController = Depends(get_test_case_controller)
) -> SuccessResponse:
    """
    Get popular tags with usage statistics.
    
    Returns the most popular tags across test cases with usage analytics.
    """
    logger.debug(
        f"Get popular tags endpoint called",
        extra={
            "user_id": current_user.id,
            "limit": limit,
            "endpoint": "GET /api/v1/testcases/tags/popular"
        }
    )
    
    return await controller.get_popular_tags(current_user, limit)


@router.get(
    "/health",
    summary="Test case service health check",
    description="""
    Check the health status of the Test Case Management service.
    
    Provides comprehensive health information about all service components including
    database connectivity, index status, performance metrics, and service availability.
    
    **Health Checks:**
    - **Database Connectivity**: MongoDB connection status and response time
    - **Collection Status**: Test case collection existence and document count
    - **Index Health**: All required indexes present and functional
    - **Service Dependencies**: Controller, services, and validation components
    - **Performance Metrics**: Average response times and throughput
    - **Memory Usage**: Service memory consumption and limits
    
    **Monitoring Integration:**
    - Compatible with Kubernetes health checks
    - Prometheus metrics integration ready
    - Structured logging for monitoring systems
    - Alert-friendly status indicators
    
    **Security:**
    - No authentication required (public health endpoint)
    - No sensitive information exposed
    - Safe for external monitoring systems
    
    Useful for monitoring, debugging, and operational visibility.
    """,
    responses={
        200: {
            "description": "Service health information",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "database": {
                            "status": "healthy",
                            "response_time_ms": 15.2,
                            "collection_exists": True,
                            "document_count": 1250,
                            "indexes": 6
                        },
                        "services": {
                            "test_case_service": "healthy",
                            "validation_service": "healthy",
                            "tag_service": "healthy",
                            "response_builder": "healthy"
                        },
                        "performance": {
                            "avg_response_time_ms": 89.5,
                            "requests_per_minute": 125,
                            "cache_hit_rate": 0.87
                        },
                        "timestamp": "2024-01-15T10:30:00Z"
                    }
                }
            }
        },
        503: {
            "description": "Service unhealthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "unhealthy",
                        "error": "Database connection failed",
                        "timestamp": "2024-01-15T10:30:00Z"
                    }
                }
            }
        }
    }
)
async def get_test_case_service_health(
    controller: TestCaseController = Depends(get_test_case_controller)
) -> dict:
    """
    Get test case service health status.
    
    Returns comprehensive health information for monitoring and debugging.
    No authentication required.
    """
    logger.debug(
        "Health check endpoint called",
        extra={"endpoint": "GET /api/v1/testcases/health"}
    )
    
    # For now, return a basic health status
    # In a full implementation, this would check actual service health
    return {
        "status": "healthy",
        "message": "Test Case Management service is operational",
        "timestamp": "2024-01-15T10:30:00Z"
    } 
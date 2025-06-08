"""
Orchestration Routes Module

This module defines FastAPI routes for orchestration engine operations, providing
HTTP endpoints that expose the OrchestrationController functionality. Routes follow
RESTful conventions and IntelliBrowse API standards with comprehensive OpenAPI
documentation and JWT-based authentication.

Endpoints:
- POST /orchestration/job - Submit new orchestration job
- GET /orchestration/job/{job_id} - Get job status and details
- DELETE /orchestration/job/{job_id} - Cancel running job
- GET /orchestration/jobs - List jobs with filtering and pagination

Features:
- JWT authentication on all endpoints
- Comprehensive request/response validation
- OpenAPI documentation with proper tags
- Dependency injection for controller
- Structured error handling and logging
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Path, Query, status
from fastapi.responses import JSONResponse

from ..controllers.orchestration_controller import (
    OrchestrationController,
    OrchestrationControllerFactory
)
from ..schemas.orchestration_schemas import (
    CreateOrchestrationJobRequest,
    JobStatusResponse,
    JobListResponse,
    OrchestrationResponse
)
from ...auth.dependencies.auth_dependencies import get_current_user
from ...auth.schemas.auth_responses import UserResponse


logger = logging.getLogger(__name__)

# Create FastAPI router with orchestration prefix and tags
router = APIRouter(
    prefix="/orchestration",
    tags=["Orchestration"],
    dependencies=[Depends(get_current_user)]
)


@router.post(
    "/job",
    response_model=OrchestrationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit Orchestration Job",
    description="""
    Submit a new orchestration job for asynchronous execution.
    
    This endpoint accepts job specifications including target entities (test cases, 
    test suites), execution parameters, and retry configurations. The job is 
    validated and queued for execution by the DAG execution engine.
    
    **Authentication Required**: JWT token with valid user credentials.
    
    **Request Body**: Complete job specification with validation
    **Response**: Job metadata including assigned job ID and initial status
    
    **HTTP Status Codes**:
    - 202: Job accepted and queued for execution
    - 400: Invalid job specification or validation errors
    - 403: Insufficient permissions or inactive user account
    - 500: Internal server error during job submission
    """,
    responses={
        202: {
            "description": "Job submitted successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Orchestration job 'Test Suite Execution' submitted successfully",
                        "data": {
                            "job_id": "60f7b1b9e4b0c8a4f8e6d1a2",
                            "status": "pending",
                            "submitted_at": "2024-01-25T10:30:00Z",
                            "priority": 5,
                            "estimated_duration_ms": 300000
                        },
                        "request_id": "req_123456789"
                    }
                }
            }
        },
        400: {
            "description": "Invalid job specification",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Job validation failed: test_execution jobs require at least one test case ID"
                    }
                }
            }
        },
        403: {
            "description": "Insufficient permissions",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Insufficient permissions: User account is not active"
                    }
                }
            }
        }
    }
)
async def submit_orchestration_job(
    job_request: CreateOrchestrationJobRequest,
    current_user: UserResponse = Depends(get_current_user),
    controller: OrchestrationController = Depends(OrchestrationControllerFactory.create_controller)
) -> OrchestrationResponse:
    """
    Submit a new orchestration job for execution.
    
    Validates the job request, checks user permissions, and submits the job
    to the orchestration engine for asynchronous processing.
    
    Args:
        job_request: Complete job specification with validation
        current_user: Authenticated user from JWT token
        controller: Injected orchestration controller instance
        
    Returns:
        OrchestrationResponse: Job submission confirmation with metadata
    """
    logger.info(
        "Processing job submission request",
        extra={
            "user_id": current_user.id,
            "job_name": job_request.job_name,
            "job_type": job_request.job_type,
            "endpoint": "POST /orchestration/job"
        }
    )
    
    return await controller.submit_orchestration_job(
        request=job_request,
        current_user=current_user
    )


@router.get(
    "/job/{job_id}",
    response_model=JobStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Job Status",
    description="""
    Retrieve comprehensive status information for a specific orchestration job.
    
    Returns detailed job information including current execution status, progress
    percentage, currently executing node, retry count, execution results, and
    complete execution timeline.
    
    **Authentication Required**: JWT token with valid user credentials.
    **Authorization**: Users can only access jobs they own.
    
    **Path Parameters**: 
    - job_id: MongoDB ObjectId of the orchestration job
    
    **Response**: Complete job status with execution details
    
    **HTTP Status Codes**:
    - 200: Job status retrieved successfully
    - 400: Invalid job ID format
    - 403: Access denied (user doesn't own the job)
    - 404: Job not found or inaccessible
    - 500: Internal server error during status retrieval
    """,
    responses={
        200: {
            "description": "Job status retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "job_id": "60f7b1b9e4b0c8a4f8e6d1a2",
                        "job_name": "Test Suite Execution",
                        "job_type": "test_suite_execution",
                        "status": "running",
                        "priority": 5,
                        "triggered_at": "2024-01-25T10:30:00Z",
                        "started_at": "2024-01-25T10:31:00Z",
                        "progress_percentage": 45.5,
                        "current_node_id": "node_test_execution_3",
                        "retry_count": 0,
                        "max_retries": 3,
                        "triggered_by": "user123",
                        "tags": ["regression", "api-tests"]
                    }
                }
            }
        },
        400: {
            "description": "Invalid job ID format",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid job ID format: invalid_id"
                    }
                }
            }
        },
        404: {
            "description": "Job not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Job 60f7b1b9e4b0c8a4f8e6d1a2 not found or access denied"
                    }
                }
            }
        }
    }
)
async def get_job_status(
    job_id: str = Path(
        ...,
        description="Unique job identifier (MongoDB ObjectId)",
        example="60f7b1b9e4b0c8a4f8e6d1a2",
        min_length=24,
        max_length=24
    ),
    current_user: UserResponse = Depends(get_current_user),
    controller: OrchestrationController = Depends(OrchestrationControllerFactory.create_controller)
) -> JobStatusResponse:
    """
    Retrieve detailed status information for a specific orchestration job.
    
    Validates job ownership and returns comprehensive job status including
    execution progress, current state, and detailed execution metadata.
    
    Args:
        job_id: Unique job identifier (MongoDB ObjectId)
        current_user: Authenticated user from JWT token
        controller: Injected orchestration controller instance
        
    Returns:
        JobStatusResponse: Comprehensive job status information
    """
    logger.info(
        "Processing job status request",
        extra={
            "user_id": current_user.id,
            "job_id": job_id,
            "endpoint": "GET /orchestration/job/{job_id}"
        }
    )
    
    return await controller.get_job_status(
        job_id=job_id,
        current_user=current_user
    )


@router.delete(
    "/job/{job_id}",
    response_model=OrchestrationResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel Orchestration Job",
    description="""
    Cancel a running orchestration job and perform graceful cleanup.
    
    Initiates job cancellation through the execution state tracker, which handles
    graceful termination of running nodes, cleanup of resources, and state
    synchronization. Only jobs in cancellable states can be cancelled.
    
    **Authentication Required**: JWT token with valid user credentials.
    **Authorization**: Users can only cancel jobs they own.
    
    **Path Parameters**: 
    - job_id: MongoDB ObjectId of the orchestration job
    
    **Cancellable States**: pending, ready, running, retry
    **Non-cancellable States**: completed, failed, cancelled
    
    **HTTP Status Codes**:
    - 200: Job cancellation initiated successfully
    - 400: Invalid job ID format
    - 403: Access denied (user doesn't own the job)
    - 404: Job not found or inaccessible
    - 409: Job cannot be cancelled in current state
    - 500: Internal server error during cancellation
    """,
    responses={
        200: {
            "description": "Job cancellation initiated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Job 60f7b1b9e4b0c8a4f8e6d1a2 cancellation initiated successfully",
                        "data": {
                            "job_id": "60f7b1b9e4b0c8a4f8e6d1a2",
                            "cancelled_at": "2024-01-25T10:35:00Z",
                            "cancellation_reason": "User requested"
                        },
                        "request_id": "req_987654321"
                    }
                }
            }
        },
        409: {
            "description": "Job cannot be cancelled",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Job 60f7b1b9e4b0c8a4f8e6d1a2 cannot be cancelled in completed state"
                    }
                }
            }
        },
        404: {
            "description": "Job not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Job 60f7b1b9e4b0c8a4f8e6d1a2 not found or access denied"
                    }
                }
            }
        }
    }
)
async def cancel_orchestration_job(
    job_id: str = Path(
        ...,
        description="Unique job identifier (MongoDB ObjectId)",
        example="60f7b1b9e4b0c8a4f8e6d1a2",
        min_length=24,
        max_length=24
    ),
    current_user: UserResponse = Depends(get_current_user),
    controller: OrchestrationController = Depends(OrchestrationControllerFactory.create_controller)
) -> OrchestrationResponse:
    """
    Cancel a running orchestration job.
    
    Validates job ownership and state, then initiates graceful cancellation
    through the execution state tracker.
    
    Args:
        job_id: Unique job identifier (MongoDB ObjectId)
        current_user: Authenticated user from JWT token
        controller: Injected orchestration controller instance
        
    Returns:
        OrchestrationResponse: Cancellation confirmation with metadata
    """
    logger.info(
        "Processing job cancellation request",
        extra={
            "user_id": current_user.id,
            "job_id": job_id,
            "endpoint": "DELETE /orchestration/job/{job_id}"
        }
    )
    
    return await controller.cancel_orchestration_job(
        job_id=job_id,
        current_user=current_user
    )


@router.get(
    "/jobs",
    response_model=JobListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Orchestration Jobs",
    description="""
    Retrieve a paginated list of orchestration jobs with filtering support.
    
    Returns jobs owned by the authenticated user with support for various filters
    including status, creation date range, and target type. Results are paginated
    and include comprehensive job metadata for each entry.
    
    **Authentication Required**: JWT token with valid user credentials.
    **User Scoping**: Only returns jobs owned by the authenticated user.
    
    **Query Parameters**: All optional for flexible filtering
    - status: Filter by job status (pending, running, completed, etc.)
    - created_after: Filter jobs created after specified date
    - created_before: Filter jobs created before specified date  
    - target_type: Filter by job type (test_execution, test_suite_execution, etc.)
    - limit: Maximum results per page (1-100, default 20)
    - offset: Number of results to skip (default 0)
    
    **HTTP Status Codes**:
    - 200: Jobs retrieved successfully
    - 400: Invalid query parameters or pagination values
    - 500: Internal server error during job listing
    """,
    responses={
        200: {
            "description": "Jobs retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "jobs": [
                            {
                                "job_id": "60f7b1b9e4b0c8a4f8e6d1a2",
                                "job_name": "Test Suite Execution",
                                "job_type": "test_suite_execution",
                                "status": "completed",
                                "priority": 5,
                                "triggered_at": "2024-01-25T10:30:00Z",
                                "completed_at": "2024-01-25T10:45:00Z",
                                "progress_percentage": 100.0,
                                "retry_count": 0,
                                "triggered_by": "user123"
                            }
                        ],
                        "total_count": 25,
                        "page": 1,
                        "page_size": 20,
                        "has_next": True
                    }
                }
            }
        },
        400: {
            "description": "Invalid query parameters",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Limit must be between 1 and 100"
                    }
                }
            }
        }
    }
)
async def list_orchestration_jobs(
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Filter by job status (pending, running, completed, failed, cancelled)",
        example="running"
    ),
    created_after: Optional[datetime] = Query(
        None,
        alias="created_after",
        description="Filter jobs created after this date (ISO format)",
        example="2024-01-25T00:00:00Z"
    ),
    created_before: Optional[datetime] = Query(
        None,
        alias="created_before", 
        description="Filter jobs created before this date (ISO format)",
        example="2024-01-26T00:00:00Z"
    ),
    target_type: Optional[str] = Query(
        None,
        alias="target_type",
        description="Filter by job type (test_execution, test_suite_execution, etc.)",
        example="test_suite_execution"
    ),
    limit: int = Query(
        20,
        ge=1,
        le=100,
        description="Maximum number of results per page",
        example=20
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Number of results to skip for pagination",
        example=0
    ),
    current_user: UserResponse = Depends(get_current_user),
    controller: OrchestrationController = Depends(OrchestrationControllerFactory.create_controller)
) -> JobListResponse:
    """
    List orchestration jobs with filtering and pagination.
    
    Returns a paginated list of jobs owned by the authenticated user,
    with support for various filters and sorting options.
    
    Args:
        status_filter: Optional status filter
        created_after: Optional creation date lower bound
        created_before: Optional creation date upper bound
        target_type: Optional job type filter
        limit: Maximum results per page (1-100)
        offset: Results to skip for pagination
        current_user: Authenticated user from JWT token
        controller: Injected orchestration controller instance
        
    Returns:
        JobListResponse: Paginated list of job summaries
    """
    logger.info(
        "Processing job listing request",
        extra={
            "user_id": current_user.id,
            "status_filter": status_filter,
            "target_type": target_type,
            "limit": limit,
            "offset": offset,
            "endpoint": "GET /orchestration/jobs"
        }
    )
    
    return await controller.list_orchestration_jobs(
        status_filter=status_filter,
        created_after=created_after,
        created_before=created_before,
        target_type=target_type,
        limit=limit,
        offset=offset,
        current_user=current_user
    )


# Health check endpoint for orchestration service monitoring
@router.get(
    "/health",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Orchestration Service Health Check",
    description="""
    Check the health status of the orchestration service.
    
    Returns basic health information including service status, version,
    and timestamp. This endpoint can be used for monitoring and health checks.
    
    **Authentication Required**: JWT token with valid user credentials.
    
    **HTTP Status Codes**:
    - 200: Service is healthy and operational
    - 500: Service health check failed
    """,
    responses={
        200: {
            "description": "Service is healthy",
            "content": {
                "application/json": {
                    "example": {
                        "service": "orchestration",
                        "status": "healthy",
                        "version": "1.0.0",
                        "timestamp": "2024-01-25T10:30:00Z"
                    }
                }
            }
        }
    },
    tags=["Health"]
)
async def orchestration_health_check(
    current_user: UserResponse = Depends(get_current_user)
) -> dict:
    """
    Perform orchestration service health check.
    
    Returns basic service health information for monitoring purposes.
    
    Args:
        current_user: Authenticated user from JWT token
        
    Returns:
        dict: Service health information
    """
    logger.info(
        "Processing health check request",
        extra={
            "user_id": current_user.id,
            "endpoint": "GET /orchestration/health"
        }
    )
    
    return {
        "service": "orchestration",
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "authenticated_user": current_user.email
    } 
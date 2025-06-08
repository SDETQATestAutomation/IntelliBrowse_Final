"""
Scheduler Routes - FastAPI HTTP Endpoints

Implements RESTful API endpoints for the Scheduled Task Runner with comprehensive
OpenAPI documentation, JWT authentication, and proper HTTP status codes.

Route Structure:
- POST /api/scheduler/triggers/ - Create scheduled trigger
- PUT /api/scheduler/triggers/{trigger_id} - Update scheduled trigger  
- DELETE /api/scheduler/triggers/{trigger_id} - Delete scheduled trigger
- POST /api/scheduler/triggers/{trigger_id}/execute - Manual trigger execution
- GET /api/scheduler/triggers/{trigger_id}/history - Get trigger execution history

All routes require JWT authentication and provide detailed OpenAPI documentation.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query

from ...config.logging import get_logger
from ...auth.dependencies.auth_dependencies import get_current_user
from ...auth.schemas.auth_responses import UserResponse
from ..controllers.scheduler_controller import SchedulerController, SchedulerControllerFactory
from ..schemas.trigger_schemas import (
    CreateScheduledTriggerRequest,
    UpdateScheduledTriggerRequest,
    ScheduledTriggerResponse,
    ExecutionStatusResponse,
    ExecutionHistoryResponse,
    BaseResponseSchema
)

logger = get_logger(__name__)

# Create router with prefix and tags
router = APIRouter(
    prefix="/api/scheduler",
    tags=["scheduler"],
    dependencies=[Depends(get_current_user)]
)

# Controller factory for dependency injection
def get_scheduler_controller() -> SchedulerController:
    """Dependency to get scheduler controller instance"""
    return SchedulerControllerFactory.create()


@router.post(
    "/triggers/",
    response_model=ScheduledTriggerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Scheduled Trigger",
    description="""
    Create a new scheduled trigger with specified configuration.
    
    **Features:**
    - Time-based triggers with cron expressions
    - Event-driven triggers with webhook integration
    - Dependency-based triggers with conditional execution
    - Configurable retry policies and execution windows
    - Tag-based organization and metadata support
    
    **Authentication:** Requires valid JWT token
    **Authorization:** User can create triggers in their scope
    """
)
async def create_scheduled_trigger(
    request: CreateScheduledTriggerRequest,
    current_user: UserResponse = Depends(get_current_user),
    controller: SchedulerController = Depends(get_scheduler_controller)
) -> ScheduledTriggerResponse:
    """
    Create a new scheduled trigger.
    
    Args:
        request: Trigger creation request with configuration
        current_user: Authenticated user from JWT
        controller: Injected scheduler controller
        
    Returns:
        ScheduledTriggerResponse: Created trigger data with ID and configuration
        
    Raises:
        HTTPException: 
            - 400: Validation error (invalid configuration, malformed cron, etc.)
            - 401: Authentication required
            - 500: Internal server error
    """
    logger.info(
        f"API: Create scheduled trigger request",
        extra={
            "user_id": current_user.id,
            "trigger_name": request.name,
            "trigger_type": request.trigger_config.trigger_type.value,
            "endpoint": "POST /api/scheduler/triggers/"
        }
    )
    
    return await controller.create_scheduled_trigger(request, current_user)


@router.put(
    "/triggers/{trigger_id}",
    response_model=ScheduledTriggerResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Scheduled Trigger",
    description="""
    Update an existing scheduled trigger configuration.
    
    **Features:**
    - Partial updates (only specified fields are changed)
    - Configuration validation before applying changes
    - Status updates (active, paused, disabled)
    - Metadata and tag management
    - Automatic trigger rescheduling if needed
    
    **Authentication:** Requires valid JWT token
    **Authorization:** User can only update triggers they have access to
    """
)
async def update_scheduled_trigger(
    trigger_id: str,
    request: UpdateScheduledTriggerRequest,
    current_user: UserResponse = Depends(get_current_user),
    controller: SchedulerController = Depends(get_scheduler_controller)
) -> ScheduledTriggerResponse:
    """
    Update an existing scheduled trigger.
    
    Args:
        trigger_id: UUID of the trigger to update
        request: Trigger update request with changes
        current_user: Authenticated user from JWT
        controller: Injected scheduler controller
        
    Returns:
        ScheduledTriggerResponse: Updated trigger data
        
    Raises:
        HTTPException:
            - 400: Validation error (invalid ID format, empty update, etc.)
            - 401: Authentication required
            - 404: Trigger not found
            - 500: Internal server error
    """
    logger.info(
        f"API: Update scheduled trigger request",
        extra={
            "user_id": current_user.id,
            "trigger_id": trigger_id,
            "update_fields": list(request.model_dump(exclude_none=True).keys()),
            "endpoint": f"PUT /api/scheduler/triggers/{trigger_id}"
        }
    )
    
    return await controller.update_scheduled_trigger(trigger_id, request, current_user)


@router.delete(
    "/triggers/{trigger_id}",
    response_model=BaseResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Delete Scheduled Trigger",
    description="""
    Delete a scheduled trigger and remove it from the scheduling queue.
    
    **Features:**
    - Immediate removal from scheduling queue
    - Graceful handling of running executions
    - Cleanup of associated metadata and history
    - Audit logging for compliance
    
    **Warning:** This action is irreversible. All trigger configuration and 
    execution history will be permanently deleted.
    
    **Authentication:** Requires valid JWT token
    **Authorization:** User can only delete triggers they have access to
    """
)
async def delete_scheduled_trigger(
    trigger_id: str,
    current_user: UserResponse = Depends(get_current_user),
    controller: SchedulerController = Depends(get_scheduler_controller)
) -> BaseResponseSchema:
    """
    Delete a scheduled trigger.
    
    Args:
        trigger_id: UUID of the trigger to delete
        current_user: Authenticated user from JWT
        controller: Injected scheduler controller
        
    Returns:
        BaseResponseSchema: Deletion confirmation
        
    Raises:
        HTTPException:
            - 400: Validation error (invalid ID format)
            - 401: Authentication required
            - 404: Trigger not found
            - 500: Internal server error
    """
    logger.info(
        f"API: Delete scheduled trigger request",
        extra={
            "user_id": current_user.id,
            "trigger_id": trigger_id,
            "endpoint": f"DELETE /api/scheduler/triggers/{trigger_id}"
        }
    )
    
    return await controller.delete_scheduled_trigger(trigger_id, current_user)


@router.post(
    "/triggers/{trigger_id}/execute",
    response_model=ExecutionStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Manual Trigger Execution",
    description="""
    Manually trigger execution of a scheduled trigger outside its normal schedule.
    
    **Features:**
    - Immediate execution with high priority
    - Override default execution parameters
    - Real-time execution status tracking
    - Integration with existing retry policies
    - Audit logging for manual executions
    
    **Use Cases:**
    - Testing trigger configuration
    - Emergency execution outside schedule
    - Recovery from failed scheduled execution
    - On-demand execution for debugging
    
    **Authentication:** Requires valid JWT token
    **Authorization:** User must have execute permission on the trigger
    """
)
async def manual_trigger_execution(
    trigger_id: str,
    current_user: UserResponse = Depends(get_current_user),
    controller: SchedulerController = Depends(get_scheduler_controller)
) -> ExecutionStatusResponse:
    """
    Manually execute a scheduled trigger.
    
    Args:
        trigger_id: UUID of the trigger to execute
        current_user: Authenticated user from JWT
        controller: Injected scheduler controller
        
    Returns:
        ExecutionStatusResponse: Execution status with job ID and tracking info
        
    Raises:
        HTTPException:
            - 400: Validation error (invalid ID format)
            - 401: Authentication required
            - 403: Trigger is disabled or user lacks execute permission
            - 404: Trigger not found
            - 500: Internal server error
    """
    logger.info(
        f"API: Manual trigger execution request",
        extra={
            "user_id": current_user.id,
            "trigger_id": trigger_id,
            "endpoint": f"POST /api/scheduler/triggers/{trigger_id}/execute"
        }
    )
    
    return await controller.manual_trigger_execution(trigger_id, current_user)


@router.get(
    "/triggers/{trigger_id}/history",
    response_model=ExecutionHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Trigger Execution History",
    description="""
    Retrieve execution history for a scheduled trigger with pagination support.
    
    **Features:**
    - Complete execution history with success/failure details
    - Pagination for large history sets
    - Performance metrics and timing information
    - Error details and retry information
    - Filtering by date range and execution status
    
    **History Includes:**
    - Job execution status and results
    - Execution timing and performance metrics
    - Error details and stack traces (if applicable)
    - Retry attempts and outcomes
    - Worker instance and resource usage
    
    **Authentication:** Requires valid JWT token
    **Authorization:** User can only view history for accessible triggers
    """
)
async def get_trigger_history(
    trigger_id: str,
    page: int = Query(default=1, ge=1, description="Page number (starts from 1)"),
    page_size: int = Query(default=20, ge=1, le=100, description="Number of records per page (1-100)"),
    current_user: UserResponse = Depends(get_current_user),
    controller: SchedulerController = Depends(get_scheduler_controller)
) -> ExecutionHistoryResponse:
    """
    Get execution history for a scheduled trigger.
    
    Args:
        trigger_id: UUID of the trigger to get history for
        page: Page number for pagination (starts from 1)
        page_size: Number of records per page (1-100)
        current_user: Authenticated user from JWT
        controller: Injected scheduler controller
        
    Returns:
        ExecutionHistoryResponse: Paginated execution history with metadata
        
    Raises:
        HTTPException:
            - 400: Validation error (invalid ID format, pagination params)
            - 401: Authentication required
            - 404: Trigger not found
            - 500: Internal server error
    """
    logger.info(
        f"API: Get trigger history request",
        extra={
            "user_id": current_user.id,
            "trigger_id": trigger_id,
            "page": page,
            "page_size": page_size,
            "endpoint": f"GET /api/scheduler/triggers/{trigger_id}/history"
        }
    )
    
    return await controller.get_trigger_history(trigger_id, current_user, page, page_size)


# Health check endpoint for scheduler service
@router.get(
    "/health",
    response_model=BaseResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Scheduler Health Check",
    description="""
    Check the health status of the scheduler service and its components.
    
    **Features:**
    - Service availability status
    - Component health indicators
    - Performance metrics
    - Database connectivity status
    - Queue status and metrics
    
    **Authentication:** Requires valid JWT token
    """
)
async def scheduler_health_check(
    current_user: UserResponse = Depends(get_current_user)
) -> BaseResponseSchema:
    """
    Check scheduler service health.
    
    Args:
        current_user: Authenticated user from JWT
        
    Returns:
        BaseResponseSchema: Health status information
    """
    logger.info(
        f"API: Scheduler health check request",
        extra={
            "user_id": current_user.id,
            "endpoint": "GET /api/scheduler/health"
        }
    )
    
    # Phase 3 TODO: Implement actual health checks
    return BaseResponseSchema(
        success=True,
        message="Scheduler service is healthy"
    )


# Include router in main application
# This is typically done in the main FastAPI app setup
__all__ = ["router"] 
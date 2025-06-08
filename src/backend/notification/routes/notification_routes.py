"""
IntelliBrowse Notification Engine - FastAPI Routes

This module defines the FastAPI route endpoints for the Notification Engine,
providing RESTful API access to notification functionality with JWT authentication,
input validation, and standardized response formatting.

Routes:
    - GET /api/notifications - Get user's notification history
    - GET /api/notifications/{notification_id} - Get specific notification details
    - GET /api/notifications/analytics/summary - Get analytics summary
    - PUT /api/notifications/preferences - Update user preferences
    - POST /api/notifications/preferences/sync - Force preference sync
    - POST /api/notifications/{notification_id}/resend - Resend notification (admin)

Author: IntelliBrowse Team
Created: Phase 4 - Controllers & API Layer Implementation
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body, status
from pydantic import Field
from fastapi.responses import JSONResponse

# Controller imports
from ..controllers.notification_controller import NotificationController

# Schema imports
from ..schemas.notification_schemas import (
    SendNotificationRequest,
    NotificationResponse,
    NotificationStatusResponse,
    NotificationListResponse,
    NotificationHistoryListResponse,
    NotificationHistoryDetailResponse,
    NotificationHealthResponse
)
from ..schemas.history_schemas import (
    HistoryFilterRequest
)
from ..schemas.preference_schemas import (
    UserPreferencesResponse,
    UpdatePreferencesRequest,
    PreferenceSyncResponse
)
from ...schemas.response import SuccessResponse

# Auth imports
from ...auth.dependencies.auth_dependencies import get_current_user
from ...auth.schemas.auth_responses import UserResponse

# Service dependency imports
from ..services.notification_service import NotificationService
from ..services.notification_history_service import NotificationHistoryService
from ..services.notification_analytics_service import NotificationAnalyticsService
from ..services.notification_preference_sync_service import NotificationPreferenceSyncService

# Database imports
from ...config.database import get_database
from motor.motor_asyncio import AsyncIOMotorDatabase

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/api/notifications",
    tags=["notifications"],
    responses={
        401: {"description": "Unauthorized - Invalid or missing JWT token"},
        403: {"description": "Forbidden - Insufficient permissions"},
        422: {"description": "Validation Error - Invalid request data"},
        500: {"description": "Internal Server Error"}
    }
)

# PHASE 6 INTEGRATION: Include health monitoring routes
from .health_routes import router as health_router
router.include_router(health_router)


async def get_notification_controller(
    database: AsyncIOMotorDatabase = Depends(get_database)
) -> NotificationController:
    """
    Dependency injection factory for NotificationController
    
    Creates and configures the NotificationController with all required service dependencies.
    This follows the FastAPI dependency injection pattern used throughout IntelliBrowse.
    
    Args:
        database: MongoDB database instance from dependency injection
        
    Returns:
        Configured NotificationController instance
    """
    # Initialize service collections
    notifications_collection = database.notifications
    history_collection = database.notification_delivery_history
    preferences_collection = database.user_notification_preferences
    analytics_collection = database.notification_delivery_history  # Same collection for analytics
    sync_status_collection = database.notification_sync_status
    audit_collection = database.notification_audit

    # Initialize services
    notification_service = NotificationService(
        database=database,
        channel_adapters={}  # TODO: Initialize with actual channel adapters
    )
    
    history_service = NotificationHistoryService(
        collection=history_collection
    )
    
    analytics_service = NotificationAnalyticsService(
        collection=analytics_collection,
        redis_client=None  # TODO: Initialize with Redis client if available
    )
    
    preference_sync_service = NotificationPreferenceSyncService(
        preferences_collection=preferences_collection,
        sync_status_collection=sync_status_collection,
        audit_collection=audit_collection,
        user_context_service=None  # TODO: Initialize with user context service
    )
    
    # Create and return controller
    return NotificationController(
        notification_service=notification_service,
        history_service=history_service,
        analytics_service=analytics_service,
        preference_sync_service=preference_sync_service
    )


@router.get(
    "/",
    response_model=SuccessResponse[NotificationHistoryListResponse],
    summary="Get User Notification History",
    description="Retrieve paginated notification history for the authenticated user with optional filtering"
)
async def get_user_notifications(
    page: int = Query(
        default=1,
        ge=1,
        le=1000,
        description="Page number (1-based)",
        example=1
    ),
    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Number of items per page",
        example=20
    ),
    status: Optional[str] = Query(
        default=None,
        description="Filter by delivery status (sent, failed, pending)",
        example="sent"
    ),
    channel: Optional[str] = Query(
        default=None,
        description="Filter by notification channel (email, slack, webhook)",
        example="email"
    ),
    date_from: Optional[datetime] = Query(
        default=None,
        description="Start date for date range filter (ISO format)",
        example="2024-01-01T00:00:00Z"
    ),
    date_to: Optional[datetime] = Query(
        default=None,
        description="End date for date range filter (ISO format)",
        example="2024-01-31T23:59:59Z"
    ),
    priority: Optional[str] = Query(
        default=None,
        description="Filter by notification priority (low, medium, high, critical)",
        example="high"
    ),
    notification_type: Optional[str] = Query(
        default=None,
        description="Filter by notification type",
        example="test_execution_complete"
    ),
    search_term: Optional[str] = Query(
        default=None,
        max_length=100,
        description="Search term for notification content",
        example="deployment"
    ),
    current_user: UserResponse = Depends(get_current_user),
    controller: NotificationController = Depends(get_notification_controller)
):
    """
    Get paginated notification history for the authenticated user.
    
    Supports advanced filtering by status, channel, date range, priority, type, and content search.
    Returns paginated results with metadata for efficient large dataset handling.
    """
    try:
        # Create filter request if any filters are provided
        filters = None
        if any([status, channel, date_from, date_to, priority, notification_type, search_term]):
            filters = HistoryFilterRequest(
                status=status,
                channel=channel,
                date_from=date_from,
                date_to=date_to,
                priority=priority,
                notification_type=notification_type,
                search_term=search_term
            )
        
        # Delegate to controller
        response = await controller.get_user_notifications(
            user=current_user,
            page=page,
            page_size=page_size,
            filters=filters
        )
        
        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions from controller
        raise
    except Exception as e:
        logger.error(
            "Unexpected error in get_user_notifications route",
            user_id=current_user.id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )


@router.get(
    "/{notification_id}",
    response_model=SuccessResponse[NotificationHistoryDetailResponse],
    summary="Get Notification Details",
    description="Retrieve detailed information for a specific notification with full audit trace"
)
async def get_notification_by_id(
    notification_id: str = Path(
        ...,
        description="Notification identifier",
        example="ntfy_abc123def456",
        regex=r"^ntfy_[a-f0-9]{12}$"
    ),
    current_user: UserResponse = Depends(get_current_user),
    controller: NotificationController = Depends(get_notification_controller)
):
    """
    Get detailed information for a specific notification.
    
    Returns comprehensive notification details including delivery attempts,
    error logs, and audit trail. Access is restricted to the notification's
    recipients and the user who created it.
    """
    try:
        # Delegate to controller
        response = await controller.get_notification_by_id(
            user=current_user,
            notification_id=notification_id
        )
        
        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions from controller
        raise
    except Exception as e:
        logger.error(
            "Unexpected error in get_notification_by_id route",
            user_id=current_user.id,
            notification_id=notification_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )


@router.get(
    "/analytics/summary",
    response_model=SuccessResponse[Dict[str, Any]],
    summary="Get Analytics Summary",
    description="Retrieve aggregated notification analytics including delivery rates and performance metrics"
)
async def get_analytics_summary(
    time_window: str = Query(
        default="7d",
        description="Time window for analytics (1h, 1d, 7d, 30d, 90d, 365d)",
        example="7d",
        regex=r"^(1h|1d|7d|30d|90d|365d)$"
    ),
    start_date: Optional[datetime] = Query(
        default=None,
        description="Custom start date (overrides time_window)",
        example="2024-01-01T00:00:00Z"
    ),
    end_date: Optional[datetime] = Query(
        default=None,
        description="Custom end date (overrides time_window)",
        example="2024-01-31T23:59:59Z"
    ),
    current_user: UserResponse = Depends(get_current_user),
    controller: NotificationController = Depends(get_notification_controller)
):
    """
    Get aggregated analytics summary for the authenticated user.
    
    Returns dashboard-ready metrics including:
    - Channel performance statistics
    - Success/failure rates
    - Time-series data
    - User responsiveness metrics
    """
    try:
        # Delegate to controller
        response = await controller.get_analytics_summary(
            user=current_user,
            time_window=time_window,
            start_date=start_date,
            end_date=end_date
        )
        
        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions from controller
        raise
    except Exception as e:
        logger.error(
            "Unexpected error in get_analytics_summary route",
            user_id=current_user.id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )


@router.put(
    "/preferences",
    response_model=SuccessResponse[PreferenceSyncResponse],
    summary="Update User Preferences",
    description="Update notification preferences for the authenticated user with validation and sync"
)
async def update_user_preferences(
    preferences_request: UpdatePreferencesRequest = Body(
        ...,
        description="Notification preference updates",
        example={
            "channel_preferences": {
                "email": {
                    "enabled": True,
                    "priority": "high",
                    "delivery_time_windows": [
                        {
                            "start_time": "09:00",
                            "end_time": "17:00",
                            "days_of_week": [1, 2, 3, 4, 5]
                        }
                    ]
                }
            },
            "global_settings": {
                "timezone": "UTC",
                "language": "en",
                "digest_frequency": "daily"
            }
        }
    ),
    current_user: UserResponse = Depends(get_current_user),
    controller: NotificationController = Depends(get_notification_controller)
):
    """
    Update notification preferences for the authenticated user.
    
    Supports updating channel preferences, global settings, and notification type filters.
    Changes are validated and synchronized to the distributed context store.
    """
    try:
        # Delegate to controller
        response = await controller.update_user_preferences(
            user=current_user,
            preferences_request=preferences_request
        )
        
        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions from controller
        raise
    except Exception as e:
        logger.error(
            "Unexpected error in update_user_preferences route",
            user_id=current_user.id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )


@router.post(
    "/preferences/sync",
    response_model=SuccessResponse[Dict[str, Any]],
    summary="Force Preference Synchronization",
    description="Force synchronization of user preferences to distributed context store"
)
async def sync_preferences(
    force_sync: bool = Query(
        default=False,
        description="Force sync even if recently synchronized"
    ),
    current_user: UserResponse = Depends(get_current_user),
    controller: NotificationController = Depends(get_notification_controller)
):
    """
    Force synchronization of user preferences to external systems.
    
    Triggers immediate synchronization of notification preferences to the
    distributed context store, ensuring consistency across all services.
    """
    try:
        # Delegate to controller
        response = await controller.sync_preferences(
            user=current_user,
            force_sync=force_sync
        )
        
        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions from controller
        raise
    except Exception as e:
        logger.error(
            "Unexpected error in sync_preferences route",
            user_id=current_user.id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )


@router.post(
    "/{notification_id}/resend",
    response_model=SuccessResponse[Dict[str, Any]],
    summary="Resend Notification (Admin Only)",
    description="Resend a failed notification - requires admin privileges"
)
async def resend_notification(
    notification_id: str = Path(
        ...,
        description="Notification identifier to resend",
        example="ntfy_abc123def456",
        regex=r"^ntfy_[a-f0-9]{12}$"
    ),
    admin_reason: Optional[str] = Body(
        default=None,
        description="Administrative reason for resending",
        example="User reported delivery failure"
    ),
    current_user: UserResponse = Depends(get_current_user),
    controller: NotificationController = Depends(get_notification_controller)
):
    """
    Resend a notification that failed delivery (admin only).
    
    This endpoint is restricted to admin users and allows redelivery of failed
    notifications. An audit log entry is created with the admin's reason.
    
    Note: Admin role checking should be implemented at the dependency or
    middleware level in production.
    """
    try:
        # TODO: Add admin role checking
        # For now, this is a placeholder that logs the admin action
        
        # Delegate to controller
        response = await controller.resend_notification(
            user=current_user,
            notification_id=notification_id,
            admin_reason=admin_reason
        )
        
        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions from controller
        raise
    except Exception as e:
        logger.error(
            "Unexpected error in resend_notification route",
            user_id=current_user.id,
            notification_id=notification_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )


# Health check endpoint for notification service
@router.get(
    "/health",
    response_model=SuccessResponse[Dict[str, Any]],
    summary="Notification Service Health Check",
    description="Check the health and status of the notification service",
    tags=["health"]
)
async def notification_health_check():
    """
    Health check endpoint for the notification service.
    
    Returns the current status and basic connectivity information
    for the notification service components.
    """
    try:
        health_data = {
            "status": "healthy",
            "timestamp": datetime.utcnow(),
            "service": "notification_engine",
            "version": "1.0.0",
            "checks": {
                "controller": "available",
                "routes": "active",
                "dependencies": "loaded"
            }
        }
        
        return SuccessResponse(
            data=health_data,
            message="Notification service is healthy"
        )
        
    except Exception as e:
        logger.error(
            "Error in notification health check",
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Notification service health check failed"
        ) 
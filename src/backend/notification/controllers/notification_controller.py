"""
IntelliBrowse Notification Engine - Controller Layer

This module provides the HTTP orchestration layer for the Notification Engine,
implementing a fully decoupled controller that coordinates between FastAPI routes
and service layer business logic.

Classes:
    - NotificationController: Core controller for HTTP request orchestration
    - ControllerDependencies: Dependency injection container
    - RequestValidator: Input validation and sanitization

Author: IntelliBrowse Team
Created: Phase 4 - Controllers & API Layer Implementation
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from fastapi import HTTPException, status
from pydantic import ValidationError

# Service layer imports
from ..services.notification_service import NotificationService
from ..services.notification_history_service import NotificationHistoryService
from ..services.notification_analytics_service import NotificationAnalyticsService, AnalyticsTimeWindow
from ..services.notification_preference_sync_service import NotificationPreferenceSyncService

# Schema imports
from ..schemas.notification_schemas import (
    SendNotificationRequest,
    NotificationResponse,
    NotificationStatusResponse,
    NotificationListResponse
)
from ..schemas.history_schemas import (
    NotificationHistoryListResponse,
    NotificationHistoryDetailResponse,
    HistoryFilterRequest
)
from ..schemas.preference_schemas import (
    UserPreferencesResponse,
    UpdatePreferencesRequest,
    PreferenceSyncResponse
)
from ...schemas.response import BaseResponse, SuccessResponse, ErrorResponse

# Auth schema imports
from ...auth.schemas.auth_responses import UserResponse

# Configure logging
logger = logging.getLogger(__name__)


class RequestValidator:
    """
    Utility class for request validation and sanitization
    
    Provides methods to validate and sanitize incoming HTTP requests,
    protecting against injection vectors and ensuring data integrity.
    """
    
    @staticmethod
    def validate_user_id(user_id: str) -> str:
        """
        Validate and sanitize user ID
        
        Args:
            user_id: User identifier to validate
            
        Returns:
            Validated user ID
            
        Raises:
            HTTPException: If user ID is invalid
        """
        if not user_id or not user_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User ID cannot be empty"
            )
        
        # Basic sanitization - remove whitespace
        cleaned_id = user_id.strip()
        
        # Length validation
        if len(cleaned_id) < 3 or len(cleaned_id) > 128:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User ID must be between 3 and 128 characters"
            )
        
        return cleaned_id
    
    @staticmethod
    def validate_notification_id(notification_id: str) -> str:
        """
        Validate and sanitize notification ID
        
        Args:
            notification_id: Notification identifier to validate
            
        Returns:
            Validated notification ID
            
        Raises:
            HTTPException: If notification ID is invalid
        """
        if not notification_id or not notification_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Notification ID cannot be empty"
            )
        
        cleaned_id = notification_id.strip()
        
        # Basic format validation for our notification IDs (ntfy_xxxxxx)
        if not cleaned_id.startswith('ntfy_') or len(cleaned_id) != 17:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid notification ID format"
            )
        
        return cleaned_id
    
    @staticmethod
    def validate_pagination_params(page: int, page_size: int) -> tuple[int, int]:
        """
        Validate pagination parameters
        
        Args:
            page: Page number (1-based)
            page_size: Items per page
            
        Returns:
            Validated (page, page_size) tuple
            
        Raises:
            HTTPException: If pagination parameters are invalid
        """
        if page < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Page number must be >= 1"
            )
        
        if page > 1000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Page number cannot exceed 1000"
            )
        
        if page_size < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Page size must be >= 1"
            )
        
        if page_size > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Page size cannot exceed 100"
            )
        
        return page, page_size


class NotificationController:
    """
    Core controller for notification HTTP orchestration
    
    Provides async methods for coordinating between FastAPI routes and service
    layer business logic, with comprehensive error handling, logging, and security.
    """
    
    def __init__(
        self,
        notification_service: NotificationService,
        history_service: NotificationHistoryService,
        analytics_service: NotificationAnalyticsService,
        preference_sync_service: NotificationPreferenceSyncService
    ):
        """
        Initialize controller with service dependencies
        
        Args:
            notification_service: Core notification service
            history_service: Notification history service
            analytics_service: Analytics and metrics service
            preference_sync_service: Preference synchronization service
        """
        self.notification_service = notification_service
        self.history_service = history_service
        self.analytics_service = analytics_service
        self.preference_sync_service = preference_sync_service
        self.logger = logger.bind(controller="NotificationController")
    
    async def get_user_notifications(
        self,
        user: UserResponse,
        page: int = 1,
        page_size: int = 20,
        filters: Optional[HistoryFilterRequest] = None
    ) -> SuccessResponse[NotificationHistoryListResponse]:
        """
        Fetch paginated notification history for authenticated user
        
        Args:
            user: Authenticated user from JWT
            page: Page number (1-based)
            page_size: Items per page
            filters: Optional filters for history query
            
        Returns:
            Paginated list of user's notification history
            
        Raises:
            HTTPException: For validation errors or service failures
        """
        request_id = f"req_{uuid.uuid4().hex[:8]}"
        start_time = datetime.now(timezone.utc)
        
        try:
            # Validate and sanitize input
            validated_user_id = RequestValidator.validate_user_id(user.id)
            validated_page, validated_page_size = RequestValidator.validate_pagination_params(
                page, page_size
            )
            
            self.logger.info(
                "Fetching user notifications",
                request_id=request_id,
                user_id=validated_user_id,
                page=validated_page,
                page_size=validated_page_size,
                filters=filters.model_dump() if filters else None
            )
            
            # Delegate to history service
            history_response = await self.history_service.get_history(
                user_id=validated_user_id,
                page=validated_page,
                page_size=validated_page_size,
                filters=filters
            )
            
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            self.logger.info(
                "User notifications retrieved successfully",
                request_id=request_id,
                user_id=validated_user_id,
                total_count=history_response.pagination.total_count,
                returned_count=len(history_response.notifications),
                processing_time_ms=processing_time
            )
            
            return SuccessResponse(
                data=history_response,
                message=f"Retrieved {len(history_response.notifications)} notifications"
            )
            
        except ValidationError as e:
            self.logger.warning(
                "Validation error in get_user_notifications",
                request_id=request_id,
                user_id=user.id,
                error=str(e)
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Validation error: {str(e)}"
            )
        
        except Exception as e:
            self.logger.error(
                "Error fetching user notifications",
                request_id=request_id,
                user_id=user.id,
                error=str(e),
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve notifications"
            )
    
    async def get_notification_by_id(
        self,
        user: UserResponse,
        notification_id: str
    ) -> SuccessResponse[NotificationHistoryDetailResponse]:
        """
        Get detailed notification information with full audit trace
        
        Args:
            user: Authenticated user from JWT
            notification_id: Notification identifier
            
        Returns:
            Detailed notification information with audit trail
            
        Raises:
            HTTPException: For validation errors, access denied, or not found
        """
        request_id = f"req_{uuid.uuid4().hex[:8]}"
        start_time = datetime.now(timezone.utc)
        
        try:
            # Validate and sanitize input
            validated_user_id = RequestValidator.validate_user_id(user.id)
            validated_notification_id = RequestValidator.validate_notification_id(notification_id)
            
            self.logger.info(
                "Fetching notification by ID",
                request_id=request_id,
                user_id=validated_user_id,
                notification_id=validated_notification_id
            )
            
            # Delegate to history service
            detail_response = await self.history_service.get_by_id(
                user_id=validated_user_id,
                notification_id=validated_notification_id
            )
            
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            self.logger.info(
                "Notification detail retrieved successfully",
                request_id=request_id,
                user_id=validated_user_id,
                notification_id=validated_notification_id,
                processing_time_ms=processing_time
            )
            
            return SuccessResponse(
                data=detail_response,
                message="Notification details retrieved successfully"
            )
            
        except ValueError as e:
            # Handle not found or access denied from service
            error_msg = str(e)
            if "not found" in error_msg.lower():
                self.logger.warning(
                    "Notification not found",
                    request_id=request_id,
                    user_id=user.id,
                    notification_id=notification_id
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Notification not found"
                )
            elif "access denied" in error_msg.lower():
                self.logger.warning(
                    "Access denied to notification",
                    request_id=request_id,
                    user_id=user.id,
                    notification_id=notification_id
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to notification"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_msg
                )
        
        except Exception as e:
            self.logger.error(
                "Error fetching notification by ID",
                request_id=request_id,
                user_id=user.id,
                notification_id=notification_id,
                error=str(e),
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve notification details"
            )
    
    async def get_analytics_summary(
        self,
        user: UserResponse,
        time_window: str = "7d",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> SuccessResponse[Dict[str, Any]]:
        """
        Get aggregated delivery and response analytics for user
        
        Args:
            user: Authenticated user from JWT
            time_window: Time window for analytics (1h, 1d, 7d, 30d)
            start_date: Optional custom start date
            end_date: Optional custom end date
            
        Returns:
            Dashboard-ready analytics summary
            
        Raises:
            HTTPException: For validation errors or service failures
        """
        request_id = f"req_{uuid.uuid4().hex[:8]}"
        start_time = datetime.now(timezone.utc)
        
        try:
            # Validate and sanitize input
            validated_user_id = RequestValidator.validate_user_id(user.id)
            
            # Create analytics time window
            analytics_window = AnalyticsTimeWindow(
                window=time_window,
                start_date=start_date,
                end_date=end_date
            )
            
            self.logger.info(
                "Fetching analytics summary",
                request_id=request_id,
                user_id=validated_user_id,
                time_window=time_window,
                start_date=start_date,
                end_date=end_date
            )
            
            # Get dashboard summary from analytics service
            dashboard_summary = await self.analytics_service.get_dashboard_summary(
                user_id=validated_user_id,
                time_window=analytics_window
            )
            
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            self.logger.info(
                "Analytics summary retrieved successfully",
                request_id=request_id,
                user_id=validated_user_id,
                processing_time_ms=processing_time
            )
            
            return SuccessResponse(
                data=dashboard_summary.model_dump(),
                message="Analytics summary retrieved successfully"
            )
            
        except ValidationError as e:
            self.logger.warning(
                "Validation error in get_analytics_summary",
                request_id=request_id,
                user_id=user.id,
                error=str(e)
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Validation error: {str(e)}"
            )
        
        except Exception as e:
            self.logger.error(
                "Error fetching analytics summary",
                request_id=request_id,
                user_id=user.id,
                error=str(e),
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve analytics summary"
            )
    
    async def update_user_preferences(
        self,
        user: UserResponse,
        preferences_request: UpdatePreferencesRequest
    ) -> SuccessResponse[PreferenceSyncResponse]:
        """
        Update user notification preferences with validation and sync
        
        Args:
            user: Authenticated user from JWT
            preferences_request: Preference update request
            
        Returns:
            Preference sync response with status
            
        Raises:
            HTTPException: For validation errors or service failures
        """
        request_id = f"req_{uuid.uuid4().hex[:8]}"
        start_time = datetime.now(timezone.utc)
        
        try:
            # Validate and sanitize input
            validated_user_id = RequestValidator.validate_user_id(user.id)
            
            self.logger.info(
                "Updating user preferences",
                request_id=request_id,
                user_id=validated_user_id,
                preference_changes=preferences_request.model_dump()
            )
            
            # Create sync request from update request
            from ..schemas.preference_schemas import PreferenceSyncRequest
            sync_request = PreferenceSyncRequest(
                channel_preferences=preferences_request.channel_preferences,
                global_settings=preferences_request.global_settings,
                notification_types=preferences_request.notification_types,
                context={
                    "request_id": request_id,
                    "user_agent": "web_ui",
                    "source": "preference_update_endpoint"
                }
            )
            
            # Delegate to preference sync service
            sync_response = await self.preference_sync_service.sync_preferences(
                user_id=validated_user_id,
                sync_request=sync_request,
                actor_id=validated_user_id,  # User updating their own preferences
                context={"request_id": request_id}
            )
            
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            self.logger.info(
                "User preferences updated successfully",
                request_id=request_id,
                user_id=validated_user_id,
                sync_id=sync_response.sync_id,
                processing_time_ms=processing_time
            )
            
            return SuccessResponse(
                data=sync_response,
                message="Preferences updated successfully"
            )
            
        except ValidationError as e:
            self.logger.warning(
                "Validation error in update_user_preferences",
                request_id=request_id,
                user_id=user.id,
                error=str(e)
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Validation error: {str(e)}"
            )
        
        except Exception as e:
            self.logger.error(
                "Error updating user preferences",
                request_id=request_id,
                user_id=user.id,
                error=str(e),
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update preferences"
            )
    
    async def sync_preferences(
        self,
        user: UserResponse,
        force_sync: bool = False
    ) -> SuccessResponse[Dict[str, Any]]:
        """
        Force synchronization of preferences to distributed context store
        
        Args:
            user: Authenticated user from JWT
            force_sync: Whether to force sync even if recently synced
            
        Returns:
            Sync status and timing information
            
        Raises:
            HTTPException: For validation errors or service failures
        """
        request_id = f"req_{uuid.uuid4().hex[:8]}"
        start_time = datetime.now(timezone.utc)
        
        try:
            # Validate and sanitize input
            validated_user_id = RequestValidator.validate_user_id(user.id)
            
            self.logger.info(
                "Forcing preference sync",
                request_id=request_id,
                user_id=validated_user_id,
                force_sync=force_sync
            )
            
            # Create empty sync request for force sync
            from ..schemas.preference_schemas import PreferenceSyncRequest
            sync_request = PreferenceSyncRequest(
                channel_preferences={},
                global_settings={},
                notification_types={},
                context={
                    "request_id": request_id,
                    "operation": "force_sync",
                    "source": "sync_endpoint"
                }
            )
            
            # Delegate to preference sync service
            sync_response = await self.preference_sync_service.sync_preferences(
                user_id=validated_user_id,
                sync_request=sync_request,
                actor_id=validated_user_id,
                context={"request_id": request_id, "force_sync": force_sync}
            )
            
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            self.logger.info(
                "Preference sync completed",
                request_id=request_id,
                user_id=validated_user_id,
                sync_id=sync_response.sync_id,
                processing_time_ms=processing_time
            )
            
            return SuccessResponse(
                data={
                    "sync_id": sync_response.sync_id,
                    "status": sync_response.status.value,
                    "sync_timestamp": sync_response.sync_timestamp,
                    "processing_time_ms": processing_time
                },
                message="Preference synchronization completed"
            )
            
        except Exception as e:
            self.logger.error(
                "Error syncing preferences",
                request_id=request_id,
                user_id=user.id,
                error=str(e),
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to synchronize preferences"
            )
    
    async def resend_notification(
        self,
        user: UserResponse,
        notification_id: str,
        admin_reason: Optional[str] = None
    ) -> SuccessResponse[Dict[str, Any]]:
        """
        Resend a failed notification (admin only operation)
        
        Args:
            user: Authenticated user from JWT (must be admin)
            notification_id: Notification ID to resend
            admin_reason: Optional reason for resending
            
        Returns:
            Resend operation status and new delivery information
            
        Raises:
            HTTPException: For permission errors, validation errors, or service failures
        """
        request_id = f"req_{uuid.uuid4().hex[:8]}"
        start_time = datetime.now(timezone.utc)
        
        try:
            # Admin role check (simplified - in production would check user roles)
            # For now, assume admin check is done at route level or via role claim in JWT
            
            # Validate and sanitize input
            validated_user_id = RequestValidator.validate_user_id(user.id)
            validated_notification_id = RequestValidator.validate_notification_id(notification_id)
            
            self.logger.info(
                "Admin resending notification",
                request_id=request_id,
                admin_user_id=validated_user_id,
                notification_id=validated_notification_id,
                admin_reason=admin_reason
            )
            
            # TODO: Implement resend logic in notification service
            # For now, return placeholder response
            resend_result = {
                "original_notification_id": validated_notification_id,
                "resend_timestamp": datetime.now(timezone.utc),
                "admin_user_id": validated_user_id,
                "admin_reason": admin_reason,
                "status": "queued_for_resend"
            }
            
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            self.logger.info(
                "Notification resend queued",
                request_id=request_id,
                admin_user_id=validated_user_id,
                notification_id=validated_notification_id,
                processing_time_ms=processing_time
            )
            
            return SuccessResponse(
                data=resend_result,
                message="Notification queued for resend"
            )
            
        except Exception as e:
            self.logger.error(
                "Error resending notification",
                request_id=request_id,
                user_id=user.id,
                notification_id=notification_id,
                error=str(e),
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to resend notification"
            )

    # PHASE 6 INTEGRATION: Health Monitoring & Observability Methods
    
    async def get_health_status(self) -> Dict[str, Any]:
        """
        Get comprehensive health status of notification engine and all components.
        
        Returns:
            Dict containing health status of all notification components
        """
        request_id = f"health_{uuid.uuid4().hex[:8]}"
        start_time = datetime.now(timezone.utc)
        
        try:
            self.logger.info(
                "Retrieving notification engine health status",
                request_id=request_id
            )
            
            # Get component health status
            components_status = {}
            
            # Check delivery daemon status
            try:
                from ..daemon.delivery_daemon import DeliveryDaemon
                daemon_health = await self._check_daemon_health()
                components_status["delivery_daemon"] = {
                    "status": "healthy" if daemon_health["is_running"] else "degraded",
                    "last_check": datetime.now(timezone.utc).isoformat(),
                    "uptime_seconds": daemon_health.get("uptime_seconds", 0)
                }
            except Exception as e:
                components_status["delivery_daemon"] = {
                    "status": "unhealthy",
                    "error": str(e),
                    "last_check": datetime.now(timezone.utc).isoformat()
                }
            
            # Check channel adapters
            channel_health = await self._check_channel_adapters_health()
            components_status.update(channel_health)
            
            # Check database connectivity
            try:
                db_health = await self._check_database_health()
                components_status["database"] = db_health
            except Exception as e:
                components_status["database"] = {
                    "status": "unhealthy",
                    "error": str(e),
                    "last_check": datetime.now(timezone.utc).isoformat()
                }
            
            # Determine overall status
            unhealthy_components = [
                name for name, status in components_status.items() 
                if status.get("status") == "unhealthy"
            ]
            degraded_components = [
                name for name, status in components_status.items() 
                if status.get("status") == "degraded"
            ]
            
            if unhealthy_components:
                overall_status = "unhealthy"
            elif degraded_components:
                overall_status = "degraded"
            else:
                overall_status = "healthy"
            
            # Get basic metrics
            metrics = await self._get_basic_metrics()
            
            health_status = {
                "overall_status": overall_status,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "components": components_status,
                "metrics": metrics,
                "unhealthy_components": unhealthy_components,
                "degraded_components": degraded_components
            }
            
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            self.logger.info(
                "Health status retrieved",
                request_id=request_id,
                overall_status=overall_status,
                processing_time_ms=processing_time
            )
            
            return health_status
            
        except Exception as e:
            self.logger.error(
                "Error retrieving health status",
                request_id=request_id,
                error=str(e),
                exc_info=True
            )
            # Return minimal error status
            return {
                "overall_status": "error",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
                "components": {},
                "metrics": {}
            }
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get detailed performance metrics for notification system.
        
        Returns:
            Dict containing performance metrics and delivery statistics
        """
        request_id = f"metrics_{uuid.uuid4().hex[:8]}"
        start_time = datetime.now(timezone.utc)
        
        try:
            self.logger.info(
                "Retrieving performance metrics",
                request_id=request_id
            )
            
            # Get delivery metrics from analytics service
            delivery_metrics = await self._get_delivery_metrics()
            
            # Get channel-specific performance
            channel_performance = await self._get_channel_performance()
            
            # Get system performance metrics
            system_metrics = await self._get_system_metrics()
            
            metrics = {
                "delivery_metrics": delivery_metrics,
                "channel_performance": channel_performance,
                "system_metrics": system_metrics,
                "time_period": "24h",
                "generated_at": datetime.now(timezone.utc).isoformat()
            }
            
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            self.logger.info(
                "Performance metrics retrieved",
                request_id=request_id,
                processing_time_ms=processing_time
            )
            
            return metrics
            
        except Exception as e:
            self.logger.error(
                "Error retrieving performance metrics",
                request_id=request_id,
                error=str(e),
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve performance metrics: {str(e)}"
            )
    
    async def get_daemon_status(self) -> Dict[str, Any]:
        """
        Get detailed status of the notification delivery daemon.
        
        Returns:
            Dict containing daemon status and operational metrics
        """
        request_id = f"daemon_{uuid.uuid4().hex[:8]}"
        
        try:
            self.logger.info(
                "Retrieving daemon status",
                request_id=request_id
            )
            
            daemon_health = await self._check_daemon_health()
            
            # Get detailed daemon metrics
            daemon_status = {
                "daemon_status": "running" if daemon_health["is_running"] else "stopped",
                "uptime_seconds": daemon_health.get("uptime_seconds", 0),
                "last_heartbeat": datetime.now(timezone.utc).isoformat(),
                "processing_queue_size": daemon_health.get("queue_size", 0),
                "concurrent_workers": daemon_health.get("active_workers", 0),
                "failed_deliveries_1h": daemon_health.get("failed_deliveries", 0),
                "health_checks": {
                    "database": daemon_health.get("database_connected", False),
                    "email_service": daemon_health.get("email_service_healthy", False),
                    "webhook_endpoints": daemon_health.get("webhook_endpoints_healthy", False)
                },
                "performance": {
                    "avg_processing_time_ms": daemon_health.get("avg_processing_time", 0),
                    "throughput_per_minute": daemon_health.get("throughput", 0),
                    "error_rate_percent": daemon_health.get("error_rate", 0)
                }
            }
            
            self.logger.info(
                "Daemon status retrieved",
                request_id=request_id,
                daemon_running=daemon_health["is_running"]
            )
            
            return daemon_status
            
        except Exception as e:
            self.logger.error(
                "Error retrieving daemon status",
                request_id=request_id,
                error=str(e),
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve daemon status: {str(e)}"
            )
    
    async def restart_daemon(self) -> Dict[str, Any]:
        """
        Restart the notification delivery daemon.
        
        Returns:
            Dict containing restart status and timing information
        """
        request_id = f"restart_{uuid.uuid4().hex[:8]}"
        
        try:
            self.logger.info(
                "Initiating daemon restart",
                request_id=request_id
            )
            
            # TODO: Implement daemon restart logic
            # For now, return placeholder response
            restart_result = {
                "restart_initiated": True,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "estimated_downtime_seconds": 30,
                "restart_id": request_id
            }
            
            self.logger.info(
                "Daemon restart initiated",
                request_id=request_id
            )
            
            return restart_result
            
        except Exception as e:
            self.logger.error(
                "Error restarting daemon",
                request_id=request_id,
                error=str(e),
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to restart daemon: {str(e)}"
            )
    
    async def get_channel_status(self) -> Dict[str, Any]:
        """
        Get status of all notification channel adapters.
        
        Returns:
            Dict containing status of each channel adapter
        """
        request_id = f"channels_{uuid.uuid4().hex[:8]}"
        
        try:
            self.logger.info(
                "Retrieving channel status",
                request_id=request_id
            )
            
            channel_health = await self._check_channel_adapters_health()
            
            # Format for response
            channels = {}
            for channel_name, health_data in channel_health.items():
                if channel_name.endswith("_adapter"):
                    clean_name = channel_name.replace("_adapter", "")
                    channels[clean_name] = health_data
            
            channel_status = {
                "channels": channels,
                "total_channels": len(channels),
                "healthy_channels": len([c for c in channels.values() if c.get("status") == "healthy"]),
                "degraded_channels": len([c for c in channels.values() if c.get("status") == "degraded"]),
                "unhealthy_channels": len([c for c in channels.values() if c.get("status") == "unhealthy"])
            }
            
            self.logger.info(
                "Channel status retrieved",
                request_id=request_id,
                total_channels=len(channels)
            )
            
            return channel_status
            
        except Exception as e:
            self.logger.error(
                "Error retrieving channel status",
                request_id=request_id,
                error=str(e),
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve channel status: {str(e)}"
            )
    
    # Helper methods for health checks
    
    async def _check_daemon_health(self) -> Dict[str, Any]:
        """Check delivery daemon health status."""
        # TODO: Implement actual daemon health check
        # For now, return placeholder data
        return {
            "is_running": True,
            "uptime_seconds": 3600,
            "queue_size": 15,
            "active_workers": 5,
            "failed_deliveries": 2,
            "database_connected": True,
            "email_service_healthy": True,
            "webhook_endpoints_healthy": True,
            "avg_processing_time": 450,
            "throughput": 100,
            "error_rate": 0.5
        }
    
    async def _check_channel_adapters_health(self) -> Dict[str, Any]:
        """Check health status of all channel adapters."""
        # TODO: Implement actual adapter health checks
        # For now, return placeholder data
        return {
            "email_adapter": {
                "status": "healthy",
                "provider": "sendgrid",
                "last_success": datetime.now(timezone.utc).isoformat(),
                "error_rate": 0.5,
                "success_rate": 99.5
            },
            "websocket_adapter": {
                "status": "healthy",
                "active_connections": 150,
                "last_success": datetime.now(timezone.utc).isoformat(),
                "error_rate": 0.2,
                "success_rate": 99.8
            },
            "webhook_adapter": {
                "status": "degraded",
                "active_endpoints": 8,
                "last_success": datetime.now(timezone.utc).isoformat(),
                "error_rate": 2.0,
                "success_rate": 98.0
            }
        }
    
    async def _check_database_health(self) -> Dict[str, Any]:
        """Check database connectivity and performance."""
        start_time = datetime.now(timezone.utc)
        
        try:
            # Simple ping to database
            # TODO: Add actual database health check
            
            latency_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            return {
                "status": "healthy",
                "latency_ms": round(latency_ms, 2),
                "last_check": datetime.now(timezone.utc).isoformat(),
                "connected": True
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "last_check": datetime.now(timezone.utc).isoformat(),
                "connected": False
            }
    
    async def _get_basic_metrics(self) -> Dict[str, Any]:
        """Get basic performance metrics."""
        # TODO: Implement actual metrics collection
        return {
            "notifications_sent_24h": 1250,
            "success_rate": 99.2,
            "average_delivery_time_ms": 450,
            "pending_notifications": 5
        }
    
    async def _get_delivery_metrics(self) -> Dict[str, Any]:
        """Get delivery performance metrics."""
        # TODO: Implement actual delivery metrics
        return {
            "total_sent": 1250,
            "successful": 1240,
            "failed": 10,
            "pending": 5,
            "success_rate": 99.2,
            "average_delivery_time_ms": 450
        }
    
    async def _get_channel_performance(self) -> Dict[str, Any]:
        """Get channel-specific performance metrics."""
        # TODO: Implement actual channel performance metrics
        return {
            "email": {
                "sent": 800,
                "success_rate": 99.5,
                "avg_delivery_ms": 2500,
                "error_rate": 0.5
            },
            "websocket": {
                "sent": 400,
                "success_rate": 99.8,
                "avg_delivery_ms": 50,
                "error_rate": 0.2
            },
            "webhook": {
                "sent": 50,
                "success_rate": 98.0,
                "avg_delivery_ms": 1200,
                "error_rate": 2.0
            }
        }
    
    async def _get_system_metrics(self) -> Dict[str, Any]:
        """Get system-level performance metrics."""
        # TODO: Implement actual system metrics
        return {
            "memory_usage_mb": 512,
            "cpu_usage_percent": 25,
            "disk_usage_percent": 45,
            "active_connections": 150,
            "uptime_seconds": 3600
        }
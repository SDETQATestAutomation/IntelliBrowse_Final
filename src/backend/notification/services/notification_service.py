"""
Notification Module - Core Notification Service

Main notification service interface implementing comprehensive notification
management with async operations, user preferences, and delivery tracking.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..models import (
    NotificationModel, UserNotificationPreferencesModel, NotificationDeliveryHistory,
    NotificationStatus, NotificationChannel, NotificationTypeCategory
)
from ..schemas import (
    SendNotificationRequestSchema, NotificationResponseSchema,
    NotificationStatusResponseSchema, NotificationListResponseSchema,
    UserPreferencesResponseSchema, UpdatePreferencesRequestSchema,
    NotificationHistoryQuerySchema, DeliveryHistoryListResponseSchema
)
from ...config.logging import get_logger
from .channel_adapter_base import NotificationChannelAdapter, NotificationPayload

logger = get_logger(__name__)


class NotificationService:
    """
    Core notification service implementing multi-channel delivery orchestration.
    
    Provides comprehensive notification management including:
    - Asynchronous notification dispatch
    - User preference management
    - Delivery status tracking
    - Channel adapter orchestration
    - Audit trail management
    """
    
    def __init__(
        self,
        database: AsyncIOMotorDatabase,
        channel_adapters: Dict[str, NotificationChannelAdapter]
    ):
        """
        Initialize notification service with dependencies.
        
        Args:
            database: MongoDB database instance
            channel_adapters: Dictionary of available channel adapters
        """
        self.database = database
        self.channel_adapters = channel_adapters
        self.logger = logger.bind(service="NotificationService")
        
        # Collections
        self.notifications_collection = self.database.notifications
        self.preferences_collection = self.database.user_notification_preferences
        self.history_collection = self.database.notification_delivery_history
    
    async def send_notification_async(
        self,
        request: SendNotificationRequestSchema,
        user_id: str
    ) -> NotificationResponseSchema:
        """
        Send notification asynchronously with multi-channel support.
        
        Args:
            request: Notification send request
            user_id: ID of user creating the notification
            
        Returns:
            NotificationResponseSchema: Notification creation response
            
        Raises:
            ValueError: If request validation fails
            RuntimeError: If notification creation fails
        """
        start_time = datetime.now(timezone.utc)
        notification_id = f"ntfy_{uuid.uuid4().hex[:12]}"
        
        try:
            self.logger.info(
                "Creating notification",
                notification_id=notification_id,
                user_id=user_id,
                type=request.type,
                channels=request.channels,
                recipient_count=len(request.recipients)
            )
            
            # Create notification model
            notification = NotificationModel(
                notification_id=notification_id,
                type=request.type,
                title=request.title,
                content=request.content.model_dump(),
                recipients=[r.model_dump() for r in request.recipients],
                channels=request.channels,
                priority=request.priority,
                scheduled_at=request.scheduled_at,
                expires_at=request.expires_at,
                source_service="notification_api",
                correlation_id=request.correlation_id,
                context=request.context,
                created_by=user_id
            )
            
            # Store notification in database
            await self.notifications_collection.insert_one(notification.to_mongo())
            
            # Initialize delivery history for each recipient
            for recipient in request.recipients:
                history = NotificationDeliveryHistory(
                    notification_id=notification_id,
                    user_id=recipient.user_id,
                    notification_type=request.type.value,
                    priority=request.priority.value,
                    source_service="notification_api"
                )
                await self.history_collection.insert_one(history.to_mongo())
            
            # Queue for async delivery if immediate
            if request.scheduled_at is None:
                await self._queue_for_delivery(notification)
            
            creation_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            self.logger.info(
                "Notification created successfully",
                notification_id=notification_id,
                creation_time_ms=creation_time
            )
            
            return NotificationResponseSchema(
                notification_id=notification_id,
                status=NotificationStatus.PENDING,
                created_at=notification.created_at,
                scheduled_at=request.scheduled_at,
                channels=request.channels,
                recipient_count=len(request.recipients),
                estimated_delivery_time=self._calculate_estimated_delivery_time(
                    request.channels, request.scheduled_at
                )
            )
            
        except Exception as e:
            self.logger.error(
                "Notification creation failed",
                notification_id=notification_id,
                error=str(e),
                exc_info=True
            )
            raise RuntimeError(f"Failed to create notification: {str(e)}") from e
    
    async def get_delivery_status_async(
        self,
        notification_id: str,
        user_id: str
    ) -> NotificationStatusResponseSchema:
        """
        Get delivery status for a specific notification.
        
        Args:
            notification_id: Notification identifier
            user_id: Requesting user ID (for access control)
            
        Returns:
            NotificationStatusResponseSchema: Current delivery status
            
        Raises:
            ValueError: If notification not found or access denied
        """
        try:
            # Get notification from database
            notification_doc = await self.notifications_collection.find_one({
                "notification_id": notification_id
            })
            
            if not notification_doc:
                raise ValueError(f"Notification {notification_id} not found")
            
            notification = NotificationModel.from_mongo(notification_doc)
            if not notification:
                raise ValueError(f"Invalid notification data for {notification_id}")
            
            # Check access permissions (simplified)
            if notification.created_by != user_id:
                # Check if user is in recipients
                recipient_user_ids = [r.user_id for r in notification.recipients]
                if user_id not in recipient_user_ids:
                    raise ValueError("Access denied to notification")
            
            # Get delivery history for successful channels
            history_docs = await self.history_collection.find({
                "notification_id": notification_id
            }).to_list(length=100)
            
            successful_channels = []
            for history_doc in history_docs:
                history = NotificationDeliveryHistory.from_mongo(history_doc)
                if history and history.successful_channels:
                    successful_channels.extend(history.successful_channels)
            
            return NotificationStatusResponseSchema(
                notification_id=notification_id,
                status=notification.status,
                created_at=notification.created_at,
                sent_at=notification.sent_at,
                delivered_at=notification.delivered_at,
                failed_at=notification.failed_at,
                channels=notification.channels,
                successful_channels=list(set(successful_channels)),
                retry_count=notification.retry_metadata.current_attempt,
                error_details=notification.error_details
            )
            
        except ValueError:
            raise
        except Exception as e:
            self.logger.error(
                "Failed to retrieve notification status",
                notification_id=notification_id,
                error=str(e),
                exc_info=True
            )
            raise RuntimeError(f"Failed to get notification status: {str(e)}") from e
    
    async def update_user_preferences_async(
        self,
        user_id: str,
        request: UpdatePreferencesRequestSchema
    ) -> UserPreferencesResponseSchema:
        """
        Update user notification preferences.
        
        Args:
            user_id: User ID to update preferences for
            request: Preference update request
            
        Returns:
            UserPreferencesResponseSchema: Updated preferences
            
        Raises:
            RuntimeError: If preferences update fails
        """
        try:
            self.logger.info("Updating user preferences", user_id=user_id)
            
            # Get existing preferences or create new
            existing_doc = await self.preferences_collection.find_one({
                "user_id": user_id
            })
            
            if existing_doc:
                preferences = UserNotificationPreferencesModel.from_mongo(existing_doc)
                if not preferences:
                    raise RuntimeError("Invalid existing preferences data")
            else:
                # Create new preferences with defaults
                preferences = UserNotificationPreferencesModel(
                    user_id=user_id,
                    last_updated_by=user_id
                )
            
            # Update fields from request
            if request.global_enabled is not None:
                preferences.global_enabled = request.global_enabled
            
            if request.default_channels is not None:
                preferences.default_channels = request.default_channels
            
            if request.digest_enabled is not None:
                preferences.digest_enabled = request.digest_enabled
            
            if request.digest_frequency is not None:
                preferences.digest_frequency = request.digest_frequency
            
            if request.deduplication_window_minutes is not None:
                preferences.deduplication_window_minutes = request.deduplication_window_minutes
            
            # Update metadata
            preferences.last_updated_by = user_id
            preferences.update_timestamp()
            
            # Save to database
            await self.preferences_collection.replace_one(
                {"user_id": user_id},
                preferences.to_mongo(),
                upsert=True
            )
            
            self.logger.info("User preferences updated successfully", user_id=user_id)
            
            # Convert to response schema
            return self._convert_preferences_to_response(preferences)
            
        except Exception as e:
            self.logger.error(
                "Failed to update user preferences",
                user_id=user_id,
                error=str(e),
                exc_info=True
            )
            raise RuntimeError(f"Failed to update preferences: {str(e)}") from e
    
    async def get_user_history_async(
        self,
        user_id: str,
        query: NotificationHistoryQuerySchema
    ) -> DeliveryHistoryListResponseSchema:
        """
        Get notification delivery history for a user.
        
        Args:
            user_id: User ID to get history for
            query: History query parameters
            
        Returns:
            DeliveryHistoryListResponseSchema: Paginated history results
        """
        try:
            # Build query filter
            filter_query = {"user_id": user_id}
            
            if query.notification_type:
                filter_query["notification_type"] = query.notification_type.value
            
            if query.channel:
                filter_query["channels_attempted"] = query.channel.value
            
            if query.status:
                filter_query["current_status"] = query.status.value
            
            if query.start_date or query.end_date:
                date_filter = {}
                if query.start_date:
                    date_filter["$gte"] = query.start_date
                if query.end_date:
                    date_filter["$lte"] = query.end_date
                filter_query["created_at"] = date_filter
            
            # Get total count
            total_count = await self.history_collection.count_documents(filter_query)
            
            # Calculate pagination
            skip = (query.page - 1) * query.page_size
            total_pages = (total_count + query.page_size - 1) // query.page_size
            
            # Get paginated results
            cursor = self.history_collection.find(filter_query) \
                .sort("created_at", -1) \
                .skip(skip) \
                .limit(query.page_size)
            
            history_docs = await cursor.to_list(length=query.page_size)
            
            # Convert to response format
            deliveries = []
            for doc in history_docs:
                history = NotificationDeliveryHistory.from_mongo(doc)
                if history:
                    delivery_response = self._convert_history_to_response(
                        history, query.include_attempts, query.include_metrics
                    )
                    deliveries.append(delivery_response)
            
            return DeliveryHistoryListResponseSchema(
                deliveries=deliveries,
                total_count=total_count,
                page=query.page,
                page_size=query.page_size,
                total_pages=total_pages,
                has_next=query.page < total_pages,
                has_previous=query.page > 1
            )
            
        except Exception as e:
            self.logger.error(
                "Failed to retrieve user history",
                user_id=user_id,
                error=str(e),
                exc_info=True
            )
            raise RuntimeError(f"Failed to get user history: {str(e)}") from e
    
    async def _queue_for_delivery(self, notification: NotificationModel) -> None:
        """Queue notification for asynchronous delivery."""
        notification.status = NotificationStatus.PROCESSING
        await self.notifications_collection.update_one(
            {"notification_id": notification.notification_id},
            {"$set": {"status": notification.status.value}}
        )
        
        self.logger.info(
            "Notification queued for delivery",
            notification_id=notification.notification_id
        )
    
    def _calculate_estimated_delivery_time(
        self,
        channels: List[NotificationChannel],
        scheduled_at: Optional[datetime]
    ) -> str:
        """Calculate estimated delivery time based on channels and scheduling."""
        if scheduled_at:
            return "scheduled"
        
        # Simple heuristic based on channel types
        if NotificationChannel.WEBSOCKET in channels:
            return "immediate"
        elif NotificationChannel.EMAIL in channels:
            return "within 1 minute"
        elif NotificationChannel.WEBHOOK in channels:
            return "within 30 seconds"
        else:
            return "within 5 minutes"
    
    def _convert_preferences_to_response(
        self, 
        preferences: UserNotificationPreferencesModel
    ) -> UserPreferencesResponseSchema:
        """Convert preferences model to response schema."""
        from ..schemas.preference_schemas import (
            ChannelPreferenceResponseSchema, TypePreferenceResponseSchema,
            QuietHoursConfigResponseSchema, EscalationRuleResponseSchema
        )
        
        return UserPreferencesResponseSchema(
            user_id=preferences.user_id,
            global_enabled=preferences.global_enabled,
            channel_preferences=[
                ChannelPreferenceResponseSchema(
                    channel=cp.channel,
                    enabled=cp.enabled,
                    priority=cp.priority,
                    rate_limit=cp.rate_limit,
                    settings=cp.settings
                ) for cp in preferences.channel_preferences
            ],
            type_preferences=[
                TypePreferenceResponseSchema(
                    type=tp.type,
                    enabled=tp.enabled,
                    channels=tp.channels,
                    priority_threshold=tp.priority_threshold,
                    escalation_enabled=tp.escalation_enabled
                ) for tp in preferences.type_preferences
            ],
            quiet_hours=QuietHoursConfigResponseSchema(
                enabled=preferences.quiet_hours.enabled,
                start_time=preferences.quiet_hours.start_time.isoformat() if preferences.quiet_hours.start_time else None,
                end_time=preferences.quiet_hours.end_time.isoformat() if preferences.quiet_hours.end_time else None,
                timezone=preferences.quiet_hours.timezone,
                emergency_override=preferences.quiet_hours.emergency_override,
                exempt_types=preferences.quiet_hours.exempt_types
            ),
            escalation_rules=[
                EscalationRuleResponseSchema(
                    name=er.name,
                    delay_minutes=er.delay_minutes,
                    max_escalations=er.max_escalations,
                    escalation_channels=er.escalation_channels,
                    escalation_recipients=er.escalation_recipients,
                    trigger_types=er.trigger_types,
                    minimum_priority=er.minimum_priority
                ) for er in preferences.escalation_rules
            ],
            default_channels=preferences.default_channels,
            digest_enabled=preferences.digest_enabled,
            digest_frequency=preferences.digest_frequency,
            digest_time=preferences.digest_time.isoformat() if preferences.digest_time else None,
            deduplication_window_minutes=preferences.deduplication_window_minutes,
            created_at=preferences.created_at.isoformat(),
            updated_at=preferences.updated_at.isoformat() if preferences.updated_at else None,
            last_updated_by=preferences.last_updated_by
        )
    
    def _convert_history_to_response(
        self,
        history: NotificationDeliveryHistory,
        include_attempts: bool = False,
        include_metrics: bool = False
    ):
        """Convert history model to response schema."""
        from ..schemas.history_schemas import (
            DeliveryHistoryResponseSchema, DeliveryAttemptResponseSchema,
            DeliveryMetricsResponseSchema
        )
        
        # Convert delivery attempts if requested
        delivery_attempts = None
        if include_attempts and history.delivery_attempts:
            delivery_attempts = [
                DeliveryAttemptResponseSchema(
                    attempt_number=attempt.attempt_number,
                    channel=attempt.channel,
                    status=attempt.status,
                    started_at=attempt.started_at.isoformat(),
                    completed_at=attempt.completed_at.isoformat() if attempt.completed_at else None,
                    duration_ms=attempt.duration_ms,
                    provider=attempt.provider,
                    provider_message_id=attempt.provider_message_id,
                    error_code=attempt.error_code,
                    error_message=attempt.error_message,
                    retry_after_seconds=attempt.retry_after_seconds,
                    recipient_email=attempt.recipient_email,
                    webhook_url=attempt.webhook_url,
                    websocket_session_id=attempt.websocket_session_id
                ) for attempt in history.delivery_attempts
            ]
        
        # Convert metrics if requested
        metrics = None
        if include_metrics:
            metrics = DeliveryMetricsResponseSchema(
                total_attempts=history.metrics.total_attempts,
                successful_deliveries=history.metrics.successful_deliveries,
                failed_attempts=history.metrics.failed_attempts,
                average_delivery_time_ms=history.metrics.average_delivery_time_ms,
                max_delivery_time_ms=history.metrics.max_delivery_time_ms,
                min_delivery_time_ms=history.metrics.min_delivery_time_ms,
                success_rate=history.metrics.calculate_success_rate(),
                channel_success_rates=history.metrics.channel_success_rates,
                common_errors=history.metrics.common_errors
            )
        
        return DeliveryHistoryResponseSchema(
            notification_id=history.notification_id,
            user_id=history.user_id,
            notification_type=history.notification_type,
            priority=history.priority,
            current_status=history.current_status,
            first_attempt_at=history.first_attempt_at.isoformat() if history.first_attempt_at else None,
            last_attempt_at=history.last_attempt_at.isoformat() if history.last_attempt_at else None,
            final_delivery_at=history.final_delivery_at.isoformat() if history.final_delivery_at else None,
            total_delivery_time_ms=history.total_delivery_time_ms,
            channels_attempted=history.channels_attempted,
            successful_channels=history.successful_channels,
            delivery_attempts=delivery_attempts,
            metrics=metrics,
            source_service=history.source_service,
            escalated=history.escalated,
            manual_intervention=history.manual_intervention,
            notes=history.notes,
            created_at=history.created_at.isoformat(),
            updated_at=history.updated_at.isoformat() if history.updated_at else None
        ) 
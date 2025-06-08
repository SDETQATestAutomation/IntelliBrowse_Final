"""
Notification Module - Notification Dispatcher Service

Central orchestration service for multi-channel notification delivery.
Handles channel routing, user preference application, and delivery coordination.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..models import (
    NotificationModel, UserNotificationPreferencesModel, NotificationDeliveryHistory,
    NotificationStatus, NotificationChannel, NotificationTypeCategory, DeliveryStatus
)
from ..schemas import (
    SendNotificationRequestSchema, NotificationResponseSchema
)
from .channel_adapter_base import (
    NotificationChannelAdapter, NotificationPayload, NotificationResult,
    NotificationResultStatus
)
from ...config.logging import get_logger

logger = get_logger(__name__)


class NotificationDispatcherService:
    """
    Central notification dispatcher implementing multi-channel delivery orchestration.
    
    Responsible for:
    - Channel priority determination based on user preferences
    - Delegation to appropriate channel adapters
    - Delivery status tracking and history updates
    - Error handling and retry coordination
    - Async and confirmed delivery modes
    """
    
    def __init__(
        self,
        database: AsyncIOMotorDatabase,
        channel_adapters: Dict[str, NotificationChannelAdapter]
    ):
        """
        Initialize notification dispatcher.
        
        Args:
            database: MongoDB database instance
            channel_adapters: Dictionary mapping channel names to adapter instances
        """
        self.database = database
        self.channel_adapters = channel_adapters
        self.logger = logger.bind(service="NotificationDispatcherService")
        
        # Collections
        self.notifications_collection = self.database.notifications
        self.preferences_collection = self.database.user_notification_preferences
        self.history_collection = self.database.notification_delivery_history
    
    async def dispatch_notification_async(
        self,
        notification: NotificationModel,
        delivery_mode: str = "fire_and_forget"
    ) -> Dict[str, NotificationResult]:
        """
        Dispatch notification through appropriate channels based on user preferences.
        
        Args:
            notification: Notification model to dispatch
            delivery_mode: "fire_and_forget" or "confirmed_delivery"
            
        Returns:
            Dict mapping channel names to delivery results
        """
        dispatch_id = f"dispatch_{uuid.uuid4().hex[:8]}"
        start_time = datetime.now(timezone.utc)
        
        try:
            self.logger.info(
                "Starting notification dispatch",
                dispatch_id=dispatch_id,
                notification_id=notification.notification_id,
                delivery_mode=delivery_mode,
                recipient_count=len(notification.recipients)
            )
            
            # Prepare delivery results tracking
            all_results = {}
            
            # Process each recipient
            for recipient in notification.recipients:
                recipient_results = await self._dispatch_to_recipient(
                    notification, recipient, delivery_mode, dispatch_id
                )
                
                # Merge results
                for channel, result in recipient_results.items():
                    if channel not in all_results:
                        all_results[channel] = []
                    all_results[channel].append(result)
            
            # Update notification status based on results
            await self._update_notification_status(notification, all_results)
            
            # Calculate total dispatch time
            dispatch_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            self.logger.info(
                "Notification dispatch completed",
                dispatch_id=dispatch_id,
                notification_id=notification.notification_id,
                total_channels=len(all_results),
                dispatch_time_ms=dispatch_time
            )
            
            return all_results
            
        except Exception as e:
            self.logger.error(
                "Notification dispatch failed",
                dispatch_id=dispatch_id,
                notification_id=notification.notification_id,
                error=str(e),
                exc_info=True
            )
            raise RuntimeError(f"Dispatch failed: {str(e)}") from e
    
    async def _dispatch_to_recipient(
        self,
        notification: NotificationModel,
        recipient: Any,
        delivery_mode: str,
        dispatch_id: str
    ) -> Dict[str, NotificationResult]:
        """
        Dispatch notification to a specific recipient based on their preferences.
        
        Args:
            notification: Notification to dispatch
            recipient: Recipient information
            delivery_mode: Delivery mode for this dispatch
            dispatch_id: Unique dispatch identifier
            
        Returns:
            Dict mapping channel names to delivery results for this recipient
        """
        recipient_id = recipient.user_id if hasattr(recipient, 'user_id') else recipient.get('user_id')
        
        try:
            self.logger.debug(
                "Processing recipient dispatch",
                dispatch_id=dispatch_id,
                notification_id=notification.notification_id,
                recipient_id=recipient_id
            )
            
            # Get user preferences
            user_preferences = await self._get_user_preferences(recipient_id)
            
            # Determine channels to use for this recipient
            target_channels = await self._determine_target_channels(
                notification, recipient, user_preferences
            )
            
            if not target_channels:
                self.logger.warning(
                    "No valid channels found for recipient",
                    dispatch_id=dispatch_id,
                    notification_id=notification.notification_id,
                    recipient_id=recipient_id
                )
                return {}
            
            # Create delivery history record
            history = await self._create_delivery_history(
                notification, recipient_id, target_channels
            )
            
            # Dispatch to each channel
            results = {}
            
            if delivery_mode == "fire_and_forget":
                # Async dispatch to all channels simultaneously
                tasks = []
                for channel in target_channels:
                    task = self._dispatch_to_channel(
                        notification, recipient, channel, history, dispatch_id
                    )
                    tasks.append(task)
                
                # Wait for all dispatches to complete
                channel_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results
                for i, result in enumerate(channel_results):
                    channel = target_channels[i]
                    if isinstance(result, Exception):
                        self.logger.error(
                            "Channel dispatch failed",
                            dispatch_id=dispatch_id,
                            channel=channel.value,
                            error=str(result)
                        )
                        results[channel.value] = NotificationResult(
                            status=NotificationResultStatus.FAILURE,
                            success=False,
                            error_code="DISPATCH_ERROR",
                            error_message=str(result)
                        )
                    else:
                        results[channel.value] = result
                        
            else:  # confirmed_delivery
                # Sequential dispatch with confirmation
                for channel in target_channels:
                    result = await self._dispatch_to_channel(
                        notification, recipient, channel, history, dispatch_id
                    )
                    results[channel.value] = result
                    
                    # Stop on first successful delivery for confirmed mode
                    if result.success:
                        self.logger.info(
                            "Confirmed delivery successful",
                            dispatch_id=dispatch_id,
                            channel=channel.value,
                            notification_id=notification.notification_id
                        )
                        break
            
            # Update delivery history with results
            await self._update_delivery_history(history, results)
            
            return results
            
        except Exception as e:
            self.logger.error(
                "Recipient dispatch failed",
                dispatch_id=dispatch_id,
                recipient_id=recipient_id,
                error=str(e),
                exc_info=True
            )
            raise
    
    async def _dispatch_to_channel(
        self,
        notification: NotificationModel,
        recipient: Any,
        channel: NotificationChannel,
        history: NotificationDeliveryHistory,
        dispatch_id: str
    ) -> NotificationResult:
        """
        Dispatch notification to a specific channel.
        
        Args:
            notification: Notification to send
            recipient: Recipient information
            channel: Target channel
            history: Delivery history record
            dispatch_id: Dispatch identifier
            
        Returns:
            NotificationResult from the channel adapter
        """
        channel_name = channel.value
        
        try:
            self.logger.debug(
                "Dispatching to channel",
                dispatch_id=dispatch_id,
                notification_id=notification.notification_id,
                channel=channel_name
            )
            
            # Get channel adapter
            adapter = self.channel_adapters.get(channel_name)
            if not adapter:
                error_msg = f"No adapter found for channel: {channel_name}"
                self.logger.error(error_msg, dispatch_id=dispatch_id)
                return NotificationResult(
                    status=NotificationResultStatus.CHANNEL_UNAVAILABLE,
                    success=False,
                    error_code="NO_ADAPTER",
                    error_message=error_msg
                )
            
            # Check if adapter is enabled
            if not adapter.is_enabled():
                error_msg = f"Channel adapter disabled: {channel_name}"
                self.logger.warning(error_msg, dispatch_id=dispatch_id)
                return NotificationResult(
                    status=NotificationResultStatus.CHANNEL_UNAVAILABLE,
                    success=False,
                    error_code="ADAPTER_DISABLED",
                    error_message=error_msg
                )
            
            # Create notification payload
            payload = await self._create_notification_payload(notification, recipient, channel)
            
            # Validate recipient for this channel
            recipient_data = await self._extract_recipient_data(recipient, channel)
            if not await adapter.validate_recipient(recipient_data):
                error_msg = f"Invalid recipient data for channel: {channel_name}"
                self.logger.warning(error_msg, dispatch_id=dispatch_id)
                return NotificationResult(
                    status=NotificationResultStatus.INVALID_RECIPIENT,
                    success=False,
                    error_code="INVALID_RECIPIENT",
                    error_message=error_msg
                )
            
            # Record delivery attempt start
            attempt = history.add_delivery_attempt(
                channel=channel,
                started_at=datetime.now(timezone.utc)
            )
            
            # Dispatch through adapter
            result = await adapter.send(payload)
            
            # Update attempt with result
            attempt.completed_at = datetime.now(timezone.utc)
            attempt.status = DeliveryStatus.DELIVERED if result.success else DeliveryStatus.FAILED
            attempt.duration_ms = result.duration_ms
            attempt.provider = result.provider_name
            attempt.provider_message_id = result.provider_message_id
            attempt.error_code = result.error_code
            attempt.error_message = result.error_message
            
            self.logger.info(
                "Channel dispatch completed",
                dispatch_id=dispatch_id,
                notification_id=notification.notification_id,
                channel=channel_name,
                success=result.success,
                duration_ms=result.duration_ms
            )
            
            return result
            
        except Exception as e:
            self.logger.error(
                "Channel dispatch error",
                dispatch_id=dispatch_id,
                channel=channel_name,
                error=str(e),
                exc_info=True
            )
            
            # Create error result
            result = NotificationResult(
                status=NotificationResultStatus.FAILURE,
                success=False,
                error_code="DISPATCH_EXCEPTION",
                error_message=str(e)
            )
            result.mark_completed(success=False)
            return result
    
    async def _get_user_preferences(
        self, 
        user_id: str
    ) -> Optional[UserNotificationPreferencesModel]:
        """Get user notification preferences from database."""
        try:
            preferences_doc = await self.preferences_collection.find_one({
                "user_id": user_id
            })
            
            if preferences_doc:
                return UserNotificationPreferencesModel.from_mongo(preferences_doc)
            
            return None
            
        except Exception as e:
            self.logger.error(
                "Failed to get user preferences",
                user_id=user_id,
                error=str(e)
            )
            return None
    
    async def _determine_target_channels(
        self,
        notification: NotificationModel,
        recipient: Any,
        user_preferences: Optional[UserNotificationPreferencesModel]
    ) -> List[NotificationChannel]:
        """
        Determine target channels for notification based on preferences and availability.
        
        Args:
            notification: Notification to send
            recipient: Recipient information
            user_preferences: User's notification preferences
            
        Returns:
            List of channels to attempt delivery through, in priority order
        """
        # Start with notification's specified channels
        available_channels = notification.channels.copy()
        
        # If user preferences exist, apply filtering and priority
        if user_preferences and user_preferences.global_enabled:
            # Check if user has disabled notifications globally
            if not user_preferences.global_enabled:
                return []
            
            # Apply type-specific preferences
            type_preferences = user_preferences.get_type_preferences(notification.type)
            if type_preferences and not type_preferences.enabled:
                return []
            
            # Apply channel preferences and priority ordering
            if type_preferences and type_preferences.channels:
                # Use type-specific channels if defined
                available_channels = type_preferences.channels
            
            # Filter by user's enabled channels
            enabled_channels = []
            for channel in available_channels:
                channel_pref = user_preferences.get_channel_preference(channel)
                if channel_pref is None or channel_pref.enabled:
                    enabled_channels.append(channel)
            
            available_channels = enabled_channels
            
            # Sort by priority (lower number = higher priority)
            available_channels.sort(
                key=lambda ch: user_preferences.get_channel_priority(ch)
            )
        
        # Filter out channels without available adapters
        valid_channels = []
        for channel in available_channels:
            if channel.value in self.channel_adapters:
                adapter = self.channel_adapters[channel.value]
                if adapter.is_enabled():
                    valid_channels.append(channel)
        
        return valid_channels
    
    async def _create_delivery_history(
        self,
        notification: NotificationModel,
        recipient_id: str,
        target_channels: List[NotificationChannel]
    ) -> NotificationDeliveryHistory:
        """Create delivery history record for tracking."""
        history = NotificationDeliveryHistory(
            notification_id=notification.notification_id,
            user_id=recipient_id,
            notification_type=notification.type.value,
            priority=notification.priority.value,
            channels_attempted=[ch.value for ch in target_channels],
            source_service=notification.source_service
        )
        
        # Save to database
        await self.history_collection.insert_one(history.to_mongo())
        
        return history
    
    async def _create_notification_payload(
        self,
        notification: NotificationModel,
        recipient: Any,
        channel: NotificationChannel
    ) -> NotificationPayload:
        """Create notification payload for channel adapter."""
        recipient_id = recipient.user_id if hasattr(recipient, 'user_id') else recipient.get('user_id')
        recipient_email = recipient.email if hasattr(recipient, 'email') else recipient.get('email')
        recipient_name = recipient.name if hasattr(recipient, 'name') else recipient.get('name')
        
        return NotificationPayload(
            notification_id=notification.notification_id,
            type=notification.type.value,
            priority=notification.priority.value,
            title=notification.title,
            message=notification.content.get('message', ''),
            html_content=notification.content.get('html_content'),
            recipient_id=recipient_id,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            correlation_id=notification.correlation_id,
            source_service=notification.source_service,
            context=notification.context,
            scheduled_at=notification.scheduled_at,
            expires_at=notification.expires_at,
            created_at=notification.created_at
        )
    
    async def _extract_recipient_data(
        self,
        recipient: Any,
        channel: NotificationChannel
    ) -> Dict[str, Any]:
        """Extract recipient data relevant for channel validation."""
        data = {}
        
        if hasattr(recipient, 'user_id'):
            data['user_id'] = recipient.user_id
        elif isinstance(recipient, dict):
            data['user_id'] = recipient.get('user_id')
        
        if hasattr(recipient, 'email'):
            data['email'] = recipient.email
        elif isinstance(recipient, dict):
            data['email'] = recipient.get('email')
        
        if hasattr(recipient, 'name'):
            data['name'] = recipient.name
        elif isinstance(recipient, dict):
            data['name'] = recipient.get('name')
        
        # Add channel-specific data
        if channel == NotificationChannel.WEBHOOK:
            if hasattr(recipient, 'webhook_url'):
                data['webhook_url'] = recipient.webhook_url
            elif isinstance(recipient, dict):
                data['webhook_url'] = recipient.get('webhook_url')
        
        return data
    
    async def _update_delivery_history(
        self,
        history: NotificationDeliveryHistory,
        results: Dict[str, NotificationResult]
    ) -> None:
        """Update delivery history with dispatch results."""
        # Update successful channels
        successful_channels = [
            channel for channel, result in results.items() 
            if result.success
        ]
        history.successful_channels = successful_channels
        
        # Update overall status
        if successful_channels:
            history.current_status = DeliveryStatus.DELIVERED
            history.final_delivery_at = datetime.now(timezone.utc)
        else:
            history.current_status = DeliveryStatus.FAILED
        
        # Update timing
        if history.delivery_attempts:
            history.first_attempt_at = min(
                attempt.started_at for attempt in history.delivery_attempts
            )
            history.last_attempt_at = max(
                attempt.started_at for attempt in history.delivery_attempts
            )
        
        # Save updates
        await self.history_collection.update_one(
            {"notification_id": history.notification_id, "user_id": history.user_id},
            {"$set": history.to_mongo()}
        )
    
    async def _update_notification_status(
        self,
        notification: NotificationModel,
        all_results: Dict[str, List[NotificationResult]]
    ) -> None:
        """Update notification status based on delivery results."""
        # Determine overall success
        has_success = any(
            any(result.success for result in results)
            for results in all_results.values()
        )
        
        # Update notification status
        if has_success:
            notification.status = NotificationStatus.DELIVERED
            notification.delivered_at = datetime.now(timezone.utc)
        else:
            notification.status = NotificationStatus.FAILED
            notification.failed_at = datetime.now(timezone.utc)
        
        # Save updates
        await self.notifications_collection.update_one(
            {"notification_id": notification.notification_id},
            {"$set": {
                "status": notification.status.value,
                "delivered_at": notification.delivered_at,
                "failed_at": notification.failed_at
            }}
        ) 
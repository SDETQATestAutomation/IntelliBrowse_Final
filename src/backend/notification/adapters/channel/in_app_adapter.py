"""
IntelliBrowse Notification Engine - In-App Channel Adapter

This module implements the in-app notification delivery channel by storing
notifications in the database for display within the application interface,
providing immediate notification visibility and read status tracking.

Classes:
    - InAppAdapter: Database-based in-app notification adapter
    - InAppConfig: In-app notification configuration
    - NotificationDisplayManager: UI notification management

Author: IntelliBrowse Team
Created: Phase 5 - Background Tasks & Delivery Daemon Implementation
"""

import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from .base_adapter import (
    BaseChannelAdapter,
    ChannelConfig,
    ChannelType,
    DeliveryContext,
    AdapterCapabilities,
    DeliveryPriority
)
from ...services.delivery_task_service import DeliveryResult, DeliveryResultStatus

# Configure logging
logger = logging.getLogger(__name__)


class InAppConfig(ChannelConfig):
    """
    In-app notification configuration extending base channel config
    
    Provides configuration options for in-app notification display,
    retention policies, and user interface integration.
    """
    
    channel_type: ChannelType = Field(default=ChannelType.IN_APP, description="Channel type")
    
    # Display configuration
    max_notifications_per_user: int = Field(default=100, description="Maximum notifications per user")
    notification_retention_days: int = Field(default=30, description="Days to retain notifications")
    auto_mark_read_after_days: int = Field(default=7, description="Auto-mark as read after days")
    
    # Priority display settings
    high_priority_badge: bool = Field(default=True, description="Show badge for high priority notifications")
    critical_priority_popup: bool = Field(default=True, description="Show popup for critical notifications")
    
    # Content formatting
    max_preview_length: int = Field(default=150, description="Maximum preview text length")
    support_rich_content: bool = Field(default=True, description="Support rich HTML content")
    support_actions: bool = Field(default=True, description="Support notification actions")
    
    # Real-time features
    enable_real_time_updates: bool = Field(default=True, description="Enable real-time notification updates")
    websocket_enabled: bool = Field(default=True, description="Enable WebSocket notifications")
    
    # Grouping and categorization
    enable_grouping: bool = Field(default=True, description="Group similar notifications")
    enable_categories: bool = Field(default=True, description="Enable notification categories")


class NotificationDisplayManager:
    """
    Manages in-app notification display logic and formatting
    
    Handles notification formatting, grouping, filtering, and
    real-time update coordination for the user interface.
    """
    
    def __init__(self, config: InAppConfig, collection: Collection):
        """
        Initialize notification display manager
        
        Args:
            config: In-app configuration
            collection: MongoDB collection for in-app notifications
        """
        self.config = config
        self.collection = collection
        self.logger = logger.bind(component="NotificationDisplayManager")
    
    async def store_notification(
        self,
        context: DeliveryContext,
        formatted_content: Dict[str, Any]
    ) -> str:
        """
        Store notification in database for in-app display
        
        Args:
            context: Delivery context
            formatted_content: Formatted notification content
            
        Returns:
            Database document ID
        """
        try:
            # Create in-app notification document
            notification_doc = {
                "notification_id": context.notification_id,
                "user_id": context.user_id,
                "correlation_id": context.correlation_id,
                
                # Content
                "title": formatted_content.get("title"),
                "content": formatted_content.get("content"),
                "preview": formatted_content.get("preview"),
                "html_content": formatted_content.get("html_content"),
                
                # Display properties
                "priority": context.delivery_priority.value,
                "category": context.notification.metadata.get("category", "general"),
                "icon": formatted_content.get("icon"),
                "color": formatted_content.get("color"),
                
                # Actions
                "actions": formatted_content.get("actions", []),
                
                # Status tracking
                "status": "unread",
                "read_at": None,
                "dismissed_at": None,
                "clicked_at": None,
                
                # Metadata
                "created_at": datetime.now(timezone.utc),
                "expires_at": datetime.now(timezone.utc) + timedelta(days=self.config.notification_retention_days),
                "source": "notification_engine",
                "metadata": context.notification.metadata,
                
                # Grouping
                "group_key": self._calculate_group_key(context),
                "group_count": 1,
                "is_grouped": False
            }
            
            # Insert notification
            result = await self.collection.insert_one(notification_doc)
            
            # Handle grouping if enabled
            if self.config.enable_grouping:
                await self._handle_notification_grouping(context, notification_doc)
            
            # Cleanup old notifications if needed
            await self._cleanup_old_notifications(context.user_id)
            
            self.logger.info(
                "In-app notification stored successfully",
                notification_id=context.notification_id,
                user_id=context.user_id,
                doc_id=str(result.inserted_id)
            )
            
            return str(result.inserted_id)
            
        except PyMongoError as e:
            self.logger.error(
                "Database error storing in-app notification",
                notification_id=context.notification_id,
                user_id=context.user_id,
                error=str(e),
                exc_info=True
            )
            raise
        except Exception as e:
            self.logger.error(
                "Unexpected error storing in-app notification",
                notification_id=context.notification_id,
                user_id=context.user_id,
                error=str(e),
                exc_info=True
            )
            raise
    
    def _calculate_group_key(self, context: DeliveryContext) -> str:
        """Calculate grouping key for notification"""
        if not self.config.enable_grouping:
            return context.notification_id
        
        # Group by category and type
        category = context.notification.metadata.get("category", "general")
        notification_type = context.notification.metadata.get("type", "default")
        
        return f"{category}:{notification_type}"
    
    async def _handle_notification_grouping(
        self,
        context: DeliveryContext,
        notification_doc: Dict[str, Any]
    ):
        """Handle notification grouping logic"""
        try:
            group_key = notification_doc["group_key"]
            
            # Find existing notifications in the same group
            existing_query = {
                "user_id": context.user_id,
                "group_key": group_key,
                "status": {"$in": ["unread", "read"]},
                "_id": {"$ne": notification_doc.get("_id")}
            }
            
            existing_count = await self.collection.count_documents(existing_query)
            
            if existing_count > 0:
                # Update group count
                await self.collection.update_one(
                    {"_id": notification_doc["_id"]},
                    {
                        "$set": {
                            "group_count": existing_count + 1,
                            "is_grouped": True
                        }
                    }
                )
                
                # Mark older notifications in group as grouped
                await self.collection.update_many(
                    existing_query,
                    {"$set": {"is_grouped": True}}
                )
                
        except Exception as e:
            self.logger.warning(
                "Error handling notification grouping",
                group_key=notification_doc.get("group_key"),
                error=str(e)
            )
    
    async def _cleanup_old_notifications(self, user_id: str):
        """Clean up old notifications for user"""
        try:
            # Count current notifications for user
            current_count = await self.collection.count_documents({
                "user_id": user_id,
                "status": {"$in": ["unread", "read"]}
            })
            
            if current_count > self.config.max_notifications_per_user:
                # Remove oldest notifications exceeding limit
                excess_count = current_count - self.config.max_notifications_per_user
                
                # Find oldest notifications
                cursor = self.collection.find({
                    "user_id": user_id,
                    "status": {"$in": ["unread", "read"]}
                }).sort("created_at", 1).limit(excess_count)
                
                old_ids = [doc["_id"] async for doc in cursor]
                
                if old_ids:
                    await self.collection.delete_many({
                        "_id": {"$in": old_ids}
                    })
                    
                    self.logger.info(
                        "Cleaned up old in-app notifications",
                        user_id=user_id,
                        removed_count=len(old_ids)
                    )
            
            # Remove expired notifications
            await self.collection.delete_many({
                "user_id": user_id,
                "expires_at": {"$lt": datetime.now(timezone.utc)}
            })
            
        except Exception as e:
            self.logger.warning(
                "Error cleaning up old notifications",
                user_id=user_id,
                error=str(e)
            )
    
    def format_content_for_display(
        self,
        context: DeliveryContext
    ) -> Dict[str, Any]:
        """
        Format notification content for in-app display
        
        Args:
            context: Delivery context
            
        Returns:
            Formatted content for display
        """
        notification = context.notification
        user_context = context.user_context
        
        # Basic content
        title = notification.title
        content = notification.content
        
        # Create preview text
        preview = content[:self.config.max_preview_length]
        if len(content) > self.config.max_preview_length:
            preview += "..."
        
        # Determine display properties based on priority
        priority = context.delivery_priority
        
        display_props = self._get_priority_display_props(priority)
        
        # Format actions if supported
        actions = []
        if self.config.support_actions and notification.metadata.get("actions"):
            actions = self._format_notification_actions(notification.metadata["actions"])
        
        return {
            "title": title,
            "content": content,
            "preview": preview,
            "html_content": self._format_html_content(content, title) if self.config.support_rich_content else None,
            "icon": display_props["icon"],
            "color": display_props["color"],
            "actions": actions,
            "priority_badge": display_props["show_badge"],
            "requires_popup": display_props["show_popup"]
        }
    
    def _get_priority_display_props(self, priority: DeliveryPriority) -> Dict[str, Any]:
        """Get display properties based on priority"""
        priority_config = {
            DeliveryPriority.LOW: {
                "icon": "info",
                "color": "#6c757d",
                "show_badge": False,
                "show_popup": False
            },
            DeliveryPriority.MEDIUM: {
                "icon": "notification",
                "color": "#0d6efd",
                "show_badge": True,
                "show_popup": False
            },
            DeliveryPriority.HIGH: {
                "icon": "warning",
                "color": "#fd7e14",
                "show_badge": self.config.high_priority_badge,
                "show_popup": False
            },
            DeliveryPriority.CRITICAL: {
                "icon": "alert",
                "color": "#dc3545",
                "show_badge": True,
                "show_popup": self.config.critical_priority_popup
            }
        }
        
        return priority_config.get(priority, priority_config[DeliveryPriority.MEDIUM])
    
    def _format_notification_actions(self, actions_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format notification actions for display"""
        formatted_actions = []
        
        for action in actions_data:
            formatted_action = {
                "id": action.get("id"),
                "label": action.get("label"),
                "type": action.get("type", "button"),
                "url": action.get("url"),
                "method": action.get("method", "GET"),
                "confirm": action.get("confirm", False),
                "style": action.get("style", "secondary")
            }
            formatted_actions.append(formatted_action)
        
        return formatted_actions
    
    def _format_html_content(self, content: str, title: str) -> str:
        """Format content as HTML for rich display"""
        # Simple HTML formatting
        html_content = f"""
        <div class="notification-content">
            <h4 class="notification-title">{title}</h4>
            <div class="notification-body">
                {content.replace(chr(10), '<br>')}
            </div>
        </div>
        """
        return html_content.strip()


class InAppAdapter(BaseChannelAdapter):
    """
    In-app notification delivery adapter
    
    Delivers notifications by storing them in the database for display
    within the application interface with real-time update support.
    """
    
    def __init__(self, config: InAppConfig, collection: Collection):
        """
        Initialize in-app adapter
        
        Args:
            config: In-app configuration
            collection: MongoDB collection for in-app notifications
        """
        super().__init__(config)
        self.in_app_config = config
        self.collection = collection
        self.display_manager = NotificationDisplayManager(config, collection)
        
        # Adapter state
        self._capabilities = AdapterCapabilities(
            supports_rich_content=config.support_rich_content,
            supports_attachments=False,  # In-app doesn't support file attachments
            supports_templates=True,
            supports_scheduling=False,  # Handled by delivery daemon
            supports_batching=False,  # In-app notifications are individual
            supports_personalization=True,
            supports_delivery_tracking=True,  # Can track read/unread status
            supports_read_receipts=True,
            supports_engagement_tracking=True,
            max_content_length=10000,  # 10KB content limit
            max_subject_length=200,
            max_attachment_size_mb=None,
            supported_content_types=["text/plain", "text/html"],
            rate_limit_info={}
        )
    
    @property
    def channel_type(self) -> ChannelType:
        """Get channel type"""
        return ChannelType.IN_APP
    
    @property
    def capabilities(self) -> AdapterCapabilities:
        """Get adapter capabilities"""
        return self._capabilities
    
    async def initialize(self) -> bool:
        """
        Initialize in-app adapter and ensure database indices
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            self.logger.info("Initializing in-app adapter")
            
            # Create database indices for efficient querying
            await self._create_database_indices()
            
            # Test database connection
            await self.collection.find_one({}, {"_id": 1})
            
            self._is_initialized = True
            self.logger.info("In-app adapter initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(
                "In-app adapter initialization failed",
                error=str(e),
                exc_info=True
            )
            return False
    
    async def _create_database_indices(self):
        """Create database indices for efficient querying"""
        try:
            # Index for user notifications
            await self.collection.create_index([
                ("user_id", 1),
                ("created_at", -1)
            ])
            
            # Index for notification status
            await self.collection.create_index([
                ("user_id", 1),
                ("status", 1),
                ("created_at", -1)
            ])
            
            # Index for notification expiration
            await self.collection.create_index([
                ("expires_at", 1)
            ])
            
            # Index for grouping
            if self.in_app_config.enable_grouping:
                await self.collection.create_index([
                    ("user_id", 1),
                    ("group_key", 1),
                    ("created_at", -1)
                ])
            
            self.logger.info("Database indices created successfully")
            
        except Exception as e:
            self.logger.warning("Error creating database indices", error=str(e))
    
    async def send(self, context: DeliveryContext) -> DeliveryResult:
        """
        Send in-app notification by storing in database
        
        Args:
            context: Delivery context containing notification and user information
            
        Returns:
            Delivery result with status and metadata
        """
        start_time = time.time()
        
        try:
            # Validate delivery context
            is_valid, error_message = await self.validate_delivery_context(context)
            if not is_valid:
                processing_time = (time.time() - start_time) * 1000
                self._update_metrics(False)
                return self._create_delivery_result(
                    context=context,
                    status=DeliveryResultStatus.FAILED,
                    success=False,
                    processing_time_ms=processing_time,
                    error_message=error_message,
                    error_code="VALIDATION_ERROR"
                )
            
            # Format content for in-app display
            formatted_content = self.display_manager.format_content_for_display(context)
            
            # Store notification in database
            doc_id = await self.display_manager.store_notification(context, formatted_content)
            
            processing_time = (time.time() - start_time) * 1000
            self._update_metrics(True)
            
            self.logger.info(
                "In-app notification delivered successfully",
                notification_id=context.notification_id,
                user_id=context.user_id,
                doc_id=doc_id,
                processing_time_ms=processing_time
            )
            
            return self._create_delivery_result(
                context=context,
                status=DeliveryResultStatus.SUCCESS,
                success=True,
                processing_time_ms=processing_time,
                external_id=doc_id,
                response_data={
                    "doc_id": doc_id,
                    "user_id": context.user_id,
                    "priority": context.delivery_priority.value,
                    "requires_popup": formatted_content.get("requires_popup", False)
                }
            )
            
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            self._update_metrics(False)
            
            self.logger.error(
                "In-app notification delivery failed",
                notification_id=context.notification_id,
                user_id=context.user_id,
                error=str(e),
                exc_info=True
            )
            
            return self._create_delivery_result(
                context=context,
                status=DeliveryResultStatus.FAILED,
                success=False,
                processing_time_ms=processing_time,
                error_message=str(e),
                error_code="DATABASE_ERROR"
            )
    
    async def health_check(self) -> bool:
        """
        Perform health check on in-app adapter
        
        Returns:
            True if adapter is healthy, False otherwise
        """
        try:
            if not self._is_initialized:
                return False
            
            # Test database connection
            await self.collection.find_one({}, {"_id": 1})
            
            self._last_health_check = datetime.now(timezone.utc)
            return True
            
        except Exception as e:
            self.logger.error(
                "In-app adapter health check failed",
                error=str(e),
                exc_info=True
            )
            return False
    
    async def cleanup_expired_notifications(self) -> int:
        """
        Clean up expired in-app notifications
        
        Returns:
            Number of notifications cleaned up
        """
        try:
            current_time = datetime.now(timezone.utc)
            
            # Remove expired notifications
            result = await self.collection.delete_many({
                "expires_at": {"$lt": current_time}
            })
            
            # Auto-mark old unread notifications as read
            auto_read_cutoff = current_time - timedelta(days=self.in_app_config.auto_mark_read_after_days)
            
            await self.collection.update_many(
                {
                    "status": "unread",
                    "created_at": {"$lt": auto_read_cutoff}
                },
                {
                    "$set": {
                        "status": "read",
                        "read_at": current_time
                    }
                }
            )
            
            deleted_count = result.deleted_count
            
            self.logger.info(
                "Cleaned up expired in-app notifications",
                deleted_count=deleted_count
            )
            
            return deleted_count
            
        except Exception as e:
            self.logger.error(
                "Failed to cleanup expired notifications",
                error=str(e),
                exc_info=True
            )
            return 0
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get in-app adapter metrics"""
        base_metrics = super().get_metrics()
        
        in_app_metrics = {
            "max_notifications_per_user": self.in_app_config.max_notifications_per_user,
            "retention_days": self.in_app_config.notification_retention_days,
            "grouping_enabled": self.in_app_config.enable_grouping,
            "real_time_enabled": self.in_app_config.enable_real_time_updates,
            "rich_content_enabled": self.in_app_config.support_rich_content
        }
        
        base_metrics.update(in_app_metrics)
        return base_metrics
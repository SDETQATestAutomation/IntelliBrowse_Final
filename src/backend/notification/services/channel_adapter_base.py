"""
Notification Module - Channel Adapter Base Classes

Abstract base classes and data models for implementing notification channel adapters.
Provides standardized interfaces for email, websocket, webhook, and other delivery channels.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field


class NotificationResultStatus(str, Enum):
    """Status values for notification delivery results."""
    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"
    RATE_LIMITED = "rate_limited"
    INVALID_RECIPIENT = "invalid_recipient"
    CHANNEL_UNAVAILABLE = "channel_unavailable"


class NotificationPayload(BaseModel):
    """
    Standardized payload for notification delivery across all channels.
    
    Contains all information needed by channel adapters to deliver notifications
    while maintaining consistent structure regardless of delivery method.
    """
    # Core notification information
    notification_id: str = Field(..., description="Unique notification identifier")
    type: str = Field(..., description="Notification type category")
    priority: str = Field(..., description="Priority level (low, medium, high, urgent, critical)")
    
    # Content
    title: str = Field(..., description="Notification title/subject")
    message: str = Field(..., description="Main notification message")
    html_content: Optional[str] = Field(None, description="HTML formatted content for rich channels")
    
    # Recipient information
    recipient_id: str = Field(..., description="Target user/recipient ID")
    recipient_email: Optional[str] = Field(None, description="Email address if applicable")
    recipient_phone: Optional[str] = Field(None, description="Phone number if applicable")
    recipient_name: Optional[str] = Field(None, description="Display name for recipient")
    
    # Channel-specific settings
    channel_settings: Dict[str, Any] = Field(
        default_factory=dict,
        description="Channel-specific configuration and settings"
    )
    
    # Metadata and context
    correlation_id: Optional[str] = Field(None, description="Correlation ID for tracing")
    source_service: str = Field(..., description="Service that generated this notification")
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context data"
    )
    
    # Delivery options
    scheduled_at: Optional[datetime] = Field(None, description="Scheduled delivery time")
    expires_at: Optional[datetime] = Field(None, description="Expiration time")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    retry_delay_seconds: int = Field(default=60, description="Delay between retries")
    
    # Tracking
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp"
    )
    attempt_number: int = Field(default=1, description="Current delivery attempt number")
    
    def to_email_format(self) -> Dict[str, Any]:
        """Convert payload to email-specific format."""
        return {
            "to": self.recipient_email,
            "subject": self.title,
            "body": self.message,
            "html": self.html_content,
            "correlation_id": self.correlation_id,
            "priority": self.priority,
            "headers": {
                "X-Notification-ID": self.notification_id,
                "X-Source-Service": self.source_service,
                "X-Priority": self.priority
            }
        }
    
    def to_websocket_format(self) -> Dict[str, Any]:
        """Convert payload to WebSocket message format."""
        return {
            "notification_id": self.notification_id,
            "type": self.type,
            "title": self.title,
            "message": self.message,
            "priority": self.priority,
            "recipient_id": self.recipient_id,
            "correlation_id": self.correlation_id,
            "timestamp": self.created_at.isoformat(),
            "context": self.context
        }
    
    def to_webhook_format(self) -> Dict[str, Any]:
        """Convert payload to webhook POST body format."""
        return {
            "notification_id": self.notification_id,
            "type": self.type,
            "title": self.title,
            "message": self.message,
            "priority": self.priority,
            "recipient": {
                "id": self.recipient_id,
                "email": self.recipient_email,
                "name": self.recipient_name
            },
            "source_service": self.source_service,
            "correlation_id": self.correlation_id,
            "created_at": self.created_at.isoformat(),
            "context": self.context
        }


class NotificationResult(BaseModel):
    """
    Standardized result from notification delivery attempts.
    
    Provides consistent response format across all channel adapters
    for tracking delivery status, performance, and error handling.
    """
    # Core result information
    status: NotificationResultStatus = Field(..., description="Delivery result status")
    success: bool = Field(..., description="Whether delivery was successful")
    
    # Timing information
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Delivery attempt start time"
    )
    completed_at: Optional[datetime] = Field(None, description="Delivery completion time")
    duration_ms: Optional[int] = Field(None, description="Delivery duration in milliseconds")
    
    # Provider and delivery details
    provider_name: Optional[str] = Field(None, description="Service provider used")
    provider_message_id: Optional[str] = Field(None, description="Provider's message identifier")
    external_id: Optional[str] = Field(None, description="External system identifier")
    
    # Error information
    error_code: Optional[str] = Field(None, description="Error code if delivery failed")
    error_message: Optional[str] = Field(None, description="Human-readable error description")
    error_details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional error context and details"
    )
    
    # Retry information
    retry_recommended: bool = Field(default=False, description="Whether retry is recommended")
    retry_after_seconds: Optional[int] = Field(None, description="Suggested retry delay")
    max_retries_exceeded: bool = Field(default=False, description="Whether max retries reached")
    
    # Channel-specific response data
    channel_response: Dict[str, Any] = Field(
        default_factory=dict,
        description="Channel-specific response data"
    )
    
    # Metrics
    bytes_sent: Optional[int] = Field(None, description="Bytes transmitted")
    recipient_count: int = Field(default=1, description="Number of recipients")
    
    def mark_completed(self, success: bool = True) -> None:
        """Mark the delivery as completed and calculate duration."""
        self.completed_at = datetime.now(timezone.utc)
        self.success = success
        
        if self.completed_at and self.started_at:
            delta = self.completed_at - self.started_at
            self.duration_ms = int(delta.total_seconds() * 1000)
    
    def add_error(
        self, 
        error_code: str, 
        error_message: str, 
        retry_recommended: bool = False,
        retry_after_seconds: Optional[int] = None
    ) -> None:
        """Add error information to the result."""
        self.status = NotificationResultStatus.FAILURE
        self.success = False
        self.error_code = error_code
        self.error_message = error_message
        self.retry_recommended = retry_recommended
        self.retry_after_seconds = retry_after_seconds
        self.mark_completed(success=False)
    
    def mark_rate_limited(self, retry_after_seconds: int) -> None:
        """Mark result as rate limited with retry information."""
        self.status = NotificationResultStatus.RATE_LIMITED
        self.success = False
        self.retry_recommended = True
        self.retry_after_seconds = retry_after_seconds
        self.error_message = f"Rate limited, retry after {retry_after_seconds} seconds"
        self.mark_completed(success=False)


class NotificationChannelAdapter(ABC):
    """
    Abstract base class for notification channel adapters.
    
    Defines the standard interface that all channel implementations must provide.
    Each channel (email, websocket, webhook, SMS, etc.) implements this interface
    to provide consistent notification delivery capabilities.
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        """
        Initialize the channel adapter.
        
        Args:
            name: Human-readable name for this adapter
            config: Channel-specific configuration dictionary
        """
        self.name = name
        self.config = config
        self.enabled = config.get("enabled", True)
        self.max_retries = config.get("max_retries", 3)
        self.timeout_seconds = config.get("timeout_seconds", 30)
    
    @abstractmethod
    async def send(self, payload: NotificationPayload) -> NotificationResult:
        """
        Send notification through this channel.
        
        Args:
            payload: Standardized notification payload
            
        Returns:
            NotificationResult: Delivery result with status and metadata
            
        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError("Channel adapters must implement send()")
    
    @abstractmethod
    async def validate_recipient(self, recipient_data: Dict[str, Any]) -> bool:
        """
        Validate that recipient data is suitable for this channel.
        
        Args:
            recipient_data: Recipient information dictionary
            
        Returns:
            bool: True if recipient is valid for this channel
            
        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError("Channel adapters must implement validate_recipient()")
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Check health/availability of this channel.
        
        Returns:
            Dict containing health status and metrics
            
        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError("Channel adapters must implement health_check()")
    
    async def supports_batch(self) -> bool:
        """
        Check if this channel supports batch delivery.
        
        Returns:
            bool: True if batch delivery is supported
        """
        return False
    
    async def get_rate_limits(self) -> Dict[str, int]:
        """
        Get rate limit information for this channel.
        
        Returns:
            Dict with rate limit details (per_minute, per_hour, per_day)
        """
        return {
            "per_minute": self.config.get("rate_limit_per_minute", 60),
            "per_hour": self.config.get("rate_limit_per_hour", 1000),
            "per_day": self.config.get("rate_limit_per_day", 10000)
        }
    
    def is_enabled(self) -> bool:
        """Check if this channel is currently enabled."""
        return self.enabled
    
    def get_channel_type(self) -> str:
        """Get the channel type identifier."""
        return getattr(self, "channel_type", self.__class__.__name__.lower())
    
    def __str__(self) -> str:
        """String representation of the adapter."""
        return f"{self.__class__.__name__}(name='{self.name}', enabled={self.enabled})"
    
    def __repr__(self) -> str:
        """Detailed representation of the adapter."""
        return f"{self.__class__.__name__}(name='{self.name}', config={self.config})"


class EmailChannelAdapter(NotificationChannelAdapter):
    """
    Base class for email channel implementations.
    
    Provides common email functionality that can be extended by
    specific email providers (SendGrid, AWS SES, SMTP, etc.).
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.channel_type = "email"
        self.from_address = config.get("from_address")
        self.from_name = config.get("from_name", "IntelliBrowse Notifications")
    
    async def validate_recipient(self, recipient_data: Dict[str, Any]) -> bool:
        """Validate email recipient data."""
        email = recipient_data.get("email")
        if not email:
            return False
        
        # Basic email validation
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(email_pattern, email))
    
    async def supports_batch(self) -> bool:
        """Email channels typically support batch delivery."""
        return True


class WebSocketChannelAdapter(NotificationChannelAdapter):
    """
    Base class for WebSocket channel implementations.
    
    Provides common WebSocket functionality for real-time notifications.
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.channel_type = "websocket"
        self.connection_manager = None  # To be injected
    
    async def validate_recipient(self, recipient_data: Dict[str, Any]) -> bool:
        """Validate WebSocket recipient data."""
        user_id = recipient_data.get("user_id")
        return bool(user_id)


class WebhookChannelAdapter(NotificationChannelAdapter):
    """
    Base class for webhook channel implementations.
    
    Provides common webhook functionality for external system integrations.
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.channel_type = "webhook"
        self.default_webhook_url = config.get("default_webhook_url")
        self.authentication = config.get("authentication", {})
    
    async def validate_recipient(self, recipient_data: Dict[str, Any]) -> bool:
        """Validate webhook recipient data."""
        webhook_url = recipient_data.get("webhook_url") or self.default_webhook_url
        return bool(webhook_url)


class LoggingChannelAdapter(NotificationChannelAdapter):
    """
    Logging channel adapter for development and debugging.
    
    Logs notifications instead of delivering them, useful for testing
    and development environments.
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.channel_type = "logging"
    
    async def send(self, payload: NotificationPayload) -> NotificationResult:
        """Log the notification instead of sending it."""
        result = NotificationResult(
            status=NotificationResultStatus.SUCCESS,
            success=True,
            provider_name="logging"
        )
        
        print(f"[NOTIFICATION LOG] {payload.notification_id}: {payload.title}")
        print(f"  Type: {payload.type}, Priority: {payload.priority}")
        print(f"  Recipient: {payload.recipient_id}")
        print(f"  Message: {payload.message}")
        
        result.mark_completed(success=True)
        return result
    
    async def validate_recipient(self, recipient_data: Dict[str, Any]) -> bool:
        """Always valid for logging."""
        return True
    
    async def health_check(self) -> Dict[str, Any]:
        """Logging channel is always healthy."""
        return {
            "status": "healthy",
            "channel": "logging",
            "message": "Logging channel is operational"
        } 
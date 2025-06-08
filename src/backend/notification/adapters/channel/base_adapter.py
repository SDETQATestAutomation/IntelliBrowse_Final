"""
IntelliBrowse Notification Engine - Base Channel Adapter

This module defines the base interface and contract for all notification delivery
channel adapters, providing a standardized approach for implementing different
notification delivery mechanisms (email, in-app, push, SMS, etc.).

Classes:
    - BaseChannelAdapter: Abstract base class for all channel adapters
    - ChannelConfig: Configuration container for channel settings
    - DeliveryContext: Context information for delivery attempts
    - AdapterCapabilities: Capabilities declaration for adapters

Author: IntelliBrowse Team
Created: Phase 5 - Background Tasks & Delivery Daemon Implementation
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
from enum import Enum

from pydantic import BaseModel, Field

# Import delivery result and notification models
from ...services.delivery_task_service import DeliveryResult, DeliveryResultStatus
from ...models.notification_model import NotificationModel
from ...schemas.user_context import UserContext

# Configure logging
logger = logging.getLogger(__name__)


class ChannelType(str, Enum):
    """Enumeration of supported notification channels"""
    EMAIL = "email"
    IN_APP = "in_app"
    PUSH = "push"
    SMS = "sms"
    WEBHOOK = "webhook"
    SLACK = "slack"
    TEAMS = "teams"


class DeliveryPriority(str, Enum):
    """Enumeration of delivery priorities"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ChannelConfig(BaseModel):
    """
    Configuration container for channel adapter settings
    
    Provides standardized configuration structure that can be extended
    by specific channel adapters with their own settings.
    """
    
    channel_type: ChannelType = Field(..., description="Type of notification channel")
    enabled: bool = Field(default=True, description="Whether channel is enabled")
    
    # Rate limiting configuration
    rate_limit_per_minute: Optional[int] = Field(None, description="Rate limit per minute")
    rate_limit_per_hour: Optional[int] = Field(None, description="Rate limit per hour")
    rate_limit_per_day: Optional[int] = Field(None, description="Rate limit per day")
    
    # Timeout configuration
    connection_timeout_seconds: float = Field(default=30.0, description="Connection timeout")
    read_timeout_seconds: float = Field(default=60.0, description="Read timeout")
    
    # Retry configuration specific to channel
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    retry_delay_seconds: float = Field(default=5.0, description="Base retry delay")
    
    # Priority handling
    supported_priorities: List[DeliveryPriority] = Field(
        default=[DeliveryPriority.LOW, DeliveryPriority.MEDIUM, DeliveryPriority.HIGH, DeliveryPriority.CRITICAL],
        description="Supported delivery priorities"
    )
    
    # Channel-specific configuration (to be extended by subclasses)
    channel_settings: Dict[str, Any] = Field(default_factory=dict, description="Channel-specific settings")
    
    class Config:
        """Pydantic model configuration"""
        use_enum_values = True


class DeliveryContext(BaseModel):
    """
    Context information for delivery attempts
    
    Contains all contextual information needed for a delivery attempt,
    including user context, notification metadata, and delivery preferences.
    """
    
    # Core identifiers
    notification_id: str = Field(..., description="Notification identifier")
    user_id: str = Field(..., description="Target user identifier")
    correlation_id: str = Field(..., description="Correlation ID for tracking")
    
    # User context
    user_context: UserContext = Field(..., description="User context information")
    
    # Notification data
    notification: NotificationModel = Field(..., description="Notification to deliver")
    
    # Delivery preferences
    preferred_channel: Optional[ChannelType] = Field(None, description="User's preferred channel")
    delivery_priority: DeliveryPriority = Field(default=DeliveryPriority.MEDIUM, description="Delivery priority")
    
    # Timing information
    scheduled_at: Optional[datetime] = Field(None, description="Scheduled delivery time")
    deadline: Optional[datetime] = Field(None, description="Delivery deadline")
    
    # Retry context
    attempt_number: int = Field(default=1, description="Current attempt number")
    previous_errors: List[str] = Field(default_factory=list, description="Previous delivery errors")
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        """Pydantic model configuration"""
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class AdapterCapabilities(BaseModel):
    """
    Capabilities declaration for channel adapters
    
    Declares what features and functionality a channel adapter supports,
    enabling the delivery daemon to make informed routing decisions.
    """
    
    # Basic capabilities
    supports_rich_content: bool = Field(default=False, description="Supports rich HTML/formatted content")
    supports_attachments: bool = Field(default=False, description="Supports file attachments")
    supports_templates: bool = Field(default=False, description="Supports message templates")
    
    # Delivery features
    supports_scheduling: bool = Field(default=False, description="Supports scheduled delivery")
    supports_batching: bool = Field(default=False, description="Supports batch delivery")
    supports_personalization: bool = Field(default=True, description="Supports content personalization")
    
    # Tracking capabilities
    supports_delivery_tracking: bool = Field(default=False, description="Supports delivery confirmation")
    supports_read_receipts: bool = Field(default=False, description="Supports read receipt tracking")
    supports_engagement_tracking: bool = Field(default=False, description="Supports engagement metrics")
    
    # Content constraints
    max_content_length: Optional[int] = Field(None, description="Maximum content length in characters")
    max_subject_length: Optional[int] = Field(None, description="Maximum subject length in characters")
    max_attachment_size_mb: Optional[float] = Field(None, description="Maximum attachment size in MB")
    
    # Supported content types
    supported_content_types: List[str] = Field(
        default=["text/plain"],
        description="Supported content MIME types"
    )
    
    # Rate limiting information
    rate_limit_info: Dict[str, int] = Field(
        default_factory=dict,
        description="Rate limiting information (requests per time period)"
    )


class BaseChannelAdapter(ABC):
    """
    Abstract base class for all notification channel adapters
    
    Defines the standard interface that all channel adapters must implement,
    ensuring consistent behavior across different delivery mechanisms.
    """
    
    def __init__(self, config: ChannelConfig):
        """
        Initialize the channel adapter
        
        Args:
            config: Channel configuration
        """
        self.config = config
        self.logger = logger.bind(
            adapter=self.__class__.__name__,
            channel=config.channel_type.value
        )
        
        # Initialize adapter-specific state
        self._is_initialized = False
        self._last_health_check = None
        self._delivery_count = 0
        self._failure_count = 0
    
    @property
    @abstractmethod
    def channel_type(self) -> ChannelType:
        """
        Get the channel type this adapter handles
        
        Returns:
            Channel type enumeration value
        """
        pass
    
    @property
    @abstractmethod
    def capabilities(self) -> AdapterCapabilities:
        """
        Get the capabilities of this adapter
        
        Returns:
            Adapter capabilities declaration
        """
        pass
    
    @abstractmethod
    async def initialize(self) -> bool:
        """
        Initialize the adapter and establish any required connections
        
        Returns:
            True if initialization successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def send(
        self,
        context: DeliveryContext
    ) -> DeliveryResult:
        """
        Send notification through this channel
        
        Args:
            context: Delivery context containing all necessary information
            
        Returns:
            Delivery result with status and metadata
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Perform health check on the channel adapter
        
        Returns:
            True if adapter is healthy, False otherwise
        """
        pass
    
    async def prepare_content(
        self,
        notification: NotificationModel,
        user_context: UserContext
    ) -> Dict[str, Any]:
        """
        Prepare notification content for this channel
        
        This method can be overridden by subclasses to implement
        channel-specific content preparation and formatting.
        
        Args:
            notification: Notification to prepare
            user_context: User context for personalization
            
        Returns:
            Prepared content dictionary
        """
        return {
            "subject": notification.title,
            "content": notification.content,
            "metadata": notification.metadata
        }
    
    async def validate_delivery_context(
        self,
        context: DeliveryContext
    ) -> tuple[bool, Optional[str]]:
        """
        Validate delivery context before attempting delivery
        
        Args:
            context: Delivery context to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Basic validation
            if not context.notification_id:
                return False, "Missing notification ID"
            
            if not context.user_id:
                return False, "Missing user ID"
            
            if not context.notification:
                return False, "Missing notification data"
            
            if not context.user_context:
                return False, "Missing user context"
            
            # Check if channel is enabled
            if not self.config.enabled:
                return False, f"Channel {self.config.channel_type.value} is disabled"
            
            # Check content constraints
            if self.capabilities.max_content_length:
                if len(context.notification.content) > self.capabilities.max_content_length:
                    return False, f"Content length exceeds maximum of {self.capabilities.max_content_length}"
            
            if self.capabilities.max_subject_length:
                if len(context.notification.title) > self.capabilities.max_subject_length:
                    return False, f"Subject length exceeds maximum of {self.capabilities.max_subject_length}"
            
            return True, None
            
        except Exception as e:
            self.logger.error(
                "Error validating delivery context",
                error=str(e),
                exc_info=True
            )
            return False, f"Validation error: {str(e)}"
    
    def _create_delivery_result(
        self,
        context: DeliveryContext,
        status: DeliveryResultStatus,
        success: bool,
        processing_time_ms: float,
        error_message: Optional[str] = None,
        error_code: Optional[str] = None,
        external_id: Optional[str] = None,
        response_data: Optional[Dict[str, Any]] = None
    ) -> DeliveryResult:
        """
        Create a standardized delivery result
        
        Args:
            context: Delivery context
            status: Delivery result status
            success: Whether delivery was successful
            processing_time_ms: Processing time in milliseconds
            error_message: Error message if failed
            error_code: Error code if available
            external_id: External service delivery ID
            response_data: Response data from delivery service
            
        Returns:
            Delivery result object
        """
        return DeliveryResult(
            notification_id=context.notification_id,
            user_id=context.user_id,
            channel=self.channel_type.value,
            status=status,
            attempt_timestamp=datetime.now(timezone.utc),
            processing_time_ms=processing_time_ms,
            success=success,
            error_message=error_message,
            error_code=error_code,
            error_details=None,
            external_id=external_id,
            response_data=response_data,
            attempt_number=context.attempt_number,
            max_attempts=self.config.max_retries,
            should_retry=not success and context.attempt_number < self.config.max_retries,
            next_retry_at=None  # Will be calculated by retry policy
        )
    
    def _update_metrics(self, success: bool):
        """Update adapter metrics"""
        self._delivery_count += 1
        if not success:
            self._failure_count += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get adapter performance metrics
        
        Returns:
            Dictionary containing adapter metrics
        """
        return {
            "channel_type": self.channel_type.value,
            "total_deliveries": self._delivery_count,
            "total_failures": self._failure_count,
            "success_rate": (self._delivery_count - self._failure_count) / max(self._delivery_count, 1),
            "is_initialized": self._is_initialized,
            "last_health_check": self._last_health_check.isoformat() if self._last_health_check else None,
            "config": {
                "enabled": self.config.enabled,
                "max_retries": self.config.max_retries,
                "connection_timeout": self.config.connection_timeout_seconds,
                "read_timeout": self.config.read_timeout_seconds
            }
        }
    
    async def shutdown(self):
        """
        Gracefully shutdown the adapter and clean up resources
        
        Can be overridden by subclasses to implement adapter-specific cleanup.
        """
        self.logger.info(f"Shutting down {self.channel_type.value} adapter")
        self._is_initialized = False
    
    def __str__(self) -> str:
        """String representation of the adapter"""
        return f"{self.__class__.__name__}({self.channel_type.value})"
    
    def __repr__(self) -> str:
        """Detailed string representation of the adapter"""
        return (
            f"{self.__class__.__name__}("
            f"channel_type={self.channel_type.value}, "
            f"enabled={self.config.enabled}, "
            f"initialized={self._is_initialized}"
            f")"
        ) 
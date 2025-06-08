"""
Notification Module - Delivery History Models

Implements delivery tracking, audit trails, and delivery attempt logging
for comprehensive notification system observability.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from enum import Enum
from pydantic import BaseModel, Field, field_validator, ConfigDict

from .notification_model import BaseMongoModel, NotificationChannel
from ...config.logging import get_logger

logger = get_logger(__name__)


class DeliveryStatus(str, Enum):
    """Delivery attempt status enumeration."""
    INITIATED = "initiated"        # Delivery attempt started
    IN_PROGRESS = "in_progress"    # Currently attempting delivery
    DELIVERED = "delivered"        # Successfully delivered
    FAILED = "failed"             # Delivery failed
    REJECTED = "rejected"         # Rejected by recipient/channel
    CANCELLED = "cancelled"       # Cancelled before completion
    TIMEOUT = "timeout"           # Delivery attempt timed out


class DeliveryAttempt(BaseModel):
    """Individual delivery attempt record."""
    attempt_number: int = Field(..., ge=1, description="Attempt sequence number")
    channel: NotificationChannel = Field(..., description="Delivery channel used")
    status: DeliveryStatus = Field(..., description="Delivery attempt status")
    
    # Timing
    started_at: datetime = Field(..., description="Attempt start time")
    completed_at: Optional[datetime] = Field(None, description="Attempt completion time")
    duration_ms: Optional[int] = Field(None, ge=0, description="Delivery duration in milliseconds")
    
    # Delivery details
    provider: Optional[str] = Field(None, description="Service provider used (e.g., SendGrid, SES)")
    provider_message_id: Optional[str] = Field(None, description="Provider-specific message ID")
    provider_response: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Provider response data"
    )
    
    # Error handling
    error_code: Optional[str] = Field(None, description="Error code if failed")
    error_message: Optional[str] = Field(None, description="Error description")
    retry_after_seconds: Optional[int] = Field(None, description="Suggested retry delay")
    
    # Context
    recipient_email: Optional[str] = Field(None, description="Email address used")
    webhook_url: Optional[str] = Field(None, description="Webhook URL used")
    websocket_session_id: Optional[str] = Field(None, description="WebSocket session ID")
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
        }
    )
    
    @field_validator('provider_response')
    @classmethod
    def validate_provider_response(cls, v):
        """Validate provider response dictionary."""
        return v if v is not None else {}
    
    @field_validator('completed_at')
    @classmethod
    def validate_completion_time(cls, v, values):
        """Validate completion time is after start time."""
        if v is not None and 'started_at' in values:
            started_at = values['started_at']
            if isinstance(started_at, datetime) and v < started_at:
                logger.warning("Completion time is before start time")
        return v
    
    def mark_completed(self, status: DeliveryStatus, error_message: Optional[str] = None) -> None:
        """
        Mark delivery attempt as completed.
        
        Args:
            status: Final delivery status
            error_message: Error message if failed
        """
        self.status = status
        self.completed_at = datetime.now(timezone.utc)
        
        if self.started_at:
            duration = (self.completed_at - self.started_at).total_seconds() * 1000
            self.duration_ms = int(duration)
        
        if error_message:
            self.error_message = error_message
    
    def is_successful(self) -> bool:
        """Check if delivery attempt was successful."""
        return self.status == DeliveryStatus.DELIVERED
    
    def is_retryable(self) -> bool:
        """Check if delivery attempt failure is retryable."""
        non_retryable_statuses = [DeliveryStatus.DELIVERED, DeliveryStatus.REJECTED, DeliveryStatus.CANCELLED]
        return self.status not in non_retryable_statuses


class NotificationMetrics(BaseModel):
    """Aggregated metrics for notification performance."""
    total_attempts: int = Field(default=0, ge=0, description="Total delivery attempts")
    successful_deliveries: int = Field(default=0, ge=0, description="Successful deliveries")
    failed_attempts: int = Field(default=0, ge=0, description="Failed attempts")
    
    # Performance metrics
    average_delivery_time_ms: Optional[float] = Field(None, description="Average delivery time")
    max_delivery_time_ms: Optional[int] = Field(None, description="Maximum delivery time")
    min_delivery_time_ms: Optional[int] = Field(None, description="Minimum delivery time")
    
    # Channel breakdown
    channel_success_rates: Dict[str, float] = Field(
        default_factory=dict,
        description="Success rate by channel"
    )
    
    # Error analysis
    common_errors: List[str] = Field(
        default_factory=list,
        description="Most common error messages"
    )
    
    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
        }
    )
    
    def calculate_success_rate(self) -> float:
        """Calculate overall success rate."""
        if self.total_attempts == 0:
            return 0.0
        return (self.successful_deliveries / self.total_attempts) * 100.0


class NotificationDeliveryHistory(BaseMongoModel):
    """
    Comprehensive delivery history and audit trail model.
    
    Tracks all delivery attempts, performance metrics, and provides
    audit capabilities for notification system observability.
    """
    
    # Core identification
    notification_id: str = Field(..., description="Associated notification ID")
    user_id: str = Field(..., description="Target user ID")
    
    # Delivery tracking
    delivery_attempts: List[DeliveryAttempt] = Field(
        default_factory=list,
        description="Chronological delivery attempts"
    )
    
    # Current state
    current_status: DeliveryStatus = Field(
        default=DeliveryStatus.INITIATED,
        description="Current overall delivery status"
    )
    channels_attempted: List[NotificationChannel] = Field(
        default_factory=list,
        description="Channels that have been attempted"
    )
    successful_channels: List[NotificationChannel] = Field(
        default_factory=list,
        description="Channels with successful delivery"
    )
    
    # Timing and performance
    first_attempt_at: Optional[datetime] = Field(None, description="Time of first delivery attempt")
    last_attempt_at: Optional[datetime] = Field(None, description="Time of last delivery attempt")
    final_delivery_at: Optional[datetime] = Field(None, description="Time of successful delivery")
    total_delivery_time_ms: Optional[int] = Field(None, description="Total time from start to delivery")
    
    # Aggregated metrics
    metrics: NotificationMetrics = Field(
        default_factory=NotificationMetrics,
        description="Aggregated delivery metrics"
    )
    
    # Context and metadata
    notification_type: str = Field(..., description="Type of notification")
    priority: str = Field(..., description="Notification priority")
    source_service: str = Field(..., description="Service that created notification")
    
    # User context
    user_preferences_snapshot: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="User preferences at time of delivery"
    )
    
    # Troubleshooting
    escalated: bool = Field(default=False, description="Whether delivery was escalated")
    manual_intervention: bool = Field(default=False, description="Whether manual intervention was required")
    notes: Optional[str] = Field(None, description="Additional notes or comments")
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
        }
    )
    
    @field_validator('notification_id', 'user_id')
    @classmethod
    def validate_required_ids(cls, v):
        """Validate required ID fields."""
        if not v or len(v) < 3:
            raise ValueError("ID must be at least 3 characters")
        return v
    
    @field_validator('delivery_attempts')
    @classmethod
    def validate_attempts_order(cls, v):
        """Validate delivery attempts are in chronological order."""
        if len(v) <= 1:
            return v
        
        for i in range(1, len(v)):
            if v[i].attempt_number <= v[i-1].attempt_number:
                raise ValueError("Delivery attempts must be in sequential order")
        
        return v
    
    def add_delivery_attempt(self, attempt: DeliveryAttempt) -> None:
        """
        Add a new delivery attempt to the history.
        
        Args:
            attempt: Delivery attempt to record
        """
        # Set attempt number
        attempt.attempt_number = len(self.delivery_attempts) + 1
        
        # Add to attempts list
        self.delivery_attempts.append(attempt)
        
        # Update tracking fields
        if not self.first_attempt_at:
            self.first_attempt_at = attempt.started_at
        
        self.last_attempt_at = attempt.started_at
        
        # Update channel tracking
        if attempt.channel not in self.channels_attempted:
            self.channels_attempted.append(attempt.channel)
        
        # Update successful channels if delivered
        if attempt.is_successful() and attempt.channel not in self.successful_channels:
            self.successful_channels.append(attempt.channel)
            if not self.final_delivery_at:
                self.final_delivery_at = attempt.completed_at
        
        # Update current status
        if attempt.is_successful():
            self.current_status = DeliveryStatus.DELIVERED
        elif attempt.status == DeliveryStatus.FAILED:
            self.current_status = DeliveryStatus.FAILED
        else:
            self.current_status = attempt.status
        
        # Recalculate metrics
        self._update_metrics()
        self.update_timestamp()
    
    def get_latest_attempt(self) -> Optional[DeliveryAttempt]:
        """Get the most recent delivery attempt."""
        if not self.delivery_attempts:
            return None
        return self.delivery_attempts[-1]
    
    def get_attempts_for_channel(self, channel: NotificationChannel) -> List[DeliveryAttempt]:
        """
        Get all delivery attempts for a specific channel.
        
        Args:
            channel: Notification channel
            
        Returns:
            List[DeliveryAttempt]: Attempts for the specified channel
        """
        return [attempt for attempt in self.delivery_attempts if attempt.channel == channel]
    
    def get_successful_attempts(self) -> List[DeliveryAttempt]:
        """Get all successful delivery attempts."""
        return [attempt for attempt in self.delivery_attempts if attempt.is_successful()]
    
    def get_failed_attempts(self) -> List[DeliveryAttempt]:
        """Get all failed delivery attempts."""
        return [attempt for attempt in self.delivery_attempts if attempt.status == DeliveryStatus.FAILED]
    
    def is_delivery_complete(self) -> bool:
        """Check if notification has been successfully delivered."""
        return len(self.successful_channels) > 0
    
    def has_channel_succeeded(self, channel: NotificationChannel) -> bool:
        """Check if delivery succeeded on a specific channel."""
        return channel in self.successful_channels
    
    def get_delivery_summary(self) -> Dict[str, Any]:
        """
        Get a summary of delivery status and performance.
        
        Returns:
            Dict[str, Any]: Delivery summary information
        """
        summary = {
            "notification_id": self.notification_id,
            "user_id": self.user_id,
            "status": self.current_status,
            "is_delivered": self.is_delivery_complete(),
            "total_attempts": len(self.delivery_attempts),
            "channels_attempted": len(self.channels_attempted),
            "successful_channels": len(self.successful_channels),
            "first_attempt_at": self.first_attempt_at,
            "final_delivery_at": self.final_delivery_at,
            "success_rate": self.metrics.calculate_success_rate()
        }
        
        if self.total_delivery_time_ms:
            summary["total_delivery_time_ms"] = self.total_delivery_time_ms
        
        return summary
    
    def _update_metrics(self) -> None:
        """Update aggregated metrics based on delivery attempts."""
        if not self.delivery_attempts:
            return
        
        # Basic counts
        self.metrics.total_attempts = len(self.delivery_attempts)
        self.metrics.successful_deliveries = len(self.get_successful_attempts())
        self.metrics.failed_attempts = len(self.get_failed_attempts())
        
        # Performance metrics
        completed_attempts = [a for a in self.delivery_attempts if a.duration_ms is not None]
        if completed_attempts:
            durations = [a.duration_ms for a in completed_attempts]
            self.metrics.average_delivery_time_ms = sum(durations) / len(durations)
            self.metrics.max_delivery_time_ms = max(durations)
            self.metrics.min_delivery_time_ms = min(durations)
        
        # Channel success rates
        self.metrics.channel_success_rates = {}
        for channel in self.channels_attempted:
            channel_attempts = self.get_attempts_for_channel(channel)
            successful = [a for a in channel_attempts if a.is_successful()]
            
            success_rate = len(successful) / len(channel_attempts) * 100.0 if channel_attempts else 0.0
            self.metrics.channel_success_rates[channel.value] = success_rate
        
        # Common errors
        failed_attempts = self.get_failed_attempts()
        error_messages = [a.error_message for a in failed_attempts if a.error_message]
        # Get most common errors (simplified - just take first 5 unique)
        unique_errors = list(set(error_messages))[:5]
        self.metrics.common_errors = unique_errors
        
        # Calculate total delivery time
        if self.first_attempt_at and self.final_delivery_at:
            total_time = (self.final_delivery_at - self.first_attempt_at).total_seconds() * 1000
            self.total_delivery_time_ms = int(total_time)
    
    def mark_escalated(self, notes: Optional[str] = None) -> None:
        """Mark delivery as escalated."""
        self.escalated = True
        if notes:
            self.notes = notes
        self.update_timestamp()
    
    def mark_manual_intervention(self, notes: Optional[str] = None) -> None:
        """Mark delivery as requiring manual intervention."""
        self.manual_intervention = True
        if notes:
            self.notes = notes
        self.update_timestamp()


class NotificationDeliveryHistoryOperations:
    """
    Utility class for NotificationDeliveryHistory database operations.
    Provides indexes, validation rules, and collection settings.
    """
    
    def __init__(self):
        self.collection_name = "notification_delivery_history"
    
    @staticmethod
    def get_indexes() -> List[Dict[str, Any]]:
        """
        Define MongoDB indexes for delivery history collection.
        
        Returns:
            List[Dict[str, Any]]: Index definitions for optimal query performance
        """
        return [
            # Primary lookups
            {
                "key": {"notification_id": 1},
                "unique": True,
                "name": "idx_notification_id_unique"
            },
            {
                "key": {"user_id": 1, "created_at": -1},
                "name": "idx_user_id_date"
            },
            
            # Status and performance queries
            {
                "key": {"current_status": 1, "last_attempt_at": -1},
                "name": "idx_status_last_attempt"
            },
            {
                "key": {"successful_channels": 1, "final_delivery_at": -1},
                "name": "idx_successful_channels"
            },
            
            # Channel and type analysis
            {
                "key": {"channels_attempted": 1, "notification_type": 1},
                "name": "idx_channels_type"
            },
            {
                "key": {"source_service": 1, "priority": 1, "created_at": -1},
                "name": "idx_source_priority_date"
            },
            
            # Troubleshooting queries
            {
                "key": {"escalated": 1, "manual_intervention": 1},
                "name": "idx_escalation_intervention"
            },
            {
                "key": {"current_status": 1, "escalated": 1, "created_at": -1},
                "name": "idx_status_escalated_date"
            },
            
            # Performance analysis
            {
                "key": {"metrics.total_attempts": -1, "created_at": -1},
                "name": "idx_metrics_attempts"
            },
            {
                "key": {"total_delivery_time_ms": -1},
                "name": "idx_delivery_time"
            },
            
            # TTL index for cleanup (90 days)
            {
                "key": {"created_at": 1},
                "expireAfterSeconds": 7776000,  # 90 days
                "name": "idx_ttl_cleanup"
            }
        ]
    
    @staticmethod
    def get_collection_validation() -> Dict[str, Any]:
        """
        Define MongoDB collection validation rules.
        
        Returns:
            Dict[str, Any]: Collection validation schema
        """
        return {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["notification_id", "user_id", "notification_type", "priority", "source_service"],
                "properties": {
                    "notification_id": {
                        "bsonType": "string",
                        "minLength": 3,
                        "maxLength": 100
                    },
                    "user_id": {
                        "bsonType": "string",
                        "minLength": 3,
                        "maxLength": 100
                    },
                    "current_status": {
                        "enum": [
                            "initiated", "in_progress", "delivered", "failed", 
                            "rejected", "cancelled", "timeout"
                        ]
                    },
                    "delivery_attempts": {
                        "bsonType": "array",
                        "maxItems": 50  # Reasonable limit for retry attempts
                    },
                    "channels_attempted": {
                        "bsonType": "array",
                        "items": {
                            "enum": ["email", "websocket", "webhook", "logging"]
                        }
                    },
                    "successful_channels": {
                        "bsonType": "array",
                        "items": {
                            "enum": ["email", "websocket", "webhook", "logging"]
                        }
                    },
                    "escalated": {
                        "bsonType": "bool"
                    },
                    "manual_intervention": {
                        "bsonType": "bool"
                    }
                }
            }
        }
    
    def get_collection_settings(self) -> Dict[str, Any]:
        """
        Get complete collection configuration.
        
        Returns:
            Dict[str, Any]: Collection settings with indexes and validation
        """
        return {
            "indexes": self.get_indexes(),
            "validation": self.get_collection_validation(),
            "collection_name": self.collection_name
        } 
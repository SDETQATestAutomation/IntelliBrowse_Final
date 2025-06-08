"""
Notification Module - Core Notification Model

Implements the core notification document with multi-channel delivery metadata,
recipient information, content management, and retry tracking.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
from pydantic import BaseModel, Field, field_validator, ConfigDict
from bson import ObjectId

from ...config.logging import get_logger

logger = get_logger(__name__)


class BaseMongoModel(BaseModel):
    """
    Base model for MongoDB documents with common fields and utilities.
    
    Implements DRY principles for timestamps, schema versioning, and
    datetime serialization handling across all MongoDB models.
    """
    
    # Document identity
    id: Optional[str] = Field(None, alias="_id", description="MongoDB document ID")
    
    # Schema versioning for migrations (stored as _schema_version in MongoDB)
    schema_version: str = Field(
        default="1.0",
        alias="_schema_version",
        description="Schema version for forward compatibility"
    )
    
    # Audit trail with UTC-aware timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp (UTC)"
    )
    updated_at: Optional[datetime] = Field(
        None,
        description="Last update timestamp (UTC)"
    )
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        use_enum_values=True,
        json_encoders={
            ObjectId: str,
            datetime: lambda v: v.isoformat() if v else None,
        }
    )
    
    @field_validator('created_at', 'updated_at', mode='before')
    @classmethod
    def validate_datetime_utc(cls, v):
        """Ensure datetime fields are UTC-aware with fallback handling."""
        if v is None:
            return v
        
        if isinstance(v, str):
            try:
                # Parse ISO string with fallback
                if v.endswith('Z'):
                    v = v[:-1] + '+00:00'
                return datetime.fromisoformat(v)
            except ValueError:
                logger.warning(f"Failed to parse datetime string: {v}, using current UTC time")
                return datetime.now(timezone.utc)
        
        if isinstance(v, datetime):
            # Ensure timezone awareness
            if v.tzinfo is None:
                logger.debug("Converting naive datetime to UTC")
                return v.replace(tzinfo=timezone.utc)
            return v
        
        logger.warning(f"Invalid datetime value: {v}, using current UTC time")
        return datetime.now(timezone.utc)
    
    def update_timestamp(self) -> None:
        """Update the updated_at timestamp to current UTC time."""
        self.updated_at = datetime.now(timezone.utc)
    
    @classmethod
    def from_mongo(cls, data: Dict[str, Any]) -> Optional["BaseMongoModel"]:
        """Create model instance from MongoDB document."""
        if not data:
            return None
        
        try:
            # Handle ObjectId conversion
            if "_id" in data and isinstance(data["_id"], ObjectId):
                data["_id"] = str(data["_id"])
            
            # Handle datetime fields
            for field in ["created_at", "updated_at"]:
                if field in data and data[field]:
                    if isinstance(data[field], datetime):
                        # Ensure UTC timezone
                        if data[field].tzinfo is None:
                            data[field] = data[field].replace(tzinfo=timezone.utc)
            
            return cls(**data)
        except Exception as e:
            logger.error(f"Failed to create {cls.__name__} from MongoDB data: {e}")
            return None
    
    def to_mongo(self) -> Dict[str, Any]:
        """Convert model to MongoDB document format."""
        data = self.model_dump(by_alias=True, exclude_none=True)
        
        # Convert string ID back to ObjectId for MongoDB
        if "_id" in data and data["_id"]:
            try:
                data["_id"] = ObjectId(data["_id"])
            except Exception:
                # If conversion fails, remove the field to let MongoDB generate new ID
                del data["_id"]
        
        # Ensure UTC datetime storage
        for field in ["created_at", "updated_at"]:
            if field in data and data[field]:
                if isinstance(data[field], str):
                    try:
                        data[field] = datetime.fromisoformat(data[field])
                    except ValueError:
                        logger.warning(f"Invalid datetime string for {field}: {data[field]}")
                        data[field] = datetime.now(timezone.utc)
        
        return data


class NotificationStatus(str, Enum):
    """Notification lifecycle status enumeration."""
    PENDING = "pending"        # Queued for processing
    PROCESSING = "processing"  # Currently being processed
    SENT = "sent"             # Sent to channel(s) 
    DELIVERED = "delivered"   # Confirmed delivery
    FAILED = "failed"         # Delivery failed after retries
    CANCELLED = "cancelled"   # Cancelled before processing


class NotificationPriority(str, Enum):
    """Notification priority levels for processing order."""
    LOW = "low"           # Standard notifications
    MEDIUM = "medium"     # Default priority
    HIGH = "high"         # Important notifications  
    URGENT = "urgent"     # Critical system alerts
    CRITICAL = "critical" # Highest priority - immediate processing


class NotificationChannel(str, Enum):
    """Available notification delivery channels."""
    EMAIL = "email"       # Email delivery via SMTP providers
    WEBSOCKET = "websocket"  # Real-time in-app notifications
    WEBHOOK = "webhook"   # External system HTTP callbacks
    LOGGING = "logging"   # Audit trail only (no external delivery)


class NotificationTypeCategory(str, Enum):
    """Notification type categories for preference management."""
    SYSTEM_ALERT = "system_alert"         # System health and errors
    TEST_EXECUTION = "test_execution"     # Test run notifications
    QUALITY_METRICS = "quality_metrics"  # Quality threshold alerts
    USER_MANAGEMENT = "user_management"  # Account and access changes  
    INTEGRATION = "integration"          # External system events


class RetryMetadata(BaseModel):
    """Retry tracking metadata for failed notifications."""
    max_retries: int = Field(default=3, ge=0, le=10, description="Maximum retry attempts")
    current_attempt: int = Field(default=0, ge=0, description="Current attempt number")
    next_retry_at: Optional[datetime] = Field(None, description="Scheduled retry time")
    last_error: Optional[str] = Field(None, description="Last failure reason")
    backoff_multiplier: float = Field(default=2.0, ge=1.0, le=5.0, description="Exponential backoff multiplier")
    
    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
        }
    )


class NotificationContent(BaseModel):
    """Notification content with channel-specific formatting."""
    subject: str = Field(..., min_length=1, max_length=200, description="Notification subject/title")
    body: str = Field(..., min_length=1, max_length=2000, description="Notification body content")
    template_id: Optional[str] = Field(None, description="Template ID for dynamic content")
    template_variables: Dict[str, Any] = Field(default_factory=dict, description="Template variable values")
    channel_specific: Dict[str, Any] = Field(default_factory=dict, description="Channel-specific content overrides")
    
    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
        }
    )
    
    @field_validator('template_variables', 'channel_specific')
    @classmethod
    def validate_dict_fields(cls, v):
        """Validate dictionary fields are not None."""
        return v if v is not None else {}


class NotificationRecipient(BaseModel):
    """Notification recipient information with targeting details."""
    user_id: str = Field(..., description="Target user ID")
    email: Optional[str] = Field(None, description="User email address")
    preferred_channels: List[NotificationChannel] = Field(
        default_factory=list,
        description="User's preferred delivery channels"
    )
    role_based: bool = Field(default=False, description="Whether this is role-based targeting")
    roles: List[str] = Field(default_factory=list, description="User roles if role-based")
    
    model_config = ConfigDict(use_enum_values=True)
    
    @field_validator('preferred_channels')
    @classmethod
    def validate_channels(cls, v):
        """Ensure at least one channel is specified if not empty."""
        if v is not None and len(v) == 0:
            return [NotificationChannel.EMAIL]  # Default fallback
        return v


class NotificationModel(BaseMongoModel):
    """
    Core notification document model for multi-channel delivery.
    
    Implements atomic notification records with embedded delivery metadata,
    recipient targeting, content management, and retry logic following
    the Channel Adapter Factory architecture design.
    """
    
    # Core identification
    notification_id: str = Field(..., description="Unique notification identifier")
    type: NotificationTypeCategory = Field(..., description="Notification type category")
    title: str = Field(..., min_length=1, max_length=200, description="Notification title")
    
    # Content and targeting
    content: NotificationContent = Field(..., description="Notification content with formatting")
    recipients: List[NotificationRecipient] = Field(
        ..., 
        min_length=1, 
        max_length=100,
        description="Target recipients with channel preferences"
    )
    
    # Delivery configuration
    channels: List[NotificationChannel] = Field(
        ...,
        min_length=1,
        description="Delivery channels to use"
    )
    priority: NotificationPriority = Field(
        default=NotificationPriority.MEDIUM,
        description="Processing priority level"
    )
    
    # Processing state
    status: NotificationStatus = Field(
        default=NotificationStatus.PENDING,
        description="Current notification status"
    )
    
    # Scheduling and timing
    scheduled_at: Optional[datetime] = Field(
        None,
        description="Scheduled delivery time (None for immediate)"
    )
    expires_at: Optional[datetime] = Field(
        None,
        description="Notification expiration time"
    )
    
    # Retry and failure handling
    retry_metadata: RetryMetadata = Field(
        default_factory=RetryMetadata,
        description="Retry configuration and tracking"
    )
    
    # Integration context
    source_service: str = Field(..., description="Service that created the notification")
    correlation_id: Optional[str] = Field(None, description="Correlation ID for tracking")
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context data"
    )
    
    # Audit and tracking
    sent_at: Optional[datetime] = Field(None, description="Actual send time")
    delivered_at: Optional[datetime] = Field(None, description="Delivery confirmation time")
    failed_at: Optional[datetime] = Field(None, description="Failure time")
    error_details: Optional[str] = Field(None, description="Failure reason details")
    
    # Lifecycle management
    created_by: str = Field(..., description="User ID who created the notification")
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_encoders={
            ObjectId: str,
            datetime: lambda v: v.isoformat() if v else None,
        }
    )
    
    @field_validator('notification_id')
    @classmethod
    def validate_notification_id(cls, v):
        """Validate notification ID format."""
        if not v or len(v) < 8:
            raise ValueError("Notification ID must be at least 8 characters")
        return v
    
    @field_validator('recipients')
    @classmethod
    def validate_recipients(cls, v):
        """Validate recipients list."""
        if not v or len(v) == 0:
            raise ValueError("At least one recipient must be specified")
        
        # Check for duplicate user IDs
        user_ids = [r.user_id for r in v]
        if len(user_ids) != len(set(user_ids)):
            raise ValueError("Duplicate recipients are not allowed")
        
        return v
    
    @field_validator('channels')
    @classmethod
    def validate_channels(cls, v):
        """Validate delivery channels."""
        if not v or len(v) == 0:
            raise ValueError("At least one delivery channel must be specified")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_channels = []
        for channel in v:
            if channel not in seen:
                seen.add(channel)
                unique_channels.append(channel)
        
        return unique_channels
    
    @field_validator('scheduled_at', 'expires_at')
    @classmethod
    def validate_scheduling(cls, v):
        """Validate scheduling timestamps."""
        if v is not None and v < datetime.now(timezone.utc):
            logger.warning(f"Scheduling time is in the past: {v}")
        return v
    
    def mark_sent(self) -> None:
        """Mark notification as sent and update timestamp."""
        self.status = NotificationStatus.SENT
        self.sent_at = datetime.now(timezone.utc)
        self.update_timestamp()
    
    def mark_delivered(self) -> None:
        """Mark notification as delivered and update timestamp."""
        self.status = NotificationStatus.DELIVERED
        self.delivered_at = datetime.now(timezone.utc)
        self.update_timestamp()
    
    def mark_failed(self, error_message: str) -> None:
        """Mark notification as failed with error details."""
        self.status = NotificationStatus.FAILED
        self.failed_at = datetime.now(timezone.utc)
        self.error_details = error_message
        self.update_timestamp()
    
    def increment_retry(self) -> bool:
        """
        Increment retry attempt counter.
        
        Returns:
            bool: True if retry should be attempted, False if max retries exceeded
        """
        self.retry_metadata.current_attempt += 1
        
        if self.retry_metadata.current_attempt >= self.retry_metadata.max_retries:
            self.mark_failed(f"Max retries ({self.retry_metadata.max_retries}) exceeded")
            return False
        
        # Calculate next retry time with exponential backoff
        base_delay = 60  # 1 minute base delay
        backoff_delay = base_delay * (self.retry_metadata.backoff_multiplier ** self.retry_metadata.current_attempt)
        max_delay = 3600  # 1 hour maximum delay
        
        delay_seconds = min(backoff_delay, max_delay)
        self.retry_metadata.next_retry_at = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(seconds=delay_seconds)
        
        self.update_timestamp()
        return True
    
    def is_expired(self) -> bool:
        """Check if notification has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at
    
    def is_ready_for_retry(self) -> bool:
        """Check if notification is ready for retry attempt."""
        if self.retry_metadata.next_retry_at is None:
            return False
        
        return (
            self.status == NotificationStatus.FAILED and
            datetime.now(timezone.utc) >= self.retry_metadata.next_retry_at and
            self.retry_metadata.current_attempt < self.retry_metadata.max_retries
        )
    
    def get_effective_channels(self, user_preferences: Optional[Dict[str, Any]] = None) -> List[NotificationChannel]:
        """
        Get effective delivery channels based on user preferences.
        
        Args:
            user_preferences: User notification preferences
            
        Returns:
            List[NotificationChannel]: Channels to use for delivery
        """
        if not user_preferences:
            return self.channels
        
        # Apply user preference filtering
        user_enabled_channels = user_preferences.get('enabled_channels', [])
        if not user_enabled_channels:
            return self.channels
        
        # Intersection of requested channels and user preferences
        effective_channels = [
            channel for channel in self.channels 
            if channel in user_enabled_channels
        ]
        
        # Fallback to original channels if user has disabled all
        return effective_channels if effective_channels else self.channels


class NotificationModelOperations:
    """
    Utility class for NotificationModel database operations and indexing.
    Provides indexes, validation rules, and collection settings.
    """
    
    def __init__(self):
        self.collection_name = "notifications"
    
    @staticmethod
    def get_indexes() -> List[Dict[str, Any]]:
        """
        Define MongoDB indexes for notification collection.
        
        Returns:
            List[Dict[str, Any]]: Index definitions for optimal query performance
        """
        return [
            # Primary queries
            {
                "key": {"notification_id": 1},
                "unique": True,
                "name": "idx_notification_id_unique"
            },
            {
                "key": {"status": 1, "priority": -1, "created_at": 1},
                "name": "idx_status_priority_created"
            },
            
            # Recipient queries
            {
                "key": {"recipients.user_id": 1, "status": 1},
                "name": "idx_recipients_status"
            },
            
            # Channel and type queries
            {
                "key": {"channels": 1, "type": 1},
                "name": "idx_channels_type"
            },
            
            # Scheduling and retry queries  
            {
                "key": {"scheduled_at": 1, "status": 1},
                "name": "idx_scheduled_status"
            },
            {
                "key": {"retry_metadata.next_retry_at": 1, "status": 1},
                "name": "idx_retry_schedule"
            },
            
            # Audit and cleanup
            {
                "key": {"created_by": 1, "created_at": -1},
                "name": "idx_created_by_date"
            },
            {
                "key": {"source_service": 1, "type": 1, "created_at": -1},
                "name": "idx_source_type_date"
            },
            
            # TTL index for automatic cleanup (30 days)
            {
                "key": {"created_at": 1},
                "expireAfterSeconds": 2592000,  # 30 days
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
                "required": [
                    "notification_id", "type", "title", "content", 
                    "recipients", "channels", "created_by", "source_service"
                ],
                "properties": {
                    "notification_id": {
                        "bsonType": "string",
                        "minLength": 8,
                        "maxLength": 100
                    },
                    "type": {
                        "enum": [
                            "system_alert", "test_execution", "quality_metrics", 
                            "user_management", "integration"
                        ]
                    },
                    "status": {
                        "enum": [
                            "pending", "processing", "sent", "delivered", "failed", "cancelled"
                        ]
                    },
                    "priority": {
                        "enum": ["low", "medium", "high", "urgent", "critical"]
                    },
                    "channels": {
                        "bsonType": "array",
                        "minItems": 1,
                        "items": {
                            "enum": ["email", "websocket", "webhook", "logging"]
                        }
                    },
                    "recipients": {
                        "bsonType": "array",
                        "minItems": 1,
                        "maxItems": 100
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
"""
Notification Module - User Preference Models

Implements user notification preferences with channel configuration,
quiet hours, escalation rules, and type-specific preferences.
"""

from datetime import datetime, timezone, time
from typing import Dict, List, Optional, Any
from enum import Enum
from pydantic import BaseModel, Field, field_validator, ConfigDict

from .notification_model import BaseMongoModel, NotificationChannel, NotificationTypeCategory
from ...config.logging import get_logger

logger = get_logger(__name__)


class NotificationChannelPreference(BaseModel):
    """Channel-specific notification preferences."""
    channel: NotificationChannel = Field(..., description="Notification channel")
    enabled: bool = Field(default=True, description="Whether this channel is enabled")
    priority: int = Field(default=1, ge=1, le=10, description="Channel priority (1=highest)")
    rate_limit: Optional[int] = Field(None, ge=1, description="Max notifications per hour")
    
    # Channel-specific settings
    settings: Dict[str, Any] = Field(
        default_factory=dict,
        description="Channel-specific configuration"
    )
    
    model_config = ConfigDict(use_enum_values=True)
    
    @field_validator('settings')
    @classmethod
    def validate_settings(cls, v):
        """Validate settings dictionary."""
        return v if v is not None else {}


class NotificationTypePreference(BaseModel):
    """Type-specific notification preferences."""
    type: NotificationTypeCategory = Field(..., description="Notification type")
    enabled: bool = Field(default=True, description="Whether this type is enabled")
    channels: List[NotificationChannel] = Field(
        default_factory=list,
        description="Enabled channels for this type"
    )
    
    # Type-specific overrides
    priority_threshold: Optional[str] = Field(
        None,
        description="Minimum priority level for this type"
    )
    escalation_enabled: bool = Field(
        default=False,
        description="Whether escalation is enabled for this type"
    )
    
    model_config = ConfigDict(use_enum_values=True)


class QuietHoursConfig(BaseModel):
    """Quiet hours configuration for reducing notifications."""
    enabled: bool = Field(default=False, description="Whether quiet hours are enabled")
    start_time: Optional[time] = Field(None, description="Quiet hours start time")
    end_time: Optional[time] = Field(None, description="Quiet hours end time") 
    timezone: str = Field(default="UTC", description="Timezone for quiet hours")
    
    # Exception handling
    emergency_override: bool = Field(
        default=True,
        description="Allow critical/urgent notifications during quiet hours"
    )
    exempt_types: List[NotificationTypeCategory] = Field(
        default_factory=list,
        description="Notification types exempt from quiet hours"
    )
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_encoders={
            time: lambda v: v.isoformat() if v else None,
        }
    )
    
    @field_validator('start_time', 'end_time')
    @classmethod
    def validate_time_fields(cls, v):
        """Validate time fields."""
        if v is not None and not isinstance(v, time):
            try:
                if isinstance(v, str):
                    # Parse time string (HH:MM format)
                    return datetime.strptime(v, "%H:%M").time()
            except ValueError:
                logger.warning(f"Invalid time format: {v}")
                return None
        return v
    
    def is_quiet_time(self, check_time: datetime) -> bool:
        """
        Check if given time falls within quiet hours.
        
        Args:
            check_time: Time to check (should be timezone-aware)
            
        Returns:
            bool: True if time falls within quiet hours
        """
        if not self.enabled or not self.start_time or not self.end_time:
            return False
        
        current_time = check_time.time()
        
        # Handle same-day quiet hours
        if self.start_time <= self.end_time:
            return self.start_time <= current_time <= self.end_time
        
        # Handle overnight quiet hours (crosses midnight)
        return current_time >= self.start_time or current_time <= self.end_time


class EscalationRule(BaseModel):
    """Escalation rule for notification delivery."""
    name: str = Field(..., min_length=1, max_length=100, description="Escalation rule name")
    
    # Trigger conditions
    delay_minutes: int = Field(default=30, ge=1, le=1440, description="Delay before escalation")
    max_escalations: int = Field(default=3, ge=1, le=10, description="Maximum escalation levels")
    
    # Escalation targets
    escalation_channels: List[NotificationChannel] = Field(
        default_factory=list,
        description="Additional channels for escalation"
    )
    escalation_recipients: List[str] = Field(
        default_factory=list,
        description="Additional recipient user IDs"
    )
    
    # Conditions
    trigger_types: List[NotificationTypeCategory] = Field(
        default_factory=list,
        description="Notification types that trigger escalation"
    )
    minimum_priority: str = Field(
        default="high",
        description="Minimum priority for escalation"
    )
    
    model_config = ConfigDict(use_enum_values=True)
    
    @field_validator('escalation_recipients')
    @classmethod
    def validate_recipients(cls, v):
        """Validate escalation recipients."""
        if v and len(v) > 20:  # Reasonable limit
            raise ValueError("Too many escalation recipients (max 20)")
        return v


class UserNotificationPreferencesModel(BaseMongoModel):
    """
    User notification preferences document model.
    
    Implements comprehensive user preferences for multi-channel notifications
    including channel priorities, quiet hours, type preferences, and escalation rules.
    """
    
    # Core identification
    user_id: str = Field(..., description="User ID (unique per user)")
    
    # Global preferences
    global_enabled: bool = Field(default=True, description="Global notification toggle")
    
    # Channel preferences
    channel_preferences: List[NotificationChannelPreference] = Field(
        default_factory=list,
        description="Channel-specific preferences"
    )
    
    # Type preferences  
    type_preferences: List[NotificationTypePreference] = Field(
        default_factory=list,
        description="Type-specific preferences"
    )
    
    # Quiet hours configuration
    quiet_hours: QuietHoursConfig = Field(
        default_factory=QuietHoursConfig,
        description="Quiet hours configuration"
    )
    
    # Escalation rules
    escalation_rules: List[EscalationRule] = Field(
        default_factory=list,
        description="Escalation rules for critical notifications"
    )
    
    # Default fallback settings
    default_channels: List[NotificationChannel] = Field(
        default_factory=lambda: [NotificationChannel.EMAIL],
        description="Default channels when no preferences set"
    )
    
    # Digest settings
    digest_enabled: bool = Field(default=False, description="Enable notification digest")
    digest_frequency: str = Field(default="daily", description="Digest frequency (hourly, daily, weekly)")
    digest_time: Optional[time] = Field(None, description="Preferred digest delivery time")
    
    # Advanced settings
    deduplication_window_minutes: int = Field(
        default=60,
        ge=1,
        le=1440,
        description="Time window for duplicate notification suppression"
    )
    
    # Metadata
    last_updated_by: str = Field(..., description="User who last updated preferences")
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_encoders={
            time: lambda v: v.isoformat() if v else None,
        }
    )
    
    @field_validator('user_id')
    @classmethod
    def validate_user_id(cls, v):
        """Validate user ID format."""
        if not v or len(v) < 3:
            raise ValueError("User ID must be at least 3 characters")
        return v
    
    @field_validator('channel_preferences')
    @classmethod
    def validate_channel_preferences(cls, v):
        """Validate channel preferences for uniqueness."""
        if not v:
            return v
        
        # Check for duplicate channels
        channels = [pref.channel for pref in v]
        if len(channels) != len(set(channels)):
            raise ValueError("Duplicate channel preferences are not allowed")
        
        return v
    
    @field_validator('type_preferences')
    @classmethod
    def validate_type_preferences(cls, v):
        """Validate type preferences for uniqueness."""
        if not v:
            return v
        
        # Check for duplicate types
        types = [pref.type for pref in v]
        if len(types) != len(set(types)):
            raise ValueError("Duplicate type preferences are not allowed")
        
        return v
    
    @field_validator('digest_frequency')
    @classmethod
    def validate_digest_frequency(cls, v):
        """Validate digest frequency values."""
        valid_frequencies = ["hourly", "daily", "weekly"]
        if v not in valid_frequencies:
            raise ValueError(f"Digest frequency must be one of: {valid_frequencies}")
        return v
    
    def get_channel_preference(self, channel: NotificationChannel) -> Optional[NotificationChannelPreference]:
        """
        Get preferences for a specific channel.
        
        Args:
            channel: Notification channel
            
        Returns:
            NotificationChannelPreference: Channel preference or None
        """
        for pref in self.channel_preferences:
            if pref.channel == channel:
                return pref
        return None
    
    def get_type_preference(self, notification_type: NotificationTypeCategory) -> Optional[NotificationTypePreference]:
        """
        Get preferences for a specific notification type.
        
        Args:
            notification_type: Notification type category
            
        Returns:
            NotificationTypePreference: Type preference or None
        """
        for pref in self.type_preferences:
            if pref.type == notification_type:
                return pref
        return None
    
    def is_channel_enabled(self, channel: NotificationChannel) -> bool:
        """
        Check if a channel is enabled for the user.
        
        Args:
            channel: Notification channel to check
            
        Returns:
            bool: True if channel is enabled
        """
        if not self.global_enabled:
            return False
        
        channel_pref = self.get_channel_preference(channel)
        if channel_pref:
            return channel_pref.enabled
        
        # Default to enabled if no specific preference
        return True
    
    def is_type_enabled(self, notification_type: NotificationTypeCategory) -> bool:
        """
        Check if a notification type is enabled for the user.
        
        Args:
            notification_type: Notification type to check
            
        Returns:
            bool: True if type is enabled
        """
        if not self.global_enabled:
            return False
        
        type_pref = self.get_type_preference(notification_type)
        if type_pref:
            return type_pref.enabled
        
        # Default to enabled if no specific preference
        return True
    
    def get_enabled_channels_for_type(self, notification_type: NotificationTypeCategory) -> List[NotificationChannel]:
        """
        Get enabled channels for a specific notification type.
        
        Args:
            notification_type: Notification type
            
        Returns:
            List[NotificationChannel]: Enabled channels for the type
        """
        if not self.global_enabled or not self.is_type_enabled(notification_type):
            return []
        
        type_pref = self.get_type_preference(notification_type)
        if type_pref and type_pref.channels:
            # Filter by enabled channels
            enabled_channels = []
            for channel in type_pref.channels:
                if self.is_channel_enabled(channel):
                    enabled_channels.append(channel)
            return enabled_channels
        
        # Use default channels filtered by enabled status
        enabled_channels = []
        for channel in self.default_channels:
            if self.is_channel_enabled(channel):
                enabled_channels.append(channel)
        
        return enabled_channels
    
    def get_ordered_channels(self) -> List[NotificationChannel]:
        """
        Get channels ordered by priority.
        
        Returns:
            List[NotificationChannel]: Channels ordered by priority (highest first)
        """
        if not self.channel_preferences:
            return self.default_channels
        
        # Sort by priority (lower number = higher priority)
        sorted_prefs = sorted(
            [p for p in self.channel_preferences if p.enabled],
            key=lambda x: x.priority
        )
        
        return [pref.channel for pref in sorted_prefs]
    
    def should_escalate(self, notification_type: NotificationTypeCategory, priority: str) -> bool:
        """
        Check if notification should trigger escalation.
        
        Args:
            notification_type: Notification type
            priority: Notification priority
            
        Returns:
            bool: True if escalation should be triggered
        """
        if not self.escalation_rules:
            return False
        
        for rule in self.escalation_rules:
            # Check if rule applies to this type
            if rule.trigger_types and notification_type not in rule.trigger_types:
                continue
            
            # Check priority threshold
            priority_levels = ["low", "medium", "high", "urgent", "critical"]
            try:
                min_priority_index = priority_levels.index(rule.minimum_priority)
                current_priority_index = priority_levels.index(priority)
                
                if current_priority_index >= min_priority_index:
                    return True
            except ValueError:
                # Invalid priority, skip this rule
                continue
        
        return False
    
    def is_in_quiet_hours(self, check_time: Optional[datetime] = None) -> bool:
        """
        Check if current time is within quiet hours.
        
        Args:
            check_time: Time to check (defaults to current time)
            
        Returns:
            bool: True if in quiet hours
        """
        if check_time is None:
            check_time = datetime.now(timezone.utc)
        
        return self.quiet_hours.is_quiet_time(check_time)
    
    def should_suppress_during_quiet_hours(
        self, 
        notification_type: NotificationTypeCategory, 
        priority: str
    ) -> bool:
        """
        Check if notification should be suppressed during quiet hours.
        
        Args:
            notification_type: Notification type
            priority: Notification priority
            
        Returns:
            bool: True if notification should be suppressed
        """
        if not self.is_in_quiet_hours():
            return False
        
        # Check emergency override for high priority
        if self.quiet_hours.emergency_override and priority in ["urgent", "critical"]:
            return False
        
        # Check type exemptions
        if notification_type in self.quiet_hours.exempt_types:
            return False
        
        return True
    
    def add_channel_preference(self, channel_pref: NotificationChannelPreference) -> None:
        """
        Add or update channel preference.
        
        Args:
            channel_pref: Channel preference to add/update
        """
        # Remove existing preference for this channel
        self.channel_preferences = [
            p for p in self.channel_preferences 
            if p.channel != channel_pref.channel
        ]
        
        # Add new preference
        self.channel_preferences.append(channel_pref)
        self.update_timestamp()
    
    def add_type_preference(self, type_pref: NotificationTypePreference) -> None:
        """
        Add or update type preference.
        
        Args:
            type_pref: Type preference to add/update
        """
        # Remove existing preference for this type
        self.type_preferences = [
            p for p in self.type_preferences 
            if p.type != type_pref.type
        ]
        
        # Add new preference
        self.type_preferences.append(type_pref)
        self.update_timestamp()


class UserNotificationPreferencesOperations:
    """
    Utility class for UserNotificationPreferences database operations.
    Provides indexes, validation rules, and collection settings.
    """
    
    def __init__(self):
        self.collection_name = "user_notification_preferences"
    
    @staticmethod
    def get_indexes() -> List[Dict[str, Any]]:
        """
        Define MongoDB indexes for user preferences collection.
        
        Returns:
            List[Dict[str, Any]]: Index definitions for optimal query performance
        """
        return [
            # Primary user lookup
            {
                "key": {"user_id": 1},
                "unique": True,
                "name": "idx_user_id_unique"
            },
            
            # Channel preferences queries
            {
                "key": {"channel_preferences.channel": 1, "channel_preferences.enabled": 1},
                "name": "idx_channel_prefs"
            },
            
            # Type preferences queries
            {
                "key": {"type_preferences.type": 1, "type_preferences.enabled": 1},
                "name": "idx_type_prefs"
            },
            
            # Global settings queries
            {
                "key": {"global_enabled": 1, "updated_at": -1},
                "name": "idx_global_enabled"
            },
            
            # Escalation queries
            {
                "key": {"escalation_rules.trigger_types": 1},
                "name": "idx_escalation_types"
            },
            
            # Audit trail
            {
                "key": {"last_updated_by": 1, "updated_at": -1},
                "name": "idx_updated_by_date"
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
                "required": ["user_id", "last_updated_by"],
                "properties": {
                    "user_id": {
                        "bsonType": "string",
                        "minLength": 3,
                        "maxLength": 100
                    },
                    "global_enabled": {
                        "bsonType": "bool"
                    },
                    "channel_preferences": {
                        "bsonType": "array",
                        "maxItems": 10
                    },
                    "type_preferences": {
                        "bsonType": "array",
                        "maxItems": 20
                    },
                    "escalation_rules": {
                        "bsonType": "array",
                        "maxItems": 10
                    },
                    "digest_frequency": {
                        "enum": ["hourly", "daily", "weekly"]
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
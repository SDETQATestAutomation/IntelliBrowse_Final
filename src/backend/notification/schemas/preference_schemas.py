"""
Notification Module - User Preference Schemas

Pydantic schemas for user notification preference API endpoints with comprehensive 
validation and OpenAPI documentation examples following IntelliBrowse patterns.
"""

from datetime import time
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator

from ..models import (
    NotificationChannel, NotificationTypeCategory
)


class ChannelPreferenceRequestSchema(BaseModel):
    """Schema for configuring channel preferences."""
    channel: NotificationChannel = Field(
        ...,
        description="Notification channel to configure",
        examples=["email", "websocket", "webhook"]
    )
    enabled: bool = Field(
        default=True,
        description="Whether this channel is enabled"
    )
    priority: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Channel priority (1=highest, 10=lowest)",
        examples=[1, 5, 10]
    )
    rate_limit: Optional[int] = Field(
        None,
        ge=1,
        le=1000,
        description="Maximum notifications per hour for this channel",
        examples=[50, 100, 200]
    )
    settings: Dict[str, Any] = Field(
        default_factory=dict,
        description="Channel-specific configuration settings",
        examples=[{
            "email": {"format": "html", "digest_enabled": False},
            "webhook": {"url": "https://api.company.com/notifications", "timeout": 30}
        }]
    )
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "channel": "email",
                "enabled": True,
                "priority": 1,
                "rate_limit": 100,
                "settings": {
                    "format": "html",
                    "digest_enabled": False,
                    "signature": "Best regards,\\nIntelliBrowse Team"
                }
            }
        }
    )


class TypePreferenceRequestSchema(BaseModel):
    """Schema for configuring notification type preferences."""
    type: NotificationTypeCategory = Field(
        ...,
        description="Notification type to configure",
        examples=["test_execution", "system_alert", "quality_metrics"]
    )
    enabled: bool = Field(
        default=True,
        description="Whether this notification type is enabled"
    )
    channels: List[NotificationChannel] = Field(
        default_factory=list,
        description="Enabled channels for this notification type",
        examples=[["email"], ["email", "websocket"], ["webhook"]]
    )
    priority_threshold: Optional[str] = Field(
        None,
        description="Minimum priority level for this type",
        examples=["medium", "high", "urgent"]
    )
    escalation_enabled: bool = Field(
        default=False,
        description="Whether escalation is enabled for this type"
    )
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "type": "test_execution",
                "enabled": True,
                "channels": ["email", "websocket"],
                "priority_threshold": "medium",
                "escalation_enabled": False
            }
        }
    )


class QuietHoursConfigRequestSchema(BaseModel):
    """Schema for configuring quiet hours."""
    enabled: bool = Field(
        default=False,
        description="Whether quiet hours are enabled"
    )
    start_time: Optional[str] = Field(
        None,
        description="Quiet hours start time (HH:MM format)",
        examples=["22:00", "23:30"]
    )
    end_time: Optional[str] = Field(
        None,
        description="Quiet hours end time (HH:MM format)",
        examples=["07:00", "08:30"]
    )
    timezone: str = Field(
        default="UTC",
        description="Timezone for quiet hours",
        examples=["UTC", "America/New_York", "Europe/London"]
    )
    emergency_override: bool = Field(
        default=True,
        description="Allow critical/urgent notifications during quiet hours"
    )
    exempt_types: List[NotificationTypeCategory] = Field(
        default_factory=list,
        description="Notification types exempt from quiet hours",
        examples=[["system_alert"], ["system_alert", "quality_metrics"]]
    )
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "enabled": True,
                "start_time": "22:00",
                "end_time": "07:00",
                "timezone": "America/New_York",
                "emergency_override": True,
                "exempt_types": ["system_alert"]
            }
        }
    )
    
    @field_validator('start_time', 'end_time')
    @classmethod
    def validate_time_format(cls, v):
        """Validate time format is HH:MM."""
        if v is None:
            return v
        
        try:
            # Parse and validate time format
            time.fromisoformat(v)
            return v
        except ValueError:
            raise ValueError("Time must be in HH:MM format (e.g., '22:00')")


class EscalationRuleRequestSchema(BaseModel):
    """Schema for configuring escalation rules."""
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Escalation rule name",
        examples=["Critical Alert Escalation", "Test Failure Escalation"]
    )
    delay_minutes: int = Field(
        default=30,
        ge=1,
        le=1440,
        description="Delay before escalation in minutes",
        examples=[15, 30, 60]
    )
    max_escalations: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum escalation levels"
    )
    escalation_channels: List[NotificationChannel] = Field(
        default_factory=list,
        description="Additional channels for escalation",
        examples=[["webhook"], ["email", "webhook"]]
    )
    escalation_recipients: List[str] = Field(
        default_factory=list,
        description="Additional recipient user IDs for escalation",
        examples=[["manager_123"], ["admin_456", "oncall_789"]]
    )
    trigger_types: List[NotificationTypeCategory] = Field(
        default_factory=list,
        description="Notification types that trigger this escalation",
        examples=[["system_alert"], ["system_alert", "quality_metrics"]]
    )
    minimum_priority: str = Field(
        default="high",
        description="Minimum priority for escalation",
        examples=["medium", "high", "urgent", "critical"]
    )
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "name": "Critical System Alert Escalation",
                "delay_minutes": 30,
                "max_escalations": 3,
                "escalation_channels": ["webhook"],
                "escalation_recipients": ["manager_123", "oncall_456"],
                "trigger_types": ["system_alert"],
                "minimum_priority": "urgent"
            }
        }
    )
    
    @field_validator('escalation_recipients')
    @classmethod
    def validate_escalation_recipients(cls, v):
        """Validate escalation recipients list."""
        if v and len(v) > 20:
            raise ValueError("Maximum 20 escalation recipients allowed")
        return v


class UpdatePreferencesRequestSchema(BaseModel):
    """Schema for updating user notification preferences."""
    global_enabled: Optional[bool] = Field(
        None,
        description="Global notification toggle"
    )
    channel_preferences: Optional[List[ChannelPreferenceRequestSchema]] = Field(
        None,
        description="Channel-specific preferences to update"
    )
    type_preferences: Optional[List[TypePreferenceRequestSchema]] = Field(
        None,
        description="Type-specific preferences to update"
    )
    quiet_hours: Optional[QuietHoursConfigRequestSchema] = Field(
        None,
        description="Quiet hours configuration"
    )
    escalation_rules: Optional[List[EscalationRuleRequestSchema]] = Field(
        None,
        description="Escalation rules to update"
    )
    default_channels: Optional[List[NotificationChannel]] = Field(
        None,
        description="Default channels when no specific preferences set",
        examples=[["email"], ["email", "websocket"]]
    )
    digest_enabled: Optional[bool] = Field(
        None,
        description="Enable notification digest"
    )
    digest_frequency: Optional[str] = Field(
        None,
        description="Digest frequency",
        examples=["hourly", "daily", "weekly"]
    )
    digest_time: Optional[str] = Field(
        None,
        description="Preferred digest delivery time (HH:MM format)",
        examples=["09:00", "18:00"]
    )
    deduplication_window_minutes: Optional[int] = Field(
        None,
        ge=1,
        le=1440,
        description="Time window for duplicate notification suppression",
        examples=[30, 60, 120]
    )
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "global_enabled": True,
                "channel_preferences": [
                    {
                        "channel": "email",
                        "enabled": True,
                        "priority": 1,
                        "rate_limit": 100
                    },
                    {
                        "channel": "websocket",
                        "enabled": True,
                        "priority": 2
                    }
                ],
                "quiet_hours": {
                    "enabled": True,
                    "start_time": "22:00",
                    "end_time": "07:00",
                    "timezone": "America/New_York"
                },
                "digest_enabled": False,
                "digest_frequency": "daily",
                "deduplication_window_minutes": 60
            }
        }
    )
    
    @field_validator('digest_frequency')
    @classmethod
    def validate_digest_frequency(cls, v):
        """Validate digest frequency values."""
        if v is not None:
            valid_frequencies = ["hourly", "daily", "weekly"]
            if v not in valid_frequencies:
                raise ValueError(f"Digest frequency must be one of: {valid_frequencies}")
        return v


class ChannelPreferenceResponseSchema(BaseModel):
    """Schema for channel preference response."""
    channel: NotificationChannel = Field(..., description="Notification channel")
    enabled: bool = Field(..., description="Whether channel is enabled")
    priority: int = Field(..., description="Channel priority")
    rate_limit: Optional[int] = Field(None, description="Rate limit per hour")
    settings: Dict[str, Any] = Field(default_factory=dict, description="Channel settings")
    
    model_config = ConfigDict(use_enum_values=True)


class TypePreferenceResponseSchema(BaseModel):
    """Schema for type preference response."""
    type: NotificationTypeCategory = Field(..., description="Notification type")
    enabled: bool = Field(..., description="Whether type is enabled")
    channels: List[NotificationChannel] = Field(default_factory=list, description="Enabled channels")
    priority_threshold: Optional[str] = Field(None, description="Minimum priority threshold")
    escalation_enabled: bool = Field(..., description="Whether escalation is enabled")
    
    model_config = ConfigDict(use_enum_values=True)


class QuietHoursConfigResponseSchema(BaseModel):
    """Schema for quiet hours configuration response."""
    enabled: bool = Field(..., description="Whether quiet hours are enabled")
    start_time: Optional[str] = Field(None, description="Start time")
    end_time: Optional[str] = Field(None, description="End time")
    timezone: str = Field(..., description="Timezone")
    emergency_override: bool = Field(..., description="Emergency override enabled")
    exempt_types: List[NotificationTypeCategory] = Field(default_factory=list, description="Exempt types")
    
    model_config = ConfigDict(use_enum_values=True)


class EscalationRuleResponseSchema(BaseModel):
    """Schema for escalation rule response."""
    name: str = Field(..., description="Rule name")
    delay_minutes: int = Field(..., description="Delay before escalation")
    max_escalations: int = Field(..., description="Maximum escalation levels")
    escalation_channels: List[NotificationChannel] = Field(default_factory=list, description="Escalation channels")
    escalation_recipients: List[str] = Field(default_factory=list, description="Escalation recipients")
    trigger_types: List[NotificationTypeCategory] = Field(default_factory=list, description="Trigger types")
    minimum_priority: str = Field(..., description="Minimum priority")
    
    model_config = ConfigDict(use_enum_values=True)


class UserPreferencesResponseSchema(BaseModel):
    """Schema for complete user preferences response."""
    user_id: str = Field(..., description="User ID")
    global_enabled: bool = Field(..., description="Global notification toggle")
    
    # Preferences
    channel_preferences: List[ChannelPreferenceResponseSchema] = Field(
        default_factory=list,
        description="Channel-specific preferences"
    )
    type_preferences: List[TypePreferenceResponseSchema] = Field(
        default_factory=list,
        description="Type-specific preferences"
    )
    quiet_hours: QuietHoursConfigResponseSchema = Field(
        ...,
        description="Quiet hours configuration"
    )
    escalation_rules: List[EscalationRuleResponseSchema] = Field(
        default_factory=list,
        description="Escalation rules"
    )
    
    # Defaults and settings
    default_channels: List[NotificationChannel] = Field(
        default_factory=list,
        description="Default channels"
    )
    digest_enabled: bool = Field(..., description="Digest enabled")
    digest_frequency: str = Field(..., description="Digest frequency")
    digest_time: Optional[str] = Field(None, description="Digest time")
    deduplication_window_minutes: int = Field(..., description="Deduplication window")
    
    # Metadata
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")
    last_updated_by: str = Field(..., description="Last updated by user ID")
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "user_id": "user_123",
                "global_enabled": True,
                "channel_preferences": [
                    {
                        "channel": "email",
                        "enabled": True,
                        "priority": 1,
                        "rate_limit": 100,
                        "settings": {
                            "format": "html"
                        }
                    }
                ],
                "type_preferences": [
                    {
                        "type": "test_execution",
                        "enabled": True,
                        "channels": ["email", "websocket"],
                        "priority_threshold": "medium",
                        "escalation_enabled": False
                    }
                ],
                "quiet_hours": {
                    "enabled": True,
                    "start_time": "22:00",
                    "end_time": "07:00",
                    "timezone": "America/New_York",
                    "emergency_override": True,
                    "exempt_types": ["system_alert"]
                },
                "escalation_rules": [],
                "default_channels": ["email"],
                "digest_enabled": False,
                "digest_frequency": "daily",
                "digest_time": None,
                "deduplication_window_minutes": 60,
                "created_at": "2025-01-07T10:00:00Z",
                "updated_at": "2025-01-07T15:30:00Z",
                "last_updated_by": "user_123"
            }
        }
    ) 
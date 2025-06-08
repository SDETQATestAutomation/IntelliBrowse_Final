"""
Notification Module - Schemas Package

Pydantic schemas for API request/response validation and OpenAPI documentation.
Implements strict validation for multi-channel notification endpoints.
"""

from .notification_schemas import (
    SendNotificationRequestSchema,
    NotificationResponseSchema,
    NotificationStatusResponseSchema,
    NotificationListResponseSchema,
    NotificationMetricsResponseSchema
)
from .preference_schemas import (
    UserPreferencesResponseSchema,
    UpdatePreferencesRequestSchema,
    ChannelPreferenceRequestSchema,
    QuietHoursConfigRequestSchema,
    EscalationRuleRequestSchema
)
from .history_schemas import (
    NotificationHistoryQuerySchema,
    DeliveryHistoryResponseSchema,
    DeliveryHistoryListResponseSchema,
    DeliveryAttemptResponseSchema,
    DeliveryMetricsResponseSchema,
    DeliveryAuditResponseSchema,
    NotificationHistoryStatsSchema
)

__all__ = [
    # Core notification schemas
    "SendNotificationRequestSchema",
    "NotificationResponseSchema", 
    "NotificationStatusResponseSchema",
    "NotificationListResponseSchema",
    "NotificationMetricsResponseSchema",
    
    # User preference schemas
    "UserPreferencesResponseSchema",
    "UpdatePreferencesRequestSchema",
    "ChannelPreferenceRequestSchema",
    "QuietHoursConfigRequestSchema",
    "EscalationRuleRequestSchema",
    
    # Delivery history schemas
    "NotificationHistoryQuerySchema",
    "DeliveryHistoryResponseSchema",
    "DeliveryHistoryListResponseSchema",
    "DeliveryAttemptResponseSchema",
    "DeliveryMetricsResponseSchema",
    "DeliveryAuditResponseSchema",
    "NotificationHistoryStatsSchema"
] 
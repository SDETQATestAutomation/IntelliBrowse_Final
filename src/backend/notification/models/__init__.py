"""
Notification Module - Models Package

Core data models for multi-channel notification system.
Implements MongoDB document models with proper validation and audit trails.
"""

from .notification_model import (
    NotificationModel,
    NotificationStatus,
    NotificationPriority,
    NotificationChannel,
    NotificationTypeCategory,
    NotificationContent,
    NotificationRecipient,
    RetryMetadata,
    NotificationModelOperations
)
from .notification_preference_model import (
    UserNotificationPreferencesModel,
    NotificationChannelPreference,
    NotificationTypePreference,
    QuietHoursConfig,
    EscalationRule,
    UserNotificationPreferencesOperations
)
from .notification_history_model import (
    NotificationDeliveryHistory,
    DeliveryStatus,
    DeliveryAttempt,
    NotificationMetrics,
    NotificationDeliveryHistoryOperations
)

__all__ = [
    # Core notification models
    "NotificationModel",
    "NotificationStatus", 
    "NotificationPriority",
    "NotificationChannel",
    "NotificationTypeCategory",
    "NotificationContent",
    "NotificationRecipient",
    "RetryMetadata",
    "NotificationModelOperations",
    
    # User preferences
    "UserNotificationPreferencesModel",
    "NotificationChannelPreference",
    "NotificationTypePreference", 
    "QuietHoursConfig",
    "EscalationRule",
    "UserNotificationPreferencesOperations",
    
    # Delivery tracking
    "NotificationDeliveryHistory",
    "DeliveryStatus",
    "DeliveryAttempt",
    "NotificationMetrics",
    "NotificationDeliveryHistoryOperations"
] 
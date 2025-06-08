"""
Notification Module - Channel Adapters Package

Concrete implementations of notification channel adapters for multi-channel delivery.
"""

from .email_adapter import EmailNotificationAdapter
from .slack_adapter import SlackNotificationAdapter  
from .webhook_adapter import WebhookNotificationAdapter

__all__ = [
    "EmailNotificationAdapter",
    "SlackNotificationAdapter", 
    "WebhookNotificationAdapter"
] 
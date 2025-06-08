"""
Notification Module - Utilities Package

Database utilities, MongoDB collection management, and helper functions
for the notification system.
"""

from .mongodb_setup import (
    setup_notification_collections,
    create_notification_indexes,
    NotificationCollectionManager
)

__all__ = [
    # MongoDB setup and management
    "setup_notification_collections",
    "create_notification_indexes", 
    "NotificationCollectionManager"
] 
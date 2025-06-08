"""
IntelliBrowse Notification Engine - Services Module

This module provides comprehensive notification services including:
- Foundation services (storage, configuration)
- Dispatch services (notification routing and delivery)
- History services (notification history and analytics)
- Preference services (user preference management and sync)
- Security services (audit trail and compliance)

All services follow clean architecture principles with proper separation
of concerns, dependency injection, and comprehensive error handling.

Author: IntelliBrowse Team
"""

# Foundation Layer Services (Phase 1)
from .notification_storage_service import (
    NotificationStorageService,
    NotificationQueryBuilder,
    StorageTransaction
)

from .notification_configuration_service import (
    NotificationConfigurationService,
    ConfigurationValidator,
    ConfigurationCache
)

# Dispatch Layer Services (Phase 2)
from .notification_dispatcher import (
    NotificationDispatcherService,
    RecipientProcessor,
    DeliveryOrchestrator,
    DispatchMode
)

from .retry_manager import (
    RetryManager,
    RetryConfiguration,
    RetryPolicy,
    FailureType
)

from .error_manager import (
    ErrorManager,
    CircuitBreaker,
    CircuitBreakerConfig,
    ErrorSeverity
)

# History & Analytics Services (Phase 3)
from .notification_history_service import (
    NotificationHistoryService,
    HistoryQueryParameters,
    HistoryFilterBuilder,
    HistoryPaginator,
    HistorySortOption,
    NotFoundError
)

from .notification_analytics_service import (
    NotificationAnalyticsService,
    AnalyticsTimeWindow,
    AnalyticsCacheManager,
    MetricsAggregator,
    TimeWindow
)

# Preference Management Services (Phase 3)
from .notification_preference_sync_service import (
    NotificationPreferenceSyncService,
    PreferenceValidator,
    SyncStatusTracker,
    PreferenceAuditor,
    SyncStatus,
    PreferenceChangeType
)

# Security & Compliance Services (Phase 3)
from .notification_audit_service import (
    NotificationAuditService,
    DataMaskingEngine,
    ComplianceReporter,
    SecurityEventDetector,
    AuditEventType,
    SecurityEventSeverity
)

# Export all services and utilities
__all__ = [
    # Foundation Layer (Phase 1)
    "NotificationStorageService",
    "NotificationQueryBuilder", 
    "StorageTransaction",
    "NotificationConfigurationService",
    "ConfigurationValidator",
    "ConfigurationCache",
    
    # Dispatch Layer (Phase 2)
    "NotificationDispatcherService",
    "RecipientProcessor",
    "DeliveryOrchestrator",
    "DispatchMode",
    "RetryManager",
    "RetryConfiguration",
    "RetryPolicy",
    "FailureType",
    "ErrorManager",
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "ErrorSeverity",
    
    # History & Analytics (Phase 3)
    "NotificationHistoryService",
    "HistoryQueryParameters",
    "HistoryFilterBuilder",
    "HistoryPaginator",
    "HistorySortOption",
    "NotFoundError",
    "NotificationAnalyticsService",
    "AnalyticsTimeWindow",
    "AnalyticsCacheManager",
    "MetricsAggregator",
    "TimeWindow",
    
    # Preference Management (Phase 3)
    "NotificationPreferenceSyncService",
    "PreferenceValidator",
    "SyncStatusTracker",
    "PreferenceAuditor",
    "SyncStatus",
    "PreferenceChangeType",
    
    # Security & Compliance (Phase 3)
    "NotificationAuditService",
    "DataMaskingEngine",
    "ComplianceReporter",
    "SecurityEventDetector",
    "AuditEventType",
    "SecurityEventSeverity"
] 
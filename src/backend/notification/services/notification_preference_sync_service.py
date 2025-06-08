"""
IntelliBrowse Notification Engine - Preference Sync Service

This module provides comprehensive user notification preference synchronization
capabilities including preference validation, user context integration, 
opt-in/opt-out management, and comprehensive audit trail maintenance.

Classes:
    - NotificationPreferenceSyncService: Core preference sync service
    - PreferenceValidator: Validation logic for preference updates
    - SyncStatusTracker: Sync status monitoring and reporting
    - PreferenceAuditor: Audit trail management for preference changes

Author: IntelliBrowse Team
Created: Phase 3 - Preference Sync Implementation
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from enum import Enum

from bson import ObjectId
from pydantic import BaseModel, Field, validator
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from ..models.user_notification_preferences import (
    UserNotificationPreferencesModel,
    ChannelPreference,
    DeliveryTimeWindow,
    NotificationPriority
)
from ..schemas.preference_sync_schemas import (
    PreferenceSyncRequest,
    PreferenceSyncResponse,
    SyncStatusResponse,
    PreferenceAuditEntry,
    BulkPreferenceUpdate,
    OptInOutRequest,
    PreferenceImpactAnalysis
)

# Configure logging
logger = logging.getLogger(__name__)


class SyncStatus(str, Enum):
    """Enumeration of preference sync statuses"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class PreferenceChangeType(str, Enum):
    """Enumeration of preference change types for audit"""
    CHANNEL_ENABLED = "channel_enabled"
    CHANNEL_DISABLED = "channel_disabled"
    PRIORITY_CHANGED = "priority_changed"
    TIME_WINDOW_UPDATED = "time_window_updated"
    OPT_IN = "opt_in"
    OPT_OUT = "opt_out"
    BULK_UPDATE = "bulk_update"
    SYNC_CONFIGURATION = "sync_configuration"


class PreferenceValidator:
    """
    Validation logic for notification preference updates
    
    Provides comprehensive validation including business rules,
    channel availability, and consistency checks for preference updates.
    """
    
    @staticmethod
    def validate_channel_preferences(
        channel_preferences: Dict[str, ChannelPreference],
        available_channels: Set[str]
    ) -> List[str]:
        """
        Validate channel preference configuration
        
        Args:
            channel_preferences: Channel preferences to validate
            available_channels: Set of available notification channels
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Check for unknown channels
        for channel in channel_preferences.keys():
            if channel not in available_channels:
                errors.append(f"Unknown notification channel: {channel}")
        
        # Validate each channel preference
        for channel, preference in channel_preferences.items():
            try:
                # Validate priority levels
                if preference.priority not in [p.value for p in NotificationPriority]:
                    errors.append(f"Invalid priority '{preference.priority}' for channel {channel}")
                
                # Validate delivery time windows
                if preference.delivery_time_windows:
                    for window in preference.delivery_time_windows:
                        if window.start_time >= window.end_time:
                            errors.append(
                                f"Invalid time window for channel {channel}: "
                                f"start_time must be before end_time"
                            )
                        
                        if not (0 <= window.start_time.hour <= 23 and 0 <= window.end_time.hour <= 23):
                            errors.append(
                                f"Invalid time window hours for channel {channel}: "
                                f"hours must be between 0 and 23"
                            )
                
                # Validate retry configuration
                if preference.max_retries is not None and preference.max_retries < 0:
                    errors.append(f"Invalid max_retries for channel {channel}: must be >= 0")
                
                if preference.retry_delay_minutes is not None and preference.retry_delay_minutes < 1:
                    errors.append(f"Invalid retry_delay_minutes for channel {channel}: must be >= 1")
                    
            except Exception as e:
                errors.append(f"Validation error for channel {channel}: {str(e)}")
        
        return errors
    
    @staticmethod
    def validate_global_settings(
        global_settings: Dict[str, Any]
    ) -> List[str]:
        """
        Validate global notification settings
        
        Args:
            global_settings: Global settings to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Validate timezone
        timezone = global_settings.get("timezone")
        if timezone:
            try:
                import pytz
                pytz.timezone(timezone)
            except Exception:
                errors.append(f"Invalid timezone: {timezone}")
        
        # Validate language
        language = global_settings.get("language")
        if language:
            valid_languages = {"en", "es", "fr", "de", "it", "pt", "ja", "ko", "zh"}
            if language not in valid_languages:
                errors.append(f"Unsupported language: {language}")
        
        # Validate digest settings
        digest_frequency = global_settings.get("digest_frequency")
        if digest_frequency:
            valid_frequencies = {"immediate", "hourly", "daily", "weekly", "never"}
            if digest_frequency not in valid_frequencies:
                errors.append(f"Invalid digest_frequency: {digest_frequency}")
        
        # Validate quiet hours
        quiet_hours = global_settings.get("quiet_hours")
        if quiet_hours:
            try:
                start_hour = quiet_hours.get("start_hour", 0)
                end_hour = quiet_hours.get("end_hour", 0)
                
                if not (0 <= start_hour <= 23 and 0 <= end_hour <= 23):
                    errors.append("Quiet hours must be between 0 and 23")
                    
            except Exception as e:
                errors.append(f"Invalid quiet_hours configuration: {str(e)}")
        
        return errors
    
    @staticmethod
    def analyze_preference_impact(
        current_preferences: UserNotificationPreferencesModel,
        new_preferences: Dict[str, Any]
    ) -> PreferenceImpactAnalysis:
        """
        Analyze the impact of preference changes
        
        Args:
            current_preferences: Current user preferences
            new_preferences: Proposed preference changes
            
        Returns:
            Analysis of the impact of the changes
        """
        impact = PreferenceImpactAnalysis(
            channels_affected=[],
            notifications_impacted=0,
            delivery_changes=[],
            warnings=[],
            recommendations=[]
        )
        
        try:
            # Analyze channel changes
            current_channels = set(current_preferences.channel_preferences.keys())
            new_channel_prefs = new_preferences.get("channel_preferences", {})
            new_channels = set(new_channel_prefs.keys())
            
            # Check for disabled channels
            for channel in current_channels:
                current_enabled = current_preferences.channel_preferences[channel].enabled
                new_enabled = new_channel_prefs.get(channel, {}).get("enabled", current_enabled)
                
                if current_enabled and not new_enabled:
                    impact.channels_affected.append(channel)
                    impact.delivery_changes.append(f"Channel {channel} will be disabled")
                    impact.warnings.append(
                        f"Disabling {channel} may result in missed notifications"
                    )
                elif not current_enabled and new_enabled:
                    impact.channels_affected.append(channel)
                    impact.delivery_changes.append(f"Channel {channel} will be enabled")
            
            # Check for new channels
            new_channel_additions = new_channels - current_channels
            for channel in new_channel_additions:
                impact.channels_affected.append(channel)
                impact.delivery_changes.append(f"New channel {channel} will be added")
            
            # Analyze priority changes
            for channel in current_channels & new_channels:
                current_priority = current_preferences.channel_preferences[channel].priority
                new_priority = new_channel_prefs.get(channel, {}).get("priority", current_priority)
                
                if current_priority != new_priority:
                    impact.delivery_changes.append(
                        f"Channel {channel} priority changed from {current_priority} to {new_priority}"
                    )
            
            # Generate recommendations
            if len(impact.channels_affected) == 0:
                impact.recommendations.append("No channels will be affected by these changes")
            elif len(impact.channels_affected) > 3:
                impact.recommendations.append(
                    "Consider making changes incrementally to avoid disruption"
                )
            
            # Estimate impact on notifications
            enabled_channels = len([
                ch for ch, pref in new_channel_prefs.items()
                if pref.get("enabled", True)
            ])
            
            if enabled_channels == 0:
                impact.warnings.append("All notification channels will be disabled")
                impact.notifications_impacted = 100  # All notifications affected
            else:
                impact.notifications_impacted = len(impact.channels_affected) * 10  # Rough estimate
            
        except Exception as e:
            logger.error(f"Error analyzing preference impact: {e}")
            impact.warnings.append("Unable to fully analyze impact of changes")
        
        return impact


class SyncStatusTracker:
    """
    Sync status monitoring and reporting for preference operations
    
    Provides real-time sync status tracking with detailed progress
    information and error reporting for troubleshooting.
    """
    
    def __init__(self, collection: Collection):
        """Initialize sync status tracker with database collection"""
        self.collection = collection
        logger.debug("SyncStatusTracker initialized")
    
    async def create_sync_operation(
        self,
        user_id: str,
        operation_type: str,
        request_data: Dict[str, Any],
        actor_id: str
    ) -> str:
        """
        Create a new sync operation with tracking
        
        Args:
            user_id: User ID for the sync operation
            operation_type: Type of sync operation
            request_data: Request data for the operation
            actor_id: ID of the user/system initiating the sync
            
        Returns:
            Sync operation ID for tracking
        """
        try:
            sync_operation = {
                "_id": ObjectId(),
                "user_id": user_id,
                "operation_type": operation_type,
                "status": SyncStatus.PENDING.value,
                "request_data": request_data,
                "actor_id": actor_id,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "progress_steps": [],
                "error_details": None,
                "completion_percentage": 0
            }
            
            await self.collection.insert_one(sync_operation)
            sync_id = str(sync_operation["_id"])
            
            logger.info(f"Created sync operation {sync_id} for user {user_id}")
            return sync_id
            
        except Exception as e:
            logger.error(f"Error creating sync operation: {e}")
            raise RuntimeError(f"Failed to create sync operation: {str(e)}")
    
    async def update_sync_status(
        self,
        sync_id: str,
        status: SyncStatus,
        progress_step: Optional[str] = None,
        completion_percentage: Optional[int] = None,
        error_details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Update sync operation status and progress
        
        Args:
            sync_id: Sync operation ID
            status: New sync status
            progress_step: Current progress step description
            completion_percentage: Percentage completion (0-100)
            error_details: Error details if status is failed
        """
        try:
            update_data = {
                "status": status.value,
                "updated_at": datetime.utcnow()
            }
            
            if progress_step:
                update_data["$push"] = {
                    "progress_steps": {
                        "step": progress_step,
                        "timestamp": datetime.utcnow()
                    }
                }
            
            if completion_percentage is not None:
                update_data["completion_percentage"] = max(0, min(100, completion_percentage))
            
            if error_details:
                update_data["error_details"] = error_details
            
            await self.collection.update_one(
                {"_id": ObjectId(sync_id)},
                {"$set": update_data} if "$push" not in update_data else {
                    "$set": {k: v for k, v in update_data.items() if k != "$push"},
                    "$push": update_data["$push"]
                }
            )
            
            logger.debug(f"Updated sync operation {sync_id} to status {status.value}")
            
        except Exception as e:
            logger.error(f"Error updating sync status {sync_id}: {e}")
    
    async def get_sync_status(self, sync_id: str) -> Optional[SyncStatusResponse]:
        """
        Get current sync operation status
        
        Args:
            sync_id: Sync operation ID
            
        Returns:
            Sync status response or None if not found
        """
        try:
            sync_operation = await self.collection.find_one({"_id": ObjectId(sync_id)})
            
            if not sync_operation:
                return None
            
            return SyncStatusResponse(
                sync_id=sync_id,
                user_id=sync_operation["user_id"],
                operation_type=sync_operation["operation_type"],
                status=sync_operation["status"],
                completion_percentage=sync_operation.get("completion_percentage", 0),
                created_at=sync_operation["created_at"],
                updated_at=sync_operation["updated_at"],
                progress_steps=[step["step"] for step in sync_operation.get("progress_steps", [])],
                error_details=sync_operation.get("error_details")
            )
            
        except Exception as e:
            logger.error(f"Error getting sync status {sync_id}: {e}")
            return None


class PreferenceAuditor:
    """
    Audit trail management for preference changes
    
    Provides comprehensive audit logging with actor tracking,
    change details, and compliance reporting capabilities.
    """
    
    def __init__(self, collection: Collection):
        """Initialize preference auditor with database collection"""
        self.collection = collection
        logger.debug("PreferenceAuditor initialized")
    
    async def log_preference_change(
        self,
        user_id: str,
        change_type: PreferenceChangeType,
        actor_id: str,
        old_value: Optional[Any] = None,
        new_value: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Log a preference change for audit trail
        
        Args:
            user_id: User whose preferences changed
            change_type: Type of preference change
            actor_id: ID of the user/system making the change
            old_value: Previous value (if applicable)
            new_value: New value (if applicable)
            context: Additional context for the change
            
        Returns:
            Audit entry ID
        """
        try:
            audit_entry = {
                "_id": ObjectId(),
                "user_id": user_id,
                "change_type": change_type.value,
                "actor_id": actor_id,
                "old_value": self._sanitize_sensitive_data(old_value),
                "new_value": self._sanitize_sensitive_data(new_value),
                "context": context or {},
                "timestamp": datetime.utcnow(),
                "ip_address": context.get("ip_address") if context else None,
                "user_agent": context.get("user_agent") if context else None
            }
            
            await self.collection.insert_one(audit_entry)
            audit_id = str(audit_entry["_id"])
            
            logger.info(
                f"Logged preference change {change_type.value} for user {user_id} "
                f"by actor {actor_id}"
            )
            
            return audit_id
            
        except Exception as e:
            logger.error(f"Error logging preference change: {e}")
            raise RuntimeError(f"Failed to log preference change: {str(e)}")
    
    async def get_user_audit_history(
        self,
        user_id: str,
        limit: int = 100,
        start_date: Optional[datetime] = None
    ) -> List[PreferenceAuditEntry]:
        """
        Get audit history for a specific user
        
        Args:
            user_id: User ID for audit history
            limit: Maximum number of entries to return
            start_date: Optional start date for filtering
            
        Returns:
            List of audit entries for the user
        """
        try:
            query = {"user_id": user_id}
            
            if start_date:
                query["timestamp"] = {"$gte": start_date}
            
            cursor = self.collection.find(query).sort("timestamp", -1).limit(limit)
            audit_entries = await cursor.to_list(length=limit)
            
            return [
                PreferenceAuditEntry(
                    id=str(entry["_id"]),
                    user_id=entry["user_id"],
                    change_type=entry["change_type"],
                    actor_id=entry["actor_id"],
                    old_value=entry.get("old_value"),
                    new_value=entry.get("new_value"),
                    context=entry.get("context", {}),
                    timestamp=entry["timestamp"]
                )
                for entry in audit_entries
            ]
            
        except Exception as e:
            logger.error(f"Error getting audit history for user {user_id}: {e}")
            raise RuntimeError(f"Failed to get audit history: {str(e)}")
    
    def _sanitize_sensitive_data(self, data: Any) -> Any:
        """
        Sanitize sensitive data for audit logging
        
        Removes or masks sensitive information like API keys,
        passwords, and personal data for compliance.
        """
        if isinstance(data, dict):
            sanitized = {}
            sensitive_keys = {
                "password", "api_key", "secret", "token", "webhook_secret",
                "auth_token", "private_key", "ssn", "credit_card"
            }
            
            for key, value in data.items():
                if any(sensitive in key.lower() for sensitive in sensitive_keys):
                    sanitized[key] = "[REDACTED]"
                elif isinstance(value, (dict, list)):
                    sanitized[key] = self._sanitize_sensitive_data(value)
                else:
                    sanitized[key] = value
            
            return sanitized
        
        elif isinstance(data, list):
            return [self._sanitize_sensitive_data(item) for item in data]
        
        return data


class NotificationPreferenceSyncService:
    """
    Core service for notification preference synchronization and management
    
    Provides comprehensive preference sync capabilities including validation,
    user context integration, audit trail management, and impact analysis.
    """
    
    def __init__(
        self,
        preferences_collection: Collection,
        sync_status_collection: Collection,
        audit_collection: Collection,
        user_context_service=None
    ):
        """
        Initialize the preference sync service
        
        Args:
            preferences_collection: MongoDB collection for user preferences
            sync_status_collection: Collection for sync operation tracking
            audit_collection: Collection for audit trail
            user_context_service: External user context service (optional)
        """
        self.preferences_collection = preferences_collection
        self.user_context_service = user_context_service
        
        self.validator = PreferenceValidator()
        self.sync_tracker = SyncStatusTracker(sync_status_collection)
        self.auditor = PreferenceAuditor(audit_collection)
        
        # Available notification channels (should be configurable)
        self.available_channels = {"email", "slack", "webhook", "sms", "push"}
        
        logger.info("NotificationPreferenceSyncService initialized")
    
    async def sync_preferences(
        self,
        user_id: str,
        sync_request: PreferenceSyncRequest,
        actor_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> PreferenceSyncResponse:
        """
        Synchronize user notification preferences
        
        Validates, applies, and syncs user preference changes with
        comprehensive audit trail and error handling.
        
        Args:
            user_id: User ID for preference sync
            sync_request: Preference sync request with updates
            actor_id: ID of the user/system initiating sync
            context: Additional context (IP, user agent, etc.)
            
        Returns:
            Sync response with operation details and status
        """
        sync_id = None
        
        try:
            # Create sync operation for tracking
            sync_id = await self.sync_tracker.create_sync_operation(
                user_id=user_id,
                operation_type="preference_sync",
                request_data=sync_request.dict(),
                actor_id=actor_id
            )
            
            await self.sync_tracker.update_sync_status(
                sync_id, SyncStatus.IN_PROGRESS, "Starting preference validation", 10
            )
            
            # Get current preferences
            current_preferences = await self._get_user_preferences(user_id)
            
            # Validate preference updates
            validation_errors = await self._validate_sync_request(sync_request)
            if validation_errors:
                await self.sync_tracker.update_sync_status(
                    sync_id, SyncStatus.FAILED, "Validation failed", 0,
                    {"validation_errors": validation_errors}
                )
                
                return PreferenceSyncResponse(
                    sync_id=sync_id,
                    user_id=user_id,
                    status=SyncStatus.FAILED,
                    success=False,
                    validation_errors=validation_errors,
                    changes_applied=[],
                    sync_timestamp=datetime.utcnow()
                )
            
            await self.sync_tracker.update_sync_status(
                sync_id, SyncStatus.IN_PROGRESS, "Validation completed", 30
            )
            
            # Analyze impact of changes
            impact_analysis = self.validator.analyze_preference_impact(
                current_preferences, sync_request.dict()
            )
            
            await self.sync_tracker.update_sync_status(
                sync_id, SyncStatus.IN_PROGRESS, "Applying preference changes", 50
            )
            
            # Apply preference updates
            changes_applied = await self._apply_preference_changes(
                user_id, sync_request, current_preferences, actor_id, context
            )
            
            await self.sync_tracker.update_sync_status(
                sync_id, SyncStatus.IN_PROGRESS, "Syncing with user context", 70
            )
            
            # Sync with external user context if available
            sync_warnings = []
            if self.user_context_service:
                try:
                    await self._sync_with_user_context(user_id, sync_request)
                except Exception as e:
                    logger.warning(f"User context sync failed: {e}")
                    sync_warnings.append(f"User context sync failed: {str(e)}")
            
            await self.sync_tracker.update_sync_status(
                sync_id, SyncStatus.COMPLETED, "Preference sync completed", 100
            )
            
            # Create successful response
            response = PreferenceSyncResponse(
                sync_id=sync_id,
                user_id=user_id,
                status=SyncStatus.COMPLETED,
                success=True,
                validation_errors=[],
                changes_applied=changes_applied,
                sync_timestamp=datetime.utcnow(),
                impact_analysis=impact_analysis,
                warnings=sync_warnings
            )
            
            logger.info(
                f"Successfully synced preferences for user {user_id} "
                f"({len(changes_applied)} changes applied)"
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error syncing preferences for user {user_id}: {e}")
            
            if sync_id:
                await self.sync_tracker.update_sync_status(
                    sync_id, SyncStatus.FAILED, f"Sync failed: {str(e)}", 0,
                    {"error": str(e), "error_type": type(e).__name__}
                )
            
            return PreferenceSyncResponse(
                sync_id=sync_id or "unknown",
                user_id=user_id,
                status=SyncStatus.FAILED,
                success=False,
                validation_errors=[],
                changes_applied=[],
                sync_timestamp=datetime.utcnow(),
                error_message=f"Sync failed: {str(e)}"
            )
    
    async def bulk_update_preferences(
        self,
        bulk_request: BulkPreferenceUpdate,
        actor_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[PreferenceSyncResponse]:
        """
        Perform bulk preference updates for multiple users
        
        Args:
            bulk_request: Bulk update request with user preferences
            actor_id: ID of the user/system initiating bulk update
            context: Additional context for the operation
            
        Returns:
            List of sync responses for each user
        """
        try:
            import asyncio
            
            # Create individual sync requests
            sync_tasks = []
            for user_update in bulk_request.user_updates:
                sync_request = PreferenceSyncRequest(
                    channel_preferences=user_update.channel_preferences,
                    global_settings=user_update.global_settings
                )
                
                task = self.sync_preferences(
                    user_id=user_update.user_id,
                    sync_request=sync_request,
                    actor_id=actor_id,
                    context=context
                )
                sync_tasks.append(task)
            
            # Execute all syncs in parallel
            responses = await asyncio.gather(*sync_tasks, return_exceptions=True)
            
            # Handle any exceptions
            final_responses = []
            for i, response in enumerate(responses):
                if isinstance(response, Exception):
                    user_id = bulk_request.user_updates[i].user_id
                    logger.error(f"Bulk sync failed for user {user_id}: {response}")
                    
                    error_response = PreferenceSyncResponse(
                        sync_id="bulk_error",
                        user_id=user_id,
                        status=SyncStatus.FAILED,
                        success=False,
                        validation_errors=[],
                        changes_applied=[],
                        sync_timestamp=datetime.utcnow(),
                        error_message=f"Bulk sync failed: {str(response)}"
                    )
                    final_responses.append(error_response)
                else:
                    final_responses.append(response)
            
            # Log bulk operation
            successful_syncs = sum(1 for r in final_responses if r.success)
            logger.info(
                f"Completed bulk preference sync: {successful_syncs}/{len(final_responses)} successful"
            )
            
            return final_responses
            
        except Exception as e:
            logger.error(f"Error in bulk preference update: {e}")
            raise RuntimeError(f"Failed to perform bulk preference update: {str(e)}")
    
    async def handle_opt_in_out(
        self,
        user_id: str,
        opt_request: OptInOutRequest,
        actor_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> PreferenceSyncResponse:
        """
        Handle user opt-in or opt-out requests
        
        Args:
            user_id: User ID for opt-in/out operation
            opt_request: Opt-in/out request details
            actor_id: ID of the user/system initiating the request
            context: Additional context for the operation
            
        Returns:
            Sync response with opt-in/out results
        """
        try:
            # Get current preferences
            current_preferences = await self._get_user_preferences(user_id)
            
            # Build sync request based on opt-in/out
            channel_preferences = current_preferences.channel_preferences.copy()
            
            if opt_request.opt_in:
                # Enable specified channels
                for channel in opt_request.channels:
                    if channel in channel_preferences:
                        channel_preferences[channel].enabled = True
                    else:
                        # Create default preference for new channel
                        channel_preferences[channel] = ChannelPreference(
                            enabled=True,
                            priority=NotificationPriority.MEDIUM
                        )
                
                change_type = PreferenceChangeType.OPT_IN
                operation = "opt_in"
                
            else:
                # Disable specified channels
                for channel in opt_request.channels:
                    if channel in channel_preferences:
                        channel_preferences[channel].enabled = False
                
                change_type = PreferenceChangeType.OPT_OUT
                operation = "opt_out"
            
            # Create sync request
            sync_request = PreferenceSyncRequest(
                channel_preferences={
                    ch: pref.dict() for ch, pref in channel_preferences.items()
                },
                global_settings=current_preferences.global_settings
            )
            
            # Log the opt-in/out action
            await self.auditor.log_preference_change(
                user_id=user_id,
                change_type=change_type,
                actor_id=actor_id,
                old_value={"channels": [ch for ch, pref in current_preferences.channel_preferences.items() if pref.enabled]},
                new_value={"channels": opt_request.channels, "opt_in": opt_request.opt_in},
                context=context
            )
            
            # Execute sync
            response = await self.sync_preferences(user_id, sync_request, actor_id, context)
            
            logger.info(f"Processed {operation} for user {user_id} channels: {opt_request.channels}")
            
            return response
            
        except Exception as e:
            logger.error(f"Error handling opt-in/out for user {user_id}: {e}")
            raise RuntimeError(f"Failed to handle opt-in/out request: {str(e)}")
    
    async def get_sync_status(self, sync_id: str) -> Optional[SyncStatusResponse]:
        """Get sync operation status"""
        return await self.sync_tracker.get_sync_status(sync_id)
    
    async def get_user_audit_history(
        self,
        user_id: str,
        limit: int = 50
    ) -> List[PreferenceAuditEntry]:
        """Get audit history for a user"""
        return await self.auditor.get_user_audit_history(user_id, limit)
    
    # Helper methods
    
    async def _get_user_preferences(self, user_id: str) -> UserNotificationPreferencesModel:
        """Get current user preferences or create defaults"""
        try:
            preferences_doc = await self.preferences_collection.find_one({"user_id": user_id})
            
            if preferences_doc:
                return UserNotificationPreferencesModel(**preferences_doc)
            else:
                # Create default preferences
                default_preferences = UserNotificationPreferencesModel(
                    user_id=user_id,
                    channel_preferences={
                        channel: ChannelPreference(
                            enabled=True,
                            priority=NotificationPriority.MEDIUM
                        )
                        for channel in self.available_channels
                    }
                )
                
                # Save default preferences
                await self.preferences_collection.insert_one(default_preferences.dict())
                return default_preferences
                
        except Exception as e:
            logger.error(f"Error getting user preferences for {user_id}: {e}")
            raise
    
    async def _validate_sync_request(self, sync_request: PreferenceSyncRequest) -> List[str]:
        """Validate sync request data"""
        errors = []
        
        # Validate channel preferences
        if sync_request.channel_preferences:
            channel_errors = self.validator.validate_channel_preferences(
                sync_request.channel_preferences, self.available_channels
            )
            errors.extend(channel_errors)
        
        # Validate global settings
        if sync_request.global_settings:
            global_errors = self.validator.validate_global_settings(
                sync_request.global_settings
            )
            errors.extend(global_errors)
        
        return errors
    
    async def _apply_preference_changes(
        self,
        user_id: str,
        sync_request: PreferenceSyncRequest,
        current_preferences: UserNotificationPreferencesModel,
        actor_id: str,
        context: Optional[Dict[str, Any]]
    ) -> List[str]:
        """Apply preference changes and return list of changes made"""
        changes_applied = []
        
        try:
            # Update channel preferences
            if sync_request.channel_preferences:
                for channel, new_pref_data in sync_request.channel_preferences.items():
                    old_pref = current_preferences.channel_preferences.get(channel)
                    new_pref = ChannelPreference(**new_pref_data)
                    
                    # Log specific changes
                    if not old_pref:
                        changes_applied.append(f"Added channel {channel}")
                        await self.auditor.log_preference_change(
                            user_id, PreferenceChangeType.CHANNEL_ENABLED,
                            actor_id, None, new_pref.dict(), context
                        )
                    else:
                        if old_pref.enabled != new_pref.enabled:
                            if new_pref.enabled:
                                changes_applied.append(f"Enabled channel {channel}")
                                await self.auditor.log_preference_change(
                                    user_id, PreferenceChangeType.CHANNEL_ENABLED,
                                    actor_id, old_pref.enabled, new_pref.enabled, context
                                )
                            else:
                                changes_applied.append(f"Disabled channel {channel}")
                                await self.auditor.log_preference_change(
                                    user_id, PreferenceChangeType.CHANNEL_DISABLED,
                                    actor_id, old_pref.enabled, new_pref.enabled, context
                                )
                        
                        if old_pref.priority != new_pref.priority:
                            changes_applied.append(f"Changed {channel} priority to {new_pref.priority}")
                            await self.auditor.log_preference_change(
                                user_id, PreferenceChangeType.PRIORITY_CHANGED,
                                actor_id, old_pref.priority, new_pref.priority, context
                            )
                    
                    current_preferences.channel_preferences[channel] = new_pref
            
            # Update global settings
            if sync_request.global_settings:
                old_settings = current_preferences.global_settings
                current_preferences.global_settings.update(sync_request.global_settings)
                
                for key, new_value in sync_request.global_settings.items():
                    old_value = old_settings.get(key)
                    if old_value != new_value:
                        changes_applied.append(f"Changed global setting {key}")
                        await self.auditor.log_preference_change(
                            user_id, PreferenceChangeType.SYNC_CONFIGURATION,
                            actor_id, old_value, new_value, context
                        )
            
            # Update last sync timestamp
            current_preferences.last_updated = datetime.utcnow()
            current_preferences.last_sync_status = SyncStatus.COMPLETED.value
            
            # Save updated preferences
            await self.preferences_collection.replace_one(
                {"user_id": user_id},
                current_preferences.dict(),
                upsert=True
            )
            
            return changes_applied
            
        except Exception as e:
            logger.error(f"Error applying preference changes for user {user_id}: {e}")
            raise
    
    async def _sync_with_user_context(
        self,
        user_id: str,
        sync_request: PreferenceSyncRequest
    ) -> None:
        """Sync preferences with external user context service"""
        if not self.user_context_service:
            return
        
        try:
            # Extract relevant data for user context
            context_data = {
                "notification_preferences": {
                    "channels_enabled": [
                        ch for ch, pref in sync_request.channel_preferences.items()
                        if pref.get("enabled", True)
                    ] if sync_request.channel_preferences else [],
                    "global_settings": sync_request.global_settings or {},
                    "last_updated": datetime.utcnow().isoformat()
                }
            }
            
            # Call user context service
            await self.user_context_service.update_user_context(user_id, context_data)
            
            logger.debug(f"Synced preferences with user context for user {user_id}")
            
        except Exception as e:
            logger.warning(f"Failed to sync with user context for user {user_id}: {e}")
            raise


# Export the service class and related models
__all__ = [
    "NotificationPreferenceSyncService",
    "PreferenceValidator",
    "SyncStatusTracker",
    "PreferenceAuditor",
    "SyncStatus",
    "PreferenceChangeType"
] 
"""
Notification Module - MongoDB Collection Setup

Comprehensive MongoDB collection setup with optimized indexes, TTL policies,
and performance configurations for the notification system.
"""

import asyncio
from datetime import timedelta
from typing import Dict, List, Any, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo import IndexModel, ASCENDING, DESCENDING, TEXT
from pymongo.errors import CollectionInvalid, OperationFailure

from ...config.logging import get_logger

logger = get_logger(__name__)


class NotificationCollectionManager:
    """
    Manages MongoDB collections and indexes for the notification system.
    
    Provides centralized setup, optimization, and maintenance for all
    notification-related database collections.
    """
    
    def __init__(self, database: AsyncIOMotorDatabase):
        """
        Initialize collection manager.
        
        Args:
            database: MongoDB database instance
        """
        self.database = database
        self.logger = logger.bind(component="NotificationCollectionManager")
        
        # Collection references
        self.notifications_collection = database.notifications
        self.preferences_collection = database.user_notification_preferences
        self.history_collection = database.notification_delivery_history
    
    async def setup_all_collections(self) -> Dict[str, bool]:
        """
        Set up all notification collections with indexes and configurations.
        
        Returns:
            Dict[str, bool]: Success status for each collection setup
        """
        results = {}
        
        try:
            self.logger.info("Starting notification collections setup")
            
            # Setup individual collections
            results["notifications"] = await self._setup_notifications_collection()
            results["preferences"] = await self._setup_preferences_collection()
            results["history"] = await self._setup_history_collection()
            
            # Verify setup
            total_setup = len(results)
            successful_setup = sum(1 for success in results.values() if success)
            
            self.logger.info(
                "Notification collections setup completed",
                total_collections=total_setup,
                successful_setups=successful_setup,
                results=results
            )
            
            return results
            
        except Exception as e:
            self.logger.error(
                "Failed to setup notification collections",
                error=str(e),
                exc_info=True
            )
            raise RuntimeError(f"Collection setup failed: {str(e)}") from e
    
    async def _setup_notifications_collection(self) -> bool:
        """Setup notifications collection with indexes and TTL."""
        try:
            self.logger.info("Setting up notifications collection")
            
            # Create collection if it doesn't exist
            try:
                await self.database.create_collection("notifications")
            except CollectionInvalid:
                # Collection already exists
                pass
            
            # Define indexes for notifications collection
            indexes = [
                # Primary query indexes
                IndexModel(
                    [("notification_id", ASCENDING)],
                    unique=True,
                    name="idx_notification_id_unique"
                ),
                IndexModel(
                    [("created_by", ASCENDING)],
                    name="idx_created_by"
                ),
                IndexModel(
                    [("status", ASCENDING)],
                    name="idx_status"
                ),
                IndexModel(
                    [("type", ASCENDING)],
                    name="idx_type"
                ),
                IndexModel(
                    [("priority", ASCENDING)],
                    name="idx_priority"
                ),
                
                # Compound indexes for common queries
                IndexModel(
                    [("created_by", ASCENDING), ("status", ASCENDING)],
                    name="idx_created_by_status"
                ),
                IndexModel(
                    [("type", ASCENDING), ("priority", ASCENDING)],
                    name="idx_type_priority"
                ),
                IndexModel(
                    [("status", ASCENDING), ("created_at", DESCENDING)],
                    name="idx_status_created_at"
                ),
                
                # Scheduling and processing indexes
                IndexModel(
                    [("scheduled_at", ASCENDING)],
                    name="idx_scheduled_at",
                    sparse=True  # Only index documents with scheduled_at field
                ),
                IndexModel(
                    [("expires_at", ASCENDING)],
                    name="idx_expires_at",
                    sparse=True
                ),
                
                # Recipient-based queries
                IndexModel(
                    [("recipients.user_id", ASCENDING)],
                    name="idx_recipients_user_id"
                ),
                IndexModel(
                    [("recipients.user_id", ASCENDING), ("status", ASCENDING)],
                    name="idx_recipients_user_id_status"
                ),
                
                # Channel and correlation tracking
                IndexModel(
                    [("channels", ASCENDING)],
                    name="idx_channels"
                ),
                IndexModel(
                    [("correlation_id", ASCENDING)],
                    name="idx_correlation_id",
                    sparse=True
                ),
                IndexModel(
                    [("source_service", ASCENDING)],
                    name="idx_source_service"
                ),
                
                # Time-based queries and cleanup
                IndexModel(
                    [("created_at", DESCENDING)],
                    name="idx_created_at_desc"
                ),
                IndexModel(
                    [("sent_at", ASCENDING)],
                    name="idx_sent_at",
                    sparse=True
                ),
                IndexModel(
                    [("delivered_at", ASCENDING)],
                    name="idx_delivered_at",
                    sparse=True
                ),
                
                # TTL index for automatic cleanup of old notifications
                IndexModel(
                    [("created_at", ASCENDING)],
                    name="idx_ttl_cleanup",
                    expireAfterSeconds=int(timedelta(days=90).total_seconds())  # 90 days retention
                ),
                
                # Text search index for content search
                IndexModel(
                    [("title", TEXT), ("content.message", TEXT)],
                    name="idx_text_search",
                    default_language="english"
                )
            ]
            
            # Create indexes
            await self.notifications_collection.create_indexes(indexes)
            
            self.logger.info(
                "Notifications collection setup completed",
                indexes_created=len(indexes)
            )
            return True
            
        except Exception as e:
            self.logger.error(
                "Failed to setup notifications collection",
                error=str(e),
                exc_info=True
            )
            return False
    
    async def _setup_preferences_collection(self) -> bool:
        """Setup user notification preferences collection with indexes."""
        try:
            self.logger.info("Setting up user notification preferences collection")
            
            # Create collection if it doesn't exist
            try:
                await self.database.create_collection("user_notification_preferences")
            except CollectionInvalid:
                # Collection already exists
                pass
            
            # Define indexes for preferences collection
            indexes = [
                # Primary key
                IndexModel(
                    [("user_id", ASCENDING)],
                    unique=True,
                    name="idx_user_id_unique"
                ),
                
                # Settings queries
                IndexModel(
                    [("global_enabled", ASCENDING)],
                    name="idx_global_enabled"
                ),
                IndexModel(
                    [("digest_enabled", ASCENDING)],
                    name="idx_digest_enabled"
                ),
                IndexModel(
                    [("digest_frequency", ASCENDING)],
                    name="idx_digest_frequency"
                ),
                
                # Channel preference queries
                IndexModel(
                    [("channel_preferences.channel", ASCENDING)],
                    name="idx_channel_preferences_channel"
                ),
                IndexModel(
                    [("channel_preferences.enabled", ASCENDING)],
                    name="idx_channel_preferences_enabled"
                ),
                
                # Type preference queries
                IndexModel(
                    [("type_preferences.type", ASCENDING)],
                    name="idx_type_preferences_type"
                ),
                IndexModel(
                    [("type_preferences.enabled", ASCENDING)],
                    name="idx_type_preferences_enabled"
                ),
                
                # Quiet hours queries
                IndexModel(
                    [("quiet_hours.enabled", ASCENDING)],
                    name="idx_quiet_hours_enabled"
                ),
                IndexModel(
                    [("quiet_hours.timezone", ASCENDING)],
                    name="idx_quiet_hours_timezone"
                ),
                
                # Metadata
                IndexModel(
                    [("created_at", DESCENDING)],
                    name="idx_created_at_desc"
                ),
                IndexModel(
                    [("updated_at", DESCENDING)],
                    name="idx_updated_at_desc",
                    sparse=True
                ),
                IndexModel(
                    [("last_updated_by", ASCENDING)],
                    name="idx_last_updated_by"
                ),
                
                # Compound queries for preferences management
                IndexModel(
                    [("global_enabled", ASCENDING), ("digest_enabled", ASCENDING)],
                    name="idx_global_digest_enabled"
                )
            ]
            
            # Create indexes
            await self.preferences_collection.create_indexes(indexes)
            
            self.logger.info(
                "User notification preferences collection setup completed",
                indexes_created=len(indexes)
            )
            return True
            
        except Exception as e:
            self.logger.error(
                "Failed to setup preferences collection",
                error=str(e),
                exc_info=True
            )
            return False
    
    async def _setup_history_collection(self) -> bool:
        """Setup notification delivery history collection with indexes and TTL."""
        try:
            self.logger.info("Setting up notification delivery history collection")
            
            # Create collection if it doesn't exist
            try:
                await self.database.create_collection("notification_delivery_history")
            except CollectionInvalid:
                # Collection already exists
                pass
            
            # Define indexes for history collection
            indexes = [
                # Primary queries
                IndexModel(
                    [("notification_id", ASCENDING)],
                    name="idx_notification_id"
                ),
                IndexModel(
                    [("user_id", ASCENDING)],
                    name="idx_user_id"
                ),
                
                # Status and delivery tracking
                IndexModel(
                    [("current_status", ASCENDING)],
                    name="idx_current_status"
                ),
                IndexModel(
                    [("notification_type", ASCENDING)],
                    name="idx_notification_type"
                ),
                IndexModel(
                    [("priority", ASCENDING)],
                    name="idx_priority"
                ),
                
                # Channel tracking
                IndexModel(
                    [("channels_attempted", ASCENDING)],
                    name="idx_channels_attempted"
                ),
                IndexModel(
                    [("successful_channels", ASCENDING)],
                    name="idx_successful_channels"
                ),
                
                # Compound indexes for common queries
                IndexModel(
                    [("user_id", ASCENDING), ("current_status", ASCENDING)],
                    name="idx_user_id_status"
                ),
                IndexModel(
                    [("user_id", ASCENDING), ("notification_type", ASCENDING)],
                    name="idx_user_id_type"
                ),
                IndexModel(
                    [("user_id", ASCENDING), ("created_at", DESCENDING)],
                    name="idx_user_id_created_at"
                ),
                IndexModel(
                    [("notification_id", ASCENDING), ("user_id", ASCENDING)],
                    name="idx_notification_id_user_id"
                ),
                
                # Performance and metrics queries
                IndexModel(
                    [("source_service", ASCENDING)],
                    name="idx_source_service"
                ),
                IndexModel(
                    [("escalated", ASCENDING)],
                    name="idx_escalated"
                ),
                IndexModel(
                    [("manual_intervention", ASCENDING)],
                    name="idx_manual_intervention"
                ),
                
                # Time-based queries
                IndexModel(
                    [("created_at", DESCENDING)],
                    name="idx_created_at_desc"
                ),
                IndexModel(
                    [("first_attempt_at", ASCENDING)],
                    name="idx_first_attempt_at",
                    sparse=True
                ),
                IndexModel(
                    [("last_attempt_at", ASCENDING)],
                    name="idx_last_attempt_at",
                    sparse=True
                ),
                IndexModel(
                    [("final_delivery_at", ASCENDING)],
                    name="idx_final_delivery_at",
                    sparse=True
                ),
                
                # Analytics and reporting indexes
                IndexModel(
                    [("notification_type", ASCENDING), ("current_status", ASCENDING), ("created_at", DESCENDING)],
                    name="idx_analytics_type_status_time"
                ),
                IndexModel(
                    [("source_service", ASCENDING), ("current_status", ASCENDING)],
                    name="idx_source_service_status"
                ),
                IndexModel(
                    [("channels_attempted", ASCENDING), ("current_status", ASCENDING)],
                    name="idx_channels_status"
                ),
                
                # Delivery attempt tracking (nested array queries)
                IndexModel(
                    [("delivery_attempts.channel", ASCENDING)],
                    name="idx_delivery_attempts_channel"
                ),
                IndexModel(
                    [("delivery_attempts.status", ASCENDING)],
                    name="idx_delivery_attempts_status"
                ),
                IndexModel(
                    [("delivery_attempts.provider", ASCENDING)],
                    name="idx_delivery_attempts_provider",
                    sparse=True
                ),
                
                # TTL index for automatic cleanup of old history records
                IndexModel(
                    [("created_at", ASCENDING)],
                    name="idx_ttl_history_cleanup",
                    expireAfterSeconds=int(timedelta(days=365).total_seconds())  # 1 year retention
                )
            ]
            
            # Create indexes
            await self.history_collection.create_indexes(indexes)
            
            self.logger.info(
                "Notification delivery history collection setup completed",
                indexes_created=len(indexes)
            )
            return True
            
        except Exception as e:
            self.logger.error(
                "Failed to setup history collection",
                error=str(e),
                exc_info=True
            )
            return False
    
    async def verify_indexes(self) -> Dict[str, List[str]]:
        """
        Verify that all required indexes exist.
        
        Returns:
            Dict containing index information for each collection
        """
        try:
            results = {}
            
            # Check notifications collection indexes
            notifications_indexes = await self.notifications_collection.list_indexes().to_list(length=None)
            results["notifications"] = [idx["name"] for idx in notifications_indexes]
            
            # Check preferences collection indexes
            preferences_indexes = await self.preferences_collection.list_indexes().to_list(length=None)
            results["preferences"] = [idx["name"] for idx in preferences_indexes]
            
            # Check history collection indexes
            history_indexes = await self.history_collection.list_indexes().to_list(length=None)
            results["history"] = [idx["name"] for idx in history_indexes]
            
            self.logger.info(
                "Index verification completed",
                notifications_indexes=len(results["notifications"]),
                preferences_indexes=len(results["preferences"]),
                history_indexes=len(results["history"])
            )
            
            return results
            
        except Exception as e:
            self.logger.error(
                "Failed to verify indexes",
                error=str(e),
                exc_info=True
            )
            raise RuntimeError(f"Index verification failed: {str(e)}") from e
    
    async def drop_all_indexes(self) -> Dict[str, bool]:
        """
        Drop all indexes (except _id) for maintenance/rebuilding.
        
        Returns:
            Dict[str, bool]: Success status for each collection
        """
        results = {}
        
        try:
            self.logger.warning("Dropping all notification indexes for rebuild")
            
            # Drop indexes for each collection (keeps _id index)
            collections = [
                ("notifications", self.notifications_collection),
                ("preferences", self.preferences_collection),
                ("history", self.history_collection)
            ]
            
            for name, collection in collections:
                try:
                    await collection.drop_indexes()
                    results[name] = True
                    self.logger.info(f"Dropped indexes for {name} collection")
                except Exception as e:
                    results[name] = False
                    self.logger.error(f"Failed to drop indexes for {name} collection", error=str(e))
            
            return results
            
        except Exception as e:
            self.logger.error(
                "Failed to drop indexes",
                error=str(e),
                exc_info=True
            )
            raise RuntimeError(f"Index dropping failed: {str(e)}") from e
    
    async def get_collection_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get statistics for all notification collections.
        
        Returns:
            Dict containing statistics for each collection
        """
        try:
            stats = {}
            
            collections = [
                ("notifications", "notifications"),
                ("preferences", "user_notification_preferences"),
                ("history", "notification_delivery_history")
            ]
            
            for name, collection_name in collections:
                try:
                    collection_stats = await self.database.command("collStats", collection_name)
                    stats[name] = {
                        "document_count": collection_stats.get("count", 0),
                        "storage_size": collection_stats.get("storageSize", 0),
                        "total_index_size": collection_stats.get("totalIndexSize", 0),
                        "index_count": collection_stats.get("nindexes", 0),
                        "avg_document_size": collection_stats.get("avgObjSize", 0)
                    }
                except Exception as e:
                    stats[name] = {"error": str(e)}
            
            return stats
            
        except Exception as e:
            self.logger.error(
                "Failed to get collection stats",
                error=str(e),
                exc_info=True
            )
            return {}


async def setup_notification_collections(database: AsyncIOMotorDatabase) -> Dict[str, bool]:
    """
    Convenience function to set up all notification collections.
    
    Args:
        database: MongoDB database instance
        
    Returns:
        Dict[str, bool]: Success status for each collection
    """
    manager = NotificationCollectionManager(database)
    results = await manager.setup_all_collections()
    return results


async def create_notification_indexes(database: AsyncIOMotorDatabase) -> Dict[str, bool]:
    """
    Convenience function to create notification indexes.
    
    Args:
        database: MongoDB database instance
        
    Returns:
        Dict[str, bool]: Success status for each collection
    """
    manager = NotificationCollectionManager(database)
    return await manager.setup_all_collections()


async def bootstrap_notification_database(database: AsyncIOMotorDatabase) -> Dict[str, Any]:
    """
    Bootstrap the notification database with all required setup.
    
    This function should be called during application startup to ensure
    all notification collections and indexes are properly configured.
    
    Args:
        database: MongoDB database instance
        
    Returns:
        Dict containing setup results and statistics
    """
    logger_bootstrap = logger.bind(component="NotificationBootstrap")
    
    try:
        logger_bootstrap.info("Starting notification database bootstrap")
        
        # Initialize collection manager
        manager = NotificationCollectionManager(database)
        
        # Setup all collections
        setup_results = await manager.setup_all_collections()
        
        # Verify indexes
        index_verification = await manager.verify_indexes()
        
        # Get collection statistics
        collection_stats = await manager.get_collection_stats()
        
        bootstrap_result = {
            "success": all(setup_results.values()),
            "setup_results": setup_results,
            "index_counts": {
                collection: len(indexes) 
                for collection, indexes in index_verification.items()
            },
            "collection_stats": collection_stats,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        if bootstrap_result["success"]:
            logger_bootstrap.info(
                "Notification database bootstrap completed successfully",
                **bootstrap_result
            )
        else:
            logger_bootstrap.error(
                "Notification database bootstrap completed with errors",
                **bootstrap_result
            )
        
        return bootstrap_result
        
    except Exception as e:
        logger_bootstrap.error(
            "Notification database bootstrap failed",
            error=str(e),
            exc_info=True
        )
        return {
            "success": False,
            "error": str(e),
            "timestamp": asyncio.get_event_loop().time()
        } 
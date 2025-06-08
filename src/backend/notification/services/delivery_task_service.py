"""
IntelliBrowse Notification Engine - Delivery Task Service

This module provides the core delivery task management functionality for the 
notification engine, handling notification lifecycle management, status tracking,
and audit trail maintenance for the background delivery daemon.

Classes:
    - DeliveryTaskService: Core service for delivery task management
    - DeliveryResult: Result object for delivery attempt tracking
    - NotificationQuery: Query builder for pending notification retrieval
    - AuditLogger: Structured audit logging for delivery attempts

Author: IntelliBrowse Team
Created: Phase 5 - Background Tasks & Delivery Daemon Implementation
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

from bson import ObjectId
from pydantic import BaseModel, Field
from pymongo.collection import Collection
from pymongo.errors import PyMongoError
from pymongo import ASCENDING, DESCENDING

# Import notification models
from ..models.notification_model import NotificationModel, NotificationStatus
from ..models.notification_delivery_history import NotificationDeliveryHistory, DeliveryStatus

# Import retry utilities
from ..utils.retry import RetryPolicy, RetryableOperation, DEFAULT_RETRY_POLICY

# Configure logging
logger = logging.getLogger(__name__)


class DeliveryResultStatus(str, Enum):
    """Enumeration of delivery result statuses"""
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    RETRY_REQUIRED = "retry_required"


class DeliveryResult(BaseModel):
    """
    Result object for notification delivery attempts
    
    Contains comprehensive information about delivery attempt results,
    including status, timing, error details, and retry recommendations.
    """
    
    notification_id: str = Field(..., description="Notification identifier")
    user_id: str = Field(..., description="Target user identifier")
    channel: str = Field(..., description="Delivery channel used")
    status: DeliveryResultStatus = Field(..., description="Delivery result status")
    
    # Timing information
    attempt_timestamp: datetime = Field(..., description="When delivery was attempted")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")
    
    # Success/failure details
    success: bool = Field(..., description="Whether delivery was successful")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    error_code: Optional[str] = Field(None, description="Error code if available")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    
    # Delivery metadata
    external_id: Optional[str] = Field(None, description="External service delivery ID")
    response_data: Optional[Dict[str, Any]] = Field(None, description="Response data from delivery service")
    
    # Retry information
    attempt_number: int = Field(..., description="Current attempt number")
    max_attempts: int = Field(..., description="Maximum allowed attempts")
    should_retry: bool = Field(..., description="Whether this delivery should be retried")
    next_retry_at: Optional[datetime] = Field(None, description="When next retry should occur")
    
    class Config:
        """Pydantic model configuration"""
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class NotificationQuery(BaseModel):
    """
    Query builder for pending notification retrieval
    
    Provides flexible query building for fetching pending notifications
    with various filtering and sorting options.
    """
    
    limit: int = Field(default=100, ge=1, le=1000, description="Maximum notifications to retrieve")
    offset: int = Field(default=0, ge=0, description="Offset for pagination")
    
    # Time-based filtering
    pending_since: Optional[datetime] = Field(None, description="Fetch notifications pending since this time")
    created_before: Optional[datetime] = Field(None, description="Fetch notifications created before this time")
    
    # Status filtering
    statuses: List[NotificationStatus] = Field(
        default=[NotificationStatus.PENDING],
        description="Notification statuses to include"
    )
    
    # Priority filtering
    min_priority: Optional[str] = Field(None, description="Minimum priority level")
    
    # Channel filtering
    channels: Optional[List[str]] = Field(None, description="Specific channels to include")
    
    # Retry filtering
    max_retry_count: Optional[int] = Field(None, description="Maximum retry count for inclusion")
    
    def build_mongo_query(self) -> Dict[str, Any]:
        """
        Build MongoDB query from parameters
        
        Returns:
            MongoDB query dictionary
        """
        query = {}
        
        # Status filtering
        if self.statuses:
            if len(self.statuses) == 1:
                query["status"] = self.statuses[0].value
            else:
                query["status"] = {"$in": [status.value for status in self.statuses]}
        
        # Time-based filtering
        time_conditions = {}
        if self.pending_since:
            time_conditions["$gte"] = self.pending_since
        if self.created_before:
            time_conditions["$lte"] = self.created_before
        
        if time_conditions:
            query["created_at"] = time_conditions
        
        # Priority filtering
        if self.min_priority:
            # Assuming priority order: low < medium < high < critical
            priority_order = {"low": 1, "medium": 2, "high": 3, "critical": 4}
            min_value = priority_order.get(self.min_priority, 1)
            query["priority_value"] = {"$gte": min_value}
        
        # Channel filtering
        if self.channels:
            query["channels"] = {"$in": self.channels}
        
        return query


class AuditLogger:
    """
    Structured audit logging for delivery attempts
    
    Provides comprehensive audit trail logging for notification delivery
    attempts with structured data and proper correlation.
    """
    
    def __init__(self, audit_collection: Collection):
        """
        Initialize audit logger
        
        Args:
            audit_collection: MongoDB collection for audit logs
        """
        self.audit_collection = audit_collection
        self.logger = logger.bind(component="AuditLogger")
    
    async def log_delivery_attempt(
        self,
        notification_id: str,
        user_id: str,
        channel: str,
        result: DeliveryResult,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Log a delivery attempt with comprehensive details
        
        Args:
            notification_id: Notification identifier
            user_id: Target user identifier
            channel: Delivery channel
            result: Delivery result object
            context: Additional context information
            
        Returns:
            Audit log entry ID
        """
        audit_id = f"audit_{uuid.uuid4().hex[:12]}"
        
        try:
            audit_entry = {
                "audit_id": audit_id,
                "notification_id": notification_id,
                "user_id": user_id,
                "channel": channel,
                "timestamp": datetime.now(timezone.utc),
                
                # Delivery details
                "delivery_status": result.status.value,
                "success": result.success,
                "attempt_number": result.attempt_number,
                "processing_time_ms": result.processing_time_ms,
                
                # Error details (if any)
                "error_message": result.error_message,
                "error_code": result.error_code,
                "error_details": result.error_details,
                
                # External service details
                "external_id": result.external_id,
                "response_data": result.response_data,
                
                # Retry information
                "should_retry": result.should_retry,
                "next_retry_at": result.next_retry_at,
                
                # Context
                "context": context or {},
                
                # Metadata
                "source": "delivery_daemon",
                "audit_version": "1.0"
            }
            
            await self.audit_collection.insert_one(audit_entry)
            
            self.logger.info(
                "Delivery attempt logged",
                audit_id=audit_id,
                notification_id=notification_id,
                user_id=user_id,
                channel=channel,
                status=result.status.value,
                success=result.success
            )
            
            return audit_id
            
        except Exception as e:
            self.logger.error(
                "Failed to log delivery attempt",
                notification_id=notification_id,
                user_id=user_id,
                channel=channel,
                error=str(e),
                exc_info=True
            )
            raise


class DeliveryTaskService:
    """
    Core service for delivery task management
    
    Provides comprehensive functionality for managing notification delivery
    lifecycle, including pending notification retrieval, status updates,
    and retry policy management.
    """
    
    def __init__(
        self,
        notifications_collection: Collection,
        history_collection: Collection,
        audit_collection: Collection,
        default_retry_policy: Optional[RetryPolicy] = None
    ):
        """
        Initialize delivery task service
        
        Args:
            notifications_collection: MongoDB collection for notifications
            history_collection: MongoDB collection for delivery history
            audit_collection: MongoDB collection for audit logs
            default_retry_policy: Default retry policy for deliveries
        """
        self.notifications_collection = notifications_collection
        self.history_collection = history_collection
        self.audit_collection = audit_collection
        self.default_retry_policy = default_retry_policy or DEFAULT_RETRY_POLICY
        
        self.audit_logger = AuditLogger(audit_collection)
        self.logger = logger.bind(service="DeliveryTaskService")
    
    async def get_pending_notifications(
        self,
        query: Optional[NotificationQuery] = None
    ) -> List[NotificationModel]:
        """
        Retrieve pending notifications for delivery
        
        Args:
            query: Query parameters for filtering notifications
            
        Returns:
            List of pending notification models
        """
        if query is None:
            query = NotificationQuery()
        
        try:
            # Build MongoDB query
            mongo_query = query.build_mongo_query()
            
            self.logger.debug(
                "Fetching pending notifications",
                query=mongo_query,
                limit=query.limit,
                offset=query.offset
            )
            
            # Execute query with sorting by creation time (oldest first)
            cursor = self.notifications_collection.find(mongo_query) \
                .sort("created_at", ASCENDING) \
                .skip(query.offset) \
                .limit(query.limit)
            
            notifications = []
            async for doc in cursor:
                try:
                    notification = NotificationModel.from_mongo(doc)
                    if notification:
                        notifications.append(notification)
                except Exception as e:
                    self.logger.warning(
                        "Failed to parse notification from MongoDB",
                        doc_id=str(doc.get("_id")),
                        error=str(e)
                    )
                    continue
            
            self.logger.info(
                "Retrieved pending notifications",
                count=len(notifications),
                query_limit=query.limit
            )
            
            return notifications
            
        except PyMongoError as e:
            self.logger.error(
                "Database error retrieving pending notifications",
                error=str(e),
                exc_info=True
            )
            raise
        except Exception as e:
            self.logger.error(
                "Unexpected error retrieving pending notifications",
                error=str(e),
                exc_info=True
            )
            raise
    
    async def mark_as_delivered(
        self,
        notification_id: str,
        user_id: str,
        channel: str,
        result: DeliveryResult,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Mark notification as successfully delivered
        
        Args:
            notification_id: Notification identifier
            user_id: Target user identifier
            channel: Delivery channel
            result: Delivery result object
            context: Additional context information
            
        Returns:
            True if successfully marked, False otherwise
        """
        try:
            # Update notification status
            update_result = await self.notifications_collection.update_one(
                {"notification_id": notification_id},
                {
                    "$set": {
                        "status": NotificationStatus.DELIVERED.value,
                        "delivered_at": datetime.now(timezone.utc),
                        "last_updated": datetime.now(timezone.utc)
                    }
                }
            )
            
            if update_result.matched_count == 0:
                self.logger.warning(
                    "Notification not found for delivery marking",
                    notification_id=notification_id
                )
                return False
            
            # Update delivery history
            await self.history_collection.update_one(
                {
                    "notification_id": notification_id,
                    "user_id": user_id
                },
                {
                    "$set": {
                        "delivery_status": DeliveryStatus.DELIVERED.value,
                        "delivered_at": datetime.now(timezone.utc),
                        "delivery_channel": channel,
                        "external_id": result.external_id,
                        "processing_time_ms": result.processing_time_ms,
                        "last_updated": datetime.now(timezone.utc)
                    },
                    "$inc": {
                        "delivery_attempts": 1
                    }
                },
                upsert=True
            )
            
            # Log audit trail
            await self.audit_logger.log_delivery_attempt(
                notification_id=notification_id,
                user_id=user_id,
                channel=channel,
                result=result,
                context=context
            )
            
            self.logger.info(
                "Notification marked as delivered",
                notification_id=notification_id,
                user_id=user_id,
                channel=channel,
                processing_time_ms=result.processing_time_ms
            )
            
            return True
            
        except Exception as e:
            self.logger.error(
                "Failed to mark notification as delivered",
                notification_id=notification_id,
                user_id=user_id,
                channel=channel,
                error=str(e),
                exc_info=True
            )
            return False
    
    async def mark_as_failed(
        self,
        notification_id: str,
        user_id: str,
        channel: str,
        result: DeliveryResult,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Mark notification delivery as failed
        
        Args:
            notification_id: Notification identifier
            user_id: Target user identifier
            channel: Delivery channel
            result: Delivery result object
            context: Additional context information
            
        Returns:
            True if successfully marked, False otherwise
        """
        try:
            # Determine final status based on retry eligibility
            final_status = NotificationStatus.FAILED if not result.should_retry else NotificationStatus.PENDING
            
            # Update notification status
            update_data = {
                "last_updated": datetime.now(timezone.utc),
                "last_error": result.error_message
            }
            
            if not result.should_retry:
                update_data["status"] = final_status.value
                update_data["failed_at"] = datetime.now(timezone.utc)
            
            if result.next_retry_at:
                update_data["next_retry_at"] = result.next_retry_at
            
            await self.notifications_collection.update_one(
                {"notification_id": notification_id},
                {"$set": update_data}
            )
            
            # Update delivery history
            history_update = {
                "delivery_status": DeliveryStatus.FAILED.value if not result.should_retry else DeliveryStatus.PENDING.value,
                "last_error": result.error_message,
                "error_code": result.error_code,
                "error_details": result.error_details,
                "last_attempt_at": datetime.now(timezone.utc),
                "processing_time_ms": result.processing_time_ms,
                "last_updated": datetime.now(timezone.utc)
            }
            
            if result.next_retry_at:
                history_update["next_retry_at"] = result.next_retry_at
            
            await self.history_collection.update_one(
                {
                    "notification_id": notification_id,
                    "user_id": user_id
                },
                {
                    "$set": history_update,
                    "$inc": {
                        "delivery_attempts": 1,
                        "failure_count": 1
                    }
                },
                upsert=True
            )
            
            # Log audit trail
            await self.audit_logger.log_delivery_attempt(
                notification_id=notification_id,
                user_id=user_id,
                channel=channel,
                result=result,
                context=context
            )
            
            self.logger.warning(
                "Notification marked as failed",
                notification_id=notification_id,
                user_id=user_id,
                channel=channel,
                error_message=result.error_message,
                should_retry=result.should_retry,
                next_retry_at=result.next_retry_at
            )
            
            return True
            
        except Exception as e:
            self.logger.error(
                "Failed to mark notification as failed",
                notification_id=notification_id,
                user_id=user_id,
                channel=channel,
                error=str(e),
                exc_info=True
            )
            return False
    
    async def apply_retry_policy(
        self,
        notification_id: str,
        current_attempt: int,
        last_error: Exception,
        retry_policy: Optional[RetryPolicy] = None
    ) -> Tuple[bool, Optional[datetime]]:
        """
        Apply retry policy to determine if notification should be retried
        
        Args:
            notification_id: Notification identifier
            current_attempt: Current attempt number
            last_error: Last delivery error
            retry_policy: Retry policy to apply (uses default if None)
            
        Returns:
            Tuple of (should_retry, next_retry_time)
        """
        policy = retry_policy or self.default_retry_policy
        
        try:
            # Check if should retry based on policy
            should_retry = policy.should_retry(current_attempt, last_error)
            
            if not should_retry:
                self.logger.info(
                    "Retry policy determined no retry needed",
                    notification_id=notification_id,
                    current_attempt=current_attempt,
                    max_attempts=policy.max_attempts
                )
                return False, None
            
            # Calculate next retry time
            delay_seconds = policy.calculate_delay(current_attempt + 1)
            next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
            
            self.logger.info(
                "Retry policy applied",
                notification_id=notification_id,
                current_attempt=current_attempt,
                should_retry=should_retry,
                delay_seconds=delay_seconds,
                next_retry_at=next_retry_at
            )
            
            return should_retry, next_retry_at
            
        except Exception as e:
            self.logger.error(
                "Failed to apply retry policy",
                notification_id=notification_id,
                current_attempt=current_attempt,
                error=str(e),
                exc_info=True
            )
            return False, None
    
    async def get_retry_ready_notifications(
        self,
        limit: int = 100
    ) -> List[NotificationModel]:
        """
        Get notifications that are ready for retry
        
        Args:
            limit: Maximum number of notifications to retrieve
            
        Returns:
            List of notifications ready for retry
        """
        try:
            current_time = datetime.now(timezone.utc)
            
            # Query for notifications with retry scheduled in the past
            query = {
                "status": NotificationStatus.PENDING.value,
                "next_retry_at": {"$lte": current_time}
            }
            
            cursor = self.notifications_collection.find(query) \
                .sort("next_retry_at", ASCENDING) \
                .limit(limit)
            
            notifications = []
            async for doc in cursor:
                try:
                    notification = NotificationModel.from_mongo(doc)
                    if notification:
                        notifications.append(notification)
                except Exception as e:
                    self.logger.warning(
                        "Failed to parse retry notification",
                        doc_id=str(doc.get("_id")),
                        error=str(e)
                    )
                    continue
            
            self.logger.info(
                "Retrieved retry-ready notifications",
                count=len(notifications),
                limit=limit
            )
            
            return notifications
            
        except Exception as e:
            self.logger.error(
                "Failed to get retry-ready notifications",
                error=str(e),
                exc_info=True
            )
            return []
    
    async def cleanup_old_audit_logs(
        self,
        retention_days: int = 30
    ) -> int:
        """
        Clean up old audit logs based on retention policy
        
        Args:
            retention_days: Number of days to retain audit logs
            
        Returns:
            Number of audit logs deleted
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
            
            result = await self.audit_collection.delete_many({
                "timestamp": {"$lt": cutoff_date}
            })
            
            deleted_count = result.deleted_count
            
            self.logger.info(
                "Cleaned up old audit logs",
                deleted_count=deleted_count,
                retention_days=retention_days,
                cutoff_date=cutoff_date
            )
            
            return deleted_count
            
        except Exception as e:
            self.logger.error(
                "Failed to cleanup old audit logs",
                retention_days=retention_days,
                error=str(e),
                exc_info=True
            )
            return 0
    
    async def get_delivery_stats(
        self,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get delivery statistics for monitoring
        
        Args:
            hours: Number of hours to look back for statistics
            
        Returns:
            Dictionary containing delivery statistics
        """
        try:
            since_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            
            # Get statistics from audit collection
            pipeline = [
                {
                    "$match": {
                        "timestamp": {"$gte": since_time}
                    }
                },
                {
                    "$group": {
                        "_id": {
                            "status": "$delivery_status",
                            "channel": "$channel"
                        },
                        "count": {"$sum": 1},
                        "avg_processing_time": {"$avg": "$processing_time_ms"}
                    }
                }
            ]
            
            cursor = self.audit_collection.aggregate(pipeline)
            results = await cursor.to_list(length=100)
            
            # Process results into structured format
            stats = {
                "period_hours": hours,
                "since_time": since_time,
                "by_status": {},
                "by_channel": {},
                "totals": {
                    "total_attempts": 0,
                    "successful_deliveries": 0,
                    "failed_deliveries": 0,
                    "average_processing_time_ms": 0
                }
            }
            
            total_processing_time = 0
            total_count = 0
            
            for result in results:
                status = result["_id"]["status"]
                channel = result["_id"]["channel"]
                count = result["count"]
                avg_time = result["avg_processing_time"] or 0
                
                # Update by status
                if status not in stats["by_status"]:
                    stats["by_status"][status] = 0
                stats["by_status"][status] += count
                
                # Update by channel
                if channel not in stats["by_channel"]:
                    stats["by_channel"][channel] = 0
                stats["by_channel"][channel] += count
                
                # Update totals
                total_count += count
                total_processing_time += avg_time * count
                
                if status == "success":
                    stats["totals"]["successful_deliveries"] += count
                else:
                    stats["totals"]["failed_deliveries"] += count
            
            stats["totals"]["total_attempts"] = total_count
            if total_count > 0:
                stats["totals"]["average_processing_time_ms"] = total_processing_time / total_count
                stats["totals"]["success_rate"] = stats["totals"]["successful_deliveries"] / total_count
            else:
                stats["totals"]["success_rate"] = 0
            
            return stats
            
        except Exception as e:
            self.logger.error(
                "Failed to get delivery statistics",
                hours=hours,
                error=str(e),
                exc_info=True
            )
            return {
                "error": "Failed to retrieve statistics",
                "period_hours": hours
            }
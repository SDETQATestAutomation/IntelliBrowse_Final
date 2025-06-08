"""
IntelliBrowse Notification Engine - History Service

This module provides comprehensive notification history management capabilities,
including paginated history retrieval, detailed trace information, and advanced
filtering options for user-scoped notification history access.

Classes:
    - NotificationHistoryService: Core service for history operations
    - HistoryQueryParameters: Pydantic model for query validation
    - HistoryFilterBuilder: Helper for building MongoDB queries
    - HistoryPaginator: Pagination utility for large datasets

Author: IntelliBrowse Team
Created: Phase 3 - History Management Implementation
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

from bson import ObjectId
from pydantic import BaseModel, Field, validator
from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from ..models.notification_delivery_history import NotificationDeliveryHistory
from ..models.user_notification_preferences import UserNotificationPreferencesModel
from ..schemas.notification_history_schemas import (
    NotificationHistoryResponse,
    NotificationHistoryDetailResponse,
    NotificationHistoryListResponse,
    HistoryFilterRequest,
    PaginationMetadata
)

# Configure logging
logger = logging.getLogger(__name__)


class HistorySortOption(str, Enum):
    """Enumeration of valid sorting options for history queries"""
    CREATED_DESC = "created_desc"
    CREATED_ASC = "created_asc"
    STATUS_ASC = "status_asc"
    STATUS_DESC = "status_desc"
    CHANNEL_ASC = "channel_asc"
    CHANNEL_DESC = "channel_desc"


class HistoryQueryParameters(BaseModel):
    """
    Pydantic model for validating and structuring history query parameters
    
    Provides comprehensive validation for all query parameters including
    pagination, filtering, and sorting options with proper data types
    and business rule enforcement.
    """
    
    user_id: str = Field(..., description="User ID for scoping history queries")
    page: int = Field(default=1, ge=1, le=1000, description="Page number (1-based)")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")
    
    # Filtering parameters
    status: Optional[str] = Field(None, description="Filter by delivery status")
    channel: Optional[str] = Field(None, description="Filter by notification channel")
    date_from: Optional[datetime] = Field(None, description="Start date for date range filter")
    date_to: Optional[datetime] = Field(None, description="End date for date range filter")
    priority: Optional[str] = Field(None, description="Filter by notification priority")
    notification_type: Optional[str] = Field(None, description="Filter by notification type")
    
    # Sorting parameters
    sort_by: HistorySortOption = Field(
        default=HistorySortOption.CREATED_DESC,
        description="Sort option for results"
    )
    
    # Search parameters
    search_term: Optional[str] = Field(
        None, 
        max_length=100, 
        description="Search term for notification content"
    )
    
    @validator('user_id')
    def validate_user_id(cls, v):
        """Validate user ID format"""
        if not v or not v.strip():
            raise ValueError("User ID cannot be empty")
        return v.strip()
    
    @validator('date_to')
    def validate_date_range(cls, v, values):
        """Validate that date_to is after date_from if both are provided"""
        if v and 'date_from' in values and values['date_from']:
            if v <= values['date_from']:
                raise ValueError("date_to must be after date_from")
        return v
    
    @validator('search_term')
    def validate_search_term(cls, v):
        """Validate and clean search term"""
        if v:
            cleaned = v.strip()
            if len(cleaned) < 2:
                raise ValueError("Search term must be at least 2 characters")
            return cleaned
        return v


class HistoryFilterBuilder:
    """
    Helper class for building MongoDB query filters from validated parameters
    
    Provides methods to construct complex MongoDB queries with proper
    indexing support and query optimization for efficient history retrieval.
    """
    
    @staticmethod
    def build_query(params: HistoryQueryParameters) -> Dict[str, Any]:
        """
        Build MongoDB query from validated parameters
        
        Args:
            params: Validated query parameters
            
        Returns:
            MongoDB query dictionary optimized for indexed fields
        """
        query = {"user_id": params.user_id}
        
        # Status filter
        if params.status:
            query["delivery_status"] = params.status
        
        # Channel filter
        if params.channel:
            query["channel"] = params.channel
        
        # Priority filter
        if params.priority:
            query["priority"] = params.priority
        
        # Notification type filter
        if params.notification_type:
            query["notification_type"] = params.notification_type
        
        # Date range filter
        if params.date_from or params.date_to:
            date_query = {}
            if params.date_from:
                date_query["$gte"] = params.date_from
            if params.date_to:
                date_query["$lte"] = params.date_to
            query["created_at"] = date_query
        
        # Search term filter (text search on content and subject)
        if params.search_term:
            query["$or"] = [
                {"notification_content.subject": {"$regex": params.search_term, "$options": "i"}},
                {"notification_content.body": {"$regex": params.search_term, "$options": "i"}},
                {"notification_content.message": {"$regex": params.search_term, "$options": "i"}}
            ]
        
        logger.debug(f"Built MongoDB query for user {params.user_id}: {query}")
        return query
    
    @staticmethod
    def build_sort(sort_by: HistorySortOption) -> List[Tuple[str, int]]:
        """
        Build MongoDB sort specification from sort option
        
        Args:
            sort_by: Validated sort option
            
        Returns:
            List of (field, direction) tuples for MongoDB sort
        """
        sort_mapping = {
            HistorySortOption.CREATED_DESC: [("created_at", DESCENDING)],
            HistorySortOption.CREATED_ASC: [("created_at", ASCENDING)],
            HistorySortOption.STATUS_DESC: [("delivery_status", DESCENDING), ("created_at", DESCENDING)],
            HistorySortOption.STATUS_ASC: [("delivery_status", ASCENDING), ("created_at", DESCENDING)],
            HistorySortOption.CHANNEL_DESC: [("channel", DESCENDING), ("created_at", DESCENDING)],
            HistorySortOption.CHANNEL_ASC: [("channel", ASCENDING), ("created_at", DESCENDING)]
        }
        
        return sort_mapping.get(sort_by, [("created_at", DESCENDING)])


class HistoryPaginator:
    """
    Utility class for handling pagination of history results
    
    Provides methods for calculating pagination metadata and applying
    skip/limit operations for efficient large dataset handling.
    """
    
    @staticmethod
    def calculate_pagination(
        total_count: int,
        page: int,
        page_size: int
    ) -> PaginationMetadata:
        """
        Calculate pagination metadata from query results
        
        Args:
            total_count: Total number of matching documents
            page: Current page number (1-based)
            page_size: Number of items per page
            
        Returns:
            Comprehensive pagination metadata
        """
        total_pages = max(1, (total_count + page_size - 1) // page_size)
        has_next = page < total_pages
        has_previous = page > 1
        
        return PaginationMetadata(
            current_page=page,
            page_size=page_size,
            total_items=total_count,
            total_pages=total_pages,
            has_next=has_next,
            has_previous=has_previous,
            next_page=page + 1 if has_next else None,
            previous_page=page - 1 if has_previous else None
        )
    
    @staticmethod
    def calculate_skip_limit(page: int, page_size: int) -> Tuple[int, int]:
        """
        Calculate MongoDB skip and limit values for pagination
        
        Args:
            page: Current page number (1-based)
            page_size: Number of items per page
            
        Returns:
            Tuple of (skip, limit) for MongoDB query
        """
        skip = (page - 1) * page_size
        return skip, page_size


class NotificationHistoryService:
    """
    Core service for notification history management and retrieval
    
    Provides comprehensive history access with user scoping, advanced filtering,
    pagination support, and detailed trace information for audit and debugging.
    """
    
    def __init__(self, collection: Collection):
        """
        Initialize the history service with database collection
        
        Args:
            collection: MongoDB collection for notification history
        """
        self.collection = collection
        self.filter_builder = HistoryFilterBuilder()
        self.paginator = HistoryPaginator()
        
        logger.info("NotificationHistoryService initialized")
    
    async def get_history(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        filters: Optional[HistoryFilterRequest] = None
    ) -> NotificationHistoryListResponse:
        """
        Retrieve paginated notification history for a specific user
        
        Provides comprehensive history access with filtering, sorting, and
        pagination support. All results are scoped to the authenticated user.
        
        Args:
            user_id: User ID for scoping history queries
            page: Page number for pagination (1-based)
            page_size: Number of items per page
            filters: Optional filtering parameters
            
        Returns:
            Paginated list of notification history with metadata
            
        Raises:
            ValueError: For invalid parameters
            RuntimeError: For database errors
        """
        try:
            # Build query parameters
            query_params = HistoryQueryParameters(
                user_id=user_id,
                page=page,
                page_size=page_size,
                **(filters.dict() if filters else {})
            )
            
            # Build MongoDB query and sort
            query = self.filter_builder.build_query(query_params)
            sort_spec = self.filter_builder.build_sort(query_params.sort_by)
            
            # Calculate pagination
            skip, limit = self.paginator.calculate_skip_limit(page, page_size)
            
            # Execute count query for pagination metadata
            total_count = await self._count_documents(query)
            
            # Execute main query with pagination and sorting
            cursor = self.collection.find(query).sort(sort_spec).skip(skip).limit(limit)
            documents = await cursor.to_list(length=limit)
            
            # Convert documents to response models
            history_items = []
            for doc in documents:
                try:
                    history_item = self._document_to_history_response(doc)
                    history_items.append(history_item)
                except Exception as e:
                    logger.warning(f"Failed to convert document {doc.get('_id')} to response: {e}")
                    continue
            
            # Calculate pagination metadata
            pagination = self.paginator.calculate_pagination(total_count, page, page_size)
            
            # Build response
            response = NotificationHistoryListResponse(
                items=history_items,
                pagination=pagination,
                total_count=total_count,
                applied_filters=filters.dict() if filters else {}
            )
            
            logger.info(
                f"Retrieved {len(history_items)} history items for user {user_id} "
                f"(page {page}/{pagination.total_pages})"
            )
            
            return response
            
        except ValueError as e:
            logger.error(f"Invalid parameters for history query: {e}")
            raise
        except PyMongoError as e:
            logger.error(f"Database error during history retrieval: {e}")
            raise RuntimeError(f"Failed to retrieve notification history: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during history retrieval: {e}")
            raise RuntimeError(f"Failed to retrieve notification history: {str(e)}")
    
    async def get_by_id(
        self,
        user_id: str,
        notification_id: str
    ) -> NotificationHistoryDetailResponse:
        """
        Retrieve detailed information for a specific notification
        
        Provides comprehensive trace information including delivery attempts,
        error details, and full payload information for debugging and audit.
        
        Args:
            user_id: User ID for authorization and scoping
            notification_id: Notification ID to retrieve
            
        Returns:
            Detailed notification information with full trace
            
        Raises:
            ValueError: For invalid notification ID format
            NotFoundError: If notification not found or not accessible
            RuntimeError: For database errors
        """
        try:
            # Validate notification ID format
            if not ObjectId.is_valid(notification_id):
                raise ValueError(f"Invalid notification ID format: {notification_id}")
            
            # Build query with user scoping
            query = {
                "_id": ObjectId(notification_id),
                "user_id": user_id
            }
            
            # Execute query
            document = await self._find_one(query)
            if not document:
                raise NotFoundError(
                    f"Notification {notification_id} not found or not accessible"
                )
            
            # Convert to detailed response
            response = self._document_to_detail_response(document)
            
            logger.info(
                f"Retrieved detailed history for notification {notification_id} "
                f"for user {user_id}"
            )
            
            return response
            
        except ValueError as e:
            logger.error(f"Invalid notification ID {notification_id}: {e}")
            raise
        except NotFoundError as e:
            logger.warning(f"Notification not found: {e}")
            raise
        except PyMongoError as e:
            logger.error(f"Database error during notification retrieval: {e}")
            raise RuntimeError(f"Failed to retrieve notification details: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during notification retrieval: {e}")
            raise RuntimeError(f"Failed to retrieve notification details: {str(e)}")
    
    async def get_recent_history(
        self,
        user_id: str,
        hours: int = 24,
        limit: int = 50
    ) -> List[NotificationHistoryResponse]:
        """
        Retrieve recent notification history for a user
        
        Optimized method for getting recent notifications without full pagination,
        useful for dashboard displays and real-time updates.
        
        Args:
            user_id: User ID for scoping
            hours: Number of hours to look back (default: 24)
            limit: Maximum number of results (default: 50)
            
        Returns:
            List of recent notifications sorted by creation time
        """
        try:
            # Calculate date threshold
            since_date = datetime.utcnow() - timedelta(hours=hours)
            
            # Build query
            query = {
                "user_id": user_id,
                "created_at": {"$gte": since_date}
            }
            
            # Execute query with sorting and limit
            cursor = self.collection.find(query).sort("created_at", DESCENDING).limit(limit)
            documents = await cursor.to_list(length=limit)
            
            # Convert to response models
            history_items = []
            for doc in documents:
                try:
                    history_item = self._document_to_history_response(doc)
                    history_items.append(history_item)
                except Exception as e:
                    logger.warning(f"Failed to convert recent document {doc.get('_id')}: {e}")
                    continue
            
            logger.info(
                f"Retrieved {len(history_items)} recent notifications for user {user_id} "
                f"(last {hours} hours)"
            )
            
            return history_items
            
        except Exception as e:
            logger.error(f"Error retrieving recent history for user {user_id}: {e}")
            raise RuntimeError(f"Failed to retrieve recent history: {str(e)}")
    
    async def get_user_statistics(self, user_id: str) -> Dict[str, Any]:
        """
        Get notification statistics for a specific user
        
        Provides summary statistics including delivery rates, channel usage,
        and failure patterns for user dashboard and analytics.
        
        Args:
            user_id: User ID for statistics calculation
            
        Returns:
            Dictionary with comprehensive user notification statistics
        """
        try:
            # Aggregation pipeline for user statistics
            pipeline = [
                {"$match": {"user_id": user_id}},
                {
                    "$group": {
                        "_id": None,
                        "total_notifications": {"$sum": 1},
                        "successful_deliveries": {
                            "$sum": {"$cond": [{"$eq": ["$delivery_status", "delivered"]}, 1, 0]}
                        },
                        "failed_deliveries": {
                            "$sum": {"$cond": [{"$eq": ["$delivery_status", "failed"]}, 1, 0]}
                        },
                        "pending_deliveries": {
                            "$sum": {"$cond": [{"$eq": ["$delivery_status", "pending"]}, 1, 0]}
                        },
                        "channels_used": {"$addToSet": "$channel"},
                        "latest_notification": {"$max": "$created_at"},
                        "earliest_notification": {"$min": "$created_at"}
                    }
                }
            ]
            
            # Execute aggregation
            results = await self._aggregate(pipeline)
            stats = results[0] if results else {}
            
            # Calculate derived statistics
            total = stats.get("total_notifications", 0)
            successful = stats.get("successful_deliveries", 0)
            failed = stats.get("failed_deliveries", 0)
            
            success_rate = (successful / total * 100) if total > 0 else 0
            failure_rate = (failed / total * 100) if total > 0 else 0
            
            return {
                "total_notifications": total,
                "successful_deliveries": successful,
                "failed_deliveries": failed,
                "pending_deliveries": stats.get("pending_deliveries", 0),
                "success_rate": round(success_rate, 2),
                "failure_rate": round(failure_rate, 2),
                "channels_used": stats.get("channels_used", []),
                "latest_notification": stats.get("latest_notification"),
                "earliest_notification": stats.get("earliest_notification"),
                "total_channels": len(stats.get("channels_used", []))
            }
            
        except Exception as e:
            logger.error(f"Error calculating statistics for user {user_id}: {e}")
            raise RuntimeError(f"Failed to calculate user statistics: {str(e)}")
    
    # Helper methods for database operations
    
    async def _count_documents(self, query: Dict[str, Any]) -> int:
        """Execute count query with error handling"""
        try:
            return await self.collection.count_documents(query)
        except PyMongoError as e:
            logger.error(f"Error counting documents: {e}")
            raise
    
    async def _find_one(self, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Execute find_one query with error handling"""
        try:
            return await self.collection.find_one(query)
        except PyMongoError as e:
            logger.error(f"Error finding document: {e}")
            raise
    
    async def _aggregate(self, pipeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute aggregation pipeline with error handling"""
        try:
            cursor = self.collection.aggregate(pipeline)
            return await cursor.to_list(length=None)
        except PyMongoError as e:
            logger.error(f"Error executing aggregation: {e}")
            raise
    
    def _document_to_history_response(self, doc: Dict[str, Any]) -> NotificationHistoryResponse:
        """Convert MongoDB document to history response model"""
        try:
            return NotificationHistoryResponse(
                id=str(doc["_id"]),
                user_id=doc["user_id"],
                notification_type=doc.get("notification_type", "unknown"),
                channel=doc["channel"],
                delivery_status=doc["delivery_status"],
                priority=doc.get("priority", "medium"),
                subject=doc.get("notification_content", {}).get("subject", ""),
                created_at=doc["created_at"],
                delivered_at=doc.get("delivered_at"),
                failed_at=doc.get("failed_at"),
                retry_count=doc.get("retry_count", 0),
                error_message=doc.get("error_details", {}).get("message") if doc.get("error_details") else None
            )
        except KeyError as e:
            logger.error(f"Missing required field in document {doc.get('_id')}: {e}")
            raise ValueError(f"Invalid document structure: missing {e}")
    
    def _document_to_detail_response(self, doc: Dict[str, Any]) -> NotificationHistoryDetailResponse:
        """Convert MongoDB document to detailed history response model"""
        try:
            return NotificationHistoryDetailResponse(
                id=str(doc["_id"]),
                user_id=doc["user_id"],
                notification_type=doc.get("notification_type", "unknown"),
                channel=doc["channel"],
                delivery_status=doc["delivery_status"],
                priority=doc.get("priority", "medium"),
                notification_content=doc.get("notification_content", {}),
                created_at=doc["created_at"],
                delivered_at=doc.get("delivered_at"),
                failed_at=doc.get("failed_at"),
                retry_count=doc.get("retry_count", 0),
                retry_history=doc.get("retry_history", []),
                error_details=doc.get("error_details"),
                delivery_metadata=doc.get("delivery_metadata", {}),
                trace_id=doc.get("trace_id"),
                correlation_id=doc.get("correlation_id")
            )
        except KeyError as e:
            logger.error(f"Missing required field in detailed document {doc.get('_id')}: {e}")
            raise ValueError(f"Invalid document structure: missing {e}")


class NotFoundError(Exception):
    """Exception raised when a requested notification is not found"""
    pass


# Export the service class and related models
__all__ = [
    "NotificationHistoryService",
    "HistoryQueryParameters",
    "HistoryFilterBuilder",
    "HistoryPaginator",
    "HistorySortOption",
    "NotFoundError"
] 
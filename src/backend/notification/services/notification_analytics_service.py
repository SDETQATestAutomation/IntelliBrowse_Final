"""
IntelliBrowse Notification Engine - Analytics Service

This module provides comprehensive notification analytics capabilities including
success/failure rate aggregation, failure analysis, user responsiveness metrics,
and dashboard-ready data formatting with caching support for performance.

Classes:
    - NotificationAnalyticsService: Core analytics service
    - AnalyticsTimeWindow: Time window configuration for analytics
    - AnalyticsCacheManager: Redis caching for performance optimization
    - MetricsAggregator: Helper for building aggregation pipelines

Author: IntelliBrowse Team
Created: Phase 3 - Analytics Implementation
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from enum import Enum
import json
import hashlib

from bson import ObjectId
from pydantic import BaseModel, Field, validator
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from ..schemas.notification_analytics_schemas import (
    AnalyticsResponse,
    ChannelAnalytics,
    FailureAnalysis,
    UserResponsivenessMetrics,
    TimeSeriesData,
    AnalyticsTimeRange,
    DashboardSummary
)

# Configure logging
logger = logging.getLogger(__name__)


class TimeWindow(str, Enum):
    """Enumeration of supported time windows for analytics"""
    HOUR = "1h"
    DAY = "1d"
    WEEK = "7d"
    MONTH = "30d"
    QUARTER = "90d"
    YEAR = "365d"


class AnalyticsTimeWindow(BaseModel):
    """
    Configuration for analytics time window calculations
    
    Provides flexible time window configuration with automatic
    date boundary calculation and time zone support.
    """
    
    window: TimeWindow = Field(..., description="Time window duration")
    start_date: Optional[datetime] = Field(None, description="Custom start date")
    end_date: Optional[datetime] = Field(None, description="Custom end date")
    timezone: str = Field(default="UTC", description="Timezone for calculations")
    
    @validator('end_date')
    def validate_date_range(cls, v, values):
        """Validate that end_date is after start_date if both are provided"""
        if v and 'start_date' in values and values['start_date']:
            if v <= values['start_date']:
                raise ValueError("end_date must be after start_date")
        return v
    
    def get_date_range(self) -> tuple[datetime, datetime]:
        """
        Calculate actual date range for the time window
        
        Returns:
            Tuple of (start_date, end_date) for the time window
        """
        end_date = self.end_date or datetime.utcnow()
        
        if self.start_date:
            start_date = self.start_date
        else:
            # Calculate start date based on window
            window_mapping = {
                TimeWindow.HOUR: timedelta(hours=1),
                TimeWindow.DAY: timedelta(days=1),
                TimeWindow.WEEK: timedelta(days=7),
                TimeWindow.MONTH: timedelta(days=30),
                TimeWindow.QUARTER: timedelta(days=90),
                TimeWindow.YEAR: timedelta(days=365)
            }
            delta = window_mapping.get(self.window, timedelta(days=1))
            start_date = end_date - delta
        
        return start_date, end_date


class AnalyticsCacheManager:
    """
    Redis-based caching manager for analytics results
    
    Provides intelligent caching with configurable TTL, cache invalidation,
    and fallback mechanisms for improved analytics performance.
    """
    
    def __init__(self, redis_client=None, default_ttl: int = 300):
        """
        Initialize cache manager with Redis client
        
        Args:
            redis_client: Redis client instance (optional)
            default_ttl: Default cache TTL in seconds
        """
        self.redis_client = redis_client
        self.default_ttl = default_ttl
        self.cache_prefix = "intellibrowse:analytics:"
        
        logger.info(f"AnalyticsCacheManager initialized with TTL {default_ttl}s")
    
    def _generate_cache_key(self, user_id: str, query_params: Dict[str, Any]) -> str:
        """Generate consistent cache key from parameters"""
        params_str = json.dumps(query_params, sort_keys=True, default=str)
        params_hash = hashlib.md5(params_str.encode()).hexdigest()
        return f"{self.cache_prefix}{user_id}:{params_hash}"
    
    async def get_cached_result(
        self,
        user_id: str,
        query_params: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached analytics result
        
        Args:
            user_id: User ID for cache scoping
            query_params: Query parameters for cache key generation
            
        Returns:
            Cached result or None if not found
        """
        if not self.redis_client:
            return None
        
        try:
            cache_key = self._generate_cache_key(user_id, query_params)
            cached_data = await self.redis_client.get(cache_key)
            
            if cached_data:
                result = json.loads(cached_data)
                logger.debug(f"Cache hit for analytics query: {cache_key}")
                return result
            
            logger.debug(f"Cache miss for analytics query: {cache_key}")
            return None
            
        except Exception as e:
            logger.warning(f"Error retrieving from cache: {e}")
            return None
    
    async def cache_result(
        self,
        user_id: str,
        query_params: Dict[str, Any],
        result: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> None:
        """
        Cache analytics result with TTL
        
        Args:
            user_id: User ID for cache scoping
            query_params: Query parameters for cache key generation
            result: Analytics result to cache
            ttl: Cache TTL in seconds (uses default if None)
        """
        if not self.redis_client:
            return
        
        try:
            cache_key = self._generate_cache_key(user_id, query_params)
            cache_ttl = ttl or self.default_ttl
            
            cached_data = json.dumps(result, default=str)
            await self.redis_client.setex(cache_key, cache_ttl, cached_data)
            
            logger.debug(f"Cached analytics result: {cache_key} (TTL: {cache_ttl}s)")
            
        except Exception as e:
            logger.warning(f"Error caching analytics result: {e}")
    
    async def invalidate_user_cache(self, user_id: str) -> None:
        """Invalidate all cached results for a user"""
        if not self.redis_client:
            return
        
        try:
            pattern = f"{self.cache_prefix}{user_id}:*"
            keys = await self.redis_client.keys(pattern)
            
            if keys:
                await self.redis_client.delete(*keys)
                logger.info(f"Invalidated {len(keys)} cache entries for user {user_id}")
                
        except Exception as e:
            logger.warning(f"Error invalidating user cache: {e}")


class MetricsAggregator:
    """
    Helper class for building MongoDB aggregation pipelines for analytics
    
    Provides reusable aggregation pipeline components for various
    analytics calculations with optimization for performance.
    """
    
    @staticmethod
    def build_base_match(user_id: str, time_window: AnalyticsTimeWindow) -> Dict[str, Any]:
        """Build base match stage for user and time filtering"""
        start_date, end_date = time_window.get_date_range()
        
        return {
            "$match": {
                "user_id": user_id,
                "created_at": {
                    "$gte": start_date,
                    "$lte": end_date
                }
            }
        }
    
    @staticmethod
    def build_channel_analytics_pipeline(
        user_id: str,
        time_window: AnalyticsTimeWindow
    ) -> List[Dict[str, Any]]:
        """Build aggregation pipeline for channel analytics"""
        base_match = MetricsAggregator.build_base_match(user_id, time_window)
        
        return [
            base_match,
            {
                "$group": {
                    "_id": "$channel",
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
                    "avg_delivery_time": {
                        "$avg": {
                            "$subtract": ["$delivered_at", "$created_at"]
                        }
                    },
                    "max_retry_count": {"$max": "$retry_count"},
                    "avg_retry_count": {"$avg": "$retry_count"}
                }
            },
            {
                "$addFields": {
                    "success_rate": {
                        "$multiply": [
                            {"$divide": ["$successful_deliveries", "$total_notifications"]},
                            100
                        ]
                    },
                    "failure_rate": {
                        "$multiply": [
                            {"$divide": ["$failed_deliveries", "$total_notifications"]},
                            100
                        ]
                    }
                }
            },
            {"$sort": {"total_notifications": -1}}
        ]
    
    @staticmethod
    def build_failure_analysis_pipeline(
        user_id: str,
        time_window: AnalyticsTimeWindow
    ) -> List[Dict[str, Any]]:
        """Build aggregation pipeline for failure analysis"""
        base_match = MetricsAggregator.build_base_match(user_id, time_window)
        
        return [
            base_match,
            {"$match": {"delivery_status": "failed"}},
            {
                "$group": {
                    "_id": {
                        "error_type": "$error_details.error_type",
                        "channel": "$channel"
                    },
                    "failure_count": {"$sum": 1},
                    "error_messages": {"$addToSet": "$error_details.message"},
                    "affected_notifications": {"$addToSet": "$_id"},
                    "first_occurrence": {"$min": "$failed_at"},
                    "last_occurrence": {"$max": "$failed_at"}
                }
            },
            {
                "$group": {
                    "_id": "$_id.error_type",
                    "total_failures": {"$sum": "$failure_count"},
                    "channels_affected": {"$addToSet": "$_id.channel"},
                    "error_messages": {"$addToSet": "$error_messages"},
                    "first_seen": {"$min": "$first_occurrence"},
                    "last_seen": {"$max": "$last_occurrence"},
                    "notification_count": {"$sum": {"$size": "$affected_notifications"}}
                }
            },
            {"$sort": {"total_failures": -1}},
            {"$limit": 20}
        ]
    
    @staticmethod
    def build_time_series_pipeline(
        user_id: str,
        time_window: AnalyticsTimeWindow,
        granularity: str = "day"
    ) -> List[Dict[str, Any]]:
        """Build aggregation pipeline for time series data"""
        base_match = MetricsAggregator.build_base_match(user_id, time_window)
        
        # Define date truncation based on granularity
        date_truncation = {
            "hour": {
                "year": {"$year": "$created_at"},
                "month": {"$month": "$created_at"},
                "day": {"$dayOfMonth": "$created_at"},
                "hour": {"$hour": "$created_at"}
            },
            "day": {
                "year": {"$year": "$created_at"},
                "month": {"$month": "$created_at"},
                "day": {"$dayOfMonth": "$created_at"}
            },
            "week": {
                "year": {"$year": "$created_at"},
                "week": {"$week": "$created_at"}
            },
            "month": {
                "year": {"$year": "$created_at"},
                "month": {"$month": "$created_at"}
            }
        }
        
        return [
            base_match,
            {
                "$group": {
                    "_id": date_truncation.get(granularity, date_truncation["day"]),
                    "total_notifications": {"$sum": 1},
                    "successful_deliveries": {
                        "$sum": {"$cond": [{"$eq": ["$delivery_status", "delivered"]}, 1, 0]}
                    },
                    "failed_deliveries": {
                        "$sum": {"$cond": [{"$eq": ["$delivery_status", "failed"]}, 1, 0]}
                    },
                    "pending_deliveries": {
                        "$sum": {"$cond": [{"$eq": ["$delivery_status", "pending"]}, 1, 0]}
                    }
                }
            },
            {"$sort": {"_id": 1}}
        ]


class NotificationAnalyticsService:
    """
    Core service for notification analytics and metrics calculation
    
    Provides comprehensive analytics capabilities including channel performance,
    failure analysis, user engagement metrics, and time-series data with
    intelligent caching for optimal performance.
    """
    
    def __init__(self, collection: Collection, redis_client=None):
        """
        Initialize the analytics service
        
        Args:
            collection: MongoDB collection for notification history
            redis_client: Redis client for caching (optional)
        """
        self.collection = collection
        self.cache_manager = AnalyticsCacheManager(redis_client)
        self.metrics_aggregator = MetricsAggregator()
        
        logger.info("NotificationAnalyticsService initialized")
    
    async def get_channel_analytics(
        self,
        user_id: str,
        time_window: AnalyticsTimeWindow
    ) -> List[ChannelAnalytics]:
        """
        Get analytics data for notification channels
        
        Provides comprehensive channel performance metrics including
        success rates, delivery times, and retry statistics.
        
        Args:
            user_id: User ID for scoping analytics
            time_window: Time window for analytics calculation
            
        Returns:
            List of channel analytics with performance metrics
        """
        try:
            # Check cache first
            cache_params = {
                "operation": "channel_analytics",
                "time_window": time_window.dict()
            }
            
            cached_result = await self.cache_manager.get_cached_result(user_id, cache_params)
            if cached_result:
                return [ChannelAnalytics(**item) for item in cached_result]
            
            # Build and execute aggregation pipeline
            pipeline = self.metrics_aggregator.build_channel_analytics_pipeline(
                user_id, time_window
            )
            
            results = await self._execute_aggregation(pipeline)
            
            # Convert to response models
            channel_analytics = []
            for result in results:
                analytics = ChannelAnalytics(
                    channel=result["_id"],
                    total_notifications=result["total_notifications"],
                    successful_deliveries=result["successful_deliveries"],
                    failed_deliveries=result["failed_deliveries"],
                    pending_deliveries=result["pending_deliveries"],
                    success_rate=round(result.get("success_rate", 0), 2),
                    failure_rate=round(result.get("failure_rate", 0), 2),
                    average_delivery_time_ms=int(result.get("avg_delivery_time", 0)),
                    max_retry_count=result.get("max_retry_count", 0),
                    average_retry_count=round(result.get("avg_retry_count", 0), 2)
                )
                channel_analytics.append(analytics)
            
            # Cache results
            await self.cache_manager.cache_result(
                user_id,
                cache_params,
                [analytics.dict() for analytics in channel_analytics],
                ttl=300  # 5 minutes cache
            )
            
            logger.info(f"Generated channel analytics for user {user_id}")
            return channel_analytics
            
        except Exception as e:
            logger.error(f"Error generating channel analytics for user {user_id}: {e}")
            raise RuntimeError(f"Failed to generate channel analytics: {str(e)}")
    
    async def get_failure_analysis(
        self,
        user_id: str,
        time_window: AnalyticsTimeWindow
    ) -> FailureAnalysis:
        """
        Analyze notification failures and patterns
        
        Provides detailed failure analysis including top failure causes,
        affected channels, and error patterns for troubleshooting.
        
        Args:
            user_id: User ID for scoping analysis
            time_window: Time window for failure analysis
            
        Returns:
            Comprehensive failure analysis with trending and patterns
        """
        try:
            # Check cache first
            cache_params = {
                "operation": "failure_analysis",
                "time_window": time_window.dict()
            }
            
            cached_result = await self.cache_manager.get_cached_result(user_id, cache_params)
            if cached_result:
                return FailureAnalysis(**cached_result)
            
            # Build and execute aggregation pipeline
            pipeline = self.metrics_aggregator.build_failure_analysis_pipeline(
                user_id, time_window
            )
            
            results = await self._execute_aggregation(pipeline)
            
            # Process results into failure analysis
            top_failure_causes = []
            total_failures = 0
            channels_affected = set()
            
            for result in results:
                error_type = result["_id"] or "unknown_error"
                failure_count = result["total_failures"]
                total_failures += failure_count
                
                # Flatten error messages
                error_messages = []
                for msg_list in result.get("error_messages", []):
                    if isinstance(msg_list, list):
                        error_messages.extend(msg_list)
                    else:
                        error_messages.append(msg_list)
                
                # Add to channels affected
                channels_affected.update(result.get("channels_affected", []))
                
                cause = {
                    "error_type": error_type,
                    "failure_count": failure_count,
                    "percentage": 0,  # Will calculate after processing all results
                    "channels_affected": result.get("channels_affected", []),
                    "sample_error_messages": error_messages[:5],  # Top 5 error messages
                    "first_seen": result.get("first_seen"),
                    "last_seen": result.get("last_seen")
                }
                top_failure_causes.append(cause)
            
            # Calculate percentages
            for cause in top_failure_causes:
                if total_failures > 0:
                    cause["percentage"] = round(
                        (cause["failure_count"] / total_failures) * 100, 2
                    )
            
            # Create failure analysis response
            failure_analysis = FailureAnalysis(
                total_failures=total_failures,
                unique_error_types=len(top_failure_causes),
                channels_affected=list(channels_affected),
                top_failure_causes=top_failure_causes[:10],  # Top 10 causes
                failure_trend="stable",  # TODO: Implement trend calculation
                time_window=time_window.dict()
            )
            
            # Cache results
            await self.cache_manager.cache_result(
                user_id,
                cache_params,
                failure_analysis.dict(),
                ttl=600  # 10 minutes cache
            )
            
            logger.info(
                f"Generated failure analysis for user {user_id}: "
                f"{total_failures} failures, {len(top_failure_causes)} error types"
            )
            
            return failure_analysis
            
        except Exception as e:
            logger.error(f"Error generating failure analysis for user {user_id}: {e}")
            raise RuntimeError(f"Failed to generate failure analysis: {str(e)}")
    
    async def get_user_responsiveness_metrics(
        self,
        user_id: str,
        time_window: AnalyticsTimeWindow
    ) -> UserResponsivenessMetrics:
        """
        Calculate user responsiveness and engagement metrics
        
        Analyzes user interaction with notifications including open rates,
        click-through rates, and response times for optimization insights.
        
        Args:
            user_id: User ID for metrics calculation
            time_window: Time window for metrics analysis
            
        Returns:
            Comprehensive user responsiveness metrics
        """
        try:
            # Check cache first
            cache_params = {
                "operation": "responsiveness_metrics",
                "time_window": time_window.dict()
            }
            
            cached_result = await self.cache_manager.get_cached_result(user_id, cache_params)
            if cached_result:
                return UserResponsivenessMetrics(**cached_result)
            
            # Build aggregation pipeline for responsiveness
            base_match = self.metrics_aggregator.build_base_match(user_id, time_window)
            
            pipeline = [
                base_match,
                {
                    "$group": {
                        "_id": None,
                        "total_notifications": {"$sum": 1},
                        "notifications_opened": {
                            "$sum": {"$cond": [{"$gt": ["$opened_at", None]}, 1, 0]}
                        },
                        "notifications_clicked": {
                            "$sum": {"$cond": [{"$gt": ["$clicked_at", None]}, 1, 0]}
                        },
                        "avg_open_time": {
                            "$avg": {
                                "$subtract": ["$opened_at", "$delivered_at"]
                            }
                        },
                        "avg_click_time": {
                            "$avg": {
                                "$subtract": ["$clicked_at", "$opened_at"]
                            }
                        },
                        "fastest_open": {
                            "$min": {
                                "$subtract": ["$opened_at", "$delivered_at"]
                            }
                        },
                        "slowest_open": {
                            "$max": {
                                "$subtract": ["$opened_at", "$delivered_at"]
                            }
                        }
                    }
                }
            ]
            
            results = await self._execute_aggregation(pipeline)
            result = results[0] if results else {}
            
            # Calculate metrics
            total_notifications = result.get("total_notifications", 0)
            notifications_opened = result.get("notifications_opened", 0)
            notifications_clicked = result.get("notifications_clicked", 0)
            
            open_rate = (notifications_opened / total_notifications * 100) if total_notifications > 0 else 0
            click_through_rate = (notifications_clicked / notifications_opened * 100) if notifications_opened > 0 else 0
            
            # Create responsiveness metrics
            metrics = UserResponsivenessMetrics(
                total_notifications_sent=total_notifications,
                notifications_opened=notifications_opened,
                notifications_clicked=notifications_clicked,
                open_rate=round(open_rate, 2),
                click_through_rate=round(click_through_rate, 2),
                average_open_time_seconds=int(result.get("avg_open_time", 0) / 1000) if result.get("avg_open_time") else 0,
                average_click_time_seconds=int(result.get("avg_click_time", 0) / 1000) if result.get("avg_click_time") else 0,
                fastest_open_time_seconds=int(result.get("fastest_open", 0) / 1000) if result.get("fastest_open") else 0,
                slowest_open_time_seconds=int(result.get("slowest_open", 0) / 1000) if result.get("slowest_open") else 0,
                engagement_score=round((open_rate + click_through_rate) / 2, 2),
                time_window=time_window.dict()
            )
            
            # Cache results
            await self.cache_manager.cache_result(
                user_id,
                cache_params,
                metrics.dict(),
                ttl=900  # 15 minutes cache
            )
            
            logger.info(
                f"Generated responsiveness metrics for user {user_id}: "
                f"{open_rate:.1f}% open rate, {click_through_rate:.1f}% CTR"
            )
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error generating responsiveness metrics for user {user_id}: {e}")
            raise RuntimeError(f"Failed to generate responsiveness metrics: {str(e)}")
    
    async def get_time_series_data(
        self,
        user_id: str,
        time_window: AnalyticsTimeWindow,
        granularity: str = "day"
    ) -> List[TimeSeriesData]:
        """
        Generate time series data for notification trends
        
        Provides time-based analytics for trending analysis and
        dashboard visualization with configurable granularity.
        
        Args:
            user_id: User ID for data scoping
            time_window: Time window for analysis
            granularity: Time granularity (hour, day, week, month)
            
        Returns:
            List of time series data points with notification metrics
        """
        try:
            # Build and execute aggregation pipeline
            pipeline = self.metrics_aggregator.build_time_series_pipeline(
                user_id, time_window, granularity
            )
            
            results = await self._execute_aggregation(pipeline)
            
            # Convert to time series data
            time_series = []
            for result in results:
                # Create date from aggregation result
                date_parts = result["_id"]
                if granularity == "hour":
                    timestamp = datetime(
                        date_parts["year"],
                        date_parts["month"],
                        date_parts["day"],
                        date_parts["hour"]
                    )
                elif granularity == "day":
                    timestamp = datetime(
                        date_parts["year"],
                        date_parts["month"],
                        date_parts["day"]
                    )
                elif granularity == "week":
                    # Calculate date from year and week
                    import calendar
                    timestamp = datetime.strptime(
                        f"{date_parts['year']}-{date_parts['week']}-1",
                        "%Y-%W-%w"
                    )
                elif granularity == "month":
                    timestamp = datetime(
                        date_parts["year"],
                        date_parts["month"],
                        1
                    )
                else:
                    timestamp = datetime(
                        date_parts["year"],
                        date_parts["month"],
                        date_parts["day"]
                    )
                
                data_point = TimeSeriesData(
                    timestamp=timestamp,
                    total_notifications=result["total_notifications"],
                    successful_deliveries=result["successful_deliveries"],
                    failed_deliveries=result["failed_deliveries"],
                    pending_deliveries=result["pending_deliveries"],
                    success_rate=round(
                        (result["successful_deliveries"] / result["total_notifications"] * 100)
                        if result["total_notifications"] > 0 else 0, 2
                    )
                )
                time_series.append(data_point)
            
            logger.info(
                f"Generated {len(time_series)} time series data points for user {user_id} "
                f"({granularity} granularity)"
            )
            
            return time_series
            
        except Exception as e:
            logger.error(f"Error generating time series data for user {user_id}: {e}")
            raise RuntimeError(f"Failed to generate time series data: {str(e)}")
    
    async def get_dashboard_summary(
        self,
        user_id: str,
        time_window: AnalyticsTimeWindow
    ) -> DashboardSummary:
        """
        Generate comprehensive dashboard summary
        
        Combines multiple analytics components into a single
        dashboard-ready response for efficient data loading.
        
        Args:
            user_id: User ID for dashboard scoping
            time_window: Time window for summary calculation
            
        Returns:
            Comprehensive dashboard summary with all key metrics
        """
        try:
            # Execute analytics in parallel for efficiency
            import asyncio
            
            channel_analytics_task = self.get_channel_analytics(user_id, time_window)
            failure_analysis_task = self.get_failure_analysis(user_id, time_window)
            responsiveness_task = self.get_user_responsiveness_metrics(user_id, time_window)
            time_series_task = self.get_time_series_data(user_id, time_window, "day")
            
            channel_analytics, failure_analysis, responsiveness, time_series = await asyncio.gather(
                channel_analytics_task,
                failure_analysis_task,
                responsiveness_task,
                time_series_task,
                return_exceptions=True
            )
            
            # Handle any exceptions
            if isinstance(channel_analytics, Exception):
                logger.error(f"Channel analytics failed: {channel_analytics}")
                channel_analytics = []
            
            if isinstance(failure_analysis, Exception):
                logger.error(f"Failure analysis failed: {failure_analysis}")
                failure_analysis = FailureAnalysis(
                    total_failures=0,
                    unique_error_types=0,
                    channels_affected=[],
                    top_failure_causes=[],
                    failure_trend="unknown",
                    time_window=time_window.dict()
                )
            
            if isinstance(responsiveness, Exception):
                logger.error(f"Responsiveness metrics failed: {responsiveness}")
                responsiveness = UserResponsivenessMetrics(
                    total_notifications_sent=0,
                    notifications_opened=0,
                    notifications_clicked=0,
                    open_rate=0,
                    click_through_rate=0,
                    average_open_time_seconds=0,
                    average_click_time_seconds=0,
                    fastest_open_time_seconds=0,
                    slowest_open_time_seconds=0,
                    engagement_score=0,
                    time_window=time_window.dict()
                )
            
            if isinstance(time_series, Exception):
                logger.error(f"Time series generation failed: {time_series}")
                time_series = []
            
            # Create dashboard summary
            summary = DashboardSummary(
                user_id=user_id,
                time_window=time_window.dict(),
                generated_at=datetime.utcnow(),
                channel_analytics=channel_analytics,
                failure_analysis=failure_analysis,
                user_responsiveness=responsiveness,
                time_series_data=time_series,
                total_notifications=responsiveness.total_notifications_sent,
                overall_success_rate=sum(
                    ch.success_rate * ch.total_notifications
                    for ch in channel_analytics
                ) / sum(ch.total_notifications for ch in channel_analytics) if channel_analytics else 0
            )
            
            logger.info(f"Generated dashboard summary for user {user_id}")
            return summary
            
        except Exception as e:
            logger.error(f"Error generating dashboard summary for user {user_id}: {e}")
            raise RuntimeError(f"Failed to generate dashboard summary: {str(e)}")
    
    async def invalidate_user_analytics(self, user_id: str) -> None:
        """
        Invalidate all cached analytics for a user
        
        Called when new notifications are processed to ensure
        analytics remain accurate and up-to-date.
        
        Args:
            user_id: User ID for cache invalidation
        """
        await self.cache_manager.invalidate_user_cache(user_id)
        logger.info(f"Invalidated analytics cache for user {user_id}")
    
    # Helper methods
    
    async def _execute_aggregation(self, pipeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute MongoDB aggregation pipeline with error handling"""
        try:
            cursor = self.collection.aggregate(pipeline)
            return await cursor.to_list(length=None)
        except PyMongoError as e:
            logger.error(f"Error executing aggregation pipeline: {e}")
            raise


# Export the service class and related models
__all__ = [
    "NotificationAnalyticsService",
    "AnalyticsTimeWindow",
    "AnalyticsCacheManager",
    "MetricsAggregator",
    "TimeWindow"
] 
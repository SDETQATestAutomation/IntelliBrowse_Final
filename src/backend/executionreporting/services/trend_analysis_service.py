"""
Execution Reporting Module - Trend Analysis Service

Service for detecting execution patterns, anomaly windows, and time-series grouping.
Provides advanced statistical analysis for trend identification and forecasting.
"""

import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from statistics import mean, stdev
from motor.motor_asyncio import AsyncIOMotorDatabase

from ...config.logging import get_logger
from ..models.execution_report_model import (
    TrendAnalysisModel, TrendDirection, MetricPeriod, AggregationLevel
)
from ..schemas.report_schemas import (
    TrendAnalysisResponse, TimeRangeFilter, MetricFilter
)

logger = get_logger(__name__)


class TrendAnalysisService:
    """
    Advanced trend analysis service for execution pattern detection.
    
    Provides comprehensive trend analysis capabilities including:
    - Time-series pattern recognition
    - Anomaly detection and alerting
    - Forecasting and predictive analytics
    - Statistical trend calculation
    """
    
    def __init__(
        self,
        database: AsyncIOMotorDatabase,
        cache_service: Optional[Any] = None,
        data_aggregation_service: Optional[Any] = None
    ):
        """Initialize trend analysis service with dependencies"""
        self.database = database
        self.cache_service = cache_service
        self.data_aggregation_service = data_aggregation_service
        self.logger = logger.bind(service="TrendAnalysisService")
        
        # Collections
        self.trend_analysis_collection = self.database.trend_analysis
        self.execution_traces_collection = self.database.execution_traces
        
    async def analyze_execution_trends(
        self,
        time_range: TimeRangeFilter,
        metrics: MetricFilter,
        aggregation_level: AggregationLevel = AggregationLevel.DAILY,
        user_id: str = None
    ) -> TrendAnalysisResponse:
        """
        Analyze execution trends over specified time range.
        
        Args:
            time_range: Time period for trend analysis
            metrics: Metric filters for scope selection
            aggregation_level: Level of data aggregation (hourly, daily, weekly)
            user_id: ID of user requesting analysis
            
        Returns:
            TrendAnalysisResponse: Comprehensive trend analysis data
            
        Raises:
            ValueError: If parameters are invalid
            RuntimeError: If analysis fails
        """
        start_time = datetime.now(timezone.utc)
        analysis_id = f"trend_{uuid.uuid4().hex[:12]}"
        
        try:
            self.logger.info(
                "Starting trend analysis",
                analysis_id=analysis_id,
                aggregation_level=aggregation_level,
                user_id=user_id
            )
            
            # Check cache for existing analysis
            if self.cache_service:
                cached_analysis = await self._check_trend_cache(
                    time_range, metrics, aggregation_level
                )
                if cached_analysis:
                    self.logger.info("Returning cached trend analysis", analysis_id=analysis_id)
                    return cached_analysis
            
            # Perform fresh trend analysis
            trend_data = await self._analyze_fresh_trends(
                time_range, metrics, aggregation_level, analysis_id, user_id
            )
            
            # Cache the result
            if self.cache_service:
                await self._cache_trend_analysis(time_range, metrics, aggregation_level, trend_data)
            
            analysis_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            self.logger.info(
                "Trend analysis completed",
                analysis_id=analysis_id,
                analysis_time_ms=analysis_time
            )
            
            return trend_data
            
        except Exception as e:
            self.logger.error(
                "Trend analysis failed",
                analysis_id=analysis_id,
                error=str(e),
                exc_info=True
            )
            raise RuntimeError(f"Failed to analyze trends: {str(e)}") from e
    
    async def _analyze_fresh_trends(
        self,
        time_range: TimeRangeFilter,
        metrics: MetricFilter,
        aggregation_level: AggregationLevel,
        analysis_id: str,
        user_id: str
    ) -> TrendAnalysisResponse:
        """Perform fresh trend analysis from database data"""
        
        # Build aggregation pipeline for time-series data
        pipeline = await self._build_trend_pipeline(time_range, metrics, aggregation_level)
        
        # Execute aggregation
        trend_data_points = []
        async for document in self.execution_traces_collection.aggregate(pipeline):
            trend_data_points.append(document)
        
        # Calculate trend statistics
        trend_direction = self._calculate_trend_direction(trend_data_points)
        volatility = self._calculate_volatility(trend_data_points)
        anomalies = await self._detect_anomalies(trend_data_points)
        forecast = await self._generate_forecast(trend_data_points, 7)  # 7-period forecast
        
        # Calculate period-over-period changes
        percentage_change = self._calculate_percentage_change(trend_data_points)
        absolute_change = self._calculate_absolute_change(trend_data_points)
        
        # Create trend analysis response
        trend_analysis = TrendAnalysisResponse(
            analysis_id=analysis_id,
            period=aggregation_level.value,
            trend_direction=trend_direction,
            data_points=len(trend_data_points),
            percentage_change=percentage_change,
            absolute_change=absolute_change,
            volatility=volatility,
            anomalies_detected=len(anomalies),
            forecast_periods=len(forecast),
            confidence_score=self._calculate_confidence_score(trend_data_points),
            generated_at=datetime.now(timezone.utc),
            data_freshness_seconds=0
        )
        
        # Store analysis for future reference
        await self._store_trend_analysis(trend_analysis, time_range, metrics, user_id)
        
        return trend_analysis
    
    async def _build_trend_pipeline(
        self,
        time_range: TimeRangeFilter,
        metrics: MetricFilter,
        aggregation_level: AggregationLevel
    ) -> List[Dict[str, Any]]:
        """Build MongoDB aggregation pipeline for trend analysis"""
        
        # Date grouping based on aggregation level
        date_group_expression = self._get_date_group_expression(aggregation_level)
        
        # Match stage for filtering
        match_stage = {
            "triggered_at": {
                "$gte": time_range.start_date,
                "$lte": time_range.end_date
            }
        }
        
        # Add metric filters
        if metrics.test_suite_ids:
            match_stage["test_suite_id"] = {"$in": metrics.test_suite_ids}
        if metrics.test_case_ids:
            match_stage["test_case_id"] = {"$in": metrics.test_case_ids}
        if metrics.execution_types:
            match_stage["execution_type"] = {"$in": metrics.execution_types}
        if metrics.status_filter:
            match_stage["status"] = {"$in": metrics.status_filter}
        
        pipeline = [
            {"$match": match_stage},
            {
                "$group": {
                    "_id": date_group_expression,
                    "total_executions": {"$sum": 1},
                    "passed_executions": {
                        "$sum": {"$cond": [{"$eq": ["$status", "passed"]}, 1, 0]}
                    },
                    "failed_executions": {
                        "$sum": {"$cond": [{"$eq": ["$status", "failed"]}, 1, 0]}
                    },
                    "avg_duration": {"$avg": "$execution_duration_ms"},
                    "period_date": {"$first": "$triggered_at"}
                }
            },
            {
                "$addFields": {
                    "pass_rate": {
                        "$cond": [
                            {"$eq": ["$total_executions", 0]},
                            0,
                            {"$divide": ["$passed_executions", "$total_executions"]}
                        ]
                    }
                }
            },
            {"$sort": {"_id": 1}}
        ]
        
        return pipeline
    
    def _get_date_group_expression(self, aggregation_level: AggregationLevel) -> Dict[str, Any]:
        """Get date grouping expression based on aggregation level"""
        
        if aggregation_level == AggregationLevel.HOURLY:
            return {
                "year": {"$year": "$triggered_at"},
                "month": {"$month": "$triggered_at"},
                "day": {"$dayOfMonth": "$triggered_at"},
                "hour": {"$hour": "$triggered_at"}
            }
        elif aggregation_level == AggregationLevel.DAILY:
            return {
                "year": {"$year": "$triggered_at"},
                "month": {"$month": "$triggered_at"},
                "day": {"$dayOfMonth": "$triggered_at"}
            }
        elif aggregation_level == AggregationLevel.WEEKLY:
            return {
                "year": {"$year": "$triggered_at"},
                "week": {"$week": "$triggered_at"}
            }
        elif aggregation_level == AggregationLevel.MONTHLY:
            return {
                "year": {"$year": "$triggered_at"},
                "month": {"$month": "$triggered_at"}
            }
        else:
            # Default to daily
            return {
                "year": {"$year": "$triggered_at"},
                "month": {"$month": "$triggered_at"},
                "day": {"$dayOfMonth": "$triggered_at"}
            }
    
    def _calculate_trend_direction(self, data_points: List[Dict[str, Any]]) -> TrendDirection:
        """Calculate overall trend direction from data points"""
        
        if len(data_points) < 2:
            return TrendDirection.STABLE
        
        # Extract pass rates for trend calculation
        pass_rates = [point.get("pass_rate", 0) for point in data_points]
        
        # Calculate linear regression slope
        n = len(pass_rates)
        x_values = list(range(n))
        
        x_mean = mean(x_values)
        y_mean = mean(pass_rates)
        
        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, pass_rates))
        denominator = sum((x - x_mean) ** 2 for x in x_values)
        
        if denominator == 0:
            return TrendDirection.STABLE
        
        slope = numerator / denominator
        
        # Determine trend direction based on slope
        if slope > 0.01:  # Improving trend threshold
            return TrendDirection.IMPROVING
        elif slope < -0.01:  # Declining trend threshold
            return TrendDirection.DECLINING
        else:
            return TrendDirection.STABLE
    
    def _calculate_volatility(self, data_points: List[Dict[str, Any]]) -> float:
        """Calculate volatility (standard deviation) of pass rates"""
        
        if len(data_points) < 2:
            return 0.0
        
        pass_rates = [point.get("pass_rate", 0) for point in data_points]
        
        try:
            return stdev(pass_rates)
        except:
            return 0.0
    
    async def _detect_anomalies(self, data_points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect anomalies in trend data using statistical methods"""
        
        if len(data_points) < 5:  # Need minimum data for anomaly detection
            return []
        
        pass_rates = [point.get("pass_rate", 0) for point in data_points]
        mean_rate = mean(pass_rates)
        
        try:
            std_rate = stdev(pass_rates)
        except:
            return []
        
        anomalies = []
        threshold = 2 * std_rate  # 2-sigma threshold
        
        for i, point in enumerate(data_points):
            rate = point.get("pass_rate", 0)
            if abs(rate - mean_rate) > threshold:
                anomalies.append({
                    "period": point.get("_id"),
                    "value": rate,
                    "deviation": abs(rate - mean_rate),
                    "severity": "high" if abs(rate - mean_rate) > 3 * std_rate else "medium"
                })
        
        return anomalies
    
    async def _generate_forecast(
        self,
        data_points: List[Dict[str, Any]],
        periods: int
    ) -> List[Dict[str, Any]]:
        """Generate simple forecast for future periods"""
        
        if len(data_points) < 3:
            return []
        
        # Simple moving average forecast
        recent_rates = [point.get("pass_rate", 0) for point in data_points[-3:]]
        forecast_rate = mean(recent_rates)
        
        forecast = []
        for i in range(periods):
            forecast.append({
                "period": f"forecast_{i+1}",
                "predicted_pass_rate": forecast_rate,
                "confidence": max(0.5, 1.0 - (i * 0.1))  # Decreasing confidence
            })
        
        return forecast
    
    def _calculate_percentage_change(self, data_points: List[Dict[str, Any]]) -> float:
        """Calculate percentage change from first to last period"""
        
        if len(data_points) < 2:
            return 0.0
        
        first_rate = data_points[0].get("pass_rate", 0)
        last_rate = data_points[-1].get("pass_rate", 0)
        
        if first_rate == 0:
            return 0.0 if last_rate == 0 else 100.0
        
        return ((last_rate - first_rate) / first_rate) * 100
    
    def _calculate_absolute_change(self, data_points: List[Dict[str, Any]]) -> float:
        """Calculate absolute change from first to last period"""
        
        if len(data_points) < 2:
            return 0.0
        
        first_rate = data_points[0].get("pass_rate", 0)
        last_rate = data_points[-1].get("pass_rate", 0)
        
        return last_rate - first_rate
    
    def _calculate_confidence_score(self, data_points: List[Dict[str, Any]]) -> float:
        """Calculate confidence score for trend analysis"""
        
        # Base confidence on data volume and consistency
        data_volume_score = min(1.0, len(data_points) / 30)  # Higher confidence with more data
        
        if len(data_points) < 2:
            return data_volume_score * 0.5
        
        # Calculate consistency (inverse of volatility)
        volatility = self._calculate_volatility(data_points)
        consistency_score = max(0.1, 1.0 - volatility)
        
        return (data_volume_score + consistency_score) / 2
    
    async def _check_trend_cache(
        self,
        time_range: TimeRangeFilter,
        metrics: MetricFilter,
        aggregation_level: AggregationLevel
    ) -> Optional[TrendAnalysisResponse]:
        """Check cache for existing trend analysis"""
        # Implement cache checking logic
        return None
    
    async def _cache_trend_analysis(
        self,
        time_range: TimeRangeFilter,
        metrics: MetricFilter,
        aggregation_level: AggregationLevel,
        analysis: TrendAnalysisResponse
    ) -> None:
        """Cache trend analysis result"""
        # Implement caching logic
        pass
    
    async def _store_trend_analysis(
        self,
        analysis: TrendAnalysisResponse,
        time_range: TimeRangeFilter,
        metrics: MetricFilter,
        user_id: str
    ) -> None:
        """Store trend analysis in database"""
        
        trend_model = TrendAnalysisModel(
            analysis_id=analysis.analysis_id,
            period=MetricPeriod(analysis.period),
            trend_direction=analysis.trend_direction,
            data_points=analysis.data_points,
            percentage_change=analysis.percentage_change,
            absolute_change=analysis.absolute_change,
            volatility=analysis.volatility,
            anomalies_detected=analysis.anomalies_detected,
            forecast_periods=analysis.forecast_periods,
            confidence_score=analysis.confidence_score,
            generated_by=user_id,
            metadata={
                "time_range": {
                    "start": time_range.start_date.isoformat(),
                    "end": time_range.end_date.isoformat()
                },
                "filters": metrics.dict() if metrics else {}
            }
        )
        
        await self.trend_analysis_collection.insert_one(trend_model.dict(by_alias=True))


class TrendAnalysisServiceFactory:
    """Factory for creating TrendAnalysisService instances"""
    
    @staticmethod
    def create(
        database: AsyncIOMotorDatabase,
        cache_service: Optional[Any] = None,
        data_aggregation_service: Optional[Any] = None
    ) -> TrendAnalysisService:
        """Create and configure TrendAnalysisService instance"""
        return TrendAnalysisService(
            database=database,
            cache_service=cache_service,
            data_aggregation_service=data_aggregation_service
        ) 
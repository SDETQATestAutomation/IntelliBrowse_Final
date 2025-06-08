"""
Execution Reporting Module - Report Service

Core service for report generation, data aggregation, and business logic.
Implements clean architecture with dependency injection and async operations.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase

from ...config.logging import get_logger
from ..models.execution_report_model import (
    ExecutionReportModel, ReportType, AggregationLevel, QualityScore
)
from ..schemas.report_schemas import (
    ReportGenerationRequest, ExecutionReportResponse, ReportFilters
)

logger = get_logger(__name__)


class ReportService:
    """
    Core report generation service with business logic for execution analytics.
    
    Provides comprehensive report generation capabilities with intelligent caching,
    real-time data processing, and performance optimization.
    """
    
    def __init__(
        self,
        database: AsyncIOMotorDatabase,
        cache_service: Optional[Any] = None,
        data_aggregation_service: Optional[Any] = None
    ):
        """Initialize report service with dependencies"""
        self.database = database
        self.cache_service = cache_service
        self.data_aggregation_service = data_aggregation_service
        self.logger = logger.bind(service="ReportService")
        
        # Collections
        self.execution_reports_collection = self.database.execution_reports
        self.execution_traces_collection = self.database.execution_traces
        
    async def generate_report(
        self,
        request: ReportGenerationRequest,
        user_id: str
    ) -> ExecutionReportResponse:
        """
        Generate execution report based on request parameters.
        
        Args:
            request: Report generation request with filters and configuration
            user_id: ID of user requesting the report
            
        Returns:
            ExecutionReportResponse: Generated report data
            
        Raises:
            ValueError: If request parameters are invalid
            RuntimeError: If report generation fails
        """
        start_time = datetime.now(timezone.utc)
        report_id = f"report_{uuid.uuid4().hex[:12]}"
        
        try:
            self.logger.info(
                "Starting report generation",
                report_id=report_id,
                report_type=request.report_type,
                user_id=user_id
            )
            
            # Check cache if enabled
            if request.cache_enabled and self.cache_service:
                cached_report = await self._check_cache(request)
                if cached_report:
                    self.logger.info("Returning cached report", report_id=report_id)
                    return cached_report
            
            # Generate fresh report
            report_data = await self._generate_fresh_report(request, report_id, user_id)
            
            # Cache the result if caching is enabled
            if request.cache_enabled and self.cache_service:
                await self._cache_report(request, report_data)
            
            generation_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            self.logger.info(
                "Report generation completed",
                report_id=report_id,
                generation_time_ms=generation_time
            )
            
            return report_data
            
        except Exception as e:
            self.logger.error(
                "Report generation failed",
                report_id=report_id,
                error=str(e),
                exc_info=True
            )
            raise RuntimeError(f"Failed to generate report: {str(e)}") from e
    
    async def _generate_fresh_report(
        self,
        request: ReportGenerationRequest,
        report_id: str,
        user_id: str
    ) -> ExecutionReportResponse:
        """Generate a fresh report from database data"""
        
        # Build query based on filters
        query = await self._build_execution_query(request.filters)
        
        # Aggregate execution data
        execution_metrics = await self._aggregate_execution_metrics(query)
        
        # Calculate derived metrics
        quality_score = self._calculate_quality_score(execution_metrics)
        
        # Build drill-down navigation if applicable
        drilldown_nav = await self._build_drilldown_navigation(request.filters)
        
        # Create report response
        report = ExecutionReportResponse(
            report_id=report_id,
            report_type=request.report_type,
            name=request.name or f"{request.report_type.value.title()} Report",
            total_executions=execution_metrics.get("total_executions", 0),
            passed_executions=execution_metrics.get("passed_executions", 0),
            failed_executions=execution_metrics.get("failed_executions", 0),
            cancelled_executions=execution_metrics.get("cancelled_executions", 0),
            pass_rate=execution_metrics.get("pass_rate", 0.0),
            flakiness_index=execution_metrics.get("flakiness_index", 0.0),
            quality_score=quality_score,
            average_duration_ms=execution_metrics.get("average_duration_ms"),
            total_duration_ms=execution_metrics.get("total_duration_ms"),
            drilldown_navigation=drilldown_nav,
            generated_at=datetime.now(timezone.utc),
            data_freshness_seconds=0,  # Fresh data
            cached=False
        )
        
        # Store report in database for future reference
        await self._store_report(report, request.filters, user_id)
        
        return report
    
    async def _build_execution_query(self, filters: ReportFilters) -> Dict[str, Any]:
        """Build MongoDB query from report filters"""
        query = {}
        
        # Time range filter
        if filters.time_range:
            query["triggered_at"] = {
                "$gte": filters.time_range.start_date,
                "$lte": filters.time_range.end_date
            }
        
        # Metric filters
        if filters.metrics:
            if filters.metrics.test_suite_ids:
                query["test_suite_id"] = {"$in": filters.metrics.test_suite_ids}
            
            if filters.metrics.test_case_ids:
                query["test_case_id"] = {"$in": filters.metrics.test_case_ids}
            
            if filters.metrics.execution_types:
                query["execution_type"] = {"$in": filters.metrics.execution_types}
            
            if filters.metrics.tags:
                query["tags"] = {"$in": filters.metrics.tags}
            
            if filters.metrics.status_filter:
                query["status"] = {"$in": filters.metrics.status_filter}
            
            if filters.metrics.user_ids:
                query["triggered_by"] = {"$in": filters.metrics.user_ids}
        
        return query
    
    async def _aggregate_execution_metrics(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregate execution metrics from database"""
        
        # Use aggregation pipeline for efficient data processing
        pipeline = [
            {"$match": query},
            {
                "$group": {
                    "_id": None,
                    "total_executions": {"$sum": 1},
                    "passed_executions": {
                        "$sum": {"$cond": [{"$eq": ["$status", "passed"]}, 1, 0]}
                    },
                    "failed_executions": {
                        "$sum": {"$cond": [{"$eq": ["$status", "failed"]}, 1, 0]}
                    },
                    "cancelled_executions": {
                        "$sum": {"$cond": [{"$eq": ["$status", "cancelled"]}, 1, 0]}
                    },
                    "total_duration_ms": {"$sum": "$total_duration_ms"},
                    "durations": {"$push": "$total_duration_ms"}
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
                    },
                    "average_duration_ms": {
                        "$cond": [
                            {"$eq": ["$total_executions", 0]},
                            0,
                            {"$avg": "$durations"}
                        ]
                    }
                }
            }
        ]
        
        try:
            cursor = self.execution_traces_collection.aggregate(pipeline)
            results = await cursor.to_list(length=1)
            
            if not results:
                return {
                    "total_executions": 0,
                    "passed_executions": 0,
                    "failed_executions": 0,
                    "cancelled_executions": 0,
                    "pass_rate": 0.0,
                    "flakiness_index": 0.0,
                    "average_duration_ms": None,
                    "total_duration_ms": None
                }
            
            metrics = results[0]
            
            # Calculate flakiness index (placeholder implementation)
            metrics["flakiness_index"] = await self._calculate_flakiness_index(query)
            
            return metrics
            
        except Exception as e:
            self.logger.error("Failed to aggregate execution metrics", error=str(e))
            raise
    
    async def _calculate_flakiness_index(self, query: Dict[str, Any]) -> float:
        """Calculate test flakiness index based on execution patterns"""
        # Placeholder implementation - would use sophisticated flakiness detection
        # This would analyze test result patterns, retry counts, etc.
        try:
            # Simple heuristic: ratio of retried executions to total executions
            retry_pipeline = [
                {"$match": query},
                {
                    "$group": {
                        "_id": None,
                        "total": {"$sum": 1},
                        "retried": {
                            "$sum": {"$cond": [{"$gt": ["$retry_count", 0]}, 1, 0]}
                        }
                    }
                }
            ]
            
            cursor = self.execution_traces_collection.aggregate(retry_pipeline)
            results = await cursor.to_list(length=1)
            
            if not results or results[0]["total"] == 0:
                return 0.0
            
            return min(results[0]["retried"] / results[0]["total"], 1.0)
            
        except Exception as e:
            self.logger.warning("Failed to calculate flakiness index", error=str(e))
            return 0.0
    
    def _calculate_quality_score(self, metrics: Dict[str, Any]) -> QualityScore:
        """Calculate overall quality score based on metrics"""
        if metrics["total_executions"] == 0:
            return QualityScore.CRITICAL
        
        pass_rate = metrics.get("pass_rate", 0.0)
        flakiness_index = metrics.get("flakiness_index", 0.0)
        
        # Weighted quality score calculation
        pass_weight = 0.7
        flakiness_weight = 0.3
        
        quality_score = (pass_rate * pass_weight) + ((1 - flakiness_index) * flakiness_weight)
        
        # Map to quality score enum
        if quality_score >= 0.9:
            return QualityScore.EXCELLENT
        elif quality_score >= 0.8:
            return QualityScore.GOOD
        elif quality_score >= 0.7:
            return QualityScore.FAIR
        elif quality_score >= 0.6:
            return QualityScore.POOR
        else:
            return QualityScore.CRITICAL
    
    async def _build_drilldown_navigation(self, filters: ReportFilters) -> Optional[Dict[str, Any]]:
        """Build drill-down navigation context"""
        # Placeholder implementation - would build navigation based on aggregation level
        return None
    
    async def _check_cache(self, request: ReportGenerationRequest) -> Optional[ExecutionReportResponse]:
        """Check if cached report exists for the request"""
        # Placeholder - would implement caching logic
        return None
    
    async def _cache_report(self, request: ReportGenerationRequest, report: ExecutionReportResponse) -> None:
        """Cache the generated report"""
        # Placeholder - would implement caching logic
        pass
    
    async def _store_report(
        self,
        report: ExecutionReportResponse,
        filters: ReportFilters,
        user_id: str
    ) -> None:
        """Store generated report in database"""
        try:
            report_doc = ExecutionReportModel(
                report_id=report.report_id,
                report_type=report.report_type,
                report_name=report.name,
                scope=filters.aggregation_level,
                filters=filters.model_dump(),
                time_range={
                    "start_date": filters.time_range.start_date,
                    "end_date": filters.time_range.end_date
                },
                total_executions=report.total_executions,
                passed_executions=report.passed_executions,
                failed_executions=report.failed_executions,
                cancelled_executions=report.cancelled_executions,
                pass_rate=report.pass_rate,
                flakiness_index=report.flakiness_index,
                quality_score=report.quality_score,
                average_duration_ms=report.average_duration_ms,
                total_duration_ms=report.total_duration_ms,
                generated_by=user_id,
                last_updated=report.generated_at
            )
            
            await self.execution_reports_collection.insert_one(report_doc.to_mongo())
            
        except Exception as e:
            self.logger.warning("Failed to store report", report_id=report.report_id, error=str(e))
    
    async def get_report_list(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get list of reports for a user"""
        try:
            skip = (page - 1) * page_size
            
            # Get reports for user
            cursor = self.execution_reports_collection.find(
                {"generated_by": user_id}
            ).sort("created_at", -1).skip(skip).limit(page_size)
            
            reports = []
            async for doc in cursor:
                reports.append({
                    "report_id": doc.get("report_id"),
                    "name": doc.get("report_name"),
                    "type": doc.get("report_type"),
                    "generated_at": doc.get("created_at"),
                    "generated_by": doc.get("generated_by")
                })
            
            # Get total count
            total_count = await self.execution_reports_collection.count_documents(
                {"generated_by": user_id}
            )
            
            return reports, total_count
            
        except Exception as e:
            self.logger.error("Failed to get report list", user_id=user_id, error=str(e))
            return [], 0


class ReportServiceFactory:
    """Factory for creating ReportService instances with proper dependencies"""
    
    @staticmethod
    def create(
        database: AsyncIOMotorDatabase,
        cache_service: Optional[Any] = None,
        data_aggregation_service: Optional[Any] = None
    ) -> ReportService:
        """Create ReportService instance with dependencies"""
        return ReportService(
            database=database,
            cache_service=cache_service,
            data_aggregation_service=data_aggregation_service
        ) 
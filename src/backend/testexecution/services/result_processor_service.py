"""
Test Execution Engine - Result Processor Service

Provides comprehensive result processing and aggregation including:
- Individual execution result processing and validation
- Test suite result aggregation and summary generation
- Report generation in multiple formats
- Result notification and webhook integration
- Performance metrics and analytics

Implements the progressive observability architecture from creative phase decisions.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
from enum import Enum

from motor.motor_asyncio import AsyncIOMotorDatabase

from ..models.execution_trace_model import (
    ExecutionTraceModel,
    ExecutionStatus,
    StepStatus,
    StepResultModel,
    ExecutionStatistics,
    ExecutionType
)
from ..schemas.execution_schemas import ReportFormat, ResultSeverity

logger = logging.getLogger(__name__)


class ProcessedExecutionResult:
    """Processed execution result with analytics and insights"""
    
    def __init__(
        self,
        execution_id: str,
        status: ExecutionStatus,
        statistics: ExecutionStatistics,
        step_results: List[StepResultModel],
        insights: Dict[str, Any],
        recommendations: List[str]
    ):
        self.execution_id = execution_id
        self.status = status
        self.statistics = statistics
        self.step_results = step_results
        self.insights = insights
        self.recommendations = recommendations
        self.processed_at = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "execution_id": self.execution_id,
            "status": self.status,
            "statistics": self.statistics.model_dump() if self.statistics else None,
            "step_results": [step.model_dump() for step in self.step_results],
            "insights": self.insights,
            "recommendations": self.recommendations,
            "processed_at": self.processed_at.isoformat()
        }


class ResultProcessorService:
    """
    Service for processing and analyzing execution results.
    
    Provides comprehensive result processing, aggregation, analytics,
    and reporting capabilities for test execution results.
    """
    
    def __init__(self, database: AsyncIOMotorDatabase):
        self.database = database
        self.collection = database.execution_traces
        self.results_collection = database.execution_results
        self.analytics_collection = database.execution_analytics
        
        logger.info("ResultProcessorService initialized")
    
    async def process_execution_result(
        self,
        execution_id: str,
        step_results: List[StepResultModel],
        final_status: ExecutionStatus
    ) -> ProcessedExecutionResult:
        """
        Process individual execution result with analytics and insights.
        
        Args:
            execution_id: Execution identifier
            step_results: List of step execution results
            final_status: Final execution status
            
        Returns:
            ProcessedExecutionResult: Processed result with insights
        """
        try:
            logger.info(f"Processing execution result: {execution_id}")
            
            # Calculate execution statistics
            statistics = await self._calculate_execution_statistics(step_results)
            
            # Generate insights and recommendations
            insights = await self._generate_execution_insights(step_results, final_status)
            recommendations = await self._generate_recommendations(step_results, insights)
            
            # Create processed result
            processed_result = ProcessedExecutionResult(
                execution_id=execution_id,
                status=final_status,
                statistics=statistics,
                step_results=step_results,
                insights=insights,
                recommendations=recommendations
            )
            
            # Store processed result
            await self._store_processed_result(processed_result)
            
            # Update execution trace with final statistics
            await self._update_execution_trace(execution_id, statistics, final_status)
            
            logger.info(f"Execution result processed successfully: {execution_id}")
            return processed_result
            
        except Exception as e:
            logger.error(f"Failed to process execution result: {execution_id} - {str(e)}")
            raise
    
    async def aggregate_suite_results(
        self,
        suite_execution_id: str,
        test_case_results: List[ProcessedExecutionResult]
    ) -> Dict[str, Any]:
        """
        Aggregate test suite results from individual test case results.
        
        Args:
            suite_execution_id: Suite execution identifier
            test_case_results: List of processed test case results
            
        Returns:
            Aggregated suite result summary
        """
        try:
            logger.info(f"Aggregating suite results: {suite_execution_id}")
            
            if not test_case_results:
                return {
                    "suite_execution_id": suite_execution_id,
                    "total_test_cases": 0,
                    "overall_status": ExecutionStatus.PASSED,
                    "summary": "No test cases executed"
                }
            
            # Calculate suite-level statistics
            total_cases = len(test_case_results)
            passed_cases = len([r for r in test_case_results if r.status == ExecutionStatus.PASSED])
            failed_cases = len([r for r in test_case_results if r.status == ExecutionStatus.FAILED])
            cancelled_cases = len([r for r in test_case_results if r.status == ExecutionStatus.CANCELLED])
            
            # Determine overall suite status
            if failed_cases > 0:
                overall_status = ExecutionStatus.FAILED
            elif cancelled_cases > 0:
                overall_status = ExecutionStatus.CANCELLED
            else:
                overall_status = ExecutionStatus.PASSED
            
            # Calculate aggregated timing
            total_duration = sum(
                r.statistics.total_duration_ms or 0 for r in test_case_results if r.statistics
            )
            
            # Generate suite insights
            suite_insights = await self._generate_suite_insights(test_case_results)
            
            # Create aggregated result
            aggregated_result = {
                "suite_execution_id": suite_execution_id,
                "total_test_cases": total_cases,
                "passed_cases": passed_cases,
                "failed_cases": failed_cases,
                "cancelled_cases": cancelled_cases,
                "success_rate": (passed_cases / total_cases) * 100 if total_cases > 0 else 0,
                "overall_status": overall_status,
                "total_duration_ms": total_duration,
                "average_case_duration_ms": total_duration / total_cases if total_cases > 0 else 0,
                "insights": suite_insights,
                "test_case_results": [r.to_dict() for r in test_case_results],
                "aggregated_at": datetime.now(timezone.utc).isoformat()
            }
            
            # Store aggregated result
            await self._store_suite_result(aggregated_result)
            
            logger.info(f"Suite results aggregated successfully: {suite_execution_id}")
            return aggregated_result
            
        except Exception as e:
            logger.error(f"Failed to aggregate suite results: {suite_execution_id} - {str(e)}")
            raise
    
    async def generate_execution_report(
        self,
        execution_id: str,
        report_format: ReportFormat = ReportFormat.JSON,
        include_details: bool = True
    ) -> Dict[str, Any]:
        """
        Generate comprehensive execution report.
        
        Args:
            execution_id: Execution identifier
            report_format: Desired report format
            include_details: Whether to include detailed step information
            
        Returns:
            Generated report data
        """
        try:
            logger.info(f"Generating execution report: {execution_id} ({report_format})")
            
            # Load execution data
            execution = await self._load_execution_data(execution_id)
            if not execution:
                raise ValueError(f"Execution not found: {execution_id}")
            
            # Load processed result
            processed_result = await self._load_processed_result(execution_id)
            
            # Generate report based on format
            if report_format == ReportFormat.JSON:
                report = await self._generate_json_report(execution, processed_result, include_details)
            elif report_format == ReportFormat.HTML:
                report = await self._generate_html_report(execution, processed_result, include_details)
            elif report_format == ReportFormat.CSV:
                report = await self._generate_csv_report(execution, processed_result, include_details)
            else:
                raise ValueError(f"Unsupported report format: {report_format}")
            
            logger.info(f"Execution report generated successfully: {execution_id}")
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate execution report: {execution_id} - {str(e)}")
            raise
    
    async def get_execution_analytics(
        self,
        time_range_days: int = 30,
        execution_type: Optional[ExecutionType] = None
    ) -> Dict[str, Any]:
        """
        Get execution analytics and trends.
        
        Args:
            time_range_days: Number of days to analyze
            execution_type: Filter by execution type
            
        Returns:
            Analytics data with trends and insights
        """
        try:
            logger.info(f"Generating execution analytics for {time_range_days} days")
            
            # Calculate date range
            end_date = datetime.now(timezone.utc)
            start_date = end_date.replace(day=end_date.day - time_range_days)
            
            # Build query
            query = {
                "triggered_at": {"$gte": start_date, "$lte": end_date}
            }
            if execution_type:
                query["execution_type"] = execution_type
            
            # Aggregate execution data
            pipeline = [
                {"$match": query},
                {"$group": {
                    "_id": {
                        "status": "$status",
                        "execution_type": "$execution_type",
                        "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$triggered_at"}}
                    },
                    "count": {"$sum": 1},
                    "avg_duration": {"$avg": "$statistics.total_duration_ms"},
                    "total_duration": {"$sum": "$statistics.total_duration_ms"}
                }},
                {"$sort": {"_id.date": 1}}
            ]
            
            cursor = self.collection.aggregate(pipeline)
            aggregated_data = []
            async for doc in cursor:
                aggregated_data.append(doc)
            
            # Process analytics
            analytics = await self._process_analytics_data(aggregated_data, time_range_days)
            
            logger.info("Execution analytics generated successfully")
            return analytics
            
        except Exception as e:
            logger.error(f"Failed to generate execution analytics: {str(e)}")
            raise
    
    # Private Helper Methods
    
    async def _calculate_execution_statistics(
        self,
        step_results: List[StepResultModel]
    ) -> ExecutionStatistics:
        """Calculate comprehensive execution statistics."""
        if not step_results:
            return ExecutionStatistics()
        
        total_steps = len(step_results)
        completed_steps = len([s for s in step_results if s.status in [StepStatus.PASSED, StepStatus.FAILED]])
        passed_steps = len([s for s in step_results if s.status == StepStatus.PASSED])
        failed_steps = len([s for s in step_results if s.status == StepStatus.FAILED])
        
        # Calculate timing
        durations = [s.duration_ms for s in step_results if s.duration_ms is not None]
        total_duration = sum(durations) if durations else 0
        avg_step_duration = total_duration / len(durations) if durations else 0
        
        # Calculate rates
        success_rate = (passed_steps / total_steps) if total_steps > 0 else 0
        error_rate = (failed_steps / total_steps) if total_steps > 0 else 0
        
        return ExecutionStatistics(
            total_steps=total_steps,
            completed_steps=completed_steps,
            progress_percentage=100.0 if completed_steps == total_steps else (completed_steps / total_steps) * 100,
            total_duration_ms=total_duration,
            average_step_duration_ms=avg_step_duration,
            success_rate=success_rate,
            error_rate=error_rate,
            retry_rate=0.0  # Would be calculated from retry information
        )
    
    async def _generate_execution_insights(
        self,
        step_results: List[StepResultModel],
        final_status: ExecutionStatus
    ) -> Dict[str, Any]:
        """Generate insights from execution results."""
        insights = {
            "performance": {},
            "reliability": {},
            "patterns": {},
            "issues": []
        }
        
        if not step_results:
            return insights
        
        # Performance insights
        durations = [s.duration_ms for s in step_results if s.duration_ms is not None]
        if durations:
            insights["performance"] = {
                "fastest_step_ms": min(durations),
                "slowest_step_ms": max(durations),
                "median_step_ms": sorted(durations)[len(durations) // 2],
                "performance_variance": max(durations) - min(durations)
            }
        
        # Reliability insights
        failed_steps = [s for s in step_results if s.status == StepStatus.FAILED]
        if failed_steps:
            error_types = {}
            for step in failed_steps:
                if step.error_details:
                    error_type = step.error_details.get("error_type", "Unknown")
                    error_types[error_type] = error_types.get(error_type, 0) + 1
            
            insights["reliability"] = {
                "failure_count": len(failed_steps),
                "common_errors": error_types,
                "failure_rate": len(failed_steps) / len(step_results)
            }
        
        # Pattern detection
        step_statuses = [s.status for s in step_results]
        if len(set(step_statuses)) == 1:
            insights["patterns"]["consistent_results"] = True
        
        # Issue identification
        if final_status == ExecutionStatus.FAILED:
            insights["issues"].append("Execution failed - review failed steps")
        
        if insights["performance"].get("performance_variance", 0) > 10000:  # 10 seconds
            insights["issues"].append("High performance variance detected")
        
        return insights
    
    async def _generate_recommendations(
        self,
        step_results: List[StepResultModel],
        insights: Dict[str, Any]
    ) -> List[str]:
        """Generate recommendations based on execution analysis."""
        recommendations = []
        
        # Performance recommendations
        if insights.get("performance", {}).get("slowest_step_ms", 0) > 30000:  # 30 seconds
            recommendations.append("Consider optimizing slow steps or increasing timeouts")
        
        # Reliability recommendations
        reliability = insights.get("reliability", {})
        if reliability.get("failure_rate", 0) > 0.2:  # 20% failure rate
            recommendations.append("High failure rate detected - review test case stability")
        
        # Error-specific recommendations
        common_errors = reliability.get("common_errors", {})
        if "TimeoutError" in common_errors:
            recommendations.append("Timeout errors detected - consider increasing step timeouts")
        
        if "AssertionError" in common_errors:
            recommendations.append("Assertion failures detected - review expected vs actual results")
        
        # General recommendations
        if not recommendations:
            recommendations.append("Execution completed successfully - no specific recommendations")
        
        return recommendations
    
    async def _generate_suite_insights(
        self,
        test_case_results: List[ProcessedExecutionResult]
    ) -> Dict[str, Any]:
        """Generate insights for test suite execution."""
        insights = {
            "performance": {},
            "reliability": {},
            "coverage": {},
            "trends": {}
        }
        
        if not test_case_results:
            return insights
        
        # Performance insights
        durations = [r.statistics.total_duration_ms for r in test_case_results if r.statistics and r.statistics.total_duration_ms]
        if durations:
            insights["performance"] = {
                "fastest_case_ms": min(durations),
                "slowest_case_ms": max(durations),
                "total_suite_duration_ms": sum(durations),
                "average_case_duration_ms": sum(durations) / len(durations)
            }
        
        # Reliability insights
        failed_results = [r for r in test_case_results if r.status == ExecutionStatus.FAILED]
        insights["reliability"] = {
            "suite_success_rate": (len(test_case_results) - len(failed_results)) / len(test_case_results),
            "failed_test_cases": len(failed_results),
            "total_test_cases": len(test_case_results)
        }
        
        return insights
    
    async def _store_processed_result(self, processed_result: ProcessedExecutionResult) -> None:
        """Store processed result in database."""
        try:
            await self.results_collection.insert_one(processed_result.to_dict())
        except Exception as e:
            logger.error(f"Failed to store processed result: {processed_result.execution_id} - {str(e)}")
    
    async def _store_suite_result(self, suite_result: Dict[str, Any]) -> None:
        """Store aggregated suite result in database."""
        try:
            await self.results_collection.insert_one(suite_result)
        except Exception as e:
            logger.error(f"Failed to store suite result: {suite_result.get('suite_execution_id')} - {str(e)}")
    
    async def _update_execution_trace(
        self,
        execution_id: str,
        statistics: ExecutionStatistics,
        final_status: ExecutionStatus
    ) -> None:
        """Update execution trace with final statistics."""
        try:
            from bson import ObjectId
            await self.collection.update_one(
                {"_id": ObjectId(execution_id)},
                {"$set": {
                    "statistics": statistics.model_dump(),
                    "status": final_status,
                    "completed_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc)
                }}
            )
        except Exception as e:
            logger.error(f"Failed to update execution trace: {execution_id} - {str(e)}")
    
    async def _load_execution_data(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Load execution data from database."""
        try:
            from bson import ObjectId
            doc = await self.collection.find_one({"_id": ObjectId(execution_id)})
            if doc:
                doc['execution_id'] = str(doc['_id'])
                return doc
            return None
        except Exception as e:
            logger.error(f"Failed to load execution data: {execution_id} - {str(e)}")
            return None
    
    async def _load_processed_result(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Load processed result from database."""
        try:
            doc = await self.results_collection.find_one({"execution_id": execution_id})
            return doc
        except Exception as e:
            logger.error(f"Failed to load processed result: {execution_id} - {str(e)}")
            return None
    
    async def _generate_json_report(
        self,
        execution: Dict[str, Any],
        processed_result: Optional[Dict[str, Any]],
        include_details: bool
    ) -> Dict[str, Any]:
        """Generate JSON format report."""
        report = {
            "report_type": "execution_report",
            "format": "json",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "execution": {
                "execution_id": execution["execution_id"],
                "status": execution["status"],
                "execution_type": execution["execution_type"],
                "triggered_by": execution["triggered_by"],
                "triggered_at": execution["triggered_at"].isoformat() if isinstance(execution["triggered_at"], datetime) else execution["triggered_at"],
                "completed_at": execution.get("completed_at").isoformat() if execution.get("completed_at") else None
            }
        }
        
        if processed_result:
            report["results"] = processed_result
        
        if include_details and execution.get("embedded_steps"):
            report["step_details"] = execution["embedded_steps"]
        
        return report
    
    async def _generate_html_report(
        self,
        execution: Dict[str, Any],
        processed_result: Optional[Dict[str, Any]],
        include_details: bool
    ) -> Dict[str, Any]:
        """Generate HTML format report."""
        # Simplified HTML report generation
        html_content = f"""
        <html>
        <head><title>Execution Report - {execution['execution_id']}</title></head>
        <body>
        <h1>Test Execution Report</h1>
        <h2>Execution Details</h2>
        <p>ID: {execution['execution_id']}</p>
        <p>Status: {execution['status']}</p>
        <p>Type: {execution['execution_type']}</p>
        <p>Triggered By: {execution['triggered_by']}</p>
        </body>
        </html>
        """
        
        return {
            "content": html_content,
            "content_type": "text/html"
        }
    
    async def _generate_csv_report(
        self,
        execution: Dict[str, Any],
        processed_result: Optional[Dict[str, Any]],
        include_details: bool
    ) -> Dict[str, Any]:
        """Generate CSV format report."""
        # Simplified CSV report generation
        csv_content = "execution_id,status,type,triggered_by,triggered_at\n"
        csv_content += f"{execution['execution_id']},{execution['status']},{execution['execution_type']},{execution['triggered_by']},{execution['triggered_at']}\n"
        
        return {
            "content": csv_content,
            "content_type": "text/csv"
        }
    
    async def _process_analytics_data(
        self,
        aggregated_data: List[Dict[str, Any]],
        time_range_days: int
    ) -> Dict[str, Any]:
        """Process aggregated data into analytics insights."""
        analytics = {
            "time_range_days": time_range_days,
            "total_executions": 0,
            "status_distribution": {},
            "type_distribution": {},
            "daily_trends": [],
            "performance_metrics": {},
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Process aggregated data
        for item in aggregated_data:
            analytics["total_executions"] += item["count"]
            
            # Status distribution
            status = item["_id"]["status"]
            analytics["status_distribution"][status] = analytics["status_distribution"].get(status, 0) + item["count"]
            
            # Type distribution
            exec_type = item["_id"]["execution_type"]
            analytics["type_distribution"][exec_type] = analytics["type_distribution"].get(exec_type, 0) + item["count"]
        
        return analytics


class ResultProcessorServiceFactory:
    """Factory for creating ResultProcessorService instances."""
    
    @staticmethod
    def create(database: AsyncIOMotorDatabase) -> ResultProcessorService:
        """Create ResultProcessorService instance with database dependency."""
        return ResultProcessorService(database) 
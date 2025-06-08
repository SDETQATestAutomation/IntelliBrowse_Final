"""
Execution Reporting Module - Quality Metrics Service

Service for quality assessment including flakiness scoring, stability trends,
MTTR (Mean Time To Resolve) analysis, and risk heatmap generation.
"""

import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from statistics import mean, median
from collections import defaultdict, Counter
from motor.motor_asyncio import AsyncIOMotorDatabase

from ...config.logging import get_logger
from ..models.execution_report_model import (
    QualityMetricsModel, QualityScore, QualityThreshold
)
from ..schemas.report_schemas import (
    QualityMetricsResponse, TimeRangeFilter, MetricFilter
)

logger = get_logger(__name__)


class QualityMetricsService:
    """
    Advanced quality metrics service for comprehensive quality assessment.
    
    Provides quality analytics capabilities including:
    - Flakiness detection and scoring
    - Stability trend analysis
    - MTTR (Mean Time To Resolve) calculation
    - Risk heatmap generation
    - Quality threshold monitoring
    """
    
    def __init__(
        self,
        database: AsyncIOMotorDatabase,
        cache_service: Optional[Any] = None,
        data_aggregation_service: Optional[Any] = None
    ):
        """Initialize quality metrics service with dependencies"""
        self.database = database
        self.cache_service = cache_service
        self.data_aggregation_service = data_aggregation_service
        self.logger = logger.bind(service="QualityMetricsService")
        
        # Collections
        self.quality_metrics_collection = self.database.quality_metrics
        self.execution_traces_collection = self.database.execution_traces
        self.test_cases_collection = self.database.test_cases
        
    async def calculate_quality_metrics(
        self,
        time_range: TimeRangeFilter,
        metrics: MetricFilter,
        user_id: str = None
    ) -> QualityMetricsResponse:
        """
        Calculate comprehensive quality metrics for execution data.
        
        Args:
            time_range: Time period for quality analysis
            metrics: Metric filters for scope selection
            user_id: ID of user requesting metrics
            
        Returns:
            QualityMetricsResponse: Comprehensive quality metrics data
            
        Raises:
            ValueError: If parameters are invalid
            RuntimeError: If calculation fails
        """
        start_time = datetime.now(timezone.utc)
        metrics_id = f"quality_{uuid.uuid4().hex[:12]}"
        
        try:
            self.logger.info(
                "Starting quality metrics calculation",
                metrics_id=metrics_id,
                user_id=user_id
            )
            
            # Check cache for existing metrics
            if self.cache_service:
                cached_metrics = await self._check_quality_cache(time_range, metrics)
                if cached_metrics:
                    self.logger.info("Returning cached quality metrics", metrics_id=metrics_id)
                    return cached_metrics
            
            # Calculate fresh quality metrics
            quality_data = await self._calculate_fresh_metrics(
                time_range, metrics, metrics_id, user_id
            )
            
            # Cache the result
            if self.cache_service:
                await self._cache_quality_metrics(time_range, metrics, quality_data)
            
            calculation_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            self.logger.info(
                "Quality metrics calculation completed",
                metrics_id=metrics_id,
                calculation_time_ms=calculation_time
            )
            
            return quality_data
            
        except Exception as e:
            self.logger.error(
                "Quality metrics calculation failed",
                metrics_id=metrics_id,
                error=str(e),
                exc_info=True
            )
            raise RuntimeError(f"Failed to calculate quality metrics: {str(e)}") from e
    
    async def _calculate_fresh_metrics(
        self,
        time_range: TimeRangeFilter,
        metrics: MetricFilter,
        metrics_id: str,
        user_id: str
    ) -> QualityMetricsResponse:
        """Calculate fresh quality metrics from database data"""
        
        # Build query for execution data
        query = await self._build_quality_query(time_range, metrics)
        
        # Get execution data
        executions = []
        async for execution in self.execution_traces_collection.find(query):
            executions.append(execution)
        
        # Calculate core metrics
        overall_score = await self._calculate_overall_quality_score(executions)
        flakiness_score = await self._calculate_flakiness_score(executions)
        stability_score = await self._calculate_stability_score(executions)
        mttr = await self._calculate_mttr(executions)
        
        # Generate risk assessment
        risk_factors = await self._analyze_risk_factors(executions)
        recommendations = await self._generate_recommendations(executions, overall_score)
        
        # Calculate threshold violations
        threshold_violations = await self._check_threshold_violations(
            overall_score, flakiness_score, stability_score, mttr
        )
        
        # Create quality metrics response
        quality_metrics = QualityMetricsResponse(
            metrics_id=metrics_id,
            overall_quality_score=overall_score,
            flakiness_score=flakiness_score,
            stability_score=stability_score,
            mttr_hours=mttr,
            total_test_cases=await self._count_unique_test_cases(executions),
            passing_test_cases=await self._count_passing_test_cases(executions),
            failing_test_cases=await self._count_failing_test_cases(executions),
            flaky_test_cases=await self._count_flaky_test_cases(executions),
            risk_factors=risk_factors,
            recommendations=recommendations,
            threshold_violations=threshold_violations,
            generated_at=datetime.now(timezone.utc),
            data_freshness_seconds=0
        )
        
        # Store metrics for future reference
        await self._store_quality_metrics(quality_metrics, time_range, metrics, user_id)
        
        return quality_metrics
    
    async def _build_quality_query(
        self,
        time_range: TimeRangeFilter,
        metrics: MetricFilter
    ) -> Dict[str, Any]:
        """Build MongoDB query for quality metrics calculation"""
        
        query = {
            "triggered_at": {
                "$gte": time_range.start_date,
                "$lte": time_range.end_date
            }
        }
        
        # Add metric filters
        if metrics.test_suite_ids:
            query["test_suite_id"] = {"$in": metrics.test_suite_ids}
        if metrics.test_case_ids:
            query["test_case_id"] = {"$in": metrics.test_case_ids}
        if metrics.execution_types:
            query["execution_type"] = {"$in": metrics.execution_types}
        if metrics.status_filter:
            query["status"] = {"$in": metrics.status_filter}
        if metrics.tags:
            query["tags"] = {"$in": metrics.tags}
        
        return query
    
    async def _calculate_overall_quality_score(self, executions: List[Dict[str, Any]]) -> QualityScore:
        """Calculate overall quality score based on multiple factors"""
        
        if not executions:
            return QualityScore.POOR
        
        # Calculate base pass rate
        total_executions = len(executions)
        passed_executions = sum(1 for exec in executions if exec.get("status") == "passed")
        pass_rate = passed_executions / total_executions if total_executions > 0 else 0
        
        # Calculate consistency factor (inverse of flakiness)
        flaky_tests = await self._identify_flaky_tests(executions)
        total_tests = len(set(exec.get("test_case_id") for exec in executions))
        consistency_factor = 1.0 - (len(flaky_tests) / total_tests if total_tests > 0 else 0)
        
        # Calculate duration stability
        durations = [exec.get("execution_duration_ms", 0) for exec in executions if exec.get("execution_duration_ms")]
        duration_stability = self._calculate_duration_stability(durations)
        
        # Weighted quality score calculation
        quality_score = (
            pass_rate * 0.5 +  # 50% weight on pass rate
            consistency_factor * 0.3 +  # 30% weight on consistency
            duration_stability * 0.2  # 20% weight on duration stability
        )
        
        # Map to quality score enum
        if quality_score >= 0.9:
            return QualityScore.EXCELLENT
        elif quality_score >= 0.8:
            return QualityScore.GOOD
        elif quality_score >= 0.6:
            return QualityScore.AVERAGE
        elif quality_score >= 0.4:
            return QualityScore.BELOW_AVERAGE
        else:
            return QualityScore.POOR
    
    async def _calculate_flakiness_score(self, executions: List[Dict[str, Any]]) -> float:
        """Calculate flakiness score based on test result consistency"""
        
        # Group executions by test case
        test_results = defaultdict(list)
        for execution in executions:
            test_id = execution.get("test_case_id")
            status = execution.get("status")
            if test_id and status:
                test_results[test_id].append(status)
        
        flaky_count = 0
        total_tests = len(test_results)
        
        for test_id, results in test_results.items():
            if len(set(results)) > 1:  # Test has both pass and fail results
                # Calculate flakiness intensity
                result_counts = Counter(results)
                min_count = min(result_counts.values())
                max_count = max(result_counts.values())
                
                # Consider it flaky if minority results are > 10% of total
                if min_count / len(results) > 0.1:
                    flaky_count += 1
        
        return flaky_count / total_tests if total_tests > 0 else 0.0
    
    def _calculate_duration_stability(self, durations: List[float]) -> float:
        """Calculate stability score based on execution duration consistency"""
        
        if len(durations) < 2:
            return 1.0  # Assume stable if insufficient data
        
        try:
            duration_mean = mean(durations)
            duration_std = (sum((x - duration_mean) ** 2 for x in durations) / len(durations)) ** 0.5
            
            # Coefficient of variation (CV) as stability measure
            cv = duration_std / duration_mean if duration_mean > 0 else 0
            
            # Convert CV to stability score (lower CV = higher stability)
            stability = max(0.0, 1.0 - cv)
            return min(1.0, stability)
        except:
            return 0.5  # Default moderate stability
    
    async def _identify_flaky_tests(self, executions: List[Dict[str, Any]]) -> List[str]:
        """Identify flaky test cases from execution data"""
        
        test_results = defaultdict(list)
        for execution in executions:
            test_id = execution.get("test_case_id")
            status = execution.get("status")
            if test_id and status:
                test_results[test_id].append(status)
        
        flaky_tests = []
        for test_id, results in test_results.items():
            if len(set(results)) > 1:  # Has both pass and fail
                result_counts = Counter(results)
                min_count = min(result_counts.values())
                
                # Flaky if minority results are > 10% of total
                if min_count / len(results) > 0.1:
                    flaky_tests.append(test_id)
        
        return flaky_tests
    
    async def _calculate_stability_score(self, executions: List[Dict[str, Any]]) -> float:
        """Calculate stability score based on execution consistency"""
        
        if not executions:
            return 0.0
        
        # Group by time periods to check stability over time
        time_buckets = defaultdict(list)
        for execution in executions:
            triggered_at = execution.get("triggered_at")
            if triggered_at:
                # Group by day
                day_key = triggered_at.date()
                status = execution.get("status")
                time_buckets[day_key].append(status)
        
        stable_periods = 0
        total_periods = len(time_buckets)
        
        for period, statuses in time_buckets.items():
            if statuses:
                pass_rate = sum(1 for s in statuses if s == "passed") / len(statuses)
                # Consider stable if pass rate is > 80% or < 20% (consistently good or bad)
                if pass_rate > 0.8 or pass_rate < 0.2:
                    stable_periods += 1
        
        return stable_periods / total_periods if total_periods > 0 else 0.0
    
    async def _calculate_mttr(self, executions: List[Dict[str, Any]]) -> float:
        """Calculate Mean Time To Resolve (MTTR) for failed tests"""
        
        # Group executions by test case and sort by time
        test_timelines = defaultdict(list)
        for execution in executions:
            test_id = execution.get("test_case_id")
            if test_id:
                test_timelines[test_id].append({
                    "status": execution.get("status"),
                    "triggered_at": execution.get("triggered_at"),
                    "execution_id": execution.get("_id")
                })
        
        resolution_times = []
        
        for test_id, timeline in test_timelines.items():
            # Sort by time
            timeline.sort(key=lambda x: x["triggered_at"])
            
            # Find failure to resolution patterns
            failure_start = None
            for execution in timeline:
                if execution["status"] == "failed" and failure_start is None:
                    failure_start = execution["triggered_at"]
                elif execution["status"] == "passed" and failure_start is not None:
                    # Resolution found
                    resolution_time = execution["triggered_at"] - failure_start
                    resolution_times.append(resolution_time.total_seconds() / 3600)  # Convert to hours
                    failure_start = None
        
        return mean(resolution_times) if resolution_times else 0.0
    
    async def _count_unique_test_cases(self, executions: List[Dict[str, Any]]) -> int:
        """Count unique test cases in executions"""
        return len(set(exec.get("test_case_id") for exec in executions if exec.get("test_case_id")))
    
    async def _count_passing_test_cases(self, executions: List[Dict[str, Any]]) -> int:
        """Count test cases that have at least one passing execution"""
        passing_tests = set()
        for execution in executions:
            if execution.get("status") == "passed":
                test_id = execution.get("test_case_id")
                if test_id:
                    passing_tests.add(test_id)
        return len(passing_tests)
    
    async def _count_failing_test_cases(self, executions: List[Dict[str, Any]]) -> int:
        """Count test cases that have only failing executions"""
        test_statuses = defaultdict(set)
        for execution in executions:
            test_id = execution.get("test_case_id")
            status = execution.get("status")
            if test_id and status:
                test_statuses[test_id].add(status)
        
        failing_only = sum(1 for statuses in test_statuses.values() 
                          if "failed" in statuses and "passed" not in statuses)
        return failing_only
    
    async def _count_flaky_test_cases(self, executions: List[Dict[str, Any]]) -> int:
        """Count flaky test cases"""
        flaky_tests = await self._identify_flaky_tests(executions)
        return len(flaky_tests)
    
    async def _analyze_risk_factors(self, executions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analyze risk factors from execution data"""
        
        risk_factors = []
        
        # High failure rate risk
        total_executions = len(executions)
        failed_executions = sum(1 for exec in executions if exec.get("status") == "failed")
        failure_rate = failed_executions / total_executions if total_executions > 0 else 0
        
        if failure_rate > 0.3:  # >30% failure rate
            risk_factors.append({
                "type": "high_failure_rate",
                "severity": "high" if failure_rate > 0.5 else "medium",
                "description": f"High failure rate detected: {failure_rate:.1%}",
                "impact": "Quality degradation and reduced confidence"
            })
        
        # Flaky tests risk
        flaky_tests = await self._identify_flaky_tests(executions)
        if len(flaky_tests) > 0:
            total_tests = await self._count_unique_test_cases(executions)
            flaky_percentage = len(flaky_tests) / total_tests if total_tests > 0 else 0
            
            if flaky_percentage > 0.1:  # >10% flaky tests
                risk_factors.append({
                    "type": "test_flakiness",
                    "severity": "high" if flaky_percentage > 0.2 else "medium",
                    "description": f"Flaky tests detected: {len(flaky_tests)} tests ({flaky_percentage:.1%})",
                    "impact": "Unreliable test results and reduced trust"
                })
        
        # Long duration risk
        durations = [exec.get("execution_duration_ms", 0) for exec in executions if exec.get("execution_duration_ms")]
        if durations:
            avg_duration = mean(durations)
            if avg_duration > 300000:  # >5 minutes average
                risk_factors.append({
                    "type": "long_execution_time",
                    "severity": "medium",
                    "description": f"Long average execution time: {avg_duration/60000:.1f} minutes",
                    "impact": "Slower feedback and reduced development velocity"
                })
        
        return risk_factors
    
    async def _generate_recommendations(
        self,
        executions: List[Dict[str, Any]],
        quality_score: QualityScore
    ) -> List[str]:
        """Generate actionable recommendations based on quality analysis"""
        
        recommendations = []
        
        # Quality-based recommendations
        if quality_score in [QualityScore.POOR, QualityScore.BELOW_AVERAGE]:
            recommendations.append("Review and fix failing test cases to improve overall quality")
            recommendations.append("Implement additional error handling and validation")
        
        # Flaky test recommendations
        flaky_tests = await self._identify_flaky_tests(executions)
        if len(flaky_tests) > 0:
            recommendations.append("Investigate and fix flaky tests to improve reliability")
            recommendations.append("Consider adding wait conditions or improving test isolation")
        
        # Performance recommendations
        durations = [exec.get("execution_duration_ms", 0) for exec in executions if exec.get("execution_duration_ms")]
        if durations:
            avg_duration = mean(durations)
            if avg_duration > 180000:  # >3 minutes
                recommendations.append("Optimize test execution time to improve feedback speed")
                recommendations.append("Consider parallel execution or test case optimization")
        
        # Coverage recommendations
        total_tests = await self._count_unique_test_cases(executions)
        if total_tests < 10:
            recommendations.append("Increase test coverage to improve quality confidence")
        
        return recommendations
    
    async def _check_threshold_violations(
        self,
        quality_score: QualityScore,
        flakiness_score: float,
        stability_score: float,
        mttr: float
    ) -> List[Dict[str, Any]]:
        """Check for quality threshold violations"""
        
        violations = []
        
        # Quality score thresholds
        if quality_score == QualityScore.POOR:
            violations.append({
                "metric": "overall_quality",
                "threshold": "GOOD",
                "actual": quality_score.value,
                "severity": "high"
            })
        
        # Flakiness threshold
        if flakiness_score > 0.15:  # >15% flaky tests
            violations.append({
                "metric": "flakiness",
                "threshold": "0.15",
                "actual": flakiness_score,
                "severity": "medium"
            })
        
        # Stability threshold
        if stability_score < 0.7:  # <70% stability
            violations.append({
                "metric": "stability",
                "threshold": "0.70",
                "actual": stability_score,
                "severity": "medium"
            })
        
        # MTTR threshold
        if mttr > 24:  # >24 hours MTTR
            violations.append({
                "metric": "mttr",
                "threshold": "24.0",
                "actual": mttr,
                "severity": "high"
            })
        
        return violations
    
    async def _check_quality_cache(
        self,
        time_range: TimeRangeFilter,
        metrics: MetricFilter
    ) -> Optional[QualityMetricsResponse]:
        """Check cache for existing quality metrics"""
        # Implement cache checking logic
        return None
    
    async def _cache_quality_metrics(
        self,
        time_range: TimeRangeFilter,
        metrics: MetricFilter,
        quality_data: QualityMetricsResponse
    ) -> None:
        """Cache quality metrics result"""
        # Implement caching logic
        pass
    
    async def _store_quality_metrics(
        self,
        metrics: QualityMetricsResponse,
        time_range: TimeRangeFilter,
        filters: MetricFilter,
        user_id: str
    ) -> None:
        """Store quality metrics in database"""
        
        quality_model = QualityMetricsModel(
            metrics_id=metrics.metrics_id,
            overall_quality_score=metrics.overall_quality_score,
            flakiness_score=metrics.flakiness_score,
            stability_score=metrics.stability_score,
            mttr_hours=metrics.mttr_hours,
            total_test_cases=metrics.total_test_cases,
            passing_test_cases=metrics.passing_test_cases,
            failing_test_cases=metrics.failing_test_cases,
            flaky_test_cases=metrics.flaky_test_cases,
            generated_by=user_id,
            metadata={
                "time_range": {
                    "start": time_range.start_date.isoformat(),
                    "end": time_range.end_date.isoformat()
                },
                "filters": filters.dict() if filters else {},
                "risk_factors": metrics.risk_factors,
                "recommendations": metrics.recommendations,
                "threshold_violations": metrics.threshold_violations
            }
        )
        
        await self.quality_metrics_collection.insert_one(quality_model.dict(by_alias=True))


class QualityMetricsServiceFactory:
    """Factory for creating QualityMetricsService instances"""
    
    @staticmethod
    def create(
        database: AsyncIOMotorDatabase,
        cache_service: Optional[Any] = None,
        data_aggregation_service: Optional[Any] = None
    ) -> QualityMetricsService:
        """Create and configure QualityMetricsService instance"""
        return QualityMetricsService(
            database=database,
            cache_service=cache_service,
            data_aggregation_service=data_aggregation_service
        ) 
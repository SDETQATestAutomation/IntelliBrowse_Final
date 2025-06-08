"""
Test Execution Engine - Execution Monitoring Service

Provides comprehensive monitoring and observability including:
- Real-time execution metrics collection
- Performance monitoring and analytics
- Health checks and system status
- Alerting and notification integration
- Dashboard data aggregation

Implements the progressive observability architecture from creative phase decisions.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, AsyncIterator
from enum import Enum
import asyncio

from motor.motor_asyncio import AsyncIOMotorDatabase

from ..models.execution_trace_model import (
    ExecutionStatus,
    ExecutionType,
    StepStatus,
    ExecutionStatistics
)

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """System health status levels"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    DOWN = "down"


class MetricType(str, Enum):
    """Types of metrics collected"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


class AlertSeverity(str, Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ExecutionMetric:
    """Execution metric data structure"""
    
    def __init__(
        self,
        name: str,
        metric_type: MetricType,
        value: float,
        tags: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None
    ):
        self.name = name
        self.metric_type = metric_type
        self.value = value
        self.tags = tags or {}
        self.timestamp = timestamp or datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metric to dictionary for storage"""
        return {
            "name": self.name,
            "type": self.metric_type,
            "value": self.value,
            "tags": self.tags,
            "timestamp": self.timestamp.isoformat()
        }


class HealthCheck:
    """Health check result"""
    
    def __init__(
        self,
        component: str,
        status: HealthStatus,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        response_time_ms: Optional[float] = None
    ):
        self.component = component
        self.status = status
        self.message = message
        self.details = details or {}
        self.response_time_ms = response_time_ms
        self.checked_at = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert health check to dictionary"""
        return {
            "component": self.component,
            "status": self.status,
            "message": self.message,
            "details": self.details,
            "response_time_ms": self.response_time_ms,
            "checked_at": self.checked_at.isoformat()
        }


class ExecutionMonitoringService:
    """
    Service for monitoring test execution engine performance and health.
    
    Provides comprehensive monitoring capabilities including metrics collection,
    health checks, performance analytics, and alerting integration.
    """
    
    def __init__(self, database: AsyncIOMotorDatabase):
        self.database = database
        self.collection = database.execution_traces
        self.metrics_collection = database.execution_metrics
        self.health_collection = database.health_checks
        self.alerts_collection = database.execution_alerts
        
        # Monitoring configuration
        self.metrics_retention_days = 30
        self.health_check_interval_seconds = 60
        self.alert_thresholds = {
            "execution_failure_rate": 0.2,  # 20%
            "queue_depth": 100,
            "average_execution_time_ms": 300000,  # 5 minutes
            "system_response_time_ms": 5000  # 5 seconds
        }
        
        # Background monitoring
        self._monitoring_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
        logger.info("ExecutionMonitoringService initialized")
    
    async def collect_execution_metrics(self, execution_id: str) -> Dict[str, Any]:
        """
        Collect comprehensive metrics for a specific execution.
        
        Args:
            execution_id: Execution identifier
            
        Returns:
            Collected metrics data
        """
        try:
            logger.debug(f"Collecting execution metrics: {execution_id}")
            
            # Load execution data
            from bson import ObjectId
            execution_doc = await self.collection.find_one({"_id": ObjectId(execution_id)})
            if not execution_doc:
                raise ValueError(f"Execution not found: {execution_id}")
            
            # Calculate metrics
            metrics = {}
            
            # Basic execution metrics
            metrics["execution_duration_ms"] = execution_doc.get("statistics", {}).get("total_duration_ms", 0)
            metrics["execution_status"] = execution_doc.get("status")
            metrics["execution_type"] = execution_doc.get("execution_type")
            metrics["step_count"] = execution_doc.get("statistics", {}).get("total_steps", 0)
            metrics["success_rate"] = execution_doc.get("statistics", {}).get("success_rate", 0)
            
            # Performance metrics
            if execution_doc.get("statistics"):
                stats = execution_doc["statistics"]
                metrics["average_step_duration_ms"] = stats.get("average_step_duration_ms", 0)
                metrics["error_rate"] = stats.get("error_rate", 0)
                metrics["retry_rate"] = stats.get("retry_rate", 0)
            
            # Timing metrics
            triggered_at = execution_doc.get("triggered_at")
            started_at = execution_doc.get("started_at")
            completed_at = execution_doc.get("completed_at")
            
            if triggered_at and started_at:
                if isinstance(triggered_at, str):
                    triggered_at = datetime.fromisoformat(triggered_at)
                if isinstance(started_at, str):
                    started_at = datetime.fromisoformat(started_at)
                queue_time_ms = (started_at - triggered_at).total_seconds() * 1000
                metrics["queue_time_ms"] = queue_time_ms
            
            # Store metrics
            await self._store_execution_metrics(execution_id, metrics)
            
            logger.debug(f"Execution metrics collected: {execution_id}")
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to collect execution metrics: {execution_id} - {str(e)}")
            return {}
    
    async def get_system_health(self) -> Dict[str, Any]:
        """
        Get comprehensive system health status.
        
        Returns:
            System health information
        """
        try:
            logger.debug("Checking system health")
            
            health_checks = []
            overall_status = HealthStatus.HEALTHY
            
            # Database health check
            db_health = await self._check_database_health()
            health_checks.append(db_health)
            if db_health.status in [HealthStatus.CRITICAL, HealthStatus.DOWN]:
                overall_status = HealthStatus.CRITICAL
            elif db_health.status == HealthStatus.WARNING and overall_status == HealthStatus.HEALTHY:
                overall_status = HealthStatus.WARNING
            
            # Execution engine health check
            engine_health = await self._check_execution_engine_health()
            health_checks.append(engine_health)
            if engine_health.status in [HealthStatus.CRITICAL, HealthStatus.DOWN]:
                overall_status = HealthStatus.CRITICAL
            elif engine_health.status == HealthStatus.WARNING and overall_status == HealthStatus.HEALTHY:
                overall_status = HealthStatus.WARNING
            
            # Queue health check
            queue_health = await self._check_queue_health()
            health_checks.append(queue_health)
            if queue_health.status in [HealthStatus.CRITICAL, HealthStatus.DOWN]:
                overall_status = HealthStatus.CRITICAL
            elif queue_health.status == HealthStatus.WARNING and overall_status == HealthStatus.HEALTHY:
                overall_status = HealthStatus.WARNING
            
            # Performance health check
            performance_health = await self._check_performance_health()
            health_checks.append(performance_health)
            if performance_health.status in [HealthStatus.CRITICAL, HealthStatus.DOWN]:
                overall_status = HealthStatus.CRITICAL
            elif performance_health.status == HealthStatus.WARNING and overall_status == HealthStatus.HEALTHY:
                overall_status = HealthStatus.WARNING
            
            health_summary = {
                "overall_status": overall_status,
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "health_checks": [check.to_dict() for check in health_checks],
                "summary": {
                    "total_checks": len(health_checks),
                    "healthy": len([c for c in health_checks if c.status == HealthStatus.HEALTHY]),
                    "warning": len([c for c in health_checks if c.status == HealthStatus.WARNING]),
                    "critical": len([c for c in health_checks if c.status == HealthStatus.CRITICAL]),
                    "down": len([c for c in health_checks if c.status == HealthStatus.DOWN])
                }
            }
            
            # Store health check results
            await self._store_health_check_results(health_summary)
            
            logger.debug(f"System health check completed: {overall_status}")
            return health_summary
            
        except Exception as e:
            logger.error(f"Failed to check system health: {str(e)}")
            return {
                "overall_status": HealthStatus.DOWN,
                "error": str(e),
                "checked_at": datetime.now(timezone.utc).isoformat()
            }
    
    async def get_performance_analytics(
        self,
        time_range_hours: int = 24,
        execution_type: Optional[ExecutionType] = None
    ) -> Dict[str, Any]:
        """
        Get performance analytics for specified time range.
        
        Args:
            time_range_hours: Hours of data to analyze
            execution_type: Optional filter by execution type
            
        Returns:
            Performance analytics data
        """
        try:
            logger.info(f"Generating performance analytics for {time_range_hours} hours")
            
            # Calculate time range
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(hours=time_range_hours)
            
            # Build aggregation pipeline
            match_stage = {
                "triggered_at": {"$gte": start_time, "$lte": end_time},
                "status": {"$in": [ExecutionStatus.PASSED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED]}
            }
            
            if execution_type:
                match_stage["execution_type"] = execution_type
            
            pipeline = [
                {"$match": match_stage},
                {"$group": {
                    "_id": {
                        "status": "$status",
                        "execution_type": "$execution_type",
                        "hour": {"$hour": "$triggered_at"}
                    },
                    "count": {"$sum": 1},
                    "avg_duration": {"$avg": "$statistics.total_duration_ms"},
                    "min_duration": {"$min": "$statistics.total_duration_ms"},
                    "max_duration": {"$max": "$statistics.total_duration_ms"},
                    "avg_steps": {"$avg": "$statistics.total_steps"},
                    "avg_success_rate": {"$avg": "$statistics.success_rate"}
                }},
                {"$sort": {"_id.hour": 1}}
            ]
            
            cursor = self.collection.aggregate(pipeline)
            aggregated_data = []
            async for doc in cursor:
                aggregated_data.append(doc)
            
            # Process analytics
            analytics = await self._process_performance_analytics(aggregated_data, time_range_hours)
            
            logger.info("Performance analytics generated successfully")
            return analytics
            
        except Exception as e:
            logger.error(f"Failed to generate performance analytics: {str(e)}")
            return {"error": str(e)}
    
    async def get_execution_trends(self, days: int = 7) -> Dict[str, Any]:
        """
        Get execution trends over specified number of days.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Trend analysis data
        """
        try:
            logger.info(f"Generating execution trends for {days} days")
            
            # Calculate date range
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=days)
            
            # Daily execution counts
            daily_pipeline = [
                {"$match": {
                    "triggered_at": {"$gte": start_date, "$lte": end_date}
                }},
                {"$group": {
                    "_id": {
                        "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$triggered_at"}},
                        "status": "$status"
                    },
                    "count": {"$sum": 1}
                }},
                {"$sort": {"_id.date": 1}}
            ]
            
            cursor = self.collection.aggregate(daily_pipeline)
            daily_data = []
            async for doc in cursor:
                daily_data.append(doc)
            
            # Process trend data
            trends = await self._process_trend_data(daily_data, days)
            
            logger.info("Execution trends generated successfully")
            return trends
            
        except Exception as e:
            logger.error(f"Failed to generate execution trends: {str(e)}")
            return {"error": str(e)}
    
    async def start_monitoring(self) -> None:
        """Start background monitoring tasks."""
        if self._monitoring_task and not self._monitoring_task.done():
            logger.warning("Monitoring already running")
            return
        
        logger.info("Starting execution monitoring")
        self._shutdown_event.clear()
        self._monitoring_task = asyncio.create_task(self._background_monitor())
    
    async def stop_monitoring(self) -> None:
        """Stop background monitoring tasks."""
        logger.info("Stopping execution monitoring")
        self._shutdown_event.set()
        
        if self._monitoring_task:
            try:
                await asyncio.wait_for(self._monitoring_task, timeout=30.0)
            except asyncio.TimeoutError:
                logger.warning("Monitoring task did not stop gracefully")
                self._monitoring_task.cancel()
    
    # Private Helper Methods
    
    async def _background_monitor(self) -> None:
        """Background monitoring task."""
        logger.info("Background monitoring started")
        
        try:
            while not self._shutdown_event.is_set():
                try:
                    # Perform periodic health checks
                    await self.get_system_health()
                    
                    # Collect system metrics
                    await self._collect_system_metrics()
                    
                    # Check for alerts
                    await self._check_alert_conditions()
                    
                    # Clean up old data
                    await self._cleanup_old_data()
                    
                    # Wait for next iteration
                    await asyncio.sleep(self.health_check_interval_seconds)
                    
                except Exception as e:
                    logger.error(f"Error in background monitoring: {str(e)}")
                    await asyncio.sleep(60.0)  # Longer wait on error
                    
        except asyncio.CancelledError:
            logger.info("Background monitoring cancelled")
        except Exception as e:
            logger.error(f"Background monitoring error: {str(e)}")
        finally:
            logger.info("Background monitoring stopped")
    
    async def _check_database_health(self) -> HealthCheck:
        """Check database connectivity and performance."""
        start_time = datetime.now(timezone.utc)
        
        try:
            # Simple database ping
            await self.database.command("ping")
            
            # Check collection accessibility
            count = await self.collection.count_documents({})
            
            response_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            if response_time > 5000:  # 5 seconds
                return HealthCheck(
                    component="database",
                    status=HealthStatus.WARNING,
                    message=f"Database responding slowly ({response_time:.0f}ms)",
                    details={"response_time_ms": response_time, "document_count": count},
                    response_time_ms=response_time
                )
            else:
                return HealthCheck(
                    component="database",
                    status=HealthStatus.HEALTHY,
                    message="Database is healthy",
                    details={"response_time_ms": response_time, "document_count": count},
                    response_time_ms=response_time
                )
                
        except Exception as e:
            response_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            return HealthCheck(
                component="database",
                status=HealthStatus.DOWN,
                message=f"Database connection failed: {str(e)}",
                details={"error": str(e)},
                response_time_ms=response_time
            )
    
    async def _check_execution_engine_health(self) -> HealthCheck:
        """Check execution engine health."""
        try:
            # Check recent execution activity
            recent_time = datetime.now(timezone.utc) - timedelta(minutes=10)
            recent_executions = await self.collection.count_documents({
                "triggered_at": {"$gte": recent_time}
            })
            
            # Check for stuck executions
            stuck_threshold = datetime.now(timezone.utc) - timedelta(hours=2)
            stuck_executions = await self.collection.count_documents({
                "status": ExecutionStatus.RUNNING,
                "started_at": {"$lt": stuck_threshold}
            })
            
            if stuck_executions > 0:
                return HealthCheck(
                    component="execution_engine",
                    status=HealthStatus.WARNING,
                    message=f"Found {stuck_executions} potentially stuck executions",
                    details={
                        "stuck_executions": stuck_executions,
                        "recent_executions": recent_executions
                    }
                )
            else:
                return HealthCheck(
                    component="execution_engine",
                    status=HealthStatus.HEALTHY,
                    message="Execution engine is healthy",
                    details={"recent_executions": recent_executions}
                )
                
        except Exception as e:
            return HealthCheck(
                component="execution_engine",
                status=HealthStatus.CRITICAL,
                message=f"Execution engine check failed: {str(e)}",
                details={"error": str(e)}
            )
    
    async def _check_queue_health(self) -> HealthCheck:
        """Check execution queue health."""
        try:
            # Check queue depth (would integrate with queue service in real implementation)
            # For now, simulate queue health check
            queue_depth = 0  # Would get from queue service
            
            if queue_depth > self.alert_thresholds["queue_depth"]:
                return HealthCheck(
                    component="execution_queue",
                    status=HealthStatus.WARNING,
                    message=f"Queue depth is high: {queue_depth}",
                    details={"queue_depth": queue_depth}
                )
            else:
                return HealthCheck(
                    component="execution_queue",
                    status=HealthStatus.HEALTHY,
                    message="Queue is healthy",
                    details={"queue_depth": queue_depth}
                )
                
        except Exception as e:
            return HealthCheck(
                component="execution_queue",
                status=HealthStatus.CRITICAL,
                message=f"Queue health check failed: {str(e)}",
                details={"error": str(e)}
            )
    
    async def _check_performance_health(self) -> HealthCheck:
        """Check system performance health."""
        try:
            # Check recent execution performance
            recent_time = datetime.now(timezone.utc) - timedelta(hours=1)
            
            pipeline = [
                {"$match": {
                    "completed_at": {"$gte": recent_time},
                    "status": {"$in": [ExecutionStatus.PASSED, ExecutionStatus.FAILED]}
                }},
                {"$group": {
                    "_id": None,
                    "avg_duration": {"$avg": "$statistics.total_duration_ms"},
                    "failure_rate": {"$avg": {"$cond": [{"$eq": ["$status", ExecutionStatus.FAILED]}, 1, 0]}},
                    "count": {"$sum": 1}
                }}
            ]
            
            cursor = self.collection.aggregate(pipeline)
            results = await cursor.to_list(length=1)
            
            if not results:
                return HealthCheck(
                    component="performance",
                    status=HealthStatus.HEALTHY,
                    message="No recent executions to analyze",
                    details={"recent_executions": 0}
                )
            
            result = results[0]
            avg_duration = result.get("avg_duration", 0)
            failure_rate = result.get("failure_rate", 0)
            count = result.get("count", 0)
            
            issues = []
            status = HealthStatus.HEALTHY
            
            if avg_duration > self.alert_thresholds["average_execution_time_ms"]:
                issues.append(f"Average execution time is high: {avg_duration:.0f}ms")
                status = HealthStatus.WARNING
            
            if failure_rate > self.alert_thresholds["execution_failure_rate"]:
                issues.append(f"Failure rate is high: {failure_rate:.1%}")
                status = HealthStatus.WARNING
            
            message = "Performance is healthy" if not issues else "; ".join(issues)
            
            return HealthCheck(
                component="performance",
                status=status,
                message=message,
                details={
                    "avg_duration_ms": avg_duration,
                    "failure_rate": failure_rate,
                    "recent_executions": count
                }
            )
            
        except Exception as e:
            return HealthCheck(
                component="performance",
                status=HealthStatus.CRITICAL,
                message=f"Performance check failed: {str(e)}",
                details={"error": str(e)}
            )
    
    async def _store_execution_metrics(self, execution_id: str, metrics: Dict[str, Any]) -> None:
        """Store execution metrics in database."""
        try:
            metric_doc = {
                "execution_id": execution_id,
                "metrics": metrics,
                "collected_at": datetime.now(timezone.utc)
            }
            
            await self.metrics_collection.insert_one(metric_doc)
            
        except Exception as e:
            logger.error(f"Failed to store execution metrics: {execution_id} - {str(e)}")
    
    async def _store_health_check_results(self, health_summary: Dict[str, Any]) -> None:
        """Store health check results in database."""
        try:
            await self.health_collection.insert_one(health_summary)
            
        except Exception as e:
            logger.error(f"Failed to store health check results: {str(e)}")
    
    async def _collect_system_metrics(self) -> None:
        """Collect system-wide metrics."""
        try:
            # Collect various system metrics
            metrics = []
            
            # Active executions count
            active_count = await self.collection.count_documents({
                "status": {"$in": [ExecutionStatus.PENDING, ExecutionStatus.QUEUED, ExecutionStatus.RUNNING]}
            })
            metrics.append(ExecutionMetric("active_executions", MetricType.GAUGE, active_count))
            
            # Completed executions in last hour
            recent_time = datetime.now(timezone.utc) - timedelta(hours=1)
            completed_count = await self.collection.count_documents({
                "completed_at": {"$gte": recent_time}
            })
            metrics.append(ExecutionMetric("completed_executions_1h", MetricType.COUNTER, completed_count))
            
            # Store metrics
            for metric in metrics:
                await self.metrics_collection.insert_one(metric.to_dict())
                
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {str(e)}")
    
    async def _check_alert_conditions(self) -> None:
        """Check for alert conditions and generate alerts."""
        try:
            # Check failure rate
            recent_time = datetime.now(timezone.utc) - timedelta(hours=1)
            
            total_executions = await self.collection.count_documents({
                "completed_at": {"$gte": recent_time}
            })
            
            if total_executions > 10:  # Only alert if we have sufficient data
                failed_executions = await self.collection.count_documents({
                    "completed_at": {"$gte": recent_time},
                    "status": ExecutionStatus.FAILED
                })
                
                failure_rate = failed_executions / total_executions
                
                if failure_rate > self.alert_thresholds["execution_failure_rate"]:
                    await self._generate_alert(
                        AlertSeverity.WARNING,
                        "High Failure Rate",
                        f"Execution failure rate is {failure_rate:.1%} (threshold: {self.alert_thresholds['execution_failure_rate']:.1%})",
                        {"failure_rate": failure_rate, "failed_executions": failed_executions, "total_executions": total_executions}
                    )
                    
        except Exception as e:
            logger.error(f"Failed to check alert conditions: {str(e)}")
    
    async def _generate_alert(
        self,
        severity: AlertSeverity,
        title: str,
        message: str,
        details: Dict[str, Any]
    ) -> None:
        """Generate and store alert."""
        try:
            alert_doc = {
                "severity": severity,
                "title": title,
                "message": message,
                "details": details,
                "generated_at": datetime.now(timezone.utc),
                "acknowledged": False
            }
            
            await self.alerts_collection.insert_one(alert_doc)
            logger.warning(f"Alert generated: {title} - {message}")
            
        except Exception as e:
            logger.error(f"Failed to generate alert: {str(e)}")
    
    async def _cleanup_old_data(self) -> None:
        """Clean up old monitoring data."""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.metrics_retention_days)
            
            # Clean up old metrics
            await self.metrics_collection.delete_many({"collected_at": {"$lt": cutoff_date}})
            
            # Clean up old health checks
            await self.health_collection.delete_many({"checked_at": {"$lt": cutoff_date}})
            
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {str(e)}")
    
    async def _process_performance_analytics(
        self,
        aggregated_data: List[Dict[str, Any]],
        time_range_hours: int
    ) -> Dict[str, Any]:
        """Process aggregated data into performance analytics."""
        analytics = {
            "time_range_hours": time_range_hours,
            "total_executions": 0,
            "average_duration_ms": 0,
            "success_rate": 0,
            "hourly_breakdown": [],
            "performance_trends": {},
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
        
        if not aggregated_data:
            return analytics
        
        # Process hourly data
        hourly_data = {}
        total_executions = 0
        total_duration = 0
        successful_executions = 0
        
        for item in aggregated_data:
            hour = item["_id"]["hour"]
            status = item["_id"]["status"]
            count = item["count"]
            avg_duration = item.get("avg_duration", 0)
            
            if hour not in hourly_data:
                hourly_data[hour] = {"total": 0, "passed": 0, "failed": 0, "avg_duration": 0}
            
            hourly_data[hour]["total"] += count
            hourly_data[hour][status.lower()] = hourly_data[hour].get(status.lower(), 0) + count
            
            total_executions += count
            total_duration += avg_duration * count
            
            if status == ExecutionStatus.PASSED:
                successful_executions += count
        
        # Calculate overall metrics
        analytics["total_executions"] = total_executions
        if total_executions > 0:
            analytics["average_duration_ms"] = total_duration / total_executions
            analytics["success_rate"] = successful_executions / total_executions
        
        # Format hourly breakdown
        analytics["hourly_breakdown"] = [
            {"hour": hour, **data} for hour, data in sorted(hourly_data.items())
        ]
        
        return analytics
    
    async def _process_trend_data(
        self,
        daily_data: List[Dict[str, Any]],
        days: int
    ) -> Dict[str, Any]:
        """Process daily data into trend analysis."""
        trends = {
            "time_range_days": days,
            "daily_breakdown": [],
            "trend_analysis": {},
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Process daily data
        daily_summary = {}
        for item in daily_data:
            date = item["_id"]["date"]
            status = item["_id"]["status"]
            count = item["count"]
            
            if date not in daily_summary:
                daily_summary[date] = {"total": 0, "passed": 0, "failed": 0, "cancelled": 0}
            
            daily_summary[date]["total"] += count
            daily_summary[date][status.lower()] = daily_summary[date].get(status.lower(), 0) + count
        
        # Format daily breakdown
        trends["daily_breakdown"] = [
            {"date": date, **data} for date, data in sorted(daily_summary.items())
        ]
        
        return trends


class ExecutionMonitoringServiceFactory:
    """Factory for creating ExecutionMonitoringService instances."""
    
    @staticmethod
    def create(database: AsyncIOMotorDatabase) -> ExecutionMonitoringService:
        """Create ExecutionMonitoringService instance with database dependency."""
        return ExecutionMonitoringService(database) 
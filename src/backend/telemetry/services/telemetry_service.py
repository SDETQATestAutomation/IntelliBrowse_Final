"""
Telemetry Service - Core Business Logic

Implements the foundational service layer for the Environment Telemetry & Health 
Monitoring Engine. Provides async business logic for telemetry data processing,
health assessment, and uptime calculation with comprehensive error handling.

Key Responsibilities:
- Async telemetry data ingestion and validation
- Agent heartbeat processing with adaptive timeout calculation
- System metrics recording with threshold analysis
- Uptime calculation and health status assessment
- Data persistence via MongoDB async operations
- Alert generation based on threshold breaches

Architectural Patterns:
- Dependency injection via constructor parameters
- Async/await for all database operations
- Comprehensive error handling with custom exceptions
- Structured logging with correlation IDs
- Clean separation of concerns (no HTTP logic)
"""

import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Union
from motor.motor_asyncio import AsyncIOMotorDatabase

from ...config.env import get_settings
from ...config.logging import get_logger
from ..models.telemetry_models import (
    AgentHeartbeatModel,
    SystemMetricsModel,
    TelemetrySnapshotModel,
    HealthStatusModel,
    UptimeLogModel,
    HealthStatus,
    MetricType,
    TelemetryStatus,
    AlertSeverity,
    TelemetryException,
    InvalidTelemetryDataError,
    HealthCheckFailedError
)
from ..schemas.telemetry_schemas import (
    HeartbeatRequestSchema,
    SystemMetricsRequestSchema,
    HeartbeatResponseSchema,
    SystemMetricsResponseSchema,
    UptimeStatusResponseSchema,
    HealthAssessmentSchema,
    AlertInfoSchema
)

logger = get_logger(__name__)


class TelemetryServiceException(TelemetryException):
    """Custom exception for TelemetryService operations"""
    
    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        telemetry_id: Optional[str] = None,
        error_code: Optional[str] = None
    ):
        super().__init__(message, telemetry_id, error_code)
        self.operation = operation


class TelemetryService:
    """
    Core Telemetry Service for business logic operations.
    
    Handles telemetry data processing, validation, and persistence with
    comprehensive async operations and error handling. Implements clean
    separation of concerns with no HTTP-specific logic.
    
    Dependencies:
    - AsyncIOMotorDatabase: MongoDB async client for data persistence
    - Configuration: Service configuration and thresholds
    - Logger: Structured logging with correlation tracking
    """
    
    def __init__(
        self,
        database: AsyncIOMotorDatabase,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize TelemetryService with database and configuration.
        
        Args:
            database: MongoDB async database client
            config: Service configuration dictionary with thresholds and settings
        """
        self.database = database
        self.config = config or {}
        self.logger = logger.bind(service="TelemetryService")
        
        # Collections
        self.heartbeats_collection = database.telemetry_heartbeats_ts
        self.metrics_collection = database.telemetry_metrics_ts
        self.snapshots_collection = database.telemetry_snapshots
        self.health_status_collection = database.telemetry_health_status
        self.uptime_logs_collection = database.telemetry_uptime_logs
        
        # Service configuration
        self._heartbeat_timeout_ms = self.config.get("heartbeat_timeout_ms", 90000)
        self._metrics_batch_size = self.config.get("metrics_batch_size", 1000)
        self._health_check_window_minutes = self.config.get("health_check_window_minutes", 30)
        self._uptime_calculation_interval_hours = self.config.get("uptime_calculation_interval_hours", 1)
        
        # Default thresholds
        self._default_thresholds = {
            "cpu_usage_warning": 80.0,
            "cpu_usage_critical": 95.0,
            "memory_usage_warning": 85.0,
            "memory_usage_critical": 95.0,
            "disk_usage_warning": 85.0,
            "disk_usage_critical": 95.0,
            "response_time_warning": 2000.0,  # ms
            "response_time_critical": 5000.0,  # ms
        }
        
        self.logger.info("TelemetryService initialized", extra={
            "heartbeat_timeout_ms": self._heartbeat_timeout_ms,
            "metrics_batch_size": self._metrics_batch_size,
            "health_check_window_minutes": self._health_check_window_minutes
        })
    
    async def ingest_heartbeat(
        self,
        data: HeartbeatRequestSchema
    ) -> HeartbeatResponseSchema:
        """
        Process and ingest agent heartbeat data with health assessment.
        
        Validates heartbeat data, calculates adaptive timeout, assesses health status,
        and generates alerts based on threshold breaches. Updates uptime tracking
        and maintains agent connectivity state.
        
        Args:
            data: Validated heartbeat request with agent metrics
            
        Returns:
            HeartbeatResponseSchema: Processing results with health assessment
            
        Raises:
            TelemetryServiceException: If heartbeat processing fails
            InvalidTelemetryDataError: If heartbeat data is invalid
        """
        correlation_id = str(uuid.uuid4())
        heartbeat_id = str(uuid.uuid4())
        processing_start = datetime.now(timezone.utc)
        
        bound_logger = self.logger.bind(
            operation="ingest_heartbeat",
            agent_id=data.agent_info.agent_id,
            heartbeat_id=heartbeat_id,
            correlation_id=correlation_id
        )
        
        try:
            bound_logger.info("Processing agent heartbeat")
            
            # Validate heartbeat data
            await self._validate_heartbeat_data(data, bound_logger)
            
            # Calculate adaptive timeout based on historical data
            adaptive_timeout_ms = await self._calculate_adaptive_timeout(
                data.agent_info.agent_id, 
                data.heartbeat_interval_ms,
                bound_logger
            )
            
            # Assess current health status
            calculated_health, health_score = await self._assess_agent_health(data, bound_logger)
            
            # Generate alerts for threshold breaches
            alerts_generated = await self._check_heartbeat_thresholds(data, bound_logger)
            
            # Create heartbeat model
            heartbeat = AgentHeartbeatModel(
                agent_id=data.agent_info.agent_id,
                heartbeat_id=heartbeat_id,
                sequence_number=await self._get_next_sequence_number(data.agent_info.agent_id),
                timestamp=data.timestamp,
                agent_metadata={
                    "agent_id": data.agent_info.agent_id,
                    "environment": data.agent_info.environment,
                    "availability_zone": data.agent_info.availability_zone,
                    "agent_version": data.agent_info.agent_version
                },
                health_status=calculated_health,
                status_details=data.status_details,
                cpu_usage_percent=data.cpu_usage_percent,
                memory_usage_mb=data.memory_usage_mb,
                disk_usage_percent=data.disk_usage_percent,
                network_latency_ms=data.network_latency_ms,
                bandwidth_usage_mbps=data.bandwidth_usage_mbps,
                packet_loss_percent=data.packet_loss_percent,
                active_connections=data.active_connections,
                request_count=data.request_count,
                error_count=data.error_count,
                response_time_ms=data.response_time_ms,
                geographic_location=data.agent_info.geographic_location,
                environment=data.agent_info.environment,
                availability_zone=data.agent_info.availability_zone,
                agent_version=data.agent_info.agent_version,
                heartbeat_interval_ms=data.heartbeat_interval_ms,
                timeout_threshold_ms=adaptive_timeout_ms
            )
            
            # Store heartbeat in database
            result = await self.heartbeats_collection.insert_one(heartbeat.model_dump())
            
            # Update uptime tracking
            await self._update_uptime_tracking(data.agent_info.agent_id, calculated_health, data.timestamp, bound_logger)
            
            # Calculate processing metrics
            processing_end = datetime.now(timezone.utc)
            processing_time_ms = (processing_end - processing_start).total_seconds() * 1000
            data_quality_score = await self._calculate_data_quality_score(data)
            
            # Calculate next expected heartbeat
            next_expected_heartbeat = data.timestamp + timedelta(milliseconds=data.heartbeat_interval_ms)
            
            # Generate performance recommendations
            recommendations = await self._generate_performance_recommendations(data, bound_logger)
            
            response = HeartbeatResponseSchema(
                success=True,
                heartbeat_id=heartbeat_id,
                agent_id=data.agent_info.agent_id,
                processing_time_ms=processing_time_ms,
                data_quality_score=data_quality_score,
                calculated_health=calculated_health,
                health_score=health_score,
                next_expected_heartbeat=next_expected_heartbeat,
                adaptive_timeout_ms=adaptive_timeout_ms,
                alerts_generated=alerts_generated,
                recommendations=recommendations,
                timestamp=processing_end,
                message="Heartbeat processed successfully"
            )
            
            bound_logger.info("Heartbeat processed successfully", extra={
                "processing_time_ms": processing_time_ms,
                "calculated_health": calculated_health,
                "health_score": health_score,
                "alerts_count": len(alerts_generated)
            })
            
            return response
            
        except Exception as e:
            bound_logger.error("Failed to process heartbeat", extra={
                "error": str(e),
                "error_type": type(e).__name__
            })
            
            if isinstance(e, (InvalidTelemetryDataError, TelemetryServiceException)):
                raise
            
            raise TelemetryServiceException(
                f"Failed to process heartbeat: {str(e)}",
                operation="ingest_heartbeat",
                telemetry_id=heartbeat_id,
                error_code="HEARTBEAT_PROCESSING_FAILED"
            )
    
    async def record_metrics(
        self,
        data: SystemMetricsRequestSchema
    ) -> SystemMetricsResponseSchema:
        """
        Record and process system metrics with threshold analysis.
        
        Validates metrics data, performs data quality assessment, checks thresholds,
        generates alerts for breaches, and stores metrics in time-series optimized
        collections for dashboard consumption.
        
        Args:
            data: Validated system metrics request with performance data
            
        Returns:
            SystemMetricsResponseSchema: Processing results with quality assessment
            
        Raises:
            TelemetryServiceException: If metrics processing fails
            InvalidTelemetryDataError: If metrics data is invalid
        """
        correlation_id = str(uuid.uuid4())
        processing_start = datetime.now(timezone.utc)
        
        bound_logger = self.logger.bind(
            operation="record_metrics",
            system_id=data.system_id,
            metrics_count=len(data.metrics),
            correlation_id=correlation_id
        )
        
        try:
            bound_logger.info("Processing system metrics")
            
            # Validate metrics data
            await self._validate_metrics_data(data, bound_logger)
            
            processed_count = 0
            validation_errors = []
            data_quality_scores = {}
            outliers_detected = []
            thresholds_breached = []
            alerts_generated = []
            
            # Process each metric
            for metric_data in data.metrics:
                try:
                    # Calculate data quality score
                    quality_score = await self._calculate_metric_quality_score(metric_data)
                    data_quality_scores[metric_data.metric_name] = quality_score
                    
                    # Detect outliers
                    is_outlier = await self._detect_metric_outlier(metric_data, data.system_id)
                    if is_outlier:
                        outliers_detected.append(metric_data.metric_name)
                    
                    # Check thresholds
                    threshold_result = await self._check_metric_thresholds(metric_data, data.system_id)
                    if threshold_result["breached"]:
                        thresholds_breached.append(metric_data.metric_name)
                        alerts_generated.extend(threshold_result["alerts"])
                    
                    # Create metrics model
                    metric = SystemMetricsModel(
                        metric_id=str(uuid.uuid4()),
                        system_id=data.system_id,
                        metric_name=metric_data.metric_name,
                        metric_type=metric_data.metric_type,
                        timestamp=metric_data.timestamp or data.timestamp,
                        system_metadata={
                            "system_id": data.system_id,
                            "environment": data.environment,
                            "service_name": data.service_name,
                            "component_name": data.component_name,
                            "region": data.region
                        },
                        value=metric_data.value,
                        unit=metric_data.unit,
                        data_quality_score=quality_score,
                        collection_method=data.collection_method,
                        warning_threshold=threshold_result.get("warning_threshold"),
                        critical_threshold=threshold_result.get("critical_threshold"),
                        threshold_breached=threshold_result["breached"],
                        alert_severity=threshold_result.get("alert_severity"),
                        service_name=data.service_name,
                        component_name=data.component_name,
                        environment=data.environment,
                        region=data.region,
                        dimensions=metric_data.dimensions,
                        tags=metric_data.tags,
                        processing_status=TelemetryStatus.PROCESSED
                    )
                    
                    # Store metric in database
                    await self.metrics_collection.insert_one(metric.model_dump())
                    processed_count += 1
                    
                except Exception as metric_error:
                    validation_errors.append(f"Metric {metric_data.metric_name}: {str(metric_error)}")
                    bound_logger.warning("Failed to process metric", extra={
                        "metric_name": metric_data.metric_name,
                        "error": str(metric_error)
                    })
            
            # Calculate processing metrics
            processing_end = datetime.now(timezone.utc)
            processing_time_ms = (processing_end - processing_start).total_seconds() * 1000
            
            response = SystemMetricsResponseSchema(
                success=processed_count > 0,
                metrics_processed=processed_count,
                system_id=data.system_id,
                processing_time_ms=processing_time_ms,
                validation_errors=validation_errors,
                data_quality_scores=data_quality_scores,
                outliers_detected=outliers_detected,
                thresholds_breached=thresholds_breached,
                alerts_generated=alerts_generated,
                timestamp=processing_end,
                message=f"Processed {processed_count} of {len(data.metrics)} metrics successfully"
            )
            
            bound_logger.info("Metrics processed successfully", extra={
                "metrics_processed": processed_count,
                "processing_time_ms": processing_time_ms,
                "validation_errors_count": len(validation_errors),
                "alerts_count": len(alerts_generated)
            })
            
            return response
            
        except Exception as e:
            bound_logger.error("Failed to process metrics", extra={
                "error": str(e),
                "error_type": type(e).__name__
            })
            
            if isinstance(e, (InvalidTelemetryDataError, TelemetryServiceException)):
                raise
            
            raise TelemetryServiceException(
                f"Failed to process metrics: {str(e)}",
                operation="record_metrics",
                error_code="METRICS_PROCESSING_FAILED"
            )
    
    async def calculate_uptime(
        self,
        agent_id: str,
        time_range_hours: int = 24
    ) -> UptimeStatusResponseSchema:
        """
        Calculate comprehensive uptime status and availability metrics.
        
        Analyzes heartbeat history to determine uptime percentage, downtime periods,
        SLA compliance, and availability trends. Generates uptime sessions and
        failure pattern analysis for health assessment.
        
        Args:
            agent_id: Target agent identifier
            time_range_hours: Analysis time range in hours (default 24h)
            
        Returns:
            UptimeStatusResponseSchema: Comprehensive uptime analysis
            
        Raises:
            TelemetryServiceException: If uptime calculation fails
            HealthCheckFailedError: If agent health cannot be determined
        """
        correlation_id = str(uuid.uuid4())
        calculation_start = datetime.now(timezone.utc)
        
        bound_logger = self.logger.bind(
            operation="calculate_uptime",
            agent_id=agent_id,
            time_range_hours=time_range_hours,
            correlation_id=correlation_id
        )
        
        try:
            bound_logger.info("Calculating agent uptime status")
            
            # Define time range for analysis
            end_time = calculation_start
            start_time = end_time - timedelta(hours=time_range_hours)
            
            # Retrieve heartbeat history
            heartbeat_cursor = self.heartbeats_collection.find({
                "agent_id": agent_id,
                "timestamp": {"$gte": start_time, "$lte": end_time}
            }).sort("timestamp", 1)
            
            heartbeats = await heartbeat_cursor.to_list(length=None)
            
            if not heartbeats:
                raise HealthCheckFailedError(
                    f"No heartbeat data found for agent {agent_id} in the last {time_range_hours} hours",
                    target_id=agent_id,
                    health_status=HealthStatus.UNKNOWN
                )
            
            # Calculate uptime metrics
            uptime_analysis = await self._analyze_uptime_sessions(heartbeats, start_time, end_time, bound_logger)
            
            # Determine overall health status
            overall_health = await self._determine_overall_health_status(agent_id, uptime_analysis, bound_logger)
            
            # Calculate health score
            health_score = await self._calculate_health_score(uptime_analysis, overall_health)
            
            # Get SLA targets
            sla_target = self.config.get("sla_uptime_target", 99.9)
            sla_compliance = uptime_analysis["uptime_percentage"] >= sla_target
            
            # Generate health recommendations
            health_recommendations = await self._generate_health_recommendations(
                uptime_analysis, overall_health, bound_logger
            )
            
            # Create health assessment
            health_assessment = HealthAssessmentSchema(
                overall_health=overall_health,
                health_score=health_score,
                uptime_percentage=uptime_analysis["uptime_percentage"],
                last_check=calculation_start,
                components=uptime_analysis.get("component_health", {})
            )
            
            response = UptimeStatusResponseSchema(
                agent_id=agent_id,
                calculation_period_hours=time_range_hours,
                calculated_at=calculation_start,
                health_assessment=health_assessment,
                uptime_percentage=uptime_analysis["uptime_percentage"],
                total_uptime_minutes=uptime_analysis["total_uptime_minutes"],
                total_downtime_minutes=uptime_analysis["total_downtime_minutes"],
                uptime_sessions=uptime_analysis["uptime_sessions"],
                downtime_periods=uptime_analysis["downtime_periods"],
                sla_target=sla_target,
                sla_compliance=sla_compliance,
                sla_breach_risk=uptime_analysis.get("sla_breach_risk", "low"),
                availability_trend=uptime_analysis.get("availability_trend", "stable"),
                mttr_minutes=uptime_analysis.get("mttr_minutes"),
                mtbf_hours=uptime_analysis.get("mtbf_hours"),
                failure_patterns=uptime_analysis.get("failure_patterns", []),
                health_recommendations=health_recommendations,
                data_quality_score=uptime_analysis.get("data_quality_score", 1.0),
                confidence_level=uptime_analysis.get("confidence_level", 1.0)
            )
            
            bound_logger.info("Uptime calculation completed", extra={
                "uptime_percentage": uptime_analysis["uptime_percentage"],
                "overall_health": overall_health,
                "health_score": health_score,
                "sla_compliance": sla_compliance
            })
            
            return response
            
        except Exception as e:
            bound_logger.error("Failed to calculate uptime", extra={
                "error": str(e),
                "error_type": type(e).__name__
            })
            
            if isinstance(e, (HealthCheckFailedError, TelemetryServiceException)):
                raise
            
            raise TelemetryServiceException(
                f"Failed to calculate uptime for agent {agent_id}: {str(e)}",
                operation="calculate_uptime",
                telemetry_id=agent_id,
                error_code="UPTIME_CALCULATION_FAILED"
            )
    
    # Private helper methods
    
    async def _validate_heartbeat_data(self, data: HeartbeatRequestSchema, logger) -> None:
        """Validate heartbeat data for business logic requirements"""
        # Check timestamp freshness (not older than 10 minutes)
        max_age = timedelta(minutes=10)
        if datetime.now(timezone.utc) - data.timestamp > max_age:
            raise InvalidTelemetryDataError(
                "Heartbeat timestamp is too old",
                field_name="timestamp"
            )
        
        # Validate metric ranges
        if data.cpu_usage_percent is not None and (data.cpu_usage_percent < 0 or data.cpu_usage_percent > 100):
            raise InvalidTelemetryDataError(
                "CPU usage must be between 0 and 100 percent",
                field_name="cpu_usage_percent"
            )
        
        logger.debug("Heartbeat data validation passed")
    
    async def _validate_metrics_data(self, data: SystemMetricsRequestSchema, logger) -> None:
        """Validate metrics data for business logic requirements"""
        if not data.metrics:
            raise InvalidTelemetryDataError(
                "At least one metric must be provided",
                field_name="metrics"
            )
        
        # Check for duplicate metric names
        metric_names = [m.metric_name for m in data.metrics]
        if len(metric_names) != len(set(metric_names)):
            raise InvalidTelemetryDataError(
                "Duplicate metric names are not allowed",
                field_name="metrics"
            )
        
        logger.debug("Metrics data validation passed")
    
    async def _calculate_adaptive_timeout(self, agent_id: str, current_interval_ms: int, logger) -> int:
        """Calculate adaptive timeout based on historical heartbeat intervals"""
        try:
            # Get recent heartbeat intervals
            recent_heartbeats = await self.heartbeats_collection.find({
                "agent_id": agent_id
            }).sort("timestamp", -1).limit(10).to_list(length=10)
            
            if len(recent_heartbeats) < 2:
                # Not enough history, use default multiplier
                return int(current_interval_ms * 3)
            
            # Calculate interval variations
            intervals = []
            for i in range(1, len(recent_heartbeats)):
                prev_time = recent_heartbeats[i]["timestamp"]
                curr_time = recent_heartbeats[i-1]["timestamp"]
                interval_ms = (curr_time - prev_time).total_seconds() * 1000
                intervals.append(interval_ms)
            
            # Calculate adaptive timeout (mean + 2 * std deviation)
            import statistics
            mean_interval = statistics.mean(intervals)
            std_dev = statistics.stdev(intervals) if len(intervals) > 1 else 0
            adaptive_timeout = int(mean_interval + (2 * std_dev))
            
            # Ensure minimum timeout
            min_timeout = current_interval_ms * 2
            max_timeout = current_interval_ms * 5
            
            return max(min_timeout, min(adaptive_timeout, max_timeout))
            
        except Exception as e:
            logger.warning("Failed to calculate adaptive timeout, using default", extra={"error": str(e)})
            return int(current_interval_ms * 3)
    
    async def _assess_agent_health(self, data: HeartbeatRequestSchema, logger) -> tuple[HealthStatus, float]:
        """Assess agent health based on heartbeat metrics"""
        health_score = 100.0
        health_status = HealthStatus.HEALTHY
        
        # CPU usage assessment
        if data.cpu_usage_percent is not None:
            if data.cpu_usage_percent > 95:
                health_score -= 30
                health_status = HealthStatus.CRITICAL
            elif data.cpu_usage_percent > 80:
                health_score -= 15
                if health_status == HealthStatus.HEALTHY:
                    health_status = HealthStatus.DEGRADED
        
        # Memory usage assessment
        if data.memory_usage_mb is not None and data.memory_usage_mb > 0:
            # Assuming 8GB total memory for calculation
            memory_percent = (data.memory_usage_mb / 8192) * 100
            if memory_percent > 95:
                health_score -= 25
                health_status = HealthStatus.CRITICAL
            elif memory_percent > 85:
                health_score -= 10
                if health_status == HealthStatus.HEALTHY:
                    health_status = HealthStatus.DEGRADED
        
        # Network latency assessment
        if data.network_latency_ms is not None:
            if data.network_latency_ms > 1000:
                health_score -= 20
                if health_status == HealthStatus.HEALTHY:
                    health_status = HealthStatus.DEGRADED
        
        # Error rate assessment
        if data.request_count is not None and data.error_count is not None:
            if data.request_count > 0:
                error_rate = (data.error_count / data.request_count) * 100
                if error_rate > 10:
                    health_score -= 25
                    health_status = HealthStatus.CRITICAL
                elif error_rate > 5:
                    health_score -= 10
                    if health_status == HealthStatus.HEALTHY:
                        health_status = HealthStatus.DEGRADED
        
        health_score = max(0, health_score)
        
        logger.debug("Agent health assessed", extra={
            "health_status": health_status,
            "health_score": health_score
        })
        
        return health_status, health_score
    
    async def _check_heartbeat_thresholds(self, data: HeartbeatRequestSchema, logger) -> List[AlertInfoSchema]:
        """Check heartbeat metrics against thresholds and generate alerts"""
        alerts = []
        
        # CPU usage alerts
        if data.cpu_usage_percent is not None:
            if data.cpu_usage_percent >= self._default_thresholds["cpu_usage_critical"]:
                alerts.append(AlertInfoSchema(
                    alert_id=str(uuid.uuid4()),
                    severity=AlertSeverity.CRITICAL,
                    message=f"Critical CPU usage: {data.cpu_usage_percent}%",
                    source=data.agent_info.agent_id,
                    timestamp=datetime.now(timezone.utc)
                ))
            elif data.cpu_usage_percent >= self._default_thresholds["cpu_usage_warning"]:
                alerts.append(AlertInfoSchema(
                    alert_id=str(uuid.uuid4()),
                    severity=AlertSeverity.WARNING,
                    message=f"High CPU usage: {data.cpu_usage_percent}%",
                    source=data.agent_info.agent_id,
                    timestamp=datetime.now(timezone.utc)
                ))
        
        # Response time alerts
        if data.response_time_ms is not None:
            if data.response_time_ms >= self._default_thresholds["response_time_critical"]:
                alerts.append(AlertInfoSchema(
                    alert_id=str(uuid.uuid4()),
                    severity=AlertSeverity.CRITICAL,
                    message=f"Critical response time: {data.response_time_ms}ms",
                    source=data.agent_info.agent_id,
                    timestamp=datetime.now(timezone.utc)
                ))
            elif data.response_time_ms >= self._default_thresholds["response_time_warning"]:
                alerts.append(AlertInfoSchema(
                    alert_id=str(uuid.uuid4()),
                    severity=AlertSeverity.WARNING,
                    message=f"High response time: {data.response_time_ms}ms",
                    source=data.agent_info.agent_id,
                    timestamp=datetime.now(timezone.utc)
                ))
        
        return alerts
    
    async def _get_next_sequence_number(self, agent_id: str) -> int:
        """Get next sequence number for agent heartbeat"""
        last_heartbeat = await self.heartbeats_collection.find_one(
            {"agent_id": agent_id},
            sort=[("sequence_number", -1)]
        )
        
        return (last_heartbeat.get("sequence_number", 0) + 1) if last_heartbeat else 1
    
    async def _update_uptime_tracking(self, agent_id: str, health_status: HealthStatus, timestamp: datetime, logger) -> None:
        """Update uptime tracking based on current health status"""
        try:
            # Find current active uptime session
            current_session = await self.uptime_logs_collection.find_one({
                "target_id": agent_id,
                "is_active": True
            })
            
            is_healthy = health_status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]
            
            if current_session:
                session_type = current_session["session_type"]
                
                # Check if we need to end current session
                if (session_type == "uptime" and not is_healthy) or (session_type == "downtime" and is_healthy):
                    # End current session
                    await self.uptime_logs_collection.update_one(
                        {"_id": current_session["_id"]},
                        {
                            "$set": {
                                "session_end": timestamp,
                                "is_active": False,
                                "duration": timestamp - current_session["session_start"]
                            }
                        }
                    )
                    
                    # Start new session
                    new_session = UptimeLogModel(
                        uptime_session_id=str(uuid.uuid4()),
                        target_id=agent_id,
                        target_type="agent",
                        session_start=timestamp,
                        session_type="uptime" if is_healthy else "downtime",
                        environment=current_session.get("environment", "unknown")
                    )
                    
                    await self.uptime_logs_collection.insert_one(new_session.model_dump())
            
            else:
                # No active session, start new one
                new_session = UptimeLogModel(
                    uptime_session_id=str(uuid.uuid4()),
                    target_id=agent_id,
                    target_type="agent",
                    session_start=timestamp,
                    session_type="uptime" if is_healthy else "downtime",
                    environment="unknown"
                )
                
                await self.uptime_logs_collection.insert_one(new_session.model_dump())
            
        except Exception as e:
            logger.warning("Failed to update uptime tracking", extra={"error": str(e)})
    
    async def _calculate_data_quality_score(self, data: HeartbeatRequestSchema) -> float:
        """Calculate data quality score based on completeness and validity"""
        total_fields = 12  # Total optional metric fields
        present_fields = 0
        
        # Count present optional fields
        optional_fields = [
            data.cpu_usage_percent, data.memory_usage_mb, data.disk_usage_percent,
            data.network_latency_ms, data.bandwidth_usage_mbps, data.packet_loss_percent,
            data.active_connections, data.request_count, data.error_count,
            data.response_time_ms, data.agent_info.geographic_location, data.agent_info.availability_zone
        ]
        
        present_fields = sum(1 for field in optional_fields if field is not None)
        
        return min(1.0, present_fields / total_fields)
    
    async def _generate_performance_recommendations(self, data: HeartbeatRequestSchema, logger) -> List[str]:
        """Generate performance recommendations based on heartbeat data"""
        recommendations = []
        
        if data.cpu_usage_percent and data.cpu_usage_percent > 80:
            recommendations.append("Consider scaling CPU resources or optimizing CPU-intensive processes")
        
        if data.memory_usage_mb and data.memory_usage_mb > 6000:  # Assuming 8GB total
            recommendations.append("Memory usage is high, consider increasing memory allocation")
        
        if data.response_time_ms and data.response_time_ms > 1000:
            recommendations.append("Response time is elevated, investigate application performance")
        
        if data.error_count and data.request_count and data.error_count > 0:
            error_rate = (data.error_count / data.request_count) * 100
            if error_rate > 5:
                recommendations.append("Error rate is above acceptable threshold, investigate error sources")
        
        return recommendations
    
    async def _calculate_metric_quality_score(self, metric_data) -> float:
        """Calculate quality score for individual metric"""
        score = 1.0
        
        # Check for reasonable value ranges based on metric type
        if metric_data.metric_type == MetricType.CPU_USAGE:
            if metric_data.value < 0 or metric_data.value > 100:
                score -= 0.5
        elif metric_data.metric_type == MetricType.MEMORY_USAGE:
            if metric_data.value < 0:
                score -= 0.3
        
        # Check timestamp freshness
        if metric_data.timestamp:
            age = datetime.now(timezone.utc) - metric_data.timestamp
            if age > timedelta(hours=1):
                score -= 0.2
        
        return max(0.0, score)
    
    async def _detect_metric_outlier(self, metric_data, system_id: str) -> bool:
        """Detect if metric value is an outlier based on historical data"""
        try:
            # Get recent values for this metric
            recent_metrics = await self.metrics_collection.find({
                "system_id": system_id,
                "metric_name": metric_data.metric_name,
                "timestamp": {"$gte": datetime.now(timezone.utc) - timedelta(hours=24)}
            }).limit(100).to_list(length=100)
            
            if len(recent_metrics) < 10:
                return False  # Not enough data
            
            values = [m["value"] for m in recent_metrics]
            
            # Simple outlier detection using IQR
            import statistics
            q1 = statistics.quantiles(values, n=4)[0]
            q3 = statistics.quantiles(values, n=4)[2]
            iqr = q3 - q1
            
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            
            return metric_data.value < lower_bound or metric_data.value > upper_bound
            
        except Exception:
            return False
    
    async def _check_metric_thresholds(self, metric_data, system_id: str) -> Dict[str, Any]:
        """Check metric against thresholds and generate alerts if needed"""
        result = {
            "breached": False,
            "alerts": [],
            "warning_threshold": None,
            "critical_threshold": None,
            "alert_severity": None
        }
        
        # Get thresholds based on metric type
        metric_type_name = metric_data.metric_type.value
        warning_key = f"{metric_type_name}_warning"
        critical_key = f"{metric_type_name}_critical"
        
        warning_threshold = self._default_thresholds.get(warning_key)
        critical_threshold = self._default_thresholds.get(critical_key)
        
        if warning_threshold is not None:
            result["warning_threshold"] = warning_threshold
            
            if metric_data.value >= warning_threshold:
                result["breached"] = True
                severity = AlertSeverity.WARNING
                
                if critical_threshold is not None and metric_data.value >= critical_threshold:
                    result["critical_threshold"] = critical_threshold
                    severity = AlertSeverity.CRITICAL
                
                result["alert_severity"] = severity
                result["alerts"].append(AlertInfoSchema(
                    alert_id=str(uuid.uuid4()),
                    severity=severity,
                    message=f"{metric_data.metric_name} threshold breached: {metric_data.value} {metric_data.unit}",
                    source=system_id,
                    timestamp=datetime.now(timezone.utc)
                ))
        
        return result
    
    async def _analyze_uptime_sessions(self, heartbeats: List[Dict], start_time: datetime, end_time: datetime, logger) -> Dict[str, Any]:
        """Analyze heartbeat data to calculate uptime sessions and availability metrics"""
        total_period_minutes = (end_time - start_time).total_seconds() / 60
        
        # Simple uptime calculation based on heartbeat presence
        heartbeat_timestamps = [hb["timestamp"] for hb in heartbeats]
        heartbeat_timestamps.sort()
        
        # Calculate gaps between heartbeats
        gaps = []
        for i in range(1, len(heartbeat_timestamps)):
            gap = (heartbeat_timestamps[i] - heartbeat_timestamps[i-1]).total_seconds()
            gaps.append(gap)
        
        # Estimate downtime (gaps > 2 minutes indicate potential downtime)
        downtime_seconds = sum(gap for gap in gaps if gap > 120)  # 2 minutes threshold
        uptime_seconds = (total_period_minutes * 60) - downtime_seconds
        
        uptime_percentage = (uptime_seconds / (total_period_minutes * 60)) * 100
        uptime_percentage = min(100.0, max(0.0, uptime_percentage))
        
        return {
            "uptime_percentage": uptime_percentage,
            "total_uptime_minutes": uptime_seconds / 60,
            "total_downtime_minutes": downtime_seconds / 60,
            "uptime_sessions": [],  # Simplified for now
            "downtime_periods": [],  # Simplified for now
            "data_quality_score": 1.0 if len(heartbeats) > 10 else 0.7,
            "confidence_level": 1.0 if len(heartbeats) > 50 else 0.8
        }
    
    async def _determine_overall_health_status(self, agent_id: str, uptime_analysis: Dict, logger) -> HealthStatus:
        """Determine overall health status based on uptime analysis"""
        uptime_percentage = uptime_analysis["uptime_percentage"]
        
        if uptime_percentage >= 99.0:
            return HealthStatus.HEALTHY
        elif uptime_percentage >= 95.0:
            return HealthStatus.DEGRADED
        elif uptime_percentage >= 80.0:
            return HealthStatus.CRITICAL
        else:
            return HealthStatus.OFFLINE
    
    async def _calculate_health_score(self, uptime_analysis: Dict, health_status: HealthStatus) -> float:
        """Calculate numerical health score based on uptime analysis"""
        base_score = uptime_analysis["uptime_percentage"]
        
        # Adjust based on data quality
        data_quality_factor = uptime_analysis.get("data_quality_score", 1.0)
        
        return min(100.0, base_score * data_quality_factor)
    
    async def _generate_health_recommendations(self, uptime_analysis: Dict, health_status: HealthStatus, logger) -> List[str]:
        """Generate health improvement recommendations"""
        recommendations = []
        
        uptime_percentage = uptime_analysis["uptime_percentage"]
        
        if uptime_percentage < 99.0:
            recommendations.append("Consider investigating frequent disconnections")
        
        if uptime_percentage < 95.0:
            recommendations.append("Implement redundancy mechanisms to improve availability")
        
        if uptime_percentage < 90.0:
            recommendations.append("Critical availability issues detected - immediate attention required")
        
        return recommendations 
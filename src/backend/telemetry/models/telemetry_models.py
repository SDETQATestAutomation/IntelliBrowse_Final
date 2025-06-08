"""
Environment Telemetry & Health Monitoring Engine - Core Models

Implements the foundation data models for agent health tracking, system metrics collection,
and telemetry snapshots. Designed for MongoDB time-series storage with optimized indexing
strategies for high-performance aggregation and real-time dashboard queries.

Key Models:
- AgentHeartbeatModel: Agent connectivity tracking with adaptive timeout support
- SystemMetricsModel: System performance metrics with time-series optimization
- TelemetrySnapshotModel: Aggregated telemetry data for dashboard consumption
- HealthStatusModel: Health assessment calculations with uptime tracking
- UptimeLogModel: Uptime session tracking derived from heartbeat analysis

Features:
- UTC-aware datetime handling with timezone support
- Comprehensive validation with Pydantic
- Optimized MongoDB time-series collections with TTL indexing
- Performance metrics validation and normalization
- Adaptive threshold management for health assessments
"""

from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from bson import ObjectId
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict

from ...config.logging import get_logger
from ...orchestration.models.orchestration_models import BaseMongoModel

logger = get_logger(__name__)


class HealthStatus(str, Enum):
    """
    Health status enumeration for comprehensive agent and system monitoring.
    Supports graduated health levels with alert escalation support.
    """
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"
    
    @classmethod
    def get_alert_priorities(cls) -> Dict[str, int]:
        """Get alert priority levels for each health status"""
        return {
            cls.HEALTHY: 0,
            cls.DEGRADED: 2,
            cls.CRITICAL: 8,
            cls.UNKNOWN: 5,
            cls.OFFLINE: 9,
            cls.MAINTENANCE: 1
        }
    
    def get_alert_priority(self) -> int:
        """Get alert priority level for this health status"""
        return self.get_alert_priorities().get(self, 5)


class MetricType(str, Enum):
    """
    Metric type enumeration for system performance monitoring.
    Supports comprehensive system resource tracking and custom metrics.
    """
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    DISK_USAGE = "disk_usage"
    DISK_IO = "disk_io"
    NETWORK_IO = "network_io"
    RESPONSE_TIME = "response_time"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    UPTIME = "uptime"
    CUSTOM = "custom"
    
    @classmethod
    def get_metric_units(cls) -> Dict[str, str]:
        """Get standard units for each metric type"""
        return {
            cls.CPU_USAGE: "percentage",
            cls.MEMORY_USAGE: "megabytes", 
            cls.DISK_USAGE: "percentage",
            cls.DISK_IO: "megabytes_per_second",
            cls.NETWORK_IO: "megabytes_per_second",
            cls.RESPONSE_TIME: "milliseconds",
            cls.THROUGHPUT: "requests_per_second",
            cls.ERROR_RATE: "percentage",
            cls.UPTIME: "seconds",
            cls.CUSTOM: "custom_unit"
        }


class TelemetryStatus(str, Enum):
    """
    Telemetry processing status for data pipeline tracking.
    Supports comprehensive data lifecycle management.
    """
    RECEIVED = "received"
    VALIDATED = "validated"
    PROCESSED = "processed"
    AGGREGATED = "aggregated"
    STORED = "stored"
    FAILED = "failed"
    DISCARDED = "discarded"


class AlertSeverity(str, Enum):
    """
    Alert severity enumeration for escalation management.
    Aligned with standard incident management practices.
    """
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AgentHeartbeatModel(BaseMongoModel):
    """
    Agent heartbeat model for connectivity and health tracking.
    
    Records periodic agent health pings with performance metrics and network
    statistics. Optimized for time-series analysis and adaptive timeout calculation.
    Supports failure detection algorithms and network partition analysis.
    
    Collection: telemetry_heartbeats_ts (MongoDB time-series)
    """
    
    # Core identification
    agent_id: str = Field(..., description="Unique agent identifier")
    heartbeat_id: str = Field(..., description="Unique heartbeat identifier")
    sequence_number: int = Field(..., ge=0, description="Heartbeat sequence number")
    
    # Timing information (time-series key field)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Heartbeat timestamp (time-series timeField)"
    )
    
    # Agent metadata (time-series metaField)
    agent_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Agent metadata for time-series grouping"
    )
    
    # Health status
    health_status: HealthStatus = Field(..., description="Current agent health status")
    status_details: Dict[str, Any] = Field(default_factory=dict, description="Detailed health information")
    
    # Performance metrics
    cpu_usage_percent: Optional[float] = Field(None, ge=0, le=100, description="CPU usage percentage")
    memory_usage_mb: Optional[float] = Field(None, ge=0, description="Memory usage in MB")
    disk_usage_percent: Optional[float] = Field(None, ge=0, le=100, description="Disk usage percentage")
    
    # Network metrics  
    network_latency_ms: Optional[float] = Field(None, ge=0, description="Network latency in milliseconds")
    bandwidth_usage_mbps: Optional[float] = Field(None, ge=0, description="Bandwidth usage in Mbps")
    packet_loss_percent: Optional[float] = Field(None, ge=0, le=100, description="Packet loss percentage")
    
    # Application metrics
    active_connections: Optional[int] = Field(None, ge=0, description="Number of active connections")
    request_count: Optional[int] = Field(None, ge=0, description="Request count since last heartbeat")
    error_count: Optional[int] = Field(None, ge=0, description="Error count since last heartbeat")
    response_time_ms: Optional[float] = Field(None, ge=0, description="Average response time in milliseconds")
    
    # Geographic and environment information
    geographic_location: Optional[str] = Field(None, description="Agent geographic location")
    environment: str = Field(..., description="Deployment environment (dev/staging/prod)")
    availability_zone: Optional[str] = Field(None, description="Cloud availability zone")
    
    # Version and configuration
    agent_version: str = Field(..., description="Agent software version")
    configuration_hash: Optional[str] = Field(None, description="Agent configuration hash")
    
    # Failure detection metadata
    heartbeat_interval_ms: int = Field(default=30000, ge=1000, description="Expected heartbeat interval")
    network_jitter_ms: Optional[float] = Field(None, ge=0, description="Network jitter measurement")
    timeout_threshold_ms: Optional[int] = Field(None, ge=1000, description="Calculated timeout threshold")
    
    # Collection configuration
    _collection_name: str = "telemetry_heartbeats_ts"
    
    @field_validator('agent_metadata', mode='before')
    @classmethod
    def populate_agent_metadata(cls, v, info):
        """Populate agent metadata for time-series optimization"""
        if not v:
            v = {}
        
        # Add context from other fields for time-series grouping
        data = info.data if hasattr(info, 'data') else {}
        v.update({
            "agent_id": data.get("agent_id"),
            "environment": data.get("environment", "unknown"),
            "availability_zone": data.get("availability_zone"),
            "agent_version": data.get("agent_version")
        })
        
        return v
    
    @model_validator(mode='after')
    def validate_heartbeat_data(self):
        """Validate heartbeat data consistency and health metrics"""
        # Validate performance metrics ranges
        if self.cpu_usage_percent is not None and (self.cpu_usage_percent < 0 or self.cpu_usage_percent > 100):
            raise ValueError("CPU usage must be between 0 and 100 percent")
        
        if self.disk_usage_percent is not None and (self.disk_usage_percent < 0 or self.disk_usage_percent > 100):
            raise ValueError("Disk usage must be between 0 and 100 percent")
        
        if self.packet_loss_percent is not None and (self.packet_loss_percent < 0 or self.packet_loss_percent > 100):
            raise ValueError("Packet loss must be between 0 and 100 percent")
        
        # Validate health status consistency
        if self.health_status == HealthStatus.OFFLINE and any([
            self.cpu_usage_percent, self.memory_usage_mb, self.response_time_ms
        ]):
            logger.warning(f"Agent {self.agent_id} marked offline but has performance metrics")
        
        return self
    
    def calculate_adaptive_timeout(self, historical_intervals: List[float]) -> int:
        """Calculate adaptive timeout based on historical heartbeat patterns"""
        if not historical_intervals:
            return self.heartbeat_interval_ms * 3  # Default 3x interval
        
        mean_interval = sum(historical_intervals) / len(historical_intervals)
        variance = sum((x - mean_interval) ** 2 for x in historical_intervals) / len(historical_intervals)
        std_dev = variance ** 0.5
        
        # Adaptive timeout: mean + 2 standard deviations + jitter tolerance
        jitter_tolerance = std_dev * 0.3  # 30% jitter tolerance
        adaptive_timeout = mean_interval + (2 * std_dev) + jitter_tolerance
        
        # Bound between minimum and maximum values
        min_timeout = self.heartbeat_interval_ms * 2
        max_timeout = self.heartbeat_interval_ms * 10
        
        return max(min_timeout, min(max_timeout, int(adaptive_timeout)))


class SystemMetricsModel(BaseMongoModel):
    """
    System metrics model for performance monitoring and trend analysis.
    
    Records comprehensive system performance data with configurable aggregation
    windows. Optimized for time-series storage and real-time dashboard queries.
    Supports custom metrics and threshold-based alerting.
    
    Collection: telemetry_metrics_ts (MongoDB time-series)
    """
    
    # Core identification
    metric_id: str = Field(..., description="Unique metric identifier")
    system_id: str = Field(..., description="System or service identifier")
    metric_name: str = Field(..., description="Metric name")
    metric_type: MetricType = Field(..., description="Type of metric")
    
    # Timing information (time-series key field)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Metric timestamp (time-series timeField)"
    )
    
    # System metadata (time-series metaField)
    system_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="System metadata for time-series grouping"
    )
    
    # Metric values
    value: float = Field(..., description="Primary metric value")
    unit: str = Field(..., description="Metric unit of measurement")
    normalized_value: Optional[float] = Field(None, description="Normalized metric value (0-1 scale)")
    
    # Statistical data
    min_value: Optional[float] = Field(None, description="Minimum value in aggregation window")
    max_value: Optional[float] = Field(None, description="Maximum value in aggregation window")
    avg_value: Optional[float] = Field(None, description="Average value in aggregation window")
    percentile_95: Optional[float] = Field(None, description="95th percentile value")
    percentile_99: Optional[float] = Field(None, description="99th percentile value")
    
    # Data quality
    data_quality_score: float = Field(default=1.0, ge=0, le=1.0, description="Data quality score")
    sample_count: int = Field(default=1, ge=1, description="Number of samples in aggregation")
    collection_method: str = Field(..., description="Data collection method")
    
    # Thresholds and alerting
    warning_threshold: Optional[float] = Field(None, description="Warning alert threshold")
    critical_threshold: Optional[float] = Field(None, description="Critical alert threshold")
    threshold_breached: bool = Field(default=False, description="Whether threshold was breached")
    alert_severity: Optional[AlertSeverity] = Field(None, description="Alert severity if threshold breached")
    
    # Context and classification
    service_name: Optional[str] = Field(None, description="Associated service name")
    component_name: Optional[str] = Field(None, description="Component generating metric")
    environment: str = Field(..., description="Environment (dev/staging/prod)")
    region: Optional[str] = Field(None, description="Geographic region")
    
    # Custom dimensions
    dimensions: Dict[str, Any] = Field(default_factory=dict, description="Custom metric dimensions")
    tags: List[str] = Field(default_factory=list, description="Metric tags for filtering")
    
    # Processing metadata
    processing_status: TelemetryStatus = Field(TelemetryStatus.RECEIVED, description="Processing status")
    aggregation_window: Optional[str] = Field(None, description="Aggregation window (1m, 5m, 1h)")
    
    # Collection configuration
    _collection_name: str = "telemetry_metrics_ts"
    
    @field_validator('system_metadata', mode='before')
    @classmethod
    def populate_system_metadata(cls, v, info):
        """Populate system metadata for time-series optimization"""
        if not v:
            v = {}
        
        # Add context from other fields for time-series grouping
        data = info.data if hasattr(info, 'data') else {}
        v.update({
            "system_id": data.get("system_id"),
            "metric_type": data.get("metric_type"),
            "environment": data.get("environment", "unknown"),
            "service_name": data.get("service_name"),
            "region": data.get("region")
        })
        
        return v
    
    @model_validator(mode='after')
    def validate_metric_data(self):
        """Validate metric data consistency and threshold logic"""
        # Set unit based on metric type if not provided
        if not self.unit and self.metric_type:
            metric_units = MetricType.get_metric_units()
            self.unit = metric_units.get(self.metric_type, "unknown")
        
        # Validate percentage metrics
        if self.metric_type in [MetricType.CPU_USAGE, MetricType.DISK_USAGE] and self.unit == "percentage":
            if self.value < 0 or self.value > 100:
                raise ValueError(f"{self.metric_type} percentage must be between 0 and 100")
        
        # Validate threshold logic
        if self.warning_threshold is not None and self.critical_threshold is not None:
            if self.warning_threshold >= self.critical_threshold:
                raise ValueError("Warning threshold must be less than critical threshold")
        
        # Check threshold breaches
        if self.critical_threshold is not None and self.value >= self.critical_threshold:
            self.threshold_breached = True
            self.alert_severity = AlertSeverity.CRITICAL
        elif self.warning_threshold is not None and self.value >= self.warning_threshold:
            self.threshold_breached = True
            self.alert_severity = AlertSeverity.WARNING
        
        # Normalize value for percentage metrics
        if self.metric_type in [MetricType.CPU_USAGE, MetricType.DISK_USAGE] and self.unit == "percentage":
            self.normalized_value = self.value / 100.0
        
        return self


class TelemetrySnapshotModel(BaseMongoModel):
    """
    Aggregated telemetry snapshot for dashboard consumption and trend analysis.
    
    Pre-computed aggregations optimized for real-time dashboard queries and
    historical trend analysis. Supports multiple aggregation windows and
    custom dashboard layouts.
    
    Collection: telemetry_snapshots
    """
    
    # Core identification
    snapshot_id: str = Field(..., description="Unique snapshot identifier")
    aggregation_key: str = Field(..., description="Aggregation grouping key")
    aggregation_window: str = Field(..., description="Time window (1m, 5m, 15m, 1h, 1d)")
    
    # Time range
    window_start: datetime = Field(..., description="Aggregation window start time")
    window_end: datetime = Field(..., description="Aggregation window end time")
    
    # Agent aggregations
    total_agents: int = Field(default=0, ge=0, description="Total agents in aggregation")
    healthy_agents: int = Field(default=0, ge=0, description="Healthy agents count")
    degraded_agents: int = Field(default=0, ge=0, description="Degraded agents count")
    critical_agents: int = Field(default=0, ge=0, description="Critical agents count")
    offline_agents: int = Field(default=0, ge=0, description="Offline agents count")
    
    # System metrics aggregations
    avg_cpu_usage: Optional[float] = Field(None, ge=0, le=100, description="Average CPU usage")
    max_cpu_usage: Optional[float] = Field(None, ge=0, le=100, description="Maximum CPU usage")
    avg_memory_usage: Optional[float] = Field(None, ge=0, description="Average memory usage (MB)")
    max_memory_usage: Optional[float] = Field(None, ge=0, description="Maximum memory usage (MB)")
    avg_response_time: Optional[float] = Field(None, ge=0, description="Average response time (ms)")
    max_response_time: Optional[float] = Field(None, ge=0, description="Maximum response time (ms)")
    
    # Network aggregations
    avg_network_latency: Optional[float] = Field(None, ge=0, description="Average network latency (ms)")
    max_network_latency: Optional[float] = Field(None, ge=0, description="Maximum network latency (ms)")
    total_network_throughput: Optional[float] = Field(None, ge=0, description="Total network throughput (Mbps)")
    
    # Application metrics
    total_requests: int = Field(default=0, ge=0, description="Total requests processed")
    total_errors: int = Field(default=0, ge=0, description="Total errors encountered")
    error_rate: Optional[float] = Field(None, ge=0, le=100, description="Error rate percentage")
    success_rate: Optional[float] = Field(None, ge=0, le=100, description="Success rate percentage")
    
    # Alerting summary
    total_alerts: int = Field(default=0, ge=0, description="Total alerts generated")
    critical_alerts: int = Field(default=0, ge=0, description="Critical alerts count")
    warning_alerts: int = Field(default=0, ge=0, description="Warning alerts count")
    resolved_alerts: int = Field(default=0, ge=0, description="Resolved alerts count")
    
    # Environment grouping
    environment: str = Field(..., description="Environment identifier")
    region: Optional[str] = Field(None, description="Geographic region")
    availability_zones: List[str] = Field(default_factory=list, description="Covered availability zones")
    
    # Data quality metrics
    data_completeness: float = Field(default=1.0, ge=0, le=1.0, description="Data completeness score")
    sample_count: int = Field(default=0, ge=0, description="Number of samples aggregated")
    missing_data_points: int = Field(default=0, ge=0, description="Missing data points count")
    
    # Dashboard metadata
    dashboard_layout: Optional[str] = Field(None, description="Associated dashboard layout")
    refresh_rate_seconds: int = Field(default=30, ge=5, description="Dashboard refresh rate")
    
    # Collection configuration  
    _collection_name: str = "telemetry_snapshots"
    
    @model_validator(mode='after')
    def validate_snapshot_consistency(self):
        """Validate snapshot data consistency and calculations"""
        # Validate agent counts
        if self.total_agents != (self.healthy_agents + self.degraded_agents + 
                                self.critical_agents + self.offline_agents):
            logger.warning(f"Agent count mismatch in snapshot {self.snapshot_id}")
        
        # Calculate derived metrics
        if self.total_requests > 0 and self.total_errors >= 0:
            self.error_rate = (self.total_errors / self.total_requests) * 100
            self.success_rate = 100 - self.error_rate
        
        # Validate time window
        if self.window_end <= self.window_start:
            raise ValueError("Window end must be after window start")
        
        return self


class HealthStatusModel(BaseMongoModel):
    """
    Health status model for system health assessment and uptime calculation.
    
    Stores calculated health assessments based on telemetry data analysis.
    Supports threshold-based health classification and trend analysis.
    Optimized for real-time health dashboard queries.
    
    Collection: telemetry_health_status
    """
    
    # Core identification
    health_record_id: str = Field(..., description="Unique health record identifier")
    target_id: str = Field(..., description="Target system/agent identifier")
    target_type: str = Field(..., description="Type of target (agent, system, service)")
    
    # Health assessment
    overall_health: HealthStatus = Field(..., description="Overall health status")
    health_score: float = Field(..., ge=0, le=100, description="Numerical health score (0-100)")
    confidence_level: float = Field(default=1.0, ge=0, le=1.0, description="Assessment confidence")
    
    # Component health breakdown
    component_health: Dict[str, HealthStatus] = Field(default_factory=dict, description="Individual component health")
    component_scores: Dict[str, float] = Field(default_factory=dict, description="Component health scores")
    
    # Assessment period
    assessment_start: datetime = Field(..., description="Assessment period start")
    assessment_end: datetime = Field(..., description="Assessment period end")
    assessment_duration: timedelta = Field(..., description="Assessment duration")
    
    # Uptime calculation
    uptime_percentage: float = Field(..., ge=0, le=100, description="Uptime percentage")
    downtime_duration: timedelta = Field(default=timedelta(), description="Total downtime duration")
    availability_sla: Optional[float] = Field(None, ge=0, le=100, description="SLA availability target")
    sla_compliance: Optional[bool] = Field(None, description="Whether SLA is met")
    
    # Failure tracking
    failure_count: int = Field(default=0, ge=0, description="Number of failures detected")
    mttr_seconds: Optional[float] = Field(None, ge=0, description="Mean time to recovery (seconds)")
    mttf_seconds: Optional[float] = Field(None, ge=0, description="Mean time to failure (seconds)")
    
    # Threshold information
    warning_threshold: float = Field(default=85.0, ge=0, le=100, description="Warning threshold")
    critical_threshold: float = Field(default=70.0, ge=0, le=100, description="Critical threshold")
    
    # Environment context
    environment: str = Field(..., description="Environment identifier")
    region: Optional[str] = Field(None, description="Geographic region")
    
    # Collection configuration
    _collection_name: str = "telemetry_health_status"
    
    @model_validator(mode='after')
    def validate_health_assessment(self):
        """Validate health assessment data and thresholds"""
        # Validate threshold logic
        if self.warning_threshold <= self.critical_threshold:
            raise ValueError("Warning threshold must be higher than critical threshold")
        
        # Set overall health based on score
        if self.health_score >= self.warning_threshold:
            self.overall_health = HealthStatus.HEALTHY
        elif self.health_score >= self.critical_threshold:
            self.overall_health = HealthStatus.DEGRADED
        else:
            self.overall_health = HealthStatus.CRITICAL
        
        # Check SLA compliance
        if self.availability_sla is not None:
            self.sla_compliance = self.uptime_percentage >= self.availability_sla
        
        # Validate assessment period
        if self.assessment_end <= self.assessment_start:
            raise ValueError("Assessment end must be after assessment start")
        
        self.assessment_duration = self.assessment_end - self.assessment_start
        
        return self


class UptimeLogModel(BaseMongoModel):
    """
    Uptime log model for tracking uptime sessions and availability metrics.
    
    Records uptime/downtime sessions derived from heartbeat analysis.
    Supports availability calculation and SLA compliance reporting.
    Optimized for historical uptime trend analysis.
    
    Collection: telemetry_uptime_logs
    """
    
    # Core identification
    uptime_session_id: str = Field(..., description="Unique uptime session identifier")
    target_id: str = Field(..., description="Target system/agent identifier")
    target_type: str = Field(..., description="Type of target (agent, system, service)")
    
    # Session timing
    session_start: datetime = Field(..., description="Uptime session start time")
    session_end: Optional[datetime] = Field(None, description="Uptime session end time")
    duration: Optional[timedelta] = Field(None, description="Session duration")
    
    # Session status
    session_type: str = Field(..., description="Session type (uptime, downtime, maintenance)")
    is_active: bool = Field(default=True, description="Whether session is currently active")
    
    # Failure information (for downtime sessions)
    failure_reason: Optional[str] = Field(None, description="Reason for downtime")
    failure_classification: Optional[str] = Field(None, description="Failure classification")
    recovery_action: Optional[str] = Field(None, description="Recovery action taken")
    
    # Performance during session
    avg_response_time: Optional[float] = Field(None, ge=0, description="Average response time during session")
    performance_degradation: Optional[float] = Field(None, description="Performance degradation percentage")
    
    # Environment context
    environment: str = Field(..., description="Environment identifier")
    region: Optional[str] = Field(None, description="Geographic region")
    
    # Collection configuration
    _collection_name: str = "telemetry_uptime_logs"
    
    def end_session(self, end_time: Optional[datetime] = None) -> None:
        """End the uptime session and calculate duration"""
        if end_time is None:
            end_time = datetime.now(timezone.utc)
        
        self.session_end = end_time
        self.is_active = False
        self.duration = self.session_end - self.session_start
        self.update_timestamp()


# Exception classes for telemetry operations
class TelemetryException(Exception):
    """Base exception for telemetry operations"""
    
    def __init__(self, message: str, telemetry_id: Optional[str] = None, error_code: Optional[str] = None):
        super().__init__(message)
        self.telemetry_id = telemetry_id
        self.error_code = error_code
        self.timestamp = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_type": self.__class__.__name__,
            "message": str(self),
            "telemetry_id": self.telemetry_id,
            "error_code": self.error_code,
            "timestamp": self.timestamp.isoformat()
        }


class InvalidTelemetryDataError(TelemetryException):
    """Exception for invalid telemetry data validation errors"""
    
    def __init__(self, message: str, telemetry_id: Optional[str] = None, field_name: Optional[str] = None):
        super().__init__(message, telemetry_id, "INVALID_TELEMETRY_DATA")
        self.field_name = field_name


class HealthCheckFailedError(TelemetryException):
    """Exception for health check validation failures"""
    
    def __init__(self, message: str, target_id: Optional[str] = None, health_status: Optional[HealthStatus] = None):
        super().__init__(message, target_id, "HEALTH_CHECK_FAILED")
        self.health_status = health_status


# MongoDB operations helper
class TelemetryModelOperations:
    """
    Helper class for MongoDB operations on telemetry documents.
    Provides database interaction methods with proper error handling and optimization.
    """
    
    @staticmethod
    def get_heartbeat_indexes() -> List[Dict[str, Any]]:
        """Get MongoDB indexes for heartbeats time-series collection"""
        return [
            # Time-series collection indexes
            {"timestamp": 1, "agent_id": 1},
            {"agent_id": 1, "timestamp": -1},
            {"health_status": 1, "timestamp": -1},
            {"environment": 1, "timestamp": -1},
            {"geographic_location": 1, "timestamp": -1},
            
            # Compound indexes for queries
            {"agent_id": 1, "health_status": 1, "timestamp": -1},
            {"environment": 1, "health_status": 1, "timestamp": -1},
            
            # TTL index for data retention (30 days for raw heartbeats)
            {"timestamp": 1, "expireAfterSeconds": 2592000}
        ]
    
    @staticmethod
    def get_metrics_indexes() -> List[Dict[str, Any]]:
        """Get MongoDB indexes for metrics time-series collection"""
        return [
            # Time-series collection indexes
            {"timestamp": 1, "system_id": 1, "metric_type": 1},
            {"system_id": 1, "metric_type": 1, "timestamp": -1},
            {"metric_type": 1, "timestamp": -1},
            {"environment": 1, "timestamp": -1},
            
            # Alerting indexes
            {"threshold_breached": 1, "alert_severity": 1, "timestamp": -1},
            {"system_id": 1, "threshold_breached": 1, "timestamp": -1},
            
            # TTL index for data retention (90 days for raw metrics)
            {"timestamp": 1, "expireAfterSeconds": 7776000}
        ]
    
    @staticmethod
    def get_snapshot_indexes() -> List[Dict[str, Any]]:
        """Get MongoDB indexes for telemetry snapshots collection"""
        return [
            # Primary query indexes
            {"aggregation_key": 1, "aggregation_window": 1, "window_start": -1},
            {"environment": 1, "aggregation_window": 1, "window_start": -1},
            {"window_start": -1, "window_end": -1},
            
            # Dashboard queries
            {"environment": 1, "window_start": -1},
            {"aggregation_window": 1, "window_start": -1},
            
            # TTL index for snapshot retention (1 year)
            {"window_start": 1, "expireAfterSeconds": 31536000}
        ]
    
    @staticmethod
    def get_health_status_indexes() -> List[Dict[str, Any]]:
        """Get MongoDB indexes for health status collection"""
        return [
            # Primary query indexes
            {"target_id": 1, "assessment_start": -1},
            {"target_type": 1, "overall_health": 1, "assessment_start": -1},
            {"environment": 1, "overall_health": 1, "assessment_start": -1},
            
            # SLA compliance queries
            {"sla_compliance": 1, "assessment_start": -1},
            {"target_id": 1, "sla_compliance": 1, "assessment_start": -1},
            
            # TTL index for health status retention (1 year)
            {"assessment_start": 1, "expireAfterSeconds": 31536000}
        ]
    
    @staticmethod
    def get_uptime_log_indexes() -> List[Dict[str, Any]]:
        """Get MongoDB indexes for uptime logs collection"""
        return [
            # Primary query indexes
            {"target_id": 1, "session_start": -1},
            {"target_type": 1, "session_type": 1, "session_start": -1},
            {"environment": 1, "session_start": -1},
            
            # Active session queries
            {"is_active": 1, "target_id": 1},
            {"target_id": 1, "is_active": 1, "session_start": -1},
            
            # TTL index for uptime log retention (2 years)
            {"session_start": 1, "expireAfterSeconds": 63072000}
        ] 
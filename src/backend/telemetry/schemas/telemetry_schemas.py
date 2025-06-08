"""
Environment Telemetry & Health Monitoring Engine - API Schemas

Implements comprehensive request/response schemas for telemetry operations with
robust Pydantic validation, OpenAPI documentation support, and standardized
response formats. Optimized for high-throughput data ingestion and real-time
dashboard queries.

Key Features:
- Comprehensive input validation with detailed error messages
- OpenAPI-compliant schema definitions with examples
- Standardized response formats for consistent API behavior
- Performance-optimized serialization for high-volume operations
- Type-safe data handling with comprehensive validation
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Union
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict

from ..models.telemetry_models import HealthStatus, MetricType, AlertSeverity, TelemetryStatus


# =====================================================================
# COMMON SCHEMAS
# =====================================================================

class TimeRangeSchema(BaseModel):
    """Time range specification for queries and aggregations"""
    
    start_time: datetime = Field(..., description="Start time (ISO 8601 format)")
    end_time: datetime = Field(..., description="End time (ISO 8601 format)")
    timezone: str = Field(default="UTC", description="Timezone for time range")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "start_time": "2025-01-07T20:00:00Z",
                "end_time": "2025-01-07T21:00:00Z",
                "timezone": "UTC"
            }
        }
    )
    
    @model_validator(mode='after')
    def validate_time_range(self):
        """Validate time range consistency"""
        if self.end_time <= self.start_time:
            raise ValueError("End time must be after start time")
        
        # Validate reasonable time range (not more than 1 year)
        if (self.end_time - self.start_time).days > 365:
            raise ValueError("Time range cannot exceed 365 days")
        
        return self


class AgentInfoSchema(BaseModel):
    """Agent information schema for identification and metadata"""
    
    agent_id: str = Field(..., description="Unique agent identifier")
    agent_name: Optional[str] = Field(None, description="Human-readable agent name")
    agent_version: str = Field(..., description="Agent software version")
    environment: str = Field(..., description="Deployment environment")
    geographic_location: Optional[str] = Field(None, description="Agent geographic location")
    availability_zone: Optional[str] = Field(None, description="Cloud availability zone")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "agent_id": "agent-web-01-prod",
                "agent_name": "Web Server 01",
                "agent_version": "2.1.3",
                "environment": "production",
                "geographic_location": "us-east-1",
                "availability_zone": "us-east-1a"
            }
        }
    )


class MetricDataSchema(BaseModel):
    """Individual metric data point schema"""
    
    metric_name: str = Field(..., description="Metric name")
    metric_type: MetricType = Field(..., description="Type of metric")
    value: float = Field(..., description="Metric value")
    unit: str = Field(..., description="Unit of measurement")
    timestamp: Optional[datetime] = Field(None, description="Metric timestamp")
    dimensions: Dict[str, Any] = Field(default_factory=dict, description="Custom metric dimensions")
    tags: List[str] = Field(default_factory=list, description="Metric tags")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "metric_name": "cpu_usage",
                "metric_type": "cpu_usage",
                "value": 75.5,
                "unit": "percentage",
                "timestamp": "2025-01-07T20:30:00Z",
                "dimensions": {"core": "cpu0"},
                "tags": ["system", "performance"]
            }
        }
    )


class AlertInfoSchema(BaseModel):
    """Alert information schema"""
    
    alert_id: str = Field(..., description="Unique alert identifier")
    severity: AlertSeverity = Field(..., description="Alert severity level")
    message: str = Field(..., description="Alert message")
    source: str = Field(..., description="Alert source component")
    timestamp: datetime = Field(..., description="Alert generation time")
    resolved: bool = Field(default=False, description="Whether alert is resolved")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "alert_id": "alert-cpu-high-001",
                "severity": "warning",
                "message": "CPU usage exceeded 80% threshold",
                "source": "agent-web-01-prod",
                "timestamp": "2025-01-07T20:35:00Z",
                "resolved": False
            }
        }
    )


class HealthAssessmentSchema(BaseModel):
    """Health assessment summary schema"""
    
    overall_health: HealthStatus = Field(..., description="Overall health status")
    health_score: float = Field(..., ge=0, le=100, description="Numerical health score")
    uptime_percentage: float = Field(..., ge=0, le=100, description="Uptime percentage")
    last_check: datetime = Field(..., description="Last health check time")
    components: Dict[str, HealthStatus] = Field(default_factory=dict, description="Component health breakdown")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "overall_health": "healthy",
                "health_score": 95.2,
                "uptime_percentage": 99.8,
                "last_check": "2025-01-07T20:30:00Z",
                "components": {
                    "cpu": "healthy",
                    "memory": "healthy", 
                    "disk": "degraded"
                }
            }
        }
    )


# =====================================================================
# REQUEST SCHEMAS
# =====================================================================

class HeartbeatRequestSchema(BaseModel):
    """Agent heartbeat request schema for health status reporting"""
    
    agent_info: AgentInfoSchema = Field(..., description="Agent identification and metadata")
    health_status: HealthStatus = Field(..., description="Current agent health status")
    timestamp: datetime = Field(..., description="Heartbeat timestamp")
    
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
    response_time_ms: Optional[float] = Field(None, ge=0, description="Average response time")
    
    # Additional context
    status_details: Dict[str, Any] = Field(default_factory=dict, description="Detailed status information")
    heartbeat_interval_ms: int = Field(default=30000, ge=1000, description="Expected heartbeat interval")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "agent_info": {
                    "agent_id": "agent-web-01-prod",
                    "agent_name": "Web Server 01",
                    "agent_version": "2.1.3",
                    "environment": "production",
                    "geographic_location": "us-east-1",
                    "availability_zone": "us-east-1a"
                },
                "health_status": "healthy",
                "timestamp": "2025-01-07T20:30:00Z",
                "cpu_usage_percent": 75.5,
                "memory_usage_mb": 2048.0,
                "disk_usage_percent": 45.2,
                "network_latency_ms": 15.3,
                "bandwidth_usage_mbps": 125.7,
                "active_connections": 150,
                "request_count": 1250,
                "error_count": 5,
                "response_time_ms": 120.5,
                "heartbeat_interval_ms": 30000
            }
        }
    )


class SystemMetricsRequestSchema(BaseModel):
    """System metrics ingestion request schema"""
    
    system_id: str = Field(..., description="System or service identifier")
    timestamp: datetime = Field(..., description="Metrics timestamp")
    environment: str = Field(..., description="Environment identifier")
    
    # Metric data
    metrics: List[MetricDataSchema] = Field(..., min_length=1, description="List of metric data points")
    
    # Collection context
    collection_method: str = Field(..., description="Data collection method")
    collection_interval_ms: int = Field(default=60000, ge=1000, description="Collection interval")
    
    # System context
    service_name: Optional[str] = Field(None, description="Associated service name")
    component_name: Optional[str] = Field(None, description="Component generating metrics")
    region: Optional[str] = Field(None, description="Geographic region")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "system_id": "web-service-cluster-01",
                "timestamp": "2025-01-07T20:30:00Z",
                "environment": "production",
                "metrics": [
                    {
                        "metric_name": "cpu_usage",
                        "metric_type": "cpu_usage",
                        "value": 75.5,
                        "unit": "percentage",
                        "dimensions": {"instance": "web-01"}
                    },
                    {
                        "metric_name": "memory_usage",
                        "metric_type": "memory_usage", 
                        "value": 2048.0,
                        "unit": "megabytes",
                        "dimensions": {"instance": "web-01"}
                    }
                ],
                "collection_method": "agent_push",
                "collection_interval_ms": 60000,
                "service_name": "web-service",
                "region": "us-east-1"
            }
        }
    )
    
    @field_validator('metrics')
    @classmethod
    def validate_metrics_not_empty(cls, v):
        """Ensure at least one metric is provided"""
        if not v:
            raise ValueError("At least one metric must be provided")
        return v


class TelemetryIngestionBatchSchema(BaseModel):
    """Batch telemetry ingestion request schema for high-throughput operations"""
    
    batch_id: str = Field(..., description="Unique batch identifier")
    batch_timestamp: datetime = Field(..., description="Batch processing timestamp")
    
    # Batch content
    heartbeats: List[HeartbeatRequestSchema] = Field(default_factory=list, description="Heartbeat data")
    metrics: List[SystemMetricsRequestSchema] = Field(default_factory=list, description="Metrics data")
    
    # Batch metadata
    source_system: str = Field(..., description="Source system generating batch")
    compression_used: bool = Field(default=False, description="Whether batch data is compressed")
    checksum: Optional[str] = Field(None, description="Batch data checksum for integrity")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "batch_id": "batch-20250107-203000-001",
                "batch_timestamp": "2025-01-07T20:30:00Z",
                "heartbeats": [],
                "metrics": [],
                "source_system": "telemetry-collector-v2",
                "compression_used": True,
                "checksum": "sha256:abc123..."
            }
        }
    )
    
    @model_validator(mode='after') 
    def validate_batch_content(self):
        """Validate batch has content"""
        if not self.heartbeats and not self.metrics:
            raise ValueError("Batch must contain at least heartbeats or metrics")
        return self


class HealthCheckRequestSchema(BaseModel):
    """Health check request schema for manual health assessments"""
    
    target_id: str = Field(..., description="Target system/agent identifier")
    target_type: str = Field(..., description="Type of target (agent, system, service)")
    assessment_type: str = Field(default="full", description="Type of assessment (full, quick, component)")
    
    # Assessment parameters
    time_range: Optional[TimeRangeSchema] = Field(None, description="Time range for assessment")
    components: List[str] = Field(default_factory=list, description="Specific components to assess")
    include_historical: bool = Field(default=True, description="Include historical data in assessment")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "target_id": "agent-web-01-prod",
                "target_type": "agent",
                "assessment_type": "full",
                "time_range": {
                    "start_time": "2025-01-07T19:30:00Z",
                    "end_time": "2025-01-07T20:30:00Z",
                    "timezone": "UTC"
                },
                "components": ["cpu", "memory", "disk", "network"],
                "include_historical": True
            }
        }
    )


class DashboardQuerySchema(BaseModel):
    """Dashboard data query request schema"""
    
    query_id: str = Field(..., description="Unique query identifier")
    query_type: str = Field(..., description="Type of dashboard query")
    
    # Query parameters
    time_range: TimeRangeSchema = Field(..., description="Time range for data query")
    aggregation_window: str = Field(..., description="Aggregation window (1m, 5m, 15m, 1h, 1d)")
    environments: List[str] = Field(default_factory=list, description="Environment filters")
    regions: List[str] = Field(default_factory=list, description="Region filters")
    
    # Data filtering
    agent_ids: List[str] = Field(default_factory=list, description="Specific agent IDs to include")
    system_ids: List[str] = Field(default_factory=list, description="Specific system IDs to include")
    metric_types: List[MetricType] = Field(default_factory=list, description="Metric types to include")
    health_statuses: List[HealthStatus] = Field(default_factory=list, description="Health status filters")
    
    # Query options
    include_alerts: bool = Field(default=True, description="Include alert information")
    include_trends: bool = Field(default=True, description="Include trend analysis")
    max_data_points: int = Field(default=1000, ge=1, le=10000, description="Maximum data points to return")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query_id": "dashboard-query-main-001",
                "query_type": "overview",
                "time_range": {
                    "start_time": "2025-01-07T19:30:00Z",
                    "end_time": "2025-01-07T20:30:00Z",
                    "timezone": "UTC"
                },
                "aggregation_window": "5m",
                "environments": ["production"],
                "regions": ["us-east-1"],
                "include_alerts": True,
                "include_trends": True,
                "max_data_points": 500
            }
        }
    )


# =====================================================================
# RESPONSE SCHEMAS  
# =====================================================================

class HeartbeatResponseSchema(BaseModel):
    """Agent heartbeat response schema"""
    
    success: bool = Field(..., description="Whether heartbeat was processed successfully")
    heartbeat_id: str = Field(..., description="Generated heartbeat identifier")
    agent_id: str = Field(..., description="Agent identifier")
    
    # Processing results
    processing_time_ms: float = Field(..., ge=0, description="Processing time in milliseconds")
    data_quality_score: float = Field(..., ge=0, le=1, description="Data quality assessment")
    
    # Health assessment
    calculated_health: HealthStatus = Field(..., description="Calculated health status")
    health_score: float = Field(..., ge=0, le=100, description="Numerical health score")
    
    # Timeout and monitoring
    next_expected_heartbeat: datetime = Field(..., description="Next expected heartbeat time")
    adaptive_timeout_ms: int = Field(..., description="Calculated adaptive timeout")
    
    # Alerts and recommendations
    alerts_generated: List[AlertInfoSchema] = Field(default_factory=list, description="Alerts generated")
    recommendations: List[str] = Field(default_factory=list, description="Performance recommendations")
    
    # Response metadata
    timestamp: datetime = Field(..., description="Response timestamp")
    message: str = Field(..., description="Processing status message")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "heartbeat_id": "hb-20250107-203000-001",
                "agent_id": "agent-web-01-prod",
                "processing_time_ms": 12.5,
                "data_quality_score": 0.98,
                "calculated_health": "healthy",
                "health_score": 95.2,
                "next_expected_heartbeat": "2025-01-07T21:00:00Z",
                "adaptive_timeout_ms": 45000,
                "alerts_generated": [],
                "recommendations": ["Consider optimizing memory usage"],
                "timestamp": "2025-01-07T20:30:12Z",
                "message": "Heartbeat processed successfully"
            }
        }
    )


class SystemMetricsResponseSchema(BaseModel):
    """System metrics ingestion response schema"""
    
    success: bool = Field(..., description="Whether metrics were processed successfully")
    metrics_processed: int = Field(..., ge=0, description="Number of metrics processed")
    system_id: str = Field(..., description="System identifier")
    
    # Processing results
    processing_time_ms: float = Field(..., ge=0, description="Processing time in milliseconds")
    validation_errors: List[str] = Field(default_factory=list, description="Validation errors")
    
    # Data quality assessment
    data_quality_scores: Dict[str, float] = Field(default_factory=dict, description="Per-metric quality scores")
    outliers_detected: List[str] = Field(default_factory=list, description="Outlier metrics detected")
    
    # Threshold analysis
    thresholds_breached: List[str] = Field(default_factory=list, description="Thresholds breached")
    alerts_generated: List[AlertInfoSchema] = Field(default_factory=list, description="Alerts generated")
    
    # Response metadata
    timestamp: datetime = Field(..., description="Response timestamp")
    message: str = Field(..., description="Processing status message")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "metrics_processed": 25,
                "system_id": "web-service-cluster-01",
                "processing_time_ms": 8.7,
                "validation_errors": [],
                "data_quality_scores": {
                    "cpu_usage": 1.0,
                    "memory_usage": 0.95
                },
                "outliers_detected": [],
                "thresholds_breached": ["cpu_usage"],
                "alerts_generated": [
                    {
                        "alert_id": "alert-cpu-high-001",
                        "severity": "warning",
                        "message": "CPU usage exceeded warning threshold",
                        "source": "web-service-cluster-01",
                        "timestamp": "2025-01-07T20:30:00Z",
                        "resolved": False
                    }
                ],
                "timestamp": "2025-01-07T20:30:08Z",
                "message": "Metrics processed successfully with warnings"
            }
        }
    )


class TelemetryDashboardDataSchema(BaseModel):
    """Dashboard data response schema with aggregated telemetry information"""
    
    query_id: str = Field(..., description="Query identifier")
    query_executed_at: datetime = Field(..., description="Query execution timestamp")
    data_freshness: datetime = Field(..., description="Data freshness timestamp")
    
    # Aggregated data
    time_range: TimeRangeSchema = Field(..., description="Actual time range of data")
    aggregation_window: str = Field(..., description="Aggregation window used")
    total_data_points: int = Field(..., ge=0, description="Total data points in response")
    
    # Agent summary
    agent_summary: Dict[str, Any] = Field(..., description="Agent health summary")
    system_summary: Dict[str, Any] = Field(..., description="System metrics summary")
    
    # Time-series data
    time_series_data: List[Dict[str, Any]] = Field(..., description="Time-series data points")
    
    # Alerts and notifications
    active_alerts: List[AlertInfoSchema] = Field(default_factory=list, description="Active alerts")
    alert_summary: Dict[str, int] = Field(default_factory=dict, description="Alert count by severity")
    
    # Trends and analysis
    trends: Dict[str, Any] = Field(default_factory=dict, description="Trend analysis")
    anomalies: List[Dict[str, Any]] = Field(default_factory=list, description="Detected anomalies")
    
    # Performance metadata
    query_performance: Dict[str, Any] = Field(default_factory=dict, description="Query performance metrics")
    cache_hit_ratio: float = Field(..., ge=0, le=1, description="Cache hit ratio")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query_id": "dashboard-query-main-001",
                "query_executed_at": "2025-01-07T20:30:00Z",
                "data_freshness": "2025-01-07T20:29:45Z",
                "time_range": {
                    "start_time": "2025-01-07T19:30:00Z",
                    "end_time": "2025-01-07T20:30:00Z",
                    "timezone": "UTC"
                },
                "aggregation_window": "5m",
                "total_data_points": 125,
                "agent_summary": {
                    "total_agents": 50,
                    "healthy_agents": 45,
                    "degraded_agents": 3,
                    "critical_agents": 1,
                    "offline_agents": 1
                },
                "system_summary": {
                    "avg_cpu_usage": 72.5,
                    "avg_memory_usage": 68.2,
                    "avg_response_time": 125.3
                },
                "time_series_data": [],
                "active_alerts": [],
                "alert_summary": {
                    "critical": 1,
                    "warning": 5,
                    "info": 2
                },
                "cache_hit_ratio": 0.85
            }
        }
    )


class HealthStatusResponseSchema(BaseModel):
    """Health status assessment response schema"""
    
    target_id: str = Field(..., description="Target system/agent identifier")
    assessment_id: str = Field(..., description="Health assessment identifier")
    assessment_completed_at: datetime = Field(..., description="Assessment completion time")
    
    # Health assessment results
    health_assessment: HealthAssessmentSchema = Field(..., description="Comprehensive health assessment")
    
    # Uptime information
    uptime_percentage: float = Field(..., ge=0, le=100, description="Uptime percentage")
    downtime_duration: str = Field(..., description="Total downtime duration")
    uptime_sessions: List[Dict[str, Any]] = Field(default_factory=list, description="Recent uptime sessions")
    
    # SLA compliance
    sla_target: Optional[float] = Field(None, description="SLA uptime target")
    sla_compliance: Optional[bool] = Field(None, description="SLA compliance status")
    sla_breach_risk: Optional[str] = Field(None, description="SLA breach risk assessment")
    
    # Performance trends
    performance_trends: Dict[str, Any] = Field(default_factory=dict, description="Performance trend analysis")
    failure_patterns: List[Dict[str, Any]] = Field(default_factory=list, description="Identified failure patterns")
    
    # Recommendations
    health_recommendations: List[str] = Field(default_factory=list, description="Health improvement recommendations")
    maintenance_suggestions: List[str] = Field(default_factory=list, description="Maintenance suggestions")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "target_id": "agent-web-01-prod",
                "assessment_id": "health-assessment-001",
                "assessment_completed_at": "2025-01-07T20:30:00Z",
                "health_assessment": {
                    "overall_health": "healthy",
                    "health_score": 95.2,
                    "uptime_percentage": 99.8,
                    "last_check": "2025-01-07T20:30:00Z",
                    "components": {
                        "cpu": "healthy",
                        "memory": "healthy",
                        "disk": "degraded"
                    }
                },
                "uptime_percentage": 99.8,
                "downtime_duration": "PT2M30S",
                "sla_target": 99.5,
                "sla_compliance": True,
                "health_recommendations": [
                    "Monitor disk usage trends",
                    "Consider memory optimization"
                ]
            }
        }
    )


class UptimeStatusResponseSchema(BaseModel):
    """Uptime status response schema for agent availability calculation"""
    
    agent_id: str = Field(..., description="Target agent identifier")
    calculation_period_hours: int = Field(..., ge=1, description="Analysis time period in hours")
    calculated_at: datetime = Field(..., description="Calculation timestamp")
    
    # Health assessment
    health_assessment: HealthAssessmentSchema = Field(..., description="Comprehensive health assessment")
    
    # Uptime metrics
    uptime_percentage: float = Field(..., ge=0, le=100, description="Uptime percentage")
    total_uptime_minutes: float = Field(..., ge=0, description="Total uptime in minutes")
    total_downtime_minutes: float = Field(..., ge=0, description="Total downtime in minutes")
    
    # Session data
    uptime_sessions: List[Dict[str, Any]] = Field(default_factory=list, description="Uptime sessions")
    downtime_periods: List[Dict[str, Any]] = Field(default_factory=list, description="Downtime periods")
    
    # SLA compliance
    sla_target: Optional[float] = Field(None, description="SLA uptime target")
    sla_compliance: Optional[bool] = Field(None, description="SLA compliance status")
    sla_breach_risk: Optional[str] = Field(None, description="SLA breach risk assessment")
    
    # Availability trends
    availability_trend: Optional[str] = Field(None, description="Availability trend")
    mttr_minutes: Optional[float] = Field(None, description="Mean time to recovery in minutes")
    mtbf_hours: Optional[float] = Field(None, description="Mean time between failures in hours")
    
    # Failure analysis
    failure_patterns: List[Dict[str, Any]] = Field(default_factory=list, description="Identified failure patterns")
    
    # Recommendations
    health_recommendations: List[str] = Field(default_factory=list, description="Health improvement recommendations")
    
    # Quality metrics
    data_quality_score: float = Field(..., ge=0, le=1, description="Data quality score")
    confidence_level: float = Field(..., ge=0, le=1, description="Confidence level")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "agent_id": "agent-web-01-prod",
                "calculation_period_hours": 24,
                "calculated_at": "2025-01-07T20:30:00Z",
                "health_assessment": {
                    "overall_health": "healthy",
                    "health_score": 95.2,
                    "uptime_percentage": 99.8,
                    "last_check": "2025-01-07T20:30:00Z",
                    "components": {"cpu": "healthy", "memory": "healthy"}
                },
                "uptime_percentage": 99.8,
                "total_uptime_minutes": 1437.6,
                "total_downtime_minutes": 2.4,
                "sla_target": 99.5,
                "sla_compliance": True,
                "sla_breach_risk": "low",
                "availability_trend": "stable",
                "health_recommendations": ["Monitor network stability"],
                "data_quality_score": 0.98,
                "confidence_level": 0.95
            }
        }
    )


class UptimeSummaryResponseSchema(BaseModel):
    """Uptime summary response schema for availability reporting"""
    
    target_id: str = Field(..., description="Target system/agent identifier")
    summary_period: TimeRangeSchema = Field(..., description="Summary time period")
    generated_at: datetime = Field(..., description="Summary generation timestamp")
    
    # Uptime metrics
    overall_uptime_percentage: float = Field(..., ge=0, le=100, description="Overall uptime percentage")
    total_uptime_duration: str = Field(..., description="Total uptime duration")
    total_downtime_duration: str = Field(..., description="Total downtime duration")
    
    # Availability breakdown
    daily_uptime: List[Dict[str, Any]] = Field(default_factory=list, description="Daily uptime breakdown")
    uptime_by_component: Dict[str, float] = Field(default_factory=dict, description="Uptime by component")
    
    # Incident summary
    total_incidents: int = Field(..., ge=0, description="Total incidents in period")
    incident_breakdown: Dict[str, int] = Field(default_factory=dict, description="Incidents by severity")
    mttr_minutes: Optional[float] = Field(None, description="Mean time to recovery in minutes")
    mtbf_hours: Optional[float] = Field(None, description="Mean time between failures in hours")
    
    # SLA information
    sla_targets: Dict[str, float] = Field(default_factory=dict, description="SLA targets")
    sla_compliance: Dict[str, bool] = Field(default_factory=dict, description="SLA compliance by metric")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "target_id": "web-service-cluster",
                "summary_period": {
                    "start_time": "2025-01-01T00:00:00Z",
                    "end_time": "2025-01-07T23:59:59Z",
                    "timezone": "UTC"
                },
                "generated_at": "2025-01-07T20:30:00Z",
                "overall_uptime_percentage": 99.7,
                "total_uptime_duration": "P6DT23H48M",
                "total_downtime_duration": "PT12M",
                "total_incidents": 3,
                "mttr_minutes": 4.5,
                "mtbf_hours": 56.2,
                "sla_targets": {
                    "availability": 99.5
                },
                "sla_compliance": {
                    "availability": True
                }
            }
        }
    )


class TelemetryIngestionResultSchema(BaseModel):
    """Batch telemetry ingestion result schema"""
    
    success: bool = Field(..., description="Overall batch processing success")
    batch_id: str = Field(..., description="Batch identifier")
    processed_at: datetime = Field(..., description="Batch processing timestamp")
    
    # Processing statistics
    total_heartbeats: int = Field(..., ge=0, description="Total heartbeats in batch")
    processed_heartbeats: int = Field(..., ge=0, description="Successfully processed heartbeats")
    failed_heartbeats: int = Field(..., ge=0, description="Failed heartbeat processing")
    
    total_metrics: int = Field(..., ge=0, description="Total metrics in batch")
    processed_metrics: int = Field(..., ge=0, description="Successfully processed metrics")
    failed_metrics: int = Field(..., ge=0, description="Failed metric processing")
    
    # Performance metrics
    processing_time_ms: float = Field(..., ge=0, description="Total processing time")
    throughput_per_second: float = Field(..., ge=0, description="Processing throughput")
    
    # Error handling
    validation_errors: List[str] = Field(default_factory=list, description="Validation errors")
    processing_errors: List[str] = Field(default_factory=list, description="Processing errors")
    
    # Results summary
    alerts_generated: int = Field(..., ge=0, description="Total alerts generated")
    data_quality_score: float = Field(..., ge=0, le=1, description="Overall data quality score")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "batch_id": "batch-20250107-203000-001",
                "processed_at": "2025-01-07T20:30:15Z",
                "total_heartbeats": 50,
                "processed_heartbeats": 49,
                "failed_heartbeats": 1,
                "total_metrics": 250,
                "processed_metrics": 248,
                "failed_metrics": 2,
                "processing_time_ms": 125.7,
                "throughput_per_second": 2387.5,
                "validation_errors": ["Invalid timestamp format"],
                "processing_errors": [],
                "alerts_generated": 3,
                "data_quality_score": 0.97
            }
        }
    )


# =====================================================================
# CONFIGURATION SCHEMAS
# =====================================================================

class ThresholdConfigSchema(BaseModel):
    """Threshold configuration schema for alerting"""
    
    metric_type: MetricType = Field(..., description="Metric type for threshold")
    warning_threshold: float = Field(..., description="Warning threshold value")
    critical_threshold: float = Field(..., description="Critical threshold value")
    threshold_operator: str = Field(default="greater_than", description="Threshold comparison operator")
    
    # Threshold behavior
    evaluation_window: str = Field(default="5m", description="Evaluation window for threshold")
    consecutive_breaches: int = Field(default=1, ge=1, description="Required consecutive breaches")
    auto_resolve: bool = Field(default=True, description="Auto-resolve when back to normal")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "metric_type": "cpu_usage",
                "warning_threshold": 80.0,
                "critical_threshold": 95.0,
                "threshold_operator": "greater_than",
                "evaluation_window": "5m",
                "consecutive_breaches": 2,
                "auto_resolve": True
            }
        }
    )


class AlertConfigSchema(BaseModel):
    """Alert configuration schema for notification management"""
    
    alert_type: str = Field(..., description="Type of alert")
    severity: AlertSeverity = Field(..., description="Alert severity")
    
    # Notification settings
    notification_channels: List[str] = Field(default_factory=list, description="Notification channels")
    escalation_delay_minutes: int = Field(default=15, ge=1, description="Escalation delay in minutes")
    
    # Alert behavior
    suppress_duplicates: bool = Field(default=True, description="Suppress duplicate alerts")
    suppression_window_minutes: int = Field(default=60, ge=1, description="Suppression window")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "alert_type": "high_cpu_usage",
                "severity": "warning",
                "notification_channels": ["email", "slack"],
                "escalation_delay_minutes": 15,
                "suppress_duplicates": True,
                "suppression_window_minutes": 60
            }
        }
    )


class TelemetryConfigSchema(BaseModel):
    """Telemetry system configuration schema"""
    
    # Collection settings
    default_heartbeat_interval_ms: int = Field(default=30000, ge=1000, description="Default heartbeat interval")
    default_metrics_interval_ms: int = Field(default=60000, ge=1000, description="Default metrics interval")
    
    # Data retention
    heartbeat_retention_days: int = Field(default=30, ge=1, description="Heartbeat data retention")
    metrics_retention_days: int = Field(default=90, ge=1, description="Metrics data retention")
    snapshot_retention_days: int = Field(default=365, ge=1, description="Snapshot data retention")
    
    # Processing settings
    batch_size: int = Field(default=1000, ge=1, description="Batch processing size")
    processing_timeout_ms: int = Field(default=5000, ge=1000, description="Processing timeout")
    
    # Alerting defaults
    default_thresholds: List[ThresholdConfigSchema] = Field(default_factory=list, description="Default thresholds")
    alert_configs: List[AlertConfigSchema] = Field(default_factory=list, description="Alert configurations")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "default_heartbeat_interval_ms": 30000,
                "default_metrics_interval_ms": 60000,
                "heartbeat_retention_days": 30,
                "metrics_retention_days": 90,
                "snapshot_retention_days": 365,
                "batch_size": 1000,
                "processing_timeout_ms": 5000,
                "default_thresholds": [],
                "alert_configs": []
            }
        }
    )
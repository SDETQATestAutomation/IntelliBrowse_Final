"""
Environment Telemetry & Health Monitoring Engine - Schemas Package

Implements comprehensive API request/response schemas for telemetry data ingestion,
health monitoring, and dashboard aggregation. Designed with Pydantic validation
for robust data handling and OpenAPI documentation generation.

Key Schemas:
- HeartbeatRequest/Response: Agent heartbeat and health status
- SystemMetricsRequest/Response: System performance metrics
- TelemetryDashboardData: Dashboard aggregation responses
- HealthStatusRequest/Response: Health assessment and uptime data
"""

from .telemetry_schemas import (
    # Request schemas
    HeartbeatRequestSchema,
    SystemMetricsRequestSchema,
    TelemetryIngestionBatchSchema,
    HealthCheckRequestSchema,
    DashboardQuerySchema,
    
    # Response schemas
    HeartbeatResponseSchema,
    SystemMetricsResponseSchema,
    TelemetryDashboardDataSchema,
    HealthStatusResponseSchema,
    UptimeSummaryResponseSchema,
    TelemetryIngestionResultSchema,
    
    # Common schemas
    AgentInfoSchema,
    MetricDataSchema,
    HealthAssessmentSchema,
    AlertInfoSchema,
    TimeRangeSchema,
    
    # Configuration schemas
    TelemetryConfigSchema,
    ThresholdConfigSchema,
    AlertConfigSchema
)

__all__ = [
    # Request schemas
    "HeartbeatRequestSchema",
    "SystemMetricsRequestSchema", 
    "TelemetryIngestionBatchSchema",
    "HealthCheckRequestSchema",
    "DashboardQuerySchema",
    
    # Response schemas
    "HeartbeatResponseSchema",
    "SystemMetricsResponseSchema",
    "TelemetryDashboardDataSchema",
    "HealthStatusResponseSchema",
    "UptimeSummaryResponseSchema",
    "TelemetryIngestionResultSchema",
    
    # Common schemas
    "AgentInfoSchema",
    "MetricDataSchema",
    "HealthAssessmentSchema",
    "AlertInfoSchema",
    "TimeRangeSchema",
    
    # Configuration schemas
    "TelemetryConfigSchema",
    "ThresholdConfigSchema",
    "AlertConfigSchema"
] 
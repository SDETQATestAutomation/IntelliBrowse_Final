"""
Environment Telemetry & Health Monitoring Engine - Models Package

Implements the foundation data models for telemetry ingestion, agent health tracking,
system metrics collection, and uptime monitoring. Designed for MongoDB storage with
optimized time-series indexing and high-performance aggregation pipelines.

Key Models:
- AgentHeartbeatModel: Agent connectivity and health status tracking
- SystemMetricsModel: System performance metrics collection  
- TelemetrySnapshotModel: Aggregated telemetry snapshots for dashboards
- HealthStatusModel: Health assessment and uptime calculation
"""

from .telemetry_models import (
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
    HealthCheckFailedError,
    TelemetryModelOperations
)

__all__ = [
    "AgentHeartbeatModel",
    "SystemMetricsModel", 
    "TelemetrySnapshotModel",
    "HealthStatusModel",
    "UptimeLogModel",
    "HealthStatus",
    "MetricType",
    "TelemetryStatus",
    "AlertSeverity",
    "TelemetryException",
    "InvalidTelemetryDataError",
    "HealthCheckFailedError",
    "TelemetryModelOperations"
] 
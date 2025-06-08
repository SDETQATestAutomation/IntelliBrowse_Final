"""
Telemetry Services Module

Provides comprehensive service layer implementations for the Environment Telemetry 
& Health Monitoring Engine. Implements business logic for telemetry data processing,
health assessment, and real-time dashboard aggregation.

Key Services:
- TelemetryService: Core telemetry data processing and validation
- TelemetryIngestionService: High-throughput data ingestion pipeline
- HealthMonitoringService: Agent health assessment and failure detection  
- DashboardAggregationService: Real-time dashboard data preparation

All services follow async/await patterns with comprehensive error handling,
dependency injection via FastAPI Depends(), and structured logging.
"""

from .telemetry_service import TelemetryService

__all__ = [
    "TelemetryService",
] 
"""
Telemetry Controllers Module

Provides HTTP boundary layer implementations for the Environment Telemetry 
& Health Monitoring Engine. Implements FastAPI-compatible controllers with
comprehensive request validation, JWT authentication, and error handling.

Key Controllers:
- TelemetryController: Core telemetry data ingestion and status retrieval
- TelemetryDashboardController: Dashboard data aggregation and visualization
- TelemetryConfigController: Configuration management and threshold administration

All controllers follow FastAPI patterns with:
- Pydantic request/response validation
- JWT-based authentication via Depends()
- Comprehensive error handling with HTTP status codes
- Structured logging with correlation tracking
- Clean separation from business logic (delegated to services)
"""

from .telemetry_controller import TelemetryController

__all__ = [
    "TelemetryController",
] 
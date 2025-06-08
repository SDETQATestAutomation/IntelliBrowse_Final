"""
Telemetry Routes Module

Provides FastAPI router implementations for the Environment Telemetry 
& Health Monitoring Engine. Implements RESTful API endpoints with
comprehensive OpenAPI documentation, JWT authentication, and error handling.

Key Routes:
- /telemetry/heartbeat: Agent heartbeat ingestion with health assessment
- /telemetry/system-metrics: System performance metrics recording
- /telemetry/uptime-status: Uptime analysis and SLA compliance reporting
- /telemetry/health-check: Comprehensive health assessment for agents/systems
- /telemetry/batch: High-throughput batch telemetry ingestion

All routes follow FastAPI patterns with:
- JWT-based authentication via Depends()
- Pydantic request/response validation with examples
- Comprehensive OpenAPI documentation and Swagger integration
- Structured error handling with appropriate HTTP status codes
- Clean separation from business logic (delegated to controllers)
"""

from .telemetry_routes import router

__all__ = [
    "router",
] 
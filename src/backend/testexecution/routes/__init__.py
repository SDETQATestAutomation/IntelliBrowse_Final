"""
Test Execution Engine - Routes Package

Provides FastAPI route definitions for the Test Execution Engine including:
- Execution lifecycle management endpoints
- Real-time execution monitoring and WebSocket support
- Queue management and control endpoints
- Result retrieval and reporting endpoints
- Health checks and system status endpoints

All routes follow REST API conventions with comprehensive OpenAPI documentation,
authentication requirements, and proper error handling.
"""

from .execution_routes import router as execution_router

__all__ = [
    "execution_router"
] 
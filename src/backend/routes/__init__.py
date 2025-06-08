"""
Backend Routes Package

Central router registration for all backend API modules.
Provides a consolidated entry point for FastAPI route inclusion.
"""

from fastapi import APIRouter
from ..executionreporting.routes import router as execution_reporting_router
from ..telemetry.routes import router as telemetry_router

# Create main API router
api_router = APIRouter()

# Include module routers
api_router.include_router(
    execution_reporting_router,
    prefix="/api/v1",
    tags=["Execution Reporting"]
)

api_router.include_router(
    telemetry_router,
    prefix="/api/v1",
    tags=["Telemetry"]
)

__all__ = ["api_router"]

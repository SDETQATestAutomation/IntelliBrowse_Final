"""
Health routes for IntelliBrowse backend.
Defines health check endpoints with proper FastAPI routing.
"""

from typing import Union

from fastapi import APIRouter, status

from ..config.constants import HEALTH_CHECK_ENDPOINT
from ..controllers.health_controller import HealthController
from ..schemas.response import HealthResponse, ErrorResponse

# Create router for health endpoints
router = APIRouter(
    prefix="",  # No prefix since health is at root level
    tags=["Health"],
    responses={
        404: {"description": "Not found"},
        500: {"description": "Internal server error"},
    },
)

# Initialize health controller
health_controller = HealthController()


@router.get(
    HEALTH_CHECK_ENDPOINT,
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="System Health Check",
    description="Get comprehensive system health status including resource usage and component checks",
    responses={
        200: {
            "description": "Health check completed successfully",
            "model": HealthResponse,
        },
        503: {
            "description": "System is unhealthy or degraded",
            "model": ErrorResponse,
        },
    },
)
async def get_health() -> Union[HealthResponse, ErrorResponse]:
    """
    Get comprehensive system health status.
    
    This endpoint performs detailed health checks including:
    - System resource usage (CPU, memory, disk)
    - Application configuration validation
    - Logging system status
    - Component health verification
    
    Returns:
        HealthResponse: Comprehensive health status with detailed checks
        ErrorResponse: If health check fails
    """
    return await health_controller.get_health_status()


@router.get(
    "/health/basic",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Basic Health Check",
    description="Get basic system health status for simple liveness checks",
    responses={
        200: {
            "description": "Basic health check completed successfully",
            "model": HealthResponse,
        },
        503: {
            "description": "System is unhealthy",
            "model": ErrorResponse,
        },
    },
)
async def get_basic_health() -> Union[HealthResponse, ErrorResponse]:
    """
    Get basic system health status.
    
    This endpoint provides a lightweight health check suitable for:
    - Load balancer health checks
    - Container orchestration liveness probes
    - Simple monitoring systems
    
    Returns:
        HealthResponse: Basic health status without detailed checks
        ErrorResponse: If basic health check fails
    """
    return await health_controller.get_basic_health_status()


@router.get(
    "/health/metrics",
    status_code=status.HTTP_200_OK,
    summary="Health Metrics",
    description="Get detailed health metrics for monitoring and alerting systems",
    responses={
        200: {
            "description": "Health metrics retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "uptime_seconds": 3600.0,
                        "version": "1.0.0",
                        "environment": "development",
                        "timestamp": "2024-05-31T10:00:00.000Z",
                        "checks": {
                            "memory": {"status": "healthy", "usage_percent": 45.2},
                            "disk": {"status": "healthy", "usage_percent": 65.8},
                            "cpu": {"status": "healthy", "usage_percent": 12.3}
                        },
                        "summary": {
                            "total_checks": 5,
                            "healthy_checks": 5,
                            "health_percentage": 100.0
                        }
                    }
                }
            }
        },
        503: {
            "description": "Metrics retrieval failed",
            "model": ErrorResponse,
        },
    },
)
async def get_health_metrics() -> Union[dict, ErrorResponse]:
    """
    Get detailed health metrics.
    
    This endpoint provides structured health metrics suitable for:
    - Monitoring system integration (Prometheus, Grafana)
    - Alerting systems
    - Performance tracking
    - System observability
    
    Returns:
        dict: Detailed health metrics with summary statistics
        ErrorResponse: If metrics retrieval fails
    """
    return await health_controller.get_health_metrics()


@router.get(
    "/ping",
    status_code=status.HTTP_200_OK,
    summary="Simple Ping",
    description="Simple ping endpoint for basic connectivity testing",
    responses={
        200: {
            "description": "Pong response",
            "content": {
                "application/json": {
                    "example": {"message": "pong"}
                }
            }
        }
    },
)
async def ping():
    """
    Simple ping endpoint.
    
    This endpoint provides the most basic connectivity check.
    Useful for:
    - Network connectivity testing
    - Basic service availability checks
    - Load balancer simple health checks
    
    Returns:
        dict: Simple pong response
    """
    return {"message": "pong"} 
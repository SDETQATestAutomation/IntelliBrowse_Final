"""
Health controller for IntelliBrowse backend.
Handles health check requests and coordinates with the health service.
"""

from typing import Union

from fastapi import HTTPException

from ..config.logging import get_logger
from ..schemas.response import HealthResponse, ErrorResponse, create_health_response, create_error_response
from ..services.health_service import HealthService

logger = get_logger(__name__)


class HealthController:
    """
    Controller for health check endpoints.
    Handles HTTP requests and delegates to the health service.
    """

    def __init__(self):
        self.health_service = HealthService()

    async def get_health_status(self) -> Union[HealthResponse, ErrorResponse]:
        """
        Get comprehensive system health status.
        
        Returns:
            HealthResponse with system status and checks
            
        Raises:
            HTTPException: If health check fails critically
        """
        try:
            logger.info("Health check requested")
            
            # Get health data from service
            health_data = await self.health_service.get_system_health()
            
            # Create structured response
            response = create_health_response(
                status=health_data["status"],
                uptime_seconds=health_data["uptime_seconds"],
                version=health_data["version"],
                environment=health_data["environment"],
                message=health_data["message"],
                checks=health_data.get("checks")
            )
            
            logger.info(f"Health check completed successfully - Status: {health_data['status']}")
            return response
            
        except Exception as e:
            logger.error(f"Health check controller error: {str(e)}")
            
            # For health checks, we typically don't want to return 500 errors
            # Instead, return a structured unhealthy response
            error_response = create_error_response(
                message="Health check failed",
                error_code="HEALTH_CHECK_ERROR",
                error_details={"error": str(e)}
            )
            
            return error_response

    async def get_basic_health_status(self) -> Union[HealthResponse, ErrorResponse]:
        """
        Get basic health status for simple liveness checks.
        
        Returns:
            HealthResponse with basic status information
        """
        try:
            logger.debug("Basic health check requested")
            
            # Get basic health data from service
            health_data = await self.health_service.get_basic_health()
            
            # Create structured response
            response = create_health_response(
                status=health_data["status"],
                uptime_seconds=health_data["uptime_seconds"],
                version=health_data["version"],
                environment=health_data["environment"],
                message=health_data["message"]
            )
            
            logger.debug("Basic health check completed successfully")
            return response
            
        except Exception as e:
            logger.error(f"Basic health check controller error: {str(e)}")
            
            error_response = create_error_response(
                message="Basic health check failed",
                error_code="BASIC_HEALTH_CHECK_ERROR",
                error_details={"error": str(e)}
            )
            
            return error_response

    async def get_health_metrics(self) -> Union[dict, ErrorResponse]:
        """
        Get detailed health metrics for monitoring systems.
        
        Returns:
            Dictionary with detailed system metrics
        """
        try:
            logger.debug("Health metrics requested")
            
            # Get comprehensive health data
            health_data = await self.health_service.get_system_health()
            
            # Extract metrics for monitoring
            metrics = {
                "status": health_data["status"],
                "uptime_seconds": health_data["uptime_seconds"],
                "version": health_data["version"],
                "environment": health_data["environment"],
                "timestamp": health_data.get("timestamp"),
                "checks": health_data.get("checks", {}),
            }
            
            # Add summary statistics
            if "checks" in health_data:
                checks = health_data["checks"]
                healthy_count = sum(1 for check in checks.values() 
                                  if isinstance(check, dict) and check.get("status") == "healthy")
                total_checks = len(checks)
                
                metrics["summary"] = {
                    "total_checks": total_checks,
                    "healthy_checks": healthy_count,
                    "health_percentage": (healthy_count / total_checks * 100) if total_checks > 0 else 0
                }
            
            logger.debug("Health metrics retrieved successfully")
            return metrics
            
        except Exception as e:
            logger.error(f"Health metrics controller error: {str(e)}")
            
            error_response = create_error_response(
                message="Health metrics retrieval failed",
                error_code="HEALTH_METRICS_ERROR",
                error_details={"error": str(e)}
            )
            
            return error_response 
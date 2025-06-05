"""
Health service for IntelliBrowse backend.
Implements business logic for system health checks and monitoring.
"""

import time
import psutil
from typing import Dict, Any

from ..config.constants import (
    SYSTEM_STATUS_HEALTHY,
    SYSTEM_STATUS_DEGRADED,
    SYSTEM_STATUS_UNHEALTHY,
    HEALTH_MESSAGE_RUNNING,
    HEALTH_MESSAGE_DEGRADED,
    HEALTH_MESSAGE_UNHEALTHY,
)
from ..config.env import get_settings
from ..config.logging import get_logger

logger = get_logger(__name__)

# Track application start time
_app_start_time = time.time()


class HealthService:
    """
    Service for performing health checks and system monitoring.
    """

    def __init__(self):
        self.settings = get_settings()

    async def get_system_health(self) -> Dict[str, Any]:
        """
        Perform comprehensive system health check.
        
        Returns:
            Dictionary containing health status and system information
        """
        logger.info("Performing system health check")
        
        try:
            # Calculate uptime
            uptime_seconds = time.time() - _app_start_time
            
            # Perform individual checks
            checks = await self._perform_health_checks()
            
            # Determine overall status
            overall_status = self._determine_overall_status(checks)
            
            # Get appropriate message
            message = self._get_status_message(overall_status)
            
            health_data = {
                "status": overall_status,
                "uptime_seconds": uptime_seconds,
                "version": self.settings.app_version,
                "environment": self.settings.environment,
                "message": message,
                "checks": checks,
            }
            
            logger.info(f"Health check completed - Status: {overall_status}")
            return health_data
            
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {
                "status": SYSTEM_STATUS_UNHEALTHY,
                "uptime_seconds": time.time() - _app_start_time,
                "version": self.settings.app_version,
                "environment": self.settings.environment,
                "message": HEALTH_MESSAGE_UNHEALTHY,
                "checks": {"error": str(e)},
            }

    async def _perform_health_checks(self) -> Dict[str, Any]:
        """
        Perform individual component health checks.
        
        Returns:
            Dictionary of check results
        """
        checks = {}
        
        # System resource checks
        checks["memory"] = await self._check_memory_usage()
        checks["disk"] = await self._check_disk_usage()
        checks["cpu"] = await self._check_cpu_usage()
        
        # Application checks
        checks["configuration"] = await self._check_configuration()
        checks["logging"] = await self._check_logging()
        
        # Future checks can be added here
        # checks["database"] = await self._check_database()
        # checks["external_services"] = await self._check_external_services()
        
        return checks

    async def _check_memory_usage(self) -> Dict[str, Any]:
        """Check system memory usage."""
        try:
            memory = psutil.virtual_memory()
            memory_check = {
                "status": SYSTEM_STATUS_HEALTHY,
                "usage_percent": memory.percent,
                "available_gb": round(memory.available / (1024**3), 2),
                "total_gb": round(memory.total / (1024**3), 2),
            }
            
            # Mark as degraded if memory usage is high
            if memory.percent > 85:
                memory_check["status"] = SYSTEM_STATUS_DEGRADED
                memory_check["warning"] = "High memory usage detected"
            elif memory.percent > 95:
                memory_check["status"] = SYSTEM_STATUS_UNHEALTHY
                memory_check["error"] = "Critical memory usage"
                
            return memory_check
            
        except Exception as e:
            return {
                "status": SYSTEM_STATUS_UNHEALTHY,
                "error": f"Memory check failed: {str(e)}"
            }

    async def _check_disk_usage(self) -> Dict[str, Any]:
        """Check disk usage for the current directory."""
        try:
            disk = psutil.disk_usage('/')
            disk_check = {
                "status": SYSTEM_STATUS_HEALTHY,
                "usage_percent": (disk.used / disk.total) * 100,
                "free_gb": round(disk.free / (1024**3), 2),
                "total_gb": round(disk.total / (1024**3), 2),
            }
            
            # Mark as degraded if disk usage is high
            usage_percent = disk_check["usage_percent"]
            if usage_percent > 85:
                disk_check["status"] = SYSTEM_STATUS_DEGRADED
                disk_check["warning"] = "High disk usage detected"
            elif usage_percent > 95:
                disk_check["status"] = SYSTEM_STATUS_UNHEALTHY
                disk_check["error"] = "Critical disk usage"
                
            return disk_check
            
        except Exception as e:
            return {
                "status": SYSTEM_STATUS_UNHEALTHY,
                "error": f"Disk check failed: {str(e)}"
            }

    async def _check_cpu_usage(self) -> Dict[str, Any]:
        """Check CPU usage."""
        try:
            # Get CPU usage over a short interval
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_check = {
                "status": SYSTEM_STATUS_HEALTHY,
                "usage_percent": cpu_percent,
                "cpu_count": psutil.cpu_count(),
            }
            
            # Mark as degraded if CPU usage is consistently high
            if cpu_percent > 80:
                cpu_check["status"] = SYSTEM_STATUS_DEGRADED
                cpu_check["warning"] = "High CPU usage detected"
            elif cpu_percent > 95:
                cpu_check["status"] = SYSTEM_STATUS_UNHEALTHY
                cpu_check["error"] = "Critical CPU usage"
                
            return cpu_check
            
        except Exception as e:
            return {
                "status": SYSTEM_STATUS_UNHEALTHY,
                "error": f"CPU check failed: {str(e)}"
            }

    async def _check_configuration(self) -> Dict[str, Any]:
        """Check configuration validity."""
        try:
            config_check = {
                "status": SYSTEM_STATUS_HEALTHY,
                "app_name": self.settings.app_name,
                "debug_mode": self.settings.debug,
                "environment": self.settings.environment,
            }
            
            # Check for potential configuration issues
            if self.settings.secret_key == "your-secret-key-here-change-in-production":
                if self.settings.is_production():
                    config_check["status"] = SYSTEM_STATUS_UNHEALTHY
                    config_check["error"] = "Default secret key in production"
                else:
                    config_check["status"] = SYSTEM_STATUS_DEGRADED
                    config_check["warning"] = "Using default secret key"
                    
            return config_check
            
        except Exception as e:
            return {
                "status": SYSTEM_STATUS_UNHEALTHY,
                "error": f"Configuration check failed: {str(e)}"
            }

    async def _check_logging(self) -> Dict[str, Any]:
        """Check logging system status."""
        try:
            logging_check = {
                "status": SYSTEM_STATUS_HEALTHY,
                "log_level": self.settings.log_level,
                "file_logging": self.settings.log_to_file,
            }
            
            if self.settings.log_to_file:
                logging_check["log_file"] = self.settings.log_file_path
                
            return logging_check
            
        except Exception as e:
            return {
                "status": SYSTEM_STATUS_UNHEALTHY,
                "error": f"Logging check failed: {str(e)}"
            }

    def _determine_overall_status(self, checks: Dict[str, Any]) -> str:
        """
        Determine overall system status based on individual checks.
        
        Args:
            checks: Dictionary of individual check results
            
        Returns:
            Overall system status
        """
        statuses = []
        
        for check_name, check_data in checks.items():
            if isinstance(check_data, dict) and "status" in check_data:
                statuses.append(check_data["status"])
        
        # If any check is unhealthy, overall status is unhealthy
        if SYSTEM_STATUS_UNHEALTHY in statuses:
            return SYSTEM_STATUS_UNHEALTHY
            
        # If any check is degraded, overall status is degraded
        if SYSTEM_STATUS_DEGRADED in statuses:
            return SYSTEM_STATUS_DEGRADED
            
        # Otherwise, system is healthy
        return SYSTEM_STATUS_HEALTHY

    def _get_status_message(self, status: str) -> str:
        """
        Get appropriate message for the given status.
        
        Args:
            status: System status
            
        Returns:
            Status message
        """
        if status == SYSTEM_STATUS_HEALTHY:
            return HEALTH_MESSAGE_RUNNING
        elif status == SYSTEM_STATUS_DEGRADED:
            return HEALTH_MESSAGE_DEGRADED
        else:
            return HEALTH_MESSAGE_UNHEALTHY

    async def get_basic_health(self) -> Dict[str, Any]:
        """
        Get basic health information without detailed checks.
        Useful for simple liveness probes.
        
        Returns:
            Basic health information
        """
        uptime_seconds = time.time() - _app_start_time
        
        return {
            "status": SYSTEM_STATUS_HEALTHY,
            "uptime_seconds": uptime_seconds,
            "version": self.settings.app_version,
            "environment": self.settings.environment,
            "message": HEALTH_MESSAGE_RUNNING,
        } 
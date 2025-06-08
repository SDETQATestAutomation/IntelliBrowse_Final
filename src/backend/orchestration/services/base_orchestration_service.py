"""
Base Orchestration Service

Provides the foundation service interface for all orchestration services
with dependency injection, configuration management, error handling,
and structured logging patterns.
"""

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, TypeVar, Generic, Type, Callable
from dataclasses import dataclass
from enum import Enum

from ...config.env import get_settings
from ...config.logging import get_logger
from ..models.orchestration_models import (
    OrchestrationException,
    JobStatus,
    RetryStrategy,
)

logger = get_logger(__name__)

T = TypeVar('T')


class ServiceLifecycle(str, Enum):
    """Service lifecycle states."""
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class ServiceDependency:
    """Service dependency configuration."""
    name: str
    service_type: Type
    required: bool = True
    lazy_load: bool = False
    timeout_seconds: int = 30


@dataclass
class ServiceConfiguration:
    """Service configuration parameters."""
    service_name: str
    enable_metrics: bool = True
    enable_health_checks: bool = True
    heartbeat_interval_seconds: int = 30
    operation_timeout_seconds: int = 300
    max_concurrent_operations: int = 100
    retry_attempts: int = 3
    circuit_breaker_enabled: bool = True


class BaseOrchestrationService(ABC, Generic[T]):
    """
    Base service class providing common functionality for all orchestration services.
    
    Features:
    - Dependency injection framework
    - Configuration management
    - Health monitoring
    - Error handling and recovery
    - Structured logging with correlation tracking
    - Circuit breaker pattern
    - Metrics collection
    """
    
    def __init__(self, config: Optional[ServiceConfiguration] = None):
        """Initialize the base service with configuration."""
        self._config = config or ServiceConfiguration(service_name=self.__class__.__name__)
        self._settings = get_settings()
        self._logger = get_logger(self.__class__.__name__)
        
        # Service state
        self._lifecycle_state = ServiceLifecycle.INITIALIZING
        self._dependencies: Dict[str, Any] = {}
        self._health_status: Dict[str, Any] = {}
        self._metrics: Dict[str, Any] = {}
        self._circuit_breaker_state: Dict[str, Any] = {}
        
        # Operation tracking
        self._active_operations: Dict[str, Dict[str, Any]] = {}
        self._operation_semaphore = asyncio.Semaphore(self._config.max_concurrent_operations)
        
        # Health monitoring
        self._last_heartbeat = datetime.now(timezone.utc)
        self._heartbeat_task: Optional[asyncio.Task] = None
        
        self._logger.info(f"Initializing {self._config.service_name} service")
    
    @property
    def service_name(self) -> str:
        """Get the service name."""
        return self._config.service_name
    
    @property
    def lifecycle_state(self) -> ServiceLifecycle:
        """Get the current lifecycle state."""
        return self._lifecycle_state
    
    @property
    def is_healthy(self) -> bool:
        """Check if the service is healthy."""
        return self._lifecycle_state in [ServiceLifecycle.READY, ServiceLifecycle.RUNNING]
    
    @property
    def health_status(self) -> Dict[str, Any]:
        """Get detailed health status."""
        return {
            "service_name": self.service_name,
            "lifecycle_state": self._lifecycle_state.value,
            "last_heartbeat": self._last_heartbeat.isoformat(),
            "active_operations": len(self._active_operations),
            "health_checks": self._health_status,
            "metrics": self._metrics if self._config.enable_metrics else {},
            "dependencies": {
                name: "available" if dep else "unavailable"
                for name, dep in self._dependencies.items()
            }
        }
    
    async def initialize(self) -> None:
        """Initialize the service and its dependencies."""
        try:
            self._lifecycle_state = ServiceLifecycle.INITIALIZING
            self._logger.info(f"Initializing {self.service_name} service")
            
            # Initialize dependencies
            await self._initialize_dependencies()
            
            # Perform service-specific initialization
            await self._initialize_service()
            
            # Start health monitoring if enabled
            if self._config.enable_health_checks:
                await self._start_health_monitoring()
            
            self._lifecycle_state = ServiceLifecycle.READY
            self._logger.info(f"{self.service_name} service initialized successfully")
            
        except Exception as e:
            self._lifecycle_state = ServiceLifecycle.ERROR
            self._logger.error(f"Failed to initialize {self.service_name} service: {e}")
            raise OrchestrationException(f"Service initialization failed: {e}")
    
    async def start(self) -> None:
        """Start the service."""
        if self._lifecycle_state != ServiceLifecycle.READY:
            raise OrchestrationException(f"Cannot start service in state {self._lifecycle_state}")
        
        try:
            self._lifecycle_state = ServiceLifecycle.RUNNING
            await self._start_service()
            self._logger.info(f"{self.service_name} service started")
            
        except Exception as e:
            self._lifecycle_state = ServiceLifecycle.ERROR
            self._logger.error(f"Failed to start {self.service_name} service: {e}")
            raise
    
    async def stop(self) -> None:
        """Stop the service gracefully."""
        if self._lifecycle_state == ServiceLifecycle.STOPPED:
            return
        
        try:
            self._lifecycle_state = ServiceLifecycle.STOPPING
            self._logger.info(f"Stopping {self.service_name} service")
            
            # Cancel heartbeat monitoring
            if self._heartbeat_task:
                self._heartbeat_task.cancel()
                try:
                    await self._heartbeat_task
                except asyncio.CancelledError:
                    pass
            
            # Wait for active operations to complete or timeout
            await self._wait_for_operations_completion()
            
            # Perform service-specific cleanup
            await self._stop_service()
            
            self._lifecycle_state = ServiceLifecycle.STOPPED
            self._logger.info(f"{self.service_name} service stopped")
            
        except Exception as e:
            self._lifecycle_state = ServiceLifecycle.ERROR
            self._logger.error(f"Error stopping {self.service_name} service: {e}")
            raise
    
    async def execute_operation(
        self,
        operation_id: str,
        operation: Callable[[], Any],
        timeout_seconds: Optional[int] = None,
        correlation_id: Optional[str] = None
    ) -> Any:
        """Execute an operation with tracking, timeout, and error handling."""
        timeout = timeout_seconds or self._config.operation_timeout_seconds
        
        async with self._operation_semaphore:
            operation_start = datetime.now(timezone.utc)
            
            # Track operation
            self._active_operations[operation_id] = {
                "operation_id": operation_id,
                "correlation_id": correlation_id,
                "started_at": operation_start,
                "timeout_seconds": timeout
            }
            
            try:
                self._logger.info(f"Starting operation {operation_id}", extra={
                    "operation_id": operation_id,
                    "correlation_id": correlation_id,
                    "service_name": self.service_name
                })
                
                # Execute with timeout
                result = await asyncio.wait_for(operation(), timeout=timeout)
                
                # Update metrics
                duration = (datetime.now(timezone.utc) - operation_start).total_seconds()
                self._update_operation_metrics(operation_id, duration, True)
                
                self._logger.info(f"Completed operation {operation_id}", extra={
                    "operation_id": operation_id,
                    "correlation_id": correlation_id,
                    "duration_seconds": duration
                })
                
                return result
                
            except asyncio.TimeoutError:
                self._logger.error(f"Operation {operation_id} timed out after {timeout}s", extra={
                    "operation_id": operation_id,
                    "correlation_id": correlation_id,
                    "timeout_seconds": timeout
                })
                self._update_operation_metrics(operation_id, timeout, False, "timeout")
                raise OrchestrationException(f"Operation {operation_id} timed out")
                
            except Exception as e:
                duration = (datetime.now(timezone.utc) - operation_start).total_seconds()
                self._logger.error(f"Operation {operation_id} failed: {e}", extra={
                    "operation_id": operation_id,
                    "correlation_id": correlation_id,
                    "error": str(e),
                    "duration_seconds": duration
                })
                self._update_operation_metrics(operation_id, duration, False, "error")
                raise
                
            finally:
                # Clean up operation tracking
                self._active_operations.pop(operation_id, None)
    
    def register_dependency(self, dependency: ServiceDependency, service_instance: Any) -> None:
        """Register a service dependency."""
        self._dependencies[dependency.name] = service_instance
        self._logger.debug(f"Registered dependency {dependency.name}")
    
    def get_dependency(self, name: str) -> Optional[Any]:
        """Get a registered dependency."""
        return self._dependencies.get(name)
    
    def require_dependency(self, name: str) -> Any:
        """Get a required dependency or raise exception."""
        dependency = self._dependencies.get(name)
        if dependency is None:
            raise OrchestrationException(f"Required dependency {name} not available")
        return dependency
    
    # Abstract methods for service-specific implementation
    @abstractmethod
    async def _initialize_service(self) -> None:
        """Initialize service-specific components."""
        pass
    
    @abstractmethod
    async def _start_service(self) -> None:
        """Start service-specific components."""
        pass
    
    @abstractmethod
    async def _stop_service(self) -> None:
        """Stop service-specific components."""
        pass
    
    @abstractmethod
    async def _health_check(self) -> Dict[str, Any]:
        """Perform service-specific health checks."""
        pass
    
    # Internal methods
    async def _initialize_dependencies(self) -> None:
        """Initialize registered dependencies."""
        for name, dependency in self._dependencies.items():
            if hasattr(dependency, 'initialize'):
                try:
                    await dependency.initialize()
                    self._logger.debug(f"Initialized dependency {name}")
                except Exception as e:
                    self._logger.error(f"Failed to initialize dependency {name}: {e}")
                    raise
    
    async def _start_health_monitoring(self) -> None:
        """Start health monitoring task."""
        if self._config.enable_health_checks:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
    
    async def _heartbeat_loop(self) -> None:
        """Health monitoring heartbeat loop."""
        while self._lifecycle_state in [ServiceLifecycle.READY, ServiceLifecycle.RUNNING]:
            try:
                # Update heartbeat timestamp
                self._last_heartbeat = datetime.now(timezone.utc)
                
                # Perform health checks
                health_result = await self._health_check()
                self._health_status.update(health_result)
                
                # Wait for next heartbeat
                await asyncio.sleep(self._config.heartbeat_interval_seconds)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Health check failed: {e}")
                await asyncio.sleep(self._config.heartbeat_interval_seconds)
    
    async def _wait_for_operations_completion(self) -> None:
        """Wait for active operations to complete with timeout."""
        if not self._active_operations:
            return
        
        self._logger.info(f"Waiting for {len(self._active_operations)} operations to complete")
        
        # Wait up to 30 seconds for operations to complete
        timeout = 30
        start_time = datetime.now(timezone.utc)
        
        while self._active_operations and (datetime.now(timezone.utc) - start_time).total_seconds() < timeout:
            await asyncio.sleep(1)
        
        if self._active_operations:
            self._logger.warning(f"Forcing shutdown with {len(self._active_operations)} operations still active")
    
    def _update_operation_metrics(
        self,
        operation_id: str,
        duration_seconds: float,
        success: bool,
        error_type: Optional[str] = None
    ) -> None:
        """Update operation metrics."""
        if not self._config.enable_metrics:
            return
        
        metrics = self._metrics.setdefault("operations", {
            "total_count": 0,
            "success_count": 0,
            "failure_count": 0,
            "total_duration": 0.0,
            "average_duration": 0.0,
            "error_types": {}
        })
        
        metrics["total_count"] += 1
        metrics["total_duration"] += duration_seconds
        metrics["average_duration"] = metrics["total_duration"] / metrics["total_count"]
        
        if success:
            metrics["success_count"] += 1
        else:
            metrics["failure_count"] += 1
            if error_type:
                metrics["error_types"][error_type] = metrics["error_types"].get(error_type, 0) + 1
    
    def _bind_logger_context(self, **kwargs) -> Any:
        """Bind additional context to logger."""
        return self._logger.bind(
            service_name=self.service_name,
            lifecycle_state=self._lifecycle_state.value,
            **kwargs
        ) 
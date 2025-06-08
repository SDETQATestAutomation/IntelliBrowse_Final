"""
Scheduled Task Runner Engine - Base Service Interfaces

Implements abstract base classes and service interfaces for the scheduler module.
Defines contracts for trigger resolution, lock management, and job execution
with comprehensive error handling and logging placeholders.

Key Interfaces:
- BaseSchedulerService: Core scheduling operations interface
- TriggerEngineService: Trigger resolution and queue management
- LockManagerService: Distributed locking with TTL support  
- JobExecutionService: Job lifecycle and execution tracking

Architecture Notes:
- Based on creative phase decisions: Hybrid Priority Queue + MongoDB TTL Locking
- Designed for Phase 2 implementation with clear extension points
- Full async/await patterns with structured logging
- Type-safe interfaces with comprehensive error contracts
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple
import asyncio
from contextlib import asynccontextmanager

from ...config.logging import get_logger
from ..models.trigger_model import (
    ScheduledTriggerModel, 
    ScheduledJobModel, 
    ExecutionLockModel,
    TaskStatus, 
    ExecutionStatus, 
    TriggerType
)
from ..schemas.trigger_schemas import (
    CreateScheduledTriggerRequest,
    UpdateScheduledTriggerRequest,
    LockAcquisitionRequest
)

logger = get_logger(__name__)


class SchedulerServiceException(Exception):
    """Base exception for scheduler service operations"""
    
    def __init__(self, message: str, service_name: str = None, operation: str = None, 
                 error_code: str = None, context: Dict[str, Any] = None):
        super().__init__(message)
        self.message = message
        self.service_name = service_name
        self.operation = operation
        self.error_code = error_code
        self.context = context or {}
        self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/API responses"""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "service_name": self.service_name,
            "operation": self.operation,
            "error_code": self.error_code,
            "context": self.context,
            "timestamp": self.timestamp.isoformat()
        }


class TriggerResolutionError(SchedulerServiceException):
    """Exception for trigger resolution failures"""
    
    def __init__(self, message: str, trigger_id: str = None, trigger_type: str = None):
        super().__init__(
            message, 
            service_name="TriggerEngineService",
            operation="trigger_resolution",
            error_code="TRIGGER_RESOLUTION_FAILED"
        )
        self.trigger_id = trigger_id
        self.trigger_type = trigger_type


class LockManagerError(SchedulerServiceException):
    """Exception for lock management failures"""
    
    def __init__(self, message: str, lock_id: str = None, resource_id: str = None):
        super().__init__(
            message,
            service_name="LockManagerService", 
            operation="lock_management",
            error_code="LOCK_OPERATION_FAILED"
        )
        self.lock_id = lock_id
        self.resource_id = resource_id


class BaseSchedulerService(ABC):
    """
    Abstract base class for core scheduler service operations.
    
    Defines the fundamental interface for scheduled task management including
    trigger creation, job execution tracking, and system health monitoring.
    Designed for extension in Phase 2 with full implementation logic.
    """
    
    def __init__(self, logger_name: str = None):
        """Initialize base scheduler service"""
        self.logger = get_logger(logger_name or self.__class__.__name__)
        self._initialized = False
        self._health_status = "unknown"
        
    async def initialize(self) -> bool:
        """
        Initialize the scheduler service.
        
        Returns:
            bool: True if initialization successful
            
        Raises:
            SchedulerServiceException: If initialization fails
        """
        try:
            self.logger.info("Initializing scheduler service", extra={
                "service": self.__class__.__name__,
                "operation": "initialize"
            })
            
            # Phase 2 TODO: Implement database connections, queue setup, etc.
            success = await self._perform_initialization()
            
            if success:
                self._initialized = True
                self._health_status = "healthy"
                self.logger.info("Scheduler service initialized successfully")
            else:
                self._health_status = "failed"
                self.logger.error("Scheduler service initialization failed")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Scheduler service initialization error: {e}", exc_info=True)
            self._health_status = "error"
            raise SchedulerServiceException(
                f"Service initialization failed: {e}",
                service_name=self.__class__.__name__,
                operation="initialize"
            )
    
    @abstractmethod
    async def _perform_initialization(self) -> bool:
        """Perform service-specific initialization logic"""
        pass
    
    async def shutdown(self) -> bool:
        """
        Gracefully shutdown the scheduler service.
        
        Returns:
            bool: True if shutdown successful
        """
        try:
            self.logger.info("Shutting down scheduler service")
            
            # Phase 2 TODO: Implement graceful shutdown logic
            success = await self._perform_shutdown()
            
            if success:
                self._initialized = False
                self._health_status = "shutdown"
                self.logger.info("Scheduler service shutdown completed")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Scheduler service shutdown error: {e}", exc_info=True)
            return False
    
    @abstractmethod
    async def _perform_shutdown(self) -> bool:
        """Perform service-specific shutdown logic"""
        pass
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check service health status.
        
        Returns:
            Dict containing health status and metrics
        """
        health_data = {
            "service": self.__class__.__name__,
            "status": self._health_status,
            "initialized": self._initialized,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Phase 2 TODO: Add detailed health metrics
        try:
            detailed_health = await self._check_detailed_health()
            health_data.update(detailed_health)
        except Exception as e:
            self.logger.warning(f"Detailed health check failed: {e}")
            health_data["detailed_check"] = "failed"
        
        return health_data
    
    @abstractmethod
    async def _check_detailed_health(self) -> Dict[str, Any]:
        """Perform detailed health checks specific to service implementation"""
        pass


class TriggerEngineService(BaseSchedulerService):
    """
    Service interface for trigger engine operations.
    
    Implements trigger resolution, queue management, and execution scheduling
    based on the creative phase decision: Hybrid Priority Queue with Database Persistence.
    Handles cron expressions, event-driven triggers, and dependency resolution.
    """
    
    def __init__(self):
        super().__init__("TriggerEngineService")
        self._priority_queue_size = 0
        self._active_triggers = 0
    
    async def _perform_initialization(self) -> bool:
        """Initialize trigger engine components"""
        try:
            # Phase 2 TODO: Initialize priority queue, cron parser, database connections
            self.logger.info("Initializing trigger engine components")
            
            # Placeholder for trigger engine initialization
            self._priority_queue_size = 0
            self._active_triggers = 0
            
            return True
        except Exception as e:
            self.logger.error(f"Trigger engine initialization failed: {e}")
            return False
    
    async def _perform_shutdown(self) -> bool:
        """Shutdown trigger engine components"""
        try:
            # Phase 2 TODO: Gracefully shutdown queue processing, save state
            self.logger.info("Shutting down trigger engine")
            return True
        except Exception as e:
            self.logger.error(f"Trigger engine shutdown failed: {e}")
            return False
    
    async def _check_detailed_health(self) -> Dict[str, Any]:
        """Check trigger engine specific health metrics"""
        return {
            "priority_queue_size": self._priority_queue_size,
            "active_triggers": self._active_triggers,
            "queue_processing": "healthy",  # Phase 2: Real queue health check
            "cron_parser": "healthy"        # Phase 2: Real cron parser health check
        }
    
    @abstractmethod
    async def resolve_next_trigger(self, max_count: int = 10) -> List[ScheduledTriggerModel]:
        """
        Resolve next triggers ready for execution.
        
        Args:
            max_count: Maximum number of triggers to resolve
            
        Returns:
            List of triggers ready for execution
            
        Raises:
            TriggerResolutionError: If trigger resolution fails
        """
        self.logger.info(f"Resolving next triggers (max_count={max_count})")
        
        # Phase 2 TODO: Implement hybrid priority queue logic
        # 1. Check in-memory priority queue for immediate triggers
        # 2. Load from database for scheduled triggers approaching execution time
        # 3. Evaluate conditional and dependency-based triggers
        # 4. Return sorted list by priority and execution time
        
        try:
            triggers = await self._resolve_triggers_from_queue(max_count)
            
            self.logger.info(f"Resolved {len(triggers)} triggers for execution")
            return triggers
            
        except Exception as e:
            self.logger.error(f"Trigger resolution failed: {e}", exc_info=True)
            raise TriggerResolutionError(f"Failed to resolve triggers: {e}")
    
    @abstractmethod
    async def _resolve_triggers_from_queue(self, max_count: int) -> List[ScheduledTriggerModel]:
        """Implementation-specific trigger resolution logic"""
        pass
    
    @abstractmethod
    async def schedule_trigger(self, trigger: ScheduledTriggerModel) -> bool:
        """
        Schedule a trigger for future execution.
        
        Args:
            trigger: Trigger model to schedule
            
        Returns:
            bool: True if scheduling successful
            
        Raises:
            TriggerResolutionError: If scheduling fails
        """
        self.logger.info(f"Scheduling trigger {trigger.trigger_id}")
        
        # Phase 2 TODO: Implement trigger scheduling logic
        # 1. Parse cron expression and calculate next execution time
        # 2. Add to priority queue if execution is soon
        # 3. Store in database with indexed next_execution field
        # 4. Handle event-driven and dependency triggers appropriately
        
        try:
            success = await self._add_trigger_to_schedule(trigger)
            
            if success:
                self.logger.info(f"Trigger {trigger.trigger_id} scheduled successfully")
                self._active_triggers += 1
            else:
                self.logger.warning(f"Failed to schedule trigger {trigger.trigger_id}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Trigger scheduling failed: {e}", exc_info=True)
            raise TriggerResolutionError(f"Failed to schedule trigger: {e}")
    
    @abstractmethod
    async def _add_trigger_to_schedule(self, trigger: ScheduledTriggerModel) -> bool:
        """Implementation-specific trigger scheduling logic"""
        pass
    
    @abstractmethod
    async def update_trigger_schedule(self, trigger_id: str, next_execution: datetime) -> bool:
        """
        Update trigger's next execution time.
        
        Args:
            trigger_id: ID of trigger to update
            next_execution: New next execution time
            
        Returns:
            bool: True if update successful
        """
        self.logger.info(f"Updating trigger {trigger_id} next execution to {next_execution}")
        
        # Phase 2 TODO: Update both in-memory queue and database
        # 1. Remove from current position in priority queue
        # 2. Update database record
        # 3. Re-add to priority queue if execution is soon
        
        try:
            success = await self._update_trigger_execution_time(trigger_id, next_execution)
            
            if success:
                self.logger.info(f"Trigger {trigger_id} schedule updated successfully")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Trigger schedule update failed: {e}", exc_info=True)
            raise TriggerResolutionError(f"Failed to update trigger schedule: {e}")
    
    @abstractmethod
    async def _update_trigger_execution_time(self, trigger_id: str, next_execution: datetime) -> bool:
        """Implementation-specific trigger schedule update logic"""
        pass


class LockManagerService(BaseSchedulerService):
    """
    Service interface for distributed lock management.
    
    Implements MongoDB TTL-based distributed locking as decided in the creative phase.
    Provides lock acquisition, renewal, release, and health monitoring capabilities
    with automatic cleanup through TTL expiration.
    """
    
    def __init__(self):
        super().__init__("LockManagerService")
        self._active_locks = 0
        self._failed_acquisitions = 0
    
    async def _perform_initialization(self) -> bool:
        """Initialize lock manager components"""
        try:
            # Phase 2 TODO: Initialize MongoDB connection, TTL indexes, cleanup processes
            self.logger.info("Initializing lock manager components")
            
            self._active_locks = 0
            self._failed_acquisitions = 0
            
            return True
        except Exception as e:
            self.logger.error(f"Lock manager initialization failed: {e}")
            return False
    
    async def _perform_shutdown(self) -> bool:
        """Shutdown lock manager and cleanup"""
        try:
            # Phase 2 TODO: Release all owned locks, cleanup resources
            self.logger.info("Shutting down lock manager")
            return True
        except Exception as e:
            self.logger.error(f"Lock manager shutdown failed: {e}")
            return False
    
    async def _check_detailed_health(self) -> Dict[str, Any]:
        """Check lock manager specific health metrics"""
        return {
            "active_locks": self._active_locks,
            "failed_acquisitions": self._failed_acquisitions,
            "ttl_cleanup": "healthy",     # Phase 2: Real TTL cleanup monitoring
            "lock_contention": "low"      # Phase 2: Real contention metrics
        }
    
    @abstractmethod
    async def acquire_execution_lock(self, request: LockAcquisitionRequest, 
                                   worker_instance_id: str) -> Optional[ExecutionLockModel]:
        """
        Acquire distributed execution lock.
        
        Args:
            request: Lock acquisition request details
            worker_instance_id: ID of worker instance requesting lock
            
        Returns:
            ExecutionLockModel if acquisition successful, None otherwise
            
        Raises:
            LockManagerError: If lock acquisition process fails
        """
        self.logger.info(f"Acquiring lock for {request.resource_type}:{request.resource_id}")
        
        # Phase 2 TODO: Implement MongoDB TTL-based locking
        # 1. Attempt to insert lock document with unique constraint
        # 2. Set TTL expiration based on requested duration
        # 3. Return lock model if successful, None if already locked
        # 4. Handle race conditions and cleanup expired locks
        
        try:
            lock = await self._attempt_lock_acquisition(request, worker_instance_id)
            
            if lock:
                self.logger.info(f"Lock acquired successfully: {lock.lock_id}")
                self._active_locks += 1
            else:
                self.logger.info(f"Lock acquisition failed - resource already locked")
                self._failed_acquisitions += 1
            
            return lock
            
        except Exception as e:
            self.logger.error(f"Lock acquisition error: {e}", exc_info=True)
            self._failed_acquisitions += 1
            raise LockManagerError(f"Lock acquisition failed: {e}")
    
    @abstractmethod
    async def _attempt_lock_acquisition(self, request: LockAcquisitionRequest, 
                                      worker_instance_id: str) -> Optional[ExecutionLockModel]:
        """Implementation-specific lock acquisition logic"""
        pass
    
    @abstractmethod
    async def release_execution_lock(self, lock_id: str, worker_instance_id: str) -> bool:
        """
        Release distributed execution lock.
        
        Args:
            lock_id: ID of lock to release
            worker_instance_id: ID of worker instance releasing lock
            
        Returns:
            bool: True if release successful
            
        Raises:
            LockManagerError: If lock release fails
        """
        self.logger.info(f"Releasing lock {lock_id}")
        
        # Phase 2 TODO: Implement lock release with ownership validation
        # 1. Verify lock ownership by worker instance
        # 2. Delete lock document from MongoDB
        # 3. Handle cases where lock has already expired via TTL
        
        try:
            success = await self._perform_lock_release(lock_id, worker_instance_id)
            
            if success:
                self.logger.info(f"Lock {lock_id} released successfully")
                self._active_locks = max(0, self._active_locks - 1)
            else:
                self.logger.warning(f"Lock {lock_id} release failed")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Lock release error: {e}", exc_info=True)
            raise LockManagerError(f"Lock release failed: {e}")
    
    @abstractmethod
    async def _perform_lock_release(self, lock_id: str, worker_instance_id: str) -> bool:
        """Implementation-specific lock release logic"""
        pass
    
    @abstractmethod
    async def extend_lock(self, lock_id: str, additional_seconds: int) -> bool:
        """
        Extend lock expiration time.
        
        Args:
            lock_id: ID of lock to extend
            additional_seconds: Additional time to extend lock
            
        Returns:
            bool: True if extension successful
        """
        self.logger.info(f"Extending lock {lock_id} by {additional_seconds} seconds")
        
        # Phase 2 TODO: Implement lock extension
        # 1. Find lock document by ID
        # 2. Verify lock is still valid and owned by current instance
        # 3. Update expires_at field with new expiration time
        # 4. Handle extension limits and policies
        
        try:
            success = await self._perform_lock_extension(lock_id, additional_seconds)
            
            if success:
                self.logger.info(f"Lock {lock_id} extended successfully")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Lock extension error: {e}", exc_info=True)
            raise LockManagerError(f"Lock extension failed: {e}")
    
    @abstractmethod
    async def _perform_lock_extension(self, lock_id: str, additional_seconds: int) -> bool:
        """Implementation-specific lock extension logic"""
        pass
    
    @abstractmethod
    async def check_lock_health(self, lock_id: str) -> Dict[str, Any]:
        """
        Check health status of a specific lock.
        
        Args:
            lock_id: ID of lock to check
            
        Returns:
            Dict containing lock health information
        """
        self.logger.debug(f"Checking health of lock {lock_id}")
        
        # Phase 2 TODO: Implement lock health checking
        # 1. Retrieve lock document from MongoDB
        # 2. Check expiration status and time remaining
        # 3. Verify heartbeat status if enabled
        # 4. Return comprehensive health information
        
        try:
            health_info = await self._check_lock_health_details(lock_id)
            return health_info
            
        except Exception as e:
            self.logger.error(f"Lock health check error: {e}", exc_info=True)
            return {
                "lock_id": lock_id,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    @abstractmethod
    async def _check_lock_health_details(self, lock_id: str) -> Dict[str, Any]:
        """Implementation-specific lock health check logic"""
        pass


class JobExecutionService(BaseSchedulerService):
    """
    Service interface for job execution lifecycle management.
    
    Handles job creation, status tracking, retry logic, and completion processing.
    Integrates with trigger engine and lock manager to coordinate job execution
    across multiple worker instances.
    """
    
    def __init__(self):
        super().__init__("JobExecutionService")
        self._active_jobs = 0
        self._completed_jobs = 0
        self._failed_jobs = 0
    
    async def _perform_initialization(self) -> bool:
        """Initialize job execution components"""
        try:
            # Phase 2 TODO: Initialize job tracking, retry policies, performance monitoring
            self.logger.info("Initializing job execution service")
            
            self._active_jobs = 0
            self._completed_jobs = 0
            self._failed_jobs = 0
            
            return True
        except Exception as e:
            self.logger.error(f"Job execution service initialization failed: {e}")
            return False
    
    async def _perform_shutdown(self) -> bool:
        """Shutdown job execution service"""
        try:
            # Phase 2 TODO: Complete running jobs, cleanup resources
            self.logger.info("Shutting down job execution service")
            return True
        except Exception as e:
            self.logger.error(f"Job execution service shutdown failed: {e}")
            return False
    
    async def _check_detailed_health(self) -> Dict[str, Any]:
        """Check job execution specific health metrics"""
        return {
            "active_jobs": self._active_jobs,
            "completed_jobs": self._completed_jobs,
            "failed_jobs": self._failed_jobs,
            "job_processing": "healthy",    # Phase 2: Real job processing health
            "retry_engine": "healthy"       # Phase 2: Real retry engine health
        }
    
    @abstractmethod
    async def register_job_run(self, trigger: ScheduledTriggerModel, 
                             execution_context: Dict[str, Any]) -> ScheduledJobModel:
        """
        Register a new job execution.
        
        Args:
            trigger: Trigger that initiated the job
            execution_context: Context for job execution
            
        Returns:
            ScheduledJobModel for the new job
            
        Raises:
            SchedulerServiceException: If job registration fails
        """
        self.logger.info(f"Registering job run for trigger {trigger.trigger_id}")
        
        # Phase 2 TODO: Implement job registration logic
        # 1. Create new ScheduledJobModel with unique job_id
        # 2. Set initial status to PENDING
        # 3. Store execution context and trigger metadata
        # 4. Persist to database for tracking
        
        try:
            job = await self._create_job_record(trigger, execution_context)
            
            if job:
                self.logger.info(f"Job {job.job_id} registered successfully")
                self._active_jobs += 1
            
            return job
            
        except Exception as e:
            self.logger.error(f"Job registration failed: {e}", exc_info=True)
            raise SchedulerServiceException(f"Job registration failed: {e}")
    
    @abstractmethod
    async def _create_job_record(self, trigger: ScheduledTriggerModel, 
                               execution_context: Dict[str, Any]) -> ScheduledJobModel:
        """Implementation-specific job creation logic"""
        pass
    
    @abstractmethod
    async def mark_job_complete(self, job_id: str, success: bool, 
                              result_data: Optional[Dict[str, Any]] = None,
                              error_details: Optional[Dict[str, Any]] = None,
                              performance_metrics: Optional[Dict[str, Any]] = None) -> bool:
        """
        Mark job as completed.
        
        Args:
            job_id: ID of job to mark complete
            success: Whether job completed successfully
            result_data: Job execution results
            error_details: Error details if job failed
            performance_metrics: Performance metrics
            
        Returns:
            bool: True if marking successful
        """
        self.logger.info(f"Marking job {job_id} as {'completed' if success else 'failed'}")
        
        # Phase 2 TODO: Implement job completion logic
        # 1. Update job status to COMPLETED or FAILED
        # 2. Store result data and performance metrics
        # 3. Update trigger execution statistics
        # 4. Schedule retry if job failed and retries available
        # 5. Release associated execution locks
        
        try:
            completed = await self._complete_job_execution(
                job_id, success, result_data, error_details, performance_metrics
            )
            
            if completed:
                if success:
                    self._completed_jobs += 1
                else:
                    self._failed_jobs += 1
                self._active_jobs = max(0, self._active_jobs - 1)
                
                self.logger.info(f"Job {job_id} marked as complete")
            
            return completed
            
        except Exception as e:
            self.logger.error(f"Job completion failed: {e}", exc_info=True)
            raise SchedulerServiceException(f"Job completion failed: {e}")
    
    @abstractmethod
    async def _complete_job_execution(self, job_id: str, success: bool,
                                    result_data: Optional[Dict[str, Any]],
                                    error_details: Optional[Dict[str, Any]],
                                    performance_metrics: Optional[Dict[str, Any]]) -> bool:
        """Implementation-specific job completion logic"""
        pass
    
    @abstractmethod
    async def retry_failed_job(self, job_id: str) -> bool:
        """
        Retry a failed job execution.
        
        Args:
            job_id: ID of job to retry
            
        Returns:
            bool: True if retry scheduling successful
        """
        self.logger.info(f"Retrying failed job {job_id}")
        
        # Phase 2 TODO: Implement job retry logic
        # 1. Retrieve job record and check retry eligibility
        # 2. Calculate next retry time with backoff
        # 3. Update job status to RETRYING
        # 4. Schedule job for retry execution
        # 5. Update retry attempt counter
        
        try:
            retry_scheduled = await self._schedule_job_retry(job_id)
            
            if retry_scheduled:
                self.logger.info(f"Job {job_id} scheduled for retry")
            else:
                self.logger.warning(f"Job {job_id} retry scheduling failed")
            
            return retry_scheduled
            
        except Exception as e:
            self.logger.error(f"Job retry failed: {e}", exc_info=True)
            raise SchedulerServiceException(f"Job retry failed: {e}")
    
    @abstractmethod
    async def _schedule_job_retry(self, job_id: str) -> bool:
        """Implementation-specific job retry scheduling logic"""
        pass
    
    @abstractmethod
    async def get_job_status(self, job_id: str) -> Optional[ScheduledJobModel]:
        """
        Get current status of a job.
        
        Args:
            job_id: ID of job to check
            
        Returns:
            ScheduledJobModel if found, None otherwise
        """
        self.logger.debug(f"Getting status for job {job_id}")
        
        # Phase 2 TODO: Implement job status retrieval
        # 1. Query database for job record
        # 2. Return current job model with latest status
        # 3. Handle cases where job doesn't exist
        
        try:
            job = await self._retrieve_job_record(job_id)
            return job
            
        except Exception as e:
            self.logger.error(f"Job status retrieval failed: {e}", exc_info=True)
            raise SchedulerServiceException(f"Job status retrieval failed: {e}")
    
    @abstractmethod
    async def _retrieve_job_record(self, job_id: str) -> Optional[ScheduledJobModel]:
        """Implementation-specific job retrieval logic"""
        pass


# Context manager for service coordination
@asynccontextmanager
async def scheduler_service_context(*services: BaseSchedulerService):
    """
    Context manager for coordinated service lifecycle management.
    
    Initializes all services on entry and ensures proper shutdown on exit.
    Useful for coordinating multiple scheduler services in Phase 2 implementation.
    """
    initialized_services = []
    
    try:
        # Initialize all services
        for service in services:
            if await service.initialize():
                initialized_services.append(service)
                logger.info(f"Service {service.__class__.__name__} initialized")
            else:
                logger.error(f"Service {service.__class__.__name__} initialization failed")
                raise SchedulerServiceException(f"Failed to initialize {service.__class__.__name__}")
        
        yield initialized_services
        
    finally:
        # Shutdown all initialized services
        for service in reversed(initialized_services):
            try:
                await service.shutdown()
                logger.info(f"Service {service.__class__.__name__} shutdown completed")
            except Exception as e:
                logger.error(f"Service {service.__class__.__name__} shutdown failed: {e}")


# Service factory for dependency injection (Phase 2)
class SchedulerServiceFactory:
    """
    Factory class for creating scheduler service instances.
    
    Provides dependency injection and configuration management for scheduler services.
    Will be fully implemented in Phase 2 with concrete service implementations.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.logger = get_logger("SchedulerServiceFactory")
    
    async def create_trigger_engine_service(self) -> TriggerEngineService:
        """Create and configure trigger engine service instance"""
        # Phase 2 TODO: Create concrete implementation with configuration
        self.logger.info("Creating trigger engine service (placeholder)")
        raise NotImplementedError("Phase 2 implementation required")
    
    async def create_lock_manager_service(self) -> LockManagerService:
        """Create and configure lock manager service instance"""
        # Phase 2 TODO: Create concrete implementation with MongoDB TTL configuration
        self.logger.info("Creating lock manager service (placeholder)")
        raise NotImplementedError("Phase 2 implementation required")
    
    async def create_job_execution_service(self) -> JobExecutionService:
        """Create and configure job execution service instance"""
        # Phase 2 TODO: Create concrete implementation with retry policies
        self.logger.info("Creating job execution service (placeholder)")
        raise NotImplementedError("Phase 2 implementation required")
    
    async def create_all_services(self) -> Tuple[TriggerEngineService, LockManagerService, JobExecutionService]:
        """Create all scheduler services with proper configuration"""
        trigger_service = await self.create_trigger_engine_service()
        lock_service = await self.create_lock_manager_service()
        job_service = await self.create_job_execution_service()
        
        return trigger_service, lock_service, job_service 
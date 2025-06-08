"""
Scheduled Task Runner Engine - Task Orchestration Engine

Implements the core orchestration engine for IntelliBrowse's Scheduled Task Runner.
This engine is responsible for selecting due tasks, acquiring execution locks, 
invoking execution handlers, retrying failures, and logging execution metadata.

Key Features:
- Hybrid Priority Queue with Database Persistence (Creative Phase Decision)
- MongoDB TTL-Based Distributed Locking (Creative Phase Decision)
- Exponential backoff retry logic with comprehensive error handling
- Event-driven task dispatching with job handler interface
- Extensible architecture for dynamic task types (HTTP calls, LLM tasks, etc.)

Architecture Notes:
- Based on creative phase decisions: Hybrid Priority Queue + MongoDB TTL Locking
- Implements async-safe, idempotent task execution patterns
- Prevents race conditions using distributed locking model
- Automatically retries transient failures with structured logging
- Full integration with IntelliBrowse service patterns
"""

import asyncio
import heapq
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple, Callable
from contextlib import asynccontextmanager
import traceback

from ...config.logging import get_logger
from ..models.trigger_model import (
    ScheduledTriggerModel, 
    ScheduledJobModel, 
    ExecutionLockModel,
    TaskStatus, 
    ExecutionStatus, 
    TriggerType,
    SchedulerException,
    LockAcquisitionError
)
from ..schemas.trigger_schemas import (
    LockAcquisitionRequest,
    LockAcquisitionResponse
)
from ..services.base_scheduler_service import (
    TriggerEngineService,
    LockManagerService, 
    JobExecutionService,
    SchedulerServiceException,
    TriggerResolutionError,
    LockManagerError
)

logger = get_logger(__name__)


class JobExecutionError(SchedulerException):
    """Exception for job execution failures"""
    
    def __init__(self, message: str, job_id: str = None, execution_context: Dict[str, Any] = None):
        super().__init__(
            message, 
            job_id=job_id,
            error_code="JOB_EXECUTION_FAILED"
        )
        self.execution_context = execution_context or {}


class TaskOrchestrationEngine:
    """
    Core orchestration engine for the Scheduled Task Runner.
    
    Implements the main scheduling loop that processes due triggers, acquires locks,
    dispatches job execution, and handles retry logic. Designed for high-concurrency 
    scenarios with robust error handling and comprehensive logging.
    
    Key Responsibilities:
    - Fetch due triggers from ScheduledTriggerModel
    - Resolve associated jobs using SchedulerService.resolve_next_trigger
    - Acquire execution locks using SchedulerService.acquire_execution_lock
    - Dispatch job execution via event bus or job handler interface
    - Mark job success or retry/failure via service methods
    """
    
    def __init__(self, 
                 trigger_service: TriggerEngineService,
                 lock_service: LockManagerService,
                 job_service: JobExecutionService,
                 worker_instance_id: str = None,
                 config: Dict[str, Any] = None):
        """
        Initialize the Task Orchestration Engine.
        
        Args:
            trigger_service: Service for trigger resolution and queue management
            lock_service: Service for distributed lock management  
            job_service: Service for job execution tracking
            worker_instance_id: Unique identifier for this worker instance
            config: Engine configuration parameters
        """
        self.trigger_service = trigger_service
        self.lock_service = lock_service
        self.job_service = job_service
        self.worker_instance_id = worker_instance_id or f"worker_{uuid.uuid4().hex[:8]}"
        self.config = config or {}
        
        # Engine configuration
        self.max_concurrent_executions = self.config.get("max_concurrent_executions", 10)
        self.scheduler_tick_interval = self.config.get("scheduler_tick_interval", 5)  # seconds
        self.lock_timeout_seconds = self.config.get("lock_timeout_seconds", 300)  # 5 minutes
        self.max_retries = self.config.get("max_retries", 3)
        self.retry_base_delay = self.config.get("retry_base_delay", 60)  # seconds
        self.retry_backoff_multiplier = self.config.get("retry_backoff_multiplier", 2.0)
        
        # Runtime state
        self._running = False
        self._current_executions = 0
        self._scheduler_task = None
        self._job_handlers: Dict[str, Callable] = {}
        self._metrics = {
            "total_ticks": 0,
            "triggers_processed": 0,
            "jobs_executed": 0,
            "jobs_failed": 0,
            "locks_acquired": 0,
            "locks_failed": 0,
            "retries_attempted": 0
        }
        
        # Logging context
        self.logger = get_logger(__name__).bind(
            worker_instance=self.worker_instance_id,
            engine="TaskOrchestrationEngine"
        )
        
        self.logger.info("Task Orchestration Engine initialized", extra={
            "config": self.config,
            "max_concurrent_executions": self.max_concurrent_executions,
            "scheduler_tick_interval": self.scheduler_tick_interval
        })
    
    async def start(self):
        """Start the orchestration engine scheduler loop"""
        if self._running:
            self.logger.warning("Orchestration engine already running")
            return
            
        self.logger.info("Starting Task Orchestration Engine")
        self._running = True
        
        # Start the main scheduler loop
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        
        self.logger.info("Task Orchestration Engine started successfully")
    
    async def stop(self):
        """Stop the orchestration engine and cleanup resources"""
        if not self._running:
            self.logger.warning("Orchestration engine not running")
            return
            
        self.logger.info("Stopping Task Orchestration Engine")
        self._running = False
        
        # Cancel scheduler task
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        
        # Wait for current executions to complete (with timeout)
        timeout_seconds = 30
        start_time = datetime.now(timezone.utc)
        while self._current_executions > 0:
            if (datetime.now(timezone.utc) - start_time).total_seconds() > timeout_seconds:
                self.logger.warning(f"Timeout waiting for {self._current_executions} executions to complete")
                break
            await asyncio.sleep(1)
        
        self.logger.info("Task Orchestration Engine stopped", extra={
            "final_metrics": self._metrics
        })
    
    async def _scheduler_loop(self):
        """Main scheduler loop that runs continuously"""
        self.logger.info("Scheduler loop started")
        
        try:
            while self._running:
                try:
                    await self.run_scheduler_tick()
                    self._metrics["total_ticks"] += 1
                    
                except Exception as e:
                    self.logger.error(f"Error in scheduler tick: {e}", exc_info=True, extra={
                        "error_type": type(e).__name__,
                        "error_details": str(e)
                    })
                
                # Wait for next tick
                await asyncio.sleep(self.scheduler_tick_interval)
                
        except asyncio.CancelledError:
            self.logger.info("Scheduler loop cancelled")
            raise
        except Exception as e:
            self.logger.error(f"Fatal error in scheduler loop: {e}", exc_info=True)
            raise
    
    async def run_scheduler_tick(self) -> None:
        """
        Execute a single scheduler tick.
        
        This is the main method that:
        1. Fetches due triggers from ScheduledTriggerModel
        2. Resolves associated jobs using SchedulerService.resolve_next_trigger  
        3. Acquires execution locks using SchedulerService.acquire_execution_lock
        4. Dispatches job execution (via event bus or job handler interface)
        5. Marks job success or retry/failure via service methods
        """
        try:
            # Check if we can handle more executions
            if self._current_executions >= self.max_concurrent_executions:
                self.logger.debug("Max concurrent executions reached, skipping tick", extra={
                    "current_executions": self._current_executions,
                    "max_executions": self.max_concurrent_executions
                })
                return
            
            # Calculate how many new executions we can start
            available_slots = self.max_concurrent_executions - self._current_executions
            
            # Fetch due triggers
            due_triggers = await self._fetch_due_triggers(max_count=available_slots)
            
            if not due_triggers:
                self.logger.debug("No due triggers found in current tick")
                return
            
            self.logger.info(f"Processing {len(due_triggers)} due triggers", extra={
                "trigger_count": len(due_triggers),
                "available_slots": available_slots
            })
            
            # Process each trigger
            for trigger in due_triggers:
                try:
                    await self._process_trigger(trigger)
                    self._metrics["triggers_processed"] += 1
                    
                except Exception as e:
                    self.logger.error(f"Error processing trigger {trigger.trigger_id}: {e}", 
                                    exc_info=True, extra={
                                        "trigger_id": trigger.trigger_id,
                                        "trigger_type": trigger.trigger_type,
                                        "error_type": type(e).__name__
                                    })
            
        except Exception as e:
            self.logger.error(f"Error in scheduler tick: {e}", exc_info=True)
            raise
    
    async def _fetch_due_triggers(self, max_count: int = 10) -> List[ScheduledTriggerModel]:
        """
        Fetch due triggers from the trigger service.
        
        Args:
            max_count: Maximum number of triggers to fetch
            
        Returns:
            List of due triggers ready for execution
        """
        try:
            self.logger.debug(f"Fetching due triggers (max_count={max_count})")
            
            # Use the trigger service to resolve next triggers
            due_triggers = await self.trigger_service.resolve_next_trigger(max_count=max_count)
            
            self.logger.debug(f"Fetched {len(due_triggers)} due triggers", extra={
                "trigger_count": len(due_triggers),
                "trigger_ids": [t.trigger_id for t in due_triggers]
            })
            
            return due_triggers
            
        except TriggerResolutionError as e:
            self.logger.error(f"Trigger resolution error: {e}", extra={
                "error_details": e.to_dict()
            })
            return []
            
        except Exception as e:
            self.logger.error(f"Error fetching due triggers: {e}", exc_info=True)
            return []
    
    async def _process_trigger(self, trigger: ScheduledTriggerModel):
        """
        Process a single trigger for execution.
        
        Args:
            trigger: The trigger to process
        """
        trigger_logger = self.logger.bind(
            trigger_id=trigger.trigger_id,
            trigger_type=trigger.trigger_type
        )
        
        try:
            trigger_logger.info("Processing trigger for execution")
            
            # Check if trigger can execute now
            if not trigger.can_execute_now():
                trigger_logger.warning("Trigger cannot execute now", extra={
                    "status": trigger.status,
                    "max_concurrent": trigger.max_concurrent_executions,
                    "current_executions": trigger.current_executions
                })
                return
            
            # Try to acquire execution lock
            lock = await self._acquire_execution_lock(trigger)
            if not lock:
                trigger_logger.warning("Failed to acquire execution lock")
                self._metrics["locks_failed"] += 1
                return
            
            trigger_logger.info("Acquired execution lock", extra={
                "lock_id": lock.lock_id
            })
            self._metrics["locks_acquired"] += 1
            
            # Dispatch job execution
            await self._dispatch_job_execution(trigger, lock)
            
        except Exception as e:
            trigger_logger.error(f"Error processing trigger: {e}", exc_info=True)
            raise
    
    async def _acquire_execution_lock(self, trigger: ScheduledTriggerModel) -> Optional[ExecutionLockModel]:
        """
        Acquire an execution lock for the trigger.
        
        Args:
            trigger: The trigger to acquire lock for
            
        Returns:
            ExecutionLockModel if lock acquired, None otherwise
        """
        try:
            # Create lock acquisition request
            lock_request = LockAcquisitionRequest(
                resource_type="scheduled_trigger",
                resource_id=trigger.trigger_id,
                lock_duration_seconds=self.lock_timeout_seconds,
                execution_context={
                    "trigger_id": trigger.trigger_id,
                    "trigger_type": trigger.trigger_type,
                    "task_type": trigger.task_type,
                    "worker_instance": self.worker_instance_id
                }
            )
            
            # Attempt lock acquisition
            lock = await self.lock_service.acquire_execution_lock(
                request=lock_request,
                worker_instance_id=self.worker_instance_id
            )
            
            return lock
            
        except LockManagerError as e:
            self.logger.warning(f"Lock manager error for trigger {trigger.trigger_id}: {e}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error acquiring lock for trigger {trigger.trigger_id}: {e}", exc_info=True)
            return None
    
    async def _dispatch_job_execution(self, trigger: ScheduledTriggerModel, lock: ExecutionLockModel):
        """
        Dispatch job execution for the trigger.
        
        Args:
            trigger: The trigger to execute
            lock: The acquired execution lock
        """
        job_logger = self.logger.bind(
            trigger_id=trigger.trigger_id,
            lock_id=lock.lock_id
        )
        
        try:
            # Create execution context
            execution_context = {
                "trigger_id": trigger.trigger_id,
                "lock_id": lock.lock_id,
                "worker_instance": self.worker_instance_id,
                "execution_time": datetime.now(timezone.utc).isoformat(),
                "task_type": trigger.task_type,
                "task_config": trigger.task_config,
                "task_parameters": trigger.task_parameters
            }
            
            # Register job run
            job = await self.job_service.register_job_run(
                trigger=trigger,
                execution_context=execution_context
            )
            
            job_logger = job_logger.bind(job_id=job.job_id)
            job_logger.info("Job registered for execution")
            
            # Increment current executions counter
            self._current_executions += 1
            
            # Dispatch execution asynchronously
            asyncio.create_task(self._execute_job(job, trigger, lock))
            
        except Exception as e:
            job_logger.error(f"Error dispatching job execution: {e}", exc_info=True)
            
            # Release the lock since we couldn't dispatch
            try:
                await self.lock_service.release_execution_lock(
                    lock_id=lock.lock_id,
                    worker_instance_id=self.worker_instance_id
                )
            except Exception as release_error:
                job_logger.error(f"Error releasing lock after dispatch failure: {release_error}")
            
            raise
    
    async def _execute_job(self, job: ScheduledJobModel, trigger: ScheduledTriggerModel, lock: ExecutionLockModel):
        """
        Execute a job with proper error handling and cleanup.
        
        Args:
            job: The job to execute
            trigger: The associated trigger
            lock: The execution lock
        """
        job_logger = self.logger.bind(
            job_id=job.job_id,
            trigger_id=trigger.trigger_id,
            lock_id=lock.lock_id
        )
        
        start_time = datetime.now(timezone.utc)
        success = False
        error_details = None
        result_data = None
        
        try:
            job_logger.info("Starting job execution")
            
            # Mark job as started
            job.mark_started(self.worker_instance_id)
            
            # Get job handler for this task type
            handler = self._get_job_handler(trigger.task_type)
            if not handler:
                raise JobExecutionError(
                    f"No handler found for task type: {trigger.task_type}",
                    job_id=job.job_id
                )
            
            # Execute the job
            result_data = await handler(trigger, job, lock)
            success = True
            
            job_logger.info("Job execution completed successfully", extra={
                "execution_duration": (datetime.now(timezone.utc) - start_time).total_seconds()
            })
            
        except Exception as e:
            success = False
            error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback": traceback.format_exc(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            job_logger.error(f"Job execution failed: {e}", exc_info=True, extra={
                "error_details": error_details
            })
            
        finally:
            # Calculate execution time
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            # Handle execution result
            await self._handle_execution_result(
                job_id=job.job_id,
                success=success,
                result_data=result_data,
                error_details=error_details,
                execution_time=execution_time
            )
            
            # Release execution lock
            try:
                await self.lock_service.release_execution_lock(
                    lock_id=lock.lock_id,
                    worker_instance_id=self.worker_instance_id
                )
                job_logger.debug("Execution lock released")
            except Exception as e:
                job_logger.error(f"Error releasing execution lock: {e}")
            
            # Decrement current executions counter
            self._current_executions -= 1
            
            # Update metrics
            if success:
                self._metrics["jobs_executed"] += 1
            else:
                self._metrics["jobs_failed"] += 1
    
    async def _handle_execution_result(self, job_id: str, success: bool, 
                                     result_data: Optional[Dict[str, Any]] = None,
                                     error_details: Optional[Dict[str, Any]] = None,
                                     execution_time: float = 0.0):
        """
        Handle the result of job execution.
        
        Args:
            job_id: The job ID
            success: Whether execution was successful
            result_data: Result data if successful
            error_details: Error details if failed
            execution_time: Execution time in seconds
        """
        result_logger = self.logger.bind(job_id=job_id)
        
        try:
            if success:
                # Mark job as complete
                await self.job_service.mark_job_complete(
                    job_id=job_id,
                    success=True,
                    result_data=result_data,
                    performance_metrics={
                        "execution_time_seconds": execution_time,
                        "worker_instance": self.worker_instance_id
                    }
                )
                result_logger.info("Job marked as completed successfully")
                
            else:
                # Check if job should be retried
                job = await self.job_service.get_job_status(job_id)
                if job and job.should_retry():
                    # Calculate retry delay with exponential backoff
                    retry_delay = self._calculate_retry_delay(job.retry_attempt)
                    
                    result_logger.info(f"Scheduling job retry in {retry_delay} seconds", extra={
                        "retry_attempt": job.retry_attempt + 1,
                        "max_retries": job.max_retries
                    })
                    
                    # Schedule retry
                    await self.job_service.retry_failed_job(job_id)
                    self._metrics["retries_attempted"] += 1
                    
                else:
                    # Mark job as failed (no more retries)
                    await self.job_service.mark_job_complete(
                        job_id=job_id,
                        success=False,
                        error_details=error_details,
                        performance_metrics={
                            "execution_time_seconds": execution_time,
                            "worker_instance": self.worker_instance_id
                        }
                    )
                    result_logger.info("Job marked as failed (no more retries)")
                    
        except Exception as e:
            result_logger.error(f"Error handling execution result: {e}", exc_info=True)
    
    def _calculate_retry_delay(self, retry_attempt: int) -> int:
        """
        Calculate retry delay with exponential backoff.
        
        Args:
            retry_attempt: Current retry attempt number
            
        Returns:
            Delay in seconds
        """
        delay = self.retry_base_delay * (self.retry_backoff_multiplier ** retry_attempt)
        
        # Add some jitter to prevent thundering herd
        import random
        jitter = random.uniform(0.8, 1.2)
        
        return int(delay * jitter)
    
    def _get_job_handler(self, task_type: str) -> Optional[Callable]:
        """
        Get job handler for the specified task type.
        
        Args:
            task_type: The type of task to get handler for
            
        Returns:
            Job handler function or None if not found
        """
        return self._job_handlers.get(task_type)
    
    def register_job_handler(self, task_type: str, handler: Callable):
        """
        Register a job handler for a specific task type.
        
        Args:
            task_type: The task type to register handler for
            handler: The handler function (async callable)
        """
        self._job_handlers[task_type] = handler
        self.logger.info(f"Registered job handler for task type: {task_type}")
    
    def unregister_job_handler(self, task_type: str):
        """
        Unregister a job handler for a specific task type.
        
        Args:
            task_type: The task type to unregister handler for
        """
        if task_type in self._job_handlers:
            del self._job_handlers[task_type]
            self.logger.info(f"Unregistered job handler for task type: {task_type}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get engine metrics.
        
        Returns:
            Dictionary containing engine metrics
        """
        return {
            **self._metrics,
            "worker_instance_id": self.worker_instance_id,
            "current_executions": self._current_executions,
            "max_concurrent_executions": self.max_concurrent_executions,
            "is_running": self._running,
            "registered_handlers": list(self._job_handlers.keys())
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check of the orchestration engine.
        
        Returns:
            Health check results
        """
        health_data = {
            "status": "healthy" if self._running else "stopped",
            "worker_instance_id": self.worker_instance_id,
            "current_executions": self._current_executions,
            "max_concurrent_executions": self.max_concurrent_executions,
            "metrics": self._metrics,
            "services": {}
        }
        
        # Check service health
        try:
            trigger_health = await self.trigger_service.health_check()
            health_data["services"]["trigger_service"] = trigger_health
        except Exception as e:
            health_data["services"]["trigger_service"] = {"status": "error", "error": str(e)}
        
        try:
            lock_health = await self.lock_service.health_check()
            health_data["services"]["lock_service"] = lock_health
        except Exception as e:
            health_data["services"]["lock_service"] = {"status": "error", "error": str(e)}
        
        try:
            job_health = await self.job_service.health_check()
            health_data["services"]["job_service"] = job_health
        except Exception as e:
            health_data["services"]["job_service"] = {"status": "error", "error": str(e)}
        
        return health_data


# Context manager for engine lifecycle
@asynccontextmanager
async def task_orchestration_engine_context(
    trigger_service: TriggerEngineService,
    lock_service: LockManagerService,
    job_service: JobExecutionService,
    config: Dict[str, Any] = None
):
    """
    Context manager for Task Orchestration Engine lifecycle.
    
    Args:
        trigger_service: Trigger engine service
        lock_service: Lock manager service  
        job_service: Job execution service
        config: Engine configuration
        
    Yields:
        TaskOrchestrationEngine: Initialized and started engine
    """
    engine = TaskOrchestrationEngine(
        trigger_service=trigger_service,
        lock_service=lock_service,
        job_service=job_service,
        config=config
    )
    
    try:
        await engine.start()
        yield engine
    finally:
        await engine.stop()


# Default job handlers for common task types
async def default_http_task_handler(trigger: ScheduledTriggerModel, 
                                  job: ScheduledJobModel, 
                                  lock: ExecutionLockModel) -> Dict[str, Any]:
    """
    Default handler for HTTP task execution.
    
    Args:
        trigger: The trigger that initiated the job
        job: The job being executed
        lock: The execution lock
        
    Returns:
        Execution results
    """
    # TODO: Implement HTTP task execution
    # This is a placeholder for Phase 3 implementation
    return {
        "status": "completed",
        "message": "HTTP task execution placeholder",
        "task_type": "http_call",
        "execution_id": job.job_id
    }


async def default_llm_task_handler(trigger: ScheduledTriggerModel, 
                                 job: ScheduledJobModel, 
                                 lock: ExecutionLockModel) -> Dict[str, Any]:
    """
    Default handler for LLM task execution.
    
    Args:
        trigger: The trigger that initiated the job
        job: The job being executed
        lock: The execution lock
        
    Returns:
        Execution results
    """
    # TODO: Implement LLM task execution
    # This is a placeholder for Phase 3 implementation
    return {
        "status": "completed",
        "message": "LLM task execution placeholder",
        "task_type": "llm_call",
        "execution_id": job.job_id
    }


# Factory function for creating orchestration engine
async def create_task_orchestration_engine(
    trigger_service: TriggerEngineService,
    lock_service: LockManagerService,
    job_service: JobExecutionService,
    config: Dict[str, Any] = None
) -> TaskOrchestrationEngine:
    """
    Factory function to create and configure a Task Orchestration Engine.
    
    Args:
        trigger_service: Trigger engine service
        lock_service: Lock manager service
        job_service: Job execution service
        config: Engine configuration
        
    Returns:
        Configured TaskOrchestrationEngine
    """
    engine = TaskOrchestrationEngine(
        trigger_service=trigger_service,
        lock_service=lock_service,
        job_service=job_service,
        config=config
    )
    
    # Register default handlers
    engine.register_job_handler("http_call", default_http_task_handler)
    engine.register_job_handler("llm_call", default_llm_task_handler)
    
    return engine 
"""
Retry Manager Service

Manages retry policies and failure recovery for orchestration jobs including:
- Retry rule enforcement from RetryPolicyModel
- Exponential backoff and jitter calculations
- Retry attempt tracking and job status updates
- Circuit breaker pattern implementation
"""

import asyncio
import math
import random
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase

from ...config.env import get_settings
from ...config.logging import get_logger
from .base_orchestration_service import (
    BaseOrchestrationService,
    ServiceConfiguration,
    ServiceDependency,
    ServiceLifecycle
)
from ..models.orchestration_models import (
    OrchestrationJobModel,
    RetryPolicyModel,
    JobStatus,
    RetryStrategy,
    OrchestrationException,
    RetryPolicyError,
    InvalidJobStateError
)
from ..schemas.orchestration_schemas import (
    JobStatusResponse,
    RetryPolicyResponse,
    CreateRetryPolicyRequest,
    UpdateRetryPolicyRequest
)

logger = get_logger(__name__)


class RetryManagerService(BaseOrchestrationService[RetryPolicyModel]):
    """
    Retry Manager Service for orchestration engine.
    
    Responsibilities:
    - Enforce retry rules from RetryPolicyModel
    - Calculate next retry time using configured backoff strategies
    - Track retry attempts and update job status accordingly
    - Skip retries if max_attempts exceeded or strategy == NONE
    - Implement circuit breaker patterns for failure isolation
    """
    
    def __init__(
        self,
        database: AsyncIOMotorDatabase,
        config: Optional[ServiceConfiguration] = None
    ):
        """Initialize RetryManagerService with database and configuration."""
        service_config = config or ServiceConfiguration(
            service_name="RetryManagerService",
            heartbeat_interval_seconds=30,
            operation_timeout_seconds=180,
            max_concurrent_operations=100
        )
        
        super().__init__(service_config)
        
        self.database = database
        self.jobs_collection = database.orchestration_jobs
        self.policies_collection = database.retry_policies
        
        # Retry tracking
        self._retry_queue: asyncio.Queue = asyncio.Queue(maxsize=2000)
        self._active_retries: Dict[str, Dict[str, Any]] = {}
        self._retry_timers: Dict[str, asyncio.Task] = {}
        
        # Circuit breaker tracking
        self._circuit_breakers: Dict[str, Dict[str, Any]] = {}
        
        # Performance metrics
        self._retry_metrics: Dict[str, int] = {
            "retries_attempted": 0,
            "retries_successful": 0,
            "retries_exhausted": 0,
            "circuit_breakers_opened": 0,
            "circuit_breakers_closed": 0
        }
        
        # Default retry configuration
        self._default_config = {
            "max_attempts": 3,
            "base_delay_ms": 1000,
            "max_delay_ms": 60000,
            "backoff_multiplier": 2.0,
            "jitter_enabled": True,
            "jitter_range": 0.1
        }
        
        self._logger.info("RetryManagerService initialized with database connection")
    
    async def _initialize_service(self) -> None:
        """Initialize service-specific components."""
        self._logger.info("Initializing RetryManagerService")
        
        # Verify database collections
        await self._ensure_collections_exist()
        
        # Load retry policies
        await self._load_retry_policies()
        
        # Initialize circuit breakers
        await self._initialize_circuit_breakers()
        
        self._logger.info("RetryManagerService initialization complete")
    
    async def _start_service(self) -> None:
        """Start service background tasks."""
        self._logger.info("Starting RetryManagerService background tasks")
        
        # Start retry processing loop
        asyncio.create_task(self._retry_processing_loop())
        
        # Start circuit breaker monitoring
        asyncio.create_task(self._circuit_breaker_monitoring_loop())
        
        self._logger.info("RetryManagerService background tasks started")
    
    async def _stop_service(self) -> None:
        """Stop service and cleanup resources."""
        self._logger.info("Stopping RetryManagerService")
        
        # Cancel active retry timers
        for job_id, timer_task in self._retry_timers.items():
            timer_task.cancel()
            try:
                await timer_task
            except asyncio.CancelledError:
                pass
        
        self._retry_timers.clear()
        self._active_retries.clear()
        
        self._logger.info("RetryManagerService stopped")
    
    async def _health_check(self) -> Dict[str, Any]:
        """Perform health check for retry manager service."""
        queue_size = self._retry_queue.qsize()
        active_retries_count = len(self._active_retries)
        open_circuit_breakers = len([
            cb for cb in self._circuit_breakers.values()
            if cb.get("state") == "open"
        ])
        
        return {
            "retry_queue_size": queue_size,
            "active_retries_count": active_retries_count,
            "open_circuit_breakers": open_circuit_breakers,
            "retry_metrics": self._retry_metrics.copy(),
            "healthy": queue_size < 1500 and open_circuit_breakers < 10
        }
    
    # Core Retry Operations
    
    async def schedule_retry(
        self,
        job_id: str,
        failure_reason: str,
        error_context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Schedule a retry for a failed job based on its retry policy.
        
        Args:
            job_id: Job identifier to retry
            failure_reason: Reason for the failure
            error_context: Additional error context
            
        Returns:
            bool: True if retry was scheduled, False if retries exhausted
            
        Raises:
            RetryPolicyError: If retry scheduling fails
        """
        correlation_id = str(uuid.uuid4())
        bound_logger = self._bind_logger_context(
            job_id=job_id,
            correlation_id=correlation_id
        )
        
        try:
            bound_logger.info(f"Evaluating retry for failed job: {failure_reason}")
            
            # Get job details
            job_doc = await self.jobs_collection.find_one({"job_id": job_id})
            if not job_doc:
                raise RetryPolicyError(f"Job not found: {job_id}", job_id=job_id)
            
            job = OrchestrationJobModel.from_mongo(job_doc)
            if not job:
                raise RetryPolicyError(f"Failed to load job: {job_id}", job_id=job_id)
            
            # Get retry policy
            retry_policy = await self._get_retry_policy(job)
            if not retry_policy:
                bound_logger.info("No retry policy found, marking job as aborted")
                await self._mark_job_aborted(job_id, "No retry policy configured")
                return False
            
            # Check if retry is allowed
            if not await self._can_retry(job, retry_policy, failure_reason, error_context):
                bound_logger.info("Retry not allowed, marking job as aborted")
                await self._mark_job_aborted(job_id, "Retry attempts exhausted")
                return False
            
            # Calculate retry delay
            delay_ms = await self._calculate_retry_delay(job, retry_policy)
            
            # Schedule retry
            retry_time = datetime.now(timezone.utc) + timedelta(milliseconds=delay_ms)
            
            # Update job for retry
            job.increment_retry()
            job.transition_state(
                JobStatus.RETRYING,
                reason=f"Retry scheduled: {failure_reason}",
                context={
                    "retry_attempt": job.retry_count,
                    "retry_delay_ms": delay_ms,
                    "retry_time": retry_time.isoformat(),
                    "failure_reason": failure_reason,
                    "error_context": error_context
                }
            )
            
            # Save job state
            await self.jobs_collection.update_one(
                {"job_id": job_id},
                {"$set": job.to_mongo()}
            )
            
            # Queue retry for execution
            retry_context = {
                "job_id": job_id,
                "retry_attempt": job.retry_count,
                "retry_time": retry_time,
                "policy_id": retry_policy.policy_id,
                "delay_ms": delay_ms,
                "correlation_id": correlation_id
            }
            
            await self._retry_queue.put(retry_context)
            
            # Track retry metrics
            self._retry_metrics["retries_attempted"] += 1
            
            bound_logger.info(f"Retry scheduled for {delay_ms}ms delay, attempt {job.retry_count}")
            return True
            
        except Exception as e:
            bound_logger.error(f"Failed to schedule retry: {e}")
            raise RetryPolicyError(f"Retry scheduling failed: {e}", job_id=job_id)
    
    async def cancel_retry(self, job_id: str, reason: str = "Retry cancelled") -> bool:
        """
        Cancel a scheduled retry for a job.
        
        Args:
            job_id: Job identifier
            reason: Cancellation reason
            
        Returns:
            bool: True if retry was cancelled
        """
        bound_logger = self._bind_logger_context(job_id=job_id)
        
        try:
            # Cancel retry timer if exists
            if job_id in self._retry_timers:
                timer_task = self._retry_timers.pop(job_id)
                timer_task.cancel()
                try:
                    await timer_task
                except asyncio.CancelledError:
                    pass
            
            # Remove from active retries
            self._active_retries.pop(job_id, None)
            
            # Update job status
            job_doc = await self.jobs_collection.find_one({"job_id": job_id})
            if job_doc:
                job = OrchestrationJobModel.from_mongo(job_doc)
                if job and job.status == JobStatus.RETRYING:
                    job.transition_state(JobStatus.CANCELLED, reason=reason)
                    await self.jobs_collection.update_one(
                        {"job_id": job_id},
                        {"$set": job.to_mongo()}
                    )
            
            bound_logger.info(f"Retry cancelled: {reason}")
            return True
            
        except Exception as e:
            bound_logger.error(f"Failed to cancel retry: {e}")
            return False
    
    async def create_retry_policy(
        self,
        request: CreateRetryPolicyRequest,
        created_by: str
    ) -> RetryPolicyResponse:
        """
        Create a new retry policy.
        
        Args:
            request: Retry policy creation request
            created_by: User who created the policy
            
        Returns:
            RetryPolicyResponse: Created policy information
        """
        bound_logger = self._bind_logger_context(
            policy_name=request.policy_name,
            created_by=created_by
        )
        
        try:
            bound_logger.info("Creating new retry policy")
            
            # Generate policy ID
            policy_id = str(uuid.uuid4())
            
            # Create policy model
            policy = RetryPolicyModel(
                policy_id=policy_id,
                policy_name=request.policy_name,
                policy_description=request.policy_description,
                strategy=request.strategy,
                max_attempts=request.max_attempts,
                base_delay_ms=request.base_delay_ms,
                max_delay_ms=request.max_delay_ms,
                backoff_multiplier=request.backoff_multiplier,
                jitter_enabled=request.jitter_enabled,
                jitter_range=request.jitter_range,
                circuit_breaker_enabled=request.circuit_breaker_enabled,
                failure_threshold=request.failure_threshold,
                success_threshold=request.success_threshold,
                circuit_timeout_ms=request.circuit_timeout_ms,
                retryable_error_types=request.retryable_error_types,
                non_retryable_error_types=request.non_retryable_error_types,
                applicable_job_types=request.applicable_job_types,
                tags=request.tags,
                metadata={"created_by": created_by}
            )
            
            # Save to database
            await self.policies_collection.insert_one(policy.to_mongo())
            
            bound_logger.info(f"Retry policy created successfully: {policy_id}")
            
            return RetryPolicyResponse(
                policy_id=policy_id,
                policy_name=policy.policy_name,
                strategy=policy.strategy,
                max_attempts=policy.max_attempts,
                base_delay_ms=policy.base_delay_ms,
                circuit_breaker_enabled=policy.circuit_breaker_enabled,
                created_at=policy.created_at,
                message="Retry policy created successfully"
            )
            
        except Exception as e:
            bound_logger.error(f"Failed to create retry policy: {e}")
            raise RetryPolicyError(f"Policy creation failed: {e}")
    
    # Internal Operations
    
    async def _retry_processing_loop(self) -> None:
        """Main retry processing loop."""
        self._logger.info("Starting retry processing loop")
        
        while self.lifecycle_state in [ServiceLifecycle.RUNNING, ServiceLifecycle.READY]:
            try:
                # Get retry from queue with timeout
                retry_context = await asyncio.wait_for(
                    self._retry_queue.get(),
                    timeout=5.0
                )
                
                # Process retry
                await self._process_retry(retry_context)
                
            except asyncio.TimeoutError:
                # Normal timeout, continue loop
                continue
            except Exception as e:
                self._logger.error(f"Error in retry processing loop: {e}")
                await asyncio.sleep(1)
    
    async def _circuit_breaker_monitoring_loop(self) -> None:
        """Monitor circuit breakers and update states."""
        self._logger.info("Starting circuit breaker monitoring loop")
        
        while self.lifecycle_state in [ServiceLifecycle.RUNNING, ServiceLifecycle.READY]:
            try:
                current_time = datetime.now(timezone.utc)
                
                # Check circuit breaker timeouts
                for policy_id, cb_state in self._circuit_breakers.items():
                    if cb_state["state"] == "open" and "timeout_time" in cb_state:
                        if current_time >= cb_state["timeout_time"]:
                            # Transition to half-open state
                            cb_state["state"] = "half-open"
                            cb_state["test_requests"] = 0
                            self._logger.info(f"Circuit breaker transitioned to half-open: {policy_id}")
                
                # Sleep before next check
                await asyncio.sleep(60)
                
            except Exception as e:
                self._logger.error(f"Error in circuit breaker monitoring: {e}")
                await asyncio.sleep(10)
    
    async def _process_retry(self, retry_context: Dict[str, Any]) -> None:
        """Process a single retry from the queue."""
        job_id = retry_context["job_id"]
        bound_logger = self._bind_logger_context(
            job_id=job_id,
            correlation_id=retry_context.get("correlation_id")
        )
        
        try:
            bound_logger.info("Processing retry")
            
            # Check if retry time has arrived
            retry_time = retry_context["retry_time"]
            if retry_time > datetime.now(timezone.utc):
                # Schedule for later
                delay_seconds = (retry_time - datetime.now(timezone.utc)).total_seconds()
                timer_task = asyncio.create_task(self._schedule_delayed_retry(retry_context, delay_seconds))
                self._retry_timers[job_id] = timer_task
                return
            
            # Execute retry
            await self._execute_retry(retry_context)
            
        except Exception as e:
            bound_logger.error(f"Failed to process retry: {e}")
            await self._mark_job_aborted(job_id, f"Retry processing failed: {e}")
    
    async def _schedule_delayed_retry(
        self,
        retry_context: Dict[str, Any],
        delay_seconds: float
    ) -> None:
        """Schedule retry for delayed execution."""
        job_id = retry_context["job_id"]
        
        try:
            await asyncio.sleep(delay_seconds)
            await self._execute_retry(retry_context)
        except asyncio.CancelledError:
            self._logger.info(f"Delayed retry cancelled for job: {job_id}")
        except Exception as e:
            self._logger.error(f"Failed delayed retry for job {job_id}: {e}")
            await self._mark_job_aborted(job_id, f"Delayed retry failed: {e}")
    
    async def _execute_retry(self, retry_context: Dict[str, Any]) -> None:
        """Execute the actual retry."""
        job_id = retry_context["job_id"]
        bound_logger = self._bind_logger_context(job_id=job_id)
        
        try:
            bound_logger.info("Executing retry")
            
            # Get current job state
            job_doc = await self.jobs_collection.find_one({"job_id": job_id})
            if not job_doc:
                bound_logger.warning("Job not found for retry execution")
                return
            
            job = OrchestrationJobModel.from_mongo(job_doc)
            if not job or job.status != JobStatus.RETRYING:
                bound_logger.warning(f"Job not in retrying state: {job.status if job else 'None'}")
                return
            
            # Transition job back to queued for re-execution
            job.transition_state(
                JobStatus.QUEUED,
                reason=f"Retry attempt {retry_context['retry_attempt']}",
                context={
                    "retry_executed": True,
                    "retry_attempt": retry_context["retry_attempt"]
                }
            )
            
            # Update job in database
            await self.jobs_collection.update_one(
                {"job_id": job_id},
                {"$set": job.to_mongo()}
            )
            
            # Clean up retry tracking
            self._active_retries.pop(job_id, None)
            self._retry_timers.pop(job_id, None)
            
            bound_logger.info("Retry executed successfully, job requeued")
            
        except Exception as e:
            bound_logger.error(f"Failed to execute retry: {e}")
            await self._mark_job_aborted(job_id, f"Retry execution failed: {e}")
    
    async def _get_retry_policy(self, job: OrchestrationJobModel) -> Optional[RetryPolicyModel]:
        """Get retry policy for a job."""
        # Check if job has specific retry policy
        if job.retry_policy_id:
            policy_doc = await self.policies_collection.find_one({"policy_id": job.retry_policy_id})
            if policy_doc:
                return RetryPolicyModel.from_mongo(policy_doc)
        
        # Find policy by job type
        policy_doc = await self.policies_collection.find_one({
            "applicable_job_types": job.job_type
        })
        
        if policy_doc:
            return RetryPolicyModel.from_mongo(policy_doc)
        
        # Use default policy if available
        default_policy_doc = await self.policies_collection.find_one({
            "policy_name": "default"
        })
        
        if default_policy_doc:
            return RetryPolicyModel.from_mongo(default_policy_doc)
        
        return None
    
    async def _can_retry(
        self,
        job: OrchestrationJobModel,
        policy: RetryPolicyModel,
        failure_reason: str,
        error_context: Optional[Dict[str, Any]]
    ) -> bool:
        """Check if job can be retried based on policy."""
        # Check retry strategy
        if policy.strategy == RetryStrategy.NONE:
            return False
        
        # Check max attempts
        if job.retry_count >= policy.max_attempts:
            return False
        
        # Check circuit breaker
        if policy.circuit_breaker_enabled:
            cb_state = self._circuit_breakers.get(policy.policy_id, {})
            if cb_state.get("state") == "open":
                return False
        
        # Check error type eligibility
        if policy.non_retryable_error_types:
            for error_type in policy.non_retryable_error_types:
                if error_type.lower() in failure_reason.lower():
                    return False
        
        if policy.retryable_error_types:
            retryable = False
            for error_type in policy.retryable_error_types:
                if error_type.lower() in failure_reason.lower():
                    retryable = True
                    break
            if not retryable:
                return False
        
        return True
    
    async def _calculate_retry_delay(
        self,
        job: OrchestrationJobModel,
        policy: RetryPolicyModel
    ) -> int:
        """Calculate retry delay based on policy strategy."""
        attempt = job.retry_count + 1  # Next attempt number
        
        if policy.strategy == RetryStrategy.IMMEDIATE:
            delay_ms = 0
        elif policy.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay_ms = min(
                policy.base_delay_ms * (policy.backoff_multiplier ** (attempt - 1)),
                policy.max_delay_ms
            )
        elif policy.strategy == RetryStrategy.FIBONACCI_BACKOFF:
            delay_ms = min(
                policy.base_delay_ms * self._fibonacci(attempt),
                policy.max_delay_ms
            )
        else:
            # Default to exponential backoff
            delay_ms = min(
                policy.base_delay_ms * (2 ** (attempt - 1)),
                policy.max_delay_ms
            )
        
        # Apply jitter if enabled
        if policy.jitter_enabled and delay_ms > 0:
            jitter_amount = delay_ms * policy.jitter_range
            jitter = random.uniform(-jitter_amount, jitter_amount)
            delay_ms = max(0, delay_ms + jitter)
        
        return int(delay_ms)
    
    def _fibonacci(self, n: int) -> int:
        """Calculate nth Fibonacci number."""
        if n <= 1:
            return n
        a, b = 0, 1
        for _ in range(2, n + 1):
            a, b = b, a + b
        return b
    
    async def _mark_job_aborted(self, job_id: str, reason: str) -> None:
        """Mark job as aborted due to retry exhaustion."""
        try:
            job_doc = await self.jobs_collection.find_one({"job_id": job_id})
            if job_doc:
                job = OrchestrationJobModel.from_mongo(job_doc)
                if job and job.can_transition_to(JobStatus.ABORTED):
                    job.transition_state(JobStatus.ABORTED, reason=reason)
                    await self.jobs_collection.update_one(
                        {"job_id": job_id},
                        {"$set": job.to_mongo()}
                    )
                    
                    self._retry_metrics["retries_exhausted"] += 1
                    
        except Exception as e:
            self._logger.error(f"Failed to mark job aborted: {e}")
    
    async def _load_retry_policies(self) -> None:
        """Load retry policies from database."""
        try:
            policies_cursor = self.policies_collection.find({})
            policies = await policies_cursor.to_list(length=None)
            
            self._logger.info(f"Loaded {len(policies)} retry policies")
            
        except Exception as e:
            self._logger.error(f"Failed to load retry policies: {e}")
    
    async def _initialize_circuit_breakers(self) -> None:
        """Initialize circuit breaker states."""
        try:
            # Get all policies with circuit breakers enabled
            cb_policies_cursor = self.policies_collection.find({
                "circuit_breaker_enabled": True
            })
            
            cb_policies = await cb_policies_cursor.to_list(length=None)
            
            for policy_doc in cb_policies:
                policy = RetryPolicyModel.from_mongo(policy_doc)
                if policy:
                    self._circuit_breakers[policy.policy_id] = {
                        "state": "closed",
                        "failure_count": 0,
                        "success_count": 0,
                        "last_failure_time": None,
                        "test_requests": 0
                    }
            
            self._logger.info(f"Initialized {len(self._circuit_breakers)} circuit breakers")
            
        except Exception as e:
            self._logger.error(f"Failed to initialize circuit breakers: {e}")
    
    async def _ensure_collections_exist(self) -> None:
        """Ensure required MongoDB collections exist."""
        collections = await self.database.list_collection_names()
        
        if "retry_policies" not in collections:
            await self.database.create_collection("retry_policies")
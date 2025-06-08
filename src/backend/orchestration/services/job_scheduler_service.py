"""
Job Scheduler Service

Manages the scheduling and execution of orchestration jobs including:
- DAG scheduling and validation
- Job stage dispatching via async queues
- Execution resource allocation
- Job lifecycle coordination with trace management
"""

import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, AsyncIterator
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
    OrchestrationNodeModel,
    JobStatus,
    NodeType,
    OrchestrationException,
    InvalidJobStateError
)
from ..schemas.orchestration_schemas import (
    CreateOrchestrationJobRequest,
    JobStatusResponse,
    OrchestrationResponse
)

logger = get_logger(__name__)


class JobSchedulerService(BaseOrchestrationService[OrchestrationJobModel]):
    """
    Job Scheduler Service for orchestration engine.
    
    Responsibilities:
    - Schedule execution DAGs based on OrchestrationJobModel
    - Assign trace_id, execution_id, and stage timing
    - Dispatch job stages via async queue or inter-service RPC
    - Manage job lifecycle transitions and resource allocation
    - Coordinate with RetryManagerService for failure handling
    """
    
    def __init__(
        self,
        database: AsyncIOMotorDatabase,
        config: Optional[ServiceConfiguration] = None
    ):
        """Initialize JobSchedulerService with database and configuration."""
        service_config = config or ServiceConfiguration(
            service_name="JobSchedulerService",
            heartbeat_interval_seconds=15,
            operation_timeout_seconds=300,
            max_concurrent_operations=50
        )
        
        super().__init__(service_config)
        
        self.database = database
        self.jobs_collection = database.orchestration_jobs
        self.nodes_collection = database.orchestration_nodes
        
        # Scheduling configuration
        self._scheduling_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._active_jobs: Dict[str, OrchestrationJobModel] = {}
        self._job_timers: Dict[str, asyncio.Task] = {}
        
        # Resource tracking
        self._resource_allocations: Dict[str, Dict[str, Any]] = {}
        self._execution_counters: Dict[str, int] = {
            "jobs_scheduled": 0,
            "jobs_started": 0,
            "jobs_completed": 0,
            "jobs_failed": 0
        }
        
        self._logger.info("JobSchedulerService initialized with database connection")
    
    async def _initialize_service(self) -> None:
        """Initialize service-specific components."""
        self._logger.info("Initializing JobSchedulerService")
        
        # Verify database collections
        await self._ensure_collections_exist()
        
        # Load pending jobs from database
        await self._load_pending_jobs()
        
        self._logger.info("JobSchedulerService initialization complete")
    
    async def _start_service(self) -> None:
        """Start service background tasks."""
        self._logger.info("Starting JobSchedulerService background tasks")
        
        # Start scheduling loop
        asyncio.create_task(self._scheduling_loop())
        
        # Start job monitoring loop
        asyncio.create_task(self._job_monitoring_loop())
        
        self._logger.info("JobSchedulerService background tasks started")
    
    async def _stop_service(self) -> None:
        """Stop service and cleanup resources."""
        self._logger.info("Stopping JobSchedulerService")
        
        # Cancel active job timers
        for job_id, timer_task in self._job_timers.items():
            timer_task.cancel()
            try:
                await timer_task
            except asyncio.CancelledError:
                pass
        
        self._job_timers.clear()
        self._active_jobs.clear()
        
        self._logger.info("JobSchedulerService stopped")
    
    async def _health_check(self) -> Dict[str, Any]:
        """Perform health check for scheduler service."""
        queue_size = self._scheduling_queue.qsize()
        active_jobs_count = len(self._active_jobs)
        
        return {
            "scheduling_queue_size": queue_size,
            "active_jobs_count": active_jobs_count,
            "resource_allocations": len(self._resource_allocations),
            "execution_counters": self._execution_counters.copy(),
            "healthy": queue_size < 800 and active_jobs_count < 100
        }
    
    # Core Scheduling Operations
    
    async def schedule_job(
        self,
        job_request: CreateOrchestrationJobRequest,
        triggered_by: str,
        priority: int = 5
    ) -> JobStatusResponse:
        """
        Schedule a new orchestration job for execution.
        
        Args:
            job_request: Job creation request with execution context
            triggered_by: User ID who triggered the job
            priority: Job priority (1=highest, 10=lowest)
            
        Returns:
            JobStatusResponse: Created job with assigned IDs
            
        Raises:
            OrchestrationException: If job cannot be scheduled
        """
        correlation_id = str(uuid.uuid4())
        bound_logger = self._bind_logger_context(
            job_name=job_request.job_name,
            triggered_by=triggered_by,
            correlation_id=correlation_id
        )
        
        try:
            bound_logger.info("Scheduling new orchestration job")
            
            # Generate unique identifiers
            job_id = str(uuid.uuid4())
            trace_id = str(uuid.uuid4())
            execution_id = str(uuid.uuid4())
            
            # Create job model
            job = OrchestrationJobModel(
                job_id=job_id,
                job_name=job_request.job_name,
                job_description=job_request.job_description,
                job_type=job_request.job_type,
                priority=priority,
                tags=job_request.tags,
                execution_context={
                    **job_request.execution_context,
                    "trace_id": trace_id,
                    "execution_id": execution_id,
                    "correlation_id": correlation_id
                },
                test_suite_id=job_request.test_suite_id,
                test_case_ids=job_request.test_case_ids,
                triggered_by=triggered_by,
                triggered_at=datetime.now(timezone.utc),
                resource_requirements=job_request.resource_requirements,
                timeout_ms=job_request.timeout_ms,
                retry_policy_id=job_request.retry_policy_id,
                configuration=job_request.configuration
            )
            
            # Validate job configuration
            await self._validate_job_request(job)
            
            # Save job to database
            await self.jobs_collection.insert_one(job.to_mongo())
            
            # Add to scheduling queue
            await self._scheduling_queue.put(job)
            
            # Update metrics
            self._execution_counters["jobs_scheduled"] += 1
            
            bound_logger.info(f"Job scheduled successfully with ID: {job_id}")
            
            return JobStatusResponse(
                job_id=job_id,
                status=job.status,
                execution_context=job.execution_context,
                scheduled_at=job.scheduled_at,
                created_at=job.created_at,
                priority=job.priority,
                message="Job scheduled successfully"
            )
            
        except Exception as e:
            bound_logger.error(f"Failed to schedule job: {e}")
            raise OrchestrationException(f"Job scheduling failed: {e}")
    
    async def start_job_execution(
        self,
        job_id: str,
        execution_context: Optional[Dict[str, Any]] = None
    ) -> JobStatusResponse:
        """
        Start execution of a scheduled job.
        
        Args:
            job_id: Job identifier to start
            execution_context: Additional execution context
            
        Returns:
            JobStatusResponse: Updated job status
            
        Raises:
            InvalidJobStateError: If job cannot be started
        """
        bound_logger = self._bind_logger_context(job_id=job_id)
        
        try:
            bound_logger.info("Starting job execution")
            
            # Retrieve job from database
            job_doc = await self.jobs_collection.find_one({"job_id": job_id})
            if not job_doc:
                raise OrchestrationException(f"Job not found: {job_id}")
            
            job = OrchestrationJobModel.from_mongo(job_doc)
            if not job:
                raise OrchestrationException(f"Failed to load job: {job_id}")
            
            # Validate state transition
            if not job.can_transition_to(JobStatus.RUNNING):
                raise InvalidJobStateError(job_id, job.status, JobStatus.RUNNING)
            
            # Update execution context
            if execution_context:
                job.execution_context.update(execution_context)
            
            # Allocate resources
            await self._allocate_job_resources(job)
            
            # Transition to running state
            job.transition_state(
                JobStatus.RUNNING,
                reason="Job execution started",
                context={"started_by": "JobSchedulerService"}
            )
            job.started_at = datetime.now(timezone.utc)
            
            # Update in database
            await self.jobs_collection.update_one(
                {"job_id": job_id},
                {"$set": job.to_mongo()}
            )
            
            # Add to active jobs
            self._active_jobs[job_id] = job
            
            # Dispatch job stages
            await self._dispatch_job_stages(job)
            
            # Update metrics
            self._execution_counters["jobs_started"] += 1
            
            bound_logger.info("Job execution started successfully")
            
            return JobStatusResponse(
                job_id=job_id,
                status=job.status,
                execution_context=job.execution_context,
                started_at=job.started_at,
                allocated_resources=job.allocated_resources,
                message="Job execution started"
            )
            
        except Exception as e:
            bound_logger.error(f"Failed to start job execution: {e}")
            if isinstance(e, (InvalidJobStateError, OrchestrationException)):
                raise
            raise OrchestrationException(f"Job start failed: {e}")
    
    async def get_job_progress(self, job_id: str) -> OrchestrationResponse:
        """
        Get current execution progress for a job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            ExecutionProgressResponse: Current progress information
        """
        bound_logger = self._bind_logger_context(job_id=job_id)
        
        try:
            # Get job from active jobs or database
            job = self._active_jobs.get(job_id)
            if not job:
                job_doc = await self.jobs_collection.find_one({"job_id": job_id})
                if not job_doc:
                    raise OrchestrationException(f"Job not found: {job_id}")
                job = OrchestrationJobModel.from_mongo(job_doc)
            
            # Get node execution status
            nodes_cursor = self.nodes_collection.find({"job_id": job_id})
            nodes = await nodes_cursor.to_list(length=None)
            
            # Calculate progress metrics
            total_nodes = len(nodes)
            completed_nodes = len([n for n in nodes if n.get("execution_status") == JobStatus.COMPLETED])
            failed_nodes = len([n for n in nodes if n.get("execution_status") == JobStatus.FAILED])
            
            progress_percentage = (completed_nodes / total_nodes * 100) if total_nodes > 0 else 0
            
            return ExecutionProgressResponse(
                job_id=job_id,
                status=job.status,
                progress_percentage=progress_percentage,
                total_nodes=total_nodes,
                completed_nodes=completed_nodes,
                failed_nodes=failed_nodes,
                current_node_id=job.current_node_id,
                execution_path=job.node_execution_path,
                estimated_completion=self._estimate_completion_time(job, progress_percentage),
                performance_metrics=job.performance_metrics
            )
            
        except Exception as e:
            bound_logger.error(f"Failed to get job progress: {e}")
            raise OrchestrationException(f"Progress retrieval failed: {e}")
    
    # Internal Operations
    
    async def _scheduling_loop(self) -> None:
        """Main scheduling loop processing jobs from queue."""
        self._logger.info("Starting scheduling loop")
        
        while self.lifecycle_state in [ServiceLifecycle.RUNNING, ServiceLifecycle.READY]:
            try:
                # Get job from queue with timeout
                job = await asyncio.wait_for(
                    self._scheduling_queue.get(),
                    timeout=5.0
                )
                
                # Process scheduled job
                await self._process_scheduled_job(job)
                
            except asyncio.TimeoutError:
                # Normal timeout, continue loop
                continue
            except Exception as e:
                self._logger.error(f"Error in scheduling loop: {e}")
                await asyncio.sleep(1)
    
    async def _job_monitoring_loop(self) -> None:
        """Monitor active jobs for timeouts and state changes."""
        self._logger.info("Starting job monitoring loop")
        
        while self.lifecycle_state in [ServiceLifecycle.RUNNING, ServiceLifecycle.READY]:
            try:
                current_time = datetime.now(timezone.utc)
                jobs_to_timeout = []
                
                # Check for job timeouts
                for job_id, job in self._active_jobs.items():
                    if job.timeout_ms and job.started_at:
                        timeout_threshold = job.started_at + timedelta(milliseconds=job.timeout_ms)
                        if current_time > timeout_threshold:
                            jobs_to_timeout.append(job_id)
                
                # Handle timed out jobs
                for job_id in jobs_to_timeout:
                    await self._handle_job_timeout(job_id)
                
                # Sleep before next check
                await asyncio.sleep(30)
                
            except Exception as e:
                self._logger.error(f"Error in job monitoring loop: {e}")
                await asyncio.sleep(5)
    
    async def _process_scheduled_job(self, job: OrchestrationJobModel) -> None:
        """Process a job from the scheduling queue."""
        bound_logger = self._bind_logger_context(job_id=job.job_id)
        
        try:
            bound_logger.info("Processing scheduled job")
            
            # Check if job should be executed immediately or scheduled
            if job.scheduled_at and job.scheduled_at > datetime.now(timezone.utc):
                # Schedule for future execution
                delay_seconds = (job.scheduled_at - datetime.now(timezone.utc)).total_seconds()
                timer_task = asyncio.create_task(self._schedule_delayed_execution(job, delay_seconds))
                self._job_timers[job.job_id] = timer_task
                bound_logger.info(f"Job scheduled for delayed execution in {delay_seconds} seconds")
            else:
                # Execute immediately
                await self.start_job_execution(job.job_id)
            
        except Exception as e:
            bound_logger.error(f"Failed to process scheduled job: {e}")
            await self._mark_job_failed(job.job_id, f"Scheduling failed: {e}")
    
    async def _schedule_delayed_execution(self, job: OrchestrationJobModel, delay_seconds: float) -> None:
        """Schedule job for delayed execution."""
        try:
            await asyncio.sleep(delay_seconds)
            await self.start_job_execution(job.job_id)
        except asyncio.CancelledError:
            self._logger.info(f"Delayed execution cancelled for job: {job.job_id}")
        except Exception as e:
            self._logger.error(f"Failed delayed execution for job {job.job_id}: {e}")
            await self._mark_job_failed(job.job_id, f"Delayed execution failed: {e}")
    
    async def _dispatch_job_stages(self, job: OrchestrationJobModel) -> None:
        """Dispatch job stages for execution."""
        bound_logger = self._bind_logger_context(job_id=job.job_id)
        
        try:
            bound_logger.info("Dispatching job stages")
            
            # Get job nodes ordered by execution sequence
            nodes_cursor = self.nodes_collection.find(
                {"job_id": job.job_id}
            ).sort("node_order", 1)
            
            nodes = await nodes_cursor.to_list(length=None)
            
            if not nodes:
                bound_logger.warning("No nodes found for job, marking as completed")
                await self._mark_job_completed(job.job_id)
                return
            
            # Start execution with root nodes (nodes with no dependencies)
            root_nodes = [
                node for node in nodes 
                if not node.get("parent_nodes") or len(node.get("parent_nodes", [])) == 0
            ]
            
            for node in root_nodes:
                await self._dispatch_node_execution(job, node)
            
            bound_logger.info(f"Dispatched {len(root_nodes)} root nodes for execution")
            
        except Exception as e:
            bound_logger.error(f"Failed to dispatch job stages: {e}")
            await self._mark_job_failed(job.job_id, f"Stage dispatch failed: {e}")
    
    async def _dispatch_node_execution(self, job: OrchestrationJobModel, node: Dict[str, Any]) -> None:
        """Dispatch a single node for execution."""
        # This would integrate with the execution engine
        # For now, we'll mark nodes as queued and let the execution engine pick them up
        await self.nodes_collection.update_one(
            {"node_id": node["node_id"]},
            {
                "$set": {
                    "execution_status": JobStatus.QUEUED,
                    "started_at": datetime.now(timezone.utc)
                }
            }
        )
    
    async def _allocate_job_resources(self, job: OrchestrationJobModel) -> None:
        """Allocate required resources for job execution."""
        # Simplified resource allocation - in production this would integrate
        # with a resource manager service
        allocation = {
            "allocated_at": datetime.now(timezone.utc),
            "execution_environment": job.execution_environment or "default",
            "resource_pool": "shared",
            "allocation_id": str(uuid.uuid4())
        }
        
        job.allocated_resources = allocation
        self._resource_allocations[job.job_id] = allocation
    
    async def _validate_job_request(self, job: OrchestrationJobModel) -> None:
        """Validate job request for scheduling."""
        # Validate required fields
        if not job.job_name or not job.job_type:
            raise OrchestrationException("Job name and type are required")
        
        # Validate priority range
        if not 1 <= job.priority <= 10:
            raise OrchestrationException("Priority must be between 1 and 10")
        
        # Validate timeout if specified
        if job.timeout_ms and job.timeout_ms < 1000:
            raise OrchestrationException("Timeout must be at least 1000ms")
    
    async def _handle_job_timeout(self, job_id: str) -> None:
        """Handle job timeout."""
        bound_logger = self._bind_logger_context(job_id=job_id)
        
        try:
            bound_logger.warning("Job execution timeout detected")
            
            job = self._active_jobs.get(job_id)
            if job and job.can_transition_to(JobStatus.TIMEOUT):
                job.transition_state(
                    JobStatus.TIMEOUT,
                    reason="Job execution timeout",
                    context={"timeout_ms": job.timeout_ms}
                )
                
                await self.jobs_collection.update_one(
                    {"job_id": job_id},
                    {"$set": job.to_mongo()}
                )
                
                # Remove from active jobs
                self._active_jobs.pop(job_id, None)
                
                bound_logger.info("Job marked as timed out")
            
        except Exception as e:
            bound_logger.error(f"Failed to handle job timeout: {e}")
    
    async def _mark_job_completed(self, job_id: str) -> None:
        """Mark job as completed."""
        bound_logger = self._bind_logger_context(job_id=job_id)
        
        try:
            job = self._active_jobs.get(job_id)
            if job and job.can_transition_to(JobStatus.COMPLETED):
                job.transition_state(JobStatus.COMPLETED, reason="Job execution completed")
                job.completed_at = datetime.now(timezone.utc)
                
                if job.started_at:
                    duration = (job.completed_at - job.started_at).total_seconds() * 1000
                    job.actual_duration_ms = int(duration)
                
                await self.jobs_collection.update_one(
                    {"job_id": job_id},
                    {"$set": job.to_mongo()}
                )
                
                self._active_jobs.pop(job_id, None)
                self._execution_counters["jobs_completed"] += 1
                
                bound_logger.info("Job marked as completed")
        
        except Exception as e:
            bound_logger.error(f"Failed to mark job completed: {e}")
    
    async def _mark_job_failed(self, job_id: str, reason: str) -> None:
        """Mark job as failed."""
        bound_logger = self._bind_logger_context(job_id=job_id)
        
        try:
            job = self._active_jobs.get(job_id)
            if not job:
                job_doc = await self.jobs_collection.find_one({"job_id": job_id})
                if job_doc:
                    job = OrchestrationJobModel.from_mongo(job_doc)
            
            if job and job.can_transition_to(JobStatus.FAILED):
                job.transition_state(JobStatus.FAILED, reason=reason)
                job.last_failure_reason = reason
                
                await self.jobs_collection.update_one(
                    {"job_id": job_id},
                    {"$set": job.to_mongo()}
                )
                
                self._active_jobs.pop(job_id, None)
                self._execution_counters["jobs_failed"] += 1
                
                bound_logger.info(f"Job marked as failed: {reason}")
        
        except Exception as e:
            bound_logger.error(f"Failed to mark job failed: {e}")
    
    async def _estimate_completion_time(
        self,
        job: OrchestrationJobModel,
        progress_percentage: float
    ) -> Optional[datetime]:
        """Estimate job completion time based on progress."""
        if not job.started_at or progress_percentage <= 0:
            return None
        
        elapsed = (datetime.now(timezone.utc) - job.started_at).total_seconds()
        estimated_total = elapsed / (progress_percentage / 100)
        remaining = estimated_total - elapsed
        
        return datetime.now(timezone.utc) + timedelta(seconds=remaining)
    
    async def _ensure_collections_exist(self) -> None:
        """Ensure required MongoDB collections exist."""
        collections = await self.database.list_collection_names()
        
        if "orchestration_jobs" not in collections:
            await self.database.create_collection("orchestration_jobs")
        
        if "orchestration_nodes" not in collections:
            await self.database.create_collection("orchestration_nodes")
    
    async def _load_pending_jobs(self) -> None:
        """Load pending jobs from database on startup."""
        pending_cursor = self.jobs_collection.find({
            "status": {"$in": [JobStatus.PENDING, JobStatus.QUEUED, JobStatus.SCHEDULED]}
        })
        
        pending_jobs = await pending_cursor.to_list(length=None)
        
        for job_doc in pending_jobs:
            job = OrchestrationJobModel.from_mongo(job_doc)
            if job:
                await self._scheduling_queue.put(job)
        
        self._logger.info(f"Loaded {len(pending_jobs)} pending jobs")
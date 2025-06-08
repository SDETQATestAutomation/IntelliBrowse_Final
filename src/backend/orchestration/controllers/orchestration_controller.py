"""
Orchestration Controller Module

This module implements the OrchestrationController class which acts as the HTTP boundary
for the orchestration engine. It handles request validation, user authentication, and
asynchronous orchestration job submission. This controller connects external triggers
to the DAG Execution Engine via FastAPI-compatible endpoints.

Key Features:
- JWT-based authentication for all endpoints
- Comprehensive request/response validation using Pydantic schemas
- Integration with OrchestrationService for business logic
- Structured error handling with FastAPI HTTPException
- Audit logging with correlation tracking
- SRP compliance with dependency injection pattern
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

from fastapi import HTTPException, status, Depends
from bson import ObjectId

from ..schemas.orchestration_schemas import (
    CreateOrchestrationJobRequest,
    JobStatusResponse,
    JobListResponse,
    OrchestrationResponse,
    ErrorResponse
)
from ..services.base_orchestration_service import BaseOrchestrationService
from ..services.job_scheduler_service import JobSchedulerService
from ..engine.execution_state_tracker import ExecutionStateTracker
from ..models.orchestration_models import (
    OrchestrationJobModel,
    JobStatus,
    InvalidJobStateError,
    OrchestrationException
)
from ...auth.dependencies.auth_dependencies import get_current_user
from ...auth.schemas.auth_responses import UserResponse


logger = logging.getLogger(__name__)


class JobCancellationError(Exception):
    """Exception raised when job cancellation fails."""
    pass


class OrchestrationController:
    """
    HTTP controller for orchestration engine operations.
    
    This controller acts as the FastAPI boundary layer for orchestration operations,
    handling request validation, authentication, and routing to appropriate services.
    It follows SRP by delegating all business logic to service layers.
    
    Responsibilities:
    - HTTP request/response handling
    - Request validation using Pydantic schemas
    - JWT authentication enforcement
    - Error handling and HTTP status code mapping
    - Audit logging with correlation tracking
    - Integration with DAG execution engine
    """
    
    def __init__(
        self,
        orchestration_service: BaseOrchestrationService,
        job_scheduler_service: JobSchedulerService,
        execution_state_tracker: ExecutionStateTracker
    ):
        """
        Initialize the orchestration controller.
        
        Args:
            orchestration_service: Base orchestration service for core operations
            job_scheduler_service: Job scheduling service for job management
            execution_state_tracker: State tracking service for job monitoring
        """
        self.orchestration_service = orchestration_service
        self.job_scheduler_service = job_scheduler_service
        self.execution_state_tracker = execution_state_tracker
        self.logger = logger.getChild(self.__class__.__name__)
    
    async def submit_orchestration_job(
        self,
        request: CreateOrchestrationJobRequest,
        current_user: UserResponse = Depends(get_current_user)
    ) -> OrchestrationResponse:
        """
        Submit a new orchestration job for execution.
        
        This handler validates the incoming job request, extracts user information from
        the JWT token, and forwards the validated request to the OrchestrationService
        for asynchronous processing. It returns job metadata including the assigned
        job ID and initial status.
        
        Args:
            request: Job creation request with validation
            current_user: Authenticated user from JWT token
            
        Returns:
            OrchestrationResponse: Job submission response with metadata
            
        Raises:
            HTTPException: 400 for validation errors, 403 for authorization errors,
                          500 for internal processing errors
        """
        request_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        self.logger.info(
            "Starting job submission",
            extra={
                "request_id": request_id,
                "user_id": current_user.id,
                "job_name": request.job_name,
                "job_type": request.job_type,
                "priority": request.priority
            }
        )
        
        try:
            # Validate job type and target entity relationships
            await self._validate_job_submission(request, current_user)
            
            # Submit job to scheduler service
            job_response = await self.job_scheduler_service.start_job_async(
                request=request,
                user_id=current_user.id,
                correlation_id=request_id
            )
            
            # Calculate request latency
            end_time = datetime.utcnow()
            latency_ms = (end_time - start_time).total_seconds() * 1000
            
            self.logger.info(
                "Job submission successful",
                extra={
                    "request_id": request_id,
                    "user_id": current_user.id,
                    "job_id": job_response.get("job_id"),
                    "latency_ms": latency_ms
                }
            )
            
            return OrchestrationResponse(
                success=True,
                message=f"Orchestration job '{request.job_name}' submitted successfully",
                data={
                    "job_id": job_response.get("job_id"),
                    "status": job_response.get("status", JobStatus.PENDING.value),
                    "submitted_at": job_response.get("triggered_at"),
                    "priority": request.priority,
                    "estimated_duration_ms": request.estimated_duration_ms
                },
                request_id=request_id
            )
            
        except ValueError as e:
            self.logger.warning(
                "Job submission validation failed",
                extra={
                    "request_id": request_id,
                    "user_id": current_user.id,
                    "error": str(e)
                }
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Job validation failed: {str(e)}"
            )
            
        except PermissionError as e:
            self.logger.warning(
                "Job submission authorization failed",
                extra={
                    "request_id": request_id,
                    "user_id": current_user.id,
                    "error": str(e)
                }
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions: {str(e)}"
            )
            
        except OrchestrationException as e:
            self.logger.error(
                "Job submission orchestration error",
                extra={
                    "request_id": request_id,
                    "user_id": current_user.id,
                    "error": str(e)
                },
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Orchestration error: {str(e)}"
            )
            
        except Exception as e:
            self.logger.error(
                "Job submission unexpected error",
                extra={
                    "request_id": request_id,
                    "user_id": current_user.id,
                    "error": str(e)
                },
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error during job submission"
            )
    
    async def get_job_status(
        self,
        job_id: str,
        current_user: UserResponse = Depends(get_current_user)
    ) -> JobStatusResponse:
        """
        Retrieve the status and details of a specific orchestration job.
        
        This handler validates the job ID format, checks job ownership against
        the authenticated user, and retrieves comprehensive job metadata including
        current status, progress, and execution results.
        
        Args:
            job_id: Unique job identifier (validated as ObjectId)
            current_user: Authenticated user from JWT token
            
        Returns:
            JobStatusResponse: Comprehensive job status information
            
        Raises:
            HTTPException: 400 for invalid job ID, 403 for ownership violations,
                          404 for job not found, 500 for internal errors
        """
        request_id = str(uuid.uuid4())
        
        self.logger.info(
            "Retrieving job status",
            extra={
                "request_id": request_id,
                "user_id": current_user.id,
                "job_id": job_id
            }
        )
        
        try:
            # Validate job ID format
            if not ObjectId.is_valid(job_id):
                raise ValueError(f"Invalid job ID format: {job_id}")
            
            # Retrieve job from database
            job = await self.orchestration_service.get_job_by_id(
                job_id=job_id,
                user_id=current_user.id
            )
            
            if not job:
                self.logger.warning(
                    "Job not found",
                    extra={
                        "request_id": request_id,
                        "user_id": current_user.id,
                        "job_id": job_id
                    }
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Job {job_id} not found or access denied"
                )
            
            # Validate job ownership
            await self._validate_job_ownership(job, current_user)
            
            # Get execution state information
            execution_state = await self.execution_state_tracker.get_execution_graph(job_id)
            
            # Build comprehensive status response
            status_response = await self._build_job_status_response(job, execution_state)
            
            self.logger.info(
                "Job status retrieved successfully",
                extra={
                    "request_id": request_id,
                    "user_id": current_user.id,
                    "job_id": job_id,
                    "status": status_response.status.value
                }
            )
            
            return status_response
            
        except ValueError as e:
            self.logger.warning(
                "Job status validation failed",
                extra={
                    "request_id": request_id,
                    "user_id": current_user.id,
                    "job_id": job_id,
                    "error": str(e)
                }
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
            
        except PermissionError as e:
            self.logger.warning(
                "Job status access denied",
                extra={
                    "request_id": request_id,
                    "user_id": current_user.id,
                    "job_id": job_id,
                    "error": str(e)
                }
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(e)
            )
            
        except Exception as e:
            self.logger.error(
                "Job status retrieval error",
                extra={
                    "request_id": request_id,
                    "user_id": current_user.id,
                    "job_id": job_id,
                    "error": str(e)
                },
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error during job status retrieval"
            )
    
    async def cancel_orchestration_job(
        self,
        job_id: str,
        current_user: UserResponse = Depends(get_current_user)
    ) -> OrchestrationResponse:
        """
        Cancel a running orchestration job.
        
        This handler validates job ownership, checks if the job can be cancelled,
        and forwards the cancellation request to the ExecutionStateTracker for
        graceful job termination.
        
        Args:
            job_id: Unique job identifier
            current_user: Authenticated user from JWT token
            
        Returns:
            OrchestrationResponse: Cancellation confirmation
            
        Raises:
            HTTPException: 400 for invalid job ID, 403 for ownership violations,
                          409 for jobs that cannot be cancelled, 500 for internal errors
        """
        request_id = str(uuid.uuid4())
        
        self.logger.info(
            "Cancelling orchestration job",
            extra={
                "request_id": request_id,
                "user_id": current_user.id,
                "job_id": job_id
            }
        )
        
        try:
            # Validate job ID format
            if not ObjectId.is_valid(job_id):
                raise ValueError(f"Invalid job ID format: {job_id}")
            
            # Retrieve and validate job ownership
            job = await self.orchestration_service.get_job_by_id(
                job_id=job_id,
                user_id=current_user.id
            )
            
            if not job:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Job {job_id} not found or access denied"
                )
            
            await self._validate_job_ownership(job, current_user)
            
            # Check if job can be cancelled
            if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Job {job_id} cannot be cancelled in {job.status.value} state"
                )
            
            # Perform cancellation through state tracker
            cancellation_result = await self.execution_state_tracker.cancel_job(job_id)
            
            if not cancellation_result.get("success", False):
                raise JobCancellationError(
                    f"Failed to cancel job {job_id}: {cancellation_result.get('error', 'Unknown error')}"
                )
            
            self.logger.info(
                "Job cancellation successful",
                extra={
                    "request_id": request_id,
                    "user_id": current_user.id,
                    "job_id": job_id
                }
            )
            
            return OrchestrationResponse(
                success=True,
                message=f"Job {job_id} cancellation initiated successfully",
                data={
                    "job_id": job_id,
                    "cancelled_at": datetime.utcnow(),
                    "cancellation_reason": "User requested"
                },
                request_id=request_id
            )
            
        except ValueError as e:
            self.logger.warning(
                "Job cancellation validation failed",
                extra={
                    "request_id": request_id,
                    "user_id": current_user.id,
                    "job_id": job_id,
                    "error": str(e)
                }
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
            
        except JobCancellationError as e:
            self.logger.error(
                "Job cancellation failed",
                extra={
                    "request_id": request_id,
                    "user_id": current_user.id,
                    "job_id": job_id,
                    "error": str(e)
                }
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )
            
        except Exception as e:
            self.logger.error(
                "Job cancellation unexpected error",
                extra={
                    "request_id": request_id,
                    "user_id": current_user.id,
                    "job_id": job_id,
                    "error": str(e)
                },
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error during job cancellation"
            )
    
    async def list_orchestration_jobs(
        self,
        status_filter: Optional[str] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        target_type: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        current_user: UserResponse = Depends(get_current_user)
    ) -> JobListResponse:
        """
        List orchestration jobs with filtering and pagination support.
        
        This handler provides comprehensive job listing with support for various
        filters including status, creation date range, and target type. Results
        are paginated and scoped to the authenticated user.
        
        Args:
            status_filter: Filter by job status (optional)
            created_after: Filter jobs created after this date (optional)
            created_before: Filter jobs created before this date (optional)
            target_type: Filter by target entity type (optional)
            limit: Maximum number of results (1-100, default 20)
            offset: Number of results to skip (default 0)
            current_user: Authenticated user from JWT token
            
        Returns:
            JobListResponse: Paginated list of job summaries
            
        Raises:
            HTTPException: 400 for invalid parameters, 500 for internal errors
        """
        request_id = str(uuid.uuid4())
        
        self.logger.info(
            "Listing orchestration jobs",
            extra={
                "request_id": request_id,
                "user_id": current_user.id,
                "status_filter": status_filter,
                "target_type": target_type,
                "limit": limit,
                "offset": offset
            }
        )
        
        try:
            # Validate pagination parameters
            if limit < 1 or limit > 100:
                raise ValueError("Limit must be between 1 and 100")
            if offset < 0:
                raise ValueError("Offset must be non-negative")
            
            # Validate status filter
            if status_filter and status_filter not in [s.value for s in JobStatus]:
                raise ValueError(f"Invalid status filter: {status_filter}")
            
            # Build filter criteria
            filter_criteria = {
                "triggered_by": current_user.id
            }
            
            if status_filter:
                filter_criteria["status"] = status_filter
            
            if created_after:
                filter_criteria.setdefault("triggered_at", {})["$gte"] = created_after
            
            if created_before:
                filter_criteria.setdefault("triggered_at", {})["$lte"] = created_before
            
            if target_type:
                filter_criteria["job_type"] = target_type
            
            # Retrieve jobs from service
            jobs_result = await self.orchestration_service.list_jobs(
                filter_criteria=filter_criteria,
                limit=limit,
                offset=offset,
                sort_by="triggered_at",
                sort_order="desc"
            )
            
            # Build job status responses
            job_responses = []
            for job in jobs_result.get("jobs", []):
                execution_state = await self.execution_state_tracker.get_execution_graph(
                    str(job.id)
                )
                status_response = await self._build_job_status_response(job, execution_state)
                job_responses.append(status_response)
            
            total_count = jobs_result.get("total_count", 0)
            page = (offset // limit) + 1
            has_next = (offset + limit) < total_count
            
            self.logger.info(
                "Job listing successful",
                extra={
                    "request_id": request_id,
                    "user_id": current_user.id,
                    "total_count": total_count,
                    "returned_count": len(job_responses),
                    "page": page
                }
            )
            
            return JobListResponse(
                jobs=job_responses,
                total_count=total_count,
                page=page,
                page_size=limit,
                has_next=has_next
            )
            
        except ValueError as e:
            self.logger.warning(
                "Job listing validation failed",
                extra={
                    "request_id": request_id,
                    "user_id": current_user.id,
                    "error": str(e)
                }
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
            
        except Exception as e:
            self.logger.error(
                "Job listing unexpected error",
                extra={
                    "request_id": request_id,
                    "user_id": current_user.id,
                    "error": str(e)
                },
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error during job listing"
            )
    
    # Private helper methods
    
    async def _validate_job_submission(
        self,
        request: CreateOrchestrationJobRequest,
        current_user: UserResponse
    ) -> None:
        """
        Validate job submission request and user permissions.
        
        Args:
            request: Job creation request
            current_user: Authenticated user
            
        Raises:
            ValueError: For validation errors
            PermissionError: For authorization errors
        """
        # Validate job type
        valid_job_types = [
            "test_execution", "test_suite_execution", "test_item_validation",
            "data_processing", "notification_trigger", "cleanup_operation"
        ]
        
        if request.job_type not in valid_job_types:
            raise ValueError(f"Invalid job type: {request.job_type}")
        
        # Validate target entity relationships
        if request.job_type == "test_execution" and not request.test_case_ids:
            raise ValueError("test_execution jobs require at least one test case ID")
        
        if request.job_type == "test_suite_execution" and not request.test_suite_id:
            raise ValueError("test_suite_execution jobs require a test suite ID")
        
        # Validate priority constraints
        if request.priority < 1 or request.priority > 10:
            raise ValueError("Priority must be between 1 (highest) and 10 (lowest)")
        
        # Validate timeout constraints
        if request.timeout_ms and request.timeout_ms < 1000:
            raise ValueError("Timeout must be at least 1 second (1000ms)")
        
        # Check user permissions for target entities
        # Note: This would integrate with authorization service in a real implementation
        if not current_user.is_active:
            raise PermissionError("User account is not active")
    
    async def _validate_job_ownership(
        self,
        job: OrchestrationJobModel,
        current_user: UserResponse
    ) -> None:
        """
        Validate that the current user owns the specified job.
        
        Args:
            job: Job model to validate
            current_user: Authenticated user
            
        Raises:
            PermissionError: If user doesn't own the job
        """
        if job.triggered_by != current_user.id:
            raise PermissionError(f"Access denied to job {job.id}")
    
    async def _build_job_status_response(
        self,
        job: OrchestrationJobModel,
        execution_state: Optional[Dict[str, Any]]
    ) -> JobStatusResponse:
        """
        Build a comprehensive job status response.
        
        Args:
            job: Job model
            execution_state: Execution state from state tracker
            
        Returns:
            JobStatusResponse: Comprehensive job status information
        """
        # Calculate progress percentage
        progress_percentage = None
        current_node_id = None
        
        if execution_state:
            nodes = execution_state.get("nodes", {})
            total_nodes = len(nodes)
            completed_nodes = sum(
                1 for node in nodes.values()
                if node.get("status") in ["completed", "skipped"]
            )
            
            if total_nodes > 0:
                progress_percentage = (completed_nodes / total_nodes) * 100
            
            # Find currently executing node
            for node_id, node_data in nodes.items():
                if node_data.get("status") == "running":
                    current_node_id = node_id
                    break
        
        return JobStatusResponse(
            job_id=str(job.id),
            job_name=job.job_name,
            job_type=job.job_type,
            status=job.status,
            priority=job.priority,
            triggered_at=job.triggered_at,
            scheduled_at=job.scheduled_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            progress_percentage=progress_percentage,
            current_node_id=current_node_id,
            retry_count=job.retry_count,
            max_retries=job.max_retries,
            execution_results=job.execution_results or {},
            error_details=job.error_details,
            triggered_by=job.triggered_by,
            tags=job.tags or [],
            created_at=job.triggered_at,
            updated_at=job.updated_at
        )


class OrchestrationControllerFactory:
    """
    Factory class for creating OrchestrationController instances with dependency injection.
    
    This factory ensures proper service dependency resolution and provides a clean
    interface for controller instantiation in FastAPI dependency injection.
    """
    
    @staticmethod
    async def create_controller(
        orchestration_service: BaseOrchestrationService = Depends(),
        job_scheduler_service: JobSchedulerService = Depends(),
        execution_state_tracker: ExecutionStateTracker = Depends()
    ) -> OrchestrationController:
        """
        Create an OrchestrationController instance with injected dependencies.
        
        Args:
            orchestration_service: Base orchestration service
            job_scheduler_service: Job scheduling service
            execution_state_tracker: Execution state tracking service
            
        Returns:
            OrchestrationController: Configured controller instance
        """
        return OrchestrationController(
            orchestration_service=orchestration_service,
            job_scheduler_service=job_scheduler_service,
            execution_state_tracker=execution_state_tracker
        )
"""
Scheduled Task Runner Engine - Concrete Scheduler Service

Implements the concrete business logic service for scheduler operations.
Provides high-level interface for controllers with full implementation
of trigger management, execution tracking, and integration coordination.

This service acts as the main business logic layer between controllers
and the underlying engine services (TriggerEngineService, LockManagerService, 
JobExecutionService) following clean architecture principles.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid

from ...config.logging import get_logger
from ...auth.schemas.auth_responses import UserResponse
from ..schemas.trigger_schemas import (
    CreateScheduledTriggerRequest,
    UpdateScheduledTriggerRequest,
    ScheduledTriggerResponse,
    ExecutionStatusResponse,
    ExecutionHistoryResponse,
    BaseResponseSchema
)
from ..models.trigger_model import (
    ScheduledTriggerModel,
    ScheduledJobModel,
    TaskStatus,
    ExecutionStatus,
    TriggerType
)
from .base_scheduler_service import (
    SchedulerServiceException,
    TriggerEngineService,
    LockManagerService,
    JobExecutionService
)

logger = get_logger(__name__)


class SchedulerService:
    """
    Concrete scheduler service implementation.
    
    Provides business logic for trigger management, job execution coordination,
    and integration with the orchestration engine. Acts as the main service
    layer for controller operations with comprehensive error handling.
    """
    
    def __init__(
        self,
        trigger_engine_service: TriggerEngineService,
        lock_manager_service: LockManagerService,
        job_execution_service: JobExecutionService
    ):
        """
        Initialize scheduler service with injected dependencies.
        
        Args:
            trigger_engine_service: Service for trigger resolution and queue management
            lock_manager_service: Service for distributed locking operations
            job_execution_service: Service for job lifecycle management
        """
        self.trigger_engine_service = trigger_engine_service
        self.lock_manager_service = lock_manager_service
        self.job_execution_service = job_execution_service
        
        logger.info("SchedulerService initialized successfully")
    
    async def create_scheduled_trigger(
        self, 
        request: CreateScheduledTriggerRequest,
        user_id: str
    ) -> ScheduledTriggerResponse:
        """
        Create a new scheduled trigger.
        
        Args:
            request: Trigger creation request
            user_id: ID of the user creating the trigger
            
        Returns:
            ScheduledTriggerResponse with created trigger data
            
        Raises:
            SchedulerServiceException: If creation fails
        """
        logger.info(
            f"Creating scheduled trigger: {request.name}",
            extra={
                "user_id": user_id,
                "trigger_name": request.name,
                "trigger_type": request.trigger_config.trigger_type,
                "task_type": request.execution_config.task_type
            }
        )
        
        try:
            # Create trigger model instance
            trigger_id = str(uuid.uuid4())
            now = datetime.utcnow()
            
            # Phase 3 TODO: Implement trigger creation logic
            # For now, return a placeholder response
            trigger_data = {
                "id": trigger_id,
                "name": request.name,
                "description": request.description,
                "status": TaskStatus.ACTIVE.value,
                "trigger_type": request.trigger_config.trigger_type.value,
                "created_by": user_id,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "trigger_config": request.trigger_config.model_dump(),
                "execution_config": request.execution_config.model_dump(),
                "retry_policy": request.retry_policy.model_dump() if request.retry_policy else None,
                "tags": request.tags,
                "metadata": request.metadata
            }
            
            # Schedule the trigger in the engine
            # Phase 3 TODO: Implement actual scheduling
            logger.info(f"Scheduled trigger created successfully: {trigger_id}")
            
            return ScheduledTriggerResponse(
                success=True,
                message=f"Scheduled trigger '{request.name}' created successfully",
                data=trigger_data
            )
            
        except Exception as e:
            logger.error(
                f"Error creating scheduled trigger: {e}",
                extra={
                    "user_id": user_id,
                    "trigger_name": request.name,
                    "error": str(e)
                },
                exc_info=True
            )
            raise SchedulerServiceException(
                f"Failed to create scheduled trigger: {e}",
                service_name="SchedulerService",
                operation="create_scheduled_trigger"
            )
    
    async def update_scheduled_trigger(
        self,
        trigger_id: str,
        request: UpdateScheduledTriggerRequest,
        user_id: str
    ) -> ScheduledTriggerResponse:
        """
        Update an existing scheduled trigger.
        
        Args:
            trigger_id: ID of the trigger to update
            request: Trigger update request
            user_id: ID of the user updating the trigger
            
        Returns:
            ScheduledTriggerResponse with updated trigger data
            
        Raises:
            SchedulerServiceException: If update fails
        """
        logger.info(
            f"Updating scheduled trigger: {trigger_id}",
            extra={
                "user_id": user_id,
                "trigger_id": trigger_id,
                "update_fields": [k for k, v in request.model_dump(exclude_none=True).items() if v is not None]
            }
        )
        
        try:
            # Phase 3 TODO: Implement trigger update logic
            # For now, return a placeholder response
            now = datetime.utcnow()
            
            trigger_data = {
                "id": trigger_id,
                "name": request.name or "Updated Trigger",
                "description": request.description,
                "status": request.status.value if request.status else TaskStatus.ACTIVE.value,
                "updated_by": user_id,
                "updated_at": now.isoformat(),
                "trigger_config": request.trigger_config.model_dump() if request.trigger_config else {},
                "execution_config": request.execution_config.model_dump() if request.execution_config else {},
                "retry_policy": request.retry_policy.model_dump() if request.retry_policy else None,
                "tags": request.tags or [],
                "metadata": request.metadata or {}
            }
            
            logger.info(f"Scheduled trigger updated successfully: {trigger_id}")
            
            return ScheduledTriggerResponse(
                success=True,
                message=f"Scheduled trigger '{trigger_id}' updated successfully",
                data=trigger_data
            )
            
        except Exception as e:
            logger.error(
                f"Error updating scheduled trigger: {e}",
                extra={
                    "user_id": user_id,
                    "trigger_id": trigger_id,
                    "error": str(e)
                },
                exc_info=True
            )
            raise SchedulerServiceException(
                f"Failed to update scheduled trigger: {e}",
                service_name="SchedulerService",
                operation="update_scheduled_trigger"
            )
    
    async def delete_scheduled_trigger(
        self,
        trigger_id: str,
        user_id: str
    ) -> BaseResponseSchema:
        """
        Delete a scheduled trigger.
        
        Args:
            trigger_id: ID of the trigger to delete
            user_id: ID of the user deleting the trigger
            
        Returns:
            BaseResponseSchema confirming deletion
            
        Raises:
            SchedulerServiceException: If deletion fails
        """
        logger.info(
            f"Deleting scheduled trigger: {trigger_id}",
            extra={
                "user_id": user_id,
                "trigger_id": trigger_id
            }
        )
        
        try:
            # Phase 3 TODO: Implement trigger deletion logic
            # For now, return a placeholder response
            
            logger.info(f"Scheduled trigger deleted successfully: {trigger_id}")
            
            return BaseResponseSchema(
                success=True,
                message=f"Scheduled trigger '{trigger_id}' deleted successfully"
            )
            
        except Exception as e:
            logger.error(
                f"Error deleting scheduled trigger: {e}",
                extra={
                    "user_id": user_id,
                    "trigger_id": trigger_id,
                    "error": str(e)
                },
                exc_info=True
            )
            raise SchedulerServiceException(
                f"Failed to delete scheduled trigger: {e}",
                service_name="SchedulerService",
                operation="delete_scheduled_trigger"
            )
    
    async def manual_trigger_execution(
        self,
        trigger_id: str,
        user_id: str,
        execution_parameters: Optional[Dict[str, Any]] = None
    ) -> ExecutionStatusResponse:
        """
        Manually trigger execution of a scheduled trigger.
        
        Args:
            trigger_id: ID of the trigger to execute
            user_id: ID of the user triggering execution
            execution_parameters: Optional parameters for execution
            
        Returns:
            ExecutionStatusResponse with execution status
            
        Raises:
            SchedulerServiceException: If trigger execution fails
        """
        logger.info(
            f"Manual trigger execution requested: {trigger_id}",
            extra={
                "user_id": user_id,
                "trigger_id": trigger_id,
                "has_custom_parameters": execution_parameters is not None
            }
        )
        
        try:
            # Phase 3 TODO: Implement manual trigger execution logic
            # For now, return a placeholder response
            job_id = str(uuid.uuid4())
            now = datetime.utcnow()
            
            execution_data = {
                "job_id": job_id,
                "trigger_id": trigger_id,
                "status": ExecutionStatus.RUNNING.value,
                "started_at": now.isoformat(),
                "estimated_completion": (now.replace(minute=now.minute + 30)).isoformat(),
                "priority": 1,  # High priority for manual executions
                "worker_instance": "worker-manual-01",
                "execution_parameters": execution_parameters or {},
                "triggered_by": user_id,
                "trigger_type": "manual"
            }
            
            logger.info(
                f"Manual trigger execution initiated: {job_id}",
                extra={
                    "job_id": job_id,
                    "trigger_id": trigger_id,
                    "user_id": user_id
                }
            )
            
            return ExecutionStatusResponse(
                success=True,
                message=f"Trigger execution initiated successfully for trigger '{trigger_id}'",
                data=execution_data
            )
            
        except Exception as e:
            logger.error(
                f"Error initiating manual trigger execution: {e}",
                extra={
                    "user_id": user_id,
                    "trigger_id": trigger_id,
                    "error": str(e)
                },
                exc_info=True
            )
            raise SchedulerServiceException(
                f"Failed to initiate trigger execution: {e}",
                service_name="SchedulerService",
                operation="manual_trigger_execution"
            )
    
    async def get_trigger_history(
        self,
        trigger_id: str,
        user_id: str,
        page: int = 1,
        page_size: int = 20
    ) -> ExecutionHistoryResponse:
        """
        Get execution history for a scheduled trigger.
        
        Args:
            trigger_id: ID of the trigger
            user_id: ID of the user requesting history
            page: Page number for pagination
            page_size: Number of records per page
            
        Returns:
            ExecutionHistoryResponse with execution history
            
        Raises:
            SchedulerServiceException: If history retrieval fails
        """
        logger.info(
            f"Retrieving trigger history: {trigger_id}",
            extra={
                "user_id": user_id,
                "trigger_id": trigger_id,
                "page": page,
                "page_size": page_size
            }
        )
        
        try:
            # Phase 3 TODO: Implement trigger history retrieval logic
            # For now, return a placeholder response with sample data
            
            sample_history = [
                {
                    "job_id": f"job_{trigger_id}_001",
                    "trigger_id": trigger_id,
                    "status": ExecutionStatus.COMPLETED.value,
                    "scheduled_time": "2024-01-07T09:00:00Z",
                    "started_at": "2024-01-07T09:00:05Z",
                    "completed_at": "2024-01-07T09:25:30Z",
                    "execution_time_seconds": 1525,
                    "result_summary": "All tests passed successfully",
                    "success": True,
                    "retry_count": 0,
                    "worker_instance": "worker-01"
                },
                {
                    "job_id": f"job_{trigger_id}_002",
                    "trigger_id": trigger_id,
                    "status": ExecutionStatus.FAILED.value,
                    "scheduled_time": "2024-01-06T09:00:00Z",
                    "started_at": "2024-01-06T09:00:02Z",
                    "completed_at": "2024-01-06T09:15:45Z",
                    "execution_time_seconds": 943,
                    "error_summary": "Network timeout during test execution",
                    "success": False,
                    "retry_count": 2,
                    "worker_instance": "worker-02"
                }
            ]
            
            pagination_info = {
                "page": page,
                "page_size": page_size,
                "total_records": len(sample_history),
                "total_pages": 1,
                "has_next": False,
                "has_previous": False
            }
            
            logger.info(
                f"Trigger history retrieved successfully: {trigger_id}",
                extra={
                    "trigger_id": trigger_id,
                    "record_count": len(sample_history),
                    "page": page
                }
            )
            
            return ExecutionHistoryResponse(
                success=True,
                message=f"Trigger execution history retrieved successfully for trigger '{trigger_id}'",
                data=sample_history,
                pagination=pagination_info
            )
            
        except Exception as e:
            logger.error(
                f"Error retrieving trigger history: {e}",
                extra={
                    "user_id": user_id,
                    "trigger_id": trigger_id,
                    "error": str(e)
                },
                exc_info=True
            )
            raise SchedulerServiceException(
                f"Failed to retrieve trigger history: {e}",
                service_name="SchedulerService",
                operation="get_trigger_history"
            )


class SchedulerServiceFactory:
    """Factory for creating SchedulerService instances with proper dependencies"""
    
    @staticmethod
    def create() -> SchedulerService:
        """
        Create a SchedulerService instance with injected dependencies.
        
        Returns:
            SchedulerService: Configured service instance
            
        Note:
            Phase 3 TODO: Replace with actual service implementations
        """
        # Phase 3 TODO: Create actual service implementations
        # For now, create placeholder services
        
        # Placeholder implementations - will be replaced in Phase 3
        trigger_engine_service = None  # TriggerEngineServiceImpl()
        lock_manager_service = None    # LockManagerServiceImpl()
        job_execution_service = None   # JobExecutionServiceImpl()
        
        return SchedulerService(
            trigger_engine_service=trigger_engine_service,
            lock_manager_service=lock_manager_service,
            job_execution_service=job_execution_service
        ) 
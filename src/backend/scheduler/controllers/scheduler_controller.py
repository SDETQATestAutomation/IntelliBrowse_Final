"""
Scheduler Controller - HTTP Orchestration Layer

Handles HTTP request processing, service orchestration, and response formatting
for all Scheduled Task Runner endpoints. Acts as the interface between FastAPI
routes and business logic services with comprehensive error handling and validation.

Key Features:
- Request validation and parameter extraction
- Service orchestration with dependency injection
- Response formatting and error handling
- JWT authentication integration
- Structured logging for all operations
"""

from typing import List
from fastapi import HTTPException, status

from ...config.logging import get_logger
from ...auth.schemas.auth_responses import UserResponse
from ..services.scheduler_service import SchedulerService, SchedulerServiceException
from ..schemas.trigger_schemas import (
    CreateScheduledTriggerRequest,
    UpdateScheduledTriggerRequest,
    ScheduledTriggerResponse,
    ExecutionStatusResponse,
    ExecutionHistoryResponse,
    BaseResponseSchema
)

logger = get_logger(__name__)


class SchedulerController:
    """
    Scheduler Controller for handling HTTP requests and responses.
    
    Provides request validation, service orchestration, and response formatting
    for all scheduled task runner operations following clean architecture principles.
    Acts as the HTTP boundary layer, fully decoupled from business logic.
    """
    
    def __init__(self, scheduler_service: SchedulerService):
        """
        Initialize controller with injected scheduler service.
        
        Args:
            scheduler_service: Main business logic service for scheduler operations
        """
        self.scheduler_service = scheduler_service
        logger.info("SchedulerController initialized successfully")
    
    async def create_scheduled_trigger(
        self,
        request: CreateScheduledTriggerRequest,
        user: UserResponse
    ) -> ScheduledTriggerResponse:
        """
        Handle scheduled trigger creation request.
        
        Args:
            request: Trigger creation request with configuration
            user: Authenticated user context
            
        Returns:
            ScheduledTriggerResponse with created trigger data
            
        Raises:
            HTTPException: If creation fails with appropriate status code
        """
        logger.info(
            f"Processing create scheduled trigger request: {request.name}",
            extra={
                "user_id": user.id,
                "trigger_name": request.name,
                "trigger_type": request.trigger_config.trigger_type.value,
                "task_type": request.execution_config.task_type,
                "has_retry_policy": request.retry_policy is not None,
                "tag_count": len(request.tags)
            }
        )
        
        try:
            # Validate trigger configuration
            self._validate_trigger_request(request)
            
            # Create trigger via service
            response = await self.scheduler_service.create_scheduled_trigger(
                request, user.id
            )
            
            logger.info(
                f"Scheduled trigger created successfully",
                extra={
                    "trigger_id": response.data.get("id"),
                    "trigger_name": response.data.get("name"),
                    "user_id": user.id,
                    "trigger_type": response.data.get("trigger_type")
                }
            )
            
            return response
            
        except ValueError as e:
            logger.warning(
                f"Validation error creating scheduled trigger: {e}",
                extra={
                    "user_id": user.id,
                    "trigger_name": request.name,
                    "error": str(e)
                }
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Validation error: {str(e)}"
            )
            
        except SchedulerServiceException as e:
            logger.error(
                f"Service error creating scheduled trigger: {e}",
                extra={
                    "user_id": user.id,
                    "trigger_name": request.name,
                    "service_error": e.to_dict()
                }
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create scheduled trigger"
            )
            
        except Exception as e:
            logger.error(
                f"Unexpected error creating scheduled trigger: {e}",
                extra={
                    "user_id": user.id,
                    "trigger_name": request.name,
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error during trigger creation"
            )
    
    async def update_scheduled_trigger(
        self,
        trigger_id: str,
        request: UpdateScheduledTriggerRequest,
        user: UserResponse
    ) -> ScheduledTriggerResponse:
        """
        Handle scheduled trigger update request.
        
        Args:
            trigger_id: ID of the trigger to update
            request: Trigger update request with configuration changes
            user: Authenticated user context
            
        Returns:
            ScheduledTriggerResponse with updated trigger data
            
        Raises:
            HTTPException: If update fails with appropriate status code
        """
        logger.info(
            f"Processing update scheduled trigger request: {trigger_id}",
            extra={
                "user_id": user.id,
                "trigger_id": trigger_id,
                "update_fields": list(request.model_dump(exclude_none=True).keys())
            }
        )
        
        try:
            # Validate trigger ID format
            if not self._is_valid_trigger_id(trigger_id):
                raise ValueError(f"Invalid trigger ID format: {trigger_id}")
            
            # Validate update request
            self._validate_update_request(request)
            
            # Update trigger via service
            response = await self.scheduler_service.update_scheduled_trigger(
                trigger_id, request, user.id
            )
            
            logger.info(
                f"Scheduled trigger updated successfully: {trigger_id}",
                extra={
                    "trigger_id": trigger_id,
                    "user_id": user.id,
                    "updated_fields": list(request.model_dump(exclude_none=True).keys())
                }
            )
            
            return response
            
        except ValueError as e:
            logger.warning(
                f"Validation error updating scheduled trigger: {e}",
                extra={
                    "user_id": user.id,
                    "trigger_id": trigger_id,
                    "error": str(e)
                }
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Validation error: {str(e)}"
            )
            
        except SchedulerServiceException as e:
            logger.error(
                f"Service error updating scheduled trigger: {e}",
                extra={
                    "user_id": user.id,
                    "trigger_id": trigger_id,
                    "service_error": e.to_dict()
                }
            )
            # Check if trigger not found
            if "not found" in str(e).lower():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Scheduled trigger '{trigger_id}' not found"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to update scheduled trigger"
                )
            
        except Exception as e:
            logger.error(
                f"Unexpected error updating scheduled trigger: {e}",
                extra={
                    "user_id": user.id,
                    "trigger_id": trigger_id,
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error during trigger update"
            )
    
    async def delete_scheduled_trigger(
        self,
        trigger_id: str,
        user: UserResponse
    ) -> BaseResponseSchema:
        """
        Handle scheduled trigger deletion request.
        
        Args:
            trigger_id: ID of the trigger to delete
            user: Authenticated user context
            
        Returns:
            BaseResponseSchema confirming deletion
            
        Raises:
            HTTPException: If deletion fails with appropriate status code
        """
        logger.info(
            f"Processing delete scheduled trigger request: {trigger_id}",
            extra={
                "user_id": user.id,
                "trigger_id": trigger_id
            }
        )
        
        try:
            # Validate trigger ID format
            if not self._is_valid_trigger_id(trigger_id):
                raise ValueError(f"Invalid trigger ID format: {trigger_id}")
            
            # Delete trigger via service
            response = await self.scheduler_service.delete_scheduled_trigger(
                trigger_id, user.id
            )
            
            logger.info(
                f"Scheduled trigger deleted successfully: {trigger_id}",
                extra={
                    "trigger_id": trigger_id,
                    "user_id": user.id
                }
            )
            
            return response
            
        except ValueError as e:
            logger.warning(
                f"Validation error deleting scheduled trigger: {e}",
                extra={
                    "user_id": user.id,
                    "trigger_id": trigger_id,
                    "error": str(e)
                }
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Validation error: {str(e)}"
            )
            
        except SchedulerServiceException as e:
            logger.error(
                f"Service error deleting scheduled trigger: {e}",
                extra={
                    "user_id": user.id,
                    "trigger_id": trigger_id,
                    "service_error": e.to_dict()
                }
            )
            # Check if trigger not found
            if "not found" in str(e).lower():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Scheduled trigger '{trigger_id}' not found"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to delete scheduled trigger"
                )
            
        except Exception as e:
            logger.error(
                f"Unexpected error deleting scheduled trigger: {e}",
                extra={
                    "user_id": user.id,
                    "trigger_id": trigger_id,
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error during trigger deletion"
            )
    
    async def manual_trigger_execution(
        self,
        trigger_id: str,
        user: UserResponse
    ) -> ExecutionStatusResponse:
        """
        Handle manual trigger execution request.
        
        Args:
            trigger_id: ID of the trigger to execute manually
            user: Authenticated user context
            
        Returns:
            ExecutionStatusResponse with execution status
            
        Raises:
            HTTPException: If execution fails with appropriate status code
        """
        logger.info(
            f"Processing manual trigger execution request: {trigger_id}",
            extra={
                "user_id": user.id,
                "trigger_id": trigger_id
            }
        )
        
        try:
            # Validate trigger ID format
            if not self._is_valid_trigger_id(trigger_id):
                raise ValueError(f"Invalid trigger ID format: {trigger_id}")
            
            # Execute trigger via service
            response = await self.scheduler_service.manual_trigger_execution(
                trigger_id, user.id
            )
            
            logger.info(
                f"Manual trigger execution initiated successfully: {trigger_id}",
                extra={
                    "trigger_id": trigger_id,
                    "job_id": response.data.get("job_id"),
                    "user_id": user.id,
                    "execution_status": response.data.get("status")
                }
            )
            
            return response
            
        except ValueError as e:
            logger.warning(
                f"Validation error executing trigger: {e}",
                extra={
                    "user_id": user.id,
                    "trigger_id": trigger_id,
                    "error": str(e)
                }
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Validation error: {str(e)}"
            )
            
        except SchedulerServiceException as e:
            logger.error(
                f"Service error executing trigger: {e}",
                extra={
                    "user_id": user.id,
                    "trigger_id": trigger_id,
                    "service_error": e.to_dict()
                }
            )
            # Check if trigger not found or disabled
            if "not found" in str(e).lower():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Scheduled trigger '{trigger_id}' not found"
                )
            elif "disabled" in str(e).lower() or "inactive" in str(e).lower():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Trigger '{trigger_id}' is disabled or inactive"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to execute trigger"
                )
            
        except Exception as e:
            logger.error(
                f"Unexpected error executing trigger: {e}",
                extra={
                    "user_id": user.id,
                    "trigger_id": trigger_id,
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error during trigger execution"
            )
    
    async def get_trigger_history(
        self,
        trigger_id: str,
        user: UserResponse,
        page: int = 1,
        page_size: int = 20
    ) -> ExecutionHistoryResponse:
        """
        Handle trigger execution history request.
        
        Args:
            trigger_id: ID of the trigger to get history for
            user: Authenticated user context
            page: Page number for pagination
            page_size: Number of records per page
            
        Returns:
            ExecutionHistoryResponse with execution history
            
        Raises:
            HTTPException: If history retrieval fails with appropriate status code
        """
        logger.info(
            f"Processing trigger history request: {trigger_id}",
            extra={
                "user_id": user.id,
                "trigger_id": trigger_id,
                "page": page,
                "page_size": page_size
            }
        )
        
        try:
            # Validate trigger ID format
            if not self._is_valid_trigger_id(trigger_id):
                raise ValueError(f"Invalid trigger ID format: {trigger_id}")
            
            # Validate pagination parameters
            if page < 1:
                raise ValueError("Page number must be >= 1")
            if page_size < 1 or page_size > 100:
                raise ValueError("Page size must be between 1 and 100")
            
            # Get history via service
            response = await self.scheduler_service.get_trigger_history(
                trigger_id, user.id, page, page_size
            )
            
            logger.info(
                f"Trigger history retrieved successfully: {trigger_id}",
                extra={
                    "trigger_id": trigger_id,
                    "user_id": user.id,
                    "record_count": len(response.data),
                    "page": page,
                    "total_records": response.pagination.get("total_records", 0)
                }
            )
            
            return response
            
        except ValueError as e:
            logger.warning(
                f"Validation error retrieving trigger history: {e}",
                extra={
                    "user_id": user.id,
                    "trigger_id": trigger_id,
                    "error": str(e)
                }
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Validation error: {str(e)}"
            )
            
        except SchedulerServiceException as e:
            logger.error(
                f"Service error retrieving trigger history: {e}",
                extra={
                    "user_id": user.id,
                    "trigger_id": trigger_id,
                    "service_error": e.to_dict()
                }
            )
            # Check if trigger not found
            if "not found" in str(e).lower():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Scheduled trigger '{trigger_id}' not found"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to retrieve trigger history"
                )
            
        except Exception as e:
            logger.error(
                f"Unexpected error retrieving trigger history: {e}",
                extra={
                    "user_id": user.id,
                    "trigger_id": trigger_id,
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error during history retrieval"
            )
    
    def _validate_trigger_request(self, request: CreateScheduledTriggerRequest) -> None:
        """
        Validate trigger creation request.
        
        Args:
            request: Trigger creation request to validate
            
        Raises:
            ValueError: If validation fails
        """
        # Validate cron expression for time-based triggers
        if (request.trigger_config.trigger_type.value == "time_based" and 
            request.trigger_config.cron_expression):
            self._validate_cron_expression(request.trigger_config.cron_expression)
        
        # Validate execution window times
        if (request.trigger_config.execution_window_start and 
            request.trigger_config.execution_window_end):
            self._validate_execution_window(
                request.trigger_config.execution_window_start,
                request.trigger_config.execution_window_end
            )
        
        # Validate task type
        if not request.execution_config.task_type:
            raise ValueError("Task type is required")
    
    def _validate_update_request(self, request: UpdateScheduledTriggerRequest) -> None:
        """
        Validate trigger update request.
        
        Args:
            request: Trigger update request to validate
            
        Raises:
            ValueError: If validation fails
        """
        # Check if at least one field is being updated
        update_data = request.model_dump(exclude_none=True)
        if not update_data:
            raise ValueError("At least one field must be provided for update")
        
        # Validate cron expression if provided
        if (request.trigger_config and 
            request.trigger_config.trigger_type and
            request.trigger_config.trigger_type.value == "time_based" and 
            request.trigger_config.cron_expression):
            self._validate_cron_expression(request.trigger_config.cron_expression)
    
    def _validate_cron_expression(self, cron_expression: str) -> None:
        """
        Validate cron expression format.
        
        Args:
            cron_expression: Cron expression to validate
            
        Raises:
            ValueError: If cron expression is invalid
        """
        # Basic cron validation - Phase 3 TODO: Use croniter for full validation
        parts = cron_expression.strip().split()
        if len(parts) != 5:
            raise ValueError("Cron expression must have exactly 5 parts")
        
        # Additional validation can be added here
        logger.debug(f"Cron expression validated: {cron_expression}")
    
    def _validate_execution_window(self, start_time: str, end_time: str) -> None:
        """
        Validate execution window times.
        
        Args:
            start_time: Start time in HH:MM format
            end_time: End time in HH:MM format
            
        Raises:
            ValueError: If execution window is invalid
        """
        import re
        
        time_pattern = r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$'
        
        if not re.match(time_pattern, start_time):
            raise ValueError(f"Invalid start time format: {start_time}")
        
        if not re.match(time_pattern, end_time):
            raise ValueError(f"Invalid end time format: {end_time}")
        
        # Check if start time is before end time
        start_minutes = self._time_to_minutes(start_time)
        end_minutes = self._time_to_minutes(end_time)
        
        if start_minutes >= end_minutes:
            raise ValueError("Execution window start time must be before end time")
    
    def _time_to_minutes(self, time_str: str) -> int:
        """Convert HH:MM time string to minutes since midnight"""
        hours, minutes = map(int, time_str.split(':'))
        return hours * 60 + minutes
    
    def _is_valid_trigger_id(self, trigger_id: str) -> bool:
        """
        Validate trigger ID format.
        
        Args:
            trigger_id: Trigger ID to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        # Basic UUID validation - Phase 3 TODO: More robust validation
        import re
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        return bool(re.match(uuid_pattern, trigger_id.lower()))


class SchedulerControllerFactory:
    """Factory for creating SchedulerController instances"""
    
    @staticmethod
    def create() -> SchedulerController:
        """
        Create a SchedulerController instance with injected dependencies.
        
        Returns:
            SchedulerController: Configured controller instance
        """
        from ..services.scheduler_service import SchedulerServiceFactory
        
        scheduler_service = SchedulerServiceFactory.create()
        return SchedulerController(scheduler_service) 
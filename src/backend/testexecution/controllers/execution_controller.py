"""
Test Execution Engine - Execution Controller

Provides HTTP request/response orchestration for test execution operations including:
- Starting test case and test suite executions
- Monitoring execution progress and status
- Retrieving execution results and reports
- Managing execution queue and priorities
- Health checks and system monitoring

Follows clean architecture principles with proper error handling and authentication.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorDatabase

from ..services import (
    ExecutionService,
    ExecutionServiceFactory,
    ExecutionOrchestrator,
    ExecutionOrchestratorFactory,
    ExecutionStateService,
    ExecutionStateServiceFactory,
    ExecutionQueueService,
    ExecutionQueueServiceFactory,
    ExecutionMonitoringService,
    ExecutionMonitoringServiceFactory,
    ResultProcessorService,
    ResultProcessorServiceFactory
)
from ..schemas.execution_schemas import (
    StartTestCaseExecutionRequest,
    StartTestSuiteExecutionRequest,
    UpdateExecutionStatusRequest,
    FilterExecutionsRequest,
    ExecutionTraceResponse,
    ExecutionListResponse,
    ExecutionProgressResponse,
    ExecutionStatsResponse,
    ExecutionFieldInclusion,
    StepFieldInclusion,
    ReportFormat
)
from ..models.execution_trace_model import ExecutionStatus, ExecutionError

logger = logging.getLogger(__name__)


class ExecutionController:
    """
    Controller for handling test execution HTTP requests.
    
    Orchestrates between multiple services to provide comprehensive
    execution management capabilities through REST API endpoints.
    """
    
    def __init__(
        self,
        execution_service: ExecutionService,
        orchestrator: ExecutionOrchestrator,
        state_service: ExecutionStateService,
        queue_service: ExecutionQueueService,
        monitoring_service: ExecutionMonitoringService,
        result_processor: ResultProcessorService
    ):
        self.execution_service = execution_service
        self.orchestrator = orchestrator
        self.state_service = state_service
        self.queue_service = queue_service
        self.monitoring_service = monitoring_service
        self.result_processor = result_processor
        
        logger.info("ExecutionController initialized")
    
    # Core Execution Operations
    
    async def start_test_case_execution(
        self,
        request: StartTestCaseExecutionRequest,
        user_id: str
    ) -> ExecutionTraceResponse:
        """
        Start execution of a single test case.
        
        Args:
            request: Test case execution request
            user_id: User ID from authentication
            
        Returns:
            ExecutionTraceResponse: Created execution trace
            
        Raises:
            ExecutionError: If execution cannot be started
            ValueError: If request validation fails
        """
        try:
            logger.info(f"Starting test case execution: {request.test_case_id} by {user_id}")
            
            # Validate request
            if not request.test_case_id:
                raise ValueError("test_case_id is required")
            
            # Start execution through service
            execution_response = await self.execution_service.start_test_case_execution(
                request, user_id
            )
            
            # Queue execution for processing
            await self.queue_service.enqueue_execution(
                execution_id=execution_response.execution_id,
                execution_type=execution_response.execution_type,
                payload={
                    "test_case_id": request.test_case_id,
                    "execution_context": request.execution_context.model_dump(),
                    "execution_config": request.execution_config.model_dump(),
                    "triggered_by": user_id
                },
                priority=request.priority
            )
            
            logger.info(f"Test case execution started and queued: {execution_response.execution_id}")
            return execution_response
            
        except Exception as e:
            logger.error(f"Failed to start test case execution: {str(e)}")
            if isinstance(e, (ExecutionError, ValueError)):
                raise
            raise ExecutionError(f"Failed to start test case execution: {str(e)}")
    
    async def start_test_suite_execution(
        self,
        request: StartTestSuiteExecutionRequest,
        user_id: str
    ) -> ExecutionTraceResponse:
        """
        Start execution of a test suite.
        
        Args:
            request: Test suite execution request
            user_id: User ID from authentication
            
        Returns:
            ExecutionTraceResponse: Created execution trace
            
        Raises:
            ExecutionError: If execution cannot be started
            ValueError: If request validation fails
        """
        try:
            logger.info(f"Starting test suite execution: {request.test_suite_id} by {user_id}")
            
            # Validate request
            if not request.test_suite_id:
                raise ValueError("test_suite_id is required")
            
            # Start execution through service
            execution_response = await self.execution_service.start_test_suite_execution(
                request, user_id
            )
            
            # Queue execution for processing
            await self.queue_service.enqueue_execution(
                execution_id=execution_response.execution_id,
                execution_type=execution_response.execution_type,
                payload={
                    "test_suite_id": request.test_suite_id,
                    "execution_context": request.execution_context.model_dump(),
                    "execution_config": request.execution_config.model_dump(),
                    "triggered_by": user_id,
                    "suite_config": {
                        "parallel_execution": request.parallel_execution,
                        "max_parallel_cases": request.max_parallel_cases,
                        "continue_on_failure": request.continue_on_failure
                    }
                },
                priority=request.priority
            )
            
            logger.info(f"Test suite execution started and queued: {execution_response.execution_id}")
            return execution_response
            
        except Exception as e:
            logger.error(f"Failed to start test suite execution: {str(e)}")
            if isinstance(e, (ExecutionError, ValueError)):
                raise
            raise ExecutionError(f"Failed to start test suite execution: {str(e)}")
    
    async def get_execution(
        self,
        execution_id: str,
        user_id: str,
        include_fields: ExecutionFieldInclusion = ExecutionFieldInclusion.SUMMARY,
        include_steps: StepFieldInclusion = StepFieldInclusion.BASIC
    ) -> ExecutionTraceResponse:
        """
        Retrieve execution by ID with field inclusion control.
        
        Args:
            execution_id: Execution identifier
            user_id: User ID from authentication
            include_fields: Fields to include in response
            include_steps: Step fields to include
            
        Returns:
            ExecutionTraceResponse: Execution details
            
        Raises:
            ExecutionError: If execution not found or access denied
        """
        try:
            logger.debug(f"Retrieving execution: {execution_id} for user {user_id}")
            
            # Validate execution ID format
            if not execution_id or len(execution_id) != 24:
                raise ValueError("Invalid execution ID format")
            
            # Get execution through service
            execution_response = await self.execution_service.get_execution(
                execution_id, user_id, include_fields, include_steps
            )
            
            logger.debug(f"Execution retrieved successfully: {execution_id}")
            return execution_response
            
        except Exception as e:
            logger.error(f"Failed to retrieve execution: {execution_id} - {str(e)}")
            if isinstance(e, (ExecutionError, ValueError)):
                raise
            raise ExecutionError(f"Failed to retrieve execution: {str(e)}")
    
    async def list_executions(
        self,
        request: FilterExecutionsRequest,
        user_id: str
    ) -> ExecutionListResponse:
        """
        List executions with filtering and pagination.
        
        Args:
            request: Filter and pagination request
            user_id: User ID from authentication
            
        Returns:
            ExecutionListResponse: Paginated execution list
        """
        try:
            logger.debug(f"Listing executions for user {user_id} with filters")
            
            # Get executions through service
            execution_list = await self.execution_service.list_executions(request, user_id)
            
            logger.debug(f"Executions listed successfully: {len(execution_list.executions)} items")
            return execution_list
            
        except Exception as e:
            logger.error(f"Failed to list executions: {str(e)}")
            raise ExecutionError(f"Failed to list executions: {str(e)}")
    
    async def update_execution_status(
        self,
        execution_id: str,
        request: UpdateExecutionStatusRequest,
        user_id: str
    ) -> ExecutionTraceResponse:
        """
        Update execution status (cancel, retry, etc.).
        
        Args:
            execution_id: Execution identifier
            request: Status update request
            user_id: User ID from authentication
            
        Returns:
            ExecutionTraceResponse: Updated execution
        """
        try:
            logger.info(f"Updating execution status: {execution_id} -> {request.new_status}")
            
            # Validate execution ID
            if not execution_id or len(execution_id) != 24:
                raise ValueError("Invalid execution ID format")
            
            # Update status through state service
            success = await self.state_service.update_execution_state(
                execution_id=execution_id,
                new_status=request.new_status,
                user_id=user_id,
                metadata={
                    "reason": request.reason,
                    "additional_metadata": request.metadata
                }
            )
            
            if not success:
                raise ExecutionError("Failed to update execution status - concurrent modification")
            
            # Return updated execution
            updated_execution = await self.execution_service.get_execution(
                execution_id, user_id, ExecutionFieldInclusion.SUMMARY
            )
            
            logger.info(f"Execution status updated successfully: {execution_id}")
            return updated_execution
            
        except Exception as e:
            logger.error(f"Failed to update execution status: {execution_id} - {str(e)}")
            if isinstance(e, (ExecutionError, ValueError)):
                raise
            raise ExecutionError(f"Failed to update execution status: {str(e)}")
    
    async def get_execution_progress(
        self,
        execution_id: str,
        user_id: str
    ) -> ExecutionProgressResponse:
        """
        Get real-time execution progress.
        
        Args:
            execution_id: Execution identifier
            user_id: User ID from authentication
            
        Returns:
            ExecutionProgressResponse: Current progress information
        """
        try:
            logger.debug(f"Getting execution progress: {execution_id}")
            
            # Validate execution ID
            if not execution_id or len(execution_id) != 24:
                raise ValueError("Invalid execution ID format")
            
            # Get execution details
            execution = await self.execution_service.get_execution(
                execution_id, user_id, ExecutionFieldInclusion.SUMMARY
            )
            
            # Build progress response
            progress_response = ExecutionProgressResponse(
                execution_id=execution_id,
                status=execution.status,
                progress_percentage=execution.statistics.progress_percentage if execution.statistics else 0.0,
                current_step=None,  # Would be populated from real-time data
                estimated_remaining_ms=execution.statistics.estimated_remaining_ms if execution.statistics else None,
                last_update=datetime.now(),
                statistics=execution.statistics
            )
            
            logger.debug(f"Execution progress retrieved: {execution_id}")
            return progress_response
            
        except Exception as e:
            logger.error(f"Failed to get execution progress: {execution_id} - {str(e)}")
            if isinstance(e, (ExecutionError, ValueError)):
                raise
            raise ExecutionError(f"Failed to get execution progress: {str(e)}")
    
    # Queue Management Operations
    
    async def get_queue_status(self, user_id: str) -> Dict[str, Any]:
        """
        Get execution queue status and metrics.
        
        Args:
            user_id: User ID from authentication
            
        Returns:
            Queue status information
        """
        try:
            logger.debug(f"Getting queue status for user {user_id}")
            
            # Get queue status through service
            queue_status = await self.queue_service.get_queue_status()
            
            logger.debug("Queue status retrieved successfully")
            return queue_status
            
        except Exception as e:
            logger.error(f"Failed to get queue status: {str(e)}")
            raise ExecutionError(f"Failed to get queue status: {str(e)}")
    
    async def pause_queue(self, user_id: str) -> Dict[str, Any]:
        """
        Pause execution queue processing.
        
        Args:
            user_id: User ID from authentication
            
        Returns:
            Operation result
        """
        try:
            logger.info(f"Pausing queue by user {user_id}")
            
            await self.queue_service.pause_queue()
            
            return {
                "success": True,
                "message": "Queue paused successfully",
                "paused_by": user_id,
                "paused_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to pause queue: {str(e)}")
            raise ExecutionError(f"Failed to pause queue: {str(e)}")
    
    async def resume_queue(self, user_id: str) -> Dict[str, Any]:
        """
        Resume execution queue processing.
        
        Args:
            user_id: User ID from authentication
            
        Returns:
            Operation result
        """
        try:
            logger.info(f"Resuming queue by user {user_id}")
            
            await self.queue_service.resume_queue()
            
            return {
                "success": True,
                "message": "Queue resumed successfully",
                "resumed_by": user_id,
                "resumed_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to resume queue: {str(e)}")
            raise ExecutionError(f"Failed to resume queue: {str(e)}")
    
    # Reporting and Analytics
    
    async def generate_execution_report(
        self,
        execution_id: str,
        user_id: str,
        report_format: ReportFormat = ReportFormat.JSON,
        include_details: bool = True
    ) -> Dict[str, Any]:
        """
        Generate execution report in specified format.
        
        Args:
            execution_id: Execution identifier
            user_id: User ID from authentication
            report_format: Desired report format
            include_details: Whether to include detailed information
            
        Returns:
            Generated report data
        """
        try:
            logger.info(f"Generating execution report: {execution_id} ({report_format})")
            
            # Validate execution ID
            if not execution_id or len(execution_id) != 24:
                raise ValueError("Invalid execution ID format")
            
            # Generate report through result processor
            report = await self.result_processor.generate_execution_report(
                execution_id, report_format, include_details
            )
            
            logger.info(f"Execution report generated successfully: {execution_id}")
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate execution report: {execution_id} - {str(e)}")
            if isinstance(e, (ExecutionError, ValueError)):
                raise
            raise ExecutionError(f"Failed to generate execution report: {str(e)}")
    
    async def get_execution_analytics(
        self,
        user_id: str,
        time_range_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get execution analytics and performance metrics.
        
        Args:
            user_id: User ID from authentication
            time_range_hours: Hours of data to analyze
            
        Returns:
            Analytics data
        """
        try:
            logger.info(f"Getting execution analytics for {time_range_hours} hours")
            
            # Get analytics through monitoring service
            analytics = await self.monitoring_service.get_performance_analytics(time_range_hours)
            
            logger.info("Execution analytics retrieved successfully")
            return analytics
            
        except Exception as e:
            logger.error(f"Failed to get execution analytics: {str(e)}")
            raise ExecutionError(f"Failed to get execution analytics: {str(e)}")
    
    async def get_execution_trends(
        self,
        user_id: str,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Get execution trends over specified time period.
        
        Args:
            user_id: User ID from authentication
            days: Number of days to analyze
            
        Returns:
            Trend analysis data
        """
        try:
            logger.info(f"Getting execution trends for {days} days")
            
            # Get trends through monitoring service
            trends = await self.monitoring_service.get_execution_trends(days)
            
            logger.info("Execution trends retrieved successfully")
            return trends
            
        except Exception as e:
            logger.error(f"Failed to get execution trends: {str(e)}")
            raise ExecutionError(f"Failed to get execution trends: {str(e)}")
    
    # Health and Monitoring
    
    async def get_system_health(self, user_id: str) -> Dict[str, Any]:
        """
        Get comprehensive system health status.
        
        Args:
            user_id: User ID from authentication
            
        Returns:
            System health information
        """
        try:
            logger.debug(f"Getting system health for user {user_id}")
            
            # Get health status through monitoring service
            health_status = await self.monitoring_service.get_system_health()
            
            logger.debug("System health retrieved successfully")
            return health_status
            
        except Exception as e:
            logger.error(f"Failed to get system health: {str(e)}")
            raise ExecutionError(f"Failed to get system health: {str(e)}")
    
    async def get_execution_statistics(self, user_id: str) -> ExecutionStatsResponse:
        """
        Get execution statistics and summary metrics.
        
        Args:
            user_id: User ID from authentication
            
        Returns:
            ExecutionStatsResponse: Statistics summary
        """
        try:
            logger.debug(f"Getting execution statistics for user {user_id}")
            
            # Get analytics data
            analytics = await self.monitoring_service.get_performance_analytics(24)
            
            # Build statistics response
            stats_response = ExecutionStatsResponse(
                total_executions=analytics.get("total_executions", 0),
                executions_by_status=analytics.get("status_distribution", {}),
                executions_by_type=analytics.get("type_distribution", {}),
                average_duration_ms=analytics.get("average_duration_ms"),
                success_rate=analytics.get("success_rate", 0.0),
                most_common_tags=[],  # Would be populated from tag analysis
                recent_activity=analytics.get("hourly_breakdown", [])
            )
            
            logger.debug("Execution statistics retrieved successfully")
            return stats_response
            
        except Exception as e:
            logger.error(f"Failed to get execution statistics: {str(e)}")
            raise ExecutionError(f"Failed to get execution statistics: {str(e)}")
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Simple health check endpoint for load balancers.
        
        Returns:
            Health check response
        """
        try:
            # Basic health check
            return {
                "status": "healthy",
                "service": "test_execution_engine",
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0"
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "service": "test_execution_engine",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


class ExecutionControllerFactory:
    """Factory for creating ExecutionController instances with proper dependency injection."""
    
    @staticmethod
    def create(database: AsyncIOMotorDatabase) -> ExecutionController:
        """
        Create ExecutionController instance with all required service dependencies.
        
        Args:
            database: MongoDB database instance
            
        Returns:
            ExecutionController: Fully configured controller instance
        """
        # Create service instances
        execution_service = ExecutionServiceFactory.create(database)
        orchestrator = ExecutionOrchestratorFactory.create(database)
        state_service = ExecutionStateServiceFactory.create(database)
        queue_service = ExecutionQueueServiceFactory.create(database)
        monitoring_service = ExecutionMonitoringServiceFactory.create(database)
        result_processor = ResultProcessorServiceFactory.create(database)
        
        # Create controller with all dependencies
        return ExecutionController(
            execution_service=execution_service,
            orchestrator=orchestrator,
            state_service=state_service,
            queue_service=queue_service,
            monitoring_service=monitoring_service,
            result_processor=result_processor
        ) 
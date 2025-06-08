"""
Test Execution Engine - Main Execution Service

Provides the primary business logic for test execution operations including:
- Execution lifecycle management (create, start, monitor, complete)
- Integration with test case and test suite systems
- Execution validation and authorization
- Result processing and aggregation
- Real-time status tracking and notifications

Implements the hybrid state-event architecture from creative phase decisions.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, AsyncIterator
from bson import ObjectId

from motor.motor_asyncio import AsyncIOMotorDatabase

from ..models.execution_trace_model import (
    ExecutionTraceModel,
    ExecutionStatus,
    ExecutionType,
    StepStatus,
    ExecutionStatistics,
    ExecutionError,
    StepExecutionError,
    ExecutionTimeoutError,
    StateTransitionError
)
from ..schemas.execution_schemas import (
    StartTestCaseExecutionRequest,
    StartTestSuiteExecutionRequest,
    UpdateExecutionStatusRequest,
    FilterExecutionsRequest,
    ExecutionTraceResponse,
    ExecutionListResponse,
    ExecutionProgressResponse,
    ExecutionFieldInclusion,
    StepFieldInclusion,
    PaginationMeta,
    FilterMeta,
    SortMeta
)

logger = logging.getLogger(__name__)


class ExecutionService:
    """
    Main execution service providing comprehensive test execution management.
    
    Coordinates between orchestration, state management, result processing,
    and monitoring services to provide a unified execution interface.
    """
    
    def __init__(self, database: AsyncIOMotorDatabase):
        self.database = database
        self.collection = database.execution_traces
        
        logger.info("ExecutionService initialized")
    
    # Core Execution Operations
    
    async def start_test_case_execution(
        self,
        request: StartTestCaseExecutionRequest,
        triggered_by: str
    ) -> ExecutionTraceResponse:
        """
        Start execution of a single test case.
        
        Args:
            request: Test case execution request with configuration
            triggered_by: User ID who triggered the execution
            
        Returns:
            ExecutionTraceResponse: Created execution trace
            
        Raises:
            ExecutionError: If execution cannot be started
            ValidationError: If request validation fails
        """
        try:
            logger.info(f"Starting test case execution: {request.test_case_id} by {triggered_by}")
            
            # Validate test case exists and user has permission
            await self._validate_test_case_access(request.test_case_id, triggered_by)
            
            # Create execution trace
            execution_trace = ExecutionTraceModel(
                execution_type=ExecutionType.TEST_CASE,
                test_case_id=request.test_case_id,
                triggered_by=triggered_by,
                triggered_at=datetime.now(timezone.utc),
                status=ExecutionStatus.PENDING,
                execution_context=request.execution_context.model_dump(),
                execution_config=request.execution_config.model_dump(),
                tags=request.tags,
                metadata=request.metadata,
                priority=request.priority
            )
            
            # Save to database
            result = await self.collection.insert_one(execution_trace.model_dump())
            execution_id = str(result.inserted_id)
            execution_trace.execution_id = execution_id
            
            logger.info(f"Test case execution started successfully: {execution_id}")
            
            # Return response
            return await self._build_execution_response(
                execution_trace,
                ExecutionFieldInclusion.SUMMARY
            )
            
        except Exception as e:
            logger.error(f"Failed to start test case execution: {str(e)}")
            if isinstance(e, (ExecutionError, ValueError)):
                raise
            raise ExecutionError(f"Failed to start test case execution: {str(e)}")
    
    async def start_test_suite_execution(
        self,
        request: StartTestSuiteExecutionRequest,
        triggered_by: str
    ) -> ExecutionTraceResponse:
        """
        Start execution of a test suite.
        
        Args:
            request: Test suite execution request with configuration
            triggered_by: User ID who triggered the execution
            
        Returns:
            ExecutionTraceResponse: Created execution trace
            
        Raises:
            ExecutionError: If execution cannot be started
            ValidationError: If request validation fails
        """
        try:
            logger.info(f"Starting test suite execution: {request.test_suite_id} by {triggered_by}")
            
            # Validate test suite exists and user has permission
            await self._validate_test_suite_access(request.test_suite_id, triggered_by)
            
            # Create execution trace
            execution_trace = ExecutionTraceModel(
                execution_type=ExecutionType.TEST_SUITE,
                test_suite_id=request.test_suite_id,
                triggered_by=triggered_by,
                triggered_at=datetime.now(timezone.utc),
                status=ExecutionStatus.PENDING,
                execution_context=request.execution_context.model_dump(),
                execution_config=request.execution_config.model_dump(),
                tags=request.tags,
                metadata=request.metadata,
                priority=request.priority,
                suite_config={
                    "parallel_execution": request.parallel_execution,
                    "max_parallel_cases": request.max_parallel_cases,
                    "continue_on_failure": request.continue_on_failure
                }
            )
            
            # Save to database
            result = await self.collection.insert_one(execution_trace.model_dump())
            execution_id = str(result.inserted_id)
            execution_trace.execution_id = execution_id
            
            logger.info(f"Test suite execution started successfully: {execution_id}")
            
            # Return response
            return await self._build_execution_response(
                execution_trace,
                ExecutionFieldInclusion.SUMMARY
            )
            
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
            user_id: User requesting the execution
            include_fields: Fields to include in response
            include_steps: Step fields to include
            
        Returns:
            ExecutionTraceResponse: Execution data
            
        Raises:
            ExecutionError: If execution not found or access denied
        """
        try:
            # Validate ObjectId format
            if not ObjectId.is_valid(execution_id):
                raise ValueError(f"Invalid execution ID format: {execution_id}")
            
            # Retrieve execution
            execution_doc = await self.collection.find_one({"_id": ObjectId(execution_id)})
            if not execution_doc:
                raise ExecutionError(f"Execution not found: {execution_id}")
            
            execution_trace = ExecutionTraceModel(**execution_doc)
            
            # Validate access
            await self._validate_execution_access(execution_trace, user_id)
            
            # Build response with field inclusion
            return await self._build_execution_response(
                execution_trace,
                include_fields,
                include_steps
            )
            
        except Exception as e:
            logger.error(f"Failed to retrieve execution {execution_id}: {str(e)}")
            if isinstance(e, (ExecutionError, ValueError)):
                raise
            raise ExecutionError(f"Failed to retrieve execution: {str(e)}")
    
    async def list_executions(
        self,
        request: FilterExecutionsRequest,
        user_id: str
    ) -> ExecutionListResponse:
        """
        List executions with filtering, pagination, and sorting.
        
        Args:
            request: Filter and pagination request
            user_id: User requesting the list
            
        Returns:
            ExecutionListResponse: Paginated execution list
        """
        try:
            logger.info(f"Listing executions for user {user_id} with filters")
            
            # Build MongoDB filter
            filter_query = await self._build_filter_query(request, user_id)
            
            # Build sort criteria
            sort_criteria = self._build_sort_criteria(request.sort_field, request.sort_direction)
            
            # Calculate pagination
            skip = (request.page - 1) * request.page_size
            
            # Execute queries
            cursor = self.collection.find(filter_query).sort(sort_criteria).skip(skip).limit(request.page_size)
            executions = await cursor.to_list(length=request.page_size)
            
            # Get total count for pagination
            total_count = await self.collection.count_documents(filter_query)
            
            # Convert to models and build responses
            execution_responses = []
            for execution_doc in executions:
                execution_trace = ExecutionTraceModel(**execution_doc)
                response = await self._build_execution_response(
                    execution_trace,
                    request.include_fields,
                    request.include_steps
                )
                execution_responses.append(response)
            
            # Build pagination metadata
            total_pages = (total_count + request.page_size - 1) // request.page_size
            pagination = PaginationMeta(
                page=request.page,
                page_size=request.page_size,
                total_items=total_count,
                total_pages=total_pages,
                has_next=request.page < total_pages,
                has_previous=request.page > 1
            )
            
            # Build filter metadata
            filters = FilterMeta(
                applied_filters=self._extract_applied_filters(request),
                available_filters=["status", "execution_type", "triggered_by", "test_case_id", "test_suite_id", "tags"],
                filter_count=len(self._extract_applied_filters(request))
            )
            
            # Build sort metadata
            sorting = SortMeta(
                sort_field=request.sort_field,
                sort_direction=request.sort_direction
            )
            
            return ExecutionListResponse(
                executions=execution_responses,
                pagination=pagination,
                filters=filters,
                sorting=sorting
            )
            
        except Exception as e:
            logger.error(f"Failed to list executions: {str(e)}")
            raise ExecutionError(f"Failed to list executions: {str(e)}")
    
    # Private Helper Methods
    
    async def _validate_test_case_access(self, test_case_id: str, user_id: str) -> None:
        """Validate user has access to test case"""
        # TODO: Implement test case access validation
        # This would integrate with the test case service
        pass
    
    async def _validate_test_suite_access(self, test_suite_id: str, user_id: str) -> None:
        """Validate user has access to test suite"""
        # TODO: Implement test suite access validation
        # This would integrate with the test suite service
        pass
    
    async def _validate_execution_access(self, execution: ExecutionTraceModel, user_id: str) -> None:
        """Validate user has access to execution"""
        if execution.triggered_by != user_id:
            # TODO: Add role-based access control
            raise ExecutionError("Access denied to execution")
    
    async def _build_execution_response(
        self,
        execution: ExecutionTraceModel,
        include_fields: ExecutionFieldInclusion = ExecutionFieldInclusion.SUMMARY,
        include_steps: StepFieldInclusion = StepFieldInclusion.BASIC
    ) -> ExecutionTraceResponse:
        """Build execution response with field inclusion control"""
        
        # Core fields (always included)
        response_data = {
            "execution_id": execution.execution_id or str(execution.id),
            "status": execution.status,
            "execution_type": execution.execution_type,
            "triggered_by": execution.triggered_by,
            "triggered_at": execution.triggered_at
        }
        
        # Summary level fields
        if include_fields in [ExecutionFieldInclusion.SUMMARY, ExecutionFieldInclusion.DETAILED, ExecutionFieldInclusion.FULL]:
            response_data.update({
                "test_case_id": execution.test_case_id,
                "test_suite_id": execution.test_suite_id,
                "started_at": execution.started_at,
                "completed_at": execution.completed_at,
                "total_duration_ms": execution.total_duration_ms,
                "statistics": execution.statistics
            })
        
        # Detailed level fields
        if include_fields in [ExecutionFieldInclusion.DETAILED, ExecutionFieldInclusion.FULL]:
            response_data.update({
                "execution_context": execution.execution_context,
                "execution_config": execution.execution_config,
                "tags": execution.tags,
                "overall_result": execution.overall_result
            })
            
            # Include steps based on inclusion level
            if execution.embedded_step_results:
                response_data["embedded_steps"] = [
                    self._build_step_response(step, include_steps)
                    for step in execution.embedded_step_results
                ]
        
        # Full level fields
        if include_fields == ExecutionFieldInclusion.FULL:
            response_data.update({
                "state_history": execution.state_history,
                "execution_log": execution.execution_log,
                "debug_data": execution.debug_data,
                "metadata": execution.metadata,
                "resource_usage": execution.resource_usage
            })
        
        return ExecutionTraceResponse(**response_data)
    
    def _build_step_response(self, step: dict, include_level: StepFieldInclusion) -> dict:
        """Build step response with field inclusion control"""
        
        # Basic fields
        response = {
            "step_id": step.get("step_id"),
            "step_name": step.get("step_name"),
            "step_order": step.get("step_order"),
            "status": step.get("status")
        }
        
        # Standard level fields
        if include_level in [StepFieldInclusion.STANDARD, StepFieldInclusion.DETAILED, StepFieldInclusion.FULL]:
            response.update({
                "started_at": step.get("started_at"),
                "completed_at": step.get("completed_at"),
                "duration_ms": step.get("duration_ms"),
                "input_data": step.get("input_data"),
                "output_data": step.get("output_data"),
                "expected_result": step.get("expected_result"),
                "actual_result": step.get("actual_result")
            })
        
        # Detailed level fields
        if include_level in [StepFieldInclusion.DETAILED, StepFieldInclusion.FULL]:
            response.update({
                "error_details": step.get("error_details"),
                "warnings": step.get("warnings"),
                "retry_count": step.get("retry_count"),
                "metadata": step.get("metadata")
            })
        
        return response
    
    async def _build_filter_query(self, request: FilterExecutionsRequest, user_id: str) -> Dict[str, Any]:
        """Build MongoDB filter query from request"""
        query = {"triggered_by": user_id}  # User scoping
        
        if request.status:
            query["status"] = {"$in": [status.value for status in request.status]}
        
        if request.execution_type:
            query["execution_type"] = {"$in": [exec_type.value for exec_type in request.execution_type]}
        
        if request.test_case_id:
            query["test_case_id"] = request.test_case_id
        
        if request.test_suite_id:
            query["test_suite_id"] = request.test_suite_id
        
        if request.tags:
            query["tags"] = {"$in": request.tags}
        
        # Date range filters
        if request.triggered_after or request.triggered_before:
            date_filter = {}
            if request.triggered_after:
                date_filter["$gte"] = request.triggered_after
            if request.triggered_before:
                date_filter["$lte"] = request.triggered_before
            query["triggered_at"] = date_filter
        
        if request.completed_after or request.completed_before:
            date_filter = {}
            if request.completed_after:
                date_filter["$gte"] = request.completed_after
            if request.completed_before:
                date_filter["$lte"] = request.completed_before
            query["completed_at"] = date_filter
        
        return query
    
    def _build_sort_criteria(self, sort_field: str, sort_direction: str) -> List[tuple]:
        """Build MongoDB sort criteria"""
        direction = 1 if sort_direction == "asc" else -1
        return [(sort_field, direction)]
    
    def _extract_applied_filters(self, request: FilterExecutionsRequest) -> Dict[str, Any]:
        """Extract applied filters for metadata"""
        filters = {}
        
        if request.status:
            filters["status"] = [status.value for status in request.status]
        if request.execution_type:
            filters["execution_type"] = [exec_type.value for exec_type in request.execution_type]
        if request.test_case_id:
            filters["test_case_id"] = request.test_case_id
        if request.test_suite_id:
            filters["test_suite_id"] = request.test_suite_id
        if request.tags:
            filters["tags"] = request.tags
        if request.triggered_after:
            filters["triggered_after"] = request.triggered_after.isoformat()
        if request.triggered_before:
            filters["triggered_before"] = request.triggered_before.isoformat()
        
        return filters


class ExecutionServiceFactory:
    """Factory for creating ExecutionService instances with proper dependencies"""
    
    @staticmethod
    def create(database: AsyncIOMotorDatabase) -> ExecutionService:
        """
        Create ExecutionService with all dependencies
        
        Args:
            database: MongoDB database instance
            
        Returns:
            ExecutionService: Configured service instance
        """
        return ExecutionService(database=database) 
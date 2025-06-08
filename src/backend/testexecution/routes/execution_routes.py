"""
Test Execution Engine - FastAPI Routes

Defines all REST API endpoints for the Test Execution Engine including:
- Execution lifecycle management (start, monitor, control)
- Real-time execution monitoring and progress tracking
- Queue management and control operations
- Result retrieval and report generation
- Health checks and system analytics

All endpoints require authentication and follow REST conventions with comprehensive
OpenAPI documentation and proper error handling.
"""

import logging
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from fastapi.responses import JSONResponse

from ...auth.dependencies.auth_dependencies import get_current_user
from ...auth.services.database_service import get_database_service
from ..controllers import ExecutionController, ExecutionControllerFactory
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
from ..models.execution_trace_model import ExecutionError

logger = logging.getLogger(__name__)

# Create FastAPI router
router = APIRouter(
    prefix="/executions",
    tags=["Test Executions"],
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Resource not found"},
        500: {"description": "Internal server error"}
    }
)


# Dependency to get controller instance
async def get_execution_controller() -> ExecutionController:
    """Get ExecutionController instance with database dependency."""
    database_service = get_database_service()
    database = await database_service.get_database()
    return ExecutionControllerFactory.create(database)


# Core Execution Management Endpoints

@router.post(
    "/test-case",
    response_model=ExecutionTraceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start Test Case Execution",
    description="""
    Start execution of a single test case with specified configuration.
    
    The execution will be queued for processing and can be monitored using
    the execution ID returned in the response. Real-time progress updates
    are available through the progress endpoint or WebSocket connection.
    
    **Features:**
    - Configurable execution context and settings
    - Priority-based queue scheduling
    - Comprehensive error handling and retry logic
    - Real-time progress tracking
    
    **Performance Targets:**
    - Queue time: <5 seconds under normal load
    - API response: <200ms
    - Execution start: <30 seconds after queuing
    """
)
async def start_test_case_execution(
    request: StartTestCaseExecutionRequest,
    current_user: dict = Depends(get_current_user),
    controller: ExecutionController = Depends(get_execution_controller)
) -> ExecutionTraceResponse:
    """Start execution of a single test case."""
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User ID not found in authentication token"
            )
        
        execution_response = await controller.start_test_case_execution(request, user_id)
        return execution_response
        
    except ExecutionError as e:
        logger.error(f"Execution error in start_test_case_execution: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ValueError as e:
        logger.error(f"Validation error in start_test_case_execution: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error in start_test_case_execution: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start test case execution"
        )


@router.post(
    "/test-suite",
    response_model=ExecutionTraceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start Test Suite Execution",
    description="""
    Start execution of a test suite containing multiple test cases.
    
    Supports both sequential and parallel execution modes with configurable
    failure handling. The suite execution will coordinate individual test
    case executions and provide aggregated results.
    
    **Features:**
    - Sequential or parallel test case execution
    - Configurable failure handling (continue or stop on failure)
    - Resource management and throttling
    - Comprehensive suite-level reporting
    
    **Performance Targets:**
    - Suite setup: <10 seconds
    - Parallel execution: Up to 5 concurrent test cases
    - Memory usage: <500MB per suite execution
    """
)
async def start_test_suite_execution(
    request: StartTestSuiteExecutionRequest,
    current_user: dict = Depends(get_current_user),
    controller: ExecutionController = Depends(get_execution_controller)
) -> ExecutionTraceResponse:
    """Start execution of a test suite."""
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User ID not found in authentication token"
            )
        
        execution_response = await controller.start_test_suite_execution(request, user_id)
        return execution_response
        
    except ExecutionError as e:
        logger.error(f"Execution error in start_test_suite_execution: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ValueError as e:
        logger.error(f"Validation error in start_test_suite_execution: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error in start_test_suite_execution: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start test suite execution"
        )


@router.get(
    "/{execution_id}",
    response_model=ExecutionTraceResponse,
    summary="Get Execution Details",
    description="""
    Retrieve detailed information about a specific execution.
    
    Supports flexible field inclusion to optimize response size and
    performance based on client needs. Use field inclusion parameters
    to control the level of detail returned.
    
    **Field Inclusion Levels:**
    - `core`: Basic execution information only
    - `summary`: Core + statistics and timing
    - `detailed`: Summary + steps and configuration
    - `full`: All fields including debug data
    
    **Performance Targets:**
    - Core response: <50ms
    - Full response: <200ms
    - Data transfer: Optimized based on inclusion level
    """
)
async def get_execution(
    execution_id: str = Path(..., description="Execution identifier", regex=r"^[a-f0-9]{24}$"),
    include_fields: ExecutionFieldInclusion = Query(
        ExecutionFieldInclusion.SUMMARY,
        description="Fields to include in response"
    ),
    include_steps: StepFieldInclusion = Query(
        StepFieldInclusion.BASIC,
        description="Step fields to include"
    ),
    current_user: dict = Depends(get_current_user),
    controller: ExecutionController = Depends(get_execution_controller)
) -> ExecutionTraceResponse:
    """Get execution details by ID."""
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User ID not found in authentication token"
            )
        
        execution_response = await controller.get_execution(
            execution_id, user_id, include_fields, include_steps
        )
        return execution_response
        
    except ExecutionError as e:
        logger.error(f"Execution error in get_execution: {str(e)}")
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Execution not found: {execution_id}"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ValueError as e:
        logger.error(f"Validation error in get_execution: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error in get_execution: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve execution"
        )


@router.get(
    "/",
    response_model=ExecutionListResponse,
    summary="List Executions",
    description="""
    List executions with comprehensive filtering, sorting, and pagination.
    
    Supports filtering by status, type, date ranges, and tags. Results are
    paginated for performance and include metadata about applied filters
    and sorting criteria.
    
    **Filtering Options:**
    - Status: Filter by execution status (pending, running, completed, etc.)
    - Type: Filter by execution type (test_case, test_suite, etc.)
    - Date ranges: Filter by trigger or completion dates
    - Tags: Filter by execution tags (OR logic)
    - User: Filter by user who triggered execution
    
    **Performance Targets:**
    - Response time: <100ms for typical queries
    - Pagination: 20 items per page (configurable)
    - Maximum page size: 100 items
    """
)
async def list_executions(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[List[str]] = Query(None, description="Filter by execution status"),
    execution_type: Optional[List[str]] = Query(None, description="Filter by execution type"),
    triggered_by: Optional[str] = Query(None, description="Filter by user who triggered execution"),
    test_case_id: Optional[str] = Query(None, description="Filter by test case ID"),
    test_suite_id: Optional[str] = Query(None, description="Filter by test suite ID"),
    tags: Optional[List[str]] = Query(None, description="Filter by tags (OR logic)"),
    include_fields: ExecutionFieldInclusion = Query(
        ExecutionFieldInclusion.SUMMARY,
        description="Fields to include in response"
    ),
    include_steps: StepFieldInclusion = Query(
        StepFieldInclusion.BASIC,
        description="Step fields to include"
    ),
    current_user: dict = Depends(get_current_user),
    controller: ExecutionController = Depends(get_execution_controller)
) -> ExecutionListResponse:
    """List executions with filtering and pagination."""
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User ID not found in authentication token"
            )
        
        # Build filter request
        filter_request = FilterExecutionsRequest(
            page=page,
            page_size=page_size,
            status=status,
            execution_type=execution_type,
            triggered_by=triggered_by,
            test_case_id=test_case_id,
            test_suite_id=test_suite_id,
            tags=tags,
            include_fields=include_fields,
            include_steps=include_steps
        )
        
        execution_list = await controller.list_executions(filter_request, user_id)
        return execution_list
        
    except ExecutionError as e:
        logger.error(f"Execution error in list_executions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ValueError as e:
        logger.error(f"Validation error in list_executions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error in list_executions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list executions"
        )


@router.patch(
    "/{execution_id}/status",
    response_model=ExecutionTraceResponse,
    summary="Update Execution Status",
    description="""
    Update execution status for control operations like cancellation or retry.
    
    Supports state transitions based on current execution status with
    validation to ensure only valid transitions are allowed. Includes
    audit trail for all status changes.
    
    **Supported Operations:**
    - Cancel running or queued executions
    - Retry failed executions
    - Mark executions for review
    
    **State Transition Rules:**
    - Pending → Queued, Cancelled
    - Queued → Running, Cancelled  
    - Running → Passed, Failed, Cancelled, Timeout
    - Failed → Retrying
    - Passed → Retrying (for re-runs)
    """
)
async def update_execution_status(
    execution_id: str = Path(..., description="Execution identifier", regex=r"^[a-f0-9]{24}$"),
    request: UpdateExecutionStatusRequest = ...,
    current_user: dict = Depends(get_current_user),
    controller: ExecutionController = Depends(get_execution_controller)
) -> ExecutionTraceResponse:
    """Update execution status."""
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User ID not found in authentication token"
            )
        
        execution_response = await controller.update_execution_status(
            execution_id, request, user_id
        )
        return execution_response
        
    except ExecutionError as e:
        logger.error(f"Execution error in update_execution_status: {str(e)}")
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Execution not found: {execution_id}"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ValueError as e:
        logger.error(f"Validation error in update_execution_status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error in update_execution_status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update execution status"
        )


@router.get(
    "/{execution_id}/progress",
    response_model=ExecutionProgressResponse,
    summary="Get Execution Progress",
    description="""
    Get real-time execution progress and status information.
    
    Provides current progress percentage, estimated remaining time,
    and detailed statistics. Optimized for frequent polling by
    frontend applications and monitoring systems.
    
    **Progress Information:**
    - Progress percentage (0-100%)
    - Current executing step
    - Estimated remaining time
    - Real-time statistics
    - Last update timestamp
    
    **Performance Targets:**
    - Response time: <50ms
    - Update frequency: Real-time (sub-second)
    - Polling recommended: Every 2-5 seconds
    """
)
async def get_execution_progress(
    execution_id: str = Path(..., description="Execution identifier", regex=r"^[a-f0-9]{24}$"),
    current_user: dict = Depends(get_current_user),
    controller: ExecutionController = Depends(get_execution_controller)
) -> ExecutionProgressResponse:
    """Get real-time execution progress."""
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User ID not found in authentication token"
            )
        
        progress_response = await controller.get_execution_progress(execution_id, user_id)
        return progress_response
        
    except ExecutionError as e:
        logger.error(f"Execution error in get_execution_progress: {str(e)}")
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Execution not found: {execution_id}"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error in get_execution_progress: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get execution progress"
        )


# Queue Management Endpoints

@router.get(
    "/queue/status",
    summary="Get Queue Status",
    description="""
    Get current execution queue status and metrics.
    
    Provides comprehensive information about queue depth, processing
    status, priority distribution, and performance metrics. Useful
    for monitoring and capacity planning.
    
    **Queue Metrics:**
    - Total queued executions
    - Currently processing executions
    - Priority distribution
    - Oldest queued execution
    - Dead letter queue count
    - Processing capacity and limits
    """
)
async def get_queue_status(
    current_user: dict = Depends(get_current_user),
    controller: ExecutionController = Depends(get_execution_controller)
) -> Dict[str, Any]:
    """Get execution queue status."""
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User ID not found in authentication token"
            )
        
        queue_status = await controller.get_queue_status(user_id)
        return queue_status
        
    except ExecutionError as e:
        logger.error(f"Execution error in get_queue_status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error in get_queue_status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get queue status"
        )


@router.post(
    "/queue/pause",
    summary="Pause Queue Processing",
    description="""
    Pause execution queue processing for maintenance or load management.
    
    Stops processing new executions from the queue while allowing
    currently running executions to complete. Useful for system
    maintenance, resource management, or emergency situations.
    
    **Effects:**
    - New executions continue to be queued
    - No new executions start processing
    - Running executions continue to completion
    - Queue status changes to 'paused'
    """
)
async def pause_queue(
    current_user: dict = Depends(get_current_user),
    controller: ExecutionController = Depends(get_execution_controller)
) -> Dict[str, Any]:
    """Pause execution queue processing."""
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User ID not found in authentication token"
            )
        
        result = await controller.pause_queue(user_id)
        return result
        
    except ExecutionError as e:
        logger.error(f"Execution error in pause_queue: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error in pause_queue: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to pause queue"
        )


@router.post(
    "/queue/resume",
    summary="Resume Queue Processing",
    description="""
    Resume execution queue processing after being paused.
    
    Restarts processing of queued executions according to priority
    and scheduling rules. Queue will return to normal operation
    and begin processing pending executions.
    
    **Effects:**
    - Queue processing resumes immediately
    - Pending executions start processing by priority
    - Queue status changes to 'active'
    - Normal throughput restored
    """
)
async def resume_queue(
    current_user: dict = Depends(get_current_user),
    controller: ExecutionController = Depends(get_execution_controller)
) -> Dict[str, Any]:
    """Resume execution queue processing."""
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User ID not found in authentication token"
            )
        
        result = await controller.resume_queue(user_id)
        return result
        
    except ExecutionError as e:
        logger.error(f"Execution error in resume_queue: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error in resume_queue: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resume queue"
        )


# Reporting and Analytics Endpoints

@router.get(
    "/{execution_id}/report",
    summary="Generate Execution Report",
    description="""
    Generate comprehensive execution report in specified format.
    
    Supports multiple output formats optimized for different use cases.
    Reports include execution details, step results, performance metrics,
    and analysis insights.
    
    **Supported Formats:**
    - JSON: Structured data for API consumption
    - HTML: Human-readable web format
    - PDF: Printable document format
    - CSV: Tabular data for analysis
    
    **Report Content:**
    - Execution summary and metadata
    - Step-by-step results
    - Performance metrics and timing
    - Error analysis and recommendations
    """
)
async def generate_execution_report(
    execution_id: str = Path(..., description="Execution identifier", regex=r"^[a-f0-9]{24}$"),
    format: ReportFormat = Query(ReportFormat.JSON, description="Report format"),
    include_details: bool = Query(True, description="Include detailed step information"),
    current_user: dict = Depends(get_current_user),
    controller: ExecutionController = Depends(get_execution_controller)
) -> Dict[str, Any]:
    """Generate execution report."""
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User ID not found in authentication token"
            )
        
        report = await controller.generate_execution_report(
            execution_id, user_id, format, include_details
        )
        return report
        
    except ExecutionError as e:
        logger.error(f"Execution error in generate_execution_report: {str(e)}")
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Execution not found: {execution_id}"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error in generate_execution_report: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate execution report"
        )


@router.get(
    "/analytics",
    summary="Get Execution Analytics",
    description="""
    Get comprehensive execution analytics and performance metrics.
    
    Provides aggregated data and insights for specified time range
    including performance trends, success rates, and usage patterns.
    Useful for monitoring, optimization, and capacity planning.
    
    **Analytics Include:**
    - Execution volume and trends
    - Performance metrics and timing
    - Success/failure rates
    - Resource utilization
    - Hourly/daily breakdowns
    """
)
async def get_execution_analytics(
    time_range_hours: int = Query(24, ge=1, le=168, description="Hours of data to analyze"),
    current_user: dict = Depends(get_current_user),
    controller: ExecutionController = Depends(get_execution_controller)
) -> Dict[str, Any]:
    """Get execution analytics."""
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User ID not found in authentication token"
            )
        
        analytics = await controller.get_execution_analytics(user_id, time_range_hours)
        return analytics
        
    except ExecutionError as e:
        logger.error(f"Execution error in get_execution_analytics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error in get_execution_analytics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get execution analytics"
        )


@router.get(
    "/trends",
    summary="Get Execution Trends",
    description="""
    Get execution trends and patterns over specified time period.
    
    Analyzes execution data to identify trends, patterns, and
    anomalies. Useful for understanding usage patterns and
    planning capacity or improvements.
    
    **Trend Analysis:**
    - Daily execution volumes
    - Success rate trends
    - Performance trends
    - Usage pattern analysis
    - Seasonal variations
    """
)
async def get_execution_trends(
    days: int = Query(7, ge=1, le=30, description="Number of days to analyze"),
    current_user: dict = Depends(get_current_user),
    controller: ExecutionController = Depends(get_execution_controller)
) -> Dict[str, Any]:
    """Get execution trends."""
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User ID not found in authentication token"
            )
        
        trends = await controller.get_execution_trends(user_id, days)
        return trends
        
    except ExecutionError as e:
        logger.error(f"Execution error in get_execution_trends: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error in get_execution_trends: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get execution trends"
        )


@router.get(
    "/statistics",
    response_model=ExecutionStatsResponse,
    summary="Get Execution Statistics",
    description="""
    Get comprehensive execution statistics and summary metrics.
    
    Provides high-level statistics and key performance indicators
    for monitoring dashboard and reporting purposes.
    
    **Statistics Include:**
    - Total execution counts
    - Status distribution
    - Type distribution  
    - Average performance metrics
    - Success rates
    - Recent activity summary
    """
)
async def get_execution_statistics(
    current_user: dict = Depends(get_current_user),
    controller: ExecutionController = Depends(get_execution_controller)
) -> ExecutionStatsResponse:
    """Get execution statistics."""
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User ID not found in authentication token"
            )
        
        statistics = await controller.get_execution_statistics(user_id)
        return statistics
        
    except ExecutionError as e:
        logger.error(f"Execution error in get_execution_statistics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error in get_execution_statistics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get execution statistics"
        )


# Health and System Status Endpoints

@router.get(
    "/system/health",
    summary="Get System Health",
    description="""
    Get comprehensive system health status and diagnostics.
    
    Provides detailed health information for all system components
    including database, queue, execution engine, and performance
    metrics. Used for monitoring and alerting.
    
    **Health Checks:**
    - Database connectivity and performance
    - Execution engine status
    - Queue health and capacity
    - Performance metrics
    - Resource utilization
    """
)
async def get_system_health(
    current_user: dict = Depends(get_current_user),
    controller: ExecutionController = Depends(get_execution_controller)
) -> Dict[str, Any]:
    """Get system health status."""
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User ID not found in authentication token"
            )
        
        health_status = await controller.get_system_health(user_id)
        return health_status
        
    except ExecutionError as e:
        logger.error(f"Execution error in get_system_health: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error in get_system_health: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get system health"
        )


@router.get(
    "/health",
    summary="Health Check",
    description="""
    Simple health check endpoint for load balancers and monitoring.
    
    Provides basic service availability check without authentication
    requirements. Returns service status and basic information.
    
    **Response:**
    - Service status (healthy/unhealthy)
    - Service name and version
    - Timestamp
    - Basic error information if unhealthy
    """
)
async def health_check(
    controller: ExecutionController = Depends(get_execution_controller)
) -> Dict[str, Any]:
    """Simple health check for load balancers."""
    try:
        health_response = await controller.health_check()
        
        if health_response.get("status") == "healthy":
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=health_response
            )
        else:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content=health_response
            )
            
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "service": "test_execution_engine",
                "error": str(e),
                "timestamp": "error"
            }
        ) 
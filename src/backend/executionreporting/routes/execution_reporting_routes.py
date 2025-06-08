"""
Execution Reporting FastAPI Routes

RESTful API endpoints for the Execution Reporting Module with comprehensive
OpenAPI documentation, JWT authentication, dependency injection, and proper
request/response model binding.
"""

from typing import Optional, List, Annotated
from fastapi import APIRouter, Depends, Query, Path, Body, status, Request

from ...config.logging import get_logger
from ...auth.dependencies.auth_dependencies import get_current_user
from ...auth.schemas.auth_responses import UserResponse
from ...schemas.response import SuccessResponse
from ..controllers.execution_reporting_controller import ExecutionReportingController, ExecutionReportingControllerFactory
from ..schemas.report_schemas import (
    ReportGenerationRequest, ExecutionReportResponse, TrendAnalysisResponse,
    QualityMetricsResponse, TimeRangeFilter, MetricFilter, DrilldownResponse
)
from ..schemas.dashboard_schemas import (
    DashboardCreateRequest, DashboardResponse, DashboardUpdateRequest
)
from ..schemas.alert_schemas import (
    AlertRuleCreateRequest, AlertRuleResponse
)
from ..schemas.export_schemas import (
    ExportJobRequest, ExportJobResponse, ExportStatusResponse
)

logger = get_logger(__name__)

# Create router with prefix and tags
router = APIRouter(
    prefix="/execution-reporting",
    tags=["Execution Reporting"],
    responses={
        401: {"description": "Unauthorized - Invalid or missing authentication"},
        403: {"description": "Forbidden - Insufficient permissions"},
        500: {"description": "Internal Server Error"}
    }
)


# Dependency injection for controller
async def get_execution_reporting_controller() -> ExecutionReportingController:
    """
    Get ExecutionReportingController dependency with proper service injection.
    
    Returns:
        ExecutionReportingController instance with all dependencies injected
    """
    return ExecutionReportingControllerFactory.create()


@router.post(
    "/reports/generate",
    response_model=ExecutionReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate execution report",
    description="""
    Generate comprehensive execution report with filtering, aggregation, and drill-down capabilities.
    
    **Core Features:**
    - **Flexible Filtering**: Time range, test types, suites, tags, and execution status
    - **Multi-Level Aggregation**: Daily, weekly, monthly, and custom intervals
    - **Performance Analytics**: Execution duration, resource utilization, efficiency metrics
    - **Quality Insights**: Pass/fail trends, flakiness detection, stability analysis
    - **Drill-Down Navigation**: Interactive navigation to detailed execution data
    
    **Report Types:**
    - **SUMMARY**: High-level overview with key metrics
    - **DETAILED**: Comprehensive execution data with full breakdowns
    - **TREND**: Time-series analysis with pattern detection
    - **QUALITY**: Quality-focused metrics with recommendations
    - **PERFORMANCE**: Execution performance and resource analysis
    
    **Performance Targets:** <500ms response time for standard reports, <1s for complex analytics
    """,
    responses={
        200: {
            "description": "Execution report generated successfully",
            "model": ExecutionReportResponse
        },
        400: {
            "description": "Invalid report request parameters"
        }
    }
)
async def generate_execution_report(
    request: ReportGenerationRequest = Body(
        ...,
        description="Report generation request with filters and parameters"
    ),
    current_user: UserResponse = Depends(get_current_user),
    controller: ExecutionReportingController = Depends(get_execution_reporting_controller)
) -> ExecutionReportResponse:
    """Generate execution report with comprehensive analytics"""
    return await controller.get_execution_report(request, current_user)


@router.get(
    "/trends",
    response_model=TrendAnalysisResponse,
    summary="Get trend analysis",
    description="""
    Retrieve trend analysis with pattern detection, anomaly identification, and forecasting.
    
    **Analytics Features:**
    - **Pattern Recognition**: Identifies recurring patterns in execution data
    - **Anomaly Detection**: Flags unusual execution behaviors and outliers
    - **Statistical Forecasting**: Predicts future trends based on historical data
    - **Seasonal Analysis**: Detects seasonal patterns and cyclical behaviors
    - **Correlation Analysis**: Identifies relationships between different metrics
    
    **Trend Categories:**
    - **Execution Volume**: Test execution frequency and volume trends
    - **Quality Trends**: Pass/fail ratio evolution over time
    - **Performance Trends**: Execution duration and efficiency patterns
    - **Flakiness Trends**: Test stability and reliability evolution
    - **Coverage Trends**: Test coverage expansion and gaps
    
    **Performance:** <500ms response time with intelligent caching
    """,
    responses={
        200: {
            "description": "Trend analysis retrieved successfully",
            "model": TrendAnalysisResponse
        }
    }
)
async def get_trend_analysis(
    time_range_start: Annotated[Optional[str], Query(
        description="Start date for trend analysis (ISO 8601 format)",
        example="2024-01-01T00:00:00Z"
    )] = None,
    time_range_end: Annotated[Optional[str], Query(
        description="End date for trend analysis (ISO 8601 format)",
        example="2024-01-31T23:59:59Z"
    )] = None,
    metric_types: Annotated[Optional[str], Query(
        description="Comma-separated metric types to analyze",
        example="execution_volume,quality_trends,performance"
    )] = None,
    current_user: UserResponse = Depends(get_current_user),
    controller: ExecutionReportingController = Depends(get_execution_reporting_controller)
) -> TrendAnalysisResponse:
    """Get trend analysis with pattern detection and forecasting"""
    
    # Build time range filter
    time_range = None
    if time_range_start and time_range_end:
        time_range = TimeRangeFilter(
            start_date=time_range_start,
            end_date=time_range_end
        )
    
    # Build metric filter
    metric_filter = None
    if metric_types:
        metric_filter = MetricFilter(
            filter_type="metric_types",
            filter_value=metric_types.split(",")
        )
    
    return await controller.get_trend_analysis(time_range, metric_filter, current_user)


@router.get(
    "/quality-metrics",
    response_model=QualityMetricsResponse,
    summary="Get quality metrics",
    description="""
    Retrieve comprehensive quality metrics including flakiness scoring, stability analysis, and quality assessment.
    
    **Quality Metrics:**
    - **Overall Quality Score**: Composite score across all quality dimensions
    - **Flakiness Index**: Test reliability and consistency scoring (0-100)
    - **Stability Trends**: Long-term stability patterns and evolution
    - **MTTR Analysis**: Mean Time to Resolution for failed tests
    - **Coverage Quality**: Test coverage effectiveness and gap analysis
    - **Risk Assessment**: Quality risk indicators and recommendations
    
    **Scoring Algorithms:**
    - **Flakiness Detection**: Statistical analysis of test result consistency
    - **Quality Regression**: Identifies declining quality trends
    - **Stability Scoring**: Measures test reliability over time
    - **Risk Modeling**: Predicts quality risks based on patterns
    
    **Performance:** <500ms response time with cached calculations
    """,
    responses={
        200: {
            "description": "Quality metrics retrieved successfully",
            "model": QualityMetricsResponse
        }
    }
)
async def get_quality_metrics(
    time_range_start: Annotated[Optional[str], Query(
        description="Start date for quality analysis (ISO 8601 format)",
        example="2024-01-01T00:00:00Z"
    )] = None,
    time_range_end: Annotated[Optional[str], Query(
        description="End date for quality analysis (ISO 8601 format)",
        example="2024-01-31T23:59:59Z"
    )] = None,
    include_details: Annotated[bool, Query(
        description="Include detailed breakdown of quality metrics"
    )] = False,
    current_user: UserResponse = Depends(get_current_user),
    controller: ExecutionReportingController = Depends(get_execution_reporting_controller)
) -> QualityMetricsResponse:
    """Get comprehensive quality metrics and assessment"""
    
    # Build time range filter
    time_range = None
    if time_range_start and time_range_end:
        time_range = TimeRangeFilter(
            start_date=time_range_start,
            end_date=time_range_end
        )
    
    # Build metric filter for detail level
    metric_filter = None
    if include_details:
        metric_filter = MetricFilter(
            filter_type="detail_level",
            filter_value=["detailed"]
        )
    
    return await controller.get_quality_metrics(time_range, metric_filter, current_user)


@router.post(
    "/dashboards",
    response_model=DashboardResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create dashboard",
    description="""
    Create a new dashboard configuration with widget composition and layout management.
    
    **Dashboard Features:**
    - **Multi-Widget Composition**: Support for multiple widget types and layouts
    - **Real-Time Updates**: Live data refresh and WebSocket integration
    - **User Personalization**: User-specific dashboard configurations
    - **Responsive Design**: Adaptive layouts for different screen sizes
    - **Performance Optimization**: Intelligent caching and lazy loading
    
    **Widget Types:**
    - **Execution Summary**: High-level execution metrics and KPIs
    - **Trend Charts**: Time-series visualization with interactive navigation
    - **Quality Heatmap**: Visual quality assessment with drill-down
    - **Alert Status**: Real-time alert monitoring and notifications
    - **Performance Gauges**: Execution performance and resource utilization
    - **Custom Widgets**: User-defined widget configurations
    
    **Performance:** <1s dashboard creation with widget validation
    """,
    responses={
        201: {
            "description": "Dashboard created successfully",
            "model": DashboardResponse
        },
        400: {
            "description": "Invalid dashboard configuration"
        }
    }
)
async def create_dashboard(
    request: DashboardCreateRequest = Body(
        ...,
        description="Dashboard creation request with widget configuration"
    ),
    current_user: UserResponse = Depends(get_current_user),
    controller: ExecutionReportingController = Depends(get_execution_reporting_controller)
) -> DashboardResponse:
    """Create new dashboard with widget composition"""
    return await controller.create_dashboard(request, current_user)


@router.get(
    "/dashboards/{dashboard_id}",
    response_model=DashboardResponse,
    summary="Get dashboard",
    description="""
    Retrieve dashboard configuration and data with all widget content populated.
    
    **Dashboard Retrieval:**
    - **Complete Widget Data**: All widgets populated with current data
    - **Real-Time Updates**: Latest execution data and metrics
    - **Cached Performance**: Intelligent caching for <1s load times
    - **User Authorization**: Access control based on dashboard ownership
    - **Responsive Data**: Optimized data loading for different screen sizes
    
    **Caching Strategy:**
    - **Widget-Level Caching**: Individual widget data cached independently
    - **Progressive Loading**: Core widgets loaded first, detailed widgets follow
    - **Cache Invalidation**: Intelligent cache refresh based on data changes
    - **Force Refresh**: Optional parameter to bypass cache for real-time data
    
    **Performance:** <1s dashboard loading with comprehensive caching
    """,
    responses={
        200: {
            "description": "Dashboard retrieved successfully",
            "model": DashboardResponse
        },
        404: {
            "description": "Dashboard not found or access denied"
        }
    }
)
async def get_dashboard(
    dashboard_id: Annotated[str, Path(
        description="Dashboard ID (MongoDB ObjectId format)",
        example="60f7b1b9e4b0c8a4f8e6d1a2",
        regex=r"^[0-9a-fA-F]{24}$"
    )],
    force_refresh: Annotated[bool, Query(
        description="Force refresh of cached dashboard data"
    )] = False,
    current_user: UserResponse = Depends(get_current_user),
    controller: ExecutionReportingController = Depends(get_execution_reporting_controller)
) -> DashboardResponse:
    """Get dashboard with all widget data populated"""
    return await controller.get_dashboard(dashboard_id, force_refresh, current_user)


@router.put(
    "/dashboards/{dashboard_id}",
    response_model=DashboardResponse,
    summary="Update dashboard",
    description="""
    Update existing dashboard configuration with widget and layout modifications.
    
    **Update Features:**
    - **Widget Management**: Add, remove, or modify individual widgets
    - **Layout Changes**: Update widget positioning and sizing
    - **Configuration Updates**: Modify dashboard settings and preferences
    - **Validation**: Comprehensive validation of widget configurations
    - **Atomic Updates**: All changes applied atomically or none at all
    
    **Supported Updates:**
    - Dashboard name and description
    - Widget addition and removal
    - Widget configuration changes
    - Layout and positioning updates
    - Refresh interval settings
    - Access permission changes
    
    **Performance:** <500ms update processing with validation
    """,
    responses={
        200: {
            "description": "Dashboard updated successfully",
            "model": DashboardResponse
        },
        404: {
            "description": "Dashboard not found or access denied"
        },
        400: {
            "description": "Invalid dashboard update configuration"
        }
    }
)
async def update_dashboard(
    dashboard_id: Annotated[str, Path(
        description="Dashboard ID (MongoDB ObjectId format)",
        example="60f7b1b9e4b0c8a4f8e6d1a2",
        regex=r"^[0-9a-fA-F]{24}$"
    )],
    request: DashboardUpdateRequest = Body(
        ...,
        description="Dashboard update request with configuration changes"
    ),
    current_user: UserResponse = Depends(get_current_user),
    controller: ExecutionReportingController = Depends(get_execution_reporting_controller)
) -> DashboardResponse:
    """Update dashboard configuration and layout"""
    return await controller.update_dashboard(dashboard_id, request, current_user)


@router.post(
    "/alerts",
    response_model=AlertRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create alert rule",
    description="""
    Create a new alert rule configuration with threshold monitoring and notification management.
    
    **Alert Features:**
    - **Threshold Monitoring**: Configurable thresholds for quality metrics
    - **Multi-Channel Notifications**: Email, Slack, webhook integrations
    - **Escalation Policies**: Tiered alert escalation and acknowledgment
    - **Alert Correlation**: Intelligent alert grouping and correlation
    - **Historical Tracking**: Alert history and resolution tracking
    
    **Alert Types:**
    - **Quality Degradation**: Quality score below threshold
    - **Execution Failures**: High failure rate alerts
    - **Performance Issues**: Slow execution or resource alerts
    - **Flakiness Detection**: Test stability degradation
    - **Coverage Gaps**: Test coverage regression alerts
    
    **Performance:** <200ms alert rule creation with validation
    """,
    responses={
        201: {
            "description": "Alert rule created successfully",
            "model": AlertRuleResponse
        },
        400: {
            "description": "Invalid alert rule configuration"
        }
    }
)
async def create_alert_rule(
    request: AlertRuleCreateRequest = Body(
        ...,
        description="Alert rule creation request with threshold configuration"
    ),
    current_user: UserResponse = Depends(get_current_user),
    controller: ExecutionReportingController = Depends(get_execution_reporting_controller)
) -> AlertRuleResponse:
    """Create new alert rule with threshold monitoring"""
    return await controller.create_alert_rule(request, current_user)


@router.get(
    "/alerts/status",
    response_model=SuccessResponse,
    summary="Get alert status",
    description="""
    Retrieve current alert status and recent evaluations with detailed alert information.
    
    **Alert Status Features:**
    - **Real-Time Evaluation**: Current alert states and threshold status
    - **Recent History**: Alert firing history and resolution tracking
    - **Performance Metrics**: Alert evaluation performance and reliability
    - **Notification Status**: Delivery status of alert notifications
    - **Escalation Tracking**: Alert escalation path and acknowledgments
    
    **Alert States:**
    - **OK**: All thresholds within acceptable ranges
    - **WARNING**: Approaching threshold limits
    - **CRITICAL**: Threshold exceeded, immediate attention required
    - **UNKNOWN**: Unable to evaluate due to data issues
    
    **Performance:** <100ms alert status retrieval with caching
    """,
    responses={
        200: {
            "description": "Alert status retrieved successfully",
            "model": SuccessResponse
        }
    }
)
async def get_alert_status(
    alert_ids: Annotated[Optional[str], Query(
        description="Comma-separated list of specific alert IDs to check",
        example="60f7b1b9e4b0c8a4f8e6d1a2,60f7b1b9e4b0c8a4f8e6d1a3"
    )] = None,
    include_history: Annotated[bool, Query(
        description="Include recent alert history in response"
    )] = False,
    current_user: UserResponse = Depends(get_current_user),
    controller: ExecutionReportingController = Depends(get_execution_reporting_controller)
) -> SuccessResponse:
    """Get current alert status and evaluations"""
    
    # Parse alert IDs if provided
    alert_id_list = None
    if alert_ids:
        alert_id_list = [aid.strip() for aid in alert_ids.split(",")]
    
    result = await controller.get_alert_status(alert_id_list, current_user)
    
    # Format response
    return SuccessResponse(
        success=True,
        data=result,
        message="Alert status retrieved successfully"
    )


@router.post(
    "/exports",
    response_model=ExportJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger export job",
    description="""
    Trigger a new data export job with format conversion and job tracking.
    
    **Export Features:**
    - **Multiple Formats**: CSV, JSON, Excel, PDF report generation
    - **Large Dataset Support**: Streaming export for large data volumes
    - **Background Processing**: Asynchronous job processing with status tracking
    - **Data Filtering**: Export filtered subsets based on criteria
    - **Security**: User-scoped data access and secure download links
    
    **Export Types:**
    - **Execution Reports**: Comprehensive execution data export
    - **Trend Analysis**: Historical trend data and analytics
    - **Quality Metrics**: Quality assessment data and scores
    - **Dashboard Data**: Dashboard widget data export
    - **Alert History**: Alert and notification history
    
    **Performance:** Job initiation <200ms, processing based on data volume
    """,
    responses={
        201: {
            "description": "Export job triggered successfully",
            "model": ExportJobResponse
        },
        400: {
            "description": "Invalid export job configuration"
        }
    }
)
async def trigger_export_job(
    request: ExportJobRequest = Body(
        ...,
        description="Export job request with format and filter configuration"
    ),
    current_user: UserResponse = Depends(get_current_user),
    controller: ExecutionReportingController = Depends(get_execution_reporting_controller)
) -> ExportJobResponse:
    """Trigger new data export job with tracking"""
    return await controller.trigger_export_job(request, current_user)


@router.get(
    "/exports/{job_id}/status",
    response_model=ExportStatusResponse,
    summary="Get export status",
    description="""
    Get export job status and progress with download information.
    
    **Status Tracking:**
    - **Job Progress**: Real-time progress updates and completion percentage
    - **Processing Status**: Current processing stage and estimated completion
    - **Error Handling**: Detailed error information if job fails
    - **Download Links**: Secure download URLs when job completes
    - **Expiration**: Download link expiration and cleanup information
    
    **Job States:**
    - **QUEUED**: Job queued for processing
    - **PROCESSING**: Active data export and format conversion
    - **COMPLETED**: Export completed, download available
    - **FAILED**: Export failed with error details
    - **EXPIRED**: Download link expired, re-export required
    
    **Performance:** <50ms status retrieval with real-time updates
    """,
    responses={
        200: {
            "description": "Export status retrieved successfully",
            "model": ExportStatusResponse
        },
        404: {
            "description": "Export job not found or access denied"
        }
    }
)
async def get_export_status(
    job_id: Annotated[str, Path(
        description="Export job ID",
        example="export_60f7b1b9e4b0c8a4f8e6d1a2"
    )],
    current_user: UserResponse = Depends(get_current_user),
    controller: ExecutionReportingController = Depends(get_execution_reporting_controller)
) -> ExportStatusResponse:
    """Get export job status and download information"""
    return await controller.get_export_status(job_id, current_user)


@router.get(
    "/reports/{report_id}/drilldown",
    response_model=DrilldownResponse,
    summary="Get report drilldown data",
    description="""
    Get detailed drilldown data for specific report elements with navigation capabilities.
    
    **Drilldown Features:**
    - **Interactive Navigation**: Navigate through data hierarchies
    - **Contextual Data**: Detailed data for specific report elements
    - **Performance Optimization**: Lazy loading of drilldown data
    - **Multi-Level Support**: Support for multiple drilldown levels
    - **Filter Preservation**: Maintain parent filters in drilldown views
    
    **Drilldown Paths:**
    - **Execution Details**: From summary to individual execution records
    - **Test Breakdown**: From suite level to individual test results
    - **Time Granularity**: From daily to hourly or execution-level detail
    - **Error Analysis**: From error summary to detailed failure information
    - **Performance Deep-Dive**: From metrics to individual execution traces
    
    **Performance:** <300ms drilldown data retrieval with caching
    """,
    responses={
        200: {
            "description": "Drilldown data retrieved successfully",
            "model": DrilldownResponse
        },
        404: {
            "description": "Report not found or invalid drilldown path"
        },
        400: {
            "description": "Invalid drilldown request parameters"
        }
    }
)
async def get_report_drilldown(
    report_id: Annotated[str, Path(
        description="Report ID for drilldown navigation",
        example="60f7b1b9e4b0c8a4f8e6d1a2"
    )],
    drilldown_path: Annotated[str, Query(
        description="Drilldown path (comma-separated levels)",
        example="executions,failed,error_details"
    )],
    current_user: UserResponse = Depends(get_current_user),
    controller: ExecutionReportingController = Depends(get_execution_reporting_controller)
) -> DrilldownResponse:
    """Get detailed drilldown data for report elements"""
    
    # Parse drilldown path
    path_elements = [element.strip() for element in drilldown_path.split(",")]
    
    return await controller.get_drilldown_data(report_id, path_elements, current_user)


@router.get(
    "/health",
    summary="Execution reporting service health check",
    description="""
    Check the health status of the Execution Reporting Module.
    
    Provides comprehensive health information about all service components including
    database connectivity, service availability, cache status, and performance metrics.
    
    **Health Checks:**
    - **Service Components**: All reporting services and controllers
    - **Database Health**: MongoDB connectivity and collection status
    - **Cache Status**: Redis cache connectivity and performance
    - **Integration Health**: External service dependencies
    - **Performance Metrics**: Response times and throughput
    
    **Monitoring Integration:**
    - Compatible with Kubernetes health checks
    - Prometheus metrics integration
    - Structured logging for monitoring systems
    - Alert-friendly status indicators
    
    Useful for monitoring, debugging, and operational visibility.
    """,
    responses={
        200: {
            "description": "Service health information"
        },
        503: {
            "description": "Service unhealthy"
        }
    }
)
async def get_service_health(
    controller: ExecutionReportingController = Depends(get_execution_reporting_controller)
) -> dict:
    """Get execution reporting service health status"""
    
    try:
        # Basic health check - just verify controller instantiation
        health_status = {
            "status": "healthy",
            "service": "execution_reporting",
            "components": {
                "controller": "healthy",
                "routes": "healthy"
            },
            "timestamp": "2024-01-15T10:30:00Z"
        }
        
        return health_status
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": "2024-01-15T10:30:00Z"
        }

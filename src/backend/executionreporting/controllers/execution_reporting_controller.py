"""
Execution Reporting Module - Execution Reporting Controller

HTTP orchestration controller for execution reporting endpoints.
Handles request validation, user context extraction, and service delegation.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from ...config.logging import get_logger
from ...auth.models import UserResponse
from ..services import (
    ReportService, TrendAnalysisService, QualityMetricsService,
    DashboardOrchestrationService, AlertManagementService, ExportService
)
from ..schemas.report_schemas import (
    ReportGenerationRequest, ExecutionReportResponse, TrendAnalysisResponse,
    QualityMetricsResponse, TimeRangeFilter, MetricFilter, DrilldownResponse
)
from ..schemas.dashboard_schemas import (
    DashboardCreateRequest, DashboardResponse, DashboardUpdateRequest
)
from ..schemas.alert_schemas import (
    AlertRuleCreateRequest, AlertRuleResponse, AlertConfigurationResponse
)
from ..schemas.export_schemas import (
    ExportJobRequest, ExportJobResponse, ExportStatusResponse
)

logger = get_logger(__name__)


class ExecutionReportingController:
    """
    HTTP orchestration controller for execution reporting operations.
    
    Provides endpoints for:
    - Report generation and retrieval
    - Trend analysis and forecasting
    - Quality metrics and assessment
    - Dashboard composition and management
    - Alert monitoring and configuration
    - Data export and job tracking
    """
    
    def __init__(
        self,
        database: AsyncIOMotorDatabase,
        report_service: ReportService,
        trend_analysis_service: TrendAnalysisService,
        quality_metrics_service: QualityMetricsService,
        dashboard_service: DashboardOrchestrationService,
        alert_service: AlertManagementService,
        export_service: ExportService
    ):
        """Initialize controller with service dependencies"""
        self.database = database
        self.report_service = report_service
        self.trend_analysis_service = trend_analysis_service
        self.quality_metrics_service = quality_metrics_service
        self.dashboard_service = dashboard_service
        self.alert_service = alert_service
        self.export_service = export_service
        self.logger = logger.bind(controller="ExecutionReportingController")
    
    async def get_execution_report(
        self,
        request: ReportGenerationRequest,
        user: UserResponse
    ) -> ExecutionReportResponse:
        """
        Generate and retrieve execution report with filtering and aggregation.
        
        Args:
            request: Report generation request with filters and parameters
            user: Authenticated user context from JWT
            
        Returns:
            ExecutionReportResponse: Generated report with metrics and data
            
        Raises:
            HTTPException: If report generation fails or validation errors occur
        """
        start_time = datetime.now(timezone.utc)
        request_id = f"report_{uuid.uuid4().hex[:8]}"
        
        try:
            self.logger.info(
                "Processing execution report request",
                request_id=request_id,
                user_id=user.user_id,
                report_type=request.report_type,
                time_range=request.time_range.dict() if request.time_range else None
            )
            
            # Validate request parameters
            await self._validate_report_request(request, user)
            
            # Generate report using service
            report = await self.report_service.generate_report(
                request=request,
                user_id=user.user_id
            )
            
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            self.logger.info(
                "Execution report generated successfully",
                request_id=request_id,
                user_id=user.user_id,
                processing_time_ms=processing_time,
                report_id=report.report_id
            )
            
            return report
            
        except ValueError as e:
            self.logger.warning(
                "Invalid report request parameters",
                request_id=request_id,
                user_id=user.user_id,
                error=str(e)
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid report parameters: {str(e)}"
            )
        except Exception as e:
            self.logger.error(
                "Report generation failed",
                request_id=request_id,
                user_id=user.user_id,
                error=str(e),
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate execution report"
            )
    
    async def get_trend_analysis(
        self,
        time_range: Optional[TimeRangeFilter] = None,
        metric_filter: Optional[MetricFilter] = None,
        user: UserResponse = None
    ) -> TrendAnalysisResponse:
        """
        Get trend analysis with pattern detection and forecasting.
        
        Args:
            time_range: Optional time range filter
            metric_filter: Optional metric filter for specific tests/suites
            user: Authenticated user context from JWT
            
        Returns:
            TrendAnalysisResponse: Trend analysis with patterns and forecasts
            
        Raises:
            HTTPException: If trend analysis fails
        """
        start_time = datetime.now(timezone.utc)
        request_id = f"trend_{uuid.uuid4().hex[:8]}"
        
        try:
            self.logger.info(
                "Processing trend analysis request",
                request_id=request_id,
                user_id=user.user_id,
                time_range=time_range.dict() if time_range else None
            )
            
            # Generate trend analysis using service
            analysis = await self.trend_analysis_service.analyze_trends(
                time_range=time_range,
                metric_filter=metric_filter,
                user_id=user.user_id
            )
            
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            self.logger.info(
                "Trend analysis completed successfully",
                request_id=request_id,
                user_id=user.user_id,
                processing_time_ms=processing_time,
                patterns_detected=len(analysis.patterns),
                trends_count=len(analysis.trends)
            )
            
            return analysis
            
        except Exception as e:
            self.logger.error(
                "Trend analysis failed",
                request_id=request_id,
                user_id=user.user_id,
                error=str(e),
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to perform trend analysis"
            )
    
    async def get_quality_metrics(
        self,
        time_range: Optional[TimeRangeFilter] = None,
        metric_filter: Optional[MetricFilter] = None,
        user: UserResponse = None
    ) -> QualityMetricsResponse:
        """
        Get quality metrics including flakiness scoring and stability analysis.
        
        Args:
            time_range: Optional time range filter
            metric_filter: Optional metric filter for specific tests/suites
            user: Authenticated user context from JWT
            
        Returns:
            QualityMetricsResponse: Quality metrics with scores and recommendations
            
        Raises:
            HTTPException: If quality metrics calculation fails
        """
        start_time = datetime.now(timezone.utc)
        request_id = f"quality_{uuid.uuid4().hex[:8]}"
        
        try:
            self.logger.info(
                "Processing quality metrics request",
                request_id=request_id,
                user_id=user.user_id,
                time_range=time_range.dict() if time_range else None
            )
            
            # Calculate quality metrics using service
            metrics = await self.quality_metrics_service.calculate_quality_metrics(
                time_range=time_range,
                metric_filter=metric_filter,
                user_id=user.user_id
            )
            
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            self.logger.info(
                "Quality metrics calculated successfully",
                request_id=request_id,
                user_id=user.user_id,
                processing_time_ms=processing_time,
                overall_score=metrics.overall_score,
                flakiness_score=metrics.flakiness_score
            )
            
            return metrics
            
        except Exception as e:
            self.logger.error(
                "Quality metrics calculation failed",
                request_id=request_id,
                user_id=user.user_id,
                error=str(e),
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to calculate quality metrics"
            )
    
    async def create_dashboard(
        self,
        request: DashboardCreateRequest,
        user: UserResponse
    ) -> DashboardResponse:
        """
        Create a new dashboard configuration.
        
        Args:
            request: Dashboard creation request with layout and widgets
            user: Authenticated user context from JWT
            
        Returns:
            DashboardResponse: Created dashboard with initial data
            
        Raises:
            HTTPException: If dashboard creation fails
        """
        start_time = datetime.now(timezone.utc)
        request_id = f"dashboard_create_{uuid.uuid4().hex[:8]}"
        
        try:
            self.logger.info(
                "Processing dashboard creation request",
                request_id=request_id,
                user_id=user.user_id,
                dashboard_name=request.name,
                widget_count=len(request.widgets)
            )
            
            # Validate dashboard request
            await self._validate_dashboard_request(request, user)
            
            # Create dashboard using service
            dashboard = await self.dashboard_service.create_dashboard(
                request=request,
                user_id=user.user_id
            )
            
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            self.logger.info(
                "Dashboard created successfully",
                request_id=request_id,
                user_id=user.user_id,
                processing_time_ms=processing_time,
                dashboard_id=dashboard.dashboard_id
            )
            
            return dashboard
            
        except ValueError as e:
            self.logger.warning(
                "Invalid dashboard creation parameters",
                request_id=request_id,
                user_id=user.user_id,
                error=str(e)
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid dashboard parameters: {str(e)}"
            )
        except Exception as e:
            self.logger.error(
                "Dashboard creation failed",
                request_id=request_id,
                user_id=user.user_id,
                error=str(e),
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create dashboard"
            )
    
    async def get_dashboard(
        self,
        dashboard_id: str,
        force_refresh: bool = False,
        user: UserResponse = None
    ) -> DashboardResponse:
        """
        Get dashboard data with all widget content.
        
        Args:
            dashboard_id: ID of dashboard to retrieve
            force_refresh: Whether to force refresh of cached data
            user: Authenticated user context from JWT
            
        Returns:
            DashboardResponse: Complete dashboard with widget data
            
        Raises:
            HTTPException: If dashboard not found or access denied
        """
        start_time = datetime.now(timezone.utc)
        request_id = f"dashboard_get_{uuid.uuid4().hex[:8]}"
        
        try:
            self.logger.info(
                "Processing dashboard retrieval request",
                request_id=request_id,
                user_id=user.user_id,
                dashboard_id=dashboard_id,
                force_refresh=force_refresh
            )
            
            # Get dashboard using service
            dashboard = await self.dashboard_service.get_dashboard(
                dashboard_id=dashboard_id,
                user_id=user.user_id,
                force_refresh=force_refresh
            )
            
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            self.logger.info(
                "Dashboard retrieved successfully",
                request_id=request_id,
                user_id=user.user_id,
                processing_time_ms=processing_time,
                dashboard_id=dashboard_id,
                widget_count=len(dashboard.widgets)
            )
            
            return dashboard
            
        except ValueError as e:
            self.logger.warning(
                "Dashboard access denied or not found",
                request_id=request_id,
                user_id=user.user_id,
                dashboard_id=dashboard_id,
                error=str(e)
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dashboard not found or access denied: {str(e)}"
            )
        except Exception as e:
            self.logger.error(
                "Dashboard retrieval failed",
                request_id=request_id,
                user_id=user.user_id,
                dashboard_id=dashboard_id,
                error=str(e),
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve dashboard"
            )
    
    async def update_dashboard(
        self,
        dashboard_id: str,
        request: DashboardUpdateRequest,
        user: UserResponse
    ) -> DashboardResponse:
        """
        Update existing dashboard configuration.
        
        Args:
            dashboard_id: ID of dashboard to update
            request: Dashboard update request
            user: Authenticated user context from JWT
            
        Returns:
            DashboardResponse: Updated dashboard configuration
            
        Raises:
            HTTPException: If dashboard not found or access denied
        """
        start_time = datetime.now(timezone.utc)
        request_id = f"dashboard_update_{uuid.uuid4().hex[:8]}"
        
        try:
            self.logger.info(
                "Processing dashboard update request",
                request_id=request_id,
                user_id=user.user_id,
                dashboard_id=dashboard_id
            )
            
            # Update dashboard using service
            dashboard = await self.dashboard_service.update_dashboard(
                dashboard_id=dashboard_id,
                request=request,
                user_id=user.user_id
            )
            
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            self.logger.info(
                "Dashboard updated successfully",
                request_id=request_id,
                user_id=user.user_id,
                processing_time_ms=processing_time,
                dashboard_id=dashboard_id
            )
            
            return dashboard
            
        except ValueError as e:
            self.logger.warning(
                "Dashboard update failed - not found or access denied",
                request_id=request_id,
                user_id=user.user_id,
                dashboard_id=dashboard_id,
                error=str(e)
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dashboard not found or access denied: {str(e)}"
            )
        except Exception as e:
            self.logger.error(
                "Dashboard update failed",
                request_id=request_id,
                user_id=user.user_id,
                dashboard_id=dashboard_id,
                error=str(e),
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update dashboard"
            )
    
    async def create_alert_rule(
        self,
        request: AlertRuleCreateRequest,
        user: UserResponse
    ) -> AlertRuleResponse:
        """
        Create a new alert rule configuration.
        
        Args:
            request: Alert rule creation request
            user: Authenticated user context from JWT
            
        Returns:
            AlertRuleResponse: Created alert rule configuration
            
        Raises:
            HTTPException: If alert rule creation fails
        """
        start_time = datetime.now(timezone.utc)
        request_id = f"alert_create_{uuid.uuid4().hex[:8]}"
        
        try:
            self.logger.info(
                "Processing alert rule creation request",
                request_id=request_id,
                user_id=user.user_id,
                alert_name=request.name,
                metric_type=request.metric_type
            )
            
            # Create alert rule using service
            alert_rule = await self.alert_service.create_alert_rule(
                request=request,
                user_id=user.user_id
            )
            
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            self.logger.info(
                "Alert rule created successfully",
                request_id=request_id,
                user_id=user.user_id,
                processing_time_ms=processing_time,
                alert_id=alert_rule.alert_id
            )
            
            return alert_rule
            
        except ValueError as e:
            self.logger.warning(
                "Invalid alert rule parameters",
                request_id=request_id,
                user_id=user.user_id,
                error=str(e)
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid alert rule parameters: {str(e)}"
            )
        except Exception as e:
            self.logger.error(
                "Alert rule creation failed",
                request_id=request_id,
                user_id=user.user_id,
                error=str(e),
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create alert rule"
            )
    
    async def get_alert_status(
        self,
        alert_ids: Optional[List[str]] = None,
        user: UserResponse = None
    ) -> Dict[str, Any]:
        """
        Get alert status and recent evaluations.
        
        Args:
            alert_ids: Optional list of specific alert IDs to check
            user: Authenticated user context from JWT
            
        Returns:
            Dict containing alert statuses and recent evaluations
            
        Raises:
            HTTPException: If alert status retrieval fails
        """
        start_time = datetime.now(timezone.utc)
        request_id = f"alert_status_{uuid.uuid4().hex[:8]}"
        
        try:
            self.logger.info(
                "Processing alert status request",
                request_id=request_id,
                user_id=user.user_id,
                alert_count=len(alert_ids) if alert_ids else "all"
            )
            
            # Evaluate alerts using service
            evaluation_results = await self.alert_service.evaluate_alerts(
                alert_ids=alert_ids,
                user_id=user.user_id
            )
            
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            self.logger.info(
                "Alert status retrieved successfully",
                request_id=request_id,
                user_id=user.user_id,
                processing_time_ms=processing_time,
                alerts_evaluated=len(evaluation_results)
            )
            
            return {
                "evaluation_results": {k: v.value for k, v in evaluation_results.items()},
                "evaluation_timestamp": datetime.now(timezone.utc),
                "total_alerts": len(evaluation_results)
            }
            
        except Exception as e:
            self.logger.error(
                "Alert status retrieval failed",
                request_id=request_id,
                user_id=user.user_id,
                error=str(e),
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve alert status"
            )
    
    async def trigger_export_job(
        self,
        request: ExportJobRequest,
        user: UserResponse
    ) -> ExportJobResponse:
        """
        Trigger a new data export job.
        
        Args:
            request: Export job request with parameters
            user: Authenticated user context from JWT
            
        Returns:
            ExportJobResponse: Created export job with tracking information
            
        Raises:
            HTTPException: If export job creation fails
        """
        start_time = datetime.now(timezone.utc)
        request_id = f"export_trigger_{uuid.uuid4().hex[:8]}"
        
        try:
            self.logger.info(
                "Processing export job trigger request",
                request_id=request_id,
                user_id=user.user_id,
                export_format=request.export_format,
                data_type=request.data_type
            )
            
            # Validate export request
            await self._validate_export_request(request, user)
            
            # Trigger export job using service
            export_job = await self.export_service.create_export_job(
                request=request,
                user_id=user.user_id
            )
            
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            self.logger.info(
                "Export job triggered successfully",
                request_id=request_id,
                user_id=user.user_id,
                processing_time_ms=processing_time,
                job_id=export_job.job_id
            )
            
            return export_job
            
        except ValueError as e:
            self.logger.warning(
                "Invalid export job parameters",
                request_id=request_id,
                user_id=user.user_id,
                error=str(e)
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid export parameters: {str(e)}"
            )
        except Exception as e:
            self.logger.error(
                "Export job trigger failed",
                request_id=request_id,
                user_id=user.user_id,
                error=str(e),
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to trigger export job"
            )
    
    async def get_export_status(
        self,
        job_id: str,
        user: UserResponse
    ) -> ExportStatusResponse:
        """
        Get export job status and progress.
        
        Args:
            job_id: ID of export job to check
            user: Authenticated user context from JWT
            
        Returns:
            ExportStatusResponse: Export job status and progress information
            
        Raises:
            HTTPException: If export job not found or access denied
        """
        start_time = datetime.now(timezone.utc)
        request_id = f"export_status_{uuid.uuid4().hex[:8]}"
        
        try:
            self.logger.info(
                "Processing export status request",
                request_id=request_id,
                user_id=user.user_id,
                job_id=job_id
            )
            
            # Get export status using service
            export_status = await self.export_service.get_export_status(
                job_id=job_id,
                user_id=user.user_id
            )
            
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            self.logger.info(
                "Export status retrieved successfully",
                request_id=request_id,
                user_id=user.user_id,
                processing_time_ms=processing_time,
                job_id=job_id,
                status=export_status.status
            )
            
            return export_status
            
        except ValueError as e:
            self.logger.warning(
                "Export job not found or access denied",
                request_id=request_id,
                user_id=user.user_id,
                job_id=job_id,
                error=str(e)
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Export job not found or access denied: {str(e)}"
            )
        except Exception as e:
            self.logger.error(
                "Export status retrieval failed",
                request_id=request_id,
                user_id=user.user_id,
                job_id=job_id,
                error=str(e),
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve export status"
            )
    
    async def get_drilldown_data(
        self,
        report_id: str,
        drilldown_path: List[str],
        user: UserResponse
    ) -> DrilldownResponse:
        """
        Get detailed drilldown data for specific report elements.
        
        Args:
            report_id: ID of the parent report
            drilldown_path: Path to the specific data element
            user: Authenticated user context from JWT
            
        Returns:
            DrilldownResponse: Detailed data for the specified element
            
        Raises:
            HTTPException: If drilldown fails or report not found
        """
        start_time = datetime.now(timezone.utc)
        request_id = f"drilldown_{uuid.uuid4().hex[:8]}"
        
        try:
            self.logger.info(
                "Processing drilldown request",
                request_id=request_id,
                user_id=user.user_id,
                report_id=report_id,
                drilldown_path=drilldown_path
            )
            
            # Get drilldown data using service
            drilldown_data = await self.report_service.get_drilldown_data(
                report_id=report_id,
                drilldown_path=drilldown_path,
                user_id=user.user_id
            )
            
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            self.logger.info(
                "Drilldown data retrieved successfully",
                request_id=request_id,
                user_id=user.user_id,
                processing_time_ms=processing_time,
                report_id=report_id,
                data_points=len(drilldown_data.data) if drilldown_data.data else 0
            )
            
            return drilldown_data
            
        except ValueError as e:
            self.logger.warning(
                "Invalid drilldown request",
                request_id=request_id,
                user_id=user.user_id,
                report_id=report_id,
                error=str(e)
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid drilldown request: {str(e)}"
            )
        except Exception as e:
            self.logger.error(
                "Drilldown request failed",
                request_id=request_id,
                user_id=user.user_id,
                report_id=report_id,
                error=str(e),
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve drilldown data"
            )
    
    # Validation Helper Methods
    
    async def _validate_report_request(
        self,
        request: ReportGenerationRequest,
        user: UserResponse
    ) -> None:
        """Validate report generation request parameters"""
        
        # Validate time range
        if request.time_range:
            if request.time_range.start_date >= request.time_range.end_date:
                raise ValueError("Start date must be before end date")
            
            # Check for reasonable time range limits
            time_diff = request.time_range.end_date - request.time_range.start_date
            if time_diff.days > 365:
                raise ValueError("Time range cannot exceed 365 days")
        
        # Validate metric filters
        if request.metric_filters:
            for metric_filter in request.metric_filters:
                if not metric_filter.filter_value:
                    raise ValueError(f"Filter value required for {metric_filter.filter_type}")
    
    async def _validate_dashboard_request(
        self,
        request: DashboardCreateRequest,
        user: UserResponse
    ) -> None:
        """Validate dashboard creation request parameters"""
        
        # Validate dashboard name
        if not request.name or len(request.name.strip()) < 3:
            raise ValueError("Dashboard name must be at least 3 characters")
        
        # Validate widget count
        if len(request.widgets) > 20:
            raise ValueError("Dashboard cannot have more than 20 widgets")
        
        if len(request.widgets) == 0:
            raise ValueError("Dashboard must have at least one widget")
        
        # Validate widget configurations
        widget_ids = [widget.widget_id for widget in request.widgets]
        if len(widget_ids) != len(set(widget_ids)):
            raise ValueError("Duplicate widget IDs found")
    
    async def _validate_export_request(
        self,
        request: ExportJobRequest,
        user: UserResponse
    ) -> None:
        """Validate export job request parameters"""
        
        # Validate export format
        supported_formats = ["CSV", "JSON", "XLSX", "PDF"]
        if request.export_format not in supported_formats:
            raise ValueError(f"Unsupported export format: {request.export_format}")
        
        # Validate data type
        supported_data_types = [
            "execution_reports", "trend_analysis", "quality_metrics",
            "dashboard_data", "alert_history"
        ]
        if request.data_type not in supported_data_types:
            raise ValueError(f"Unsupported data type: {request.data_type}")
        
        # Validate time range if provided
        if request.time_range:
            if request.time_range.start_date >= request.time_range.end_date:
                raise ValueError("Start date must be before end date")


class ExecutionReportingControllerFactory:
    """Factory for creating ExecutionReportingController instances"""
    
    @staticmethod
    def create(
        database: AsyncIOMotorDatabase,
        report_service: ReportService,
        trend_analysis_service: TrendAnalysisService,
        quality_metrics_service: QualityMetricsService,
        dashboard_service: DashboardOrchestrationService,
        alert_service: AlertManagementService,
        export_service: ExportService
    ) -> ExecutionReportingController:
        """Create and configure ExecutionReportingController instance"""
        return ExecutionReportingController(
            database=database,
            report_service=report_service,
            trend_analysis_service=trend_analysis_service,
            quality_metrics_service=quality_metrics_service,
            dashboard_service=dashboard_service,
            alert_service=alert_service,
            export_service=export_service
        ) 
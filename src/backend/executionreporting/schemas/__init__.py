"""
Execution Reporting Module - Schema Package

Provides Pydantic schemas for the Execution Reporting Module including:
- Report request/response schemas for all report types
- Trend analysis schemas for statistical data
- Quality metrics schemas for assessment data
- Alert configuration schemas for notification management
- Dashboard configuration schemas for user preferences
- Export job schemas for data export functionality

All schemas follow FastAPI best practices with comprehensive validation,
examples, and OpenAPI documentation support.
"""

from .report_schemas import (
    # Report Request Schemas
    ReportGenerationRequest,
    TrendAnalysisRequest,
    QualityMetricsRequest,
    DrilldownRequest,
    
    # Report Response Schemas
    ExecutionReportResponse,
    TrendAnalysisResponse,
    QualityMetricsResponse,
    DrilldownResponse,
    ReportListResponse,
    
    # Filter and Configuration Schemas
    ReportFilters,
    TimeRangeFilter,
    MetricFilter,
    DrilldownNavigation
)

from .dashboard_schemas import (
    # Dashboard Request Schemas
    DashboardCreateRequest,
    DashboardUpdateRequest,
    WidgetCreateRequest,
    WidgetUpdateRequest,
    
    # Dashboard Response Schemas
    DashboardResponse,
    DashboardListResponse,
    WidgetResponse,
    DashboardLayoutResponse,
    
    # Configuration Schemas
    DashboardPreferences,
    WidgetConfiguration,
    LayoutConfiguration
)

from .alert_schemas import (
    # Alert Request Schemas
    AlertRuleCreateRequest,
    AlertRuleUpdateRequest,
    AlertConfigurationRequest,
    
    # Alert Response Schemas
    AlertRuleResponse,
    AlertConfigurationResponse,
    AlertInstanceResponse,
    AlertListResponse,
    
    # Alert Management Schemas
    AlertThresholdConfig,
    NotificationChannelConfig,
    EscalationRuleConfig
)

from .export_schemas import (
    # Export Request Schemas
    ExportJobRequest,
    ExportConfigurationRequest,
    
    # Export Response Schemas
    ExportJobResponse,
    ExportJobListResponse,
    ExportStatusResponse,
    
    # Export Configuration Schemas
    ExportFormatConfig,
    ExportFilterConfig
)

__all__ = [
    # Report Schemas
    "ReportGenerationRequest",
    "TrendAnalysisRequest", 
    "QualityMetricsRequest",
    "DrilldownRequest",
    "ExecutionReportResponse",
    "TrendAnalysisResponse",
    "QualityMetricsResponse",
    "DrilldownResponse",
    "ReportListResponse",
    "ReportFilters",
    "TimeRangeFilter",
    "MetricFilter",
    "DrilldownNavigation",
    
    # Dashboard Schemas
    "DashboardCreateRequest",
    "DashboardUpdateRequest",
    "WidgetCreateRequest",
    "WidgetUpdateRequest",
    "DashboardResponse",
    "DashboardListResponse",
    "WidgetResponse",
    "DashboardLayoutResponse",
    "DashboardPreferences",
    "WidgetConfiguration",
    "LayoutConfiguration",
    
    # Alert Schemas
    "AlertRuleCreateRequest",
    "AlertRuleUpdateRequest",
    "AlertConfigurationRequest",
    "AlertRuleResponse",
    "AlertConfigurationResponse",
    "AlertInstanceResponse",
    "AlertListResponse",
    "AlertThresholdConfig",
    "NotificationChannelConfig",
    "EscalationRuleConfig",
    
    # Export Schemas
    "ExportJobRequest",
    "ExportConfigurationRequest",
    "ExportJobResponse",
    "ExportJobListResponse",
    "ExportStatusResponse",
    "ExportFormatConfig",
    "ExportFilterConfig"
] 
"""
Execution Reporting Module - Model Package

Provides MongoDB models for the Execution Reporting Module including:
- ExecutionReportModel: Core execution reporting model with aggregated metrics
- TrendAnalysisModel: Historical trend analysis and pattern recognition
- QualityMetricsModel: Quality scoring and assessment metrics
- AlertConfigurationModel: Alert threshold and notification configuration
- DashboardConfigurationModel: User dashboard preferences and layout
- ExportJobModel: Export job tracking and status management

All models follow the BaseMongoModel pattern with UTC timestamps,
version management, and optimized MongoDB indexing strategies.
"""

from .execution_report_model import (
    ExecutionReportModel,
    TrendAnalysisModel,
    QualityMetricsModel,
    AlertConfigurationModel,
    DashboardConfigurationModel,
    ExportJobModel,
    ReportType,
    TrendDirection,
    QualityScore,
    AlertStatus,
    AlertSeverity,
    ExportFormat,
    ExportStatus,
    MetricPeriod,
    AggregationLevel,
    DrilldownContext,
    QualityThreshold,
    TrendDataPoint,
    AlertRule,
    DashboardWidget
)

__all__ = [
    # Core Models
    "ExecutionReportModel",
    "TrendAnalysisModel", 
    "QualityMetricsModel",
    "AlertConfigurationModel",
    "DashboardConfigurationModel",
    "ExportJobModel",
    
    # Enums
    "ReportType",
    "TrendDirection",
    "QualityScore", 
    "AlertStatus",
    "AlertSeverity",
    "ExportFormat",
    "ExportStatus",
    "MetricPeriod",
    "AggregationLevel",
    
    # Supporting Models
    "DrilldownContext",
    "QualityThreshold",
    "TrendDataPoint",
    "AlertRule",
    "DashboardWidget"
] 
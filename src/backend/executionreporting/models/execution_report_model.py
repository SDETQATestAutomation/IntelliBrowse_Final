"""
Execution Reporting Module - Core Models

Implements comprehensive reporting models for execution analytics:
- ExecutionReportModel: Core execution reporting with aggregated metrics
- TrendAnalysisModel: Historical trend analysis and pattern recognition  
- QualityMetricsModel: Quality scoring and assessment metrics
- AlertConfigurationModel: Alert threshold and notification configuration
- DashboardConfigurationModel: User dashboard preferences and layout
- ExportJobModel: Export job tracking and status management

Based on Level 4 architectural design with performance optimization,
real-time analytics, and comprehensive quality intelligence.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from bson import ObjectId
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict

from ...config.logging import get_logger
from ...testexecution.models.execution_trace_model import BaseMongoModel

logger = get_logger(__name__)


class ReportType(str, Enum):
    """Type of execution report being generated"""
    SUMMARY = "summary"
    DETAILED = "detailed"
    TREND_ANALYSIS = "trend_analysis"
    QUALITY_METRICS = "quality_metrics"
    FAILURE_ANALYSIS = "failure_analysis"
    PERFORMANCE_ANALYSIS = "performance_analysis"
    DASHBOARD = "dashboard"
    EXPORT = "export"


class TrendDirection(str, Enum):
    """Direction of trend for metrics"""
    IMPROVING = "improving"
    DEGRADING = "degrading"
    STABLE = "stable"
    VOLATILE = "volatile"
    INSUFFICIENT_DATA = "insufficient_data"


class QualityScore(str, Enum):
    """Quality assessment scores"""
    EXCELLENT = "excellent"      # 90-100%
    GOOD = "good"               # 80-89%
    FAIR = "fair"               # 70-79%
    POOR = "poor"               # 60-69%
    CRITICAL = "critical"       # <60%


class AlertStatus(str, Enum):
    """Status of alert configurations and instances"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    TRIGGERED = "triggered"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class AlertSeverity(str, Enum):
    """Severity levels for alerts"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ExportFormat(str, Enum):
    """Supported export formats"""
    JSON = "json"
    CSV = "csv"
    EXCEL = "excel"
    PDF = "pdf"


class ExportStatus(str, Enum):
    """Status of export jobs"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MetricPeriod(str, Enum):
    """Time periods for metric calculation"""
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


class AggregationLevel(str, Enum):
    """Level of data aggregation for reports"""
    TEST_CASE = "test_case"
    TEST_SUITE = "test_suite"
    PROJECT = "project"
    TEAM = "team"
    ORGANIZATION = "organization"


class DrilldownContext(BaseModel):
    """Context information for drill-down navigation"""
    level: AggregationLevel = Field(..., description="Current aggregation level")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Applied filters")
    parent_context: Optional[str] = Field(None, description="Parent context ID for navigation")
    breadcrumb: List[Dict[str, Any]] = Field(default_factory=list, description="Navigation breadcrumb")
    
    model_config = ConfigDict(use_enum_values=True)


class QualityThreshold(BaseModel):
    """Quality threshold configuration"""
    metric_name: str = Field(..., description="Name of the quality metric")
    excellent_threshold: float = Field(90.0, ge=0, le=100, description="Threshold for excellent quality")
    good_threshold: float = Field(80.0, ge=0, le=100, description="Threshold for good quality")
    fair_threshold: float = Field(70.0, ge=0, le=100, description="Threshold for fair quality")
    poor_threshold: float = Field(60.0, ge=0, le=100, description="Threshold for poor quality")
    alert_enabled: bool = Field(True, description="Whether to generate alerts for this metric")
    
    @model_validator(mode='after')
    def validate_thresholds(self):
        """Validate threshold ordering"""
        thresholds = [self.excellent_threshold, self.good_threshold, self.fair_threshold, self.poor_threshold]
        if thresholds != sorted(thresholds, reverse=True):
            raise ValueError("Thresholds must be in descending order")
        return self
    
    model_config = ConfigDict(use_enum_values=True)


class TrendDataPoint(BaseModel):
    """Single data point in a trend analysis"""
    timestamp: datetime = Field(..., description="Data point timestamp")
    value: float = Field(..., description="Metric value at this point")
    data_points: int = Field(1, ge=1, description="Number of data points averaged")
    confidence: Optional[float] = Field(None, ge=0, le=1, description="Confidence level of the measurement")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
        }
    )


class AlertRule(BaseModel):
    """Configuration for alert rules"""
    rule_id: str = Field(..., description="Unique rule identifier")
    name: str = Field(..., description="Human-readable rule name")
    description: Optional[str] = Field(None, description="Rule description")
    metric_name: str = Field(..., description="Target metric for alert")
    condition: str = Field(..., description="Alert condition (e.g., 'less_than', 'greater_than')")
    threshold_value: float = Field(..., description="Threshold value for alert")
    severity: AlertSeverity = Field(..., description="Alert severity level")
    notification_channels: List[str] = Field(default_factory=list, description="Notification channel IDs")
    enabled: bool = Field(True, description="Whether rule is active")
    cooldown_minutes: int = Field(30, ge=0, description="Cooldown period between alerts")
    
    model_config = ConfigDict(use_enum_values=True)


class DashboardWidget(BaseModel):
    """Configuration for dashboard widgets"""
    widget_id: str = Field(..., description="Unique widget identifier")
    widget_type: str = Field(..., description="Type of widget (chart, table, metric, etc.)")
    title: str = Field(..., description="Widget title")
    position: Dict[str, Any] = Field(..., description="Widget position and size")
    configuration: Dict[str, Any] = Field(default_factory=dict, description="Widget-specific configuration")
    data_source: str = Field(..., description="Data source for widget")
    refresh_interval_seconds: int = Field(300, ge=30, description="Auto-refresh interval")
    visible: bool = Field(True, description="Whether widget is visible")
    
    model_config = ConfigDict(use_enum_values=True)


class ExecutionReportModel(BaseMongoModel):
    """
    Core execution reporting model with aggregated metrics.
    
    Provides comprehensive execution analytics with intelligent caching,
    real-time updates, and drill-down capabilities for quality insights.
    """
    
    # Report Identity
    report_id: str = Field(..., description="Unique report identifier")
    report_type: ReportType = Field(..., description="Type of report")
    report_name: str = Field(..., description="Human-readable report name")
    
    # Report Scope and Filters
    scope: AggregationLevel = Field(..., description="Aggregation level for the report")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Applied filters")
    time_range: Dict[str, datetime] = Field(..., description="Report time range (start_date, end_date)")
    
    # Execution Metrics
    total_executions: int = Field(0, ge=0, description="Total executions in scope")
    passed_executions: int = Field(0, ge=0, description="Passed executions")
    failed_executions: int = Field(0, ge=0, description="Failed executions")
    cancelled_executions: int = Field(0, ge=0, description="Cancelled executions")
    
    # Performance Metrics
    average_duration_ms: Optional[float] = Field(None, ge=0, description="Average execution duration")
    median_duration_ms: Optional[float] = Field(None, ge=0, description="Median execution duration")
    total_duration_ms: Optional[int] = Field(None, ge=0, description="Total execution duration")
    
    # Quality Metrics
    pass_rate: float = Field(0.0, ge=0, le=1, description="Overall pass rate")
    flakiness_index: float = Field(0.0, ge=0, le=1, description="Test flakiness index")
    quality_score: QualityScore = Field(QualityScore.CRITICAL, description="Overall quality score")
    
    # Drill-down Context
    drilldown_context: Optional[DrilldownContext] = Field(None, description="Context for drill-down navigation")
    parent_report_id: Optional[str] = Field(None, description="Parent report ID for hierarchical navigation")
    
    # Caching and Performance
    cache_key: Optional[str] = Field(None, description="Cache key for performance optimization")
    cached_at: Optional[datetime] = Field(None, description="Cache generation timestamp")
    cache_ttl_seconds: int = Field(3600, ge=60, description="Cache time-to-live")
    
    # Real-time Updates
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last data update")
    update_frequency_seconds: int = Field(300, ge=30, description="Update frequency for real-time data")
    is_real_time: bool = Field(False, description="Whether report uses real-time data")
    
    # Report Generation
    generated_by: str = Field(..., description="User or system that generated report")
    generation_duration_ms: Optional[int] = Field(None, ge=0, description="Report generation time")
    data_freshness_seconds: Optional[int] = Field(None, ge=0, description="Age of underlying data")
    
    # Metadata
    tags: List[str] = Field(default_factory=list, description="Report tags for organization")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional report metadata")
    
    @model_validator(mode='after')
    def validate_metrics_consistency(self):
        """Validate execution metrics consistency"""
        # Validate execution counts
        calculated_total = self.passed_executions + self.failed_executions + self.cancelled_executions
        if self.total_executions != calculated_total:
            raise ValueError(f"Total executions {self.total_executions} doesn't match sum of individual counts {calculated_total}")
        
        # Calculate pass rate if not provided
        if self.pass_rate == 0.0 and self.total_executions > 0:
            self.pass_rate = self.passed_executions / self.total_executions
        
        # Validate time range
        if self.time_range.get('end_date') and self.time_range.get('start_date'):
            if self.time_range['end_date'] < self.time_range['start_date']:
                raise ValueError("End date cannot be before start date")
                
        return self
    
    def calculate_quality_score(self) -> QualityScore:
        """Calculate overall quality score based on metrics"""
        if self.total_executions == 0:
            return QualityScore.INSUFFICIENT_DATA
        
        # Weight different factors for quality score
        pass_rate_weight = 0.6
        flakiness_weight = 0.3
        duration_weight = 0.1
        
        # Calculate weighted score
        pass_score = self.pass_rate * 100
        flakiness_score = (1 - self.flakiness_index) * 100
        
        # Performance score (simple heuristic)
        duration_score = 100  # Default if no duration data
        if self.average_duration_ms:
            # Normalize against expected duration (placeholder logic)
            expected_duration = 30000  # 30 seconds baseline
            if self.average_duration_ms <= expected_duration:
                duration_score = 100
            else:
                duration_score = max(0, 100 - ((self.average_duration_ms - expected_duration) / expected_duration) * 50)
        
        overall_score = (
            pass_score * pass_rate_weight +
            flakiness_score * flakiness_weight +
            duration_score * duration_weight
        )
        
        # Map to quality score enum
        if overall_score >= 90:
            return QualityScore.EXCELLENT
        elif overall_score >= 80:
            return QualityScore.GOOD
        elif overall_score >= 70:
            return QualityScore.FAIR
        elif overall_score >= 60:
            return QualityScore.POOR
        else:
            return QualityScore.CRITICAL
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_encoders={
            ObjectId: str,
            datetime: lambda v: v.isoformat() if v else None,
        }
    )


class TrendAnalysisModel(BaseMongoModel):
    """
    Historical trend analysis and pattern recognition model.
    
    Provides sophisticated trend analysis with statistical modeling,
    pattern detection, and predictive insights for quality improvement.
    """
    
    # Trend Identity
    analysis_id: str = Field(..., description="Unique analysis identifier")
    metric_name: str = Field(..., description="Name of the metric being analyzed")
    scope: AggregationLevel = Field(..., description="Scope of trend analysis")
    
    # Analysis Period
    period: MetricPeriod = Field(..., description="Analysis period granularity")
    start_date: datetime = Field(..., description="Analysis start date")
    end_date: datetime = Field(..., description="Analysis end date")
    data_points_count: int = Field(0, ge=0, description="Number of data points in analysis")
    
    # Trend Data
    data_points: List[TrendDataPoint] = Field(default_factory=list, description="Historical data points")
    trend_direction: TrendDirection = Field(..., description="Overall trend direction")
    
    # Statistical Analysis
    mean_value: float = Field(0.0, description="Mean value across period")
    median_value: float = Field(0.0, description="Median value across period")
    standard_deviation: float = Field(0.0, ge=0, description="Standard deviation")
    variance: float = Field(0.0, ge=0, description="Variance")
    
    # Trend Metrics
    slope: float = Field(0.0, description="Trend slope (rate of change)")
    correlation_coefficient: float = Field(0.0, ge=-1, le=1, description="Correlation with time")
    confidence_interval: Dict[str, float] = Field(default_factory=dict, description="95% confidence interval")
    
    # Pattern Recognition
    seasonal_patterns: List[Dict[str, Any]] = Field(default_factory=list, description="Detected seasonal patterns")
    anomalies: List[Dict[str, Any]] = Field(default_factory=list, description="Detected anomalies")
    change_points: List[Dict[str, Any]] = Field(default_factory=list, description="Significant change points")
    
    # Forecasting
    forecast_points: List[TrendDataPoint] = Field(default_factory=list, description="Forecasted future points")
    forecast_confidence: float = Field(0.0, ge=0, le=1, description="Forecast confidence level")
    
    # Analysis Metadata
    analysis_method: str = Field("statistical", description="Analysis method used")
    model_parameters: Dict[str, Any] = Field(default_factory=dict, description="Model parameters")
    generated_by: str = Field(..., description="User or system that generated analysis")
    
    @model_validator(mode='after')
    def validate_analysis_data(self):
        """Validate trend analysis data consistency"""
        if self.end_date < self.start_date:
            raise ValueError("End date cannot be before start date")
        
        if self.data_points_count != len(self.data_points):
            raise ValueError("Data points count doesn't match actual data points")
        
        # Validate confidence interval
        if self.confidence_interval:
            if 'lower' in self.confidence_interval and 'upper' in self.confidence_interval:
                if self.confidence_interval['lower'] > self.confidence_interval['upper']:
                    raise ValueError("Lower confidence bound cannot exceed upper bound")
        
        return self
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_encoders={
            ObjectId: str,
            datetime: lambda v: v.isoformat() if v else None,
        }
    )


class QualityMetricsModel(BaseMongoModel):
    """
    Quality scoring and assessment metrics model.
    
    Provides comprehensive quality intelligence with scoring algorithms,
    threshold management, and automated quality assessment.
    """
    
    # Metrics Identity
    metrics_id: str = Field(..., description="Unique metrics identifier")
    scope: AggregationLevel = Field(..., description="Metrics aggregation scope")
    evaluation_period: MetricPeriod = Field(..., description="Evaluation period")
    
    # Quality Scores
    overall_quality_score: QualityScore = Field(..., description="Overall quality assessment")
    reliability_score: float = Field(0.0, ge=0, le=100, description="Reliability score (0-100)")
    performance_score: float = Field(0.0, ge=0, le=100, description="Performance score (0-100)")
    maintainability_score: float = Field(0.0, ge=0, le=100, description="Maintainability score (0-100)")
    
    # Detailed Metrics
    pass_rate: float = Field(0.0, ge=0, le=1, description="Overall pass rate")
    flakiness_index: float = Field(0.0, ge=0, le=1, description="Test flakiness index")
    mean_time_to_recovery: Optional[float] = Field(None, ge=0, description="MTTR in hours")
    defect_escape_rate: float = Field(0.0, ge=0, le=1, description="Defect escape rate")
    
    # Performance Metrics
    average_execution_time: Optional[float] = Field(None, ge=0, description="Average execution time in ms")
    performance_trend: TrendDirection = Field(..., description="Performance trend direction")
    resource_efficiency: float = Field(0.0, ge=0, le=1, description="Resource utilization efficiency")
    
    # Quality Thresholds
    thresholds: List[QualityThreshold] = Field(default_factory=list, description="Quality thresholds configuration")
    threshold_violations: List[Dict[str, Any]] = Field(default_factory=list, description="Current threshold violations")
    
    # Historical Comparison
    previous_period_score: Optional[float] = Field(None, ge=0, le=100, description="Previous period score")
    score_change: Optional[float] = Field(None, description="Score change from previous period")
    improvement_trend: TrendDirection = Field(TrendDirection.STABLE, description="Quality improvement trend")
    
    # Insights and Recommendations
    quality_insights: List[str] = Field(default_factory=list, description="Quality insights and observations")
    improvement_recommendations: List[str] = Field(default_factory=list, description="Improvement recommendations")
    risk_factors: List[str] = Field(default_factory=list, description="Identified risk factors")
    
    # Analysis Context
    data_completeness: float = Field(1.0, ge=0, le=1, description="Data completeness ratio")
    confidence_level: float = Field(0.95, ge=0, le=1, description="Analysis confidence level")
    generated_by: str = Field(..., description="User or system that generated metrics")
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_encoders={
            ObjectId: str,
            datetime: lambda v: v.isoformat() if v else None,
        }
    )


class AlertConfigurationModel(BaseMongoModel):
    """
    Alert threshold and notification configuration model.
    
    Provides flexible alert management with configurable thresholds,
    escalation rules, and multi-channel notification support.
    """
    
    # Alert Configuration Identity
    config_id: str = Field(..., description="Unique configuration identifier")
    name: str = Field(..., description="Human-readable configuration name")
    description: Optional[str] = Field(None, description="Configuration description")
    
    # Alert Rules
    rules: List[AlertRule] = Field(default_factory=list, description="Alert rules configuration")
    global_enabled: bool = Field(True, description="Whether alerting is globally enabled")
    
    # Notification Configuration
    notification_channels: List[Dict[str, Any]] = Field(default_factory=list, description="Notification channels")
    escalation_rules: List[Dict[str, Any]] = Field(default_factory=list, description="Alert escalation rules")
    
    # Alert History
    recent_alerts: List[Dict[str, Any]] = Field(default_factory=list, description="Recent alert instances")
    alert_statistics: Dict[str, Any] = Field(default_factory=dict, description="Alert frequency statistics")
    
    # Configuration Management
    owner: str = Field(..., description="Configuration owner")
    team: Optional[str] = Field(None, description="Team responsible for alerts")
    last_modified_by: str = Field(..., description="Last modifier")
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_encoders={
            ObjectId: str,
            datetime: lambda v: v.isoformat() if v else None,
        }
    )


class DashboardConfigurationModel(BaseMongoModel):
    """
    User dashboard preferences and layout configuration model.
    
    Provides personalized dashboard management with flexible layouts,
    widget configuration, and user preference persistence.
    """
    
    # Dashboard Identity
    dashboard_id: str = Field(..., description="Unique dashboard identifier")
    name: str = Field(..., description="Dashboard name")
    description: Optional[str] = Field(None, description="Dashboard description")
    
    # User and Access
    owner_id: str = Field(..., description="Dashboard owner user ID")
    shared_with: List[str] = Field(default_factory=list, description="User IDs with access")
    is_default: bool = Field(False, description="Whether this is the default dashboard")
    
    # Layout Configuration
    layout: Dict[str, Any] = Field(default_factory=dict, description="Dashboard layout configuration")
    widgets: List[DashboardWidget] = Field(default_factory=list, description="Dashboard widgets")
    theme: str = Field("default", description="Dashboard theme")
    
    # Display Settings
    auto_refresh: bool = Field(True, description="Whether to auto-refresh data")
    refresh_interval_seconds: int = Field(300, ge=30, description="Auto-refresh interval")
    timezone: str = Field("UTC", description="Display timezone")
    
    # Filters and Preferences
    default_filters: Dict[str, Any] = Field(default_factory=dict, description="Default filter values")
    saved_views: List[Dict[str, Any]] = Field(default_factory=list, description="Saved dashboard views")
    
    # Usage Analytics
    last_accessed: Optional[datetime] = Field(None, description="Last access timestamp")
    access_count: int = Field(0, ge=0, description="Number of times accessed")
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_encoders={
            ObjectId: str,
            datetime: lambda v: v.isoformat() if v else None,
        }
    )


class ExportJobModel(BaseMongoModel):
    """
    Export job tracking and status management model.
    
    Provides comprehensive export job management with status tracking,
    progress monitoring, and file delivery mechanisms.
    """
    
    # Job Identity
    job_id: str = Field(..., description="Unique export job identifier")
    name: str = Field(..., description="Human-readable job name")
    description: Optional[str] = Field(None, description="Job description")
    
    # Export Configuration
    export_format: ExportFormat = Field(..., description="Export format")
    data_source: str = Field(..., description="Data source for export")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Export filters")
    columns: Optional[List[str]] = Field(None, description="Specific columns to export")
    
    # Job Status
    status: ExportStatus = Field(ExportStatus.PENDING, description="Current job status")
    progress_percentage: float = Field(0.0, ge=0, le=100, description="Job progress percentage")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    
    # Timing
    started_at: Optional[datetime] = Field(None, description="Job start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Job completion timestamp")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")
    
    # Output
    file_path: Optional[str] = Field(None, description="Generated file path")
    file_size_bytes: Optional[int] = Field(None, ge=0, description="Generated file size")
    download_url: Optional[str] = Field(None, description="Download URL")
    expires_at: Optional[datetime] = Field(None, description="Download URL expiration")
    
    # Job Configuration
    requested_by: str = Field(..., description="User who requested export")
    priority: int = Field(1, ge=1, le=5, description="Job priority (1=highest)")
    max_records: Optional[int] = Field(None, ge=1, description="Maximum records to export")
    
    # Metadata
    job_metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional job metadata")
    
    @model_validator(mode='after')
    def validate_job_timing(self):
        """Validate job timing consistency"""
        if self.completed_at and self.started_at:
            if self.completed_at < self.started_at:
                raise ValueError("Completion time cannot be before start time")
        
        if self.status == ExportStatus.COMPLETED:
            if not self.completed_at:
                raise ValueError("Completed jobs must have completion timestamp")
            if not self.file_path:
                raise ValueError("Completed jobs must have file path")
        
        return self
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_encoders={
            ObjectId: str,
            datetime: lambda v: v.isoformat() if v else None,
        }
    ) 
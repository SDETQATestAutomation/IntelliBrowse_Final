"""
Execution Reporting Module - Report Schemas

Provides comprehensive Pydantic schemas for report generation, trend analysis,
quality metrics, and drill-down functionality with validation and examples.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, field_validator, ConfigDict

from ..models.execution_report_model import (
    ReportType, TrendDirection, QualityScore, MetricPeriod, AggregationLevel
)


class TimeRangeFilter(BaseModel):
    """Time range filter for reports"""
    start_date: datetime = Field(..., description="Start date for the report")
    end_date: datetime = Field(..., description="End date for the report")
    timezone: str = Field("UTC", description="Timezone for date interpretation")
    
    @field_validator('end_date')
    @classmethod
    def validate_end_after_start(cls, v, info):
        """Ensure end date is after start date"""
        if 'start_date' in info.data and v < info.data['start_date']:
            raise ValueError("End date must be after start date")
        return v
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "start_date": "2024-01-01T00:00:00Z",
                "end_date": "2024-01-31T23:59:59Z",
                "timezone": "UTC"
            }
        }
    )


class MetricFilter(BaseModel):
    """Filter for specific metrics"""
    test_suite_ids: Optional[List[str]] = Field(None, description="Filter by test suite IDs")
    test_case_ids: Optional[List[str]] = Field(None, description="Filter by test case IDs")
    execution_types: Optional[List[str]] = Field(None, description="Filter by execution types")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    user_ids: Optional[List[str]] = Field(None, description="Filter by user IDs")
    status_filter: Optional[List[str]] = Field(None, description="Filter by execution status")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "test_suite_ids": ["suite_1", "suite_2"],
                "tags": ["regression", "smoke"],
                "status_filter": ["passed", "failed"]
            }
        }
    )


class ReportFilters(BaseModel):
    """Comprehensive filter configuration for reports"""
    time_range: TimeRangeFilter = Field(..., description="Time range for the report")
    metrics: Optional[MetricFilter] = Field(None, description="Metric-specific filters")
    aggregation_level: AggregationLevel = Field(AggregationLevel.PROJECT, description="Data aggregation level")
    include_details: bool = Field(False, description="Include detailed execution data")
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "time_range": {
                    "start_date": "2024-01-01T00:00:00Z",
                    "end_date": "2024-01-31T23:59:59Z",
                    "timezone": "UTC"
                },
                "aggregation_level": "project",
                "include_details": False
            }
        }
    )


class DrilldownNavigation(BaseModel):
    """Navigation context for drill-down functionality"""
    parent_report_id: Optional[str] = Field(None, description="Parent report ID")
    breadcrumb: List[Dict[str, Any]] = Field(default_factory=list, description="Navigation breadcrumb")
    current_level: AggregationLevel = Field(..., description="Current aggregation level")
    available_levels: List[AggregationLevel] = Field(default_factory=list, description="Available drill-down levels")
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "current_level": "test_suite",
                "available_levels": ["test_case"],
                "breadcrumb": [
                    {"level": "project", "name": "MyProject", "id": "project_1"},
                    {"level": "test_suite", "name": "Regression Suite", "id": "suite_1"}
                ]
            }
        }
    )


class ReportGenerationRequest(BaseModel):
    """Request schema for generating execution reports"""
    report_type: ReportType = Field(..., description="Type of report to generate")
    name: Optional[str] = Field(None, description="Custom name for the report")
    filters: ReportFilters = Field(..., description="Report filters and configuration")
    cache_enabled: bool = Field(True, description="Whether to use cached data if available")
    real_time: bool = Field(False, description="Whether to use real-time data")
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "report_type": "summary",
                "name": "Weekly Summary Report",
                "filters": {
                    "time_range": {
                        "start_date": "2024-01-01T00:00:00Z",
                        "end_date": "2024-01-07T23:59:59Z",
                        "timezone": "UTC"
                    },
                    "aggregation_level": "project"
                },
                "cache_enabled": True,
                "real_time": False
            }
        }
    )


class TrendAnalysisRequest(BaseModel):
    """Request schema for trend analysis"""
    metric_name: str = Field(..., description="Name of the metric to analyze")
    period: MetricPeriod = Field(..., description="Analysis period granularity")
    filters: ReportFilters = Field(..., description="Analysis filters")
    include_forecast: bool = Field(False, description="Include forecast data")
    forecast_periods: int = Field(5, ge=1, le=30, description="Number of periods to forecast")
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "metric_name": "pass_rate",
                "period": "week",
                "filters": {
                    "time_range": {
                        "start_date": "2024-01-01T00:00:00Z",
                        "end_date": "2024-03-31T23:59:59Z",
                        "timezone": "UTC"
                    },
                    "aggregation_level": "project"
                },
                "include_forecast": True,
                "forecast_periods": 4
            }
        }
    )


class QualityMetricsRequest(BaseModel):
    """Request schema for quality metrics analysis"""
    scope: AggregationLevel = Field(..., description="Scope of quality analysis")
    period: MetricPeriod = Field(..., description="Analysis period")
    filters: ReportFilters = Field(..., description="Quality metrics filters")
    include_recommendations: bool = Field(True, description="Include improvement recommendations")
    benchmark_comparison: bool = Field(False, description="Include benchmark comparison")
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "scope": "project",
                "period": "month",
                "filters": {
                    "time_range": {
                        "start_date": "2024-01-01T00:00:00Z",
                        "end_date": "2024-01-31T23:59:59Z",
                        "timezone": "UTC"
                    },
                    "aggregation_level": "project"
                },
                "include_recommendations": True,
                "benchmark_comparison": False
            }
        }
    )


class DrilldownRequest(BaseModel):
    """Request schema for drill-down functionality"""
    parent_report_id: str = Field(..., description="Parent report ID for drill-down")
    target_level: AggregationLevel = Field(..., description="Target aggregation level")
    target_id: str = Field(..., description="ID of the target entity to drill into")
    filters: Optional[ReportFilters] = Field(None, description="Additional filters for drill-down")
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "parent_report_id": "report_12345",
                "target_level": "test_case",
                "target_id": "suite_regression_001",
                "filters": {
                    "time_range": {
                        "start_date": "2024-01-01T00:00:00Z",
                        "end_date": "2024-01-31T23:59:59Z",
                        "timezone": "UTC"
                    },
                    "aggregation_level": "test_case"
                }
            }
        }
    )


class ExecutionReportResponse(BaseModel):
    """Response schema for execution reports"""
    report_id: str = Field(..., description="Unique report identifier")
    report_type: ReportType = Field(..., description="Type of report")
    name: str = Field(..., description="Report name")
    
    # Execution Metrics
    total_executions: int = Field(..., description="Total number of executions")
    passed_executions: int = Field(..., description="Number of passed executions")
    failed_executions: int = Field(..., description="Number of failed executions")
    cancelled_executions: int = Field(..., description="Number of cancelled executions")
    
    # Calculated Metrics
    pass_rate: float = Field(..., description="Overall pass rate")
    flakiness_index: float = Field(..., description="Test flakiness index")
    quality_score: QualityScore = Field(..., description="Overall quality score")
    
    # Performance Metrics
    average_duration_ms: Optional[float] = Field(None, description="Average execution duration")
    total_duration_ms: Optional[int] = Field(None, description="Total execution duration")
    
    # Navigation
    drilldown_navigation: Optional[DrilldownNavigation] = Field(None, description="Drill-down navigation context")
    
    # Metadata
    generated_at: datetime = Field(..., description="Report generation timestamp")
    data_freshness_seconds: Optional[int] = Field(None, description="Age of underlying data")
    cached: bool = Field(False, description="Whether data was retrieved from cache")
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
        },
        json_schema_extra={
            "example": {
                "report_id": "report_12345",
                "report_type": "summary",
                "name": "Weekly Summary Report",
                "total_executions": 1250,
                "passed_executions": 1180,
                "failed_executions": 65,
                "cancelled_executions": 5,
                "pass_rate": 0.944,
                "flakiness_index": 0.032,
                "quality_score": "good",
                "average_duration_ms": 45230.5,
                "total_duration_ms": 56538125,
                "generated_at": "2024-01-08T10:30:00Z",
                "data_freshness_seconds": 300,
                "cached": False
            }
        }
    )


class TrendAnalysisResponse(BaseModel):
    """Response schema for trend analysis"""
    analysis_id: str = Field(..., description="Unique analysis identifier")
    metric_name: str = Field(..., description="Name of analyzed metric")
    period: MetricPeriod = Field(..., description="Analysis period")
    
    # Trend Data
    trend_direction: TrendDirection = Field(..., description="Overall trend direction")
    data_points: List[Dict[str, Any]] = Field(..., description="Historical data points")
    
    # Statistical Analysis
    mean_value: float = Field(..., description="Mean value across period")
    standard_deviation: float = Field(..., description="Standard deviation")
    slope: float = Field(..., description="Trend slope")
    correlation_coefficient: float = Field(..., description="Correlation with time")
    
    # Pattern Recognition
    seasonal_patterns: List[Dict[str, Any]] = Field(default_factory=list, description="Detected patterns")
    anomalies: List[Dict[str, Any]] = Field(default_factory=list, description="Detected anomalies")
    
    # Forecasting
    forecast_points: Optional[List[Dict[str, Any]]] = Field(None, description="Forecasted data points")
    forecast_confidence: Optional[float] = Field(None, description="Forecast confidence level")
    
    # Metadata
    generated_at: datetime = Field(..., description="Analysis generation timestamp")
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
        },
        json_schema_extra={
            "example": {
                "analysis_id": "trend_12345",
                "metric_name": "pass_rate",
                "period": "week",
                "trend_direction": "improving",
                "data_points": [
                    {"timestamp": "2024-01-01T00:00:00Z", "value": 0.85, "confidence": 0.95},
                    {"timestamp": "2024-01-08T00:00:00Z", "value": 0.88, "confidence": 0.95}
                ],
                "mean_value": 0.87,
                "standard_deviation": 0.05,
                "slope": 0.002,
                "correlation_coefficient": 0.78,
                "generated_at": "2024-01-08T10:30:00Z"
            }
        }
    )


class QualityMetricsResponse(BaseModel):
    """Response schema for quality metrics"""
    metrics_id: str = Field(..., description="Unique metrics identifier")
    scope: AggregationLevel = Field(..., description="Metrics scope")
    evaluation_period: MetricPeriod = Field(..., description="Evaluation period")
    
    # Quality Scores
    overall_quality_score: QualityScore = Field(..., description="Overall quality score")
    reliability_score: float = Field(..., description="Reliability score (0-100)")
    performance_score: float = Field(..., description="Performance score (0-100)")
    maintainability_score: float = Field(..., description="Maintainability score (0-100)")
    
    # Detailed Metrics
    pass_rate: float = Field(..., description="Overall pass rate")
    flakiness_index: float = Field(..., description="Test flakiness index")
    mean_time_to_recovery: Optional[float] = Field(None, description="MTTR in hours")
    
    # Trend Information
    improvement_trend: TrendDirection = Field(..., description="Quality improvement trend")
    score_change: Optional[float] = Field(None, description="Score change from previous period")
    
    # Insights
    quality_insights: List[str] = Field(default_factory=list, description="Quality insights")
    improvement_recommendations: List[str] = Field(default_factory=list, description="Improvement recommendations")
    risk_factors: List[str] = Field(default_factory=list, description="Risk factors")
    
    # Metadata
    confidence_level: float = Field(..., description="Analysis confidence level")
    generated_at: datetime = Field(..., description="Metrics generation timestamp")
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
        },
        json_schema_extra={
            "example": {
                "metrics_id": "quality_12345",
                "scope": "project",
                "evaluation_period": "month",
                "overall_quality_score": "good",
                "reliability_score": 88.5,
                "performance_score": 92.1,
                "maintainability_score": 85.3,
                "pass_rate": 0.885,
                "flakiness_index": 0.042,
                "improvement_trend": "improving",
                "score_change": 3.2,
                "quality_insights": [
                    "Pass rate has improved by 3.2% compared to last month",
                    "Flakiness index is within acceptable bounds"
                ],
                "confidence_level": 0.95,
                "generated_at": "2024-01-08T10:30:00Z"
            }
        }
    )


class DrilldownResponse(BaseModel):
    """Response schema for drill-down functionality"""
    drilldown_id: str = Field(..., description="Unique drill-down identifier")
    parent_report_id: str = Field(..., description="Parent report ID")
    target_level: AggregationLevel = Field(..., description="Target aggregation level")
    target_id: str = Field(..., description="Target entity ID")
    
    # Drill-down Data
    execution_data: List[Dict[str, Any]] = Field(..., description="Detailed execution data")
    summary_metrics: Dict[str, Any] = Field(..., description="Summary metrics for drill-down")
    
    # Navigation
    navigation: DrilldownNavigation = Field(..., description="Navigation context")
    available_actions: List[str] = Field(default_factory=list, description="Available user actions")
    
    # Metadata
    generated_at: datetime = Field(..., description="Drill-down generation timestamp")
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
        },
        json_schema_extra={
            "example": {
                "drilldown_id": "drilldown_12345",
                "parent_report_id": "report_12345",
                "target_level": "test_case",
                "target_id": "suite_regression_001",
                "execution_data": [
                    {
                        "execution_id": "exec_001",
                        "test_case_name": "Login Test",
                        "status": "passed",
                        "duration_ms": 2500
                    }
                ],
                "summary_metrics": {
                    "total_test_cases": 45,
                    "passed": 42,
                    "failed": 3,
                    "pass_rate": 0.933
                },
                "navigation": {
                    "current_level": "test_case",
                    "available_levels": [],
                    "breadcrumb": [
                        {"level": "project", "name": "MyProject", "id": "project_1"},
                        {"level": "test_suite", "name": "Regression Suite", "id": "suite_1"}
                    ]
                },
                "available_actions": ["export", "schedule_report"],
                "generated_at": "2024-01-08T10:30:00Z"
            }
        }
    )


class ReportListResponse(BaseModel):
    """Response schema for listing reports"""
    reports: List[Dict[str, Any]] = Field(..., description="List of available reports")
    total_count: int = Field(..., description="Total number of reports")
    page: int = Field(1, ge=1, description="Current page number")
    page_size: int = Field(20, ge=1, le=100, description="Number of items per page")
    has_next: bool = Field(False, description="Whether there are more pages")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "reports": [
                    {
                        "report_id": "report_12345",
                        "name": "Weekly Summary",
                        "type": "summary",
                        "generated_at": "2024-01-08T10:30:00Z",
                        "generated_by": "user_123"
                    }
                ],
                "total_count": 125,
                "page": 1,
                "page_size": 20,
                "has_next": True
            }
        }
    ) 
"""
Execution Reporting Module - Services Package

This package contains all service layer implementations for the execution reporting module.
Services handle business logic, data aggregation, and integration with other system components.
"""

from .report_service import ReportService, ReportServiceFactory
from .trend_analysis_service import TrendAnalysisService, TrendAnalysisServiceFactory
from .quality_metrics_service import QualityMetricsService, QualityMetricsServiceFactory
from .dashboard_orchestration_service import DashboardOrchestrationService, DashboardOrchestrationServiceFactory
from .alert_management_service import AlertManagementService, AlertManagementServiceFactory
from .export_service import ExportService, ExportServiceFactory
from .cache_management_service import CacheManagementService, CacheManagementServiceFactory
from .data_aggregation_service import DataAggregationService, DataAggregationServiceFactory

__all__ = [
    # Report Generation
    "ReportService",
    "ReportServiceFactory",
    
    # Trend Analysis
    "TrendAnalysisService", 
    "TrendAnalysisServiceFactory",
    
    # Quality Metrics
    "QualityMetricsService",
    "QualityMetricsServiceFactory",
    
    # Dashboard Orchestration
    "DashboardOrchestrationService",
    "DashboardOrchestrationServiceFactory",
    
    # Alert Management
    "AlertManagementService",
    "AlertManagementServiceFactory",
    
    # Export Service
    "ExportService",
    "ExportServiceFactory",
    
    # Cache Management
    "CacheManagementService",
    "CacheManagementServiceFactory",
    
    # Data Aggregation
    "DataAggregationService",
    "DataAggregationServiceFactory"
] 
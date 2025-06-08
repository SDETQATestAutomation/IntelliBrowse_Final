"""
Execution Reporting Module - Dashboard Schemas

Basic dashboard schemas for completing the foundation layer.
Full implementation will be expanded in Phase 3.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict

from ..models.execution_report_model import AggregationLevel


class DashboardCreateRequest(BaseModel):
    """Request schema for creating dashboards"""
    name: str = Field(..., description="Dashboard name")
    description: Optional[str] = Field(None, description="Dashboard description")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Project Overview Dashboard",
                "description": "Main project metrics and trends"
            }
        }
    )


class DashboardUpdateRequest(BaseModel):
    """Request schema for updating dashboards"""
    name: Optional[str] = Field(None, description="Dashboard name")
    description: Optional[str] = Field(None, description="Dashboard description")


class WidgetCreateRequest(BaseModel):
    """Request schema for creating widgets"""
    widget_type: str = Field(..., description="Widget type")
    title: str = Field(..., description="Widget title")
    configuration: Dict[str, Any] = Field(default_factory=dict, description="Widget configuration")


class WidgetUpdateRequest(BaseModel):
    """Request schema for updating widgets"""
    title: Optional[str] = Field(None, description="Widget title")
    configuration: Optional[Dict[str, Any]] = Field(None, description="Widget configuration")


class DashboardResponse(BaseModel):
    """Response schema for dashboard data"""
    dashboard_id: str = Field(..., description="Dashboard ID")
    name: str = Field(..., description="Dashboard name")
    widgets: List[Dict[str, Any]] = Field(default_factory=list, description="Dashboard widgets")


class DashboardListResponse(BaseModel):
    """Response schema for dashboard list"""
    dashboards: List[Dict[str, Any]] = Field(..., description="List of dashboards")
    total_count: int = Field(..., description="Total number of dashboards")


class WidgetResponse(BaseModel):
    """Response schema for widget data"""
    widget_id: str = Field(..., description="Widget ID")
    widget_type: str = Field(..., description="Widget type")
    title: str = Field(..., description="Widget title")
    data: Dict[str, Any] = Field(default_factory=dict, description="Widget data")


class DashboardLayoutResponse(BaseModel):
    """Response schema for dashboard layout"""
    layout: Dict[str, Any] = Field(..., description="Dashboard layout configuration")


class DashboardPreferences(BaseModel):
    """Dashboard preferences configuration"""
    theme: str = Field("default", description="Dashboard theme")
    auto_refresh: bool = Field(True, description="Auto-refresh enabled")
    refresh_interval: int = Field(300, description="Refresh interval in seconds")


class WidgetConfiguration(BaseModel):
    """Widget configuration schema"""
    data_source: str = Field(..., description="Data source")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Widget filters")


class LayoutConfiguration(BaseModel):
    """Layout configuration schema"""
    grid: Dict[str, Any] = Field(default_factory=dict, description="Grid configuration")
    widgets: List[Dict[str, Any]] = Field(default_factory=list, description="Widget positions") 
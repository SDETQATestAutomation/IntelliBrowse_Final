"""
Execution Reporting Module - Export Schemas

Basic export schemas for completing the foundation layer.
Full implementation will be expanded in Phase 4.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict

from ..models.execution_report_model import ExportFormat, ExportStatus


class ExportJobRequest(BaseModel):
    """Request schema for creating export jobs"""
    name: str = Field(..., description="Export job name")
    export_format: ExportFormat = Field(..., description="Export format")
    data_source: str = Field(..., description="Data source identifier")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Export filters")
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "name": "Monthly Report Export",
                "export_format": "csv",
                "data_source": "execution_reports",
                "filters": {
                    "time_range": {
                        "start_date": "2024-01-01T00:00:00Z",
                        "end_date": "2024-01-31T23:59:59Z"
                    }
                }
            }
        }
    )


class ExportConfigurationRequest(BaseModel):
    """Request schema for export configuration"""
    columns: Optional[List[str]] = Field(None, description="Columns to include in export")
    max_records: Optional[int] = Field(None, description="Maximum records to export")
    priority: int = Field(1, ge=1, le=5, description="Job priority")


class ExportJobResponse(BaseModel):
    """Response schema for export jobs"""
    job_id: str = Field(..., description="Export job ID")
    name: str = Field(..., description="Job name")
    status: ExportStatus = Field(..., description="Job status")
    progress_percentage: float = Field(..., description="Job progress")
    download_url: Optional[str] = Field(None, description="Download URL when completed")
    created_at: datetime = Field(..., description="Job creation time")
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
        }
    )


class ExportJobListResponse(BaseModel):
    """Response schema for export job list"""
    jobs: List[ExportJobResponse] = Field(default_factory=list, description="Export jobs")
    total_count: int = Field(..., description="Total job count")
    page: int = Field(1, description="Current page")
    page_size: int = Field(20, description="Page size")


class ExportStatusResponse(BaseModel):
    """Response schema for export status"""
    job_id: str = Field(..., description="Job ID")
    status: ExportStatus = Field(..., description="Current status")
    progress_percentage: float = Field(..., description="Progress percentage")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")
    error_message: Optional[str] = Field(None, description="Error message if failed")


class ExportFormatConfig(BaseModel):
    """Export format configuration"""
    format_type: ExportFormat = Field(..., description="Export format")
    options: Dict[str, Any] = Field(default_factory=dict, description="Format-specific options")


class ExportFilterConfig(BaseModel):
    """Export filter configuration"""
    time_range: Dict[str, datetime] = Field(..., description="Time range filter")
    include_filters: Dict[str, List[str]] = Field(default_factory=dict, description="Include filters")
    exclude_filters: Dict[str, List[str]] = Field(default_factory=dict, description="Exclude filters") 
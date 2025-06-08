"""
Execution Reporting Module - Alert Schemas

Basic alert schemas for completing the foundation layer.
Full implementation will be expanded in Phase 4.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict

from ..models.execution_report_model import AlertSeverity, AlertStatus


class AlertRuleCreateRequest(BaseModel):
    """Request schema for creating alert rules"""
    name: str = Field(..., description="Alert rule name")
    metric_name: str = Field(..., description="Target metric")
    condition: str = Field(..., description="Alert condition")
    threshold_value: float = Field(..., description="Threshold value")
    severity: AlertSeverity = Field(..., description="Alert severity")
    
    model_config = ConfigDict(use_enum_values=True)


class AlertRuleUpdateRequest(BaseModel):
    """Request schema for updating alert rules"""
    name: Optional[str] = Field(None, description="Alert rule name")
    threshold_value: Optional[float] = Field(None, description="Threshold value")
    enabled: Optional[bool] = Field(None, description="Rule enabled status")


class AlertConfigurationRequest(BaseModel):
    """Request schema for alert configuration"""
    rules: List[Dict[str, Any]] = Field(default_factory=list, description="Alert rules")
    global_enabled: bool = Field(True, description="Global alerting enabled")


class AlertRuleResponse(BaseModel):
    """Response schema for alert rules"""
    rule_id: str = Field(..., description="Rule ID")
    name: str = Field(..., description="Rule name")
    metric_name: str = Field(..., description="Target metric")
    threshold_value: float = Field(..., description="Threshold value")
    severity: AlertSeverity = Field(..., description="Alert severity")
    enabled: bool = Field(..., description="Rule enabled status")


class AlertConfigurationResponse(BaseModel):
    """Response schema for alert configuration"""
    config_id: str = Field(..., description="Configuration ID")
    rules: List[AlertRuleResponse] = Field(default_factory=list, description="Alert rules")
    global_enabled: bool = Field(..., description="Global alerting enabled")


class AlertInstanceResponse(BaseModel):
    """Response schema for alert instances"""
    alert_id: str = Field(..., description="Alert instance ID")
    rule_id: str = Field(..., description="Source rule ID")
    status: AlertStatus = Field(..., description="Alert status")
    triggered_at: datetime = Field(..., description="Alert trigger time")
    message: str = Field(..., description="Alert message")


class AlertListResponse(BaseModel):
    """Response schema for alert list"""
    alerts: List[AlertInstanceResponse] = Field(default_factory=list, description="Alert instances")
    total_count: int = Field(..., description="Total alert count")


class AlertThresholdConfig(BaseModel):
    """Alert threshold configuration"""
    metric_name: str = Field(..., description="Metric name")
    warning_threshold: float = Field(..., description="Warning threshold")
    critical_threshold: float = Field(..., description="Critical threshold")


class NotificationChannelConfig(BaseModel):
    """Notification channel configuration"""
    channel_id: str = Field(..., description="Channel ID")
    channel_type: str = Field(..., description="Channel type (email, slack, etc.)")
    configuration: Dict[str, Any] = Field(default_factory=dict, description="Channel configuration")


class EscalationRuleConfig(BaseModel):
    """Escalation rule configuration"""
    rule_id: str = Field(..., description="Escalation rule ID")
    conditions: Dict[str, Any] = Field(default_factory=dict, description="Escalation conditions")
    actions: List[str] = Field(default_factory=list, description="Escalation actions") 
"""
Notification Module - Delivery History Schemas

Pydantic schemas for notification delivery history and audit trail API endpoints
with comprehensive validation and OpenAPI documentation examples.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator

from ..models import (
    NotificationChannel, NotificationTypeCategory, DeliveryStatus
)


class NotificationHistoryQuerySchema(BaseModel):
    """Schema for querying notification delivery history."""
    user_id: Optional[str] = Field(
        None,
        description="Filter by user ID",
        examples=["user_123", "admin_456"]
    )
    notification_type: Optional[NotificationTypeCategory] = Field(
        None,
        description="Filter by notification type",
        examples=["test_execution", "system_alert"]
    )
    channel: Optional[NotificationChannel] = Field(
        None,
        description="Filter by delivery channel",
        examples=["email", "websocket", "webhook"]
    )
    status: Optional[DeliveryStatus] = Field(
        None,
        description="Filter by delivery status",
        examples=["delivered", "failed", "pending"]
    )
    start_date: Optional[datetime] = Field(
        None,
        description="Filter from start date (ISO format)",
        examples=["2025-01-01T00:00:00Z"]
    )
    end_date: Optional[datetime] = Field(
        None,
        description="Filter to end date (ISO format)",
        examples=["2025-01-07T23:59:59Z"]
    )
    page: int = Field(
        default=1,
        ge=1,
        description="Page number for pagination",
        examples=[1, 2, 3]
    )
    page_size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of items per page",
        examples=[10, 20, 50]
    )
    include_attempts: bool = Field(
        default=False,
        description="Include detailed delivery attempts in response"
    )
    include_metrics: bool = Field(
        default=False,
        description="Include aggregated metrics in response"
    )
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "user_id": "user_123",
                "notification_type": "test_execution",
                "channel": "email",
                "status": "delivered",
                "start_date": "2025-01-01T00:00:00Z",
                "end_date": "2025-01-07T23:59:59Z",
                "page": 1,
                "page_size": 20,
                "include_attempts": True,
                "include_metrics": False
            }
        }
    )
    
    @field_validator('end_date')
    @classmethod
    def validate_date_range(cls, v, values):
        """Validate end date is after start date."""
        if v is not None and 'start_date' in values and values['start_date'] is not None:
            if v <= values['start_date']:
                raise ValueError("End date must be after start date")
        return v


class DeliveryAttemptResponseSchema(BaseModel):
    """Schema for delivery attempt response."""
    attempt_number: int = Field(..., description="Attempt sequence number")
    channel: NotificationChannel = Field(..., description="Delivery channel used")
    status: DeliveryStatus = Field(..., description="Delivery attempt status")
    
    # Timing
    started_at: str = Field(..., description="Attempt start time")
    completed_at: Optional[str] = Field(None, description="Attempt completion time")
    duration_ms: Optional[int] = Field(None, description="Delivery duration in milliseconds")
    
    # Provider details
    provider: Optional[str] = Field(None, description="Service provider used")
    provider_message_id: Optional[str] = Field(None, description="Provider message ID")
    
    # Error details
    error_code: Optional[str] = Field(None, description="Error code if failed")
    error_message: Optional[str] = Field(None, description="Error description")
    retry_after_seconds: Optional[int] = Field(None, description="Suggested retry delay")
    
    # Context
    recipient_email: Optional[str] = Field(None, description="Email address used")
    webhook_url: Optional[str] = Field(None, description="Webhook URL used")
    websocket_session_id: Optional[str] = Field(None, description="WebSocket session ID")
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "attempt_number": 1,
                "channel": "email",
                "status": "delivered",
                "started_at": "2025-01-07T10:30:15Z",
                "completed_at": "2025-01-07T10:30:18Z",
                "duration_ms": 3200,
                "provider": "SendGrid",
                "provider_message_id": "sg_msg_123456",
                "error_code": None,
                "error_message": None,
                "retry_after_seconds": None,
                "recipient_email": "user@company.com",
                "webhook_url": None,
                "websocket_session_id": None
            }
        }
    )


class DeliveryMetricsResponseSchema(BaseModel):
    """Schema for delivery metrics response."""
    total_attempts: int = Field(..., description="Total delivery attempts")
    successful_deliveries: int = Field(..., description="Successful deliveries")
    failed_attempts: int = Field(..., description="Failed attempts")
    
    # Performance metrics
    average_delivery_time_ms: Optional[float] = Field(None, description="Average delivery time")
    max_delivery_time_ms: Optional[int] = Field(None, description="Maximum delivery time")
    min_delivery_time_ms: Optional[int] = Field(None, description="Minimum delivery time")
    
    # Success rates
    success_rate: float = Field(..., description="Overall success rate percentage")
    channel_success_rates: Dict[str, float] = Field(
        default_factory=dict,
        description="Success rate by channel"
    )
    
    # Common errors
    common_errors: List[str] = Field(
        default_factory=list,
        description="Most common error messages"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_attempts": 150,
                "successful_deliveries": 142,
                "failed_attempts": 8,
                "average_delivery_time_ms": 2500.5,
                "max_delivery_time_ms": 8500,
                "min_delivery_time_ms": 120,
                "success_rate": 94.67,
                "channel_success_rates": {
                    "email": 96.5,
                    "websocket": 92.3,
                    "webhook": 89.1
                },
                "common_errors": [
                    "SMTP connection timeout",
                    "WebSocket connection closed",
                    "Webhook endpoint unreachable"
                ]
            }
        }
    )


class DeliveryHistoryResponseSchema(BaseModel):
    """Schema for individual delivery history response."""
    notification_id: str = Field(..., description="Notification ID")
    user_id: str = Field(..., description="Target user ID")
    notification_type: str = Field(..., description="Notification type")
    priority: str = Field(..., description="Notification priority")
    
    # Status and timing
    current_status: DeliveryStatus = Field(..., description="Current delivery status")
    first_attempt_at: Optional[str] = Field(None, description="First attempt timestamp")
    last_attempt_at: Optional[str] = Field(None, description="Last attempt timestamp")
    final_delivery_at: Optional[str] = Field(None, description="Final delivery timestamp")
    total_delivery_time_ms: Optional[int] = Field(None, description="Total delivery time")
    
    # Channels
    channels_attempted: List[NotificationChannel] = Field(
        default_factory=list,
        description="Channels attempted"
    )
    successful_channels: List[NotificationChannel] = Field(
        default_factory=list,
        description="Successfully delivered channels"
    )
    
    # Delivery attempts (optional detailed view)
    delivery_attempts: Optional[List[DeliveryAttemptResponseSchema]] = Field(
        None,
        description="Detailed delivery attempts (if requested)"
    )
    
    # Metrics (optional)
    metrics: Optional[DeliveryMetricsResponseSchema] = Field(
        None,
        description="Aggregated metrics (if requested)"
    )
    
    # Context
    source_service: str = Field(..., description="Source service")
    escalated: bool = Field(..., description="Whether delivery was escalated")
    manual_intervention: bool = Field(..., description="Whether manual intervention was required")
    notes: Optional[str] = Field(None, description="Additional notes")
    
    # Audit trail
    created_at: str = Field(..., description="Record creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "notification_id": "ntfy_abc123def456",
                "user_id": "user_123",
                "notification_type": "test_execution",
                "priority": "medium",
                "current_status": "delivered",
                "first_attempt_at": "2025-01-07T10:30:15Z",
                "last_attempt_at": "2025-01-07T10:30:15Z",
                "final_delivery_at": "2025-01-07T10:30:18Z",
                "total_delivery_time_ms": 3200,
                "channels_attempted": ["email"],
                "successful_channels": ["email"],
                "delivery_attempts": [
                    {
                        "attempt_number": 1,
                        "channel": "email",
                        "status": "delivered",
                        "started_at": "2025-01-07T10:30:15Z",
                        "completed_at": "2025-01-07T10:30:18Z",
                        "duration_ms": 3200,
                        "provider": "SendGrid"
                    }
                ],
                "source_service": "test_execution_engine",
                "escalated": False,
                "manual_intervention": False,
                "notes": None,
                "created_at": "2025-01-07T10:30:00Z",
                "updated_at": "2025-01-07T10:30:20Z"
            }
        }
    )


class DeliveryHistoryListResponseSchema(BaseModel):
    """Schema for delivery history list response with pagination."""
    deliveries: List[DeliveryHistoryResponseSchema] = Field(
        default_factory=list,
        description="List of delivery history records"
    )
    total_count: int = Field(..., description="Total number of records")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there are more pages")
    has_previous: bool = Field(..., description="Whether there are previous pages")
    
    # Optional aggregated metrics for the filtered results
    summary_metrics: Optional[DeliveryMetricsResponseSchema] = Field(
        None,
        description="Summary metrics for filtered results"
    )
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "deliveries": [
                    {
                        "notification_id": "ntfy_abc123",
                        "user_id": "user_123",
                        "notification_type": "test_execution",
                        "priority": "medium",
                        "current_status": "delivered",
                        "channels_attempted": ["email"],
                        "successful_channels": ["email"],
                        "source_service": "test_execution_engine",
                        "escalated": False,
                        "manual_intervention": False,
                        "created_at": "2025-01-07T10:30:00Z"
                    }
                ],
                "total_count": 85,
                "page": 1,
                "page_size": 20,
                "total_pages": 5,
                "has_next": True,
                "has_previous": False,
                "summary_metrics": {
                    "total_attempts": 85,
                    "successful_deliveries": 80,
                    "failed_attempts": 5,
                    "success_rate": 94.12
                }
            }
        }
    )


class DeliveryAuditResponseSchema(BaseModel):
    """Schema for delivery audit trail response."""
    notification_id: str = Field(..., description="Notification ID")
    audit_trail: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Chronological audit trail events"
    )
    performance_summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Performance analysis summary"
    )
    error_analysis: Dict[str, Any] = Field(
        default_factory=dict,
        description="Error pattern analysis"
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Improvement recommendations"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "notification_id": "ntfy_abc123def456",
                "audit_trail": [
                    {
                        "timestamp": "2025-01-07T10:30:00Z",
                        "event": "notification_created",
                        "details": {
                            "type": "test_execution",
                            "priority": "medium",
                            "channels": ["email", "websocket"]
                        }
                    },
                    {
                        "timestamp": "2025-01-07T10:30:15Z",
                        "event": "delivery_attempt_started",
                        "details": {
                            "channel": "email",
                            "attempt": 1,
                            "provider": "SendGrid"
                        }
                    },
                    {
                        "timestamp": "2025-01-07T10:30:18Z",
                        "event": "delivery_successful",
                        "details": {
                            "channel": "email",
                            "duration_ms": 3200,
                            "provider_message_id": "sg_msg_123456"
                        }
                    }
                ],
                "performance_summary": {
                    "total_delivery_time_ms": 3200,
                    "channel_performance": {
                        "email": {"attempts": 1, "success": True, "duration_ms": 3200}
                    },
                    "efficiency_score": 95.5
                },
                "error_analysis": {
                    "error_count": 0,
                    "error_categories": [],
                    "retry_patterns": []
                },
                "recommendations": [
                    "Consider enabling WebSocket fallback for faster delivery",
                    "Performance is within acceptable thresholds"
                ]
            }
        }
    )


class NotificationHistoryStatsSchema(BaseModel):
    """Schema for notification history statistics."""
    period_start: str = Field(..., description="Statistics period start")
    period_end: str = Field(..., description="Statistics period end")
    
    # Overall statistics
    total_notifications: int = Field(..., description="Total notifications in period")
    total_recipients: int = Field(..., description="Total unique recipients")
    
    # Status breakdown
    status_breakdown: Dict[str, int] = Field(
        default_factory=dict,
        description="Count by delivery status"
    )
    
    # Channel statistics
    channel_statistics: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Statistics by channel"
    )
    
    # Type statistics
    type_statistics: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Statistics by notification type"
    )
    
    # Performance metrics
    average_delivery_time_ms: float = Field(..., description="Average delivery time")
    p50_delivery_time_ms: float = Field(..., description="50th percentile delivery time")
    p95_delivery_time_ms: float = Field(..., description="95th percentile delivery time")
    p99_delivery_time_ms: float = Field(..., description="99th percentile delivery time")
    
    # Reliability metrics
    overall_success_rate: float = Field(..., description="Overall success rate")
    escalation_rate: float = Field(..., description="Rate of escalated notifications")
    manual_intervention_rate: float = Field(..., description="Rate of manual interventions")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "period_start": "2025-01-01T00:00:00Z",
                "period_end": "2025-01-07T23:59:59Z",
                "total_notifications": 1250,
                "total_recipients": 85,
                "status_breakdown": {
                    "delivered": 1187,
                    "failed": 43,
                    "pending": 20
                },
                "channel_statistics": {
                    "email": {
                        "total_sent": 800,
                        "successful": 775,
                        "success_rate": 96.88,
                        "avg_delivery_time_ms": 2500
                    },
                    "websocket": {
                        "total_sent": 450,
                        "successful": 412,
                        "success_rate": 91.56,
                        "avg_delivery_time_ms": 150
                    }
                },
                "type_statistics": {
                    "test_execution": {
                        "count": 600,
                        "success_rate": 95.5,
                        "avg_delivery_time_ms": 1800
                    },
                    "system_alert": {
                        "count": 250,
                        "success_rate": 98.8,
                        "avg_delivery_time_ms": 500
                    }
                },
                "average_delivery_time_ms": 1850.5,
                "p50_delivery_time_ms": 1200.0,
                "p95_delivery_time_ms": 5200.0,
                "p99_delivery_time_ms": 8500.0,
                "overall_success_rate": 94.96,
                "escalation_rate": 2.4,
                "manual_intervention_rate": 0.8
            }
        }
    ) 
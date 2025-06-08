"""
Notification Module - Core Notification Schemas

Pydantic schemas for notification API endpoints with comprehensive validation
and OpenAPI documentation examples following IntelliBrowse patterns.
"""

from datetime import datetime, time
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator

from ..models import (
    NotificationChannel, NotificationPriority, NotificationTypeCategory, 
    NotificationStatus
)


class NotificationContentSchema(BaseModel):
    """Schema for notification content with channel-specific formatting."""
    subject: str = Field(
        ..., 
        min_length=1, 
        max_length=200,
        description="Notification subject/title",
        examples=["Test execution completed", "Quality metrics alert"]
    )
    body: str = Field(
        ..., 
        min_length=1, 
        max_length=2000,
        description="Notification body content",
        examples=["Your test suite 'User Authentication Tests' has completed with 95% success rate."]
    )
    template_id: Optional[str] = Field(
        None,
        description="Template ID for dynamic content",
        examples=["test_completion_template", "alert_template"]
    )
    template_variables: Dict[str, Any] = Field(
        default_factory=dict,
        description="Template variable values",
        examples=[{
            "suite_name": "User Authentication Tests",
            "success_rate": 95,
            "total_tests": 20,
            "failed_tests": 1
        }]
    )
    channel_specific: Dict[str, Any] = Field(
        default_factory=dict,
        description="Channel-specific content overrides",
        examples=[{
            "email": {"html_body": "<h1>Test Results</h1><p>Success rate: 95%</p>"},
            "websocket": {"action": "notification", "type": "test_result"}
        }]
    )
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "subject": "Test Suite Completion Alert",
                "body": "Your test suite 'API Integration Tests' has completed successfully with 18/20 tests passing.",
                "template_id": "test_completion_template",
                "template_variables": {
                    "suite_name": "API Integration Tests",
                    "success_rate": 90,
                    "total_tests": 20,
                    "passed_tests": 18
                },
                "channel_specific": {
                    "email": {
                        "html_body": "<h2>Test Results Summary</h2><p>Suite: API Integration Tests</p><p>Status: <strong>Completed</strong></p>"
                    }
                }
            }
        }
    )


class NotificationRecipientSchema(BaseModel):
    """Schema for notification recipient specification."""
    user_id: str = Field(
        ...,
        description="Target user ID",
        examples=["user_123", "admin_456"]
    )
    email: Optional[str] = Field(
        None,
        description="User email address (optional override)",
        examples=["user@company.com", "admin@company.com"]
    )
    preferred_channels: List[NotificationChannel] = Field(
        default_factory=list,
        description="User's preferred delivery channels",
        examples=[["email", "websocket"], ["email"], ["webhook"]]
    )
    role_based: bool = Field(
        default=False,
        description="Whether this is role-based targeting"
    )
    roles: List[str] = Field(
        default_factory=list,
        description="User roles if role-based",
        examples=[["admin", "tester"], ["quality_manager"]]
    )
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "user_id": "user_123",
                "email": "john.doe@company.com",
                "preferred_channels": ["email", "websocket"],
                "role_based": False,
                "roles": []
            }
        }
    )


class SendNotificationRequestSchema(BaseModel):
    """Schema for sending notification requests."""
    type: NotificationTypeCategory = Field(
        ...,
        description="Notification type category",
        examples=["test_execution", "system_alert", "quality_metrics"]
    )
    title: str = Field(
        ..., 
        min_length=1, 
        max_length=200,
        description="Notification title",
        examples=["Test Suite Completed", "Quality Threshold Exceeded"]
    )
    content: NotificationContentSchema = Field(
        ...,
        description="Notification content with formatting"
    )
    recipients: List[NotificationRecipientSchema] = Field(
        ..., 
        min_length=1, 
        max_length=100,
        description="Target recipients"
    )
    channels: List[NotificationChannel] = Field(
        ...,
        min_length=1,
        description="Delivery channels to use",
        examples=[["email"], ["email", "websocket"], ["webhook"]]
    )
    priority: NotificationPriority = Field(
        default=NotificationPriority.MEDIUM,
        description="Processing priority level"
    )
    scheduled_at: Optional[datetime] = Field(
        None,
        description="Scheduled delivery time (None for immediate)"
    )
    expires_at: Optional[datetime] = Field(
        None,
        description="Notification expiration time"
    )
    correlation_id: Optional[str] = Field(
        None,
        description="Correlation ID for tracking",
        examples=["test_run_789", "alert_456"]
    )
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context data",
        examples=[{
            "test_run_id": "run_123",
            "environment": "staging",
            "triggered_by": "scheduler"
        }]
    )
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "type": "test_execution",
                "title": "API Test Suite Completed",
                "content": {
                    "subject": "Test Suite Results Available",
                    "body": "Your API test suite has completed with 95% success rate. 19 out of 20 tests passed successfully.",
                    "template_id": "test_completion_template",
                    "template_variables": {
                        "suite_name": "API Integration Tests",
                        "success_rate": 95,
                        "passed_tests": 19,
                        "total_tests": 20
                    }
                },
                "recipients": [
                    {
                        "user_id": "developer_123",
                        "email": "dev@company.com",
                        "preferred_channels": ["email", "websocket"]
                    }
                ],
                "channels": ["email", "websocket"],
                "priority": "medium",
                "correlation_id": "test_run_456",
                "context": {
                    "test_run_id": "run_456",
                    "environment": "staging"
                }
            }
        }
    )


class NotificationResponseSchema(BaseModel):
    """Schema for notification creation response."""
    notification_id: str = Field(
        ...,
        description="Unique notification identifier",
        examples=["ntfy_abc123def456"]
    )
    status: NotificationStatus = Field(
        ...,
        description="Current notification status"
    )
    created_at: datetime = Field(
        ...,
        description="Creation timestamp"
    )
    scheduled_at: Optional[datetime] = Field(
        None,
        description="Scheduled delivery time"
    )
    channels: List[NotificationChannel] = Field(
        ...,
        description="Configured delivery channels"
    )
    recipient_count: int = Field(
        ...,
        description="Number of recipients"
    )
    estimated_delivery_time: Optional[str] = Field(
        None,
        description="Estimated delivery time",
        examples=["immediate", "within 5 minutes", "scheduled"]
    )
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "notification_id": "ntfy_abc123def456",
                "status": "pending",
                "created_at": "2025-01-07T10:30:00Z",
                "scheduled_at": None,
                "channels": ["email", "websocket"],
                "recipient_count": 1,
                "estimated_delivery_time": "immediate"
            }
        }
    )


class NotificationStatusResponseSchema(BaseModel):
    """Schema for notification status query response."""
    notification_id: str = Field(
        ...,
        description="Notification identifier"
    )
    status: NotificationStatus = Field(
        ...,
        description="Current notification status"
    )
    created_at: datetime = Field(
        ...,
        description="Creation timestamp"
    )
    sent_at: Optional[datetime] = Field(
        None,
        description="Send timestamp"
    )
    delivered_at: Optional[datetime] = Field(
        None,
        description="Delivery confirmation timestamp"
    )
    failed_at: Optional[datetime] = Field(
        None,
        description="Failure timestamp"
    )
    channels: List[NotificationChannel] = Field(
        ...,
        description="Configured delivery channels"
    )
    successful_channels: List[NotificationChannel] = Field(
        default_factory=list,
        description="Successfully delivered channels"
    )
    retry_count: int = Field(
        default=0,
        description="Number of retry attempts"
    )
    error_details: Optional[str] = Field(
        None,
        description="Error description if failed"
    )
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "notification_id": "ntfy_abc123def456",
                "status": "delivered",
                "created_at": "2025-01-07T10:30:00Z",
                "sent_at": "2025-01-07T10:30:15Z",
                "delivered_at": "2025-01-07T10:30:18Z",
                "failed_at": None,
                "channels": ["email", "websocket"],
                "successful_channels": ["email", "websocket"],
                "retry_count": 0,
                "error_details": None
            }
        }
    )


class NotificationListItemSchema(BaseModel):
    """Schema for notification list item."""
    notification_id: str = Field(..., description="Notification identifier")
    type: NotificationTypeCategory = Field(..., description="Notification type")
    title: str = Field(..., description="Notification title")
    status: NotificationStatus = Field(..., description="Current status")
    priority: NotificationPriority = Field(..., description="Priority level")
    created_at: datetime = Field(..., description="Creation timestamp")
    recipient_count: int = Field(..., description="Number of recipients")
    channels: List[NotificationChannel] = Field(..., description="Delivery channels")
    
    model_config = ConfigDict(use_enum_values=True)


class NotificationListResponseSchema(BaseModel):
    """Schema for notification list response with pagination."""
    notifications: List[NotificationListItemSchema] = Field(
        default_factory=list,
        description="List of notifications"
    )
    total_count: int = Field(
        ...,
        description="Total number of notifications"
    )
    page: int = Field(
        ...,
        description="Current page number"
    )
    page_size: int = Field(
        ...,
        description="Items per page"
    )
    total_pages: int = Field(
        ...,
        description="Total number of pages"
    )
    has_next: bool = Field(
        ...,
        description="Whether there are more pages"
    )
    has_previous: bool = Field(
        ...,
        description="Whether there are previous pages"
    )
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "notifications": [
                    {
                        "notification_id": "ntfy_abc123",
                        "type": "test_execution",
                        "title": "API Tests Completed",
                        "status": "delivered",
                        "priority": "medium",
                        "created_at": "2025-01-07T10:30:00Z",
                        "recipient_count": 2,
                        "channels": ["email", "websocket"]
                    }
                ],
                "total_count": 150,
                "page": 1,
                "page_size": 20,
                "total_pages": 8,
                "has_next": True,
                "has_previous": False
            }
        }
    )


class ChannelMetricsSchema(BaseModel):
    """Schema for channel-specific metrics."""
    channel: NotificationChannel = Field(..., description="Notification channel")
    total_sent: int = Field(..., description="Total notifications sent")
    successful: int = Field(..., description="Successfully delivered")
    failed: int = Field(..., description="Failed deliveries")
    success_rate: float = Field(..., description="Success rate percentage")
    average_delivery_time_ms: Optional[float] = Field(None, description="Average delivery time")
    
    model_config = ConfigDict(use_enum_values=True)


class NotificationMetricsResponseSchema(BaseModel):
    """Schema for notification system metrics response."""
    total_notifications: int = Field(..., description="Total notifications sent")
    successful_deliveries: int = Field(..., description="Successfully delivered notifications")
    failed_deliveries: int = Field(..., description="Failed delivery notifications")
    pending_notifications: int = Field(..., description="Pending notifications")
    overall_success_rate: float = Field(..., description="Overall success rate percentage")
    
    # Time period metrics
    period_start: datetime = Field(..., description="Metrics period start time")
    period_end: datetime = Field(..., description="Metrics period end time")
    
    # Channel breakdown
    channel_metrics: List[ChannelMetricsSchema] = Field(
        default_factory=list,
        description="Metrics by channel"
    )
    
    # Type breakdown
    type_metrics: Dict[str, int] = Field(
        default_factory=dict,
        description="Notification count by type"
    )
    
    # Performance metrics
    average_delivery_time_ms: Optional[float] = Field(None, description="Average delivery time")
    p95_delivery_time_ms: Optional[float] = Field(None, description="95th percentile delivery time")
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "total_notifications": 1250,
                "successful_deliveries": 1187,
                "failed_deliveries": 43,
                "pending_notifications": 20,
                "overall_success_rate": 94.96,
                "period_start": "2025-01-01T00:00:00Z",
                "period_end": "2025-01-07T23:59:59Z",
                "channel_metrics": [
                    {
                        "channel": "email",
                        "total_sent": 800,
                        "successful": 775,
                        "failed": 25,
                        "success_rate": 96.88,
                        "average_delivery_time_ms": 2500.0
                    },
                    {
                        "channel": "websocket",
                        "total_sent": 450,
                        "successful": 412,
                        "failed": 18,
                        "success_rate": 91.56,
                        "average_delivery_time_ms": 150.0
                    }
                ],
                "type_metrics": {
                    "test_execution": 600,
                    "system_alert": 250,
                    "quality_metrics": 400
                },
                "average_delivery_time_ms": 1800.0,
                "p95_delivery_time_ms": 5200.0
            }
        }
    ) 
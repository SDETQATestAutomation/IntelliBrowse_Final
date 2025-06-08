"""
Unit Tests for Notification Controller
Tests the HTTP orchestration layer of the notification engine.
Part of Phase 6 - Final Integration & Testing
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from fastapi import HTTPException

from src.backend.notification.controllers.notification_controller import NotificationController
from src.backend.notification.schemas.notification_schemas import (
    NotificationHistoryListResponse,
    NotificationHistoryDetailResponse
)
from src.backend.notification.schemas.preference_schemas import (
    UpdatePreferencesRequest,
    PreferenceSyncResponse
)
from src.backend.auth.schemas.user_schema import UserResponse


class TestNotificationController:
    """Test suite for NotificationController class."""
    
    @pytest.fixture
    def mock_services(self):
        """Create mock services for testing."""
        return {
            "notification_service": AsyncMock(),
            "history_service": AsyncMock(),
            "analytics_service": AsyncMock(),
            "preference_sync_service": AsyncMock()
        }
    
    @pytest.fixture
    def controller(self, mock_services):
        """Create NotificationController instance with mocked services."""
        return NotificationController(
            notification_service=mock_services["notification_service"],
            history_service=mock_services["history_service"],
            analytics_service=mock_services["analytics_service"],
            preference_sync_service=mock_services["preference_sync_service"]
        )
    
    @pytest.fixture
    def sample_user(self):
        """Create sample user for testing."""
        return UserResponse(
            id="user_123",
            username="testuser",
            email="test@example.com",
            is_active=True
        )
    
    @pytest.mark.asyncio
    async def test_get_user_notifications_success(self, controller, mock_services, sample_user):
        """Test successful retrieval of user notifications."""
        # Arrange
        mock_response = NotificationHistoryListResponse(
            notifications=[],
            total_count=0,
            page=1,
            page_size=20,
            total_pages=0
        )
        mock_services["history_service"].get_user_notifications.return_value = mock_response
        
        # Act
        result = await controller.get_user_notifications(
            user=sample_user,
            page=1,
            page_size=20
        )
        
        # Assert
        assert result.success is True
        assert result.data == mock_response
        mock_services["history_service"].get_user_notifications.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_user_notifications_validation_error(self, controller, sample_user):
        """Test validation error handling in get_user_notifications."""
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await controller.get_user_notifications(
                user=sample_user,
                page=0,  # Invalid page number
                page_size=20
            )
        
        assert exc_info.value.status_code == 400
        assert "Validation error" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_get_notification_by_id_success(self, controller, mock_services, sample_user):
        """Test successful retrieval of notification by ID."""
        # Arrange
        notification_id = "ntfy_abc123def456"
        mock_response = NotificationHistoryDetailResponse(
            notification_id=notification_id,
            user_id=sample_user.id,
            notification_type="test_execution_complete",
            title="Test Complete",
            content="Your test has completed successfully",
            channels=["email"],
            priority="medium",
            status="sent",
            created_at=datetime.now(timezone.utc),
            delivery_attempts=[],
            metadata={}
        )
        mock_services["history_service"].get_notification_by_id.return_value = mock_response
        
        # Act
        result = await controller.get_notification_by_id(
            user=sample_user,
            notification_id=notification_id
        )
        
        # Assert
        assert result.success is True
        assert result.data == mock_response
        mock_services["history_service"].get_notification_by_id.assert_called_once_with(
            user_id=sample_user.id,
            notification_id=notification_id
        )
    
    @pytest.mark.asyncio
    async def test_get_notification_by_id_invalid_format(self, controller, sample_user):
        """Test invalid notification ID format handling."""
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await controller.get_notification_by_id(
                user=sample_user,
                notification_id="invalid_id"
            )
        
        assert exc_info.value.status_code == 400
        assert "Invalid notification ID format" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_get_analytics_summary_success(self, controller, mock_services, sample_user):
        """Test successful analytics summary retrieval."""
        # Arrange
        mock_analytics = {
            "delivery_stats": {
                "total_sent": 100,
                "successful": 95,
                "failed": 5,
                "success_rate": 95.0
            },
            "channel_breakdown": {
                "email": 60,
                "slack": 30,
                "webhook": 10
            },
            "time_window": "7d"
        }
        mock_services["analytics_service"].get_analytics_summary.return_value = mock_analytics
        
        # Act
        result = await controller.get_analytics_summary(
            user=sample_user,
            time_window="7d"
        )
        
        # Assert
        assert result.success is True
        assert result.data == mock_analytics
        mock_services["analytics_service"].get_analytics_summary.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_user_preferences_success(self, controller, mock_services, sample_user):
        """Test successful user preferences update."""
        # Arrange
        preferences_request = UpdatePreferencesRequest(
            channel_preferences={
                "email": {
                    "enabled": True,
                    "priority": "high"
                }
            },
            global_settings={
                "timezone": "UTC",
                "language": "en"
            }
        )
        
        mock_sync_response = PreferenceSyncResponse(
            sync_id="sync_123",
            status="completed",
            sync_timestamp=datetime.now(timezone.utc),
            changes_applied=["email.enabled", "email.priority"]
        )
        mock_services["preference_sync_service"].sync_preferences.return_value = mock_sync_response
        
        # Act
        result = await controller.update_user_preferences(
            user=sample_user,
            preferences_request=preferences_request
        )
        
        # Assert
        assert result.success is True
        assert result.data == mock_sync_response
        mock_services["preference_sync_service"].sync_preferences.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_health_status_success(self, controller):
        """Test successful health status retrieval."""
        # Act
        result = await controller.get_health_status()
        
        # Assert
        assert "overall_status" in result
        assert "timestamp" in result
        assert "components" in result
        assert "metrics" in result
        assert result["overall_status"] in ["healthy", "degraded", "unhealthy", "error"]
    
    @pytest.mark.asyncio
    async def test_get_performance_metrics_success(self, controller):
        """Test successful performance metrics retrieval."""
        # Act
        result = await controller.get_performance_metrics()
        
        # Assert
        assert "delivery_metrics" in result
        assert "channel_performance" in result
        assert "system_metrics" in result
        assert "time_period" in result
        assert "generated_at" in result
    
    @pytest.mark.asyncio
    async def test_get_daemon_status_success(self, controller):
        """Test successful daemon status retrieval."""
        # Act
        result = await controller.get_daemon_status()
        
        # Assert
        assert "daemon_status" in result
        assert "uptime_seconds" in result
        assert "last_heartbeat" in result
        assert "processing_queue_size" in result
        assert "health_checks" in result
        assert "performance" in result
    
    @pytest.mark.asyncio
    async def test_restart_daemon_success(self, controller):
        """Test successful daemon restart."""
        # Act
        result = await controller.restart_daemon()
        
        # Assert
        assert "restart_initiated" in result
        assert "timestamp" in result
        assert "estimated_downtime_seconds" in result
        assert "restart_id" in result
        assert result["restart_initiated"] is True
    
    @pytest.mark.asyncio
    async def test_get_channel_status_success(self, controller):
        """Test successful channel status retrieval."""
        # Act
        result = await controller.get_channel_status()
        
        # Assert
        assert "channels" in result
        assert "total_channels" in result
        assert "healthy_channels" in result
        assert "degraded_channels" in result
        assert "unhealthy_channels" in result
    
    @pytest.mark.asyncio
    async def test_service_error_handling(self, controller, mock_services, sample_user):
        """Test error handling when service throws exception."""
        # Arrange
        mock_services["history_service"].get_user_notifications.side_effect = Exception("Service error")
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await controller.get_user_notifications(
                user=sample_user,
                page=1,
                page_size=20
            )
        
        assert exc_info.value.status_code == 500
        assert "Failed to retrieve notifications" in str(exc_info.value.detail)


class TestRequestValidator:
    """Test suite for RequestValidator utility class."""
    
    def test_validate_user_id_valid(self):
        """Test valid user ID validation."""
        from src.backend.notification.controllers.notification_controller import RequestValidator
        
        valid_id = "user_123"
        result = RequestValidator.validate_user_id(valid_id)
        assert result == valid_id
    
    def test_validate_user_id_invalid(self):
        """Test invalid user ID validation."""
        from src.backend.notification.controllers.notification_controller import RequestValidator
        
        with pytest.raises(ValueError):
            RequestValidator.validate_user_id("")
        
        with pytest.raises(ValueError):
            RequestValidator.validate_user_id("a" * 101)  # Too long
    
    def test_validate_notification_id_valid(self):
        """Test valid notification ID validation."""
        from src.backend.notification.controllers.notification_controller import RequestValidator
        
        valid_id = "ntfy_abc123def456"
        result = RequestValidator.validate_notification_id(valid_id)
        assert result == valid_id
    
    def test_validate_notification_id_invalid(self):
        """Test invalid notification ID validation."""
        from src.backend.notification.controllers.notification_controller import RequestValidator
        
        with pytest.raises(ValueError):
            RequestValidator.validate_notification_id("invalid_format")
        
        with pytest.raises(ValueError):
            RequestValidator.validate_notification_id("ntfy_")
    
    def test_validate_pagination_params_valid(self):
        """Test valid pagination parameters."""
        from src.backend.notification.controllers.notification_controller import RequestValidator
        
        page, page_size = RequestValidator.validate_pagination_params(1, 20)
        assert page == 1
        assert page_size == 20
    
    def test_validate_pagination_params_invalid(self):
        """Test invalid pagination parameters."""
        from src.backend.notification.controllers.notification_controller import RequestValidator
        
        with pytest.raises(ValueError):
            RequestValidator.validate_pagination_params(0, 20)  # Invalid page
        
        with pytest.raises(ValueError):
            RequestValidator.validate_pagination_params(1, 0)   # Invalid page_size
        
        with pytest.raises(ValueError):
            RequestValidator.validate_pagination_params(1, 101) # Page size too large


# Integration test fixtures and utilities
@pytest.fixture
def notification_test_data():
    """Sample notification data for testing."""
    return {
        "notification_id": "ntfy_abc123def456",
        "user_id": "user_123",
        "notification_type": "test_execution_complete",
        "title": "Test Execution Complete",
        "content": "Your test suite has completed successfully",
        "channels": ["email", "slack"],
        "priority": "medium",
        "status": "sent",
        "metadata": {
            "test_suite_id": "suite_789",
            "execution_time": "00:05:30"
        }
    }


@pytest.fixture
def preferences_test_data():
    """Sample preferences data for testing."""
    return {
        "channel_preferences": {
            "email": {
                "enabled": True,
                "priority": "high",
                "delivery_time_windows": [
                    {
                        "start_time": "09:00",
                        "end_time": "17:00",
                        "days_of_week": [1, 2, 3, 4, 5]
                    }
                ]
            },
            "slack": {
                "enabled": True,
                "priority": "medium"
            }
        },
        "global_settings": {
            "timezone": "UTC",
            "language": "en",
            "digest_frequency": "daily"
        },
        "notification_types": {
            "test_execution_complete": {
                "enabled": True,
                "channels": ["email", "slack"]
            },
            "system_alert": {
                "enabled": True,
                "channels": ["email"]
            }
        }
    } 
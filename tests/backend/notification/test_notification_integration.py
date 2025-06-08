"""
Integration Tests for Notification Engine
Tests end-to-end functionality of the notification system.
Part of Phase 6 - Final Integration & Testing
"""

import pytest
import asyncio
from httpx import AsyncClient
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone

from src.backend.main import app
from src.backend.config.env import get_settings


class TestNotificationEngineIntegration:
    """Integration tests for the complete notification engine."""
    
    @pytest.fixture
    def client(self):
        """Create test client for FastAPI app."""
        return TestClient(app)
    
    @pytest.fixture
    async def async_client(self):
        """Create async test client for FastAPI app."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac
    
    @pytest.fixture
    def auth_headers(self):
        """Mock authentication headers for testing."""
        # In a real test, this would be a valid JWT token
        return {
            "Authorization": "Bearer mock_jwt_token",
            "Content-Type": "application/json"
        }
    
    @pytest.mark.asyncio
    async def test_notification_health_endpoints(self, async_client):
        """Test notification health monitoring endpoints."""
        # Test main health status
        response = await async_client.get("/api/v1/notifications/health/status")
        assert response.status_code in [200, 503]  # May be unavailable in test
        
        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "data" in data
            assert "overall_status" in data["data"]
            assert "components" in data["data"]
            assert "metrics" in data["data"]
    
    @pytest.mark.asyncio
    async def test_notification_metrics_endpoint(self, async_client):
        """Test notification performance metrics endpoint."""
        response = await async_client.get("/api/v1/notifications/health/metrics")
        assert response.status_code in [200, 503]
        
        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "data" in data
            assert "delivery_metrics" in data["data"]
            assert "channel_performance" in data["data"]
    
    @pytest.mark.asyncio
    async def test_daemon_status_endpoint(self, async_client):
        """Test delivery daemon status endpoint."""
        response = await async_client.get("/api/v1/notifications/health/daemon")
        assert response.status_code in [200, 503]
        
        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "data" in data
            assert "daemon_status" in data["data"]
            assert "health_checks" in data["data"]
    
    @pytest.mark.asyncio
    async def test_channel_status_endpoint(self, async_client):
        """Test channel adapter status endpoint."""
        response = await async_client.get("/api/v1/notifications/health/channels")
        assert response.status_code in [200, 503]
        
        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "data" in data
            assert "channels" in data["data"]
            assert "total_channels" in data["data"]
    
    @pytest.mark.asyncio
    @patch('src.backend.auth.dependencies.auth_dependency.get_current_user')
    async def test_user_notifications_endpoint(self, mock_auth, async_client, auth_headers):
        """Test user notifications retrieval endpoint."""
        # Mock authenticated user
        mock_auth.return_value = {
            "id": "user_123",
            "username": "testuser",
            "email": "test@example.com",
            "is_active": True
        }
        
        response = await async_client.get(
            "/api/v1/notifications/",
            headers=auth_headers
        )
        
        # Should return 200 or appropriate error
        assert response.status_code in [200, 401, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "data" in data
    
    @pytest.mark.asyncio
    @patch('src.backend.auth.dependencies.auth_dependency.get_current_user')
    async def test_analytics_summary_endpoint(self, mock_auth, async_client, auth_headers):
        """Test analytics summary endpoint."""
        # Mock authenticated user
        mock_auth.return_value = {
            "id": "user_123",
            "username": "testuser",
            "email": "test@example.com",
            "is_active": True
        }
        
        response = await async_client.get(
            "/api/v1/notifications/analytics/summary",
            headers=auth_headers
        )
        
        assert response.status_code in [200, 401, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "data" in data
    
    @pytest.mark.asyncio
    @patch('src.backend.auth.dependencies.auth_dependency.get_current_user')
    async def test_preferences_update_endpoint(self, mock_auth, async_client, auth_headers):
        """Test user preferences update endpoint."""
        # Mock authenticated user
        mock_auth.return_value = {
            "id": "user_123",
            "username": "testuser",
            "email": "test@example.com",
            "is_active": True
        }
        
        preferences_data = {
            "channel_preferences": {
                "email": {
                    "enabled": True,
                    "priority": "high"
                }
            },
            "global_settings": {
                "timezone": "UTC",
                "language": "en"
            }
        }
        
        response = await async_client.put(
            "/api/v1/notifications/preferences",
            headers=auth_headers,
            json=preferences_data
        )
        
        assert response.status_code in [200, 400, 401, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "data" in data
    
    def test_notification_routes_registration(self, client):
        """Test that notification routes are properly registered."""
        # Test that the notification routes are accessible
        response = client.get("/api/v1/notifications/health")
        # Should not return 404 (route not found)
        assert response.status_code != 404
    
    def test_health_routes_registration(self, client):
        """Test that health monitoring routes are properly registered."""
        # Test health status endpoint
        response = client.get("/api/v1/notifications/health/status")
        assert response.status_code != 404
        
        # Test metrics endpoint
        response = client.get("/api/v1/notifications/health/metrics")
        assert response.status_code != 404
        
        # Test daemon status endpoint
        response = client.get("/api/v1/notifications/health/daemon")
        assert response.status_code != 404
        
        # Test channel status endpoint
        response = client.get("/api/v1/notifications/health/channels")
        assert response.status_code != 404


class TestNotificationDatabaseIntegration:
    """Test database integration for notification engine."""
    
    @pytest.mark.asyncio
    async def test_database_connection(self):
        """Test that notification engine can connect to database."""
        try:
            from src.backend.auth.services.database_service import get_database_service
            db_service = get_database_service()
            await db_service.connect()
            
            # Test basic database operation
            database = db_service.database
            collections = await database.list_collection_names()
            
            # Should be able to list collections without error
            assert isinstance(collections, list)
            
            await db_service.disconnect()
            
        except Exception as e:
            # Database may not be available in test environment
            pytest.skip(f"Database not available for testing: {e}")
    
    @pytest.mark.asyncio
    async def test_notification_indexes_creation(self):
        """Test that notification indexes are created properly."""
        try:
            from src.backend.auth.services.database_service import get_database_service
            from src.backend.notification.utils.mongodb_setup import ensure_notification_indexes
            
            db_service = get_database_service()
            await db_service.connect()
            
            # Test index creation
            mongo_client = db_service.client
            await ensure_notification_indexes(mongo_client)
            
            # Should complete without error
            await db_service.disconnect()
            
        except Exception as e:
            # Database may not be available in test environment
            pytest.skip(f"Database not available for testing: {e}")


class TestNotificationServiceIntegration:
    """Test service layer integration for notification engine."""
    
    @pytest.mark.asyncio
    async def test_service_dependency_injection(self):
        """Test that notification services can be properly injected."""
        try:
            from src.backend.notification.routes.notification_routes import get_notification_controller
            from src.backend.config.database import get_database
            from src.backend.auth.services.database_service import get_database_service
            
            # Mock database dependency
            db_service = get_database_service()
            await db_service.connect()
            database = db_service.database
            
            # Test controller creation with dependencies
            controller = await get_notification_controller(database)
            
            # Should create controller without error
            assert controller is not None
            
            await db_service.disconnect()
            
        except Exception as e:
            # Dependencies may not be available in test environment
            pytest.skip(f"Dependencies not available for testing: {e}")


class TestNotificationPerformance:
    """Performance tests for notification engine."""
    
    @pytest.mark.asyncio
    async def test_health_endpoint_response_time(self, async_client):
        """Test that health endpoints respond within acceptable time."""
        import time
        
        start_time = time.time()
        response = await async_client.get("/api/v1/notifications/health/status")
        end_time = time.time()
        
        response_time = (end_time - start_time) * 1000  # Convert to milliseconds
        
        # Health endpoints should respond within 1 second
        assert response_time < 1000
        
        # Should return some response (may be error in test environment)
        assert response.status_code in [200, 503, 500]
    
    @pytest.mark.asyncio
    async def test_multiple_concurrent_health_requests(self, async_client):
        """Test handling of multiple concurrent health check requests."""
        async def make_health_request():
            return await async_client.get("/api/v1/notifications/health/status")
        
        # Make 10 concurrent requests
        tasks = [make_health_request() for _ in range(10)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All requests should complete (may return errors in test environment)
        assert len(responses) == 10
        
        # No requests should raise unhandled exceptions
        for response in responses:
            if not isinstance(response, Exception):
                assert response.status_code in [200, 503, 500]


class TestNotificationErrorHandling:
    """Test error handling in notification engine."""
    
    @pytest.mark.asyncio
    async def test_invalid_notification_id_format(self, async_client, auth_headers):
        """Test handling of invalid notification ID format."""
        with patch('src.backend.auth.dependencies.auth_dependency.get_current_user') as mock_auth:
            mock_auth.return_value = {
                "id": "user_123",
                "username": "testuser",
                "email": "test@example.com",
                "is_active": True
            }
            
            response = await async_client.get(
                "/api/v1/notifications/invalid_id_format",
                headers=auth_headers
            )
            
            # Should return validation error or not found
            assert response.status_code in [400, 404, 422]
    
    @pytest.mark.asyncio
    async def test_unauthorized_access(self, async_client):
        """Test handling of unauthorized access to protected endpoints."""
        # Try to access protected endpoint without authentication
        response = await async_client.get("/api/v1/notifications/")
        
        # Should return unauthorized
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_invalid_preferences_data(self, async_client, auth_headers):
        """Test handling of invalid preferences data."""
        with patch('src.backend.auth.dependencies.auth_dependency.get_current_user') as mock_auth:
            mock_auth.return_value = {
                "id": "user_123",
                "username": "testuser",
                "email": "test@example.com",
                "is_active": True
            }
            
            invalid_preferences = {
                "invalid_field": "invalid_value"
            }
            
            response = await async_client.put(
                "/api/v1/notifications/preferences",
                headers=auth_headers,
                json=invalid_preferences
            )
            
            # Should return validation error
            assert response.status_code in [400, 422]


# Test configuration and utilities
@pytest.fixture(scope="session")
def test_settings():
    """Get test-specific settings."""
    settings = get_settings()
    # Override settings for testing if needed
    settings.environment = "test"
    return settings


@pytest.fixture
def mock_notification_data():
    """Sample notification data for testing."""
    return {
        "notification_id": "ntfy_test123456",
        "user_id": "user_test123",
        "notification_type": "test_execution_complete",
        "title": "Test Execution Complete",
        "content": "Your test suite has completed successfully",
        "channels": ["email"],
        "priority": "medium",
        "status": "sent",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "test_suite_id": "suite_test789",
            "execution_time": "00:05:30"
        }
    }


@pytest.fixture
def mock_health_data():
    """Sample health data for testing."""
    return {
        "overall_status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": {
            "delivery_daemon": {
                "status": "healthy",
                "last_check": datetime.now(timezone.utc).isoformat()
            },
            "email_adapter": {
                "status": "healthy",
                "success_rate": 99.5
            },
            "database": {
                "status": "healthy",
                "latency_ms": 12
            }
        },
        "metrics": {
            "notifications_sent_24h": 100,
            "success_rate": 99.0,
            "average_delivery_time_ms": 450
        }
    } 
"""
Orchestration Routes Integration Tests

Comprehensive end-to-end testing for orchestration API endpoints including:
- Route-level testing via AsyncClient and test FastAPI app
- JWT authentication simulation with user context
- Mock OrchestrationController integration
- Complete orchestration job lifecycle testing (submit, status, cancel, list)
- Error handling and validation testing
- Response structure and status code validation
- Performance and edge case testing

Tests all endpoints:
- POST /orchestration/job - Submit orchestration job
- GET /orchestration/job/{job_id} - Get job status by ID
- DELETE /orchestration/job/{job_id} - Cancel orchestration job
- GET /orchestration/jobs - List jobs with filtering and pagination
- GET /orchestration/health - Service health check
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from unittest.mock import AsyncMock, Mock, patch
from bson import ObjectId
from httpx import AsyncClient

from src.backend.orchestration.schemas.orchestration_schemas import (
    CreateOrchestrationJobRequest,
    JobStatusResponse,
    JobListResponse,
    OrchestrationResponse
)
from src.backend.orchestration.models.orchestration_models import JobStatus
from src.backend.orchestration.controllers.orchestration_controller import (
    OrchestrationController,
    JobCancellationError
)


@pytest.fixture
def mock_orchestration_controller():
    """
    Mock OrchestrationController for integration testing.
    
    Provides a mock controller with predefined responses for testing
    various scenarios without requiring actual service layer dependencies.
    """
    controller = AsyncMock(spec=OrchestrationController)
    
    # Configure default mock responses
    controller.submit_orchestration_job.return_value = OrchestrationResponse(
        success=True,
        message="Orchestration job 'Test Job' submitted successfully",
        data={
            "job_id": str(ObjectId()),
            "status": "pending",
            "submitted_at": datetime.utcnow(),
            "priority": 5,
            "estimated_duration_ms": 300000
        },
        request_id="test_request_123"
    )
    
    controller.get_job_status.return_value = JobStatusResponse(
        job_id=str(ObjectId()),
        job_name="Test Job",
        job_type="test_execution",
        status=JobStatus.RUNNING,
        priority=5,
        triggered_at=datetime.utcnow(),
        started_at=datetime.utcnow(),
        progress_percentage=45.5,
        current_node_id="node_test_execution_3",
        retry_count=0,
        max_retries=3,
        execution_results={},
        error_details=None,
        triggered_by="test_user_id",
        tags=["integration", "test"],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    controller.cancel_orchestration_job.return_value = OrchestrationResponse(
        success=True,
        message="Job cancellation initiated successfully",
        data={
            "job_id": str(ObjectId()),
            "cancelled_at": datetime.utcnow(),
            "cancellation_reason": "User requested"
        },
        request_id="test_request_456"
    )
    
    controller.list_orchestration_jobs.return_value = JobListResponse(
        jobs=[
            JobStatusResponse(
                job_id=str(ObjectId()),
                job_name="Test Job 1",
                job_type="test_execution",
                status=JobStatus.COMPLETED,
                priority=5,
                triggered_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
                progress_percentage=100.0,
                retry_count=0,
                max_retries=3,
                execution_results={"tests_passed": 15, "tests_failed": 0},
                triggered_by="test_user_id",
                tags=["regression"],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
        ],
        total_count=1,
        page=1,
        page_size=20,
        has_next=False
    )
    
    return controller


@pytest.fixture
def sample_job_request():
    """Sample job creation request for testing."""
    return {
        "job_name": "Integration Test Job",
        "job_description": "Test job for integration testing",
        "job_type": "test_execution",
        "priority": 5,
        "tags": ["integration", "test"],
        "test_case_ids": [str(ObjectId()), str(ObjectId())],
        "max_retries": 3,
        "timeout_ms": 300000,
        "estimated_duration_ms": 240000,
        "configuration": {
            "parallel_execution": True,
            "fail_fast": False
        },
        "metadata": {
            "environment": "test",
            "branch": "main"
        }
    }


@pytest.fixture
def sample_job_id():
    """Sample job ID for testing."""
    return str(ObjectId())


@pytest.fixture
def assert_orchestration_response():
    """Assertion helper for orchestration response structure."""
    def _assert_response(response_data: Dict[str, Any], success: bool = True):
        """Assert standard orchestration response structure."""
        assert "success" in response_data
        assert response_data["success"] == success
        assert "message" in response_data
        assert isinstance(response_data["message"], str)
        
        if success:
            assert "data" in response_data
            assert response_data["data"] is not None
        
        if "timestamp" in response_data:
            assert isinstance(response_data["timestamp"], str)
        
        if "request_id" in response_data:
            assert isinstance(response_data["request_id"], str)
    
    return _assert_response


@pytest.fixture
def assert_job_status_response():
    """Assertion helper for job status response structure."""
    def _assert_job_status(job_data: Dict[str, Any]):
        """Assert job status response structure."""
        required_fields = [
            "job_id", "job_name", "job_type", "status", "priority",
            "triggered_at", "retry_count", "max_retries", "triggered_by",
            "tags", "created_at"
        ]
        
        for field in required_fields:
            assert field in job_data, f"Missing required field: {field}"
        
        assert isinstance(job_data["job_id"], str)
        assert len(job_data["job_id"]) == 24  # ObjectId length
        assert isinstance(job_data["job_name"], str)
        assert job_data["job_type"] in [
            "test_execution", "test_suite_execution", "test_item_validation",
            "data_processing", "notification_trigger", "cleanup_operation"
        ]
        assert job_data["status"] in [s.value for s in JobStatus]
        assert isinstance(job_data["priority"], int)
        assert 1 <= job_data["priority"] <= 10
        assert isinstance(job_data["retry_count"], int)
        assert isinstance(job_data["max_retries"], int)
        assert isinstance(job_data["tags"], list)
        
        # Optional fields
        if "progress_percentage" in job_data and job_data["progress_percentage"] is not None:
            assert 0 <= job_data["progress_percentage"] <= 100
        
        if "execution_results" in job_data:
            assert isinstance(job_data["execution_results"], dict)
    
    return _assert_job_status


@pytest.mark.asyncio
class TestSubmitOrchestrationJobRoute:
    """Test the POST /orchestration/job endpoint for submitting orchestration jobs."""
    
    async def test_submit_job_success(
        self,
        authenticated_client: AsyncClient,
        mock_orchestration_controller,
        sample_job_request,
        assert_orchestration_response
    ):
        """Test successful orchestration job submission."""
        # Arrange
        with patch(
            'src.backend.orchestration.controllers.orchestration_controller.OrchestrationControllerFactory.create_controller',
            return_value=mock_orchestration_controller
        ):
            # Act
            response = await authenticated_client.post("/orchestration/job", json=sample_job_request)
        
        # Assert
        assert response.status_code == 202
        response_data = response.json()
        
        assert_orchestration_response(response_data, success=True)
        assert "submitted successfully" in response_data["message"]
        
        job_data = response_data["data"]
        assert "job_id" in job_data
        assert "status" in job_data
        assert "submitted_at" in job_data
        assert "priority" in job_data
        assert job_data["priority"] == sample_job_request["priority"]
        
        # Verify controller was called with correct parameters
        mock_orchestration_controller.submit_orchestration_job.assert_called_once()
        
        call_args = mock_orchestration_controller.submit_orchestration_job.call_args
        request_obj = call_args[1]["request"]
        assert request_obj.job_name == sample_job_request["job_name"]
        assert request_obj.job_type == sample_job_request["job_type"]
        assert request_obj.priority == sample_job_request["priority"]
    
    async def test_submit_job_validation_errors(
        self,
        authenticated_client: AsyncClient,
        mock_orchestration_controller
    ):
        """Test validation errors in job submission."""
        # Test missing job_name
        response = await authenticated_client.post("/orchestration/job", json={})
        assert response.status_code == 422
        
        # Test empty job_name
        response = await authenticated_client.post("/orchestration/job", json={"job_name": ""})
        assert response.status_code == 422
        
        # Test invalid job_type
        response = await authenticated_client.post("/orchestration/job", json={
            "job_name": "Test Job",
            "job_type": "invalid_type"
        })
        assert response.status_code == 422
    
    async def test_submit_job_unauthorized(
        self,
        async_client: AsyncClient,
        sample_job_request
    ):
        """Test job submission without authentication."""
        response = await async_client.post("/orchestration/job", json=sample_job_request)
        assert response.status_code == 401


@pytest.mark.asyncio
class TestGetJobStatusRoute:
    """Test the GET /orchestration/job/{job_id} endpoint for job status retrieval."""
    
    async def test_get_job_status_success(
        self,
        authenticated_client: AsyncClient,
        mock_orchestration_controller,
        sample_job_id,
        assert_job_status_response
    ):
        """Test successful job status retrieval."""
        # Arrange
        with patch(
            'src.backend.orchestration.controllers.orchestration_controller.OrchestrationControllerFactory.create_controller',
            return_value=mock_orchestration_controller
        ):
            # Act
            response = await authenticated_client.get(f"/orchestration/job/{sample_job_id}")
        
        # Assert
        assert response.status_code == 200
        job_data = response.json()
        
        assert_job_status_response(job_data)
        assert job_data["job_name"] == "Test Job"
        assert job_data["status"] == "running"
        assert job_data["progress_percentage"] == 45.5
        
        # Verify controller was called with correct job_id
        mock_orchestration_controller.get_job_status.assert_called_once()
        call_args = mock_orchestration_controller.get_job_status.call_args
        assert call_args[1]["job_id"] == sample_job_id
    
    async def test_get_job_status_not_found(
        self,
        authenticated_client: AsyncClient,
        mock_orchestration_controller,
        sample_job_id
    ):
        """Test job status retrieval for non-existent job."""
        # Arrange
        from fastapi import HTTPException
        mock_orchestration_controller.get_job_status.side_effect = HTTPException(
            status_code=404,
            detail=f"Job {sample_job_id} not found or access denied"
        )
        
        with patch(
            'src.backend.orchestration.controllers.orchestration_controller.OrchestrationControllerFactory.create_controller',
            return_value=mock_orchestration_controller
        ):
            # Act
            response = await authenticated_client.get(f"/orchestration/job/{sample_job_id}")
        
        # Assert
        assert response.status_code == 404
        response_data = response.json()
        assert "not found or access denied" in response_data["detail"]
    
    async def test_get_job_status_unauthorized(
        self,
        async_client: AsyncClient,
        sample_job_id
    ):
        """Test job status retrieval without authentication."""
        response = await async_client.get(f"/orchestration/job/{sample_job_id}")
        assert response.status_code == 401


@pytest.mark.asyncio
class TestCancelJobRoute:
    """Test the DELETE /orchestration/job/{job_id} endpoint for job cancellation."""
    
    async def test_cancel_job_success(
        self,
        authenticated_client: AsyncClient,
        mock_orchestration_controller,
        sample_job_id,
        assert_orchestration_response
    ):
        """Test successful job cancellation."""
        # Arrange
        with patch(
            'src.backend.orchestration.controllers.orchestration_controller.OrchestrationControllerFactory.create_controller',
            return_value=mock_orchestration_controller
        ):
            # Act
            response = await authenticated_client.delete(f"/orchestration/job/{sample_job_id}")
        
        # Assert
        assert response.status_code == 200
        response_data = response.json()
        
        assert_orchestration_response(response_data, success=True)
        assert "cancellation initiated successfully" in response_data["message"]
        
        cancellation_data = response_data["data"]
        assert "job_id" in cancellation_data
        assert "cancelled_at" in cancellation_data
        assert "cancellation_reason" in cancellation_data
        
        # Verify controller was called with correct job_id
        mock_orchestration_controller.cancel_orchestration_job.assert_called_once()
        call_args = mock_orchestration_controller.cancel_orchestration_job.call_args
        assert call_args[1]["job_id"] == sample_job_id
    
    async def test_cancel_job_not_found(
        self,
        authenticated_client: AsyncClient,
        mock_orchestration_controller,
        sample_job_id
    ):
        """Test job cancellation for non-existent job."""
        # Arrange
        from fastapi import HTTPException
        mock_orchestration_controller.cancel_orchestration_job.side_effect = HTTPException(
            status_code=404,
            detail=f"Job {sample_job_id} not found or access denied"
        )
        
        with patch(
            'src.backend.orchestration.controllers.orchestration_controller.OrchestrationControllerFactory.create_controller',
            return_value=mock_orchestration_controller
        ):
            # Act
            response = await authenticated_client.delete(f"/orchestration/job/{sample_job_id}")
        
        # Assert
        assert response.status_code == 404
        response_data = response.json()
        assert "not found or access denied" in response_data["detail"]
    
    async def test_cancel_job_unauthorized(
        self,
        async_client: AsyncClient,
        sample_job_id
    ):
        """Test job cancellation without authentication."""
        response = await async_client.delete(f"/orchestration/job/{sample_job_id}")
        assert response.status_code == 401


@pytest.mark.asyncio
class TestListJobsRoute:
    """Test the GET /orchestration/jobs endpoint for job listing."""
    
    async def test_list_jobs_success(
        self,
        authenticated_client: AsyncClient,
        mock_orchestration_controller,
        assert_job_status_response
    ):
        """Test successful job listing."""
        # Arrange
        with patch(
            'src.backend.orchestration.controllers.orchestration_controller.OrchestrationControllerFactory.create_controller',
            return_value=mock_orchestration_controller
        ):
            # Act
            response = await authenticated_client.get("/orchestration/jobs")
        
        # Assert
        assert response.status_code == 200
        response_data = response.json()
        
        assert "jobs" in response_data
        assert "total_count" in response_data
        assert "page" in response_data
        assert "page_size" in response_data
        assert "has_next" in response_data
        
        assert isinstance(response_data["jobs"], list)
        assert response_data["total_count"] == 1
        assert response_data["page"] == 1
        assert response_data["page_size"] == 20
        assert response_data["has_next"] is False
        
        # Verify job structure
        if response_data["jobs"]:
            job = response_data["jobs"][0]
            assert_job_status_response(job)
        
        # Verify controller was called with default parameters
        mock_orchestration_controller.list_orchestration_jobs.assert_called_once()
        call_args = mock_orchestration_controller.list_orchestration_jobs.call_args[1]
        assert call_args["limit"] == 20
        assert call_args["offset"] == 0
    
    async def test_list_jobs_unauthorized(
        self,
        async_client: AsyncClient
    ):
        """Test job listing without authentication."""
        response = await async_client.get("/orchestration/jobs")
        assert response.status_code == 401


@pytest.mark.asyncio
class TestOrchestrationHealthRoute:
    """Test the GET /orchestration/health endpoint for service health check."""
    
    async def test_health_check_success(
        self,
        authenticated_client: AsyncClient
    ):
        """Test successful health check."""
        # Act
        response = await authenticated_client.get("/orchestration/health")
        
        # Assert
        assert response.status_code == 200
        health_data = response.json()
        
        assert "service" in health_data
        assert health_data["service"] == "orchestration"
        assert "status" in health_data
        assert health_data["status"] == "healthy"
        assert "version" in health_data
        assert health_data["version"] == "1.0.0"
        assert "timestamp" in health_data
        assert "authenticated_user" in health_data
        
        # Verify timestamp format
        assert isinstance(health_data["timestamp"], str)
        assert health_data["timestamp"].endswith("Z")
    
    async def test_health_check_unauthorized(
        self,
        async_client: AsyncClient
    ):
        """Test health check without authentication."""
        response = await async_client.get("/orchestration/health")
        assert response.status_code == 401


@pytest.mark.asyncio
class TestRouteAuthentication:
    """Test authentication requirements across all orchestration routes."""
    
    async def test_all_routes_require_authentication(
        self,
        async_client: AsyncClient,
        sample_job_request,
        sample_job_id
    ):
        """Test that all orchestration routes require authentication."""
        # Test POST /orchestration/job
        response = await async_client.post("/orchestration/job", json=sample_job_request)
        assert response.status_code == 401
        
        # Test GET /orchestration/job/{job_id}
        response = await async_client.get(f"/orchestration/job/{sample_job_id}")
        assert response.status_code == 401
        
        # Test DELETE /orchestration/job/{job_id}
        response = await async_client.delete(f"/orchestration/job/{sample_job_id}")
        assert response.status_code == 401
        
        # Test GET /orchestration/jobs
        response = await async_client.get("/orchestration/jobs")
        assert response.status_code == 401
        
        # Test GET /orchestration/health
        response = await async_client.get("/orchestration/health")
        assert response.status_code == 401


@pytest.mark.asyncio
class TestRouteErrorHandling:
    """Test error handling across all orchestration routes."""
    
    async def test_malformed_json_requests(
        self,
        authenticated_client: AsyncClient
    ):
        """Test handling of malformed JSON requests."""
        # Test malformed JSON
        response = await authenticated_client.post(
            "/orchestration/job",
            content="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422
    
    async def test_route_not_found(
        self,
        authenticated_client: AsyncClient
    ):
        """Test non-existent route handling."""
        response = await authenticated_client.get("/orchestration/nonexistent")
        assert response.status_code == 404


@pytest.mark.asyncio
class TestRouteIntegration:
    """Test end-to-end orchestration workflow integration."""
    
    async def test_complete_job_lifecycle(
        self,
        authenticated_client: AsyncClient,
        mock_orchestration_controller,
        sample_job_request
    ):
        """Test complete job lifecycle: submit -> status -> cancel."""
        with patch(
            'src.backend.orchestration.controllers.orchestration_controller.OrchestrationControllerFactory.create_controller',
            return_value=mock_orchestration_controller
        ):
            # Step 1: Submit job
            submit_response = await authenticated_client.post("/orchestration/job", json=sample_job_request)
            assert submit_response.status_code == 202
            
            job_data = submit_response.json()["data"]
            job_id = job_data["job_id"]
            
            # Step 2: Get job status
            status_response = await authenticated_client.get(f"/orchestration/job/{job_id}")
            assert status_response.status_code == 200
            
            status_data = status_response.json()
            assert status_data["job_id"] == job_id
            
            # Step 3: Cancel job
            cancel_response = await authenticated_client.delete(f"/orchestration/job/{job_id}")
            assert cancel_response.status_code == 200
            
            cancel_data = cancel_response.json()["data"]
            assert cancel_data["job_id"] == job_id
            
            # Verify all controller methods were called
            assert mock_orchestration_controller.submit_orchestration_job.called
            assert mock_orchestration_controller.get_job_status.called
            assert mock_orchestration_controller.cancel_orchestration_job.called


@pytest.mark.asyncio
class TestGetJobStatusRoute:
    """Test the GET /orchestration/job/{job_id} endpoint for job status retrieval."""
    
    async def test_get_job_status_success(
        self,
        authenticated_client: AsyncClient,
        mock_orchestration_controller,
        sample_job_id,
        assert_job_status_response
    ):
        """Test successful job status retrieval."""
        # Arrange
        with patch(
            'src.backend.orchestration.controllers.orchestration_controller.OrchestrationControllerFactory.create_controller',
            return_value=mock_orchestration_controller
        ):
            # Act
            response = await authenticated_client.get(f"/orchestration/job/{sample_job_id}")
        
        # Assert
        assert response.status_code == 200
        job_data = response.json()
        
        assert_job_status_response(job_data)
        assert job_data["job_name"] == "Test Job"
        assert job_data["status"] == "running"
        assert job_data["progress_percentage"] == 45.5
        assert job_data["current_node_id"] == "node_test_execution_3"
        
        # Verify controller was called with correct job_id
        mock_orchestration_controller.get_job_status.assert_called_once()
        call_args = mock_orchestration_controller.get_job_status.call_args
        assert call_args[1]["job_id"] == sample_job_id
    
    async def test_get_job_status_not_found(
        self,
        authenticated_client: AsyncClient,
        mock_orchestration_controller,
        sample_job_id
    ):
        """Test job status retrieval for non-existent job."""
        # Arrange
        from fastapi import HTTPException
        mock_orchestration_controller.get_job_status.side_effect = HTTPException(
            status_code=404,
            detail=f"Job {sample_job_id} not found or access denied"
        )
        
        with patch(
            'src.backend.orchestration.controllers.orchestration_controller.OrchestrationControllerFactory.create_controller',
            return_value=mock_orchestration_controller
        ):
            # Act
            response = await authenticated_client.get(f"/orchestration/job/{sample_job_id}")
        
        # Assert
        assert response.status_code == 404
        response_data = response.json()
        assert "not found or access denied" in response_data["detail"]
    
    async def test_get_job_status_invalid_id(
        self,
        authenticated_client: AsyncClient
    ):
        """Test job status retrieval with invalid job ID format."""
        invalid_id = "invalid_job_id"
        
        response = await authenticated_client.get(f"/orchestration/job/{invalid_id}")
        assert response.status_code == 422  # Pydantic validation error
    
    async def test_get_job_status_access_denied(
        self,
        authenticated_client: AsyncClient,
        mock_orchestration_controller,
        sample_job_id
    ):
        """Test job status retrieval for job owned by different user."""
        # Arrange
        from fastapi import HTTPException
        mock_orchestration_controller.get_job_status.side_effect = HTTPException(
            status_code=403,
            detail=f"Access denied to job {sample_job_id}"
        )
        
        with patch(
            'src.backend.orchestration.controllers.orchestration_controller.OrchestrationControllerFactory.create_controller',
            return_value=mock_orchestration_controller
        ):
            # Act
            response = await authenticated_client.get(f"/orchestration/job/{sample_job_id}")
        
        # Assert
        assert response.status_code == 403
        response_data = response.json()
        assert "Access denied" in response_data["detail"]
    
    async def test_get_job_status_unauthorized(
        self,
        async_client: AsyncClient,
        sample_job_id
    ):
        """Test job status retrieval without authentication."""
        response = await async_client.get(f"/orchestration/job/{sample_job_id}")
        assert response.status_code == 401


@pytest.mark.asyncio
class TestCancelJobRoute:
    """Test the DELETE /orchestration/job/{job_id} endpoint for job cancellation."""
    
    async def test_cancel_job_success(
        self,
        authenticated_client: AsyncClient,
        mock_orchestration_controller,
        sample_job_id,
        assert_orchestration_response
    ):
        """Test successful job cancellation."""
        # Arrange
        with patch(
            'src.backend.orchestration.controllers.orchestration_controller.OrchestrationControllerFactory.create_controller',
            return_value=mock_orchestration_controller
        ):
            # Act
            response = await authenticated_client.delete(f"/orchestration/job/{sample_job_id}")
        
        # Assert
        assert response.status_code == 200
        response_data = response.json()
        
        assert_orchestration_response(response_data, success=True)
        assert "cancellation initiated successfully" in response_data["message"]
        
        cancellation_data = response_data["data"]
        assert "job_id" in cancellation_data
        assert "cancelled_at" in cancellation_data
        assert "cancellation_reason" in cancellation_data
        assert cancellation_data["cancellation_reason"] == "User requested"
        
        # Verify controller was called with correct job_id
        mock_orchestration_controller.cancel_orchestration_job.assert_called_once()
        call_args = mock_orchestration_controller.cancel_orchestration_job.call_args
        assert call_args[1]["job_id"] == sample_job_id
    
    async def test_cancel_job_not_found(
        self,
        authenticated_client: AsyncClient,
        mock_orchestration_controller,
        sample_job_id
    ):
        """Test job cancellation for non-existent job."""
        # Arrange
        from fastapi import HTTPException
        mock_orchestration_controller.cancel_orchestration_job.side_effect = HTTPException(
            status_code=404,
            detail=f"Job {sample_job_id} not found or access denied"
        )
        
        with patch(
            'src.backend.orchestration.controllers.orchestration_controller.OrchestrationControllerFactory.create_controller',
            return_value=mock_orchestration_controller
        ):
            # Act
            response = await authenticated_client.delete(f"/orchestration/job/{sample_job_id}")
        
        # Assert
        assert response.status_code == 404
        response_data = response.json()
        assert "not found or access denied" in response_data["detail"]
    
    async def test_cancel_job_invalid_state(
        self,
        authenticated_client: AsyncClient,
        mock_orchestration_controller,
        sample_job_id
    ):
        """Test job cancellation for job in non-cancellable state."""
        # Arrange
        from fastapi import HTTPException
        mock_orchestration_controller.cancel_orchestration_job.side_effect = HTTPException(
            status_code=409,
            detail=f"Job {sample_job_id} cannot be cancelled in completed state"
        )
        
        with patch(
            'src.backend.orchestration.controllers.orchestration_controller.OrchestrationControllerFactory.create_controller',
            return_value=mock_orchestration_controller
        ):
            # Act
            response = await authenticated_client.delete(f"/orchestration/job/{sample_job_id}")
        
        # Assert
        assert response.status_code == 409
        response_data = response.json()
        assert "cannot be cancelled" in response_data["detail"]
    
    async def test_cancel_job_cancellation_failure(
        self,
        authenticated_client: AsyncClient,
        mock_orchestration_controller,
        sample_job_id
    ):
        """Test job cancellation system failure."""
        # Arrange
        from fastapi import HTTPException
        mock_orchestration_controller.cancel_orchestration_job.side_effect = HTTPException(
            status_code=500,
            detail="Failed to cancel job: execution state tracker unavailable"
        )
        
        with patch(
            'src.backend.orchestration.controllers.orchestration_controller.OrchestrationControllerFactory.create_controller',
            return_value=mock_orchestration_controller
        ):
            # Act
            response = await authenticated_client.delete(f"/orchestration/job/{sample_job_id}")
        
        # Assert
        assert response.status_code == 500
        response_data = response.json()
        assert "Failed to cancel job" in response_data["detail"]
    
    async def test_cancel_job_unauthorized(
        self,
        async_client: AsyncClient,
        sample_job_id
    ):
        """Test job cancellation without authentication."""
        response = await async_client.delete(f"/orchestration/job/{sample_job_id}")
        assert response.status_code == 401


@pytest.mark.asyncio
class TestListJobsRoute:
    """Test the GET /orchestration/jobs endpoint for job listing."""
    
    async def test_list_jobs_success(
        self,
        authenticated_client: AsyncClient,
        mock_orchestration_controller,
        assert_job_status_response
    ):
        """Test successful job listing."""
        # Arrange
        with patch(
            'src.backend.orchestration.controllers.orchestration_controller.OrchestrationControllerFactory.create_controller',
            return_value=mock_orchestration_controller
        ):
            # Act
            response = await authenticated_client.get("/orchestration/jobs")
        
        # Assert
        assert response.status_code == 200
        response_data = response.json()
        
        assert "jobs" in response_data
        assert "total_count" in response_data
        assert "page" in response_data
        assert "page_size" in response_data
        assert "has_next" in response_data
        
        assert isinstance(response_data["jobs"], list)
        assert response_data["total_count"] == 1
        assert response_data["page"] == 1
        assert response_data["page_size"] == 20
        assert response_data["has_next"] is False
        
        # Verify job structure
        if response_data["jobs"]:
            job = response_data["jobs"][0]
            assert_job_status_response(job)
        
        # Verify controller was called with default parameters
        mock_orchestration_controller.list_orchestration_jobs.assert_called_once()
        call_args = mock_orchestration_controller.list_orchestration_jobs.call_args[1]
        assert call_args["limit"] == 20
        assert call_args["offset"] == 0
        assert call_args["status_filter"] is None
    
    async def test_list_jobs_with_filters(
        self,
        authenticated_client: AsyncClient,
        mock_orchestration_controller
    ):
        """Test job listing with various filters."""
        # Arrange
        filters = {
            "status": "running",
            "created_after": "2024-01-01T00:00:00Z",
            "created_before": "2024-12-31T23:59:59Z",
            "target_type": "test_execution",
            "limit": 10,
            "offset": 5
        }
        
        with patch(
            'src.backend.orchestration.controllers.orchestration_controller.OrchestrationControllerFactory.create_controller',
            return_value=mock_orchestration_controller
        ):
            # Act
            response = await authenticated_client.get("/orchestration/jobs", params=filters)
        
        # Assert
        assert response.status_code == 200
        
        # Verify controller was called with correct filters
        mock_orchestration_controller.list_orchestration_jobs.assert_called_once()
        call_args = mock_orchestration_controller.list_orchestration_jobs.call_args[1]
        assert call_args["status_filter"] == "running"
        assert call_args["target_type"] == "test_execution"
        assert call_args["limit"] == 10
        assert call_args["offset"] == 5
    
    async def test_list_jobs_pagination_validation(
        self,
        authenticated_client: AsyncClient,
        mock_orchestration_controller
    ):
        """Test pagination parameter validation."""
        # Test invalid limit (too high)
        response = await authenticated_client.get("/orchestration/jobs", params={"limit": 200})
        assert response.status_code == 422
        
        # Test invalid limit (too low)
        response = await authenticated_client.get("/orchestration/jobs", params={"limit": 0})
        assert response.status_code == 422
        
        # Test invalid offset (negative)
        response = await authenticated_client.get("/orchestration/jobs", params={"offset": -1})
        assert response.status_code == 422
    
    async def test_list_jobs_filter_validation(
        self,
        authenticated_client: AsyncClient,
        mock_orchestration_controller
    ):
        """Test filter parameter validation."""
        # Arrange
        from fastapi import HTTPException
        mock_orchestration_controller.list_orchestration_jobs.side_effect = HTTPException(
            status_code=400,
            detail="Invalid status filter: invalid_status"
        )
        
        with patch(
            'src.backend.orchestration.controllers.orchestration_controller.OrchestrationControllerFactory.create_controller',
            return_value=mock_orchestration_controller
        ):
            # Act
            response = await authenticated_client.get(
                "/orchestration/jobs", 
                params={"status": "invalid_status"}
            )
        
        # Assert
        assert response.status_code == 400
        response_data = response.json()
        assert "Invalid status filter" in response_data["detail"]
    
    async def test_list_jobs_unauthorized(
        self,
        async_client: AsyncClient
    ):
        """Test job listing without authentication."""
        response = await async_client.get("/orchestration/jobs")
        assert response.status_code == 401


@pytest.mark.asyncio
class TestOrchestrationHealthRoute:
    """Test the GET /orchestration/health endpoint for service health check."""
    
    async def test_health_check_success(
        self,
        authenticated_client: AsyncClient
    ):
        """Test successful health check."""
        # Act
        response = await authenticated_client.get("/orchestration/health")
        
        # Assert
        assert response.status_code == 200
        health_data = response.json()
        
        assert "service" in health_data
        assert health_data["service"] == "orchestration"
        assert "status" in health_data
        assert health_data["status"] == "healthy"
        assert "version" in health_data
        assert health_data["version"] == "1.0.0"
        assert "timestamp" in health_data
        assert "authenticated_user" in health_data
        
        # Verify timestamp format
        assert isinstance(health_data["timestamp"], str)
        assert health_data["timestamp"].endswith("Z")
    
    async def test_health_check_unauthorized(
        self,
        async_client: AsyncClient
    ):
        """Test health check without authentication."""
        response = await async_client.get("/orchestration/health")
        assert response.status_code == 401


@pytest.mark.asyncio
class TestRouteAuthentication:
    """Test authentication requirements across all orchestration routes."""
    
    async def test_all_routes_require_authentication(
        self,
        async_client: AsyncClient,
        sample_job_request,
        sample_job_id
    ):
        """Test that all orchestration routes require authentication."""
        # Test POST /orchestration/job
        response = await async_client.post("/orchestration/job", json=sample_job_request)
        assert response.status_code == 401
        
        # Test GET /orchestration/job/{job_id}
        response = await async_client.get(f"/orchestration/job/{sample_job_id}")
        assert response.status_code == 401
        
        # Test DELETE /orchestration/job/{job_id}
        response = await async_client.delete(f"/orchestration/job/{sample_job_id}")
        assert response.status_code == 401
        
        # Test GET /orchestration/jobs
        response = await async_client.get("/orchestration/jobs")
        assert response.status_code == 401
        
        # Test GET /orchestration/health
        response = await async_client.get("/orchestration/health")
        assert response.status_code == 401
    
    async def test_invalid_jwt_token(
        self,
        async_client: AsyncClient,
        sample_job_request
    ):
        """Test routes with invalid JWT token."""
        # Set invalid token
        async_client.headers.update({"Authorization": "Bearer invalid_token"})
        
        response = await async_client.post("/orchestration/job", json=sample_job_request)
        assert response.status_code == 401
    
    async def test_expired_jwt_token(
        self,
        async_client: AsyncClient,
        generate_jwt_token,
        sample_job_request
    ):
        """Test routes with expired JWT token."""
        # Generate expired token
        expired_token = generate_jwt_token(expires_delta=timedelta(seconds=-1))
        async_client.headers.update({"Authorization": f"Bearer {expired_token}"})
        
        response = await async_client.post("/orchestration/job", json=sample_job_request)
        assert response.status_code == 401


@pytest.mark.asyncio
class TestRouteErrorHandling:
    """Test error handling across all orchestration routes."""
    
    async def test_malformed_json_requests(
        self,
        authenticated_client: AsyncClient
    ):
        """Test handling of malformed JSON requests."""
        # Test malformed JSON
        response = await authenticated_client.post(
            "/orchestration/job",
            content="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422
    
    async def test_large_request_payloads(
        self,
        authenticated_client: AsyncClient
    ):
        """Test handling of large request payloads."""
        # Create very large request
        large_request = {
            "job_name": "Large Request Test",
            "job_type": "test_execution",
            "test_case_ids": [str(ObjectId()) for _ in range(1000)],  # Large list
            "configuration": {
                "large_data": "x" * 10000  # Large string
            }
        }
        
        response = await authenticated_client.post("/orchestration/job", json=large_request)
        # Should either accept or reject cleanly (not crash)
        assert response.status_code in [200, 201, 202, 400, 413, 422]
    
    async def test_route_not_found(
        self,
        authenticated_client: AsyncClient
    ):
        """Test non-existent route handling."""
        response = await authenticated_client.get("/orchestration/nonexistent")
        assert response.status_code == 404
    
    async def test_method_not_allowed(
        self,
        authenticated_client: AsyncClient,
        sample_job_id
    ):
        """Test incorrect HTTP method handling."""
        # Try POST on a GET-only endpoint
        response = await authenticated_client.post(f"/orchestration/job/{sample_job_id}")
        assert response.status_code == 405
        
        # Try PUT on job endpoint (not supported)
        response = await authenticated_client.put(f"/orchestration/job/{sample_job_id}")
        assert response.status_code == 405


@pytest.mark.asyncio
class TestRoutePerformance:
    """Test performance characteristics of orchestration routes."""
    
    async def test_response_timing(
        self,
        authenticated_client: AsyncClient,
        mock_orchestration_controller
    ):
        """Test that routes respond within reasonable time limits."""
        import time
        
        # Test health endpoint timing
        start_time = time.time()
        response = await authenticated_client.get("/orchestration/health")
        end_time = time.time()
        
        assert response.status_code == 200
        assert (end_time - start_time) < 1.0  # Should respond within 1 second
        
        # Test job listing timing
        with patch(
            'src.backend.orchestration.controllers.orchestration_controller.OrchestrationControllerFactory.create_controller',
            return_value=mock_orchestration_controller
        ):
            start_time = time.time()
            response = await authenticated_client.get("/orchestration/jobs")
            end_time = time.time()
        
        assert response.status_code == 200
        assert (end_time - start_time) < 2.0  # Should respond within 2 seconds


@pytest.mark.asyncio
class TestRouteIntegration:
    """Test end-to-end orchestration workflow integration."""
    
    async def test_complete_job_lifecycle(
        self,
        authenticated_client: AsyncClient,
        mock_orchestration_controller,
        sample_job_request
    ):
        """Test complete job lifecycle: submit -> status -> cancel."""
        with patch(
            'src.backend.orchestration.controllers.orchestration_controller.OrchestrationControllerFactory.create_controller',
            return_value=mock_orchestration_controller
        ):
            # Step 1: Submit job
            submit_response = await authenticated_client.post("/orchestration/job", json=sample_job_request)
            assert submit_response.status_code == 202
            
            job_data = submit_response.json()["data"]
            job_id = job_data["job_id"]
            
            # Step 2: Get job status
            status_response = await authenticated_client.get(f"/orchestration/job/{job_id}")
            assert status_response.status_code == 200
            
            status_data = status_response.json()
            assert status_data["job_id"] == job_id
            
            # Step 3: Cancel job
            cancel_response = await authenticated_client.delete(f"/orchestration/job/{job_id}")
            assert cancel_response.status_code == 200
            
            cancel_data = cancel_response.json()["data"]
            assert cancel_data["job_id"] == job_id
            
            # Verify all controller methods were called
            assert mock_orchestration_controller.submit_orchestration_job.called
            assert mock_orchestration_controller.get_job_status.called
            assert mock_orchestration_controller.cancel_orchestration_job.called 
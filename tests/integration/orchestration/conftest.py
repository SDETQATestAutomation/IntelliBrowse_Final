"""
Orchestration Integration Tests Configuration

Provides test-specific fixtures and configuration for orchestration route testing,
including simplified dependency injection and mock service setup.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, Mock
from typing import Dict, Any
from datetime import datetime
from bson import ObjectId

from src.backend.orchestration.controllers.orchestration_controller import OrchestrationController
from src.backend.orchestration.schemas.orchestration_schemas import (
    OrchestrationResponse,
    JobStatusResponse,
    JobListResponse
)
from src.backend.orchestration.models.orchestration_models import JobStatus


@pytest.fixture
def mock_orchestration_service():
    """Mock base orchestration service."""
    service = AsyncMock()
    return service


@pytest.fixture
def mock_job_scheduler_service():
    """Mock job scheduler service."""
    service = AsyncMock()
    return service


@pytest.fixture
def mock_execution_state_tracker():
    """Mock execution state tracker."""
    tracker = AsyncMock()
    return tracker


@pytest.fixture
def orchestration_controller(
    mock_orchestration_service,
    mock_job_scheduler_service,
    mock_execution_state_tracker
):
    """Create a real OrchestrationController with mocked dependencies."""
    return OrchestrationController(
        orchestration_service=mock_orchestration_service,
        job_scheduler_service=mock_job_scheduler_service,
        execution_state_tracker=mock_execution_state_tracker
    )


@pytest.fixture
def mock_controller_responses():
    """Pre-configured mock responses for controller methods."""
    return {
        "submit_job": OrchestrationResponse(
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
        ),
        "job_status": JobStatusResponse(
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
        ),
        "cancel_job": OrchestrationResponse(
            success=True,
            message="Job cancellation initiated successfully",
            data={
                "job_id": str(ObjectId()),
                "cancelled_at": datetime.utcnow(),
                "cancellation_reason": "User requested"
            },
            request_id="test_request_456"
        ),
        "list_jobs": JobListResponse(
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
    } 
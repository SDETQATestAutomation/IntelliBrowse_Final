"""
Shared pytest fixtures for IntelliBrowse test suite integration tests.

Provides comprehensive test infrastructure including:
- Async test client with authentication
- Test database setup and teardown
- JWT token generation and authentication fixtures
- Sample data factories for test suite requests/responses
- MongoDB test collections with isolated environments
"""

import pytest
import pytest_asyncio
import asyncio
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient
import httpx
import jwt

# Test environment setup
os.environ["ENVIRONMENT"] = "development"
os.environ["MONGODB_URL"] = "mongodb://localhost:27017/intellibrowse_test"
os.environ["JWT_SECRET_KEY"] = "test_secret_key_for_jwt_integration_testing"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["JWT_EXPIRY_MINUTES"] = "60"

from src.backend.main import app
from src.backend.config.env import get_settings
from src.backend.auth.schemas.auth_responses import UserResponse
from src.backend.testsuites.models.test_suite_model import TestSuiteStatus, TestSuitePriority
from src.backend.testsuites.schemas.test_suite_requests import (
    CreateTestSuiteRequest,
    UpdateTestSuiteRequest,
    BulkAddItemsRequest,
    BulkRemoveItemsRequest
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_db():
    """
    Test database fixture with isolated collections.
    
    Creates a test database connection, ensures clean state,
    and provides teardown after test session.
    """
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongodb_url)
    db = client.get_default_database()
    
    # Clean up any existing test data
    await db.test_suites.drop()
    await db.test_items.drop()
    await db.users.drop()
    
    yield db
    
    # Cleanup after tests
    await db.test_suites.drop()
    await db.test_items.drop()
    await db.users.drop()
    client.close()


@pytest_asyncio.fixture
async def test_app(test_db):
    """
    Test FastAPI application with test database.
    
    Configures the app with test database and returns
    the app instance for testing.
    """
    app.state.db = test_db
    yield app


@pytest_asyncio.fixture
async def async_client(test_app):
    """
    Async HTTP client for testing FastAPI endpoints.
    
    Provides an AsyncClient configured with the test app
    for making HTTP requests during tests.
    """
    async with AsyncClient(transport=httpx.ASGITransport(app=test_app), base_url="http://test") as client:
        yield client


@pytest.fixture
def test_user_data():
    """Test user data for authentication."""
    return {
        "id": str(ObjectId()),
        "email": "test@example.com",
        "username": "testuser",
        "full_name": "Test User",
        "is_active": True,
        "roles": ["user"]
    }


@pytest.fixture
def test_jwt_secret():
    """JWT secret key for token generation."""
    return get_settings().jwt_secret_key


@pytest.fixture
def generate_jwt_token(test_user_data, test_jwt_secret):
    """
    Factory function to generate JWT tokens for test users.
    
    Returns a function that can create JWT tokens with custom
    user data and expiration times for testing authentication.
    """
    def _generate_token(user_data: Optional[Dict] = None, expires_delta: Optional[timedelta] = None):
        user_info = user_data or test_user_data
        
        # Create payload with all required claims
        now = datetime.utcnow()
        if expires_delta:
            expire = now + expires_delta
        else:
            expire = now + timedelta(hours=1)
        
        payload = {
            "sub": user_info["id"],  # Required: subject (user ID)
            "email": user_info["email"],  # Required: user email
            "exp": expire,  # Required: expiration time
            "iat": now,  # Required: issued at time
            "username": user_info.get("username", "testuser"),
            "is_active": user_info.get("is_active", True)
        }
        
        return jwt.encode(payload, test_jwt_secret, algorithm="HS256")
    
    return _generate_token


@pytest_asyncio.fixture
async def authenticated_client(async_client, generate_jwt_token, test_user_data):
    """
    Authenticated async client with JWT token.
    
    Provides an AsyncClient with a valid JWT token in the
    Authorization header for testing protected endpoints.
    """
    token = generate_jwt_token()
    async_client.headers.update({"Authorization": f"Bearer {token}"})
    
    # Store user data for test access
    async_client.test_user = test_user_data
    
    yield async_client


@pytest_asyncio.fixture
async def test_items_setup(test_db, test_user_data):
    """
    Create test items in the database for test suite testing.
    
    Sets up a collection of test items that can be referenced
    in test suite creation and bulk operations.
    """
    test_items = []
    
    for i in range(5):
        item_doc = {
            "_id": ObjectId(),
            "title": f"Test Item {i+1}",
            "feature_id": f"feature_{i+1}",
            "scenario_id": f"scenario_{i+1}",
            "steps": {
                "type": "manual",
                "content": [f"Step 1 for test {i+1}", f"Step 2 for test {i+1}"],
                "step_count": 2
            },
            "selectors": {
                "primary": {"button": f"#btn-{i+1}"},
                "reliability_score": 0.9
            },
            "metadata": {
                "tags": [f"tag_{i+1}", "integration"],
                "auto_healing_enabled": True
            },
            "audit": {
                "created_by_user_id": test_user_data["id"],
                "created_at": datetime.utcnow(),
                "created_source": "manual"
            },
            "test_type": "generic",
            "type_data": {}
        }
        
        result = await test_db.test_items.insert_one(item_doc)
        item_doc["_id"] = result.inserted_id
        test_items.append(item_doc)
    
    yield test_items
    
    # Cleanup
    await test_db.test_items.delete_many({"audit.created_by_user_id": test_user_data["id"]})


@pytest.fixture
def sample_create_suite_request():
    """Sample test suite creation request data."""
    return CreateTestSuiteRequest(
        title="Integration Test Suite",
        description="Comprehensive integration test suite for testing",
        tags=["integration", "smoke"],
        priority=TestSuitePriority.HIGH,
        suite_items=[]
    )


@pytest.fixture
def sample_update_suite_request():
    """Sample test suite update request data."""
    return UpdateTestSuiteRequest(
        title="Updated Integration Test Suite",
        description="Updated comprehensive integration test suite",
        tags=["integration", "smoke", "regression"],
        priority=TestSuitePriority.MEDIUM,
        status=TestSuiteStatus.ACTIVE
    )


@pytest.fixture
def sample_bulk_add_request(test_items_setup):
    """
    Sample bulk add items request using test items.
    
    Creates a BulkAddItemsRequest with references to
    the test items created in test_items_setup.
    """
    async def _create_bulk_add_request(item_count: int = 3):
        items = []
        for i, test_item in enumerate(test_items_setup[:item_count]):
            items.append({
                "test_item_id": str(test_item["_id"]),
                "order": i + 1,
                "skip": False,
                "custom_tags": [f"bulk_{i+1}"],
                "note": f"Bulk added test item {i+1}"
            })
        
        return BulkAddItemsRequest(items=items)
    
    return _create_bulk_add_request


@pytest.fixture
def sample_bulk_remove_request():
    """Sample bulk remove items request data."""
    def _create_bulk_remove_request(test_item_ids: List[str]):
        return BulkRemoveItemsRequest(
            test_item_ids=test_item_ids,
            rebalance_order=True
        )
    
    return _create_bulk_remove_request


@pytest_asyncio.fixture
async def created_test_suite(test_db, test_user_data, test_items_setup):
    """
    Create a test suite in the database for testing operations.
    
    Creates a test suite with some test items for testing
    get, update, bulk operations, and delete endpoints.
    """
    suite_doc = {
        "_id": ObjectId(),
        "title": "Existing Test Suite",
        "description": "A test suite for testing operations",
        "tags": ["existing", "test"],
        "priority": "medium",
        "status": "draft",
        "owner_id": test_user_data["id"],
        "suite_items": [
            {
                "test_item_id": str(test_items_setup[0]["_id"]),
                "order": 1,
                "skip": False,
                "custom_tags": ["first"],
                "note": "First test item",
                "added_at": datetime.utcnow(),
                "added_by": test_user_data["id"]
            },
            {
                "test_item_id": str(test_items_setup[1]["_id"]),
                "order": 2,
                "skip": True,
                "custom_tags": ["second", "skip"],
                "note": "Second test item (skipped)",
                "added_at": datetime.utcnow(),
                "added_by": test_user_data["id"]
            }
        ],
        "total_items": 2,
        "active_items": 1,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "created_by": test_user_data["id"],
        "schema_version": "1.0",
        "metadata": {}
    }
    
    result = await test_db.test_suites.insert_one(suite_doc)
    suite_doc["_id"] = result.inserted_id
    
    yield suite_doc
    
    # Cleanup
    await test_db.test_suites.delete_one({"_id": suite_doc["_id"]})


@pytest.fixture
def assert_response_structure():
    """
    Utility function to assert API response structure.
    
    Provides a reusable function to validate that API responses
    follow the expected BaseResponse structure.
    """
    def _assert_structure(response_data: Dict[str, Any], success: bool = True):
        """Assert response has required BaseResponse structure."""
        assert "success" in response_data
        assert response_data["success"] is success
        assert "data" in response_data
        assert "message" in response_data
        assert "timestamp" in response_data
        
        if not success:
            assert response_data["data"] is None
        
        # Validate timestamp format
        timestamp = response_data["timestamp"]
        datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    
    return _assert_structure


@pytest.fixture
def assert_test_suite_structure():
    """
    Utility function to assert test suite data structure.
    
    Validates that test suite objects contain all required fields
    with proper types and constraints.
    """
    def _assert_suite_structure(suite_data: Dict[str, Any], include_items: bool = True):
        """Assert test suite data has required structure."""
        required_fields = [
            "id", "title", "description", "tags", "priority", "status",
            "owner_id", "total_items", "active_items", "created_at", "updated_at"
        ]
        
        for field in required_fields:
            assert field in suite_data, f"Missing required field: {field}"
        
        # Type validations
        assert isinstance(suite_data["tags"], list)
        assert isinstance(suite_data["total_items"], int)
        assert isinstance(suite_data["active_items"], int)
        assert suite_data["priority"] in ["high", "medium", "low"]
        assert suite_data["status"] in ["draft", "active", "archived"]
        
        if include_items:
            assert "suite_items" in suite_data
            assert isinstance(suite_data["suite_items"], list)
    
    return _assert_suite_structure


@pytest.fixture
def mock_service_dependencies():
    """
    Mock service dependencies for unit testing.
    
    Provides a way to mock service layer dependencies when testing
    controller or service logic in isolation.
    """
    class MockDependencies:
        def __init__(self):
            self.test_suite_service = None
            self.validation_service = None
            self.bulk_operation_service = None
            self.observability_service = None
    
    return MockDependencies() 
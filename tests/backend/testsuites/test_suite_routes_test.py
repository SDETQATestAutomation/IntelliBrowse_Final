"""
Test Suite Routes Integration Tests

Comprehensive end-to-end testing for test suite API endpoints including:
- Route-level testing via AsyncClient and test FastAPI app
- JWT authentication simulation with user context
- Complete CRUD operations testing (create, get, list, update, delete)
- Bulk operations testing (add/remove items)
- Error handling and validation testing
- Response structure and status code validation
- Performance and edge case testing

Tests all endpoints:
- POST /suites/ - Create test suite
- GET /suites/{suite_id} - Get test suite by ID
- GET /suites/ - List test suites with filtering and pagination
- PUT /suites/{suite_id} - Update test suite metadata
- PATCH /suites/{suite_id}/items/add - Bulk add items
- PATCH /suites/{suite_id}/items/remove - Bulk remove items
- DELETE /suites/{suite_id} - Soft delete test suite
- GET /suites/health - Service health check
"""

import pytest
import pytest_asyncio
from datetime import datetime
from typing import Dict, Any, List
from bson import ObjectId
from httpx import AsyncClient

from src.backend.testsuites.models.test_suite_model import TestSuiteStatus, TestSuitePriority


@pytest.mark.asyncio
class TestCreateTestSuiteRoute:
    """Test the POST /suites/ endpoint for creating test suites."""
    
    async def test_create_suite_success(
        self,
        authenticated_client: AsyncClient,
        sample_create_suite_request,
        assert_response_structure,
        assert_test_suite_structure
    ):
        """Test successful test suite creation."""
        # Arrange
        request_data = sample_create_suite_request.dict()
        
        # Act
        response = await authenticated_client.post("/api/v1/suites/", json=request_data)
        
        # Assert
        assert response.status_code == 201
        response_data = response.json()
        
        assert_response_structure(response_data, success=True)
        assert "Test suite created successfully" in response_data["message"]
        
        suite_data = response_data["data"]
        assert_test_suite_structure(suite_data, include_items=True)
        assert suite_data["title"] == request_data["title"]
        assert suite_data["description"] == request_data["description"]
        assert suite_data["priority"] == request_data["priority"]
        assert suite_data["status"] == "draft"  # Default status
        assert suite_data["total_items"] == 0  # No initial items
    
    async def test_create_suite_with_initial_items(
        self,
        authenticated_client: AsyncClient,
        test_items_setup,
        assert_response_structure,
        assert_test_suite_structure
    ):
        """Test creating suite with initial test items."""
        # Arrange
        request_data = {
            "title": "Suite with Initial Items",
            "description": "Test suite with pre-populated items",
            "tags": ["initial", "items"],
            "priority": "high",
            "suite_items": [
                {
                    "test_item_id": str(test_items_setup[0]["_id"]),
                    "order": 1,
                    "skip": False,
                    "custom_tags": ["first"],
                    "note": "First initial item"
                },
                {
                    "test_item_id": str(test_items_setup[1]["_id"]),
                    "order": 2,
                    "skip": True,
                    "custom_tags": ["second", "skip"],
                    "note": "Second initial item (skipped)"
                }
            ]
        }
        
        # Act
        response = await authenticated_client.post("/api/v1/suites/", json=request_data)
        
        # Assert
        assert response.status_code == 201
        response_data = response.json()
        
        assert_response_structure(response_data, success=True)
        suite_data = response_data["data"]
        assert_test_suite_structure(suite_data, include_items=True)
        
        assert suite_data["total_items"] == 2
        assert suite_data["active_items"] == 1  # One is skipped
        assert len(suite_data["suite_items"]) == 2
        
        # Verify item details
        item_1 = suite_data["suite_items"][0]
        assert item_1["test_item_id"] == str(test_items_setup[0]["_id"])
        assert item_1["order"] == 1
        assert item_1["skip"] is False
        assert item_1["custom_tags"] == ["first"]
        assert item_1["note"] == "First initial item"
    
    async def test_create_suite_invalid_test_items(
        self,
        authenticated_client: AsyncClient,
        assert_response_structure
    ):
        """Test creating suite with invalid test item references."""
        # Arrange
        request_data = {
            "title": "Suite with Invalid Items",
            "description": "Test suite with invalid item references",
            "suite_items": [
                {
                    "test_item_id": str(ObjectId()),  # Non-existent item
                    "order": 1,
                    "skip": False
                }
            ]
        }
        
        # Act
        response = await authenticated_client.post("/api/v1/suites/", json=request_data)
        
        # Assert
        assert response.status_code == 400
        response_data = response.json()
        
        assert_response_structure(response_data, success=False)
        assert "Invalid test item IDs" in response_data["message"]
    
    async def test_create_suite_duplicate_title(
        self,
        authenticated_client: AsyncClient,
        created_test_suite,
        assert_response_structure
    ):
        """Test creating suite with duplicate title."""
        # Arrange
        request_data = {
            "title": created_test_suite["title"],  # Same title as existing suite
            "description": "Duplicate title test"
        }
        
        # Act
        response = await authenticated_client.post("/api/v1/suites/", json=request_data)
        
        # Assert
        assert response.status_code == 409
        response_data = response.json()
        
        assert_response_structure(response_data, success=False)
        assert "already exists" in response_data["message"]
    
    async def test_create_suite_validation_errors(
        self,
        authenticated_client: AsyncClient,
        assert_response_structure
    ):
        """Test validation errors in suite creation."""
        # Test missing title
        response = await authenticated_client.post("/api/v1/suites/", json={})
        assert response.status_code == 422
        
        # Test empty title
        response = await authenticated_client.post("/api/v1/suites/", json={"title": ""})
        assert response.status_code == 422
        
        # Test invalid priority
        response = await authenticated_client.post("/api/v1/suites/", json={
            "title": "Test Suite",
            "priority": "invalid_priority"
        })
        assert response.status_code == 422
    
    async def test_create_suite_unauthorized(self, async_client: AsyncClient):
        """Test creating suite without authentication."""
        request_data = {"title": "Unauthorized Suite"}
        
        response = await async_client.post("/api/v1/suites/", json=request_data)
        assert response.status_code == 401


@pytest.mark.asyncio
class TestGetTestSuiteRoute:
    """Test the GET /suites/{suite_id} endpoint for retrieving test suites."""
    
    async def test_get_suite_success(
        self,
        authenticated_client: AsyncClient,
        created_test_suite,
        assert_response_structure,
        assert_test_suite_structure
    ):
        """Test successful test suite retrieval."""
        # Act
        response = await authenticated_client.get(f"/api/v1/suites/{created_test_suite['_id']}")
        
        # Assert
        assert response.status_code == 200
        response_data = response.json()
        
        assert_response_structure(response_data, success=True)
        suite_data = response_data["data"]
        assert_test_suite_structure(suite_data, include_items=True)
        
        assert suite_data["id"] == str(created_test_suite["_id"])
        assert suite_data["title"] == created_test_suite["title"]
        assert suite_data["total_items"] == 2
        assert len(suite_data["suite_items"]) == 2
    
    async def test_get_suite_not_found(
        self,
        authenticated_client: AsyncClient,
        assert_response_structure
    ):
        """Test retrieving non-existent test suite."""
        # Act
        response = await authenticated_client.get(f"/api/v1/suites/{ObjectId()}")
        
        # Assert
        assert response.status_code == 404
        response_data = response.json()
        
        assert_response_structure(response_data, success=False)
        assert "not found" in response_data["message"]
    
    async def test_get_suite_invalid_id(
        self,
        authenticated_client: AsyncClient
    ):
        """Test retrieving suite with invalid ID format."""
        # Act
        response = await authenticated_client.get("/api/v1/suites/invalid_id")
        
        # Assert
        assert response.status_code == 422  # Validation error
    
    async def test_get_suite_unauthorized(
        self,
        async_client: AsyncClient,
        created_test_suite
    ):
        """Test retrieving suite without authentication."""
        response = await async_client.get(f"/api/v1/suites/{created_test_suite['_id']}")
        assert response.status_code == 401


@pytest.mark.asyncio
class TestListTestSuitesRoute:
    """Test the GET /suites/ endpoint for listing test suites."""
    
    async def test_list_suites_success(
        self,
        authenticated_client: AsyncClient,
        created_test_suite,
        assert_response_structure
    ):
        """Test successful test suite listing."""
        # Act
        response = await authenticated_client.get("/api/v1/suites/")
        
        # Assert
        assert response.status_code == 200
        response_data = response.json()
        
        assert_response_structure(response_data, success=True)
        
        # Check pagination structure
        data = response_data["data"]
        assert "suites" in data
        assert "pagination" in data
        assert "filters" in data
        assert "sort" in data
        
        # Check suite list
        suites = data["suites"]
        assert isinstance(suites, list)
        assert len(suites) >= 1  # At least the created suite
        
        # Find our created suite
        our_suite = next((s for s in suites if s["id"] == str(created_test_suite["_id"])), None)
        assert our_suite is not None
        assert our_suite["title"] == created_test_suite["title"]
    
    async def test_list_suites_with_filters(
        self,
        authenticated_client: AsyncClient,
        created_test_suite,
        assert_response_structure
    ):
        """Test suite listing with various filters."""
        # Test status filter
        response = await authenticated_client.get("/api/v1/suites/?status=draft")
        assert response.status_code == 200
        response_data = response.json()
        assert_response_structure(response_data, success=True)
        
        # Test priority filter
        response = await authenticated_client.get("/api/v1/suites/?priority=medium")
        assert response.status_code == 200
        
        # Test tags filter
        response = await authenticated_client.get("/api/v1/suites/?tags=existing,test")
        assert response.status_code == 200
        
        # Test title search
        response = await authenticated_client.get("/api/v1/suites/?title_search=Existing")
        assert response.status_code == 200
        response_data = response.json()
        suites = response_data["data"]["suites"]
        assert len(suites) >= 1
        assert any("existing" in s["title"].lower() for s in suites)
    
    async def test_list_suites_pagination(
        self,
        authenticated_client: AsyncClient,
        assert_response_structure
    ):
        """Test suite listing pagination."""
        # Test pagination parameters
        response = await authenticated_client.get("/api/v1/suites/?page=1&page_size=5")
        assert response.status_code == 200
        response_data = response.json()
        
        assert_response_structure(response_data, success=True)
        
        pagination = response_data["data"]["pagination"]
        assert pagination["page"] == 1
        assert pagination["page_size"] == 5
        assert pagination["total_pages"] >= 1
        assert pagination["total_items"] >= 0
    
    async def test_list_suites_sorting(
        self,
        authenticated_client: AsyncClient,
        assert_response_structure
    ):
        """Test suite listing with sorting."""
        # Test sorting by different fields
        sort_options = [
            "created_at", "updated_at", "title", "priority", "total_items"
        ]
        
        for sort_field in sort_options:
            response = await authenticated_client.get(f"/api/v1/suites/?sort_by={sort_field}&sort_order=desc")
            assert response.status_code == 200
            
            response = await authenticated_client.get(f"/api/v1/suites/?sort_by={sort_field}&sort_order=asc")
            assert response.status_code == 200
    
    async def test_list_suites_validation_errors(
        self,
        authenticated_client: AsyncClient
    ):
        """Test validation errors in suite listing."""
        # Test invalid page
        response = await authenticated_client.get("/api/v1/suites/?page=0")
        assert response.status_code == 422
        
        # Test invalid page_size
        response = await authenticated_client.get("/api/v1/suites/?page_size=0")
        assert response.status_code == 422
        
        # Test page_size too large
        response = await authenticated_client.get("/api/v1/suites/?page_size=101")
        assert response.status_code == 422


@pytest.mark.asyncio
class TestUpdateTestSuiteRoute:
    """Test the PUT /suites/{suite_id} endpoint for updating test suites."""
    
    async def test_update_suite_success(
        self,
        authenticated_client: AsyncClient,
        created_test_suite,
        sample_update_suite_request,
        assert_response_structure,
        assert_test_suite_structure
    ):
        """Test successful test suite update."""
        # Arrange
        update_data = sample_update_suite_request.dict(exclude_unset=True)
        
        # Act
        response = await authenticated_client.put(
            f"/api/v1/suites/{created_test_suite['_id']}", 
            json=update_data
        )
        
        # Assert
        assert response.status_code == 200
        response_data = response.json()
        
        assert_response_structure(response_data, success=True)
        assert "updated successfully" in response_data["message"]
        
        suite_data = response_data["data"]
        assert_test_suite_structure(suite_data, include_items=True)
        assert suite_data["title"] == update_data["title"]
        assert suite_data["description"] == update_data["description"]
        assert suite_data["priority"] == update_data["priority"]
        assert suite_data["status"] == update_data["status"]
    
    async def test_update_suite_partial(
        self,
        authenticated_client: AsyncClient,
        created_test_suite,
        assert_response_structure
    ):
        """Test partial test suite update."""
        # Arrange - only update title
        update_data = {"title": "Partially Updated Suite"}
        
        # Act
        response = await authenticated_client.put(
            f"/api/v1/suites/{created_test_suite['_id']}", 
            json=update_data
        )
        
        # Assert
        assert response.status_code == 200
        response_data = response.json()
        
        assert_response_structure(response_data, success=True)
        suite_data = response_data["data"]
        assert suite_data["title"] == update_data["title"]
        # Other fields should remain unchanged
        assert suite_data["description"] == created_test_suite["description"]
    
    async def test_update_suite_not_found(
        self,
        authenticated_client: AsyncClient,
        sample_update_suite_request,
        assert_response_structure
    ):
        """Test updating non-existent test suite."""
        # Act
        response = await authenticated_client.put(
            f"/api/v1/suites/{ObjectId()}", 
            json=sample_update_suite_request.dict()
        )
        
        # Assert
        assert response.status_code == 404
        response_data = response.json()
        assert_response_structure(response_data, success=False)
    
    async def test_update_suite_duplicate_title(
        self,
        authenticated_client: AsyncClient,
        created_test_suite,
        test_db,
        test_user_data,
        assert_response_structure
    ):
        """Test updating suite with duplicate title."""
        # Create another suite
        another_suite = {
            "_id": ObjectId(),
            "title": "Another Suite",
            "description": "Another test suite",
            "tags": [],
            "priority": "low",
            "status": "draft",
            "owner_id": test_user_data["id"],
            "suite_items": [],
            "total_items": 0,
            "active_items": 0,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "created_by": test_user_data["id"],
            "schema_version": "1.0",
            "metadata": {}
        }
        await test_db.test_suites.insert_one(another_suite)
        
        try:
            # Try to update created_test_suite with another_suite's title
            update_data = {"title": another_suite["title"]}
            
            response = await authenticated_client.put(
                f"/api/v1/suites/{created_test_suite['_id']}", 
                json=update_data
            )
            
            assert response.status_code == 409
            response_data = response.json()
            assert_response_structure(response_data, success=False)
            assert "already exists" in response_data["message"]
        
        finally:
            # Cleanup
            await test_db.test_suites.delete_one({"_id": another_suite["_id"]})


@pytest.mark.asyncio
class TestBulkAddItemsRoute:
    """Test the PATCH /suites/{suite_id}/items/add endpoint for bulk adding items."""
    
    async def test_bulk_add_items_success(
        self,
        authenticated_client: AsyncClient,
        created_test_suite,
        test_items_setup,
        assert_response_structure
    ):
        """Test successful bulk add items operation."""
        # Arrange
        add_request = {
            "items": [
                {
                    "test_item_id": str(test_items_setup[2]["_id"]),
                    "order": 3,
                    "skip": False,
                    "custom_tags": ["bulk", "new"],
                    "note": "Bulk added item 1"
                },
                {
                    "test_item_id": str(test_items_setup[3]["_id"]),
                    "order": 4,
                    "skip": True,
                    "custom_tags": ["bulk", "skip"],
                    "note": "Bulk added item 2 (skipped)"
                }
            ]
        }
        
        # Act
        response = await authenticated_client.patch(
            f"/api/v1/suites/{created_test_suite['_id']}/items/add",
            json=add_request
        )
        
        # Assert
        assert response.status_code == 200
        response_data = response.json()
        
        assert_response_structure(response_data, success=True)
        assert "items added successfully" in response_data["message"]
        
        result = response_data["data"]
        assert result["success_count"] == 2
        assert result["invalid_count"] == 0
        assert result["duplicate_count"] == 0
        assert len(result["successful_items"]) == 2
    
    async def test_bulk_add_items_duplicates(
        self,
        authenticated_client: AsyncClient,
        created_test_suite,
        test_items_setup,
        assert_response_structure
    ):
        """Test bulk add with duplicate items."""
        # Arrange - try to add an item that's already in the suite
        add_request = {
            "items": [
                {
                    "test_item_id": str(test_items_setup[0]["_id"]),  # Already in suite
                    "order": 5,
                    "skip": False
                },
                {
                    "test_item_id": str(test_items_setup[2]["_id"]),  # New item
                    "order": 6,
                    "skip": False
                }
            ]
        }
        
        # Act
        response = await authenticated_client.patch(
            f"/api/v1/suites/{created_test_suite['_id']}/items/add",
            json=add_request
        )
        
        # Assert
        assert response.status_code == 200
        response_data = response.json()
        
        assert_response_structure(response_data, success=True)
        result = response_data["data"]
        
        # Should have 1 success and 1 duplicate
        assert result["success_count"] == 1
        assert result["duplicate_count"] == 1
        assert len(result["successful_items"]) == 1
        assert len(result["duplicate_items"]) == 1
    
    async def test_bulk_add_items_invalid_references(
        self,
        authenticated_client: AsyncClient,
        created_test_suite,
        assert_response_structure
    ):
        """Test bulk add with invalid item references."""
        # Arrange
        add_request = {
            "items": [
                {
                    "test_item_id": str(ObjectId()),  # Non-existent item
                    "order": 5,
                    "skip": False
                }
            ]
        }
        
        # Act
        response = await authenticated_client.patch(
            f"/api/v1/suites/{created_test_suite['_id']}/items/add",
            json=add_request
        )
        
        # Assert
        assert response.status_code == 200
        response_data = response.json()
        
        assert_response_structure(response_data, success=True)
        result = response_data["data"]
        
        assert result["success_count"] == 0
        assert result["invalid_count"] == 1
        assert len(result["invalid_items"]) == 1
    
    async def test_bulk_add_items_too_many(
        self,
        authenticated_client: AsyncClient,
        created_test_suite,
        test_items_setup,
        assert_response_structure
    ):
        """Test bulk add with too many items (over limit)."""
        # Arrange - create request with over 100 items
        items = []
        for i in range(101):
            items.append({
                "test_item_id": str(test_items_setup[0]["_id"]),
                "order": i + 10,
                "skip": False
            })
        
        add_request = {"items": items}
        
        # Act
        response = await authenticated_client.patch(
            f"/api/v1/suites/{created_test_suite['_id']}/items/add",
            json=add_request
        )
        
        # Assert
        assert response.status_code == 400
        response_data = response.json()
        
        assert_response_structure(response_data, success=False)
        assert "limited to 100 items" in response_data["message"]


@pytest.mark.asyncio
class TestBulkRemoveItemsRoute:
    """Test the PATCH /suites/{suite_id}/items/remove endpoint for bulk removing items."""
    
    async def test_bulk_remove_items_success(
        self,
        authenticated_client: AsyncClient,
        created_test_suite,
        test_items_setup,
        assert_response_structure
    ):
        """Test successful bulk remove items operation."""
        # Arrange
        remove_request = {
            "test_item_ids": [str(test_items_setup[0]["_id"])],
            "rebalance_order": True
        }
        
        # Act
        response = await authenticated_client.patch(
            f"/api/v1/suites/{created_test_suite['_id']}/items/remove",
            json=remove_request
        )
        
        # Assert
        assert response.status_code == 200
        response_data = response.json()
        
        assert_response_structure(response_data, success=True)
        assert "items removed successfully" in response_data["message"]
        
        result = response_data["data"]
        assert result["success_count"] == 1
        assert result["not_found_count"] == 0
        assert len(result["successful_items"]) == 1
    
    async def test_bulk_remove_items_not_found(
        self,
        authenticated_client: AsyncClient,
        created_test_suite,
        assert_response_structure
    ):
        """Test bulk remove with items not in suite."""
        # Arrange
        remove_request = {
            "test_item_ids": [str(ObjectId())],  # Not in suite
            "rebalance_order": False
        }
        
        # Act
        response = await authenticated_client.patch(
            f"/api/v1/suites/{created_test_suite['_id']}/items/remove",
            json=remove_request
        )
        
        # Assert
        assert response.status_code == 200
        response_data = response.json()
        
        assert_response_structure(response_data, success=True)
        result = response_data["data"]
        
        assert result["success_count"] == 0
        assert result["not_found_count"] == 1
        assert len(result["not_found_items"]) == 1


@pytest.mark.asyncio
class TestDeleteTestSuiteRoute:
    """Test the DELETE /suites/{suite_id} endpoint for soft deleting test suites."""
    
    async def test_delete_suite_success(
        self,
        authenticated_client: AsyncClient,
        created_test_suite,
        assert_response_structure
    ):
        """Test successful test suite deletion (soft delete)."""
        # Act
        response = await authenticated_client.delete(f"/api/v1/suites/{created_test_suite['_id']}")
        
        # Assert
        assert response.status_code == 200
        response_data = response.json()
        
        assert_response_structure(response_data, success=True)
        assert "archived successfully" in response_data["message"]
        
        delete_data = response_data["data"]
        assert delete_data["suite_id"] == str(created_test_suite["_id"])
        assert delete_data["previous_status"] == "draft"
        assert delete_data["new_status"] == "archived"
        assert "archived_at" in delete_data
    
    async def test_delete_suite_not_found(
        self,
        authenticated_client: AsyncClient,
        assert_response_structure
    ):
        """Test deleting non-existent test suite."""
        # Act
        response = await authenticated_client.delete(f"/api/v1/suites/{ObjectId()}")
        
        # Assert
        assert response.status_code == 404
        response_data = response.json()
        assert_response_structure(response_data, success=False)


@pytest.mark.asyncio
class TestTestSuiteHealthRoute:
    """Test the GET /suites/health endpoint for service health checks."""
    
    async def test_health_check_success(
        self,
        authenticated_client: AsyncClient
    ):
        """Test successful health check."""
        # Act
        response = await authenticated_client.get("/api/v1/suites/health")
        
        # Assert
        assert response.status_code == 200
        health_data = response.json()
        
        # Basic health check structure
        assert "status" in health_data
        assert health_data["status"] in ["healthy", "degraded", "unhealthy"]
        
        if "database" in health_data:
            assert "connected" in health_data["database"]
            assert isinstance(health_data["database"]["connected"], bool)


@pytest.mark.asyncio
class TestRouteAuthentication:
    """Test authentication requirements for all routes."""
    
    async def test_all_routes_require_authentication(self, async_client: AsyncClient):
        """Test that all routes except health require authentication."""
        protected_routes = [
            ("POST", "/api/v1/suites/", {"title": "Test"}),
            ("GET", f"/api/v1/suites/{ObjectId()}", None),
            ("GET", "/api/v1/suites/", None),
            ("PUT", f"/api/v1/suites/{ObjectId()}", {"title": "Updated"}),
            ("PATCH", f"/api/v1/suites/{ObjectId()}/items/add", {"items": []}),
            ("PATCH", f"/api/v1/suites/{ObjectId()}/items/remove", {"test_item_ids": []}),
            ("DELETE", f"/api/v1/suites/{ObjectId()}", None),
        ]
        
        for method, url, data in protected_routes:
            if method == "GET":
                response = await async_client.get(url)
            elif method == "POST":
                response = await async_client.post(url, json=data)
            elif method == "PUT":
                response = await async_client.put(url, json=data)
            elif method == "PATCH":
                response = await async_client.patch(url, json=data)
            elif method == "DELETE":
                response = await async_client.delete(url)
            
            assert response.status_code == 401, f"Route {method} {url} should require authentication"


@pytest.mark.asyncio
class TestRouteErrorHandling:
    """Test error handling and edge cases for all routes."""
    
    async def test_malformed_json_requests(
        self,
        authenticated_client: AsyncClient
    ):
        """Test handling of malformed JSON in requests."""
        # Test with invalid JSON content-type but valid data
        response = await authenticated_client.post(
            "/api/v1/suites/",
            content='{"title": "Test Suite"}',
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code in [200, 201, 422]  # Should handle gracefully
    
    async def test_large_request_payloads(
        self,
        authenticated_client: AsyncClient
    ):
        """Test handling of unusually large request payloads."""
        # Create a request with very large description
        large_description = "x" * 10000  # 10KB description
        
        request_data = {
            "title": "Large Payload Test",
            "description": large_description,
            "tags": ["large"] * 100  # Many tags
        }
        
        response = await authenticated_client.post("/api/v1/suites/", json=request_data)
        
        # Should either succeed or fail gracefully with validation error
        assert response.status_code in [201, 422, 413]  # Success, validation error, or payload too large 
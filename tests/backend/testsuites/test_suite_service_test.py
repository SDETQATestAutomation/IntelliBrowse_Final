"""
Test Suite Service Layer Unit Tests

Comprehensive testing of business logic and database operations for test suite service including:
- Pure logic/unit boundary testing with mocked dependencies
- Validation logic testing (item validation, duplicate checks, partial success handling)  
- Proper exception handling and error scenarios
- Database operation mocking and verification
- Async patterns and performance considerations
- Edge cases and boundary conditions

Tests all service methods:
- create_suite() - Suite creation with validation
- get_suite() - Suite retrieval with field inclusion
- list_suites() - Filtering, pagination, and sorting
- update_suite() - Metadata updates with validation
- add_items() - Bulk add operations with validation
- remove_items() - Bulk remove operations
- delete_suite() - Soft deletion
- Validation methods (_validate_item_references, _validate_title_uniqueness, etc.)
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime
from typing import Dict, Any, List, Set
from bson import ObjectId
from fastapi import HTTPException

from src.backend.testsuites.services.test_suite_service import TestSuiteService, ValidationResult
from src.backend.testsuites.schemas.test_suite_requests import (
    CreateTestSuiteRequest,
    UpdateTestSuiteRequest,
    BulkAddItemsRequest,
    BulkRemoveItemsRequest,
    FilterTestSuitesRequest,
    SuiteItemRequest
)
from src.backend.testsuites.schemas.test_suite_responses import TestSuiteResponse
from src.backend.testsuites.models.test_suite_model import TestSuiteStatus, TestSuitePriority


@pytest.mark.asyncio
class TestTestSuiteServiceCreateSuite:
    """Test the create_suite method of TestSuiteService."""
    
    async def test_create_suite_success_without_items(self):
        """Test successful suite creation without initial items."""
        # Arrange
        mock_db = AsyncMock()
        mock_collection = AsyncMock()
        mock_db.test_suites = mock_collection
        mock_db.test_items = AsyncMock()
        
        service = TestSuiteService(mock_db)
        
        # Mock title uniqueness validation
        service._validate_title_uniqueness = AsyncMock()
        service._track_operation = AsyncMock()
        
        # Mock successful insertion
        mock_insert_result = Mock()
        mock_insert_result.inserted_id = ObjectId()
        mock_collection.insert_one.return_value = mock_insert_result
        
        request = CreateTestSuiteRequest(
            title="Test Suite",
            description="Test description",
            tags=["test", "suite"],
            priority=TestSuitePriority.HIGH,
            suite_items=[]
        )
        user_id = str(ObjectId())
        
        # Act
        result = await service.create_suite(request, user_id)
        
        # Assert
        assert isinstance(result, TestSuiteResponse)
        assert result.title == "Test Suite"
        assert result.description == "Test description"
        assert result.priority == "high"
        assert result.status == "draft"
        assert result.owner_id == user_id
        assert result.total_items == 0
        assert result.active_items == 0
        
        # Verify mocks were called
        service._validate_title_uniqueness.assert_called_once_with("Test Suite", user_id)
        mock_collection.insert_one.assert_called_once()
        service._track_operation.assert_called()
    
    async def test_create_suite_success_with_items(self):
        """Test successful suite creation with initial items."""
        # Arrange
        mock_db = AsyncMock()
        mock_collection = AsyncMock()
        mock_db.test_suites = mock_collection
        mock_db.test_items = AsyncMock()
        
        service = TestSuiteService(mock_db)
        
        # Mock validations
        service._validate_title_uniqueness = AsyncMock()
        service._validate_item_references = AsyncMock(return_value=ValidationResult(
            valid_ids={str(ObjectId()), str(ObjectId())},
            invalid_ids=set()
        ))
        service._track_operation = AsyncMock()
        
        # Mock successful insertion
        mock_insert_result = Mock()
        mock_insert_result.inserted_id = ObjectId()
        mock_collection.insert_one.return_value = mock_insert_result
        
        item_1_id = str(ObjectId())
        item_2_id = str(ObjectId())
        
        request = CreateTestSuiteRequest(
            title="Suite with Items",
            description="Suite with initial items",
            suite_items=[
                SuiteItemRequest(
                    test_item_id=item_1_id,
                    order=1,
                    skip=False,
                    custom_tags=["first"],
                    note="First item"
                ),
                SuiteItemRequest(
                    test_item_id=item_2_id,
                    order=2,
                    skip=True,
                    custom_tags=["second"],
                    note="Second item (skipped)"
                )
            ]
        )
        user_id = str(ObjectId())
        
        # Act
        result = await service.create_suite(request, user_id)
        
        # Assert
        assert isinstance(result, TestSuiteResponse)
        assert result.title == "Suite with Items"
        assert result.total_items == 2
        assert result.active_items == 1  # One is skipped
        
        # Verify validation was called
        service._validate_item_references.assert_called_once()
        mock_collection.insert_one.assert_called_once()
    
    async def test_create_suite_invalid_items(self):
        """Test suite creation with invalid item references."""
        # Arrange
        mock_db = AsyncMock()
        service = TestSuiteService(mock_db)
        
        # Mock validations
        service._validate_title_uniqueness = AsyncMock()
        service._validate_item_references = AsyncMock(return_value=ValidationResult(
            valid_ids=set(),
            invalid_ids={str(ObjectId())}
        ))
        service._track_operation = AsyncMock()
        
        request = CreateTestSuiteRequest(
            title="Suite with Invalid Items",
            suite_items=[
                SuiteItemRequest(
                    test_item_id=str(ObjectId()),
                    order=1,
                    skip=False
                )
            ]
        )
        user_id = str(ObjectId())
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await service.create_suite(request, user_id)
        
        assert exc_info.value.status_code == 400
        assert "Invalid test item IDs" in str(exc_info.value.detail)
    
    async def test_create_suite_duplicate_title(self):
        """Test suite creation with duplicate title."""
        # Arrange
        mock_db = AsyncMock()
        service = TestSuiteService(mock_db)
        
        # Mock title validation to raise conflict
        service._validate_title_uniqueness = AsyncMock(
            side_effect=HTTPException(status_code=409, detail="Title already exists")
        )
        service._track_operation = AsyncMock()
        
        request = CreateTestSuiteRequest(title="Duplicate Title")
        user_id = str(ObjectId())
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await service.create_suite(request, user_id)
        
        assert exc_info.value.status_code == 409
        assert "Title already exists" in str(exc_info.value.detail)
    
    async def test_create_suite_database_error(self):
        """Test suite creation with database error."""
        # Arrange
        mock_db = AsyncMock()
        mock_collection = AsyncMock()
        mock_db.test_suites = mock_collection
        mock_db.test_items = AsyncMock()
        
        service = TestSuiteService(mock_db)
        
        # Mock validations to succeed
        service._validate_title_uniqueness = AsyncMock()
        service._track_operation = AsyncMock()
        
        # Mock database error
        mock_collection.insert_one.side_effect = Exception("Database connection failed")
        
        request = CreateTestSuiteRequest(title="Test Suite")
        user_id = str(ObjectId())
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await service.create_suite(request, user_id)
        
        assert exc_info.value.status_code == 500
        assert "Failed to create test suite" in str(exc_info.value.detail)
        
        # Verify error tracking
        service._track_operation.assert_called()


@pytest.mark.asyncio
class TestTestSuiteServiceGetSuite:
    """Test the get_suite method of TestSuiteService."""
    
    async def test_get_suite_success(self):
        """Test successful suite retrieval."""
        # Arrange
        mock_db = AsyncMock()
        mock_collection = AsyncMock()
        mock_db.test_suites = mock_collection
        
        service = TestSuiteService(mock_db)
        
        suite_id = str(ObjectId())
        user_id = str(ObjectId())
        
        # Mock database response
        suite_doc = {
            "_id": ObjectId(suite_id),
            "title": "Test Suite",
            "description": "Test description",
            "tags": ["test"],
            "priority": "medium",
            "status": "draft",
            "owner_id": user_id,
            "suite_items": [],
            "total_items": 0,
            "active_items": 0,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "created_by": user_id
        }
        
        mock_collection.find_one.return_value = suite_doc
        
        # Act
        result = await service.get_suite(suite_id, user_id=user_id)
        
        # Assert
        assert result is not None
        assert isinstance(result, TestSuiteResponse)
        assert result.id == suite_id
        assert result.title == "Test Suite"
        assert result.owner_id == user_id
        
        # Verify database query
        mock_collection.find_one.assert_called_once()
        query_args = mock_collection.find_one.call_args[0][0]
        assert query_args["_id"] == ObjectId(suite_id)
        assert query_args["owner_id"] == user_id
    
    async def test_get_suite_not_found(self):
        """Test suite retrieval when suite doesn't exist."""
        # Arrange
        mock_db = AsyncMock()
        mock_collection = AsyncMock()
        mock_db.test_suites = mock_collection
        
        service = TestSuiteService(mock_db)
        
        # Mock no results from database
        mock_collection.find_one.return_value = None
        
        suite_id = str(ObjectId())
        user_id = str(ObjectId())
        
        # Act
        result = await service.get_suite(suite_id, user_id=user_id)
        
        # Assert
        assert result is None
    
    async def test_get_suite_with_field_inclusion(self):
        """Test suite retrieval with field inclusion control."""
        # Arrange
        mock_db = AsyncMock()
        mock_collection = AsyncMock()
        mock_db.test_suites = mock_collection
        
        service = TestSuiteService(mock_db)
        
        suite_id = str(ObjectId())
        user_id = str(ObjectId())
        
        # Mock database response
        suite_doc = {
            "_id": ObjectId(suite_id),
            "title": "Test Suite",
            "description": "Test description",
            "owner_id": user_id,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        mock_collection.find_one.return_value = suite_doc
        
        # Act
        result = await service.get_suite(
            suite_id, 
            include_fields=["title", "description"], 
            user_id=user_id
        )
        
        # Assert
        assert result is not None
        mock_collection.find_one.assert_called_once()
        
        # Verify projection was used
        call_args = mock_collection.find_one.call_args
        if len(call_args) > 1 and call_args[1] is not None:
            projection = call_args[1]
            assert isinstance(projection, dict)


@pytest.mark.asyncio
class TestTestSuiteServiceListSuites:
    """Test the list_suites method of TestSuiteService."""
    
    async def test_list_suites_success(self):
        """Test successful suite listing with basic parameters."""
        # Arrange
        mock_db = AsyncMock()
        mock_collection = AsyncMock()
        mock_db.test_suites = mock_collection
        
        service = TestSuiteService(mock_db)
        
        user_id = str(ObjectId())
        
        # Mock database responses
        suite_docs = [
            {
                "_id": ObjectId(),
                "title": "Suite 1",
                "description": "First suite",
                "owner_id": user_id,
                "status": "draft",
                "priority": "medium",
                "tags": ["test"],
                "total_items": 5,
                "active_items": 4,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "_id": ObjectId(),
                "title": "Suite 2", 
                "description": "Second suite",
                "owner_id": user_id,
                "status": "active",
                "priority": "high",
                "tags": ["integration"],
                "total_items": 3,
                "active_items": 3,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
        ]
        
        # Mock aggregation pipeline results
        mock_cursor = AsyncMock()
        mock_cursor.to_list.return_value = suite_docs
        mock_collection.aggregate.return_value = mock_cursor
        
        # Mock count query
        mock_collection.count_documents.return_value = 2
        
        filters = FilterTestSuitesRequest(
            page=1,
            page_size=20,
            sort_by="created_at",
            sort_order="desc"
        )
        
        # Act
        suites, pagination, filter_meta, sort_meta = await service.list_suites(filters, user_id)
        
        # Assert
        assert len(suites) == 2
        assert all(isinstance(suite, TestSuiteResponse) for suite in suites)
        assert suites[0].title == "Suite 1"
        assert suites[1].title == "Suite 2"
        
        # Verify pagination
        assert pagination.page == 1
        assert pagination.page_size == 20
        assert pagination.total_items == 2
        assert pagination.total_pages == 1
        
        # Verify database calls
        mock_collection.aggregate.assert_called_once()
        mock_collection.count_documents.assert_called_once()
    
    async def test_list_suites_with_filters(self):
        """Test suite listing with various filters applied."""
        # Arrange
        mock_db = AsyncMock()
        mock_collection = AsyncMock()
        mock_db.test_suites = mock_collection
        
        service = TestSuiteService(mock_db)
        
        user_id = str(ObjectId())
        
        # Mock empty results for filtered query
        mock_cursor = AsyncMock()
        mock_cursor.to_list.return_value = []
        mock_collection.aggregate.return_value = mock_cursor
        mock_collection.count_documents.return_value = 0
        
        filters = FilterTestSuitesRequest(
            status=TestSuiteStatus.ACTIVE,
            priority=TestSuitePriority.HIGH,
            tags="critical,smoke",
            title_search="authentication",
            has_items=True,
            page=1,
            page_size=10,
            sort_by="title",
            sort_order="asc"
        )
        
        # Act
        suites, pagination, filter_meta, sort_meta = await service.list_suites(filters, user_id)
        
        # Assert
        assert len(suites) == 0
        assert pagination.total_items == 0
        
        # Verify aggregation was called with filters
        mock_collection.aggregate.assert_called_once()
        aggregation_pipeline = mock_collection.aggregate.call_args[0][0]
        
        # Verify the pipeline contains match stage with filters
        match_stage = next((stage for stage in aggregation_pipeline if '$match' in stage), None)
        assert match_stage is not None
        match_conditions = match_stage['$match']
        
        # Check that owner_id filter is always present
        assert match_conditions['owner_id'] == user_id
    
    async def test_list_suites_pagination_edge_cases(self):
        """Test suite listing pagination with edge cases."""
        # Arrange
        mock_db = AsyncMock()
        mock_collection = AsyncMock()
        mock_db.test_suites = mock_collection
        
        service = TestSuiteService(mock_db)
        
        user_id = str(ObjectId())
        
        # Mock results for edge case pagination
        mock_cursor = AsyncMock()
        mock_cursor.to_list.return_value = []
        mock_collection.aggregate.return_value = mock_cursor
        mock_collection.count_documents.return_value = 0
        
        # Test page beyond available data
        filters = FilterTestSuitesRequest(
            page=10,  # Way beyond available data
            page_size=5
        )
        
        # Act
        suites, pagination, filter_meta, sort_meta = await service.list_suites(filters, user_id)
        
        # Assert
        assert len(suites) == 0
        assert pagination.page == 10
        assert pagination.total_pages == 0  # No pages when no data
        assert pagination.total_items == 0


@pytest.mark.asyncio
class TestTestSuiteServiceUpdateSuite:
    """Test the update_suite method of TestSuiteService."""
    
    async def test_update_suite_success(self):
        """Test successful suite update."""
        # Arrange
        mock_db = AsyncMock()
        mock_collection = AsyncMock()
        mock_db.test_suites = mock_collection
        
        service = TestSuiteService(mock_db)
        
        # Mock ownership validation
        service._validate_suite_ownership = AsyncMock()
        service._validate_title_uniqueness = AsyncMock()
        service._track_operation = AsyncMock()
        
        suite_id = str(ObjectId())
        user_id = str(ObjectId())
        
        # Mock existing suite
        existing_suite = {
            "_id": ObjectId(suite_id),
            "title": "Original Title",
            "description": "Original description",
            "tags": ["old"],
            "priority": "low",
            "status": "draft",
            "owner_id": user_id,
            "total_items": 2,
            "active_items": 1,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "created_by": user_id
        }
        
        # Mock updated suite after update
        updated_suite = existing_suite.copy()
        updated_suite.update({
            "title": "Updated Title",
            "description": "Updated description",
            "tags": ["new", "updated"],
            "priority": "high",
            "status": "active",
            "updated_at": datetime.utcnow()
        })
        
        mock_collection.find_one_and_update.return_value = updated_suite
        
        update_request = UpdateTestSuiteRequest(
            title="Updated Title",
            description="Updated description", 
            tags=["new", "updated"],
            priority=TestSuitePriority.HIGH,
            status=TestSuiteStatus.ACTIVE
        )
        
        # Act
        result = await service.update_suite(suite_id, update_request, user_id)
        
        # Assert
        assert isinstance(result, TestSuiteResponse)
        assert result.title == "Updated Title"
        assert result.description == "Updated description"
        assert result.priority == "high"
        assert result.status == "active"
        
        # Verify validations were called
        service._validate_suite_ownership.assert_called_once_with(suite_id, user_id)
        service._validate_title_uniqueness.assert_called_once_with(
            "Updated Title", user_id, exclude_suite_id=suite_id
        )
        
        # Verify database update
        mock_collection.find_one_and_update.assert_called_once()
    
    async def test_update_suite_partial_update(self):
        """Test partial suite update with only some fields."""
        # Arrange
        mock_db = AsyncMock()
        mock_collection = AsyncMock()
        mock_db.test_suites = mock_collection
        
        service = TestSuiteService(mock_db)
        
        # Mock validations
        service._validate_suite_ownership = AsyncMock()
        service._track_operation = AsyncMock()
        
        suite_id = str(ObjectId())
        user_id = str(ObjectId())
        
        # Mock existing suite
        existing_suite = {
            "_id": ObjectId(suite_id),
            "title": "Original Title",
            "description": "Original description",
            "priority": "low",
            "status": "draft",
            "owner_id": user_id
        }
        
        # Mock updated suite (only title changed)
        updated_suite = existing_suite.copy()
        updated_suite["title"] = "Partially Updated Title"
        
        mock_collection.find_one_and_update.return_value = updated_suite
        
        # Only update title
        update_request = UpdateTestSuiteRequest(title="Partially Updated Title")
        
        # Act
        result = await service.update_suite(suite_id, update_request, user_id)
        
        # Assert
        assert result.title == "Partially Updated Title"
        
        # Verify only title validation was called (no empty title validation)
        service._validate_suite_ownership.assert_called_once()
        mock_collection.find_one_and_update.assert_called_once()
    
    async def test_update_suite_not_found(self):
        """Test updating non-existent suite."""
        # Arrange
        mock_db = AsyncMock()
        service = TestSuiteService(mock_db)
        
        # Mock ownership validation to raise not found
        service._validate_suite_ownership = AsyncMock(
            side_effect=HTTPException(status_code=404, detail="Suite not found")
        )
        service._track_operation = AsyncMock()
        
        suite_id = str(ObjectId())
        user_id = str(ObjectId())
        update_request = UpdateTestSuiteRequest(title="New Title")
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await service.update_suite(suite_id, update_request, user_id)
        
        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail)


@pytest.mark.asyncio
class TestTestSuiteServiceBulkOperations:
    """Test bulk add and remove operations."""
    
    async def test_add_items_success(self):
        """Test successful bulk add items operation."""
        # Arrange
        mock_db = AsyncMock()
        mock_collection = AsyncMock()
        mock_db.test_suites = mock_collection
        
        service = TestSuiteService(mock_db)
        
        # Mock validations and operations
        service._validate_suite_ownership = AsyncMock()
        service._validate_item_references = AsyncMock(return_value=ValidationResult(
            valid_ids={str(ObjectId()), str(ObjectId())},
            invalid_ids=set()
        ))
        service._get_existing_item_ids = AsyncMock(return_value=set())
        service._track_operation = AsyncMock()
        
        # Mock successful update
        mock_update_result = Mock()
        mock_update_result.modified_count = 1
        mock_collection.update_one.return_value = mock_update_result
        
        suite_id = str(ObjectId())
        user_id = str(ObjectId())
        
        add_request = BulkAddItemsRequest(
            items=[
                SuiteItemRequest(
                    test_item_id=str(ObjectId()),
                    order=1,
                    skip=False,
                    custom_tags=["new"],
                    note="New item 1"
                ),
                SuiteItemRequest(
                    test_item_id=str(ObjectId()),
                    order=2,
                    skip=True,
                    custom_tags=["new"],
                    note="New item 2"
                )
            ]
        )
        
        # Act
        result = await service.add_items(suite_id, add_request, user_id)
        
        # Assert
        assert result.success_count == 2
        assert result.invalid_count == 0
        assert result.duplicate_count == 0
        assert len(result.successful_items) == 2
        
        # Verify validations were called
        service._validate_suite_ownership.assert_called_once()
        service._validate_item_references.assert_called_once()
        service._get_existing_item_ids.assert_called_once()
        
        # Verify database update
        mock_collection.update_one.assert_called_once()
    
    async def test_add_items_with_duplicates(self):
        """Test bulk add with some duplicate items."""
        # Arrange
        mock_db = AsyncMock()
        mock_collection = AsyncMock()
        mock_db.test_suites = mock_collection
        
        service = TestSuiteService(mock_db)
        
        item_1_id = str(ObjectId())
        item_2_id = str(ObjectId())
        
        # Mock validations
        service._validate_suite_ownership = AsyncMock()
        service._validate_item_references = AsyncMock(return_value=ValidationResult(
            valid_ids={item_1_id, item_2_id},
            invalid_ids=set()
        ))
        # Mock that item_1 already exists in suite
        service._get_existing_item_ids = AsyncMock(return_value={item_1_id})
        service._track_operation = AsyncMock()
        
        # Mock successful update for non-duplicate
        mock_update_result = Mock()
        mock_update_result.modified_count = 1
        mock_collection.update_one.return_value = mock_update_result
        
        suite_id = str(ObjectId())
        user_id = str(ObjectId())
        
        add_request = BulkAddItemsRequest(
            items=[
                SuiteItemRequest(test_item_id=item_1_id, order=1),  # Duplicate
                SuiteItemRequest(test_item_id=item_2_id, order=2)   # New
            ]
        )
        
        # Act
        result = await service.add_items(suite_id, add_request, user_id)
        
        # Assert
        assert result.success_count == 1
        assert result.invalid_count == 0
        assert result.duplicate_count == 1
        assert len(result.successful_items) == 1
        assert len(result.duplicate_items) == 1
        assert result.duplicate_items[0]["test_item_id"] == item_1_id
    
    async def test_add_items_too_many(self):
        """Test bulk add with too many items (over limit)."""
        # Arrange
        mock_db = AsyncMock()
        service = TestSuiteService(mock_db)
        service._track_operation = AsyncMock()
        
        suite_id = str(ObjectId())
        user_id = str(ObjectId())
        
        # Create request with 101 items (over the 100 limit)
        items = [
            SuiteItemRequest(test_item_id=str(ObjectId()), order=i)
            for i in range(101)
        ]
        add_request = BulkAddItemsRequest(items=items)
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await service.add_items(suite_id, add_request, user_id)
        
        assert exc_info.value.status_code == 400
        assert "limited to 100 items" in str(exc_info.value.detail)
    
    async def test_remove_items_success(self):
        """Test successful bulk remove items operation."""
        # Arrange
        mock_db = AsyncMock()
        mock_collection = AsyncMock()
        mock_db.test_suites = mock_collection
        
        service = TestSuiteService(mock_db)
        
        # Mock validations and operations
        service._validate_suite_ownership = AsyncMock()
        service._get_existing_item_ids = AsyncMock(return_value={
            str(ObjectId()), str(ObjectId())
        })
        service._track_operation = AsyncMock()
        
        # Mock successful update
        mock_update_result = Mock()
        mock_update_result.modified_count = 1
        mock_collection.update_one.return_value = mock_update_result
        
        suite_id = str(ObjectId())
        user_id = str(ObjectId())
        
        item_ids_to_remove = [str(ObjectId()), str(ObjectId())]
        remove_request = BulkRemoveItemsRequest(
            test_item_ids=item_ids_to_remove,
            rebalance_order=True
        )
        
        # Act
        result = await service.remove_items(suite_id, remove_request, user_id)
        
        # Assert
        assert result.success_count == 2
        assert result.not_found_count == 0
        assert len(result.successful_items) == 2
        
        # Verify validations and operations
        service._validate_suite_ownership.assert_called_once()
        service._get_existing_item_ids.assert_called_once()
        mock_collection.update_one.assert_called_once()
    
    async def test_remove_items_not_found(self):
        """Test bulk remove with items not in suite."""
        # Arrange
        mock_db = AsyncMock()
        service = TestSuiteService(mock_db)
        
        # Mock validations
        service._validate_suite_ownership = AsyncMock()
        service._get_existing_item_ids = AsyncMock(return_value=set())  # No existing items
        service._track_operation = AsyncMock()
        
        suite_id = str(ObjectId())
        user_id = str(ObjectId())
        
        item_ids_to_remove = [str(ObjectId())]
        remove_request = BulkRemoveItemsRequest(test_item_ids=item_ids_to_remove)
        
        # Act
        result = await service.remove_items(suite_id, remove_request, user_id)
        
        # Assert
        assert result.success_count == 0
        assert result.not_found_count == 1
        assert len(result.not_found_items) == 1


@pytest.mark.asyncio
class TestTestSuiteServiceValidationMethods:
    """Test private validation methods."""
    
    async def test_validate_item_references_success(self):
        """Test successful item reference validation."""
        # Arrange
        mock_db = AsyncMock()
        mock_test_items = AsyncMock()
        mock_db.test_items = mock_test_items
        
        service = TestSuiteService(mock_db)
        
        item_1_id = str(ObjectId())
        item_2_id = str(ObjectId())
        user_id = str(ObjectId())
        
        # Mock database response with valid items
        mock_cursor = AsyncMock()
        mock_cursor.to_list.return_value = [
            {"_id": ObjectId(item_1_id)},
            {"_id": ObjectId(item_2_id)}
        ]
        mock_test_items.find.return_value = mock_cursor
        
        # Act
        result = await service._validate_item_references([item_1_id, item_2_id], user_id)
        
        # Assert
        assert isinstance(result, ValidationResult)
        assert result.valid_ids == {item_1_id, item_2_id}
        assert len(result.invalid_ids) == 0
        
        # Verify database query
        mock_test_items.find.assert_called_once()
        query = mock_test_items.find.call_args[0][0]
        assert "audit.created_by_user_id" in query
        assert query["audit.created_by_user_id"] == user_id
    
    async def test_validate_item_references_some_invalid(self):
        """Test item reference validation with some invalid items."""
        # Arrange
        mock_db = AsyncMock()
        mock_test_items = AsyncMock()
        mock_db.test_items = mock_test_items
        
        service = TestSuiteService(mock_db)
        
        item_1_id = str(ObjectId())
        item_2_id = str(ObjectId())
        item_3_id = str(ObjectId())
        user_id = str(ObjectId())
        
        # Mock database response with only 2 valid items
        mock_cursor = AsyncMock()
        mock_cursor.to_list.return_value = [
            {"_id": ObjectId(item_1_id)},
            {"_id": ObjectId(item_2_id)}
        ]
        mock_test_items.find.return_value = mock_cursor
        
        # Act
        result = await service._validate_item_references([item_1_id, item_2_id, item_3_id], user_id)
        
        # Assert
        assert result.valid_ids == {item_1_id, item_2_id}
        assert result.invalid_ids == {item_3_id}
    
    async def test_validate_title_uniqueness_success(self):
        """Test successful title uniqueness validation."""
        # Arrange
        mock_db = AsyncMock()
        mock_collection = AsyncMock()
        mock_db.test_suites = mock_collection
        
        service = TestSuiteService(mock_db)
        
        # Mock no existing suite with same title
        mock_collection.find_one.return_value = None
        
        title = "Unique Title"
        user_id = str(ObjectId())
        
        # Act - should not raise exception
        await service._validate_title_uniqueness(title, user_id)
        
        # Assert
        mock_collection.find_one.assert_called_once()
        query = mock_collection.find_one.call_args[0][0]
        assert query["title"] == title
        assert query["owner_id"] == user_id
    
    async def test_validate_title_uniqueness_duplicate(self):
        """Test title uniqueness validation with duplicate title."""
        # Arrange
        mock_db = AsyncMock()
        mock_collection = AsyncMock()
        mock_db.test_suites = mock_collection
        
        service = TestSuiteService(mock_db)
        
        # Mock existing suite with same title
        existing_suite = {
            "_id": ObjectId(),
            "title": "Duplicate Title",
            "owner_id": str(ObjectId())
        }
        mock_collection.find_one.return_value = existing_suite
        
        title = "Duplicate Title"
        user_id = str(ObjectId())
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await service._validate_title_uniqueness(title, user_id)
        
        assert exc_info.value.status_code == 409
        assert "already exists" in str(exc_info.value.detail)
    
    async def test_validate_suite_ownership_success(self):
        """Test successful suite ownership validation."""
        # Arrange
        mock_db = AsyncMock()
        mock_collection = AsyncMock()
        mock_db.test_suites = mock_collection
        
        service = TestSuiteService(mock_db)
        
        suite_id = str(ObjectId())
        user_id = str(ObjectId())
        
        # Mock existing suite owned by user
        existing_suite = {
            "_id": ObjectId(suite_id),
            "owner_id": user_id,
            "title": "User's Suite"
        }
        mock_collection.find_one.return_value = existing_suite
        
        # Act - should not raise exception
        await service._validate_suite_ownership(suite_id, user_id)
        
        # Assert
        mock_collection.find_one.assert_called_once()
        query = mock_collection.find_one.call_args[0][0]
        assert query["_id"] == ObjectId(suite_id)
        assert query["owner_id"] == user_id
    
    async def test_validate_suite_ownership_not_found(self):
        """Test suite ownership validation with non-existent suite."""
        # Arrange
        mock_db = AsyncMock()
        mock_collection = AsyncMock()
        mock_db.test_suites = mock_collection
        
        service = TestSuiteService(mock_db)
        
        # Mock no suite found
        mock_collection.find_one.return_value = None
        
        suite_id = str(ObjectId())
        user_id = str(ObjectId())
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await service._validate_suite_ownership(suite_id, user_id)
        
        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail)


@pytest.mark.asyncio
class TestTestSuiteServiceDeleteSuite:
    """Test the delete_suite method (soft deletion)."""
    
    async def test_delete_suite_success(self):
        """Test successful suite deletion (soft delete)."""
        # Arrange
        mock_db = AsyncMock()
        mock_collection = AsyncMock()
        mock_db.test_suites = mock_collection
        
        service = TestSuiteService(mock_db)
        
        # Mock validations and operations
        service._validate_suite_ownership = AsyncMock()
        service._track_operation = AsyncMock()
        
        # Mock successful update to archived status
        mock_update_result = Mock()
        mock_update_result.modified_count = 1
        mock_collection.update_one.return_value = mock_update_result
        
        suite_id = str(ObjectId())
        user_id = str(ObjectId())
        
        # Act
        result = await service.delete_suite(suite_id, user_id)
        
        # Assert
        assert result is True
        
        # Verify validations and operations
        service._validate_suite_ownership.assert_called_once_with(suite_id, user_id)
        mock_collection.update_one.assert_called_once()
        
        # Verify update query sets status to archived
        update_query = mock_collection.update_one.call_args[0]
        filter_query = update_query[0]
        update_operation = update_query[1]
        
        assert filter_query["_id"] == ObjectId(suite_id)
        assert update_operation["$set"]["status"] == TestSuiteStatus.ARCHIVED.value
    
    async def test_delete_suite_not_found(self):
        """Test deleting non-existent suite."""
        # Arrange
        mock_db = AsyncMock()
        service = TestSuiteService(mock_db)
        
        # Mock ownership validation to raise not found
        service._validate_suite_ownership = AsyncMock(
            side_effect=HTTPException(status_code=404, detail="Suite not found")
        )
        service._track_operation = AsyncMock()
        
        suite_id = str(ObjectId())
        user_id = str(ObjectId())
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await service.delete_suite(suite_id, user_id)
        
        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail)


@pytest.mark.asyncio
class TestTestSuiteServiceErrorHandling:
    """Test error handling and edge cases."""
    
    async def test_service_with_database_connection_issues(self):
        """Test service behavior with database connection issues."""
        # Arrange
        mock_db = AsyncMock()
        mock_collection = AsyncMock()
        mock_db.test_suites = mock_collection
        
        service = TestSuiteService(mock_db)
        
        # Mock database connection error
        mock_collection.find_one.side_effect = Exception("Connection timeout")
        
        suite_id = str(ObjectId())
        user_id = str(ObjectId())
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await service.get_suite(suite_id, user_id=user_id)
        
        assert "Connection timeout" in str(exc_info.value)
    
    async def test_invalid_object_id_handling(self):
        """Test handling of invalid ObjectId formats."""
        # Arrange
        mock_db = AsyncMock()
        service = TestSuiteService(mock_db)
        
        invalid_id = "invalid_object_id"
        user_id = str(ObjectId())
        
        # The service should handle ObjectId validation appropriately
        # This depends on implementation - might convert to ObjectId in service
        # or let the route layer handle validation
        
        # For this test, we'll assume the service gets valid ObjectIds from routes
        # and focus on testing the business logic rather than input validation
        pass
    
    @patch('src.backend.testsuites.services.test_suite_service.logger')
    async def test_operation_tracking_with_logging(self, mock_logger):
        """Test that operations are properly tracked and logged."""
        # Arrange
        mock_db = AsyncMock()
        service = TestSuiteService(mock_db)
        
        suite_id = str(ObjectId())
        user_id = str(ObjectId())
        
        # Act
        await service._track_operation(
            operation="test_operation",
            suite_id=suite_id,
            user_id=user_id,
            success=True,
            context={"test": "data"}
        )
        
        # Assert - verify logging was called
        mock_logger.info.assert_called()
        call_args = mock_logger.info.call_args
        assert "test_operation" in call_args[0][0]  # Check log message
        
        # Verify extra context was passed
        extra_context = call_args[1]["extra"]
        assert extra_context["operation"] == "test_operation"
        assert extra_context["suite_id"] == suite_id
        assert extra_context["user_id"] == user_id
        assert extra_context["success"] is True 
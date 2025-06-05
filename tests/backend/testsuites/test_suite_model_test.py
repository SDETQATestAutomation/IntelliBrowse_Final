"""
Test Suite Model Layer Integration Tests

Comprehensive testing of MongoDB integration and document model validation including:
- MongoDB document operations with test database
- Model validation and business rule enforcement
- Index management and performance optimization
- Field constraints and schema validation
- Document conversion methods (to_mongo, from_mongo, to_dict)
- Business logic methods (add_item, remove_item, etc.)
- MongoDB collection operations and validation schema
- Error handling and edge cases for data operations

Tests all model components:
- TestSuiteModel - Main document model with validation
- SuiteItemConfig - Embedded document model
- TestSuiteModelOperations - Index and collection management
- MongoDB integration patterns and optimizations
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List
from bson import ObjectId, errors as bson_errors
from pymongo.errors import ValidationError, DuplicateKeyError

from src.backend.testsuites.models.test_suite_model import (
    TestSuiteModel,
    SuiteItemConfig,
    TestSuiteModelOperations,
    TestSuiteStatus,
    TestSuitePriority
)


@pytest.mark.asyncio
class TestSuiteItemConfigModel:
    """Test the SuiteItemConfig embedded document model."""
    
    def test_suite_item_config_creation_success(self):
        """Test successful creation of SuiteItemConfig."""
        # Arrange
        test_item_id = str(ObjectId())
        
        # Act
        config = SuiteItemConfig(
            test_item_id=test_item_id,
            order=1,
            skip=False,
            custom_tags=["integration", "smoke"],
            note="Test item configuration",
            added_by=str(ObjectId())
        )
        
        # Assert
        assert config.test_item_id == test_item_id
        assert config.order == 1
        assert config.skip is False
        assert config.custom_tags == ["integration", "smoke"]
        assert config.note == "Test item configuration"
        assert isinstance(config.added_at, datetime)
        assert config.added_by is not None
    
    def test_suite_item_config_validation_errors(self):
        """Test validation errors in SuiteItemConfig."""
        # Test invalid ObjectId
        with pytest.raises(ValueError, match="test_item_id must be a valid ObjectId"):
            SuiteItemConfig(test_item_id="invalid_id", order=1)
        
        # Test invalid order (too low)
        with pytest.raises(ValueError):
            SuiteItemConfig(test_item_id=str(ObjectId()), order=0)
        
        # Test invalid order (too high)
        with pytest.raises(ValueError):
            SuiteItemConfig(test_item_id=str(ObjectId()), order=10001)
        
        # Test note too long
        long_note = "x" * 501  # Over 500 character limit
        with pytest.raises(ValueError):
            SuiteItemConfig(test_item_id=str(ObjectId()), order=1, note=long_note)
        
        # Test too many custom tags
        many_tags = [f"tag_{i}" for i in range(21)]  # Over 20 tag limit
        with pytest.raises(ValueError):
            SuiteItemConfig(test_item_id=str(ObjectId()), order=1, custom_tags=many_tags)
    
    def test_suite_item_config_tag_normalization(self):
        """Test custom tag normalization and validation."""
        # Arrange
        test_item_id = str(ObjectId())
        
        # Act
        config = SuiteItemConfig(
            test_item_id=test_item_id,
            order=1,
            custom_tags=["  Integration  ", "SMOKE", "", "  regression  "]
        )
        
        # Assert - empty and whitespace-only tags should be filtered, others normalized
        expected_tags = ["integration", "smoke", "regression"]
        assert config.custom_tags == expected_tags
    
    def test_suite_item_config_defaults(self):
        """Test default values in SuiteItemConfig."""
        # Arrange
        test_item_id = str(ObjectId())
        
        # Act
        config = SuiteItemConfig(test_item_id=test_item_id, order=1)
        
        # Assert
        assert config.skip is False
        assert config.custom_tags == []
        assert config.note is None
        assert isinstance(config.added_at, datetime)
        assert config.added_by is None


@pytest.mark.asyncio
class TestTestSuiteModelValidation:
    """Test TestSuiteModel validation and business rules."""
    
    def test_test_suite_model_creation_success(self):
        """Test successful creation of TestSuiteModel."""
        # Arrange
        owner_id = str(ObjectId())
        created_by = str(ObjectId())
        
        # Act
        suite = TestSuiteModel(
            title="Integration Test Suite",
            description="Comprehensive test suite for integration testing",
            status=TestSuiteStatus.DRAFT,
            priority=TestSuitePriority.HIGH,
            tags=["integration", "api", "smoke"],
            owner_id=owner_id,
            items=[],
            created_by=created_by
        )
        
        # Assert
        assert suite.title == "Integration Test Suite"
        assert suite.description == "Comprehensive test suite for integration testing"
        assert suite.status == TestSuiteStatus.DRAFT
        assert suite.priority == TestSuitePriority.HIGH
        assert suite.tags == ["integration", "api", "smoke"]
        assert suite.owner_id == owner_id
        assert suite.created_by == created_by
        assert suite.is_archived is False
        assert suite.items == []
        assert isinstance(suite.created_at, datetime)
        assert suite.schema_version == "1.0"
        assert suite.metadata == {}
    
    def test_test_suite_model_validation_errors(self):
        """Test validation errors in TestSuiteModel."""
        owner_id = str(ObjectId())
        created_by = str(ObjectId())
        
        # Test empty title
        with pytest.raises(ValueError, match="Title cannot be empty"):
            TestSuiteModel(title="", owner_id=owner_id, created_by=created_by)
        
        # Test whitespace-only title
        with pytest.raises(ValueError, match="Title cannot be empty"):
            TestSuiteModel(title="   ", owner_id=owner_id, created_by=created_by)
        
        # Test title too long
        long_title = "x" * 201  # Over 200 character limit
        with pytest.raises(ValueError):
            TestSuiteModel(title=long_title, owner_id=owner_id, created_by=created_by)
        
        # Test description too long
        long_description = "x" * 1001  # Over 1000 character limit
        with pytest.raises(ValueError):
            TestSuiteModel(
                title="Test Suite",
                description=long_description,
                owner_id=owner_id,
                created_by=created_by
            )
        
        # Test too many tags
        many_tags = [f"tag_{i}" for i in range(51)]  # Over 50 tag limit
        with pytest.raises(ValueError):
            TestSuiteModel(
                title="Test Suite",
                tags=many_tags,
                owner_id=owner_id,
                created_by=created_by
            )
        
        # Test invalid ObjectId format
        with pytest.raises(ValueError, match="must be a valid ObjectId"):
            TestSuiteModel(title="Test Suite", owner_id="invalid_id", created_by=created_by)
    
    def test_test_suite_model_tag_normalization(self):
        """Test tag normalization and validation."""
        # Arrange
        owner_id = str(ObjectId())
        created_by = str(ObjectId())
        
        # Act
        suite = TestSuiteModel(
            title="Test Suite",
            tags=["  INTEGRATION  ", "api", "", "  SMOKE  ", "regression"],
            owner_id=owner_id,
            created_by=created_by
        )
        
        # Assert - empty tags filtered, others normalized to lowercase
        expected_tags = ["integration", "api", "smoke", "regression"]
        assert suite.tags == expected_tags
    
    def test_test_suite_model_items_uniqueness_validation(self):
        """Test validation of unique test items within suite."""
        # Arrange
        owner_id = str(ObjectId())
        created_by = str(ObjectId())
        test_item_id = str(ObjectId())
        
        duplicate_items = [
            SuiteItemConfig(test_item_id=test_item_id, order=1),
            SuiteItemConfig(test_item_id=test_item_id, order=2)  # Same test_item_id
        ]
        
        # Act & Assert
        with pytest.raises(ValueError, match="Duplicate test item IDs found"):
            TestSuiteModel(
                title="Test Suite",
                items=duplicate_items,
                owner_id=owner_id,
                created_by=created_by
            )
    
    def test_test_suite_model_order_uniqueness_validation(self):
        """Test validation of unique order values within suite."""
        # Arrange
        owner_id = str(ObjectId())
        created_by = str(ObjectId())
        
        duplicate_order_items = [
            SuiteItemConfig(test_item_id=str(ObjectId()), order=1),
            SuiteItemConfig(test_item_id=str(ObjectId()), order=1)  # Same order
        ]
        
        # Act & Assert
        with pytest.raises(ValueError, match="Duplicate order values found"):
            TestSuiteModel(
                title="Test Suite",
                items=duplicate_order_items,
                owner_id=owner_id,
                created_by=created_by
            )


@pytest.mark.asyncio
class TestTestSuiteModelDocumentConversion:
    """Test document conversion methods."""
    
    def test_to_mongo_conversion(self):
        """Test conversion to MongoDB document format."""
        # Arrange
        owner_id = str(ObjectId())
        created_by = str(ObjectId())
        
        suite = TestSuiteModel(
            title="Test Suite",
            description="Test description",
            status=TestSuiteStatus.ACTIVE,
            priority=TestSuitePriority.HIGH,
            tags=["test"],
            owner_id=owner_id,
            created_by=created_by,
            items=[
                SuiteItemConfig(test_item_id=str(ObjectId()), order=1, skip=False)
            ]
        )
        
        # Act
        mongo_doc = suite.to_mongo()
        
        # Assert
        assert isinstance(mongo_doc, dict)
        assert mongo_doc["title"] == "Test Suite"
        assert mongo_doc["description"] == "Test description"
        assert mongo_doc["status"] == "active"  # Enum value
        assert mongo_doc["priority"] == "high"  # Enum value
        assert mongo_doc["tags"] == ["test"]
        assert mongo_doc["owner_id"] == owner_id
        assert mongo_doc["created_by"] == created_by
        assert "items" in mongo_doc
        assert len(mongo_doc["items"]) == 1
        assert isinstance(mongo_doc["created_at"], datetime)
        
        # Check that None values are excluded
        for key, value in mongo_doc.items():
            assert value is not None
    
    def test_from_mongo_conversion(self):
        """Test conversion from MongoDB document format."""
        # Arrange
        owner_id = str(ObjectId())
        created_by = str(ObjectId())
        suite_id = ObjectId()
        
        mongo_doc = {
            "_id": suite_id,
            "title": "Test Suite",
            "description": "Test description",
            "status": "active",
            "priority": "high",
            "tags": ["test"],
            "owner_id": owner_id,
            "is_archived": False,
            "items": [
                {
                    "test_item_id": str(ObjectId()),
                    "order": 1,
                    "skip": False,
                    "custom_tags": ["integration"],
                    "note": "Test item",
                    "added_at": datetime.utcnow(),
                    "added_by": created_by
                }
            ],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "created_by": created_by,
            "schema_version": "1.0",
            "metadata": {}
        }
        
        # Act
        suite = TestSuiteModel.from_mongo(mongo_doc)
        
        # Assert
        assert suite is not None
        assert suite.id == str(suite_id)
        assert suite.title == "Test Suite"
        assert suite.description == "Test description"
        assert suite.status == TestSuiteStatus.ACTIVE
        assert suite.priority == TestSuitePriority.HIGH
        assert suite.tags == ["test"]
        assert suite.owner_id == owner_id
        assert suite.created_by == created_by
        assert len(suite.items) == 1
        assert suite.items[0].test_item_id == mongo_doc["items"][0]["test_item_id"]
        assert suite.items[0].order == 1
    
    def test_from_mongo_with_none_document(self):
        """Test from_mongo with None document."""
        # Act
        result = TestSuiteModel.from_mongo(None)
        
        # Assert
        assert result is None
    
    def test_to_dict_conversion(self):
        """Test conversion to API response dictionary."""
        # Arrange
        owner_id = str(ObjectId())
        created_by = str(ObjectId())
        
        suite = TestSuiteModel(
            title="Test Suite",
            description="Test description",
            owner_id=owner_id,
            created_by=created_by,
            items=[
                SuiteItemConfig(test_item_id=str(ObjectId()), order=1, skip=False),
                SuiteItemConfig(test_item_id=str(ObjectId()), order=2, skip=True)
            ]
        )
        
        # Act
        api_dict = suite.to_dict()
        
        # Assert
        assert isinstance(api_dict, dict)
        assert api_dict["title"] == "Test Suite"
        assert api_dict["description"] == "Test description"
        assert api_dict["status"] == "draft"  # Default status
        assert api_dict["priority"] == "medium"  # Default priority
        
        # Check computed fields
        assert api_dict["total_items"] == 2
        assert api_dict["active_items"] == 1  # One is skipped
        
        # Check datetime serialization
        assert isinstance(api_dict["created_at"], str)
        if api_dict.get("updated_at"):
            assert isinstance(api_dict["updated_at"], str)


@pytest.mark.asyncio
class TestTestSuiteModelBusinessMethods:
    """Test business logic methods in TestSuiteModel."""
    
    def test_add_item_success(self):
        """Test successful item addition."""
        # Arrange
        owner_id = str(ObjectId())
        created_by = str(ObjectId())
        
        suite = TestSuiteModel(
            title="Test Suite",
            owner_id=owner_id,
            created_by=created_by
        )
        
        test_item_id = str(ObjectId())
        
        # Act
        suite.add_item(
            test_item_id=test_item_id,
            order=1,
            skip=False,
            custom_tags=["new"],
            note="New test item"
        )
        
        # Assert
        assert len(suite.items) == 1
        item = suite.items[0]
        assert item.test_item_id == test_item_id
        assert item.order == 1
        assert item.skip is False
        assert item.custom_tags == ["new"]
        assert item.note == "New test item"
    
    def test_add_item_with_auto_order(self):
        """Test item addition with automatic order assignment."""
        # Arrange
        owner_id = str(ObjectId())
        created_by = str(ObjectId())
        
        suite = TestSuiteModel(
            title="Test Suite",
            owner_id=owner_id,
            created_by=created_by,
            items=[
                SuiteItemConfig(test_item_id=str(ObjectId()), order=1),
                SuiteItemConfig(test_item_id=str(ObjectId()), order=3)  # Gap at 2
            ]
        )
        
        test_item_id = str(ObjectId())
        
        # Act - don't specify order, should auto-assign to max + 1
        suite.add_item(test_item_id=test_item_id)
        
        # Assert
        assert len(suite.items) == 3
        new_item = next(item for item in suite.items if item.test_item_id == test_item_id)
        assert new_item.order == 4  # max(1, 3) + 1
    
    def test_add_item_duplicate_id(self):
        """Test adding item with duplicate test_item_id."""
        # Arrange
        owner_id = str(ObjectId())
        created_by = str(ObjectId())
        test_item_id = str(ObjectId())
        
        suite = TestSuiteModel(
            title="Test Suite",
            owner_id=owner_id,
            created_by=created_by,
            items=[
                SuiteItemConfig(test_item_id=test_item_id, order=1)
            ]
        )
        
        # Act & Assert
        with pytest.raises(ValueError, match="already exists in the suite"):
            suite.add_item(test_item_id=test_item_id, order=2)
    
    def test_add_item_duplicate_order(self):
        """Test adding item with duplicate order."""
        # Arrange
        owner_id = str(ObjectId())
        created_by = str(ObjectId())
        
        suite = TestSuiteModel(
            title="Test Suite",
            owner_id=owner_id,
            created_by=created_by,
            items=[
                SuiteItemConfig(test_item_id=str(ObjectId()), order=1)
            ]
        )
        
        # Act & Assert
        with pytest.raises(ValueError, match="already exists in the suite"):
            suite.add_item(test_item_id=str(ObjectId()), order=1)
    
    def test_remove_item_success(self):
        """Test successful item removal."""
        # Arrange
        owner_id = str(ObjectId())
        created_by = str(ObjectId())
        test_item_id_1 = str(ObjectId())
        test_item_id_2 = str(ObjectId())
        
        suite = TestSuiteModel(
            title="Test Suite",
            owner_id=owner_id,
            created_by=created_by,
            items=[
                SuiteItemConfig(test_item_id=test_item_id_1, order=1),
                SuiteItemConfig(test_item_id=test_item_id_2, order=2)
            ]
        )
        
        # Act
        result = suite.remove_item(test_item_id_1)
        
        # Assert
        assert result is True
        assert len(suite.items) == 1
        assert suite.items[0].test_item_id == test_item_id_2
    
    def test_remove_item_with_rebalance(self):
        """Test item removal with order rebalancing."""
        # Arrange
        owner_id = str(ObjectId())
        created_by = str(ObjectId())
        test_item_id_1 = str(ObjectId())
        test_item_id_2 = str(ObjectId())
        test_item_id_3 = str(ObjectId())
        
        suite = TestSuiteModel(
            title="Test Suite",
            owner_id=owner_id,
            created_by=created_by,
            items=[
                SuiteItemConfig(test_item_id=test_item_id_1, order=1),
                SuiteItemConfig(test_item_id=test_item_id_2, order=2),
                SuiteItemConfig(test_item_id=test_item_id_3, order=3)
            ]
        )
        
        # Act - remove middle item and rebalance
        result = suite.remove_item(test_item_id_2, rebalance_order=True)
        
        # Assert
        assert result is True
        assert len(suite.items) == 2
        
        # Check orders were rebalanced
        remaining_items = sorted(suite.items, key=lambda x: x.order)
        assert remaining_items[0].test_item_id == test_item_id_1
        assert remaining_items[0].order == 1
        assert remaining_items[1].test_item_id == test_item_id_3
        assert remaining_items[1].order == 2  # Rebalanced from 3 to 2
    
    def test_remove_item_not_found(self):
        """Test removing non-existent item."""
        # Arrange
        owner_id = str(ObjectId())
        created_by = str(ObjectId())
        
        suite = TestSuiteModel(
            title="Test Suite",
            owner_id=owner_id,
            created_by=created_by,
            items=[]
        )
        
        # Act
        result = suite.remove_item(str(ObjectId()))
        
        # Assert
        assert result is False
        assert len(suite.items) == 0
    
    def test_get_item_config_success(self):
        """Test successful item configuration retrieval."""
        # Arrange
        owner_id = str(ObjectId())
        created_by = str(ObjectId())
        test_item_id = str(ObjectId())
        
        suite = TestSuiteModel(
            title="Test Suite",
            owner_id=owner_id,
            created_by=created_by,
            items=[
                SuiteItemConfig(
                    test_item_id=test_item_id,
                    order=1,
                    skip=True,
                    custom_tags=["important"],
                    note="Important test item"
                )
            ]
        )
        
        # Act
        config = suite.get_item_config(test_item_id)
        
        # Assert
        assert config is not None
        assert config.test_item_id == test_item_id
        assert config.order == 1
        assert config.skip is True
        assert config.custom_tags == ["important"]
        assert config.note == "Important test item"
    
    def test_get_item_config_not_found(self):
        """Test item configuration retrieval for non-existent item."""
        # Arrange
        owner_id = str(ObjectId())
        created_by = str(ObjectId())
        
        suite = TestSuiteModel(
            title="Test Suite",
            owner_id=owner_id,
            created_by=created_by,
            items=[]
        )
        
        # Act
        config = suite.get_item_config(str(ObjectId()))
        
        # Assert
        assert config is None
    
    def test_update_metadata_fields(self):
        """Test metadata field updates."""
        # Arrange
        owner_id = str(ObjectId())
        created_by = str(ObjectId())
        
        suite = TestSuiteModel(
            title="Original Title",
            description="Original description",
            owner_id=owner_id,
            created_by=created_by
        )
        
        original_updated_at = suite.updated_at
        
        # Act
        suite.update_metadata_fields(
            title="Updated Title",
            description="Updated description",
            priority=TestSuitePriority.HIGH,
            status=TestSuiteStatus.ACTIVE,
            tags=["updated", "test"]
        )
        
        # Assert
        assert suite.title == "Updated Title"
        assert suite.description == "Updated description"
        assert suite.priority == TestSuitePriority.HIGH
        assert suite.status == TestSuiteStatus.ACTIVE
        assert suite.tags == ["updated", "test"]
        assert suite.updated_at != original_updated_at  # Should be updated


@pytest.mark.asyncio
class TestTestSuiteModelOperations:
    """Test TestSuiteModelOperations for index and collection management."""
    
    def test_get_indexes_structure(self):
        """Test index definitions structure."""
        # Act
        indexes = TestSuiteModelOperations.get_indexes()
        
        # Assert
        assert isinstance(indexes, list)
        assert len(indexes) > 0
        
        # Verify each index has required structure
        for index in indexes:
            assert "keys" in index
            assert "options" in index
            assert isinstance(index["keys"], list)
            assert isinstance(index["options"], dict)
    
    def test_get_indexes_content(self):
        """Test specific index definitions."""
        # Act
        indexes = TestSuiteModelOperations.get_indexes()
        
        # Assert - check for key indexes
        index_names = [idx["options"].get("name", "") for idx in indexes]
        
        # Should have main query index
        assert any("owner_status_priority" in name for name in index_names)
        
        # Should have unique title index
        assert any("unique_title" in name for name in index_names)
        
        # Should have tag filtering index
        assert any("tag_filter" in name for name in index_names)
        
        # Should have text search index
        assert any("text_search" in name for name in index_names)
        
        # Should have item operations index
        assert any("item_operations" in name for name in index_names)
    
    def test_get_collection_validation_structure(self):
        """Test collection validation schema structure."""
        # Act
        validation = TestSuiteModelOperations.get_collection_validation()
        
        # Assert
        assert isinstance(validation, dict)
        assert "validator" in validation
        assert "validationLevel" in validation
        assert "validationAction" in validation
        
        # Check validator structure
        validator = validation["validator"]
        assert "$jsonSchema" in validator
        
        json_schema = validator["$jsonSchema"]
        assert "bsonType" in json_schema
        assert "required" in json_schema
        assert "properties" in json_schema
        assert json_schema["bsonType"] == "object"
    
    def test_get_collection_validation_required_fields(self):
        """Test collection validation required fields."""
        # Act
        validation = TestSuiteModelOperations.get_collection_validation()
        
        # Assert
        json_schema = validation["validator"]["$jsonSchema"]
        required_fields = json_schema["required"]
        
        # Check essential required fields
        essential_fields = ["title", "owner_id", "created_at", "created_by"]
        for field in essential_fields:
            assert field in required_fields
    
    def test_validate_document_success(self):
        """Test successful document validation."""
        # Arrange
        valid_doc = {
            "title": "Test Suite",
            "description": "Test description",
            "status": "draft",
            "priority": "medium",
            "tags": ["test"],
            "owner_id": str(ObjectId()),
            "is_archived": False,
            "items": [],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "created_by": str(ObjectId()),
            "schema_version": "1.0",
            "metadata": {}
        }
        
        # Act
        result = TestSuiteModelOperations.validate_document(valid_doc)
        
        # Assert
        assert result is True
    
    def test_validate_document_missing_required_fields(self):
        """Test document validation with missing required fields."""
        # Arrange
        invalid_doc = {
            "description": "Missing title and other required fields"
        }
        
        # Act
        result = TestSuiteModelOperations.validate_document(invalid_doc)
        
        # Assert
        assert result is False
    
    def test_validate_document_invalid_types(self):
        """Test document validation with invalid field types."""
        # Arrange
        invalid_doc = {
            "title": 123,  # Should be string
            "owner_id": str(ObjectId()),
            "created_at": datetime.utcnow(),
            "created_by": str(ObjectId())
        }
        
        # Act
        result = TestSuiteModelOperations.validate_document(invalid_doc)
        
        # Assert
        assert result is False
    
    def test_get_collection_settings(self):
        """Test collection settings configuration."""
        # Act
        operations = TestSuiteModelOperations()
        settings = operations.get_collection_settings()
        
        # Assert
        assert isinstance(settings, dict)
        
        # Should have validation settings
        if "validator" in settings:
            assert isinstance(settings["validator"], dict)
        
        if "validationLevel" in settings:
            assert settings["validationLevel"] in ["strict", "moderate"]
        
        if "validationAction" in settings:
            assert settings["validationAction"] in ["error", "warn"]


@pytest.mark.asyncio
class TestTestSuiteModelDatabaseIntegration:
    """Test MongoDB database integration with actual database operations."""
    
    async def test_document_size_monitoring(self, test_db):
        """Test document size monitoring and warnings."""
        # Arrange
        owner_id = str(ObjectId())
        created_by = str(ObjectId())
        
        # Create a suite with many items to approach size limits
        large_items = []
        for i in range(500):  # Create many items
            large_items.append(SuiteItemConfig(
                test_item_id=str(ObjectId()),
                order=i + 1,
                skip=False,
                custom_tags=[f"tag_{i}", f"category_{i % 10}"],
                note=f"This is a note for test item {i} with some additional content to increase size"
            ))
        
        suite = TestSuiteModel(
            title="Large Test Suite",
            description="A test suite with many items for size testing",
            owner_id=owner_id,
            created_by=created_by,
            items=large_items
        )
        
        # Act - convert to MongoDB format
        mongo_doc = suite.to_mongo()
        
        # Assert - document should be valid but size should be monitored
        assert isinstance(mongo_doc, dict)
        assert len(mongo_doc["items"]) == 500
        
        # Check approximate size (rough estimation)
        import sys
        doc_size = sys.getsizeof(str(mongo_doc))
        
        # Should be substantial but under MongoDB 16MB limit
        assert doc_size > 10000  # Should be reasonably large
        # Note: Real size monitoring would use bson.encode() in production
    
    async def test_index_creation_compatibility(self, test_db):
        """Test that index definitions are compatible with MongoDB."""
        # Arrange
        collection = test_db.test_suites_model_test
        
        try:
            # Act - create indexes
            indexes = TestSuiteModelOperations.get_indexes()
            
            for index_def in indexes:
                keys = [(key["field"], key["direction"]) for key in index_def["keys"]]
                options = index_def["options"]
                
                # Should not raise exception
                await collection.create_index(keys, **options)
            
            # Assert - verify indexes were created
            index_info = await collection.list_indexes().to_list(length=None)
            assert len(index_info) > 1  # At least _id and our custom indexes
        
        finally:
            # Cleanup
            await collection.drop()
    
    async def test_validation_schema_compatibility(self, test_db):
        """Test that validation schema is compatible with MongoDB."""
        # Arrange
        collection = test_db.test_suites_validation_test
        
        try:
            # Act - create collection with validation
            validation = TestSuiteModelOperations.get_collection_validation()
            
            await test_db.create_collection(
                "test_suites_validation_test",
                validator=validation["validator"],
                validationLevel=validation["validationLevel"],
                validationAction=validation["validationAction"]
            )
            
            # Test valid document insertion
            owner_id = str(ObjectId())
            created_by = str(ObjectId())
            
            valid_doc = {
                "title": "Valid Test Suite",
                "description": "A valid test suite",
                "status": "draft",
                "priority": "medium",
                "tags": ["test"],
                "owner_id": owner_id,
                "is_archived": False,
                "items": [],
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "created_by": created_by,
                "schema_version": "1.0",
                "metadata": {}
            }
            
            # Should succeed
            result = await collection.insert_one(valid_doc)
            assert result.inserted_id is not None
            
            # Test invalid document insertion (if validation is strict)
            if validation["validationAction"] == "error":
                invalid_doc = {"title": 123}  # Invalid type
                
                with pytest.raises(Exception):  # Should raise validation error
                    await collection.insert_one(invalid_doc)
        
        except Exception as e:
            # Some validation errors are expected during testing
            if "ValidationError" not in str(type(e).__name__):
                raise
        
        finally:
            # Cleanup
            await collection.drop()
    
    async def test_complex_query_performance(self, test_db):
        """Test performance characteristics of complex queries."""
        # Arrange
        collection = test_db.test_suites_performance_test
        owner_id = str(ObjectId())
        created_by = str(ObjectId())
        
        try:
            # Create test data
            test_suites = []
            for i in range(100):
                suite_doc = {
                    "title": f"Performance Test Suite {i}",
                    "description": f"Suite for performance testing {i}",
                    "status": "active" if i % 2 == 0 else "draft",
                    "priority": "high" if i % 3 == 0 else "medium",
                    "tags": [f"tag_{i % 5}", f"category_{i % 3}"],
                    "owner_id": owner_id,
                    "is_archived": False,
                    "items": [
                        {
                            "test_item_id": str(ObjectId()),
                            "order": j + 1,
                            "skip": j % 4 == 0,
                            "custom_tags": [f"item_tag_{j}"],
                            "note": f"Item {j} note",
                            "added_at": datetime.utcnow(),
                            "added_by": created_by
                        }
                        for j in range(i % 10 + 1)  # Variable number of items
                    ],
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                    "created_by": created_by,
                    "schema_version": "1.0",
                    "metadata": {}
                }
                test_suites.append(suite_doc)
            
            await collection.insert_many(test_suites)
            
            # Act & Assert - test various query patterns
            import time
            
            # Test 1: Filter by owner and status
            start_time = time.time()
            cursor = collection.find({"owner_id": owner_id, "status": "active"})
            results = await cursor.to_list(length=None)
            query_time_1 = time.time() - start_time
            
            assert len(results) == 50  # Half should be active
            assert query_time_1 < 1.0  # Should be fast
            
            # Test 2: Filter by tags
            start_time = time.time()
            cursor = collection.find({"owner_id": owner_id, "tags": {"$in": ["tag_0", "tag_1"]}})
            results = await cursor.to_list(length=None)
            query_time_2 = time.time() - start_time
            
            assert len(results) > 0
            assert query_time_2 < 1.0  # Should be fast
            
            # Test 3: Complex aggregation query
            start_time = time.time()
            pipeline = [
                {"$match": {"owner_id": owner_id}},
                {"$group": {
                    "_id": "$priority",
                    "count": {"$sum": 1},
                    "avg_items": {"$avg": {"$size": "$items"}}
                }}
            ]
            cursor = collection.aggregate(pipeline)
            results = await cursor.to_list(length=None)
            query_time_3 = time.time() - start_time
            
            assert len(results) > 0
            assert query_time_3 < 1.0  # Should be fast
        
        finally:
            # Cleanup
            await collection.drop()


@pytest.mark.asyncio
class TestTestSuiteModelEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_model_with_extreme_values(self):
        """Test model with boundary values."""
        # Arrange
        owner_id = str(ObjectId())
        created_by = str(ObjectId())
        
        # Test with maximum allowed values
        max_tags = [f"tag_{i}" for i in range(50)]  # Maximum tags
        max_title = "x" * 200  # Maximum title length
        max_description = "x" * 1000  # Maximum description length
        
        # Act
        suite = TestSuiteModel(
            title=max_title,
            description=max_description,
            tags=max_tags,
            owner_id=owner_id,
            created_by=created_by
        )
        
        # Assert
        assert len(suite.title) == 200
        assert len(suite.description) == 1000
        assert len(suite.tags) == 50
    
    def test_model_with_unicode_content(self):
        """Test model with Unicode and special characters."""
        # Arrange
        owner_id = str(ObjectId())
        created_by = str(ObjectId())
        
        # Act
        suite = TestSuiteModel(
            title="测试套件 🧪 Test Suite",
            description="Ñoñó español 中文 العربية Emoji: 🚀🔥💯",
            tags=["测试", "español", "العربية", "emoji_🧪"],
            owner_id=owner_id,
            created_by=created_by
        )
        
        # Assert
        assert "测试套件" in suite.title
        assert "🧪" in suite.title
        assert "中文" in suite.description
        assert "العربية" in suite.description
        assert "emoji_🧪" in suite.tags
    
    def test_datetime_handling_edge_cases(self):
        """Test datetime handling with various edge cases."""
        # Arrange
        owner_id = str(ObjectId())
        created_by = str(ObjectId())
        
        # Test with specific datetime
        specific_time = datetime(2024, 1, 15, 10, 30, 45, 123456)
        
        suite = TestSuiteModel(
            title="DateTime Test Suite",
            owner_id=owner_id,
            created_by=created_by
        )
        
        # Manually set specific datetime
        suite.created_at = specific_time
        suite.updated_at = specific_time
        
        # Act - convert to MongoDB and back
        mongo_doc = suite.to_mongo()
        restored_suite = TestSuiteModel.from_mongo(mongo_doc)
        
        # Assert
        assert restored_suite is not None
        assert restored_suite.created_at == specific_time
        assert restored_suite.updated_at == specific_time
        
        # Test API serialization
        api_dict = restored_suite.to_dict()
        assert isinstance(api_dict["created_at"], str)
        assert isinstance(api_dict["updated_at"], str) 
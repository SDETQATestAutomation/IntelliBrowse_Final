"""
Test Suite MongoDB Model

MongoDB document model for test suite management with embedded suite items.
Implements comprehensive validation, indexing strategy, and utility methods
following the established codebase patterns for optimal performance and maintainability.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from enum import Enum
from pydantic import BaseModel, Field, field_validator, ConfigDict
from bson import ObjectId

from ...config.env import get_settings
from ...config.logging import get_logger

logger = get_logger(__name__)


class BaseMongoModel(BaseModel):
    """
    Base model for MongoDB documents with common fields and utilities.
    
    Implements DRY principles for timestamps, schema versioning, and
    datetime serialization handling across all MongoDB models.
    """
    
    # Document identity
    id: Optional[str] = Field(None, alias="_id", description="MongoDB document ID")
    
    # Schema versioning for migrations (stored as _schema_version in MongoDB)
    schema_version: str = Field(
        default="1.0",
        alias="_schema_version",
        description="Schema version for forward compatibility"
    )
    
    # Audit trail with UTC-aware timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp (UTC)"
    )
    updated_at: Optional[datetime] = Field(
        None,
        description="Last update timestamp (UTC)"
    )
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        use_enum_values=True,
        json_encoders={
            ObjectId: str,
            datetime: lambda v: v.isoformat() if v else None,
        }
    )
    
    @field_validator('created_at', 'updated_at', mode='before')
    @classmethod
    def validate_datetime_utc(cls, v):
        """Ensure datetime fields are UTC-aware with fallback handling."""
        if v is None:
            return v
        
        if isinstance(v, str):
            try:
                # Parse ISO string with fallback
                if v.endswith('Z'):
                    v = v[:-1] + '+00:00'
                return datetime.fromisoformat(v)
            except ValueError:
                logger.warning(f"Failed to parse datetime string: {v}, using current UTC time")
                return datetime.now(timezone.utc)
        
        if isinstance(v, datetime):
            # Ensure timezone awareness
            if v.tzinfo is None:
                logger.debug("Converting naive datetime to UTC")
                return v.replace(tzinfo=timezone.utc)
            return v
        
        logger.warning(f"Invalid datetime value: {v}, using current UTC time")
        return datetime.now(timezone.utc)
    
    def update_timestamp(self) -> None:
        """Update the updated_at timestamp to current UTC time."""
        self.updated_at = datetime.now(timezone.utc)
    
    @classmethod
    def from_mongo(cls, data: Dict[str, Any]) -> Optional["BaseMongoModel"]:
        """
        Create model instance from MongoDB document.
        
        Args:
            data: MongoDB document data
            
        Returns:
            Model instance or None if data is invalid
        """
        if not data:
            return None
        
        try:
            # Handle ObjectId conversion
            if "_id" in data and isinstance(data["_id"], ObjectId):
                data["_id"] = str(data["_id"])
            
            # Handle datetime fields
            for field in ["created_at", "updated_at"]:
                if field in data and data[field]:
                    if isinstance(data[field], datetime):
                        # Ensure UTC timezone
                        if data[field].tzinfo is None:
                            data[field] = data[field].replace(tzinfo=timezone.utc)
            
            return cls(**data)
        except Exception as e:
            logger.error(f"Failed to create {cls.__name__} from MongoDB data: {e}")
            return None
    
    def to_mongo(self) -> Dict[str, Any]:
        """
        Convert model to MongoDB document format.
        
        Returns:
            Dictionary suitable for MongoDB storage
        """
        data = self.model_dump(by_alias=True, exclude_none=True)
        
        # Convert string ID back to ObjectId for MongoDB
        if "_id" in data and data["_id"]:
            try:
                data["_id"] = ObjectId(data["_id"])
            except Exception:
                # If conversion fails, remove the field to let MongoDB generate new ID
                del data["_id"]
        
        # Ensure UTC datetime storage
        for field in ["created_at", "updated_at"]:
            if field in data and data[field]:
                if isinstance(data[field], str):
                    try:
                        data[field] = datetime.fromisoformat(data[field])
                    except ValueError:
                        logger.warning(f"Invalid datetime string for {field}: {data[field]}")
                        data[field] = datetime.now(timezone.utc)
        
        return data


# Enums for status and priority management
class TestSuiteStatus(str, Enum):
    """Test suite status enumeration."""
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class TestSuitePriority(str, Enum):
    """Test suite priority enumeration."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# Embedded configuration for suite items
class SuiteItemConfig(BaseModel):
    """
    Embedded configuration for test items within a suite.
    
    Contains per-suite item configuration including execution order,
    skip flags, custom tags, and contextual notes.
    """
    
    test_item_id: str = Field(
        ...,
        description="Reference to test item (MongoDB ObjectId)",
        min_length=24,
        max_length=24
    )
    order: int = Field(
        ...,
        description="Execution order within suite (1-based)",
        ge=1,
        le=10000
    )
    skip: bool = Field(
        default=False,
        description="Skip flag for conditional execution"
    )
    custom_tags: List[str] = Field(
        default_factory=list,
        description="Additional tags specific to this item in the suite",
        max_length=20
    )
    note: Optional[str] = Field(
        None,
        description="Optional note for execution context",
        max_length=500
    )
    
    # Configuration metadata with UTC-aware timestamps
    added_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When item was added to the suite (UTC)"
    )
    added_by: Optional[str] = Field(
        None,
        description="User ID who added this item"
    )
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
        }
    )
    
    @field_validator('test_item_id')
    @classmethod
    def validate_test_item_id(cls, v):
        """Validate test item ID is valid ObjectId format."""
        if not ObjectId.is_valid(v):
            raise ValueError("test_item_id must be a valid ObjectId")
        return v
    
    @field_validator('custom_tags')
    @classmethod
    def validate_custom_tags(cls, v):
        """Validate custom tags are non-empty strings."""
        if v:
            for tag in v:
                if not isinstance(tag, str) or not tag.strip():
                    raise ValueError("Custom tags must be non-empty strings")
        return [tag.strip().lower() for tag in v if tag.strip()]
    
    @field_validator('added_at', mode='before')
    @classmethod
    def validate_added_at_utc(cls, v):
        """Ensure added_at is UTC-aware."""
        if v is None:
            return datetime.now(timezone.utc)
        
        if isinstance(v, str):
            try:
                if v.endswith('Z'):
                    v = v[:-1] + '+00:00'
                return datetime.fromisoformat(v)
            except ValueError:
                logger.warning(f"Failed to parse added_at datetime: {v}")
                return datetime.now(timezone.utc)
        
        if isinstance(v, datetime):
            if v.tzinfo is None:
                return v.replace(tzinfo=timezone.utc)
            return v
        
        return datetime.now(timezone.utc)


# Main test suite document model
class TestSuiteModel(BaseMongoModel):
    """
    Test Suite MongoDB document model.
    
    Extends BaseMongoModel with suite-specific fields and validation.
    Implements embedded document design for test items with comprehensive
    validation, performance optimization, and audit trail functionality.
    """
    
    # Core suite metadata
    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Test suite title (unique per user)"
    )
    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Test suite description"
    )
    status: TestSuiteStatus = Field(
        default=TestSuiteStatus.DRAFT,
        description="Suite status"
    )
    priority: TestSuitePriority = Field(
        default=TestSuitePriority.MEDIUM,
        description="Suite priority"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Suite tags for categorization",
        max_length=50
    )
    
    # Ownership and access control
    owner_id: str = Field(
        ...,
        description="Owner user ID (MongoDB ObjectId)"
    )
    is_archived: bool = Field(
        default=False,
        description="Soft deletion flag"
    )
    
    # Embedded test items with configurations
    items: List[SuiteItemConfig] = Field(
        default_factory=list,
        description="Test items in the suite with configurations",
        max_length=1000  # MongoDB document size limit protection
    )
    
    # Creator tracking
    created_by: str = Field(
        ...,
        description="User ID who created the suite"
    )
    
    # Additional metadata for future extensions
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata for future extensions"
    )
    
    @field_validator('title')
    @classmethod
    def validate_title(cls, v):
        """Validate title is non-empty and properly formatted."""
        if not v or not v.strip():
            raise ValueError("Title cannot be empty")
        return v.strip()
    
    @field_validator('owner_id', 'created_by')
    @classmethod
    def validate_user_ids(cls, v):
        """Validate user IDs are valid ObjectId format."""
        if not ObjectId.is_valid(v):
            raise ValueError("User ID must be a valid ObjectId")
        return v
    
    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v):
        """Validate tags are non-empty strings and normalize them."""
        if v:
            normalized = []
            for tag in v:
                if isinstance(tag, str) and tag.strip():
                    normalized.append(tag.strip().lower())
        return normalized if v else []
    
    @field_validator('items')
    @classmethod
    def validate_items_uniqueness(cls, v):
        """Validate that test item IDs are unique within the suite."""
        if not v:
            return v
        
        seen_ids = set()
        seen_orders = set()
        
        for item in v:
            if item.test_item_id in seen_ids:
                raise ValueError(f"Duplicate test item ID: {item.test_item_id}")
            seen_ids.add(item.test_item_id)
            
            if item.order in seen_orders:
                raise ValueError(f"Duplicate order value: {item.order}")
            seen_orders.add(item.order)
        
        return v
    
    @classmethod
    def from_mongo(cls, data: Dict[str, Any]) -> Optional["TestSuiteModel"]:
        """
        Create TestSuiteModel from MongoDB document with enhanced error handling.
        
        Args:
            data: MongoDB document data
            
        Returns:
            TestSuiteModel instance or None if data is invalid
        """
        if not data:
            return None
        
        try:
            # Handle ObjectId conversion
            if "_id" in data and isinstance(data["_id"], ObjectId):
                data["_id"] = str(data["_id"])
            
            # Handle embedded SuiteItemConfig objects
            if "items" in data and data["items"]:
                for item_data in data["items"]:
                    # Ensure added_at is properly handled
                    if "added_at" in item_data and isinstance(item_data["added_at"], datetime):
                        if item_data["added_at"].tzinfo is None:
                            item_data["added_at"] = item_data["added_at"].replace(tzinfo=timezone.utc)
            
            # Schema version validation
            if "_schema_version" not in data:
                logger.warning("Missing _schema_version field, adding default")
                data["_schema_version"] = "1.0"
            
            return cls(**data)
        except Exception as e:
            logger.error(
                f"Failed to create TestSuiteModel from MongoDB data: {e}",
                extra={"data": data, "error": str(e)}
            )
            return None
    
    def to_mongo(self) -> Dict[str, Any]:
        """
        Convert model to MongoDB document format with enhanced datetime handling.
        
        Returns:
            Dictionary suitable for MongoDB storage
        """
        # Use parent method and enhance
        data = super().to_mongo()
        
        # Handle embedded items datetime fields
        if "items" in data and data["items"]:
            for item in data["items"]:
                if "added_at" in item and isinstance(item["added_at"], str):
                    try:
                        item["added_at"] = datetime.fromisoformat(item["added_at"])
                    except ValueError:
                        logger.warning(f"Invalid added_at datetime in item: {item.get('test_item_id')}")
                        item["added_at"] = datetime.now(timezone.utc)
        
        return data
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert model to dictionary format for API responses.
        
        Returns:
            Dictionary with properly serialized fields
        """
        data = self.model_dump(exclude_none=True)
        
        # Convert ObjectId fields to strings
        if "id" in data and data["id"]:
            data["id"] = str(data["id"])
        
        # Ensure datetime fields are ISO format strings
        for field in ["created_at", "updated_at"]:
            if field in data and data[field]:
                if isinstance(data[field], datetime):
                    data[field] = data[field].isoformat()
        
        # Handle embedded items datetime serialization
        if "items" in data and data["items"]:
            for item in data["items"]:
                if "added_at" in item and isinstance(item["added_at"], datetime):
                    item["added_at"] = item["added_at"].isoformat()
        
        return data
    
    def add_item(self, test_item_id: str, order: Optional[int] = None, **config) -> None:
        """
        Add a test item to the suite with configuration.
        
        Args:
            test_item_id: Test item ObjectId
            order: Execution order (auto-assigned if None)
            **config: Additional configuration (skip, custom_tags, note, added_by)
        
        Raises:
            ValueError: If test item already exists or order is invalid
        """
        # Validate test item ID
        if not ObjectId.is_valid(test_item_id):
            raise ValueError("test_item_id must be a valid ObjectId")
        
        # Check for duplicates
        if any(item.test_item_id == test_item_id for item in self.items):
            raise ValueError(f"Test item {test_item_id} already exists in suite")
        
        # Auto-assign order if not provided
        if order is None:
            existing_orders = [item.order for item in self.items]
            order = max(existing_orders, default=0) + 1
        else:
            # Validate order uniqueness
            if any(item.order == order for item in self.items):
                raise ValueError(f"Order {order} already in use")
        
        # Create item configuration
        item_config = SuiteItemConfig(
            test_item_id=test_item_id,
            order=order,
            skip=config.get("skip", False),
            custom_tags=config.get("custom_tags", []),
            note=config.get("note"),
            added_at=datetime.now(timezone.utc),
            added_by=config.get("added_by")
        )
        
        self.items.append(item_config)
        self.update_timestamp()
        
        logger.debug(
            f"Added item {test_item_id} to suite with order {order}",
            extra={"suite_id": self.id, "test_item_id": test_item_id, "order": order}
        )
    
    def remove_item(self, test_item_id: str, rebalance_order: bool = False) -> bool:
        """
        Remove a test item from the suite.
        
        Args:
            test_item_id: Test item ObjectId to remove
            rebalance_order: Whether to rebalance order values after removal
            
        Returns:
            True if item was removed, False if not found
        """
        original_count = len(self.items)
        self.items = [item for item in self.items if item.test_item_id != test_item_id]
        
        if len(self.items) == original_count:
            return False  # Item not found
        
        # Rebalance order values if requested
        if rebalance_order and self.items:
            sorted_items = sorted(self.items, key=lambda x: x.order)
            for idx, item in enumerate(sorted_items, start=1):
                item.order = idx
        
        self.update_timestamp()
        
        logger.debug(
            f"Removed item {test_item_id} from suite",
            extra={"suite_id": self.id, "test_item_id": test_item_id, "rebalanced": rebalance_order}
        )
        
        return True
    
    def get_item_config(self, test_item_id: str) -> Optional[SuiteItemConfig]:
        """
        Get configuration for a specific test item.
        
        Args:
            test_item_id: Test item ObjectId
            
        Returns:
            SuiteItemConfig if found, None otherwise
        """
        for item in self.items:
            if item.test_item_id == test_item_id:
                return item
        return None
    
    def update_metadata_fields(self, **kwargs) -> None:
        """
        Update suite metadata fields.
        
        Args:
            **kwargs: Fields to update (title, description, status, priority, tags)
        """
        allowed_fields = {"title", "description", "status", "priority", "tags"}
        
        for field, value in kwargs.items():
            if field in allowed_fields and hasattr(self, field):
                setattr(self, field, value)
        
        self.update_timestamp()
        
        logger.debug(
            f"Updated suite metadata: {list(kwargs.keys())}",
            extra={"suite_id": self.id, "updated_fields": list(kwargs.keys())}
        )


class TestSuiteModelOperations:
    """
    MongoDB operations and utilities for test suite management.
    
    Provides index management, validation, and collection configuration
    for optimal performance and data integrity.
    """
    
    def __init__(self):
        self.settings = get_settings()
        # Collection name follows the established pattern
        self.collection_name = "test_suites"
    
    @staticmethod
    def get_indexes() -> List[Dict[str, Any]]:
        """
        Get MongoDB indexes for the test_suites collection.
        
        Provides compound indexes optimized for common query patterns
        including ownership, status filtering, and text search.
        
        Returns:
            List of index specifications for MongoDB
        """
        return [
            # Primary query index: owner + status + creation date
            {
                "name": "idx_owner_status_created",
                "keys": [
                    ("owner_id", 1),
                    ("is_archived", 1),
                    ("status", 1),
                    ("created_at", -1)
                ],
                "options": {
                    "background": True
                }
            },
            
            # Unique title per user constraint
            {
                "name": "idx_unique_title_per_user",
                "keys": [
                    ("owner_id", 1),
                    ("title", 1),
                    ("is_archived", 1)
                ],
                "options": {
                    "unique": True,
                    "background": True,
                    "partialFilterExpression": {
                        "is_archived": {"$ne": True}
                    }
                }
            },
            
            # Tag-based filtering
            {
                "name": "idx_tags_priority",
                "keys": [
                    ("owner_id", 1),
                    ("tags", 1),
                    ("priority", 1),
                    ("updated_at", -1)
                ],
                "options": {
                    "background": True
                }
            },
            
            # Text search on title and description
            {
                "name": "idx_text_search",
                "keys": [
                    ("title", "text"),
                    ("description", "text")
                ],
                "options": {
                    "background": True,
                    "weights": {
                        "title": 10,
                        "description": 5
                    },
                    "default_language": "english"
                }
            },
            
            # Performance index for item operations
            {
                "name": "idx_items_operations",
                "keys": [
                    ("owner_id", 1),
                    ("items.test_item_id", 1),
                    ("updated_at", -1)
                ],
                "options": {
                    "background": True,
                    "sparse": True
                }
            }
        ]
    
    @staticmethod
    def get_collection_validation() -> Dict[str, Any]:
        """
        Get MongoDB collection validation schema.
        
        Provides server-side validation rules for document integrity
        and constraint enforcement at the database level.
        
        Returns:
            MongoDB validation schema
        """
        return {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["title", "owner_id", "created_by", "created_at", "_schema_version"],
                "properties": {
                    "title": {
                        "bsonType": "string",
                        "minLength": 1,
                        "maxLength": 200,
                        "description": "Test suite title"
                    },
                    "description": {
                        "bsonType": ["string", "null"],
                        "maxLength": 1000,
                        "description": "Test suite description"
                    },
                    "status": {
                        "enum": ["draft", "active", "archived"],
                        "description": "Suite status"
                    },
                    "priority": {
                        "enum": ["high", "medium", "low"],
                        "description": "Suite priority"
                    },
                    "tags": {
                        "bsonType": "array",
                        "maxItems": 50,
                        "items": {
                            "bsonType": "string",
                            "minLength": 1
                        },
                        "description": "Suite tags"
                    },
                    "owner_id": {
                        "bsonType": "string",
                        "pattern": "^[0-9a-fA-F]{24}$",
                        "description": "Owner user ID"
                    },
                    "is_archived": {
                        "bsonType": "bool",
                        "description": "Soft deletion flag"
                    },
                    "items": {
                        "bsonType": "array",
                        "maxItems": 1000,
                        "items": {
                            "bsonType": "object",
                            "required": ["test_item_id", "order"],
                            "properties": {
                                "test_item_id": {
                                    "bsonType": "string",
                                    "pattern": "^[0-9a-fA-F]{24}$"
                                },
                                "order": {
                                    "bsonType": "int",
                                    "minimum": 1,
                                    "maximum": 10000
                                },
                                "skip": {
                                    "bsonType": "bool"
                                },
                                "custom_tags": {
                                    "bsonType": "array",
                                    "maxItems": 20,
                                    "items": {
                                        "bsonType": "string"
                                    }
                                },
                                "note": {
                                    "bsonType": ["string", "null"],
                                    "maxLength": 500
                                },
                                "added_at": {
                                    "bsonType": "date",
                                    "description": "When item was added"
                                }
                            }
                        },
                        "description": "Suite test items"
                    },
                    "created_at": {
                        "bsonType": "date",
                        "description": "Creation timestamp"
                    },
                    "updated_at": {
                        "bsonType": ["date", "null"],
                        "description": "Update timestamp"
                    },
                    "_schema_version": {
                        "bsonType": "string",
                        "description": "Schema version for migrations"
                    }
                }
            }
        }
    
    @staticmethod
    def validate_document(data: Dict[str, Any]) -> bool:
        """
        Validate test suite document structure and constraints.
        
        Performs comprehensive validation of document fields,
        business rules, and data integrity constraints.
        
        Args:
            data: Test suite document to validate
            
        Returns:
            True if document is valid
            
        Raises:
            ValueError: If validation fails with specific error message
        """
        try:
            # Basic structure validation
            if not isinstance(data, dict):
                raise ValueError("Document must be a dictionary")
            
            # Required fields validation
            required_fields = ["title", "owner_id", "created_by", "created_at"]
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Required field '{field}' is missing")
            
            # Title validation
            title = data.get("title")
            if not title or not isinstance(title, str) or len(title.strip()) == 0:
                raise ValueError("Title must be a non-empty string")
            
            if len(title) > 200:
                raise ValueError("Title must not exceed 200 characters")
            
            # ObjectId validation
            for field in ["owner_id", "created_by"]:
                if not ObjectId.is_valid(data.get(field, "")):
                    raise ValueError(f"Field '{field}' must be a valid ObjectId")
            
            # Schema version validation
            if "_schema_version" not in data:
                logger.warning("Missing _schema_version field, adding default")
                data["_schema_version"] = "1.0"
            
            # Items validation
            items = data.get("items", [])
            if not isinstance(items, list):
                raise ValueError("Items must be a list")
            
            if len(items) > 1000:
                raise ValueError("Suite cannot contain more than 1000 items")
            
            # Validate item uniqueness and order
            test_item_ids = set()
            orders = set()
            
            for item in items:
                if not isinstance(item, dict):
                    raise ValueError("Each item must be a dictionary")
                
                test_item_id = item.get("test_item_id")
                if not test_item_id or not ObjectId.is_valid(test_item_id):
                    raise ValueError("Item test_item_id must be a valid ObjectId")
                
                if test_item_id in test_item_ids:
                    raise ValueError(f"Duplicate test item ID: {test_item_id}")
                test_item_ids.add(test_item_id)
                
                order = item.get("order")
                if not isinstance(order, int) or order < 1:
                    raise ValueError("Item order must be a positive integer")
                
                if order in orders:
                    raise ValueError(f"Duplicate order value: {order}")
                orders.add(order)
            
            # Document size estimation (MongoDB 16MB limit)
            import json
            estimated_size = len(json.dumps(data, default=str))
            if estimated_size > 15 * 1024 * 1024:  # 15MB warning threshold
                logger.warning(
                    f"Document size approaching MongoDB limit: {estimated_size / 1024 / 1024:.2f}MB",
                    extra={"document_size": estimated_size, "suite_id": data.get("_id")}
                )
            
            return True
            
        except Exception as e:
            logger.error(
                f"Document validation failed: {e}",
                extra={"data": data, "error": str(e)}
            )
            raise ValueError(f"Document validation failed: {str(e)}")
    
    def get_collection_settings(self) -> Dict[str, Any]:
        """
        Get collection creation settings.
        
        Returns:
            MongoDB collection settings for optimal performance
        """
        return {
            "validator": self.get_collection_validation(),
            "validationLevel": "moderate",  # Allow updates to existing invalid docs
            "validationAction": "warn"      # Log validation failures but allow operations
        } 
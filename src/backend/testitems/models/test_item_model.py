"""
Test Item MongoDB Model

Implements the hybrid embedded + referenced schema design for test items.
Core data is embedded for fast access, large data is referenced for efficiency.
Extended with multi-test type support for GENERIC, BDD, and MANUAL test types.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List, Union
from enum import Enum
from pydantic import BaseModel, Field
from bson import ObjectId

from ...config.env import get_settings
from ...config.logging import get_logger
# Import multi-test type support
from ...testtypes import TestType, TestTypeValidatorFactory
from ...testtypes.models.base import TestTypeData, BDDTestData, ManualTestData, GenericTestData

logger = get_logger(__name__)


class TestItemStatus(str, Enum):
    """Test item status enumeration."""
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class StepType(str, Enum):
    """Test step type enumeration."""
    GHERKIN = "gherkin"
    NATURAL = "natural"
    STRUCTURED = "structured"


class CreatedSource(str, Enum):
    """Source of test item creation."""
    MANUAL = "manual"
    AI_GENERATED = "ai_generated"
    IMPORTED = "imported"


class TestItemSteps(BaseModel):
    """Embedded test steps structure."""
    type: StepType = Field(..., description="Type of test steps")
    content: List[str] = Field(..., description="List of test step content")
    step_count: int = Field(..., description="Number of steps")
    
    class Config:
        use_enum_values = True


class TestItemSelectors(BaseModel):
    """Embedded selector structure with primary and fallback selectors."""
    primary: Dict[str, str] = Field(..., description="Primary selectors for UI elements")
    fallback: Optional[Dict[str, str]] = Field(None, description="Fallback selectors")
    reliability_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Selector reliability score")


class TestItemMetadata(BaseModel):
    """Embedded metadata structure."""
    tags: List[str] = Field(default_factory=list, description="Test item tags")
    status: TestItemStatus = Field(default=TestItemStatus.DRAFT, description="Test item status")
    ai_confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="AI confidence score")
    auto_healing_enabled: bool = Field(default=False, description="Auto-healing enabled flag")
    execution_stats: Optional[Dict[str, Any]] = Field(None, description="Execution statistics")


class TestItemAudit(BaseModel):
    """Embedded audit trail structure."""
    created_by_user_id: str = Field(..., description="User ID who created the test item")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    created_source: CreatedSource = Field(default=CreatedSource.MANUAL, description="Source of creation")
    version: int = Field(default=1, description="Document version for schema migration")
    
    class Config:
        use_enum_values = True


class TestItemModel(BaseModel):
    """
    Test Item MongoDB document model.
    
    Implements hybrid embedded + referenced design:
    - Core data embedded for performance
    - Large data referenced for efficiency
    - Multi-test type support with type-specific validation
    """
    
    id: Optional[str] = Field(None, alias="_id", description="MongoDB document ID")
    title: str = Field(..., min_length=1, max_length=200, description="Test item title")
    feature_id: str = Field(..., description="Associated feature identifier")
    scenario_id: str = Field(..., description="Associated scenario identifier")
    
    # Embedded core data (frequently accessed)
    steps: TestItemSteps = Field(..., description="Test steps information")
    selectors: TestItemSelectors = Field(..., description="UI element selectors")
    metadata: TestItemMetadata = Field(default_factory=TestItemMetadata, description="Test metadata")
    audit: TestItemAudit = Field(..., description="Audit trail information")
    
    # Multi-test type support fields
    test_type: TestType = Field(default=TestType.GENERIC, description="Test type classification")
    type_data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Type-specific data")
    
    # Referenced large data
    dom_snapshot_id: Optional[str] = Field(None, description="Reference to DOM snapshot document")
    execution_history_id: Optional[str] = Field(None, description="Reference to execution history document")
    
    # Schema versioning
    schema_version: str = Field(default="1.0", description="Schema version for migrations")
    
    class Config:
        """Pydantic model configuration."""
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat(),
        }
        use_enum_values = True
    
    @classmethod
    def from_mongo(cls, data: Dict[str, Any]) -> Optional["TestItemModel"]:
        """
        Create TestItemModel instance from MongoDB document.
        
        Args:
            data: Raw MongoDB document
            
        Returns:
            TestItemModel instance or None if data is invalid
        """
        if not data:
            return None
            
        try:
            # Convert ObjectId to string for the id field
            if "_id" in data:
                data["_id"] = str(data["_id"])
                
            # Convert ObjectId references to strings
            if "dom_snapshot_id" in data and isinstance(data["dom_snapshot_id"], ObjectId):
                data["dom_snapshot_id"] = str(data["dom_snapshot_id"])
                
            if "execution_history_id" in data and isinstance(data["execution_history_id"], ObjectId):
                data["execution_history_id"] = str(data["execution_history_id"])
            
            return cls(**data)
            
        except Exception as e:
            logger.error(f"Failed to create TestItemModel from MongoDB data: {e}", extra={"data": data})
            return None
    
    def validate_type_data(self) -> Dict[str, Any]:
        """
        Validate type_data against the test_type using TestTypeValidatorFactory.
        
        Returns:
            Validated and cleaned type data dictionary
            
        Raises:
            ValueError: If validation fails
        """
        if not self.type_data:
            logger.debug(f"No type_data provided for test type {self.test_type}, skipping validation")
            return {}
        
        try:
            validated_data = TestTypeValidatorFactory.validate_type_data(
                self.test_type, 
                self.type_data
            )
            
            logger.info(
                f"Successfully validated type_data for test type {self.test_type}",
                extra={
                    "test_type": self.test_type.value if hasattr(self.test_type, 'value') else str(self.test_type),
                    "test_item_id": self.id or "new"
                }
            )
            
            return validated_data
            
        except Exception as e:
            logger.error(
                f"Type data validation failed for {self.test_type}: {e}",
                extra={
                    "test_type": self.test_type.value if hasattr(self.test_type, 'value') else str(self.test_type),
                    "test_item_id": self.id or "new",
                    "error": str(e)
                }
            )
            raise ValueError(f"Type data validation failed for {self.test_type}: {e}")
    
    def get_typed_data(self) -> Optional[Union[BDDTestData, ManualTestData, GenericTestData]]:
        """
        Convert type_data dict into a strongly typed Pydantic model.
        
        Returns:
            Typed data model instance or None if no type_data
            
        Raises:
            ValueError: If type_data cannot be converted to typed model
        """
        if not self.type_data:
            return None
        
        try:
            # Get the appropriate schema class for the test type
            schema_class = TestTypeValidatorFactory.get_schema(self.test_type)
            
            # Create a copy of type_data and ensure test_type is set
            data_copy = self.type_data.copy()
            data_copy['type'] = self.test_type
            
            # Create the typed model instance
            typed_data = schema_class(**data_copy)
            
            logger.debug(
                f"Successfully created typed data for test type {self.test_type}",
                extra={
                    "test_type": self.test_type.value if hasattr(self.test_type, 'value') else str(self.test_type),
                    "test_item_id": self.id or "new"
                }
            )
            
            return typed_data
            
        except Exception as e:
            logger.error(
                f"Failed to create typed data for {self.test_type}: {e}",
                extra={
                    "test_type": self.test_type.value if hasattr(self.test_type, 'value') else str(self.test_type),
                    "test_item_id": self.id or "new",
                    "error": str(e)
                }
            )
            raise ValueError(f"Failed to create typed data for {self.test_type}: {e}")
    
    def to_mongo(self) -> Dict[str, Any]:
        """
        Convert TestItemModel to MongoDB document format.
        
        Returns:
            Dictionary suitable for MongoDB insertion
        """
        data = self.model_dump(by_alias=True, exclude_unset=True)
        
        # Remove None values to keep documents lean
        data = {k: v for k, v in data.items() if v is not None}
        
        # Convert string id back to ObjectId for MongoDB
        if "_id" in data and isinstance(data["_id"], str):
            try:
                data["_id"] = ObjectId(data["_id"])
            except Exception:
                # If conversion fails, remove the field to let MongoDB generate one
                del data["_id"]
        
        # Convert reference IDs to ObjectId
        if "dom_snapshot_id" in data and isinstance(data["dom_snapshot_id"], str):
            try:
                data["dom_snapshot_id"] = ObjectId(data["dom_snapshot_id"])
            except Exception:
                del data["dom_snapshot_id"]
                
        if "execution_history_id" in data and isinstance(data["execution_history_id"], str):
            try:
                data["execution_history_id"] = ObjectId(data["execution_history_id"])
            except Exception:
                del data["execution_history_id"]
        
        return data
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert TestItemModel to plain dictionary for API responses.
        
        Returns:
            Dictionary with serialized test item data including type-specific fields
        """
        base_dict = {
            "id": self.id,
            "title": self.title,
            "feature_id": self.feature_id,
            "scenario_id": self.scenario_id,
            "steps": self.steps.model_dump(),
            "selectors": self.selectors.model_dump(),
            "metadata": self.metadata.model_dump(),
            "audit": {
                **self.audit.model_dump(),
                "created_at": self.audit.created_at.isoformat() if self.audit.created_at else None,
                "updated_at": self.audit.updated_at.isoformat() if self.audit.updated_at else None,
            },
            "test_type": self.test_type.value if hasattr(self.test_type, 'value') else str(self.test_type),
            "type_data": self.type_data or {},
            "dom_snapshot_id": self.dom_snapshot_id,
            "execution_history_id": self.execution_history_id,
            "schema_version": self.schema_version
        }
        
        return base_dict
    
    def update_metadata(self, **kwargs) -> None:
        """
        Update test item metadata and audit trail.
        
        Args:
            **kwargs: Metadata fields to update
        """
        # Update metadata fields
        for key, value in kwargs.items():
            if hasattr(self.metadata, key):
                setattr(self.metadata, key, value)
        
        # Update audit trail
        self.audit.updated_at = datetime.utcnow()
        self.audit.version += 1
        
        logger.info(
            f"Updated test item metadata: {self.title}",
            extra={
                "test_item_id": self.id,
                "title": self.title,
                "updated_fields": list(kwargs.keys()),
                "version": self.audit.version,
            }
        )


class TestItemModelOperations:
    """
    Helper class for MongoDB operations on test item documents.
    Provides database interaction methods with proper error handling.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.collection_name = "test_items"  # MongoDB collection name
    
    @staticmethod
    def get_indexes() -> List[Dict[str, Any]]:
        """
        Get MongoDB indexes for the test_items collection.
        Includes multi-test type support with test_type field indexing.
        
        Returns:
            List of index specifications for optimal query performance
        """
        return [
            # Primary compound index for user + status + test_type queries
            {
                "key": [
                    ("audit.created_by_user_id", 1),
                    ("metadata.status", 1),
                    ("test_type", 1),
                    ("audit.created_at", -1)
                ],
                "name": "user_status_type_created_idx",
                "background": True
            },
            # Feature-based queries with test type support
            {
                "key": [
                    ("feature_id", 1),
                    ("scenario_id", 1),
                    ("test_type", 1),
                    ("metadata.status", 1)
                ],
                "name": "feature_scenario_type_status_idx",
                "background": True
            },
            # Test type focused queries
            {
                "key": [
                    ("test_type", 1),
                    ("audit.created_at", -1)
                ],
                "name": "test_type_created_idx",
                "background": True
            },
            # Tag-based queries
            {
                "key": [
                    ("metadata.tags", 1),
                    ("test_type", 1),
                    ("audit.created_at", -1)
                ],
                "name": "tags_type_created_idx",
                "background": True
            },
            # Text search index
            {
                "key": [
                    ("title", "text"),
                    ("steps.content", "text")
                ],
                "name": "text_search_idx",
                "background": True
            },
            # AI and execution stats queries with test type
            {
                "key": [
                    ("test_type", 1),
                    ("metadata.ai_confidence_score", -1),
                    ("metadata.auto_healing_enabled", 1)
                ],
                "name": "type_ai_confidence_healing_idx",
                "background": True
            }
        ]
    
    @staticmethod
    def validate_document(data: Dict[str, Any]) -> bool:
        """
        Validate test item document structure.
        
        Args:
            data: Document data to validate
            
        Returns:
            True if document is valid
        """
        required_fields = ["title", "feature_id", "scenario_id", "steps", "selectors", "audit"]
        
        for field in required_fields:
            if field not in data:
                logger.error(f"Missing required field: {field}")
                return False
        
        # Validate steps structure
        if "steps" in data:
            steps = data["steps"]
            if not isinstance(steps, dict) or "type" not in steps or "content" not in steps:
                logger.error("Invalid steps structure")
                return False
        
        # Validate selectors structure
        if "selectors" in data:
            selectors = data["selectors"]
            if not isinstance(selectors, dict) or "primary" not in selectors:
                logger.error("Invalid selectors structure")
                return False
        
        return True 
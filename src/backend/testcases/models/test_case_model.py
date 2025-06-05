"""
Test Case MongoDB Model

MongoDB document model for test case management with embedded step blocks.
Implements comprehensive validation, indexing strategy, and intelligent features
following the creative phase architectural decisions for optimal performance.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from enum import Enum
from pydantic import BaseModel, Field, field_validator, ConfigDict
from bson import ObjectId

from ...config.env import get_settings
from ...config.logging import get_logger
from ...testtypes.enums import TestType

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
        """Create model instance from MongoDB document."""
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
        """Convert model to MongoDB document format."""
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


# Test Case Status Management
class TestCaseStatus(str, Enum):
    """Test case lifecycle status enumeration."""
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class TestCasePriority(str, Enum):
    """Test case priority enumeration."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# Step Architecture - Unified Embedded Schema with Type-Aware Validation
class StepType(str, Enum):
    """Step classification for validation and presentation."""
    ACTION = "action"           # Standard action step
    VERIFICATION = "verification"  # Result verification step
    SETUP = "setup"            # Precondition setup
    CLEANUP = "cleanup"        # Postcondition cleanup
    GIVEN = "given"            # BDD Given step
    WHEN = "when"              # BDD When step
    THEN = "then"              # BDD Then step


class StepFormatHint(str, Enum):
    """Format hints for step presentation and editing."""
    PLAIN = "plain"            # Plain text
    MARKDOWN = "markdown"      # Markdown formatting
    CODE = "code"              # Code block
    TEMPLATE = "template"      # Parameterized template


class TestCaseStep(BaseModel):
    """
    Unified step schema supporting all test types with type-aware validation.
    
    Implements the creative phase decision for embedded step storage with
    flexibility for GENERIC, BDD, and MANUAL test types.
    """
    
    # Core step data
    order: int = Field(..., ge=1, description="1-based step ordering")
    action: str = Field(..., min_length=1, max_length=1000, description="Step action description")
    expected: Optional[str] = Field(None, max_length=500, description="Expected result for this step")
    
    # Type-specific enhancements
    step_type: StepType = Field(default=StepType.ACTION, description="Step classification")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Parameterized inputs")
    
    # Contextual information
    preconditions: Optional[List[str]] = Field(default_factory=list, description="Prerequisites for this step")
    postconditions: Optional[List[str]] = Field(default_factory=list, description="State after step execution")
    notes: Optional[str] = Field(None, max_length=500, description="Additional context or hints")
    
    # Integration and references
    test_item_ref: Optional[str] = Field(None, description="Reference to reusable TestItem step")
    external_refs: Optional[List[str]] = Field(default_factory=list, description="External tool or documentation links")
    
    # Formatting and presentation
    format_hint: StepFormatHint = Field(default=StepFormatHint.PLAIN, description="Rendering format")
    is_template: bool = Field(default=False, description="Whether this step serves as a template")
    
    # Extensibility
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Type-specific or custom data")
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
        }
    )
    
    @field_validator('action')
    @classmethod
    def validate_action_content(cls, v):
        """Validate action content is meaningful."""
        if not v or not v.strip():
            raise ValueError("Action content cannot be empty")
        return v.strip()
    
    @field_validator('parameters')
    @classmethod
    def validate_parameters(cls, v):
        """Validate parameters dictionary."""
        if v is None:
            return {}
        # Ensure parameters are JSON-serializable
        try:
            import json
            json.dumps(v)
        except (TypeError, ValueError):
            raise ValueError("Parameters must be JSON-serializable")
        return v
    
    @field_validator('preconditions', 'postconditions', 'external_refs')
    @classmethod
    def validate_string_lists(cls, v):
        """Validate string list fields."""
        if v is None:
            return []
        return [item.strip() for item in v if item.strip()]


class AttachmentRef(BaseModel):
    """Reference to file attachments or external resources."""
    
    name: str = Field(..., min_length=1, max_length=200, description="Attachment name")
    url: str = Field(..., min_length=1, description="Attachment URL or file path")
    type: str = Field(..., description="Attachment type (image, document, link)")
    size: Optional[int] = Field(None, ge=0, description="File size in bytes")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Login Test Screenshot",
                "url": "https://example.com/screenshots/login_test.png",
                "type": "image",
                "size": 1024000
            }
        }
    )


class TestCaseModel(BaseMongoModel):
    """
    Test Case MongoDB document model.
    
    Implements atomic, reusable, testable units with embedded step blocks,
    intelligent tagging, and lifecycle management following clean architecture.
    """
    
    # Core identification
    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Test case title (unique per user)"
    )
    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Test case description"
    )
    
    # Test structure - Embedded Step Blocks
    steps: List[TestCaseStep] = Field(
        default_factory=list,
        description="Embedded step objects with type-aware validation",
        max_length=100  # Reasonable limit for performance
    )
    expected_result: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Clear expected outcome"
    )
    preconditions: Optional[List[str]] = Field(
        default_factory=list,
        description="Setup requirements",
        max_length=20
    )
    postconditions: Optional[List[str]] = Field(
        default_factory=list,
        description="Cleanup requirements",
        max_length=20
    )
    
    # Classification
    test_type: TestType = Field(
        default=TestType.GENERIC,
        description="Test type classification"
    )
    priority: TestCasePriority = Field(
        default=TestCasePriority.MEDIUM,
        description="Test case priority"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Categorization tags with normalization",
        max_length=50
    )
    
    # Lifecycle management
    status: TestCaseStatus = Field(
        default=TestCaseStatus.DRAFT,
        description="Test case status"
    )
    owner_id: str = Field(
        ...,
        description="User who created the test case"
    )
    
    # Integration references
    related_test_items: List[str] = Field(
        default_factory=list,
        description="ObjectId references to TestItem",
        max_length=50
    )
    suite_references: List[str] = Field(
        default_factory=list,
        description="ObjectId references to TestSuite (computed field)",
        max_length=100
    )
    
    # Optional extensions
    references: Optional[List[str]] = Field(
        default_factory=list,
        description="External links, requirements IDs",
        max_length=20
    )
    attachments: Optional[List[AttachmentRef]] = Field(
        default_factory=list,
        description="File references",
        max_length=10
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extensible metadata"
    )
    
    # Creator tracking
    created_by: str = Field(
        ...,
        description="User ID who created the test case"
    )
    
    # Soft deletion
    is_archived: bool = Field(
        default=False,
        description="Soft deletion flag"
    )
    
    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        json_encoders={
            ObjectId: str,
            datetime: lambda v: v.isoformat() if v else None,
        }
    )
    
    @field_validator('title')
    @classmethod
    def validate_title(cls, v):
        """Validate title content."""
        if not v or not v.strip():
            raise ValueError("Title cannot be empty")
        return v.strip()
    
    @field_validator('owner_id', 'created_by')
    @classmethod
    def validate_user_ids(cls, v):
        """Validate user ID format."""
        if not v or len(v) != 24:
            raise ValueError("User ID must be a valid 24-character MongoDB ObjectId")
        return v
    
    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v):
        """Validate and normalize tags."""
        if v is None:
            return []
        
        # Normalize tags: lowercase, strip whitespace, remove duplicates
        normalized_tags = []
        seen = set()
        for tag in v:
            if isinstance(tag, str):
                normalized_tag = tag.lower().strip()
                if normalized_tag and normalized_tag not in seen:
                    normalized_tags.append(normalized_tag)
                    seen.add(normalized_tag)
        
        return normalized_tags
    
    @field_validator('steps')
    @classmethod
    def validate_steps_order(cls, v):
        """Validate step ordering is sequential."""
        if not v:
            return v
        
        orders = [step.order for step in v]
        expected_orders = list(range(1, len(v) + 1))
        
        if sorted(orders) != expected_orders:
            raise ValueError("Step orders must be sequential starting from 1")
        
        return v
    
    @field_validator('related_test_items', 'suite_references')
    @classmethod
    def validate_object_id_lists(cls, v):
        """Validate ObjectId reference lists."""
        if v is None:
            return []
        
        validated_ids = []
        for item_id in v:
            if isinstance(item_id, str) and len(item_id) == 24:
                try:
                    ObjectId(item_id)  # Validate ObjectId format
                    validated_ids.append(item_id)
                except Exception:
                    logger.warning(f"Invalid ObjectId format: {item_id}")
        
        return validated_ids
    
    def add_step(self, step: TestCaseStep) -> None:
        """Add a new step with automatic ordering."""
        step.order = len(self.steps) + 1
        self.steps.append(step)
        self.update_timestamp()
    
    def remove_step(self, step_order: int, rebalance: bool = True) -> bool:
        """Remove a step by order and optionally rebalance orders."""
        initial_count = len(self.steps)
        self.steps = [step for step in self.steps if step.order != step_order]
        
        if len(self.steps) < initial_count:
            if rebalance:
                # Rebalance step orders
                for i, step in enumerate(sorted(self.steps, key=lambda s: s.order)):
                    step.order = i + 1
            self.update_timestamp()
            return True
        
        return False
    
    def get_step_by_order(self, order: int) -> Optional[TestCaseStep]:
        """Get step by order number."""
        for step in self.steps:
            if step.order == order:
                return step
        return None
    
    def normalize_tags(self) -> List[str]:
        """Get normalized tags for consistent storage."""
        return [tag.lower().strip() for tag in self.tags if tag.strip()]
    
    def add_tag(self, tag: str) -> bool:
        """Add a tag if not already present."""
        normalized_tag = tag.lower().strip()
        if normalized_tag and normalized_tag not in [t.lower() for t in self.tags]:
            self.tags.append(normalized_tag)
            self.update_timestamp()
            return True
        return False
    
    def remove_tag(self, tag: str) -> bool:
        """Remove a tag."""
        normalized_tag = tag.lower().strip()
        initial_count = len(self.tags)
        self.tags = [t for t in self.tags if t.lower() != normalized_tag]
        
        if len(self.tags) < initial_count:
            self.update_timestamp()
            return True
        return False
    
    def update_status(self, new_status: TestCaseStatus) -> None:
        """Update status with timestamp."""
        if self.status != new_status:
            self.status = new_status
            self.update_timestamp()
    
    def get_steps_by_type(self, step_type: StepType) -> List[TestCaseStep]:
        """Get steps filtered by type."""
        return [step for step in self.steps if step.step_type == step_type]
    
    def has_bdd_structure(self) -> bool:
        """Check if test case follows BDD Given-When-Then structure."""
        bdd_types = {StepType.GIVEN, StepType.WHEN, StepType.THEN}
        step_types = {step.step_type for step in self.steps}
        return len(bdd_types.intersection(step_types)) >= 2
    
    def get_complexity_score(self) -> float:
        """Calculate test case complexity score based on various factors."""
        base_score = len(self.steps) * 0.1
        
        # Factor in step complexity
        complexity_factors = {
            StepType.SETUP: 0.2,
            StepType.CLEANUP: 0.2,
            StepType.VERIFICATION: 0.3,
            StepType.ACTION: 0.1,
            StepType.GIVEN: 0.1,
            StepType.WHEN: 0.2,
            StepType.THEN: 0.3,
        }
        
        for step in self.steps:
            base_score += complexity_factors.get(step.step_type, 0.1)
            if step.parameters:
                base_score += 0.1
            if step.preconditions:
                base_score += len(step.preconditions) * 0.05
        
        return min(round(base_score, 2), 10.0)  # Cap at 10.0


class TestCaseModelOperations:
    """
    Test Case Model Operations and Index Management.
    
    Provides index definitions, validation schemas, and collection settings
    for optimal MongoDB performance and data integrity.
    """
    
    def __init__(self):
        """Initialize test case model operations."""
        self.settings = get_settings()
    
    @staticmethod
    def get_indexes() -> List[Dict[str, Any]]:
        """
        Get MongoDB index definitions for test case collection.
        
        Implements the 6-index strategy from the creative phase for optimal performance:
        1. Primary Index: owner_id + status + created_at
        2. Search Index: owner_id + tags + test_type  
        3. Title Uniqueness: owner_id + title (unique)
        4. Priority Filter: owner_id + priority + status
        5. Integration Index: related_test_items (sparse)
        6. Archive TTL: status + updated_at with TTL for archived cases
        """
        return [
            {
                "keys": {"owner_id": 1, "status": 1, "created_at": -1},
                "name": "idx_owner_status_created",
                "background": True,
            },
            {
                "keys": {"owner_id": 1, "tags": 1, "test_type": 1},
                "name": "idx_owner_tags_type",
                "background": True,
            },
            {
                "keys": {"owner_id": 1, "title": 1},
                "name": "idx_owner_title_unique",
                "unique": True,
                "background": True,
            },
            {
                "keys": {"owner_id": 1, "priority": 1, "status": 1},
                "name": "idx_owner_priority_status",
                "background": True,
            },
            {
                "keys": {"related_test_items": 1},
                "name": "idx_related_items_sparse",
                "sparse": True,
                "background": True,
            },
            {
                "keys": {"status": 1, "updated_at": 1},
                "name": "idx_status_updated_ttl",
                "background": True,
                "expireAfterSeconds": 31536000,  # 1 year TTL for archived cases
                "partialFilterExpression": {"status": "archived"}
            },
        ]
    
    @staticmethod
    def get_collection_validation() -> Dict[str, Any]:
        """Get MongoDB collection validation schema."""
        return {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["title", "expected_result", "test_type", "status", "owner_id", "created_by"],
                "properties": {
                    "title": {
                        "bsonType": "string",
                        "minLength": 1,
                        "maxLength": 200,
                        "description": "Test case title"
                    },
                    "expected_result": {
                        "bsonType": "string",
                        "minLength": 1,
                        "maxLength": 1000,
                        "description": "Expected test outcome"
                    },
                    "test_type": {
                        "enum": ["generic", "bdd", "manual"],
                        "description": "Test type classification"
                    },
                    "status": {
                        "enum": ["draft", "active", "deprecated", "archived"],
                        "description": "Test case lifecycle status"
                    },
                    "priority": {
                        "enum": ["high", "medium", "low"],
                        "description": "Test case priority"
                    },
                    "owner_id": {
                        "bsonType": "string",
                        "pattern": "^[0-9a-fA-F]{24}$",
                        "description": "Owner user ID"
                    },
                    "created_by": {
                        "bsonType": "string",
                        "pattern": "^[0-9a-fA-F]{24}$",
                        "description": "Creator user ID"
                    },
                    "tags": {
                        "bsonType": "array",
                        "maxItems": 50,
                        "items": {
                            "bsonType": "string",
                            "maxLength": 50
                        }
                    },
                    "steps": {
                        "bsonType": "array",
                        "maxItems": 100,
                        "items": {
                            "bsonType": "object",
                            "required": ["order", "action"],
                            "properties": {
                                "order": {
                                    "bsonType": "int",
                                    "minimum": 1
                                },
                                "action": {
                                    "bsonType": "string",
                                    "minLength": 1,
                                    "maxLength": 1000
                                }
                            }
                        }
                    }
                }
            }
        }
    
    def get_collection_settings(self) -> Dict[str, Any]:
        """Get collection settings for test cases."""
        return {
            "validator": self.get_collection_validation(),
            "validationLevel": "moderate",
            "validationAction": "warn"
        } 
"""
Test Item Service Layer

Business logic and database operations for test item management.
Implements CRUD operations with filtering, pagination, and query optimization.
Extended with multi-test type support for GENERIC, BDD, and MANUAL test types.
"""

import math
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple, Set
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from ...config.env import get_settings
from ...config.logging import get_logger
from ...testtypes import TestType, TestTypeValidatorFactory
from ..models.test_item_model import (
    TestItemModel, 
    TestItemSteps, 
    TestItemSelectors, 
    TestItemMetadata, 
    TestItemAudit,
    TestItemModelOperations,
    TestItemStatus,
    StepType,
    CreatedSource
)
from ..schemas.test_item_schemas import (
    CreateTestItemRequest,
    FilterTestItemsRequest,
    TestItemResponse,
    TestItemResponseBuilder,
    PaginationMeta,
    FilterMeta,
    SortMeta
)

logger = get_logger(__name__)


class TestItemService:
    """
    Test Item Service for business logic and database operations.
    
    Provides comprehensive test item management with optimized queries,
    pagination, filtering, and response building following the creative design.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        """
        Initialize test item service.
        
        Args:
            db: MongoDB database instance
        """
        self.db = db
        self.collection = db.test_items
        self.settings = get_settings()
        self.operations = TestItemModelOperations()
        
        logger.info("TestItemService initialized")
    
    async def create_test_item(
        self, 
        request: CreateTestItemRequest, 
        user_id: str
    ) -> TestItemModel:
        """
        Create a new test item with multi-test type support.
        
        Args:
            request: Test item creation request
            user_id: ID of the user creating the test item
            
        Returns:
            Created TestItemModel instance
            
        Raises:
            ValueError: If request validation fails
            Exception: If database operation fails
        """
        logger.info(
            f"Creating test item: {request.title}",
            extra={
                "user_id": user_id,
                "feature_id": request.feature_id,
                "scenario_id": request.scenario_id,
                "test_type": request.test_type.value if hasattr(request.test_type, 'value') else str(request.test_type)
            }
        )
        
        try:
            # Validate and clean type_data using the factory
            validated_type_data = {}
            if request.type_data:
                try:
                    validated_type_data = TestTypeValidatorFactory.validate_type_data(
                        request.test_type, 
                        request.type_data
                    )
                    logger.info(
                        f"Successfully validated type_data for {request.test_type}",
                        extra={
                            "test_type": request.test_type.value if hasattr(request.test_type, 'value') else str(request.test_type),
                            "data_size": len(str(request.type_data))
                        }
                    )
                except Exception as e:
                    logger.error(
                        f"Type data validation failed: {e}",
                        extra={
                            "test_type": request.test_type.value if hasattr(request.test_type, 'value') else str(request.test_type),
                            "error": str(e)
                        }
                    )
                    raise ValueError(f"Type data validation failed for {request.test_type}: {e}")
            
            # Create steps model with calculated step count
            steps = TestItemSteps(
                type=request.steps.type,
                content=request.steps.content,
                step_count=len(request.steps.content)
            )
            
            # Create selectors model
            selectors = TestItemSelectors(
                primary=request.selectors.primary,
                fallback=request.selectors.fallback,
                reliability_score=request.selectors.reliability_score
            )
            
            # Create metadata with defaults
            metadata = TestItemMetadata(
                tags=request.tags or [],
                status=TestItemStatus.DRAFT,  # New items start as draft
                ai_confidence_score=request.ai_confidence_score,
                auto_healing_enabled=request.auto_healing_enabled or False
            )
            
            # Create audit trail
            now = datetime.utcnow()
            audit = TestItemAudit(
                created_by_user_id=user_id,
                created_at=now,
                created_source=CreatedSource.MANUAL
            )
            
            # Create test item model with multi-test type support
            test_item = TestItemModel(
                title=request.title,
                feature_id=request.feature_id,
                scenario_id=request.scenario_id,
                steps=steps,
                selectors=selectors,
                metadata=metadata,
                audit=audit,
                test_type=request.test_type,
                type_data=validated_type_data,
                dom_snapshot_id=request.dom_snapshot_id
            )
            
            # Validate before insertion
            test_item_doc = test_item.to_mongo()
            if not self.operations.validate_document(test_item_doc):
                raise ValueError("Invalid test item document structure")
            
            # Insert into MongoDB
            result = await self.collection.insert_one(test_item_doc)
            test_item.id = str(result.inserted_id)
            
            logger.info(
                f"Test item created successfully: {test_item.id}",
                extra={
                    "test_item_id": test_item.id,
                    "title": test_item.title,
                    "test_type": test_item.test_type.value if hasattr(test_item.test_type, 'value') else str(test_item.test_type),
                    "user_id": user_id
                }
            )
            
            return test_item
            
        except Exception as e:
            logger.error(
                f"Failed to create test item: {e}",
                extra={
                    "user_id": user_id,
                    "title": request.title,
                    "test_type": request.test_type.value if hasattr(request.test_type, 'value') else str(request.test_type),
                    "error": str(e)
                }
            )
            raise
    
    async def get_test_item(
        self, 
        item_id: str, 
        user_id: str,
        include_fields: Optional[Set[str]] = None
    ) -> Optional[TestItemModel]:
        """
        Retrieve a test item by ID with optional type-specific data enrichment.
        
        Args:
            item_id: Test item ID
            user_id: User ID (for access control)
            include_fields: Optional fields to project
            
        Returns:
            TestItemModel instance or None if not found
        """
        logger.debug(
            f"Retrieving test item: {item_id}",
            extra={"test_item_id": item_id, "user_id": user_id}
        )
        
        try:
            # Build query with user access control
            query = {
                "_id": ObjectId(item_id),
                "audit.created_by_user_id": user_id
            }
            
            # Build projection for performance optimization
            projection = self._build_projection(include_fields)
            
            # Execute query
            document = await self.collection.find_one(query, projection)
            
            if not document:
                logger.warning(
                    f"Test item not found or access denied: {item_id}",
                    extra={"test_item_id": item_id, "user_id": user_id}
                )
                return None
            
            # Convert to model
            test_item = TestItemModel.from_mongo(document)
            
            if test_item:
                logger.debug(
                    f"Test item retrieved successfully: {item_id}",
                    extra={
                        "test_item_id": item_id,
                        "test_type": test_item.test_type.value if hasattr(test_item.test_type, 'value') else str(test_item.test_type),
                        "user_id": user_id
                    }
                )
            
            return test_item
            
        except Exception as e:
            logger.error(
                f"Failed to retrieve test item: {e}",
                extra={
                    "test_item_id": item_id,
                    "user_id": user_id,
                    "error": str(e)
                }
            )
            raise
    
    async def list_test_items(
        self,
        user_id: str,
        filters: FilterTestItemsRequest
    ) -> Tuple[List[TestItemModel], int, PaginationMeta, FilterMeta, SortMeta]:
        """
        List test items with filtering and pagination.
        
        Args:
            user_id: User ID for access control
            filters: Filter and pagination parameters
            
        Returns:
            Tuple of (items, total_count, pagination_meta, filter_meta, sort_meta)
        """
        logger.debug(
            f"Listing test items for user: {user_id}",
            extra={
                "user_id": user_id,
                "page": filters.page,
                "page_size": filters.page_size
            }
        )
        
        try:
            # Build query
            query = self._build_query(user_id, filters)
            
            # Build projection for performance
            include_fields = self._parse_include_fields(filters.include_fields)
            projection = self._build_projection(include_fields)
            
            # Build sort
            sort_spec = self._build_sort(filters.sort_by, filters.sort_order)
            
            # Calculate pagination
            skip = (filters.page - 1) * filters.page_size
            
            # Execute count query (without projection for accuracy)
            total_count = await self.collection.count_documents(query)
            
            # Execute data query with projection, sorting, and pagination
            cursor = self.collection.find(query, projection).sort(sort_spec).skip(skip).limit(filters.page_size)
            documents = await cursor.to_list(length=filters.page_size)
            
            # Convert to models
            items = []
            for doc in documents:
                item = TestItemModel.from_mongo(doc)
                if item:
                    items.append(item)
            
            # Create metadata
            pagination_meta = self._create_pagination_meta(
                filters.page, filters.page_size, total_count
            )
            
            filter_meta = self._create_filter_meta(filters)
            sort_meta = SortMeta(sort_by=filters.sort_by, sort_order=filters.sort_order)
            
            logger.info(
                f"Listed {len(items)} test items (total: {total_count})",
                extra={
                    "user_id": user_id,
                    "returned_count": len(items),
                    "total_count": total_count,
                    "page": filters.page
                }
            )
            
            return items, total_count, pagination_meta, filter_meta, sort_meta
            
        except Exception as e:
            logger.error(
                f"Failed to list test items for user {user_id}: {e}",
                extra={"user_id": user_id, "error": str(e)}
            )
            raise
    
    async def update_test_item_status(
        self,
        item_id: str,
        user_id: str,
        status: TestItemStatus
    ) -> Optional[TestItemModel]:
        """
        Update test item status.
        
        Args:
            item_id: Test item ID
            user_id: User ID for access control
            status: New status
            
        Returns:
            Updated TestItemModel or None if not found
        """
        logger.info(
            f"Updating test item status: {item_id} -> {status}",
            extra={"test_item_id": item_id, "user_id": user_id, "new_status": status}
        )
        
        try:
            query = {
                "_id": ObjectId(item_id),
                "audit.created_by_user_id": user_id
            }
            
            update = {
                "$set": {
                    "metadata.status": status.value,
                    "audit.updated_at": datetime.utcnow(),
                    "$inc": {"audit.version": 1}
                }
            }
            
            result = await self.collection.find_one_and_update(
                query,
                update,
                return_document=True
            )
            
            if result:
                return TestItemModel.from_mongo(result)
            
            return None
            
        except Exception as e:
            logger.error(
                f"Failed to update test item status {item_id}: {e}",
                extra={"test_item_id": item_id, "user_id": user_id, "error": str(e)}
            )
            raise
    
    async def get_health_status(self) -> Dict[str, Any]:
        """
        Get service health status.
        
        Returns:
            Health status information
        """
        try:
            # Test database connectivity
            await self.collection.find_one({}, {"_id": 1})
            
            # Get collection stats
            stats = await self.db.command("collStats", "test_items")
            
            return {
                "status": "healthy",
                "collection_exists": True,
                "document_count": stats.get("count", 0),
                "storage_size": stats.get("storageSize", 0),
                "indexes": len(stats.get("indexSizes", {}))
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    def _build_query(self, user_id: str, filters: FilterTestItemsRequest) -> Dict[str, Any]:
        """
        Build MongoDB query from filters with multi-test type support.
        
        Args:
            user_id: User ID for access control
            filters: Filter parameters including test_type
            
        Returns:
            MongoDB query dictionary
        """
        query = {"audit.created_by_user_id": user_id}
        
        # Feature filter
        if filters.feature_id:
            query["feature_id"] = filters.feature_id
        
        # Scenario filter
        if filters.scenario_id:
            query["scenario_id"] = filters.scenario_id
        
        # Status filter
        if filters.status:
            query["metadata.status"] = filters.status.value
        
        # Test type filter
        if filters.test_type:
            query["test_type"] = filters.test_type.value if hasattr(filters.test_type, 'value') else str(filters.test_type)
        
        # Tags filter (AND operation)
        if filters.tags:
            query["metadata.tags"] = {"$all": filters.tags}
        
        # Date range filters
        date_query = {}
        if filters.created_after:
            date_query["$gte"] = filters.created_after
        if filters.created_before:
            date_query["$lte"] = filters.created_before
        
        if date_query:
            query["audit.created_at"] = date_query
        
        # Text search
        if filters.search_query:
            query["$text"] = {"$search": filters.search_query}
        
        return query
    
    def _build_projection(self, include_fields: Optional[Set[str]]) -> Optional[Dict[str, int]]:
        """
        Build MongoDB projection from include fields.
        
        Args:
            include_fields: Set of fields to include
            
        Returns:
            MongoDB projection dictionary or None for all fields
        """
        if not include_fields:
            return None
        
        projection = {"_id": 1}  # Always include ID
        
        # Core fields (always needed for TestItemCore)
        core_fields = [
            "title", "feature_id", "scenario_id", 
            "audit.created_by_user_id", "audit.created_at", "audit.updated_at",
            "metadata.status", "test_type", "type_data"
        ]
        
        for field in core_fields:
            projection[field] = 1
        
        # Optional fields based on include_fields
        if "steps" in include_fields:
            projection["steps"] = 1
        
        if "selectors" in include_fields:
            projection["selectors"] = 1
        
        if "metadata" in include_fields:
            projection["metadata"] = 1
        
        if "execution_stats" in include_fields:
            projection["metadata.execution_stats"] = 1
        
        return projection
    
    def _build_sort(self, sort_by: str, sort_order: str) -> List[Tuple[str, int]]:
        """
        Build MongoDB sort specification with multi-test type support.
        
        Args:
            sort_by: Field to sort by
            sort_order: Sort order (asc/desc)
            
        Returns:
            MongoDB sort specification
        """
        direction = 1 if sort_order == "asc" else -1
        
        # Map sort fields to MongoDB fields
        field_mapping = {
            "created_at": "audit.created_at",
            "updated_at": "audit.updated_at",
            "title": "title",
            "feature_id": "feature_id",
            "scenario_id": "scenario_id",
            "test_type": "test_type"
        }
        
        mongodb_field = field_mapping.get(sort_by, "audit.created_at")
        
        return [(mongodb_field, direction)]
    
    def _parse_include_fields(self, include_fields_str: Optional[str]) -> Optional[Set[str]]:
        """
        Parse include_fields parameter.
        
        Args:
            include_fields_str: Comma-separated string of fields
            
        Returns:
            Set of field names or None
        """
        if not include_fields_str:
            return None
        
        fields = {field.strip() for field in include_fields_str.split(",") if field.strip()}
        
        # Always include core
        fields.add("core")
        
        return fields
    
    def _create_pagination_meta(
        self, 
        page: int, 
        page_size: int, 
        total_count: int
    ) -> PaginationMeta:
        """
        Create pagination metadata.
        
        Args:
            page: Current page number
            page_size: Items per page
            total_count: Total number of items
            
        Returns:
            PaginationMeta instance
        """
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 0
        
        return PaginationMeta(
            page=page,
            page_size=page_size,
            total_items=total_count,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1
        )
    
    def _create_filter_meta(self, filters: FilterTestItemsRequest) -> FilterMeta:
        """
        Create filter metadata with multi-test type support.
        
        Args:
            filters: Filter parameters including test_type
            
        Returns:
            FilterMeta instance
        """
        return FilterMeta(
            feature_id=filters.feature_id,
            scenario_id=filters.scenario_id,
            status=filters.status.value if filters.status else None,
            test_type=filters.test_type.value if hasattr(filters.test_type, 'value') else str(filters.test_type) if filters.test_type else None,
            tags=filters.tags,
            created_after=filters.created_after,
            created_before=filters.created_before,
            search_query=filters.search_query
        )
    
    async def ensure_indexes(self) -> None:
        """
        Ensure database indexes are created for optimal performance.
        """
        logger.info("Ensuring test item collection indexes")
        
        try:
            indexes = self.operations.get_indexes()
            
            for index_spec in indexes:
                await self.collection.create_index(
                    index_spec["key"],
                    name=index_spec["name"],
                    background=index_spec.get("background", True)
                )
                
            logger.info(f"Created {len(indexes)} indexes for test_items collection")
            
        except Exception as e:
            logger.error(f"Failed to create indexes: {e}")
            raise


class TestItemResponseService:
    """
    Service for building test item responses with field inclusion control.
    Implements the response builder pattern from creative design.
    """
    
    @staticmethod
    def build_response(
        test_item: TestItemModel,
        include_fields: Optional[Set[str]] = None
    ) -> TestItemResponse:
        """
        Build test item response with selective field inclusion.
        
        Args:
            test_item: TestItemModel instance
            include_fields: Set of fields to include
            
        Returns:
            TestItemResponse with selected fields
        """
        return TestItemResponseBuilder.build_from_include_fields(
            test_item, include_fields
        )
    
    @staticmethod
    def build_list_responses(
        test_items: List[TestItemModel],
        include_fields: Optional[Set[str]] = None
    ) -> List[TestItemResponse]:
        """
        Build list of test item responses with selective field inclusion.
        
        Args:
            test_items: List of TestItemModel instances
            include_fields: Set of fields to include
            
        Returns:
            List of TestItemResponse with selected fields
        """
        return [
            TestItemResponseService.build_response(item, include_fields)
            for item in test_items
        ]
    
    @staticmethod
    def create_summary_stats(
        total_count: int,
        status_counts: Optional[Dict[str, int]] = None
    ) -> Dict[str, Any]:
        """
        Create summary statistics for list responses.
        
        Args:
            total_count: Total number of items
            status_counts: Optional status breakdown
            
        Returns:
            Summary statistics dictionary
        """
        summary = {
            "total_items": total_count,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if status_counts:
            summary["status_breakdown"] = status_counts
        
        return summary 
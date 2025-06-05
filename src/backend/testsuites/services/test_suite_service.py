"""
Test Suite Service Layer

Business logic and database operations for test suite management.
Implements comprehensive CRUD operations, bulk item management, validation,
and observability following creative phase architectural decisions.
"""

import math
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple, Set, NamedTuple
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from fastapi import HTTPException

from ...config.env import get_settings
from ...config.logging import get_logger
from ..schemas.test_suite_requests import (
    CreateTestSuiteRequest,
    UpdateTestSuiteRequest,
    BulkAddItemsRequest,
    BulkRemoveItemsRequest,
    FilterTestSuitesRequest,
    TestSuitePriority,
    TestSuiteStatus
)
from ..schemas.test_suite_responses import (
    TestSuiteResponse,
    TestSuiteResponseBuilder,
    BulkOperationResult,
    BulkOperationItem,
    PaginationMeta,
    FilterMeta,
    SortMeta
)

logger = get_logger(__name__)


class ValidationResult(NamedTuple):
    """Result of test item validation operation."""
    valid_ids: Set[str]
    invalid_ids: Set[str]


class TestSuiteService:
    """
    Test Suite Service for comprehensive business logic and database operations.
    
    Implements suite CRUD operations, bulk item management, validation strategies,
    and observability patterns following the creative phase decisions.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        """
        Initialize test suite service with database client.
        
        Args:
            db: MongoDB database instance
        """
        self.db = db
        self.suite_collection = db.test_suites
        self.test_item_collection = db.test_items
        self.settings = get_settings()
        
        logger.info("TestSuiteService initialized")
    
    async def create_suite(
        self, 
        request: CreateTestSuiteRequest, 
        user_id: str
    ) -> TestSuiteResponse:
        """
        Create a new test suite with optional initial items.
        
        Implements batch validation for initial items and atomic creation
        following creative phase validation strategy.
        
        Args:
            request: Suite creation request with metadata and optional items
            user_id: ID of the user creating the suite
            
        Returns:
            Created test suite response
            
        Raises:
            HTTPException: If validation fails or creation fails
        """
        logger.info(
            f"Creating test suite: {request.title}",
            extra={
                "user_id": user_id,
                "title": request.title,
                "initial_items": len(request.suite_items),
                "priority": request.priority.value
            }
        )
        
        try:
            # Validate title uniqueness for user
            await self._validate_title_uniqueness(request.title, user_id)
            
            # Validate initial test items if provided
            validated_items = []
            if request.suite_items:
                validation_result = await self._validate_item_references(
                    [item.test_item_id for item in request.suite_items], 
                    user_id
                )
                
                if validation_result.invalid_ids:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid test item IDs: {list(validation_result.invalid_ids)}"
                    )
                
                # Filter to only valid items and convert to dict
                validated_items = [
                    item.dict() for item in request.suite_items 
                    if item.test_item_id in validation_result.valid_ids
                ]
            
            # Create suite document
            now = datetime.utcnow()
            suite_doc = {
                "title": request.title,
                "description": request.description,
                "tags": request.tags or [],
                "priority": request.priority.value,
                "status": TestSuiteStatus.DRAFT.value,
                "owner_id": user_id,
                "suite_items": validated_items,
                "total_items": len(validated_items),
                "active_items": len([item for item in validated_items if not item.get("skip", False)]),
                "created_at": now,
                "updated_at": now
            }
            
            # Atomic insertion
            result = await self.suite_collection.insert_one(suite_doc)
            suite_doc["_id"] = result.inserted_id
            
            # Track operation for observability
            await self._track_operation(
                operation="create_suite",
                suite_id=str(result.inserted_id),
                user_id=user_id,
                success=True,
                context={"items_count": len(validated_items)}
            )
            
            logger.info(
                f"Test suite created successfully: {result.inserted_id}",
                extra={
                    "suite_id": str(result.inserted_id),
                    "title": request.title,
                    "user_id": user_id,
                    "items_count": len(validated_items)
                }
            )
            
            # Build and return response
            return TestSuiteResponseBuilder.build_from_document(
                suite_doc,
                include_items=True,
                include_statistics=True,
                include_computed=True
            )
            
        except HTTPException:
            raise
        except Exception as e:
            await self._track_operation(
                operation="create_suite",
                suite_id="unknown",
                user_id=user_id,
                success=False,
                context={"error": str(e)}
            )
            logger.error(
                f"Failed to create test suite: {e}",
                extra={
                    "user_id": user_id,
                    "title": request.title,
                    "error": str(e)
                }
            )
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create test suite: {str(e)}"
            )
    
    async def get_suite(
        self, 
        suite_id: str, 
        include_fields: Optional[List[str]] = None,
        user_id: Optional[str] = None
    ) -> Optional[TestSuiteResponse]:
        """
        Get test suite by ID with optional field inclusion control.
        
        Implements performance optimization through selective field loading
        and supports owner-based access control.
        
        Args:
            suite_id: Test suite identifier
            include_fields: Optional list of fields to include (items, statistics, computed)
            user_id: Optional user ID for ownership validation
            
        Returns:
            Test suite response or None if not found
            
        Raises:
            HTTPException: If access denied or invalid suite ID
        """
        logger.info(
            f"Retrieving test suite: {suite_id}",
            extra={
                "suite_id": suite_id,
                "user_id": user_id,
                "include_fields": include_fields
            }
        )
        
        try:
            # Validate ObjectId format
            if not ObjectId.is_valid(suite_id):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid suite ID format"
                )
            
            # Build query with optional owner filter
            query = {"_id": ObjectId(suite_id)}
            if user_id:
                query["owner_id"] = user_id
            
            # Find suite
            suite_doc = await self.suite_collection.find_one(query)
            if not suite_doc:
                if user_id:
                    raise HTTPException(
                        status_code=404,
                        detail="Test suite not found or access denied"
                    )
                return None
            
            # Parse include fields
            include_items = include_fields and "items" in include_fields
            include_statistics = include_fields and "statistics" in include_fields
            include_computed = include_fields and "computed" in include_fields
            
            # Track operation
            await self._track_operation(
                operation="get_suite",
                suite_id=suite_id,
                user_id=user_id or "anonymous",
                success=True,
                context={"include_fields": include_fields}
            )
            
            logger.info(
                f"Test suite retrieved successfully: {suite_id}",
                extra={
                    "suite_id": suite_id,
                    "title": suite_doc.get("title"),
                    "user_id": user_id
                }
            )
            
            # Build response with requested fields
            return TestSuiteResponseBuilder.build_from_document(
                suite_doc,
                include_items=include_items,
                include_statistics=include_statistics,
                include_computed=include_computed
            )
            
        except HTTPException:
            raise
        except Exception as e:
            await self._track_operation(
                operation="get_suite",
                suite_id=suite_id,
                user_id=user_id or "anonymous",
                success=False,
                context={"error": str(e)}
            )
            logger.error(
                f"Failed to retrieve test suite: {e}",
                extra={
                    "suite_id": suite_id,
                    "user_id": user_id,
                    "error": str(e)
                }
            )
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve test suite: {str(e)}"
            )
    
    async def list_suites(
        self, 
        filters: FilterTestSuitesRequest, 
        user_id: str
    ) -> Tuple[List[TestSuiteResponse], PaginationMeta, FilterMeta, SortMeta]:
        """
        List test suites with comprehensive filtering, pagination, and sorting.
        
        Implements optimized queries with compound indexing and projection
        for performance following creative phase decisions.
        
        Args:
            filters: Filter, pagination, and sorting parameters
            user_id: User ID for ownership scoping
            
        Returns:
            Tuple of (suites list, pagination metadata, filter metadata, sort metadata)
            
        Raises:
            HTTPException: If query execution fails
        """
        logger.info(
            f"Listing test suites for user: {user_id}",
            extra={
                "user_id": user_id,
                "page": filters.page,
                "page_size": filters.page_size,
                "filters": filters.dict(exclude_none=True)
            }
        )
        
        try:
            # Build query with ownership scope
            query = {"owner_id": user_id}
            
            # Apply filters
            if filters.status:
                query["status"] = filters.status.value
            if filters.priority:
                query["priority"] = filters.priority.value
            if filters.tags:
                query["tags"] = {"$all": filters.tags}
            if filters.title_search:
                query["title"] = {"$regex": filters.title_search, "$options": "i"}
            if filters.has_items is not None:
                if filters.has_items:
                    query["total_items"] = {"$gt": 0}
                else:
                    query["total_items"] = {"$eq": 0}
            
            # Build sort criteria
            sort_order = 1 if filters.sort_order == "asc" else -1
            sort_criteria = [(filters.sort_by, sort_order)]
            
            # Get total count for pagination
            total_count = await self.suite_collection.count_documents(query)
            
            # Calculate pagination
            skip = (filters.page - 1) * filters.page_size
            total_pages = math.ceil(total_count / filters.page_size)
            
            # Execute paginated query
            cursor = self.suite_collection.find(query).sort(sort_criteria).skip(skip).limit(filters.page_size)
            suite_docs = await cursor.to_list(length=None)
            
            # Build responses - core only for list performance
            suites = [
                TestSuiteResponseBuilder.build_from_document(
                    doc, 
                    include_items=False,
                    include_statistics=False,
                    include_computed=False
                )
                for doc in suite_docs
            ]
            
            # Create metadata
            pagination_meta = PaginationMeta(
                page=filters.page,
                page_size=filters.page_size,
                total_items=total_count,
                total_pages=total_pages,
                has_next=filters.page < total_pages,
                has_previous=filters.page > 1
            )
            
            filter_meta = FilterMeta(
                status=filters.status.value if filters.status else None,
                priority=filters.priority.value if filters.priority else None,
                tags=filters.tags,
                title_search=filters.title_search,
                has_items=filters.has_items
            )
            
            sort_meta = SortMeta(
                sort_by=filters.sort_by,
                sort_order=filters.sort_order
            )
            
            # Track operation
            await self._track_operation(
                operation="list_suites",
                suite_id="list",
                user_id=user_id,
                success=True,
                context={
                    "total_count": total_count,
                    "returned_count": len(suites),
                    "filters_applied": len([f for f in [filters.status, filters.priority, filters.tags, filters.title_search, filters.has_items] if f is not None])
                }
            )
            
            logger.info(
                f"Test suites retrieved successfully: {len(suites)} of {total_count}",
                extra={
                    "user_id": user_id,
                    "returned_count": len(suites),
                    "total_count": total_count,
                    "page": filters.page
                }
            )
            
            return suites, pagination_meta, filter_meta, sort_meta
            
        except Exception as e:
            await self._track_operation(
                operation="list_suites",
                suite_id="list",
                user_id=user_id,
                success=False,
                context={"error": str(e)}
            )
            logger.error(
                f"Failed to list test suites: {e}",
                extra={
                    "user_id": user_id,
                    "error": str(e)
                }
            )
            raise HTTPException(
                status_code=500,
                detail=f"Failed to list test suites: {str(e)}"
            )
    
    async def update_suite(
        self, 
        suite_id: str, 
        update: UpdateTestSuiteRequest,
        user_id: str
    ) -> TestSuiteResponse:
        """
        Update test suite metadata with atomic operations.
        
        Validates ownership, field constraints, and performs atomic updates
        with comprehensive logging and observability.
        
        Args:
            suite_id: Test suite identifier
            update: Update request with partial fields
            user_id: User ID for ownership validation
            
        Returns:
            Updated test suite response
            
        Raises:
            HTTPException: If validation fails or update fails
        """
        logger.info(
            f"Updating test suite: {suite_id}",
            extra={
                "suite_id": suite_id,
                "user_id": user_id,
                "update_fields": list(update.dict(exclude_none=True).keys())
            }
        )
        
        try:
            # Validate ObjectId format
            if not ObjectId.is_valid(suite_id):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid suite ID format"
                )
            
            # Validate suite exists and user owns it
            await self._validate_suite_ownership(suite_id, user_id)
            
            # Build update document
            update_doc = {}
            update_data = update.dict(exclude_none=True)
            
            if "title" in update_data:
                # Validate title uniqueness for user (excluding current suite)
                await self._validate_title_uniqueness(update_data["title"], user_id, exclude_suite_id=suite_id)
                update_doc["title"] = update_data["title"]
            
            if "description" in update_data:
                update_doc["description"] = update_data["description"]
            
            if "tags" in update_data:
                update_doc["tags"] = update_data["tags"]
            
            if "priority" in update_data:
                update_doc["priority"] = update_data["priority"].value
            
            if "status" in update_data:
                update_doc["status"] = update_data["status"].value
            
            # Always update timestamp
            update_doc["updated_at"] = datetime.utcnow()
            
            # Atomic update
            result = await self.suite_collection.update_one(
                {"_id": ObjectId(suite_id), "owner_id": user_id},
                {"$set": update_doc}
            )
            
            if result.matched_count == 0:
                raise HTTPException(
                    status_code=404,
                    detail="Test suite not found or access denied"
                )
            
            # Get updated document
            updated_doc = await self.suite_collection.find_one({"_id": ObjectId(suite_id)})
            
            # Track operation
            await self._track_operation(
                operation="update_suite",
                suite_id=suite_id,
                user_id=user_id,
                success=True,
                context={"updated_fields": list(update_data.keys())}
            )
            
            logger.info(
                f"Test suite updated successfully: {suite_id}",
                extra={
                    "suite_id": suite_id,
                    "user_id": user_id,
                    "updated_fields": list(update_data.keys())
                }
            )
            
            return TestSuiteResponseBuilder.build_from_document(
                updated_doc,
                include_items=True,
                include_statistics=True,
                include_computed=True
            )
            
        except HTTPException:
            raise
        except Exception as e:
            await self._track_operation(
                operation="update_suite",
                suite_id=suite_id,
                user_id=user_id,
                success=False,
                context={"error": str(e)}
            )
            logger.error(
                f"Failed to update test suite: {e}",
                extra={
                    "suite_id": suite_id,
                    "user_id": user_id,
                    "error": str(e)
                }
            )
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update test suite: {str(e)}"
            )
    
    async def add_items(
        self, 
        suite_id: str, 
        request: BulkAddItemsRequest,
        user_id: str
    ) -> BulkOperationResult:
        """
        Bulk add test items to suite with comprehensive validation.
        
        Implements validated bulk operations pattern from creative phase with
        partial success handling and duplicate detection.
        
        Args:
            suite_id: Test suite identifier
            request: Bulk add request with item configurations
            user_id: User ID for ownership validation
            
        Returns:
            Bulk operation result with detailed status
            
        Raises:
            HTTPException: If validation fails or operation fails
        """
        logger.info(
            f"Bulk adding items to suite: {suite_id}",
            extra={
                "suite_id": suite_id,
                "user_id": user_id,
                "items_count": len(request.items)
            }
        )
        
        try:
            # Validate suite ownership
            await self._validate_suite_ownership(suite_id, user_id)
            
            # Validate test item references
            item_ids = [item.test_item_id for item in request.items]
            validation_result = await self._validate_item_references(item_ids, user_id)
            
            # Get existing item IDs in suite
            existing_items = await self._get_existing_item_ids(suite_id)
            
            # Process items and categorize results
            success_items = []
            failed_items = []
            
            for item in request.items:
                if item.test_item_id not in validation_result.valid_ids:
                    failed_items.append(BulkOperationItem(
                        test_item_id=item.test_item_id,
                        status="invalid",
                        message="Test item not found or access denied"
                    ))
                elif item.test_item_id in existing_items:
                    failed_items.append(BulkOperationItem(
                        test_item_id=item.test_item_id,
                        status="duplicate",
                        message="Test item already exists in suite"
                    ))
                else:
                    success_items.append(BulkOperationItem(
                        test_item_id=item.test_item_id,
                        status="success",
                        message="Item added successfully"
                    ))
            
            # Add valid items to suite
            valid_configs = [
                item.dict() for item in request.items 
                if item.test_item_id in [si.test_item_id for si in success_items]
            ]
            
            if valid_configs:
                # Atomic update with item addition and count updates
                await self.suite_collection.update_one(
                    {"_id": ObjectId(suite_id), "owner_id": user_id},
                    {
                        "$push": {"suite_items": {"$each": valid_configs}},
                        "$inc": {
                            "total_items": len(valid_configs),
                            "active_items": len([c for c in valid_configs if not c.get("skip", False)])
                        },
                        "$set": {"updated_at": datetime.utcnow()}
                    }
                )
            
            # Build result
            result = BulkOperationResult(
                total_requested=len(request.items),
                successful=len(success_items),
                failed=len(failed_items),
                success_items=success_items,
                failed_items=failed_items,
                overall_success=len(failed_items) == 0
            )
            
            # Track operation
            await self._track_operation(
                operation="add_items",
                suite_id=suite_id,
                user_id=user_id,
                success=True,
                context={
                    "requested": len(request.items),
                    "successful": len(success_items),
                    "failed": len(failed_items)
                }
            )
            
            logger.info(
                f"Bulk add items completed: {len(success_items)} successful, {len(failed_items)} failed",
                extra={
                    "suite_id": suite_id,
                    "user_id": user_id,
                    "successful": len(success_items),
                    "failed": len(failed_items)
                }
            )
            
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            await self._track_operation(
                operation="add_items",
                suite_id=suite_id,
                user_id=user_id,
                success=False,
                context={"error": str(e)}
            )
            logger.error(
                f"Failed to bulk add items: {e}",
                extra={
                    "suite_id": suite_id,
                    "user_id": user_id,
                    "error": str(e)
                }
            )
            raise HTTPException(
                status_code=500,
                detail=f"Failed to add items to suite: {str(e)}"
            )
    
    async def remove_items(
        self, 
        suite_id: str, 
        request: BulkRemoveItemsRequest,
        user_id: str
    ) -> BulkOperationResult:
        """
        Bulk remove test items from suite with optional order rebalancing.
        
        Implements atomic removal operations with comprehensive result reporting
        and optional order value rebalancing.
        
        Args:
            suite_id: Test suite identifier
            request: Bulk remove request with item IDs
            user_id: User ID for ownership validation
            
        Returns:
            Bulk operation result with detailed status
            
        Raises:
            HTTPException: If validation fails or operation fails
        """
        logger.info(
            f"Bulk removing items from suite: {suite_id}",
            extra={
                "suite_id": suite_id,
                "user_id": user_id,
                "items_count": len(request.test_item_ids)
            }
        )
        
        try:
            # Validate suite ownership
            await self._validate_suite_ownership(suite_id, user_id)
            
            # Get current suite items
            suite_doc = await self.suite_collection.find_one(
                {"_id": ObjectId(suite_id)},
                {"suite_items": 1}
            )
            current_items = suite_doc.get("suite_items", [])
            current_item_ids = {item["test_item_id"] for item in current_items}
            
            # Process removal requests
            success_items = []
            failed_items = []
            
            for item_id in request.test_item_ids:
                if item_id in current_item_ids:
                    success_items.append(BulkOperationItem(
                        test_item_id=item_id,
                        status="success",
                        message="Item removed successfully"
                    ))
                else:
                    failed_items.append(BulkOperationItem(
                        test_item_id=item_id,
                        status="not_found",
                        message="Item not found in suite"
                    ))
            
            # Remove items and update counts
            if success_items:
                remove_ids = {item.test_item_id for item in success_items}
                
                # Filter out removed items
                remaining_items = [
                    item for item in current_items 
                    if item["test_item_id"] not in remove_ids
                ]
                
                # Rebalance order if requested
                if request.rebalance_order and remaining_items:
                    for i, item in enumerate(remaining_items):
                        item["order"] = i + 1
                
                # Calculate new counts
                new_total = len(remaining_items)
                new_active = len([item for item in remaining_items if not item.get("skip", False)])
                
                # Atomic update
                await self.suite_collection.update_one(
                    {"_id": ObjectId(suite_id), "owner_id": user_id},
                    {
                        "$set": {
                            "suite_items": remaining_items,
                            "total_items": new_total,
                            "active_items": new_active,
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
            
            # Build result
            result = BulkOperationResult(
                total_requested=len(request.test_item_ids),
                successful=len(success_items),
                failed=len(failed_items),
                success_items=success_items,
                failed_items=failed_items,
                overall_success=len(failed_items) == 0
            )
            
            # Track operation
            await self._track_operation(
                operation="remove_items",
                suite_id=suite_id,
                user_id=user_id,
                success=True,
                context={
                    "requested": len(request.test_item_ids),
                    "successful": len(success_items),
                    "failed": len(failed_items),
                    "rebalanced": request.rebalance_order
                }
            )
            
            logger.info(
                f"Bulk remove items completed: {len(success_items)} successful, {len(failed_items)} failed",
                extra={
                    "suite_id": suite_id,
                    "user_id": user_id,
                    "successful": len(success_items),
                    "failed": len(failed_items),
                    "rebalanced": request.rebalance_order
                }
            )
            
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            await self._track_operation(
                operation="remove_items",
                suite_id=suite_id,
                user_id=user_id,
                success=False,
                context={"error": str(e)}
            )
            logger.error(
                f"Failed to bulk remove items: {e}",
                extra={
                    "suite_id": suite_id,
                    "user_id": user_id,
                    "error": str(e)
                }
            )
            raise HTTPException(
                status_code=500,
                detail=f"Failed to remove items from suite: {str(e)}"
            )
    
    async def delete_suite(
        self, 
        suite_id: str, 
        user_id: str
    ) -> bool:
        """
        Soft delete test suite by setting status to archived.
        
        Implements soft deletion pattern for data recovery capability
        while maintaining referential integrity.
        
        Args:
            suite_id: Test suite identifier
            user_id: User ID for ownership validation
            
        Returns:
            True if deletion successful
            
        Raises:
            HTTPException: If validation fails or deletion fails
        """
        logger.info(
            f"Deleting test suite: {suite_id}",
            extra={
                "suite_id": suite_id,
                "user_id": user_id
            }
        )
        
        try:
            # Validate ObjectId format
            if not ObjectId.is_valid(suite_id):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid suite ID format"
                )
            
            # Soft delete by updating status
            result = await self.suite_collection.update_one(
                {"_id": ObjectId(suite_id), "owner_id": user_id},
                {
                    "$set": {
                        "status": TestSuiteStatus.ARCHIVED.value,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.matched_count == 0:
                raise HTTPException(
                    status_code=404,
                    detail="Test suite not found or access denied"
                )
            
            # Track operation
            await self._track_operation(
                operation="delete_suite",
                suite_id=suite_id,
                user_id=user_id,
                success=True,
                context={"soft_delete": True}
            )
            
            logger.info(
                f"Test suite deleted successfully: {suite_id}",
                extra={
                    "suite_id": suite_id,
                    "user_id": user_id
                }
            )
            
            return True
            
        except HTTPException:
            raise
        except Exception as e:
            await self._track_operation(
                operation="delete_suite",
                suite_id=suite_id,
                user_id=user_id,
                success=False,
                context={"error": str(e)}
            )
            logger.error(
                f"Failed to delete test suite: {e}",
                extra={
                    "suite_id": suite_id,
                    "user_id": user_id,
                    "error": str(e)
                }
            )
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete test suite: {str(e)}"
            )
    
    # Private helper methods for DRY compliance and separation of concerns
    
    async def _validate_item_references(
        self, 
        item_ids: List[str], 
        user_id: str
    ) -> ValidationResult:
        """
        Batch validate test item references using single database query.
        
        Implements batch validation strategy from creative phase for
        optimal performance and clear error separation.
        
        Args:
            item_ids: List of test item IDs to validate
            user_id: User ID for ownership validation
            
        Returns:
            ValidationResult with valid and invalid ID sets
        """
        if not item_ids:
            return ValidationResult(valid_ids=set(), invalid_ids=set())
        
        try:
            # Single MongoDB query with $in operator
            cursor = self.test_item_collection.find(
                {
                    "_id": {"$in": [ObjectId(id) for id in item_ids if ObjectId.is_valid(id)]},
                    "audit.created_by_user_id": user_id
                },
                {"_id": 1}  # Projection optimization
            )
            
            valid_object_ids = {doc["_id"] async for doc in cursor}
            valid_ids = {str(oid) for oid in valid_object_ids}
            invalid_ids = set(item_ids) - valid_ids
            
            return ValidationResult(valid_ids=valid_ids, invalid_ids=invalid_ids)
            
        except Exception as e:
            logger.error(
                f"Failed to validate item references: {e}",
                extra={
                    "item_ids_count": len(item_ids),
                    "user_id": user_id,
                    "error": str(e)
                }
            )
            # Treat all as invalid on validation error
            return ValidationResult(valid_ids=set(), invalid_ids=set(item_ids))
    
    async def _validate_suite_ownership(self, suite_id: str, user_id: str) -> None:
        """
        Validate that user owns the specified suite.
        
        Args:
            suite_id: Test suite identifier
            user_id: User ID for ownership validation
            
        Raises:
            HTTPException: If suite not found or access denied
        """
        exists = await self.suite_collection.find_one(
            {"_id": ObjectId(suite_id), "owner_id": user_id},
            {"_id": 1}
        )
        
        if not exists:
            raise HTTPException(
                status_code=404,
                detail="Test suite not found or access denied"
            )
    
    async def _validate_title_uniqueness(
        self, 
        title: str, 
        user_id: str, 
        exclude_suite_id: Optional[str] = None
    ) -> None:
        """
        Validate that suite title is unique for the user.
        
        Args:
            title: Suite title to validate
            user_id: User ID for scope validation
            exclude_suite_id: Optional suite ID to exclude from check (for updates)
            
        Raises:
            HTTPException: If title already exists
        """
        query = {"title": title, "owner_id": user_id}
        if exclude_suite_id:
            query["_id"] = {"$ne": ObjectId(exclude_suite_id)}
        
        exists = await self.suite_collection.find_one(query, {"_id": 1})
        if exists:
            raise HTTPException(
                status_code=400,
                detail="A test suite with this title already exists"
            )
    
    async def _get_existing_item_ids(self, suite_id: str) -> Set[str]:
        """
        Get set of existing test item IDs in the suite.
        
        Args:
            suite_id: Test suite identifier
            
        Returns:
            Set of existing test item IDs
        """
        suite_doc = await self.suite_collection.find_one(
            {"_id": ObjectId(suite_id)},
            {"suite_items.test_item_id": 1}
        )
        
        if not suite_doc:
            return set()
        
        return {item["test_item_id"] for item in suite_doc.get("suite_items", [])}
    
    async def _track_operation(
        self, 
        operation: str, 
        suite_id: str, 
        user_id: str, 
        success: bool, 
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Track suite operation for observability and monitoring.
        
        Implements hybrid observability pattern from creative phase with
        structured logging for dashboard and analytics.
        
        Args:
            operation: Operation name (create, read, update, delete, bulk_add, bulk_remove)
            suite_id: Test suite identifier
            user_id: User ID performing operation
            success: Operation success status
            context: Additional context data
        """
        log_data = {
            "operation": operation,
            "suite_id": suite_id,
            "user_id": user_id,
            "success": success,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if context:
            log_data.update(context)
        
        # Structured logging for monitoring and analytics
        logger.info(
            f"Suite operation tracked: {operation}",
            extra=log_data
        )
        
        # Future: Could implement real-time metrics collection here
        # for dashboard APIs and performance monitoring 
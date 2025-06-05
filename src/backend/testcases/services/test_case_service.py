"""
Test Case Service - Business Logic Layer

Implements core business operations for the Test Case Management system.
Enforces all CREATIVE phase patterns including async validation, tag normalization,
and reusable step integrity enforcement with comprehensive observability.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Set, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorCollection
from bson import ObjectId
import logging

from ...config.env import get_settings
from ...config.logging import get_logger
from ...config.database import get_database
from ...schemas.response import BaseResponse
from ..models.test_case_model import (
    TestCaseModel,
    TestCaseStep,
    TestCaseStatus,
    TestCasePriority,
    StepType,
    AttachmentRef
)
from ..schemas.test_case_schemas import (
    CreateTestCaseRequest,
    UpdateTestCaseRequest,
    FilterTestCasesRequest,
    TestCaseResponse,
    TestCaseListResponse,
    TestCaseCore,
    TestCaseSteps,
    TestCaseStatistics,
    TestCaseReferences,
    PaginationMeta,
    FilterMeta,
    SortMeta
)
from ...testtypes.enums import TestType

logger = get_logger(__name__)
settings = get_settings()


class ValidationResult:
    """Validation result container with error tracking."""
    
    def __init__(self, valid: bool, error: Optional[str] = None, warnings: Optional[List[str]] = None):
        self.valid = valid
        self.error = error
        self.warnings = warnings or []


class TestCaseValidationService:
    """
    Validation service implementing deep validation with DFS-based cycle detection.
    Handles type-aware step validation and reusable step integrity enforcement.
    """
    
    def __init__(self, database: AsyncIOMotorDatabase):
        self.db = database
        self.test_cases_collection: AsyncIOMotorCollection = database.test_cases
        self.test_items_collection: AsyncIOMotorCollection = database.test_items
        self._validation_cache: Dict[str, ValidationResult] = {}
    
    async def validate_test_case(self, test_case_data: Dict[str, Any], test_case_id: Optional[str] = None) -> ValidationResult:
        """
        Comprehensive test case validation with business rule enforcement.
        
        Args:
            test_case_data: Test case data to validate
            test_case_id: Existing test case ID (for updates)
        
        Returns:
            ValidationResult with validation status and errors
        """
        try:
            # Check title uniqueness per user
            if 'title' in test_case_data and 'owner_id' in test_case_data:
                is_unique = await self._validate_title_uniqueness(
                    test_case_data['title'],
                    test_case_data['owner_id'],
                    test_case_id
                )
                if not is_unique:
                    return ValidationResult(False, "Test case title must be unique per user")
            
            # Validate steps if present
            if 'steps' in test_case_data:
                step_validation = await self._validate_steps(
                    test_case_data['steps'],
                    test_case_data.get('test_type', TestType.GENERIC)
                )
                if not step_validation.valid:
                    return step_validation
            
            # Validate test item references
            if 'related_test_items' in test_case_data:
                ref_validation = await self._validate_test_item_references(
                    test_case_data['related_test_items'],
                    test_case_data.get('owner_id')
                )
                if not ref_validation.valid:
                    return ref_validation
            
            # Validate step references for circular dependencies
            if 'steps' in test_case_data:
                cycle_validation = await self._validate_step_references(
                    test_case_data['steps'],
                    test_case_id
                )
                if not cycle_validation.valid:
                    return cycle_validation
            
            return ValidationResult(True)
            
        except Exception as e:
            logger.error(f"Test case validation failed: {e}")
            return ValidationResult(False, f"Validation error: {str(e)}")
    
    async def _validate_title_uniqueness(self, title: str, owner_id: str, exclude_id: Optional[str] = None) -> bool:
        """Validate title uniqueness per user."""
        query = {"title": title, "owner_id": owner_id, "is_archived": False}
        if exclude_id:
            query["_id"] = {"$ne": ObjectId(exclude_id)}
        
        existing = await self.test_cases_collection.find_one(query)
        return existing is None
    
    async def _validate_steps(self, steps: List[Dict[str, Any]], test_type: TestType) -> ValidationResult:
        """Type-aware step validation."""
        if not steps:
            return ValidationResult(True)
        
        # Validate step ordering
        orders = [step.get('order', 0) for step in steps]
        if not all(isinstance(o, int) and o > 0 for o in orders):
            return ValidationResult(False, "All steps must have positive integer order values")
        
        if len(set(orders)) != len(orders):
            return ValidationResult(False, "Step orders must be unique")
        
        # Type-specific validation
        for step in steps:
            step_validation = await self._validate_single_step(step, test_type)
            if not step_validation.valid:
                return step_validation
        
        return ValidationResult(True)
    
    async def _validate_single_step(self, step: Dict[str, Any], test_type: TestType) -> ValidationResult:
        """Validate individual step based on test type."""
        step_type = step.get('step_type', StepType.ACTION)
        
        if test_type == TestType.BDD:
            valid_bdd_types = {StepType.GIVEN, StepType.WHEN, StepType.THEN}
            if step_type not in valid_bdd_types:
                return ValidationResult(False, "BDD test cases must use Given/When/Then step types")
        
        # Validate action content
        action = step.get('action', '').strip()
        if len(action) < 3:
            return ValidationResult(False, "Step actions must be at least 3 characters long")
        
        # Validate test item reference if present
        test_item_ref = step.get('test_item_ref')
        if test_item_ref:
            ref_exists = await self._validate_test_item_exists(test_item_ref)
            if not ref_exists:
                return ValidationResult(False, f"Referenced test item {test_item_ref} does not exist")
        
        return ValidationResult(True)
    
    async def _validate_test_item_references(self, test_item_ids: List[str], owner_id: Optional[str]) -> ValidationResult:
        """Validate test item references exist and are accessible."""
        if not test_item_ids:
            return ValidationResult(True)
        
        try:
            object_ids = [ObjectId(ref_id) for ref_id in test_item_ids]
        except Exception:
            return ValidationResult(False, "Invalid test item reference format")
        
        # Check if all referenced test items exist
        existing_count = await self.test_items_collection.count_documents({
            "_id": {"$in": object_ids},
            "is_archived": False
        })
        
        if existing_count != len(object_ids):
            return ValidationResult(False, "One or more referenced test items do not exist")
        
        return ValidationResult(True)
    
    async def _validate_test_item_exists(self, test_item_id: str) -> bool:
        """Check if a single test item exists."""
        try:
            object_id = ObjectId(test_item_id)
            result = await self.test_items_collection.find_one({
                "_id": object_id,
                "is_archived": False
            })
            return result is not None
        except Exception:
            return False
    
    async def _validate_step_references(self, steps: List[Dict[str, Any]], exclude_test_case_id: Optional[str] = None) -> ValidationResult:
        """
        DFS-based circular dependency detection for step references.
        Prevents cycles in test item references.
        """
        # Build reference graph
        graph = {}
        for step in steps:
            test_item_ref = step.get('test_item_ref')
            if test_item_ref:
                if exclude_test_case_id not in graph:
                    graph[exclude_test_case_id] = set()
                graph[exclude_test_case_id].add(test_item_ref)
        
        # Check for cycles using DFS
        visited = set()
        rec_stack = set()
        
        def has_cycle(node):
            if node in rec_stack:
                return True
            if node in visited:
                return False
            
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in graph.get(node, []):
                if has_cycle(neighbor):
                    return True
            
            rec_stack.remove(node)
            return False
        
        for node in graph:
            if has_cycle(node):
                return ValidationResult(False, "Circular dependency detected in step references")
        
        return ValidationResult(True)


class TestCaseTagService:
    """
    Intelligent tagging service with normalization and auto-complete.
    Implements hybrid tag index pattern from creative phase.
    """
    
    def __init__(self, database: AsyncIOMotorDatabase):
        self.db = database
        self.test_cases_collection: AsyncIOMotorCollection = database.test_cases
        self.tag_index_collection: AsyncIOMotorCollection = database.tag_index
    
    async def normalize_tags(self, tags: List[str]) -> List[str]:
        """Normalize tags with intelligent processing."""
        if not tags:
            return []
        
        normalized = []
        for tag in tags:
            # Basic normalization
            normalized_tag = tag.strip().lower()
            if len(normalized_tag) >= 2 and normalized_tag not in normalized:
                normalized.append(normalized_tag)
        
        # Update tag index usage
        await self._update_tag_usage(normalized)
        
        return normalized
    
    async def suggest_tags(self, partial: str, limit: int = 10) -> List[str]:
        """Get tag suggestions with fuzzy matching."""
        if len(partial) < 2:
            return []
        
        # Simple prefix matching (can be enhanced with fuzzy matching)
        pattern = f"^{partial.lower()}"
        suggestions = await self.tag_index_collection.find(
            {"tag": {"$regex": pattern}},
            {"tag": 1, "usage_count": 1}
        ).sort("usage_count", -1).limit(limit).to_list(length=limit)
        
        return [s["tag"] for s in suggestions]
    
    async def get_popular_tags(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get most popular tags with usage counts."""
        popular = await self.tag_index_collection.find(
            {},
            {"tag": 1, "usage_count": 1}
        ).sort("usage_count", -1).limit(limit).to_list(length=limit)
        
        return popular
    
    async def _update_tag_usage(self, tags: List[str]) -> None:
        """Update tag usage statistics in tag index."""
        for tag in tags:
            await self.tag_index_collection.update_one(
                {"tag": tag},
                {
                    "$inc": {"usage_count": 1},
                    "$set": {"last_used": datetime.now(timezone.utc)}
                },
                upsert=True
            )


class TestCaseResponseBuilder:
    """
    Flexible response construction with field inclusion control.
    Optimizes response size based on requested fields.
    """
    
    def __init__(self):
        pass
    
    async def build_test_case_response(
        self,
        test_case: TestCaseModel,
        include_steps: bool = False,
        include_statistics: bool = False,
        include_references: bool = False
    ) -> TestCaseResponse:
        """Build flexible test case response."""
        
        # Core data (always included)
        core = TestCaseCore(
            id=test_case.id,
            title=test_case.title,
            description=test_case.description,
            status=test_case.status.value,
            priority=test_case.priority.value,
            test_type=test_case.test_type.value,
            tags=test_case.tags,
            expected_result=test_case.expected_result,
            owner_id=test_case.owner_id,
            created_by=test_case.created_by,
            created_at=test_case.created_at,
            updated_at=test_case.updated_at,
            step_count=len(test_case.steps),
            complexity_score=test_case.get_complexity_score()
        )
        
        # Optional detailed fields
        steps_data = None
        if include_steps:
            steps_data = await self._build_steps_response(test_case)
        
        statistics_data = None
        if include_statistics:
            statistics_data = await self._build_statistics_response(test_case)
        
        references_data = None
        if include_references:
            references_data = await self._build_references_response(test_case)
        
        return TestCaseResponse(
            core=core,
            steps=steps_data,
            statistics=statistics_data,
            references=references_data
        )
    
    async def _build_steps_response(self, test_case: TestCaseModel) -> TestCaseSteps:
        """Build steps response data."""
        from ..schemas.test_case_schemas import TestCaseStepResponse
        
        step_responses = []
        for step in test_case.steps:
            step_response = TestCaseStepResponse(
                order=step.order,
                action=step.action,
                expected=step.expected,
                step_type=step.step_type.value,
                parameters=step.parameters,
                preconditions=step.preconditions,
                postconditions=step.postconditions,
                notes=step.notes,
                test_item_ref=step.test_item_ref,
                external_refs=step.external_refs,
                format_hint=step.format_hint.value,
                is_template=step.is_template,
                metadata=step.metadata
            )
            step_responses.append(step_response)
        
        # Calculate step type summary
        step_types_summary = {}
        for step in test_case.steps:
            step_type = step.step_type.value
            step_types_summary[step_type] = step_types_summary.get(step_type, 0) + 1
        
        return TestCaseSteps(
            steps=step_responses,
            step_count=len(test_case.steps),
            bdd_structure=test_case.has_bdd_structure(),
            step_types_summary=step_types_summary
        )
    
    async def _build_statistics_response(self, test_case: TestCaseModel) -> TestCaseStatistics:
        """Build statistics response data."""
        # Estimate execution time (basic calculation)
        execution_time_estimate = len(test_case.steps) * 30  # 30 seconds per step average
        
        # Calculate automation readiness (simplified)
        automation_readiness = 0.5  # Default value, can be enhanced
        if test_case.test_type == TestType.GENERIC:
            automation_readiness += 0.3
        if any(step.test_item_ref for step in test_case.steps):
            automation_readiness += 0.2
        
        automation_readiness = min(1.0, automation_readiness)
        
        # Human-readable last activity
        last_activity = None
        if test_case.updated_at:
            days_ago = (datetime.now(timezone.utc) - test_case.updated_at).days
            if days_ago == 0:
                last_activity = "Updated today"
            elif days_ago == 1:
                last_activity = "Updated yesterday"
            else:
                last_activity = f"Updated {days_ago} days ago"
        
        return TestCaseStatistics(
            execution_time_estimate=execution_time_estimate,
            automation_readiness=automation_readiness,
            last_activity=last_activity,
            reference_count=len(test_case.related_test_items),
            attachment_count=len(test_case.attachments) if test_case.attachments else 0
        )
    
    async def _build_references_response(self, test_case: TestCaseModel) -> TestCaseReferences:
        """Build references response data."""
        from ..schemas.test_case_schemas import AttachmentRefResponse
        
        attachment_responses = []
        if test_case.attachments:
            for attachment in test_case.attachments:
                attachment_response = AttachmentRefResponse(
                    name=attachment.name,
                    url=attachment.url,
                    type=attachment.type,
                    size=attachment.size
                )
                attachment_responses.append(attachment_response)
        
        return TestCaseReferences(
            related_test_items=test_case.related_test_items,
            suite_references=test_case.suite_references,
            references=test_case.references or [],
            attachments=attachment_responses,
            preconditions=test_case.preconditions,
            postconditions=test_case.postconditions,
            metadata=test_case.metadata
        )


class TestCaseService:
    """
    Main business logic service for test case management.
    
    Implements comprehensive CRUD operations with async validation,
    tag normalization, and performance optimization following
    creative phase architectural decisions.
    """
    
    def __init__(self):
        self.db: Optional[AsyncIOMotorDatabase] = None
        self.collection: Optional[AsyncIOMotorCollection] = None
        self.validation_service: Optional[TestCaseValidationService] = None
        self.tag_service: Optional[TestCaseTagService] = None
        self.response_builder: TestCaseResponseBuilder = TestCaseResponseBuilder()
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize service with database connections and dependencies."""
        if self._initialized:
            return
        
        self.db = await get_database()
        self.collection = self.db.test_cases
        self.validation_service = TestCaseValidationService(self.db)
        self.tag_service = TestCaseTagService(self.db)
        self._initialized = True
        
        logger.info("TestCaseService initialized successfully")
    
    async def create_test_case(self, request: CreateTestCaseRequest, user_id: str) -> TestCaseResponse:
        """
        Create new test case with comprehensive validation.
        
        Args:
            request: Test case creation request
            user_id: ID of the user creating the test case
        
        Returns:
            TestCaseResponse with created test case data
        
        Raises:
            ValueError: If validation fails
            RuntimeError: If creation fails
        """
        await self.initialize()
        
        start_time = datetime.now()
        logger.info(f"Creating test case '{request.title}' for user {user_id}")
        
        try:
            # Normalize tags
            normalized_tags = await self.tag_service.normalize_tags(request.tags)
            
            # Convert request to model data
            test_case_data = {
                "title": request.title,
                "description": request.description,
                "expected_result": request.expected_result,
                "preconditions": request.preconditions,
                "postconditions": request.postconditions,
                "test_type": request.test_type,
                "priority": request.priority,
                "tags": normalized_tags,
                "related_test_items": request.related_test_items,
                "references": request.references,
                "metadata": request.metadata,
                "owner_id": user_id,
                "created_by": user_id,
                "status": TestCaseStatus.DRAFT
            }
            
            # Convert steps
            steps = []
            for i, step_req in enumerate(request.steps, 1):
                step = TestCaseStep(
                    order=i,
                    action=step_req.action,
                    expected=step_req.expected,
                    step_type=step_req.step_type,
                    parameters=step_req.parameters,
                    preconditions=step_req.preconditions,
                    postconditions=step_req.postconditions,
                    notes=step_req.notes,
                    test_item_ref=step_req.test_item_ref,
                    external_refs=step_req.external_refs,
                    format_hint=step_req.format_hint,
                    is_template=step_req.is_template,
                    metadata=step_req.metadata
                )
                steps.append(step)
            
            test_case_data["steps"] = [step.model_dump() for step in steps]
            
            # Convert attachments
            if request.attachments:
                attachments = []
                for att_req in request.attachments:
                    attachment = AttachmentRef(
                        name=att_req.name,
                        url=att_req.url,
                        type=att_req.type,
                        size=att_req.size
                    )
                    attachments.append(attachment)
                test_case_data["attachments"] = [att.model_dump() for att in attachments]
            
            # Validate test case
            validation_result = await self.validation_service.validate_test_case(test_case_data)
            if not validation_result.valid:
                raise ValueError(f"Validation failed: {validation_result.error}")
            
            # Create model instance
            test_case = TestCaseModel(**test_case_data)
            
            # Insert into database
            mongo_data = test_case.to_mongo()
            result = await self.collection.insert_one(mongo_data)
            
            # Retrieve created document
            created_doc = await self.collection.find_one({"_id": result.inserted_id})
            created_test_case = TestCaseModel.from_mongo(created_doc)
            
            # Build response
            response = await self.response_builder.build_test_case_response(
                created_test_case,
                include_steps=True,
                include_statistics=True,
                include_references=True
            )
            
            # Log performance metrics
            duration = (datetime.now() - start_time).total_seconds() * 1000
            logger.info(f"Test case created successfully in {duration:.2f}ms")
            
            return response
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to create test case: {e}")
            raise RuntimeError(f"Test case creation failed: {str(e)}")
    
    async def get_test_case(
        self,
        test_case_id: str,
        user_id: str,
        include_steps: bool = False,
        include_statistics: bool = False,
        include_references: bool = False
    ) -> Optional[TestCaseResponse]:
        """
        Retrieve test case by ID with optional field inclusion.
        
        Args:
            test_case_id: Test case ID
            user_id: Requesting user ID
            include_steps: Include step details
            include_statistics: Include computed statistics
            include_references: Include reference data
        
        Returns:
            TestCaseResponse if found and accessible, None otherwise
        """
        await self.initialize()
        
        start_time = datetime.now()
        logger.debug(f"Retrieving test case {test_case_id} for user {user_id}")
        
        try:
            # Find test case
            query = {
                "_id": ObjectId(test_case_id),
                "owner_id": user_id,
                "is_archived": False
            }
            
            doc = await self.collection.find_one(query)
            if not doc:
                return None
            
            test_case = TestCaseModel.from_mongo(doc)
            if not test_case:
                return None
            
            # Build response
            response = await self.response_builder.build_test_case_response(
                test_case,
                include_steps=include_steps,
                include_statistics=include_statistics,
                include_references=include_references
            )
            
            # Log performance
            duration = (datetime.now() - start_time).total_seconds() * 1000
            logger.debug(f"Test case retrieved in {duration:.2f}ms")
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to retrieve test case {test_case_id}: {e}")
            return None
    
    async def list_test_cases(
        self,
        user_id: str,
        filters: FilterTestCasesRequest
    ) -> TestCaseListResponse:
        """
        List test cases with filtering, sorting, and pagination.
        
        Args:
            user_id: Requesting user ID
            filters: Filter and pagination parameters
        
        Returns:
            TestCaseListResponse with paginated results
        """
        await self.initialize()
        
        start_time = datetime.now()
        logger.debug(f"Listing test cases for user {user_id} with filters")
        
        try:
            # Build query
            query = {
                "owner_id": user_id,
                "is_archived": False
            }
            
            # Apply filters
            if filters.status:
                query["status"] = filters.status.value
            if filters.priority:
                query["priority"] = filters.priority.value
            if filters.test_type:
                query["test_type"] = filters.test_type.value
            if filters.tags:
                query["tags"] = {"$all": filters.tags}
            if filters.title_search:
                query["title"] = {"$regex": filters.title_search, "$options": "i"}
            if filters.has_steps is not None:
                if filters.has_steps:
                    query["steps.0"] = {"$exists": True}
                else:
                    query["steps"] = {"$size": 0}
            if filters.created_after:
                query["created_at"] = {"$gte": filters.created_after}
            if filters.created_before:
                if "created_at" in query:
                    query["created_at"]["$lte"] = filters.created_before
                else:
                    query["created_at"] = {"$lte": filters.created_before}
            
            # Count total items
            total_count = await self.collection.count_documents(query)
            
            # Calculate pagination
            page = max(1, filters.page)
            page_size = min(100, max(1, filters.page_size))
            skip = (page - 1) * page_size
            total_pages = (total_count + page_size - 1) // page_size
            
            # Build sort criteria
            sort_field = filters.sort_by
            if sort_field not in ["created_at", "updated_at", "title", "priority", "status"]:
                sort_field = "updated_at"
            
            sort_direction = -1 if filters.sort_order == "desc" else 1
            sort_criteria = [(sort_field, sort_direction)]
            
            # Execute query
            cursor = self.collection.find(query).sort(sort_criteria).skip(skip).limit(page_size)
            docs = await cursor.to_list(length=page_size)
            
            # Convert to models and build responses
            test_cases = []
            for doc in docs:
                test_case = TestCaseModel.from_mongo(doc)
                if test_case:
                    response = await self.response_builder.build_test_case_response(
                        test_case,
                        include_steps=filters.include_steps,
                        include_statistics=filters.include_statistics,
                        include_references=filters.include_references
                    )
                    test_cases.append(response)
            
            # Build metadata
            pagination = PaginationMeta(
                page=page,
                page_size=page_size,
                total_items=total_count,
                total_pages=total_pages,
                has_next=page < total_pages,
                has_previous=page > 1
            )
            
            filter_meta = FilterMeta(
                status=filters.status.value if filters.status else None,
                priority=filters.priority.value if filters.priority else None,
                test_type=filters.test_type.value if filters.test_type else None,
                tags=filters.tags,
                title_search=filters.title_search,
                has_steps=filters.has_steps
            )
            
            sort_meta = SortMeta(
                sort_by=sort_field,
                sort_order=filters.sort_order
            )
            
            # Build summary
            summary = {
                "total_count": total_count,
                "filtered_count": len(test_cases)
            }
            
            # Log performance
            duration = (datetime.now() - start_time).total_seconds() * 1000
            logger.debug(f"Listed {len(test_cases)} test cases in {duration:.2f}ms")
            
            return TestCaseListResponse.create_success(
                test_cases=test_cases,
                pagination=pagination,
                filters=filter_meta,
                sorting=sort_meta,
                summary=summary
            )
            
        except Exception as e:
            logger.error(f"Failed to list test cases: {e}")
            raise RuntimeError(f"Test case listing failed: {str(e)}")
    
    async def update_test_case(
        self,
        test_case_id: str,
        request: UpdateTestCaseRequest,
        user_id: str
    ) -> Optional[TestCaseResponse]:
        """
        Update test case with validation and optimistic locking.
        
        Args:
            test_case_id: Test case ID to update
            request: Update request data
            user_id: User ID performing the update
        
        Returns:
            Updated TestCaseResponse if successful, None if not found
        
        Raises:
            ValueError: If validation fails
            RuntimeError: If update fails
        """
        await self.initialize()
        
        start_time = datetime.now()
        logger.info(f"Updating test case {test_case_id} for user {user_id}")
        
        try:
            # Find existing test case
            existing_doc = await self.collection.find_one({
                "_id": ObjectId(test_case_id),
                "owner_id": user_id,
                "is_archived": False
            })
            
            if not existing_doc:
                return None
            
            existing_test_case = TestCaseModel.from_mongo(existing_doc)
            
            # Build update data
            update_data = {}
            
            # Update fields if provided
            if request.title is not None:
                update_data["title"] = request.title
            if request.description is not None:
                update_data["description"] = request.description
            if request.expected_result is not None:
                update_data["expected_result"] = request.expected_result
            if request.preconditions is not None:
                update_data["preconditions"] = request.preconditions
            if request.postconditions is not None:
                update_data["postconditions"] = request.postconditions
            if request.test_type is not None:
                update_data["test_type"] = request.test_type
            if request.priority is not None:
                update_data["priority"] = request.priority
            if request.tags is not None:
                update_data["tags"] = await self.tag_service.normalize_tags(request.tags)
            if request.related_test_items is not None:
                update_data["related_test_items"] = request.related_test_items
            if request.references is not None:
                update_data["references"] = request.references
            if request.metadata is not None:
                update_data["metadata"] = request.metadata
            
            # Handle attachments
            if request.attachments is not None:
                attachments = []
                for att_req in request.attachments:
                    attachment = AttachmentRef(
                        name=att_req.name,
                        url=att_req.url,
                        type=att_req.type,
                        size=att_req.size
                    )
                    attachments.append(attachment)
                update_data["attachments"] = [att.model_dump() for att in attachments]
            
            # Merge with existing data for validation
            validation_data = existing_test_case.model_dump()
            validation_data.update(update_data)
            validation_data["owner_id"] = user_id
            
            # Validate update
            validation_result = await self.validation_service.validate_test_case(
                validation_data, test_case_id
            )
            if not validation_result.valid:
                raise ValueError(f"Validation failed: {validation_result.error}")
            
            # Prepare MongoDB update
            update_data["updated_at"] = datetime.now(timezone.utc)
            
            # Perform update
            result = await self.collection.update_one(
                {"_id": ObjectId(test_case_id)},
                {"$set": update_data}
            )
            
            if result.modified_count == 0:
                return None
            
            # Retrieve updated document
            updated_doc = await self.collection.find_one({"_id": ObjectId(test_case_id)})
            updated_test_case = TestCaseModel.from_mongo(updated_doc)
            
            # Build response
            response = await self.response_builder.build_test_case_response(
                updated_test_case,
                include_steps=True,
                include_statistics=True,
                include_references=True
            )
            
            # Log performance
            duration = (datetime.now() - start_time).total_seconds() * 1000
            logger.info(f"Test case updated successfully in {duration:.2f}ms")
            
            return response
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to update test case {test_case_id}: {e}")
            raise RuntimeError(f"Test case update failed: {str(e)}")
    
    async def delete_test_case(self, test_case_id: str, user_id: str) -> bool:
        """
        Soft delete test case (archive).
        
        Args:
            test_case_id: Test case ID to delete
            user_id: User ID performing the deletion
        
        Returns:
            True if deleted successfully, False if not found
        """
        await self.initialize()
        
        logger.info(f"Deleting test case {test_case_id} for user {user_id}")
        
        try:
            result = await self.collection.update_one(
                {
                    "_id": ObjectId(test_case_id),
                    "owner_id": user_id,
                    "is_archived": False
                },
                {
                    "$set": {
                        "is_archived": True,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            
            success = result.modified_count > 0
            if success:
                logger.info(f"Test case {test_case_id} archived successfully")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to delete test case {test_case_id}: {e}")
            return False 
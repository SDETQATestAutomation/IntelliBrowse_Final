"""
Test Item Controller Layer

Handles HTTP request processing, validation, service orchestration,
and response formatting for test item endpoints.
"""

from typing import Optional, Set
from fastapi import HTTPException, status

from ...config.logging import get_logger
from ..services.test_item_service import TestItemService, TestItemResponseService
from ..schemas.test_item_schemas import (
    CreateTestItemRequest,
    FilterTestItemsRequest,
    TestItemCreateResponse,
    TestItemDetailResponse,
    TestItemListResponse,
    TestItemResponseBuilder
)
from ...schemas.response import ErrorResponse

logger = get_logger(__name__)


class TestItemController:
    """
    Test Item Controller for handling HTTP requests and responses.
    
    Provides request validation, service orchestration, and response formatting
    for all test item operations following clean architecture principles.
    """
    
    def __init__(self, test_item_service: TestItemService):
        """
        Initialize controller with test item service.
        
        Args:
            test_item_service: TestItemService instance
        """
        self.test_item_service = test_item_service
        self.response_service = TestItemResponseService()
        
        logger.info("TestItemController initialized")
    
    async def create_test_item(
        self,
        request: CreateTestItemRequest,
        user_id: str
    ) -> TestItemCreateResponse:
        """
        Handle test item creation request.
        
        Args:
            request: Test item creation request
            user_id: Authenticated user ID
            
        Returns:
            TestItemCreateResponse with created test item
            
        Raises:
            HTTPException: If creation fails
        """
        logger.info(
            f"Processing create test item request: {request.title}",
            extra={
                "user_id": user_id,
                "feature_id": request.feature_id,
                "scenario_id": request.scenario_id
            }
        )
        
        try:
            # Create test item via service
            test_item = await self.test_item_service.create_test_item(request, user_id)
            
            # Build response with full details for creation
            include_fields = {"core", "steps", "selectors", "metadata", "computed"}
            test_item_response = self.response_service.build_response(
                test_item, include_fields
            )
            
            # Create success response
            response = TestItemCreateResponse.create_success(
                test_item=test_item_response,
                message=f"Test item '{test_item.title}' created successfully"
            )
            
            logger.info(
                f"Test item created successfully: {test_item.id}",
                extra={
                    "test_item_id": test_item.id,
                    "title": test_item.title,
                    "user_id": user_id
                }
            )
            
            return response
            
        except ValueError as e:
            logger.warning(
                f"Validation error creating test item: {e}",
                extra={"user_id": user_id, "title": request.title}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Validation error: {str(e)}"
            )
            
        except Exception as e:
            logger.error(
                f"Failed to create test item: {e}",
                extra={
                    "user_id": user_id,
                    "title": request.title,
                    "error": str(e)
                }
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create test item"
            )
    
    async def get_test_item(
        self,
        item_id: str,
        user_id: str,
        include_fields: Optional[str] = None
    ) -> TestItemDetailResponse:
        """
        Handle test item retrieval request.
        
        Args:
            item_id: Test item ID
            user_id: Authenticated user ID
            include_fields: Optional comma-separated fields to include
            
        Returns:
            TestItemDetailResponse with test item details
            
        Raises:
            HTTPException: If retrieval fails or item not found
        """
        logger.debug(
            f"Processing get test item request: {item_id}",
            extra={"test_item_id": item_id, "user_id": user_id}
        )
        
        try:
            # Validate item_id format
            if not self._is_valid_object_id(item_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid test item ID format"
                )
            
            # Parse include fields
            parsed_include_fields = self._parse_include_fields(include_fields)
            
            # Retrieve test item via service
            test_item = await self.test_item_service.get_test_item(
                item_id, user_id, parsed_include_fields
            )
            
            if not test_item:
                logger.warning(
                    f"Test item not found: {item_id}",
                    extra={"test_item_id": item_id, "user_id": user_id}
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Test item not found"
                )
            
            # Build response with requested fields
            test_item_response = self.response_service.build_response(
                test_item, parsed_include_fields
            )
            
            # Create success response
            response = TestItemDetailResponse.create_success(
                test_item=test_item_response,
                message="Test item retrieved successfully"
            )
            
            logger.debug(
                f"Test item retrieved successfully: {item_id}",
                extra={"test_item_id": item_id, "title": test_item.title}
            )
            
            return response
            
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
            
        except Exception as e:
            logger.error(
                f"Failed to retrieve test item {item_id}: {e}",
                extra={"test_item_id": item_id, "user_id": user_id, "error": str(e)}
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve test item"
            )
    
    async def list_test_items(
        self,
        user_id: str,
        filters: FilterTestItemsRequest
    ) -> TestItemListResponse:
        """
        Handle test items list request with filtering and pagination.
        
        Args:
            user_id: Authenticated user ID
            filters: Filter and pagination parameters
            
        Returns:
            TestItemListResponse with paginated test items
            
        Raises:
            HTTPException: If listing fails
        """
        logger.debug(
            f"Processing list test items request for user: {user_id}",
            extra={
                "user_id": user_id,
                "page": filters.page,
                "page_size": filters.page_size,
                "feature_id": filters.feature_id,
                "test_type": filters.test_type.value if hasattr(filters.test_type, 'value') else str(filters.test_type) if filters.test_type else None,
                "status": filters.status.value if filters.status else None
            }
        )
        
        try:
            # List test items via service
            (
                test_items,
                total_count,
                pagination_meta,
                filter_meta,
                sort_meta
            ) = await self.test_item_service.list_test_items(user_id, filters)
            
            # Parse include fields for response building
            parsed_include_fields = self._parse_include_fields(filters.include_fields)
            
            # Build response list with selective field inclusion
            test_item_responses = self.response_service.build_list_responses(
                test_items, parsed_include_fields
            )
            
            # Create summary statistics
            summary = self.response_service.create_summary_stats(total_count)
            
            # Create success response
            response = TestItemListResponse.create_success(
                items=test_item_responses,
                pagination=pagination_meta,
                filters=filter_meta,
                sorting=sort_meta,
                summary=summary,
                message=f"Retrieved {len(test_item_responses)} test items (total: {total_count})"
            )
            
            logger.info(
                f"Listed {len(test_item_responses)} test items for user {user_id} (total: {total_count})",
                extra={
                    "user_id": user_id,
                    "returned_count": len(test_item_responses),
                    "total_count": total_count,
                    "page": filters.page
                }
            )
            
            return response
            
        except Exception as e:
            logger.error(
                f"Failed to list test items for user {user_id}: {e}",
                extra={"user_id": user_id, "error": str(e)}
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve test items"
            )
    
    async def get_health_status(self) -> dict:
        """
        Handle health status request for test item service.
        
        Returns:
            Health status information
        """
        logger.debug("Processing test item service health check")
        
        try:
            health_info = await self.test_item_service.get_health_status()
            
            logger.debug(
                f"Test item service health: {health_info.get('status', 'unknown')}"
            )
            
            return health_info
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    def _is_valid_object_id(self, object_id: str) -> bool:
        """
        Validate MongoDB ObjectId format.
        
        Args:
            object_id: String to validate
            
        Returns:
            True if valid ObjectId format
        """
        try:
            from bson import ObjectId
            ObjectId(object_id)
            return True
        except Exception:
            return False
    
    def _parse_include_fields(self, include_fields_str: Optional[str]) -> Optional[Set[str]]:
        """
        Parse include_fields parameter from request.
        
        Args:
            include_fields_str: Comma-separated string of fields
            
        Returns:
            Set of field names or None
        """
        if not include_fields_str:
            # Default includes for optimal performance
            return {"core", "metadata"}
        
        # Handle special "all" value
        if include_fields_str.lower() == "all":
            return {"core", "steps", "selectors", "metadata", "execution_stats", "type_data", "computed"}
        
        # Parse comma-separated fields
        fields = {field.strip() for field in include_fields_str.split(",") if field.strip()}
        
        # Always include core
        fields.add("core")
        
        # Validate field names
        valid_fields = {
            "core", "steps", "selectors", "metadata", "execution_stats", "type_data", "computed"
        }
        
        invalid_fields = fields - valid_fields
        if invalid_fields:
            logger.warning(
                f"Invalid include fields: {invalid_fields}",
                extra={"invalid_fields": list(invalid_fields)}
            )
            # Remove invalid fields but continue
            fields = fields & valid_fields
        
        return fields
    
    def _create_error_response(
        self,
        message: str,
        error_code: Optional[str] = None,
        error_details: Optional[dict] = None
    ) -> ErrorResponse:
        """
        Create standardized error response.
        
        Args:
            message: Error message
            error_code: Optional error code
            error_details: Optional error details
            
        Returns:
            ErrorResponse instance
        """
        return ErrorResponse(
            message=message,
            error_code=error_code,
            error_details=error_details
        )


class TestItemControllerFactory:
    """
    Factory for creating TestItemController instances with proper dependencies.
    """
    
    @staticmethod
    def create(test_item_service: TestItemService) -> TestItemController:
        """
        Create TestItemController with injected dependencies.
        
        Args:
            test_item_service: TestItemService instance
            
        Returns:
            Configured TestItemController instance
        """
        return TestItemController(test_item_service) 
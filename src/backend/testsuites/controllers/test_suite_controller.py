"""
Test Suite Controller Layer

Handles HTTP request processing, validation, service orchestration,
and response formatting for test suite endpoints.
Implements clean architecture separation between HTTP concerns and business logic.
"""

from typing import Optional, List
from fastapi import HTTPException, status
from bson import ObjectId

from ...config.logging import get_logger
from ..services.test_suite_service import TestSuiteService
from ..schemas.test_suite_requests import (
    CreateTestSuiteRequest,
    UpdateTestSuiteRequest,
    BulkAddItemsRequest,
    BulkRemoveItemsRequest,
    FilterTestSuitesRequest
)
from ..schemas.test_suite_responses import (
    TestSuiteCreateResponse,
    TestSuiteDetailResponse,
    TestSuiteListResponse,
    TestSuiteUpdateResponse,
    BulkOperationResponse,
    TestSuiteListData
)
from ...schemas.response import ErrorResponse, SuccessResponse

logger = get_logger(__name__)


class TestSuiteController:
    """
    Test Suite Controller for handling HTTP requests and responses.
    
    Provides request validation, service orchestration, and response formatting
    for all test suite operations following clean architecture principles.
    """
    
    def __init__(self, test_suite_service: TestSuiteService):
        """
        Initialize controller with test suite service.
        
        Args:
            test_suite_service: TestSuiteService instance for business logic
        """
        self.test_suite_service = test_suite_service
        
        logger.info("TestSuiteController initialized")
    
    async def create_suite(
        self,
        request: CreateTestSuiteRequest,
        user_id: str
    ) -> TestSuiteCreateResponse:
        """
        Handle test suite creation request.
        
        Orchestrates suite creation via service layer and formats HTTP response
        with comprehensive error handling and logging.
        
        Args:
            request: Test suite creation request with metadata and optional items
            user_id: Authenticated user ID from JWT context
            
        Returns:
            TestSuiteCreateResponse with created suite details
            
        Raises:
            HTTPException: If creation fails with appropriate status codes
        """
        logger.info(
            f"Processing create test suite request: {request.title}",
            extra={
                "user_id": user_id,
                "title": request.title,
                "initial_items": len(request.suite_items),
                "priority": request.priority.value
            }
        )
        
        try:
            # Create test suite via service layer
            test_suite_response = await self.test_suite_service.create_suite(request, user_id)
            
            # Format successful response
            response = TestSuiteCreateResponse.create_success(
                test_suite=test_suite_response,
                message=f"Test suite '{test_suite_response.core.title}' created successfully"
            )
            
            logger.info(
                f"Test suite created successfully: {test_suite_response.core.id}",
                extra={
                    "suite_id": test_suite_response.core.id,
                    "title": test_suite_response.core.title,
                    "user_id": user_id,
                    "items_count": test_suite_response.core.total_items
                }
            )
            
            return response
            
        except HTTPException as e:
            # Re-raise service layer HTTP exceptions (validation, business logic errors)
            logger.warning(
                f"Business logic error creating test suite: {e.detail}",
                extra={
                    "user_id": user_id,
                    "title": request.title,
                    "status_code": e.status_code
                }
            )
            raise
            
        except ValueError as e:
            # Handle validation errors
            logger.warning(
                f"Validation error creating test suite: {e}",
                extra={"user_id": user_id, "title": request.title}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Validation error: {str(e)}"
            )
            
        except Exception as e:
            # Handle unexpected errors
            logger.error(
                f"Unexpected error creating test suite: {e}",
                extra={
                    "user_id": user_id,
                    "title": request.title,
                    "error": str(e)
                }
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create test suite"
            )
    
    async def get_suite(
        self,
        suite_id: str,
        include_fields: Optional[List[str]],
        user_id: str
    ) -> TestSuiteDetailResponse:
        """
        Handle test suite retrieval request.
        
        Orchestrates suite retrieval with field inclusion control and
        formats appropriate HTTP response with error handling.
        
        Args:
            suite_id: Test suite identifier
            include_fields: Optional list of fields to include (items, statistics, computed)
            user_id: Authenticated user ID from JWT context
            
        Returns:
            TestSuiteDetailResponse with suite details
            
        Raises:
            HTTPException: If retrieval fails or suite not found
        """
        logger.info(
            f"Processing get test suite request: {suite_id}",
            extra={
                "suite_id": suite_id,
                "user_id": user_id,
                "include_fields": include_fields
            }
        )
        
        try:
            # Validate suite ID format
            if not self._is_valid_object_id(suite_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid suite ID format"
                )
            
            # Retrieve test suite via service layer
            test_suite_response = await self.test_suite_service.get_suite(
                suite_id, include_fields, user_id
            )
            
            if not test_suite_response:
                logger.warning(
                    f"Test suite not found: {suite_id}",
                    extra={"suite_id": suite_id, "user_id": user_id}
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Test suite not found or access denied"
                )
            
            # Format successful response
            response = TestSuiteDetailResponse.create_success(
                test_suite=test_suite_response,
                message="Test suite retrieved successfully"
            )
            
            logger.info(
                f"Test suite retrieved successfully: {suite_id}",
                extra={
                    "suite_id": suite_id,
                    "title": test_suite_response.core.title,
                    "user_id": user_id
                }
            )
            
            return response
            
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
            
        except Exception as e:
            # Handle unexpected errors
            logger.error(
                f"Unexpected error retrieving test suite {suite_id}: {e}",
                extra={"suite_id": suite_id, "user_id": user_id, "error": str(e)}
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve test suite"
            )
    
    async def list_suites(
        self,
        filters: FilterTestSuitesRequest,
        user_id: str
    ) -> TestSuiteListResponse:
        """
        Handle test suite listing request with filtering and pagination.
        
        Orchestrates suite listing via service layer with comprehensive
        filtering, pagination, and sorting support.
        
        Args:
            filters: Filter, pagination, and sorting parameters
            user_id: Authenticated user ID from JWT context
            
        Returns:
            TestSuiteListResponse with paginated suite list and metadata
            
        Raises:
            HTTPException: If listing fails
        """
        logger.info(
            f"Processing list test suites request for user: {user_id}",
            extra={
                "user_id": user_id,
                "page": filters.page,
                "page_size": filters.page_size,
                "filters_applied": self._get_applied_filters_count(filters)
            }
        )
        
        try:
            # List test suites via service layer
            suites, pagination_meta, filter_meta, sort_meta = await self.test_suite_service.list_suites(
                filters, user_id
            )
            
            # Create summary statistics
            summary = {
                "total_suites": pagination_meta.total_items,
                "current_page_count": len(suites),
                "filters_applied": self._get_applied_filters_count(filters),
                "page_info": {
                    "current": pagination_meta.page,
                    "total_pages": pagination_meta.total_pages,
                    "has_next": pagination_meta.has_next,
                    "has_previous": pagination_meta.has_previous
                }
            }
            
            # Format successful response
            response = TestSuiteListResponse.create_success(
                suites=suites,
                pagination=pagination_meta,
                filters=filter_meta,
                sorting=sort_meta,
                summary=summary,
                message=f"Retrieved {len(suites)} test suites"
            )
            
            logger.info(
                f"Test suites listed successfully: {len(suites)} of {pagination_meta.total_items}",
                extra={
                    "user_id": user_id,
                    "returned_count": len(suites),
                    "total_count": pagination_meta.total_items,
                    "page": filters.page
                }
            )
            
            return response
            
        except HTTPException as e:
            # Re-raise service layer HTTP exceptions
            logger.warning(
                f"Service error listing test suites: {e.detail}",
                extra={"user_id": user_id, "status_code": e.status_code}
            )
            raise
            
        except Exception as e:
            # Handle unexpected errors
            logger.error(
                f"Unexpected error listing test suites: {e}",
                extra={"user_id": user_id, "error": str(e)}
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to list test suites"
            )
    
    async def update_suite(
        self,
        suite_id: str,
        request: UpdateTestSuiteRequest,
        user_id: str
    ) -> TestSuiteUpdateResponse:
        """
        Handle test suite update request.
        
        Orchestrates suite metadata updates via service layer with
        comprehensive validation and error handling.
        
        Args:
            suite_id: Test suite identifier
            request: Update request with partial suite metadata
            user_id: Authenticated user ID from JWT context
            
        Returns:
            TestSuiteUpdateResponse with updated suite details
            
        Raises:
            HTTPException: If update fails or suite not found
        """
        logger.info(
            f"Processing update test suite request: {suite_id}",
            extra={
                "suite_id": suite_id,
                "user_id": user_id,
                "update_fields": list(request.dict(exclude_none=True).keys())
            }
        )
        
        try:
            # Validate suite ID format
            if not self._is_valid_object_id(suite_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid suite ID format"
                )
            
            # Update test suite via service layer
            test_suite_response = await self.test_suite_service.update_suite(
                suite_id, request, user_id
            )
            
            # Format successful response
            response = TestSuiteUpdateResponse.create_success(
                test_suite=test_suite_response,
                message=f"Test suite '{test_suite_response.core.title}' updated successfully"
            )
            
            logger.info(
                f"Test suite updated successfully: {suite_id}",
                extra={
                    "suite_id": suite_id,
                    "title": test_suite_response.core.title,
                    "user_id": user_id,
                    "updated_fields": list(request.dict(exclude_none=True).keys())
                }
            )
            
            return response
            
        except HTTPException as e:
            # Re-raise service layer HTTP exceptions
            logger.warning(
                f"Service error updating test suite: {e.detail}",
                extra={
                    "suite_id": suite_id,
                    "user_id": user_id,
                    "status_code": e.status_code
                }
            )
            raise
            
        except ValueError as e:
            # Handle validation errors
            logger.warning(
                f"Validation error updating test suite: {e}",
                extra={"suite_id": suite_id, "user_id": user_id}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Validation error: {str(e)}"
            )
            
        except Exception as e:
            # Handle unexpected errors
            logger.error(
                f"Unexpected error updating test suite {suite_id}: {e}",
                extra={"suite_id": suite_id, "user_id": user_id, "error": str(e)}
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update test suite"
            )
    
    async def add_items(
        self,
        suite_id: str,
        request: BulkAddItemsRequest,
        user_id: str
    ) -> BulkOperationResponse:
        """
        Handle bulk add items request.
        
        Orchestrates bulk item addition via service layer with
        comprehensive validation and partial success handling.
        
        Args:
            suite_id: Test suite identifier
            request: Bulk add request with item configurations
            user_id: Authenticated user ID from JWT context
            
        Returns:
            BulkOperationResponse with operation results
            
        Raises:
            HTTPException: If operation fails or suite not found
        """
        logger.info(
            f"Processing bulk add items request for suite: {suite_id}",
            extra={
                "suite_id": suite_id,
                "user_id": user_id,
                "items_count": len(request.items)
            }
        )
        
        try:
            # Validate suite ID format
            if not self._is_valid_object_id(suite_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid suite ID format"
                )
            
            # Add items via service layer
            operation_result = await self.test_suite_service.add_items(
                suite_id, request, user_id
            )
            
            # Format response based on operation success
            if operation_result.overall_success:
                message = f"Successfully added {operation_result.successful} items to suite"
            else:
                message = f"Added {operation_result.successful} items with {operation_result.failed} failures"
            
            response = BulkOperationResponse.create_success(
                result=operation_result,
                message=message
            )
            
            logger.info(
                f"Bulk add items completed: {operation_result.successful} successful, {operation_result.failed} failed",
                extra={
                    "suite_id": suite_id,
                    "user_id": user_id,
                    "successful": operation_result.successful,
                    "failed": operation_result.failed,
                    "overall_success": operation_result.overall_success
                }
            )
            
            return response
            
        except HTTPException as e:
            # Re-raise service layer HTTP exceptions
            logger.warning(
                f"Service error adding items to suite: {e.detail}",
                extra={
                    "suite_id": suite_id,
                    "user_id": user_id,
                    "status_code": e.status_code
                }
            )
            raise
            
        except Exception as e:
            # Handle unexpected errors
            logger.error(
                f"Unexpected error adding items to suite {suite_id}: {e}",
                extra={"suite_id": suite_id, "user_id": user_id, "error": str(e)}
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to add items to suite"
            )
    
    async def remove_items(
        self,
        suite_id: str,
        request: BulkRemoveItemsRequest,
        user_id: str
    ) -> BulkOperationResponse:
        """
        Handle bulk remove items request.
        
        Orchestrates bulk item removal via service layer with
        optional order rebalancing and comprehensive result reporting.
        
        Args:
            suite_id: Test suite identifier
            request: Bulk remove request with item IDs and options
            user_id: Authenticated user ID from JWT context
            
        Returns:
            BulkOperationResponse with operation results
            
        Raises:
            HTTPException: If operation fails or suite not found
        """
        logger.info(
            f"Processing bulk remove items request for suite: {suite_id}",
            extra={
                "suite_id": suite_id,
                "user_id": user_id,
                "items_count": len(request.test_item_ids),
                "rebalance_order": request.rebalance_order
            }
        )
        
        try:
            # Validate suite ID format
            if not self._is_valid_object_id(suite_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid suite ID format"
                )
            
            # Remove items via service layer
            operation_result = await self.test_suite_service.remove_items(
                suite_id, request, user_id
            )
            
            # Format response based on operation success
            if operation_result.overall_success:
                message = f"Successfully removed {operation_result.successful} items from suite"
                if request.rebalance_order:
                    message += " with order rebalancing"
            else:
                message = f"Removed {operation_result.successful} items with {operation_result.failed} not found"
            
            response = BulkOperationResponse.create_success(
                result=operation_result,
                message=message
            )
            
            logger.info(
                f"Bulk remove items completed: {operation_result.successful} successful, {operation_result.failed} failed",
                extra={
                    "suite_id": suite_id,
                    "user_id": user_id,
                    "successful": operation_result.successful,
                    "failed": operation_result.failed,
                    "rebalanced": request.rebalance_order,
                    "overall_success": operation_result.overall_success
                }
            )
            
            return response
            
        except HTTPException as e:
            # Re-raise service layer HTTP exceptions
            logger.warning(
                f"Service error removing items from suite: {e.detail}",
                extra={
                    "suite_id": suite_id,
                    "user_id": user_id,
                    "status_code": e.status_code
                }
            )
            raise
            
        except Exception as e:
            # Handle unexpected errors
            logger.error(
                f"Unexpected error removing items from suite {suite_id}: {e}",
                extra={"suite_id": suite_id, "user_id": user_id, "error": str(e)}
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to remove items from suite"
            )
    
    async def delete_suite(
        self,
        suite_id: str,
        user_id: str
    ) -> SuccessResponse:
        """
        Handle test suite deletion request.
        
        Orchestrates suite soft deletion via service layer with
        comprehensive validation and logging.
        
        Args:
            suite_id: Test suite identifier
            user_id: Authenticated user ID from JWT context
            
        Returns:
            SuccessResponse confirming deletion
            
        Raises:
            HTTPException: If deletion fails or suite not found
        """
        logger.info(
            f"Processing delete test suite request: {suite_id}",
            extra={"suite_id": suite_id, "user_id": user_id}
        )
        
        try:
            # Validate suite ID format
            if not self._is_valid_object_id(suite_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid suite ID format"
                )
            
            # Delete test suite via service layer
            success = await self.test_suite_service.delete_suite(suite_id, user_id)
            
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Test suite not found or access denied"
                )
            
            # Format successful response
            response = SuccessResponse(
                data={"suite_id": suite_id, "deleted": True},
                message="Test suite deleted successfully"
            )
            
            logger.info(
                f"Test suite deleted successfully: {suite_id}",
                extra={"suite_id": suite_id, "user_id": user_id}
            )
            
            return response
            
        except HTTPException as e:
            # Re-raise service layer HTTP exceptions
            logger.warning(
                f"Service error deleting test suite: {e.detail}",
                extra={
                    "suite_id": suite_id,
                    "user_id": user_id,
                    "status_code": e.status_code
                }
            )
            raise
            
        except Exception as e:
            # Handle unexpected errors
            logger.error(
                f"Unexpected error deleting test suite {suite_id}: {e}",
                extra={"suite_id": suite_id, "user_id": user_id, "error": str(e)}
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete test suite"
            )
    
    # Private helper methods for validation and utility functions
    
    def _is_valid_object_id(self, object_id: str) -> bool:
        """
        Validate MongoDB ObjectId format.
        
        Args:
            object_id: String to validate as ObjectId
            
        Returns:
            True if valid ObjectId format, False otherwise
        """
        try:
            ObjectId(object_id)
            return True
        except Exception:
            return False
    
    def _get_applied_filters_count(self, filters: FilterTestSuitesRequest) -> int:
        """
        Count the number of filters applied in the request.
        
        Args:
            filters: Filter request to analyze
            
        Returns:
            Number of active filters
        """
        active_filters = 0
        
        if filters.status:
            active_filters += 1
        if filters.priority:
            active_filters += 1
        if filters.tags:
            active_filters += 1
        if filters.title_search:
            active_filters += 1
        if filters.has_items is not None:
            active_filters += 1
            
        return active_filters


class TestSuiteControllerFactory:
    """
    Factory for creating TestSuiteController instances with proper dependencies.
    
    Provides clean dependency injection and separation of concerns
    for controller instantiation.
    """
    
    @staticmethod
    def create(test_suite_service: TestSuiteService) -> TestSuiteController:
        """
        Create TestSuiteController instance with injected service.
        
        Args:
            test_suite_service: TestSuiteService instance for business logic
            
        Returns:
            Configured TestSuiteController instance
        """
        return TestSuiteController(test_suite_service) 
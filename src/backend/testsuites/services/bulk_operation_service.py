"""
Bulk operation service for test suite management.

Provides efficient bulk operations for adding and removing test items
from test suites with comprehensive validation and partial success handling.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

from ...config.logging import get_logger
from .test_suite_service import TestSuiteService
from .validation_service import TestItemValidationService

logger = get_logger(__name__)


class BulkOperationService:
    """
    Service for handling bulk operations on test suite items.
    
    Provides efficient batch operations for adding and removing test items
    with comprehensive validation, partial success handling, and detailed reporting.
    """
    
    def __init__(
        self, 
        suite_service: TestSuiteService,
        validation_service: TestItemValidationService
    ):
        """
        Initialize the bulk operation service.
        
        Args:
            suite_service: Test suite service for database operations
            validation_service: Validation service for test item validation
        """
        self.suite_service = suite_service
        self.validation_service = validation_service
    
    async def bulk_add_items(
        self,
        suite_id: str,
        items: List[Dict[str, Any]],
        user_id: str
    ) -> Dict[str, Any]:
        """
        Add multiple test items to a suite with validation and partial success handling.
        
        Args:
            suite_id: Test suite ID
            items: List of item configurations to add
            user_id: User ID for access control
            
        Returns:
            Dict containing operation results:
            - success_count: Number of successfully added items
            - invalid_count: Number of invalid items
            - duplicate_count: Number of duplicate items
            - added_items: List of successfully added items
            - invalid_items: List of invalid items with reasons
            - duplicate_items: List of duplicate items
            - overall_success: Boolean indicating if operation succeeded
        """
        logger.info(
            f"Starting bulk add operation: {len(items)} items to suite {suite_id}",
            extra={
                "suite_id": suite_id,
                "user_id": user_id,
                "item_count": len(items),
                "service": "bulk_operation"
            }
        )
        
        # Validate operation size
        size_validation = await self.validation_service.validate_bulk_operation_limits(
            len(items)
        )
        
        if not size_validation["is_valid"]:
            return {
                "success_count": 0,
                "invalid_count": len(items),
                "duplicate_count": 0,
                "added_items": [],
                "invalid_items": [
                    {
                        "item": item,
                        "reason": size_validation["message"]
                    }
                    for item in items
                ],
                "duplicate_items": [],
                "overall_success": False,
                "message": size_validation["message"]
            }
        
        # Extract test item IDs for validation
        test_item_ids = [item.get("test_item_id") for item in items if item.get("test_item_id")]
        
        # Validate test item references
        validation_result = await self.validation_service.validate_test_item_ids(
            test_item_ids, user_id
        )
        
        # Get current suite to check for duplicates
        suite = await self.suite_service.get_suite_by_id(suite_id, user_id)
        if not suite:
            return {
                "success_count": 0,
                "invalid_count": len(items),
                "duplicate_count": 0,
                "added_items": [],
                "invalid_items": [
                    {
                        "item": item,
                        "reason": "Test suite not found or access denied"
                    }
                    for item in items
                ],
                "duplicate_items": [],
                "overall_success": False,
                "message": "Test suite not found or access denied"
            }
        
        # Check for existing items in the suite
        existing_item_ids = {
            item.get("test_item_id") 
            for item in suite.get("items", [])
        }
        
        # Categorize items
        added_items = []
        invalid_items = []
        duplicate_items = []
        
        invalid_id_set = {
            invalid["test_item_id"] 
            for invalid in validation_result["invalid_ids"]
        }
        
        for item in items:
            test_item_id = item.get("test_item_id")
            
            if test_item_id in invalid_id_set:
                # Find the specific reason from validation
                reason = next(
                    (invalid["reason"] for invalid in validation_result["invalid_ids"] 
                     if invalid["test_item_id"] == test_item_id),
                    "Invalid test item reference"
                )
                invalid_items.append({
                    "item": item,
                    "reason": reason
                })
            elif test_item_id in existing_item_ids:
                duplicate_items.append({
                    "item": item,
                    "reason": "Test item already exists in suite"
                })
            else:
                # Valid item to add
                item_config = {
                    "test_item_id": test_item_id,
                    "order": item.get("order", 0),
                    "skip": item.get("skip", False),
                    "custom_tags": item.get("custom_tags", []),
                    "note": item.get("note"),
                    "added_at": datetime.utcnow()
                }
                added_items.append(item_config)
        
        # Add valid items to the suite
        if added_items:
            try:
                await self.suite_service.add_items_to_suite(
                    suite_id, added_items, user_id
                )
                logger.info(
                    f"Successfully added {len(added_items)} items to suite {suite_id}",
                    extra={
                        "suite_id": suite_id,
                        "user_id": user_id,
                        "added_count": len(added_items),
                        "service": "bulk_operation"
                    }
                )
            except Exception as e:
                logger.error(
                    f"Failed to add items to suite {suite_id}: {e}",
                    extra={
                        "suite_id": suite_id,
                        "user_id": user_id,
                        "error": str(e),
                        "service": "bulk_operation"
                    }
                )
                # Move all items to invalid if database operation fails
                invalid_items.extend([
                    {
                        "item": item,
                        "reason": "Database operation failed"
                    }
                    for item in added_items
                ])
                added_items = []
        
        result = {
            "success_count": len(added_items),
            "invalid_count": len(invalid_items),
            "duplicate_count": len(duplicate_items),
            "added_items": added_items,
            "invalid_items": invalid_items,
            "duplicate_items": duplicate_items,
            "overall_success": len(added_items) > 0,
            "message": self._generate_bulk_add_message(
                len(added_items), len(invalid_items), len(duplicate_items)
            )
        }
        
        logger.info(
            f"Bulk add operation completed: {result['success_count']} added, "
            f"{result['invalid_count']} invalid, {result['duplicate_count']} duplicates",
            extra={
                "suite_id": suite_id,
                "user_id": user_id,
                "result": result,
                "service": "bulk_operation"
            }
        )
        
        return result
    
    async def bulk_remove_items(
        self,
        suite_id: str,
        test_item_ids: List[str],
        user_id: str,
        rebalance_order: bool = False
    ) -> Dict[str, Any]:
        """
        Remove multiple test items from a suite.
        
        Args:
            suite_id: Test suite ID
            test_item_ids: List of test item IDs to remove
            user_id: User ID for access control
            rebalance_order: Whether to rebalance order after removal
            
        Returns:
            Dict containing operation results:
            - success_count: Number of successfully removed items
            - not_found_count: Number of items not found in suite
            - removed_items: List of removed item IDs
            - not_found_items: List of item IDs not found in suite
            - overall_success: Boolean indicating if operation succeeded
        """
        logger.info(
            f"Starting bulk remove operation: {len(test_item_ids)} items from suite {suite_id}",
            extra={
                "suite_id": suite_id,
                "user_id": user_id,
                "item_count": len(test_item_ids),
                "rebalance_order": rebalance_order,
                "service": "bulk_operation"
            }
        )
        
        # Get current suite
        suite = await self.suite_service.get_suite_by_id(suite_id, user_id)
        if not suite:
            return {
                "success_count": 0,
                "not_found_count": len(test_item_ids),
                "removed_items": [],
                "not_found_items": test_item_ids,
                "overall_success": False,
                "message": "Test suite not found or access denied"
            }
        
        # Check which items exist in the suite
        existing_item_ids = {
            item.get("test_item_id") 
            for item in suite.get("items", [])
        }
        
        # Categorize items
        items_to_remove = []
        not_found_items = []
        
        for test_item_id in test_item_ids:
            if test_item_id in existing_item_ids:
                items_to_remove.append(test_item_id)
            else:
                not_found_items.append(test_item_id)
        
        # Remove items from the suite
        if items_to_remove:
            try:
                await self.suite_service.remove_items_from_suite(
                    suite_id, items_to_remove, user_id, rebalance_order
                )
                logger.info(
                    f"Successfully removed {len(items_to_remove)} items from suite {suite_id}",
                    extra={
                        "suite_id": suite_id,
                        "user_id": user_id,
                        "removed_count": len(items_to_remove),
                        "rebalance_order": rebalance_order,
                        "service": "bulk_operation"
                    }
                )
            except Exception as e:
                logger.error(
                    f"Failed to remove items from suite {suite_id}: {e}",
                    extra={
                        "suite_id": suite_id,
                        "user_id": user_id,
                        "error": str(e),
                        "service": "bulk_operation"
                    }
                )
                # Move all items to not_found if database operation fails
                not_found_items.extend(items_to_remove)
                items_to_remove = []
        
        result = {
            "success_count": len(items_to_remove),
            "not_found_count": len(not_found_items),
            "removed_items": items_to_remove,
            "not_found_items": not_found_items,
            "overall_success": len(items_to_remove) > 0,
            "message": self._generate_bulk_remove_message(
                len(items_to_remove), len(not_found_items)
            )
        }
        
        logger.info(
            f"Bulk remove operation completed: {result['success_count']} removed, "
            f"{result['not_found_count']} not found",
            extra={
                "suite_id": suite_id,
                "user_id": user_id,
                "result": result,
                "service": "bulk_operation"
            }
        )
        
        return result
    
    def _generate_bulk_add_message(
        self, 
        success_count: int, 
        invalid_count: int, 
        duplicate_count: int
    ) -> str:
        """Generate a descriptive message for bulk add operation results."""
        if success_count == 0:
            if invalid_count > 0 and duplicate_count > 0:
                return f"No items added: {invalid_count} invalid, {duplicate_count} duplicates"
            elif invalid_count > 0:
                return f"No items added: {invalid_count} invalid items"
            elif duplicate_count > 0:
                return f"No items added: {duplicate_count} duplicate items"
            else:
                return "No items added"
        else:
            parts = [f"{success_count} items added successfully"]
            if invalid_count > 0:
                parts.append(f"{invalid_count} invalid")
            if duplicate_count > 0:
                parts.append(f"{duplicate_count} duplicates")
            return "; ".join(parts)
    
    def _generate_bulk_remove_message(
        self, 
        success_count: int, 
        not_found_count: int
    ) -> str:
        """Generate a descriptive message for bulk remove operation results."""
        if success_count == 0:
            if not_found_count > 0:
                return f"No items removed: {not_found_count} items not found in suite"
            else:
                return "No items removed"
        else:
            parts = [f"{success_count} items removed successfully"]
            if not_found_count > 0:
                parts.append(f"{not_found_count} not found")
            return "; ".join(parts) 
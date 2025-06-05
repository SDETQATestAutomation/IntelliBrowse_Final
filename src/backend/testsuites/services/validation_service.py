"""
Test item validation service for test suite operations.

Provides validation services for test item references, ensuring data integrity
and access control for test suite operations.
"""

from typing import List, Dict, Any, Optional, Set
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from ...config.logging import get_logger

logger = get_logger(__name__)


class TestItemValidationService:
    """
    Service for validating test item references in test suite operations.
    
    Provides comprehensive validation for test item IDs, ensuring they exist,
    belong to the correct user, and are accessible for suite operations.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        """
        Initialize the validation service.
        
        Args:
            db: MongoDB database instance
        """
        self.db = db
        self.test_items_collection = db.test_items
    
    async def validate_test_item_ids(
        self, 
        test_item_ids: List[str], 
        user_id: str
    ) -> Dict[str, Any]:
        """
        Validate a list of test item IDs for a specific user.
        
        Args:
            test_item_ids: List of test item IDs to validate
            user_id: User ID for access control
            
        Returns:
            Dict containing validation results:
            - valid_ids: List of valid test item IDs
            - invalid_ids: List of invalid test item IDs with reasons
            - total_count: Total number of IDs validated
            - valid_count: Number of valid IDs
            - invalid_count: Number of invalid IDs
        """
        if not test_item_ids:
            return {
                "valid_ids": [],
                "invalid_ids": [],
                "total_count": 0,
                "valid_count": 0,
                "invalid_count": 0
            }
        
        logger.debug(
            f"Validating {len(test_item_ids)} test item IDs for user {user_id}",
            extra={
                "user_id": user_id,
                "item_count": len(test_item_ids),
                "service": "validation"
            }
        )
        
        valid_ids = []
        invalid_ids = []
        
        # Convert string IDs to ObjectIds and validate format
        object_ids = []
        for item_id in test_item_ids:
            try:
                object_ids.append(ObjectId(item_id))
            except Exception:
                invalid_ids.append({
                    "test_item_id": item_id,
                    "reason": "Invalid ObjectId format"
                })
                continue
        
        if object_ids:
            # Query database for existing items belonging to the user
            cursor = self.test_items_collection.find({
                "_id": {"$in": object_ids},
                "audit.created_by_user_id": user_id
            })
            
            existing_items = await cursor.to_list(length=None)
            existing_ids = {str(item["_id"]) for item in existing_items}
            
            # Categorize IDs as valid or invalid
            for item_id in test_item_ids:
                if item_id in existing_ids:
                    valid_ids.append(item_id)
                elif item_id not in [invalid["test_item_id"] for invalid in invalid_ids]:
                    # Only add if not already marked as invalid due to format
                    invalid_ids.append({
                        "test_item_id": item_id,
                        "reason": "Test item not found or access denied"
                    })
        
        result = {
            "valid_ids": valid_ids,
            "invalid_ids": invalid_ids,
            "total_count": len(test_item_ids),
            "valid_count": len(valid_ids),
            "invalid_count": len(invalid_ids)
        }
        
        logger.info(
            f"Validation completed: {result['valid_count']}/{result['total_count']} valid",
            extra={
                "user_id": user_id,
                "validation_result": result,
                "service": "validation"
            }
        )
        
        return result
    
    async def check_test_item_exists(self, test_item_id: str, user_id: str) -> bool:
        """
        Check if a single test item exists and belongs to the user.
        
        Args:
            test_item_id: Test item ID to check
            user_id: User ID for access control
            
        Returns:
            True if the test item exists and belongs to the user, False otherwise
        """
        try:
            object_id = ObjectId(test_item_id)
        except Exception:
            return False
        
        count = await self.test_items_collection.count_documents({
            "_id": object_id,
            "audit.created_by_user_id": user_id
        })
        
        return count > 0
    
    async def get_test_item_details(
        self, 
        test_item_ids: List[str], 
        user_id: str
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get detailed information for valid test items.
        
        Args:
            test_item_ids: List of test item IDs
            user_id: User ID for access control
            
        Returns:
            Dict mapping test_item_id to item details for valid items
        """
        if not test_item_ids:
            return {}
        
        try:
            object_ids = [ObjectId(item_id) for item_id in test_item_ids]
        except Exception as e:
            logger.warning(
                f"Invalid ObjectId format in test item IDs: {e}",
                extra={"user_id": user_id, "service": "validation"}
            )
            return {}
        
        cursor = self.test_items_collection.find({
            "_id": {"$in": object_ids},
            "audit.created_by_user_id": user_id
        })
        
        items = await cursor.to_list(length=None)
        
        return {
            str(item["_id"]): {
                "title": item.get("title", ""),
                "feature_id": item.get("feature_id", ""),
                "scenario_id": item.get("scenario_id", ""),
                "test_type": item.get("test_type", ""),
                "tags": item.get("metadata", {}).get("tags", [])
            }
            for item in items
        }
    
    async def validate_bulk_operation_limits(
        self, 
        operation_size: int, 
        max_items: int = 100
    ) -> Dict[str, Any]:
        """
        Validate bulk operation size limits.
        
        Args:
            operation_size: Number of items in the operation
            max_items: Maximum allowed items (default: 100)
            
        Returns:
            Dict containing validation result and details
        """
        is_valid = operation_size <= max_items
        
        return {
            "is_valid": is_valid,
            "operation_size": operation_size,
            "max_allowed": max_items,
            "message": (
                "Operation size is within limits" if is_valid 
                else f"Operation size ({operation_size}) exceeds limit ({max_items})"
            )
        } 
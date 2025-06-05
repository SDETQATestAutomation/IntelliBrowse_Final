"""
MongoDB Index Management for Test Suites

Handles MongoDB index creation, management, and validation for the test suites collection.
Provides async operations with comprehensive error handling and logging.
"""

import asyncio
from typing import List, Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection
from pymongo.errors import OperationFailure, DuplicateKeyError

from ...config.env import get_settings
from ...config.logging import get_logger
from .test_suite_model import TestSuiteModelOperations

logger = get_logger(__name__)


class TestSuiteIndexManager:
    """
    MongoDB index management for test suites collection.
    
    Handles index creation, validation, and maintenance operations
    with comprehensive error handling and fallback mechanisms.
    """
    
    def __init__(self, client: AsyncIOMotorClient):
        """
        Initialize index manager.
        
        Args:
            client: Async MongoDB client
        """
        self.client = client
        self.settings = get_settings()
        self.db = client[self.settings.mongodb_database]
        self.collection: AsyncIOMotorCollection = self.db["test_suites"]
        self.operations = TestSuiteModelOperations()
    
    async def create_indexes(self) -> Dict[str, Any]:
        """
        Create all required indexes for test suites collection.
        
        Returns:
            Dictionary with creation results and any errors
        """
        results = {
            "success": True,
            "indexes_created": [],
            "indexes_skipped": [],
            "errors": []
        }
        
        try:
            logger.info("Starting index creation for test_suites collection")
            
            # Get index specifications
            index_specs = self.operations.get_indexes()
            
            for index_spec in index_specs:
                try:
                    await self._create_single_index(index_spec, results)
                except Exception as e:
                    logger.error(
                        f"Failed to create index {index_spec.get('name', 'unknown')}: {e}",
                        extra={"index_spec": index_spec, "error": str(e)}
                    )
                    results["errors"].append({
                        "index_name": index_spec.get("name", "unknown"),
                        "error": str(e)
                    })
                    results["success"] = False
            
            # Create TTL index if configured
            if self.settings.test_suite_ttl_days > 0:
                try:
                    await self._create_ttl_index(results)
                except Exception as e:
                    logger.error(f"Failed to create TTL index: {e}")
                    results["errors"].append({
                        "index_name": "ttl_archived_cleanup",
                        "error": str(e)
                    })
            
            # Log final results
            if results["success"]:
                logger.info(
                    f"Index creation completed successfully. "
                    f"Created: {len(results['indexes_created'])}, "
                    f"Skipped: {len(results['indexes_skipped'])}"
                )
            else:
                logger.warning(
                    f"Index creation completed with errors. "
                    f"Created: {len(results['indexes_created'])}, "
                    f"Errors: {len(results['errors'])}"
                )
            
            return results
            
        except Exception as e:
            logger.error(f"Index creation process failed: {e}")
            results["success"] = False
            results["errors"].append({
                "index_name": "global",
                "error": str(e)
            })
            return results
    
    async def _create_single_index(self, index_spec: Dict[str, Any], results: Dict[str, Any]) -> None:
        """
        Create a single index with error handling.
        
        Args:
            index_spec: Index specification
            results: Results dictionary to update
        """
        index_name = index_spec.get("name", "unknown")
        
        try:
            # Check if index already exists
            existing_indexes = await self.collection.list_indexes().to_list(length=None)
            existing_names = [idx.get("name") for idx in existing_indexes]
            
            if index_name in existing_names:
                logger.debug(f"Index {index_name} already exists, skipping")
                results["indexes_skipped"].append(index_name)
                return
            
            # Create the index
            keys = index_spec["keys"]
            options = index_spec.get("options", {})
            options["name"] = index_name
            
            await self.collection.create_index(keys, **options)
            
            logger.info(f"Successfully created index: {index_name}")
            results["indexes_created"].append(index_name)
            
        except DuplicateKeyError:
            logger.debug(f"Index {index_name} already exists (duplicate key), skipping")
            results["indexes_skipped"].append(index_name)
            
        except OperationFailure as e:
            if "already exists" in str(e).lower():
                logger.debug(f"Index {index_name} already exists, skipping")
                results["indexes_skipped"].append(index_name)
            else:
                raise
    
    async def _create_ttl_index(self, results: Dict[str, Any]) -> None:
        """
        Create TTL index for archived test suites.
        
        Args:
            results: Results dictionary to update
        """
        if not hasattr(self.settings, 'test_suite_ttl_days'):
            logger.debug("TTL configuration not found, skipping TTL index")
            return
        
        ttl_seconds = self.settings.test_suite_ttl_days * 24 * 60 * 60
        index_name = "ttl_archived_cleanup"
        
        try:
            # Check if TTL index exists
            existing_indexes = await self.collection.list_indexes().to_list(length=None)
            existing_names = [idx.get("name") for idx in existing_indexes]
            
            if index_name in existing_names:
                logger.debug(f"TTL index {index_name} already exists, skipping")
                results["indexes_skipped"].append(index_name)
                return
            
            # Create TTL index on updated_at for archived suites
            await self.collection.create_index(
                [("updated_at", 1)],
                name=index_name,
                expireAfterSeconds=ttl_seconds,
                partialFilterExpression={"is_archived": True},
                background=True
            )
            
            logger.info(
                f"Created TTL index for archived suites: {self.settings.test_suite_ttl_days} days retention"
            )
            results["indexes_created"].append(index_name)
            
        except Exception as e:
            logger.error(f"Failed to create TTL index: {e}")
            raise
    
    async def validate_indexes(self) -> Dict[str, Any]:
        """
        Validate that all required indexes exist and are correctly configured.
        
        Returns:
            Validation results with missing or incorrect indexes
        """
        results = {
            "valid": True,
            "missing_indexes": [],
            "incorrect_indexes": [],
            "existing_indexes": []
        }
        
        try:
            # Get current indexes
            existing_indexes = await self.collection.list_indexes().to_list(length=None)
            existing_index_names = [idx.get("name") for idx in existing_indexes]
            results["existing_indexes"] = existing_index_names
            
            # Get required indexes
            required_specs = self.operations.get_indexes()
            required_names = [spec.get("name") for spec in required_specs]
            
            # Check for missing indexes
            for required_name in required_names:
                if required_name not in existing_index_names:
                    results["missing_indexes"].append(required_name)
                    results["valid"] = False
            
            # Log validation results
            if results["valid"]:
                logger.info("Index validation successful - all required indexes exist")
            else:
                logger.warning(
                    f"Index validation failed - missing indexes: {results['missing_indexes']}"
                )
            
            return results
            
        except Exception as e:
            logger.error(f"Index validation failed: {e}")
            results["valid"] = False
            results["error"] = str(e)
            return results
    
    async def drop_indexes(self, index_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Drop specified indexes or all non-default indexes.
        
        Args:
            index_names: Specific index names to drop, or None for all
            
        Returns:
            Drop operation results
        """
        results = {
            "success": True,
            "indexes_dropped": [],
            "errors": []
        }
        
        try:
            if index_names is None:
                # Get all custom indexes (exclude _id_ default index)
                existing_indexes = await self.collection.list_indexes().to_list(length=None)
                index_names = [
                    idx.get("name") for idx in existing_indexes 
                    if idx.get("name") != "_id_"
                ]
            
            for index_name in index_names:
                try:
                    await self.collection.drop_index(index_name)
                    logger.info(f"Dropped index: {index_name}")
                    results["indexes_dropped"].append(index_name)
                    
                except OperationFailure as e:
                    if "index not found" in str(e).lower():
                        logger.debug(f"Index {index_name} not found, skipping")
                    else:
                        logger.error(f"Failed to drop index {index_name}: {e}")
                        results["errors"].append({
                            "index_name": index_name,
                            "error": str(e)
                        })
                        results["success"] = False
            
            return results
            
        except Exception as e:
            logger.error(f"Index drop operation failed: {e}")
            results["success"] = False
            results["errors"].append({
                "operation": "drop_indexes",
                "error": str(e)
            })
            return results


async def ensure_test_suite_indexes(client: AsyncIOMotorClient) -> Dict[str, Any]:
    """
    Ensure all test suite indexes are created.
    
    Convenience function for application startup.
    
    Args:
        client: Async MongoDB client
        
    Returns:
        Index creation results
    """
    manager = TestSuiteIndexManager(client)
    return await manager.create_indexes()


async def validate_test_suite_indexes(client: AsyncIOMotorClient) -> Dict[str, Any]:
    """
    Validate test suite indexes exist.
    
    Convenience function for health checks.
    
    Args:
        client: Async MongoDB client
        
    Returns:
        Index validation results
    """
    manager = TestSuiteIndexManager(client)
    return await manager.validate_indexes() 
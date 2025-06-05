"""
Observability service for test suite operations.

Provides monitoring, metrics, and health check capabilities for test suite
operations and service dependencies.
"""

from typing import Dict, Any, Optional
from datetime import datetime
import time

from ...config.logging import get_logger

logger = get_logger(__name__)


class SuiteObservabilityService:
    """
    Service for monitoring and observability of test suite operations.
    
    Provides health checks, metrics collection, and monitoring capabilities
    for test suite services and dependencies.
    """
    
    def __init__(self):
        """Initialize the observability service."""
        self.start_time = datetime.utcnow()
        self.operation_metrics = {
            "total_operations": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "avg_response_time_ms": 0.0
        }
    
    async def get_service_health(self) -> Dict[str, Any]:
        """
        Get comprehensive health status of test suite services.
        
        Returns:
            Dict containing health status and metrics
        """
        uptime_seconds = (datetime.utcnow() - self.start_time).total_seconds()
        
        health_status = {
            "status": "healthy",
            "uptime_seconds": uptime_seconds,
            "uptime_human": self._format_uptime(uptime_seconds),
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "validation_service": "healthy",
                "bulk_operation_service": "healthy",
                "test_suite_service": "healthy"
            },
            "metrics": self.operation_metrics.copy(),
            "version": "1.0.0"
        }
        
        logger.debug(
            "Health check performed",
            extra={
                "health_status": health_status,
                "service": "observability"
            }
        )
        
        return health_status
    
    async def get_database_health(self, db) -> Dict[str, Any]:
        """
        Get database health and performance metrics.
        
        Args:
            db: Database connection
            
        Returns:
            Dict containing database health information
        """
        try:
            start_time = time.time()
            
            # Test database connectivity
            await db.command("ping")
            response_time_ms = (time.time() - start_time) * 1000
            
            # Get collection stats
            test_suites_stats = await self._get_collection_stats(db, "test_suites")
            test_items_stats = await self._get_collection_stats(db, "test_items")
            
            database_health = {
                "connected": True,
                "response_time_ms": round(response_time_ms, 2),
                "collections": {
                    "test_suites": test_suites_stats,
                    "test_items": test_items_stats
                },
                "status": "healthy" if response_time_ms < 100 else "degraded"
            }
            
            logger.debug(
                f"Database health check completed: {response_time_ms:.2f}ms",
                extra={
                    "database_health": database_health,
                    "service": "observability"
                }
            )
            
            return database_health
            
        except Exception as e:
            logger.error(
                f"Database health check failed: {e}",
                extra={
                    "error": str(e),
                    "service": "observability"
                }
            )
            
            return {
                "connected": False,
                "response_time_ms": None,
                "error": str(e),
                "status": "unhealthy"
            }
    
    async def record_operation_metrics(
        self,
        operation_type: str,
        success: bool,
        duration_ms: float,
        additional_metrics: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record metrics for a test suite operation.
        
        Args:
            operation_type: Type of operation (create, update, delete, etc.)
            success: Whether the operation was successful
            duration_ms: Operation duration in milliseconds
            additional_metrics: Additional metrics to record
        """
        self.operation_metrics["total_operations"] += 1
        
        if success:
            self.operation_metrics["successful_operations"] += 1
        else:
            self.operation_metrics["failed_operations"] += 1
        
        # Update average response time
        current_avg = self.operation_metrics["avg_response_time_ms"]
        total_ops = self.operation_metrics["total_operations"]
        
        self.operation_metrics["avg_response_time_ms"] = (
            (current_avg * (total_ops - 1) + duration_ms) / total_ops
        )
        
        logger.info(
            f"Operation metrics recorded: {operation_type}",
            extra={
                "operation_type": operation_type,
                "success": success,
                "duration_ms": duration_ms,
                "additional_metrics": additional_metrics or {},
                "service": "observability"
            }
        )
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get current performance metrics.
        
        Returns:
            Dict containing performance metrics
        """
        success_rate = 0.0
        if self.operation_metrics["total_operations"] > 0:
            success_rate = (
                self.operation_metrics["successful_operations"] / 
                self.operation_metrics["total_operations"] * 100
            )
        
        return {
            "total_operations": self.operation_metrics["total_operations"],
            "success_rate_percent": round(success_rate, 2),
            "avg_response_time_ms": round(self.operation_metrics["avg_response_time_ms"], 2),
            "successful_operations": self.operation_metrics["successful_operations"],
            "failed_operations": self.operation_metrics["failed_operations"]
        }
    
    async def _get_collection_stats(self, db, collection_name: str) -> Dict[str, Any]:
        """
        Get statistics for a specific collection.
        
        Args:
            db: Database connection
            collection_name: Name of the collection
            
        Returns:
            Dict containing collection statistics
        """
        try:
            collection = db[collection_name]
            
            # Get document count
            document_count = await collection.count_documents({})
            
            # Get collection stats
            stats = await db.command("collStats", collection_name)
            
            return {
                "document_count": document_count,
                "storage_size_mb": round(stats.get("storageSize", 0) / (1024 * 1024), 2),
                "avg_document_size_kb": round(stats.get("avgObjSize", 0) / 1024, 2),
                "total_indexes": stats.get("nindexes", 0),
                "exists": True
            }
            
        except Exception as e:
            logger.warning(
                f"Failed to get stats for collection {collection_name}: {e}",
                extra={
                    "collection_name": collection_name,
                    "error": str(e),
                    "service": "observability"
                }
            )
            
            return {
                "document_count": 0,
                "storage_size_mb": 0,
                "avg_document_size_kb": 0,
                "total_indexes": 0,
                "exists": False,
                "error": str(e)
            }
    
    def _format_uptime(self, uptime_seconds: float) -> str:
        """
        Format uptime in a human-readable format.
        
        Args:
            uptime_seconds: Uptime in seconds
            
        Returns:
            Human-readable uptime string
        """
        if uptime_seconds < 60:
            return f"{int(uptime_seconds)} seconds"
        elif uptime_seconds < 3600:
            minutes = int(uptime_seconds / 60)
            return f"{minutes} minutes"
        elif uptime_seconds < 86400:
            hours = int(uptime_seconds / 3600)
            minutes = int((uptime_seconds % 3600) / 60)
            return f"{hours} hours, {minutes} minutes"
        else:
            days = int(uptime_seconds / 86400)
            hours = int((uptime_seconds % 86400) / 3600)
            return f"{days} days, {hours} hours"
    
    async def log_operation_start(
        self,
        operation_type: str,
        operation_id: str,
        user_id: str,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        Log the start of an operation and return start time.
        
        Args:
            operation_type: Type of operation
            operation_id: Unique identifier for the operation
            user_id: User performing the operation
            additional_context: Additional context information
            
        Returns:
            Start time timestamp for duration calculation
        """
        start_time = time.time()
        
        logger.info(
            f"Operation started: {operation_type}",
            extra={
                "operation_type": operation_type,
                "operation_id": operation_id,
                "user_id": user_id,
                "start_time": start_time,
                "additional_context": additional_context or {},
                "service": "observability"
            }
        )
        
        return start_time
    
    async def log_operation_end(
        self,
        operation_type: str,
        operation_id: str,
        user_id: str,
        start_time: float,
        success: bool,
        result_summary: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log the end of an operation and record metrics.
        
        Args:
            operation_type: Type of operation
            operation_id: Unique identifier for the operation
            user_id: User performing the operation
            start_time: Start time from log_operation_start
            success: Whether the operation was successful
            result_summary: Summary of operation results
        """
        end_time = time.time()
        duration_ms = (end_time - start_time) * 1000
        
        logger.info(
            f"Operation completed: {operation_type}",
            extra={
                "operation_type": operation_type,
                "operation_id": operation_id,
                "user_id": user_id,
                "duration_ms": duration_ms,
                "success": success,
                "result_summary": result_summary or {},
                "service": "observability"
            }
        )
        
        # Record metrics
        await self.record_operation_metrics(
            operation_type, success, duration_ms, result_summary
        ) 
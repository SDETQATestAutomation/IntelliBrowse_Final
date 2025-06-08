"""
Test Execution Engine - Execution Queue Service

Provides async execution queue management including:
- Priority-based execution queuing
- Background job processing
- Queue monitoring and health checks
- Dead letter queue handling
- Load balancing and throttling

Implements scalable queue architecture for high-volume execution processing.
"""

import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, AsyncIterator
from enum import Enum
import json

from motor.motor_asyncio import AsyncIOMotorDatabase

from ..models.execution_trace_model import (
    ExecutionStatus,
    ExecutionType,
    ExecutionError
)

logger = logging.getLogger(__name__)


class QueuePriority(int, Enum):
    """Queue priority levels (lower number = higher priority)"""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5


class QueueStatus(str, Enum):
    """Queue status enumeration"""
    ACTIVE = "active"
    PAUSED = "paused"
    DRAINING = "draining"
    STOPPED = "stopped"


class ExecutionQueueItem:
    """Queue item representing an execution request"""
    
    def __init__(
        self,
        execution_id: str,
        execution_type: ExecutionType,
        priority: QueuePriority,
        payload: Dict[str, Any],
        scheduled_at: Optional[datetime] = None,
        retry_count: int = 0,
        max_retries: int = 3
    ):
        self.execution_id = execution_id
        self.execution_type = execution_type
        self.priority = priority
        self.payload = payload
        self.queued_at = datetime.now(timezone.utc)
        self.scheduled_at = scheduled_at or self.queued_at
        self.retry_count = retry_count
        self.max_retries = max_retries
        self.processing_started_at: Optional[datetime] = None
        self.last_error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert queue item to dictionary for storage"""
        return {
            "execution_id": self.execution_id,
            "execution_type": self.execution_type,
            "priority": self.priority,
            "payload": self.payload,
            "queued_at": self.queued_at.isoformat(),
            "scheduled_at": self.scheduled_at.isoformat(),
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "processing_started_at": self.processing_started_at.isoformat() if self.processing_started_at else None,
            "last_error": self.last_error
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExecutionQueueItem':
        """Create queue item from dictionary"""
        item = cls(
            execution_id=data["execution_id"],
            execution_type=ExecutionType(data["execution_type"]),
            priority=QueuePriority(data["priority"]),
            payload=data["payload"],
            scheduled_at=datetime.fromisoformat(data["scheduled_at"]),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3)
        )
        item.queued_at = datetime.fromisoformat(data["queued_at"])
        if data.get("processing_started_at"):
            item.processing_started_at = datetime.fromisoformat(data["processing_started_at"])
        item.last_error = data.get("last_error")
        return item


class ExecutionQueueService:
    """
    Service for managing execution queue with priority handling and background processing.
    
    Provides scalable queue management with priority-based scheduling,
    retry logic, dead letter queue handling, and comprehensive monitoring.
    """
    
    def __init__(self, database: AsyncIOMotorDatabase):
        self.database = database
        self.queue_collection = database.execution_queue
        self.dead_letter_collection = database.execution_dead_letter_queue
        self.queue_metrics_collection = database.queue_metrics
        
        # Queue configuration
        self.max_concurrent_executions = 10
        self.queue_status = QueueStatus.ACTIVE
        self.processing_timeout_minutes = 30
        
        # Background processing
        self._processing_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
        logger.info("ExecutionQueueService initialized")
    
    async def enqueue_execution(
        self,
        execution_id: str,
        execution_type: ExecutionType,
        payload: Dict[str, Any],
        priority: QueuePriority = QueuePriority.NORMAL,
        scheduled_at: Optional[datetime] = None
    ) -> bool:
        """
        Add execution to queue with specified priority.
        
        Args:
            execution_id: Execution identifier
            execution_type: Type of execution
            payload: Execution payload data
            priority: Queue priority level
            scheduled_at: Optional scheduled execution time
            
        Returns:
            bool: True if successfully queued
        """
        try:
            logger.info(f"Enqueuing execution: {execution_id} (priority: {priority})")
            
            # Create queue item
            queue_item = ExecutionQueueItem(
                execution_id=execution_id,
                execution_type=execution_type,
                priority=priority,
                payload=payload,
                scheduled_at=scheduled_at
            )
            
            # Store in queue collection
            await self.queue_collection.insert_one(queue_item.to_dict())
            
            # Update queue metrics
            await self._update_queue_metrics("enqueued", execution_type, priority)
            
            logger.info(f"Execution queued successfully: {execution_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to enqueue execution: {execution_id} - {str(e)}")
            return False
    
    async def dequeue_execution(self) -> Optional[ExecutionQueueItem]:
        """
        Dequeue next execution based on priority and schedule.
        
        Returns:
            ExecutionQueueItem: Next execution to process or None if queue is empty
        """
        try:
            if self.queue_status != QueueStatus.ACTIVE:
                return None
            
            # Find next item to process (priority + scheduled time)
            current_time = datetime.now(timezone.utc)
            
            # Query for ready items, ordered by priority then scheduled time
            cursor = self.queue_collection.find({
                "scheduled_at": {"$lte": current_time.isoformat()},
                "processing_started_at": None
            }).sort([("priority", 1), ("scheduled_at", 1)]).limit(1)
            
            doc = await cursor.to_list(length=1)
            if not doc:
                return None
            
            item_doc = doc[0]
            queue_item = ExecutionQueueItem.from_dict(item_doc)
            
            # Mark as processing
            queue_item.processing_started_at = current_time
            await self.queue_collection.update_one(
                {"_id": item_doc["_id"]},
                {"$set": {"processing_started_at": current_time.isoformat()}}
            )
            
            logger.debug(f"Dequeued execution: {queue_item.execution_id}")
            return queue_item
            
        except Exception as e:
            logger.error(f"Failed to dequeue execution: {str(e)}")
            return None
    
    async def complete_execution(self, execution_id: str, success: bool, error_message: Optional[str] = None) -> None:
        """
        Mark execution as completed and remove from queue.
        
        Args:
            execution_id: Execution identifier
            success: Whether execution was successful
            error_message: Error message if execution failed
        """
        try:
            logger.debug(f"Completing execution: {execution_id} (success: {success})")
            
            # Find queue item
            item_doc = await self.queue_collection.find_one({"execution_id": execution_id})
            if not item_doc:
                logger.warning(f"Queue item not found for completion: {execution_id}")
                return
            
            if success:
                # Remove from queue on success
                await self.queue_collection.delete_one({"execution_id": execution_id})
                await self._update_queue_metrics("completed", ExecutionType(item_doc["execution_type"]))
            else:
                # Handle failure - retry or move to dead letter queue
                await self._handle_execution_failure(execution_id, error_message)
            
        except Exception as e:
            logger.error(f"Failed to complete execution: {execution_id} - {str(e)}")
    
    async def retry_execution(self, execution_id: str, error_message: Optional[str] = None) -> bool:
        """
        Retry failed execution if retry limit not exceeded.
        
        Args:
            execution_id: Execution identifier
            error_message: Error message from failed execution
            
        Returns:
            bool: True if execution was queued for retry
        """
        try:
            logger.info(f"Retrying execution: {execution_id}")
            
            # Find queue item
            item_doc = await self.queue_collection.find_one({"execution_id": execution_id})
            if not item_doc:
                logger.warning(f"Queue item not found for retry: {execution_id}")
                return False
            
            queue_item = ExecutionQueueItem.from_dict(item_doc)
            
            # Check retry limit
            if queue_item.retry_count >= queue_item.max_retries:
                logger.warning(f"Retry limit exceeded for execution: {execution_id}")
                await self._move_to_dead_letter_queue(queue_item, "Retry limit exceeded")
                return False
            
            # Increment retry count and reset processing state
            queue_item.retry_count += 1
            queue_item.processing_started_at = None
            queue_item.last_error = error_message
            queue_item.scheduled_at = datetime.now(timezone.utc) + timedelta(minutes=queue_item.retry_count * 2)  # Exponential backoff
            
            # Update in database
            await self.queue_collection.update_one(
                {"execution_id": execution_id},
                {"$set": queue_item.to_dict()}
            )
            
            await self._update_queue_metrics("retried", ExecutionType(item_doc["execution_type"]))
            
            logger.info(f"Execution queued for retry: {execution_id} (attempt {queue_item.retry_count})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to retry execution: {execution_id} - {str(e)}")
            return False
    
    async def get_queue_status(self) -> Dict[str, Any]:
        """
        Get current queue status and metrics.
        
        Returns:
            Queue status information
        """
        try:
            # Count items by status
            total_queued = await self.queue_collection.count_documents({})
            processing = await self.queue_collection.count_documents({"processing_started_at": {"$ne": None}})
            pending = total_queued - processing
            
            # Count by priority
            priority_counts = {}
            for priority in QueuePriority:
                count = await self.queue_collection.count_documents({"priority": priority.value})
                priority_counts[priority.name] = count
            
            # Get oldest queued item
            oldest_cursor = self.queue_collection.find({}).sort("queued_at", 1).limit(1)
            oldest_docs = await oldest_cursor.to_list(length=1)
            oldest_queued_at = None
            if oldest_docs:
                oldest_queued_at = oldest_docs[0]["queued_at"]
            
            # Dead letter queue count
            dead_letter_count = await self.dead_letter_collection.count_documents({})
            
            return {
                "queue_status": self.queue_status,
                "total_queued": total_queued,
                "pending": pending,
                "processing": processing,
                "priority_distribution": priority_counts,
                "oldest_queued_at": oldest_queued_at,
                "dead_letter_count": dead_letter_count,
                "max_concurrent_executions": self.max_concurrent_executions,
                "processing_timeout_minutes": self.processing_timeout_minutes,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get queue status: {str(e)}")
            return {"error": str(e)}
    
    async def start_background_processing(self) -> None:
        """Start background queue processing task."""
        if self._processing_task and not self._processing_task.done():
            logger.warning("Background processing already running")
            return
        
        logger.info("Starting background queue processing")
        self._shutdown_event.clear()
        self._processing_task = asyncio.create_task(self._background_processor())
    
    async def stop_background_processing(self) -> None:
        """Stop background queue processing task."""
        logger.info("Stopping background queue processing")
        self._shutdown_event.set()
        
        if self._processing_task:
            try:
                await asyncio.wait_for(self._processing_task, timeout=30.0)
            except asyncio.TimeoutError:
                logger.warning("Background processing task did not stop gracefully")
                self._processing_task.cancel()
    
    async def pause_queue(self) -> None:
        """Pause queue processing."""
        logger.info("Pausing queue processing")
        self.queue_status = QueueStatus.PAUSED
    
    async def resume_queue(self) -> None:
        """Resume queue processing."""
        logger.info("Resuming queue processing")
        self.queue_status = QueueStatus.ACTIVE
    
    async def clear_queue(self, execution_type: Optional[ExecutionType] = None) -> int:
        """
        Clear queue items (for maintenance).
        
        Args:
            execution_type: Optional filter by execution type
            
        Returns:
            Number of items cleared
        """
        try:
            query = {}
            if execution_type:
                query["execution_type"] = execution_type
            
            result = await self.queue_collection.delete_many(query)
            cleared_count = result.deleted_count
            
            logger.info(f"Cleared {cleared_count} items from queue")
            return cleared_count
            
        except Exception as e:
            logger.error(f"Failed to clear queue: {str(e)}")
            return 0
    
    # Private Helper Methods
    
    async def _background_processor(self) -> None:
        """Background task for processing queue items."""
        logger.info("Background queue processor started")
        
        try:
            while not self._shutdown_event.is_set():
                try:
                    # Check for timed out executions
                    await self._handle_timed_out_executions()
                    
                    # Process queue items if active
                    if self.queue_status == QueueStatus.ACTIVE:
                        await self._process_queue_batch()
                    
                    # Wait before next iteration
                    await asyncio.sleep(5.0)  # 5 second polling interval
                    
                except Exception as e:
                    logger.error(f"Error in background processor: {str(e)}")
                    await asyncio.sleep(10.0)  # Longer wait on error
                    
        except asyncio.CancelledError:
            logger.info("Background queue processor cancelled")
        except Exception as e:
            logger.error(f"Background queue processor error: {str(e)}")
        finally:
            logger.info("Background queue processor stopped")
    
    async def _process_queue_batch(self) -> None:
        """Process a batch of queue items."""
        # Check current processing count
        processing_count = await self.queue_collection.count_documents({"processing_started_at": {"$ne": None}})
        
        if processing_count >= self.max_concurrent_executions:
            return  # At capacity
        
        # Process available slots
        available_slots = self.max_concurrent_executions - processing_count
        
        for _ in range(min(available_slots, 5)):  # Process up to 5 items per batch
            queue_item = await self.dequeue_execution()
            if not queue_item:
                break  # No more items to process
            
            # Start execution processing (in real implementation, this would trigger actual execution)
            asyncio.create_task(self._simulate_execution_processing(queue_item))
    
    async def _simulate_execution_processing(self, queue_item: ExecutionQueueItem) -> None:
        """Simulate execution processing (placeholder for actual execution)."""
        try:
            logger.debug(f"Simulating execution processing: {queue_item.execution_id}")
            
            # Simulate processing time
            import random
            processing_time = random.uniform(5.0, 30.0)
            await asyncio.sleep(processing_time)
            
            # Simulate success/failure (90% success rate)
            success = random.random() > 0.1
            
            if success:
                await self.complete_execution(queue_item.execution_id, True)
            else:
                await self.complete_execution(queue_item.execution_id, False, "Simulated execution failure")
            
        except Exception as e:
            logger.error(f"Execution processing failed: {queue_item.execution_id} - {str(e)}")
            await self.complete_execution(queue_item.execution_id, False, str(e))
    
    async def _handle_timed_out_executions(self) -> None:
        """Handle executions that have timed out."""
        timeout_threshold = datetime.now(timezone.utc) - timedelta(minutes=self.processing_timeout_minutes)
        
        cursor = self.queue_collection.find({
            "processing_started_at": {"$ne": None, "$lt": timeout_threshold.isoformat()}
        })
        
        async for doc in cursor:
            execution_id = doc["execution_id"]
            logger.warning(f"Execution timed out: {execution_id}")
            await self.retry_execution(execution_id, "Execution timed out")
    
    async def _handle_execution_failure(self, execution_id: str, error_message: Optional[str]) -> None:
        """Handle execution failure - retry or move to dead letter queue."""
        item_doc = await self.queue_collection.find_one({"execution_id": execution_id})
        if not item_doc:
            return
        
        queue_item = ExecutionQueueItem.from_dict(item_doc)
        
        if queue_item.retry_count < queue_item.max_retries:
            # Retry execution
            await self.retry_execution(execution_id, error_message)
        else:
            # Move to dead letter queue
            await self._move_to_dead_letter_queue(queue_item, error_message or "Execution failed")
    
    async def _move_to_dead_letter_queue(self, queue_item: ExecutionQueueItem, reason: str) -> None:
        """Move failed execution to dead letter queue."""
        try:
            logger.warning(f"Moving execution to dead letter queue: {queue_item.execution_id} - {reason}")
            
            # Add to dead letter queue
            dead_letter_item = queue_item.to_dict()
            dead_letter_item["moved_to_dlq_at"] = datetime.now(timezone.utc).isoformat()
            dead_letter_item["failure_reason"] = reason
            
            await self.dead_letter_collection.insert_one(dead_letter_item)
            
            # Remove from main queue
            await self.queue_collection.delete_one({"execution_id": queue_item.execution_id})
            
            await self._update_queue_metrics("dead_lettered", queue_item.execution_type)
            
        except Exception as e:
            logger.error(f"Failed to move execution to dead letter queue: {queue_item.execution_id} - {str(e)}")
    
    async def _update_queue_metrics(
        self,
        operation: str,
        execution_type: ExecutionType,
        priority: Optional[QueuePriority] = None
    ) -> None:
        """Update queue metrics for monitoring."""
        try:
            metric_doc = {
                "operation": operation,
                "execution_type": execution_type,
                "priority": priority.value if priority else None,
                "timestamp": datetime.now(timezone.utc)
            }
            
            await self.queue_metrics_collection.insert_one(metric_doc)
            
        except Exception as e:
            logger.error(f"Failed to update queue metrics: {str(e)}")


class ExecutionQueueServiceFactory:
    """Factory for creating ExecutionQueueService instances."""
    
    @staticmethod
    def create(database: AsyncIOMotorDatabase) -> ExecutionQueueService:
        """Create ExecutionQueueService instance with database dependency."""
        return ExecutionQueueService(database) 
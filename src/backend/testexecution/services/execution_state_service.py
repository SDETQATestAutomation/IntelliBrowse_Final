"""
Test Execution Engine - Execution State Service

Provides real-time state tracking and notification services including:
- Atomic state updates with validation
- Real-time state change notifications
- Execution history and audit trail
- State recovery and synchronization
- WebSocket event broadcasting

Implements the progressive observability architecture from creative phase decisions.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, AsyncIterator, Set
from bson import ObjectId
import asyncio
from enum import Enum

from motor.motor_asyncio import AsyncIOMotorDatabase

from ..models.execution_trace_model import (
    ExecutionTraceModel,
    ExecutionStatus,
    StepStatus,
    ExecutionStatistics,
    StateTransitionError
)

logger = logging.getLogger(__name__)


class StateChangeEventType(str, Enum):
    """Types of state change events"""
    EXECUTION_STARTED = "execution_started"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_FAILED = "execution_failed"
    EXECUTION_CANCELLED = "execution_cancelled"
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    PROGRESS_UPDATE = "progress_update"
    ERROR_OCCURRED = "error_occurred"


class StateChangeEvent:
    """State change event data structure"""
    
    def __init__(
        self,
        event_type: StateChangeEventType,
        execution_id: str,
        timestamp: datetime,
        data: Dict[str, Any],
        user_id: Optional[str] = None
    ):
        self.event_type = event_type
        self.execution_id = execution_id
        self.timestamp = timestamp
        self.data = data
        self.user_id = user_id
        self.event_id = f"{execution_id}_{timestamp.timestamp()}_{event_type}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "execution_id": self.execution_id,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "user_id": self.user_id
        }


class ExecutionStateService:
    """
    Service for managing execution state with real-time tracking and notifications.
    
    Provides atomic state updates, event broadcasting, and comprehensive
    state history for audit and recovery purposes.
    """
    
    def __init__(self, database: AsyncIOMotorDatabase):
        self.database = database
        self.collection = database.execution_traces
        self.state_history_collection = database.execution_state_history
        
        # In-memory subscribers for real-time notifications
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}
        self._global_subscribers: Set[asyncio.Queue] = set()
        
        # State transition validation matrix
        self.valid_transitions = {
            ExecutionStatus.PENDING: [ExecutionStatus.QUEUED, ExecutionStatus.CANCELLED],
            ExecutionStatus.QUEUED: [ExecutionStatus.RUNNING, ExecutionStatus.CANCELLED],
            ExecutionStatus.RUNNING: [ExecutionStatus.PASSED, ExecutionStatus.FAILED, 
                                    ExecutionStatus.CANCELLED, ExecutionStatus.TIMEOUT],
            ExecutionStatus.PASSED: [ExecutionStatus.RETRYING],
            ExecutionStatus.FAILED: [ExecutionStatus.RETRYING],
            ExecutionStatus.CANCELLED: [],  # Terminal state
            ExecutionStatus.TIMEOUT: [ExecutionStatus.RETRYING],
            ExecutionStatus.RETRYING: [ExecutionStatus.RUNNING, ExecutionStatus.ABORTED],
            ExecutionStatus.ABORTED: []  # Terminal state
        }
        
        logger.info("ExecutionStateService initialized")
    
    async def update_execution_state(
        self,
        execution_id: str,
        new_status: ExecutionStatus,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update execution state with atomic validation and event broadcasting.
        
        Args:
            execution_id: Execution identifier
            new_status: New execution status
            user_id: User making the change (optional)
            metadata: Additional metadata for the state change
            
        Returns:
            bool: True if state was updated successfully
            
        Raises:
            StateTransitionError: If state transition is invalid
        """
        try:
            logger.info(f"Updating execution state: {execution_id} -> {new_status}")
            
            # Load current execution state
            current_execution = await self._load_execution_state(execution_id)
            if not current_execution:
                raise StateTransitionError(f"Execution not found: {execution_id}")
            
            current_status = current_execution.status
            
            # Validate state transition
            if not self._is_valid_transition(current_status, new_status):
                raise StateTransitionError(
                    f"Invalid state transition: {current_status} -> {new_status}"
                )
            
            # Prepare update data
            update_data = {
                'status': new_status,
                'updated_at': datetime.now(timezone.utc)
            }
            
            # Add completion timestamp for terminal states
            if self._is_terminal_state(new_status):
                update_data['completed_at'] = datetime.now(timezone.utc)
            
            # Add metadata if provided
            if metadata:
                update_data['state_metadata'] = metadata
            
            # Perform atomic update
            result = await self.collection.update_one(
                {"_id": ObjectId(execution_id), "status": current_status},
                {"$set": update_data}
            )
            
            if result.modified_count == 0:
                # State was changed by another process, reload and retry
                logger.warning(f"State update conflict detected for execution: {execution_id}")
                return False
            
            # Record state change in history
            await self._record_state_change(
                execution_id,
                current_status,
                new_status,
                user_id,
                metadata
            )
            
            # Broadcast state change event
            await self._broadcast_state_change(
                execution_id,
                current_status,
                new_status,
                user_id,
                metadata
            )
            
            logger.info(f"Execution state updated successfully: {execution_id} {current_status} -> {new_status}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update execution state: {execution_id} - {str(e)}")
            raise
    
    async def update_execution_progress(
        self,
        execution_id: str,
        statistics: ExecutionStatistics,
        current_step: Optional[str] = None
    ) -> None:
        """
        Update execution progress with real-time statistics.
        
        Args:
            execution_id: Execution identifier
            statistics: Updated execution statistics
            current_step: Currently executing step name
        """
        try:
            logger.debug(f"Updating execution progress: {execution_id} - {statistics.progress_percentage}%")
            
            update_data = {
                'statistics': statistics.model_dump(),
                'updated_at': datetime.now(timezone.utc)
            }
            
            if current_step:
                update_data['current_step'] = current_step
            
            await self.collection.update_one(
                {"_id": ObjectId(execution_id)},
                {"$set": update_data}
            )
            
            # Broadcast progress update event
            event = StateChangeEvent(
                event_type=StateChangeEventType.PROGRESS_UPDATE,
                execution_id=execution_id,
                timestamp=datetime.now(timezone.utc),
                data={
                    'statistics': statistics.model_dump(),
                    'current_step': current_step
                }
            )
            
            await self._notify_subscribers(event)
            
        except Exception as e:
            logger.error(f"Failed to update execution progress: {execution_id} - {str(e)}")
    
    async def subscribe_to_execution_changes(
        self,
        execution_id: str
    ) -> AsyncIterator[StateChangeEvent]:
        """
        Subscribe to state changes for a specific execution.
        
        Args:
            execution_id: Execution to monitor
            
        Yields:
            StateChangeEvent: State change events for the execution
        """
        queue = asyncio.Queue()
        
        try:
            # Add subscriber to execution-specific list
            if execution_id not in self._subscribers:
                self._subscribers[execution_id] = set()
            self._subscribers[execution_id].add(queue)
            
            logger.info(f"Subscribed to execution changes: {execution_id}")
            
            # Yield events from queue
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield event
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    heartbeat = StateChangeEvent(
                        event_type=StateChangeEventType.PROGRESS_UPDATE,
                        execution_id=execution_id,
                        timestamp=datetime.now(timezone.utc),
                        data={"heartbeat": True}
                    )
                    yield heartbeat
                    
        except Exception as e:
            logger.error(f"Error in execution subscription: {execution_id} - {str(e)}")
        finally:
            # Clean up subscription
            if execution_id in self._subscribers:
                self._subscribers[execution_id].discard(queue)
                if not self._subscribers[execution_id]:
                    del self._subscribers[execution_id]
            logger.info(f"Unsubscribed from execution changes: {execution_id}")
    
    async def subscribe_to_all_changes(self) -> AsyncIterator[StateChangeEvent]:
        """
        Subscribe to all execution state changes.
        
        Yields:
            StateChangeEvent: All state change events
        """
        queue = asyncio.Queue()
        
        try:
            # Add to global subscribers
            self._global_subscribers.add(queue)
            logger.info("Subscribed to all execution changes")
            
            # Yield events from queue
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield event
                except asyncio.TimeoutError:
                    # Send heartbeat
                    heartbeat = StateChangeEvent(
                        event_type=StateChangeEventType.PROGRESS_UPDATE,
                        execution_id="global",
                        timestamp=datetime.now(timezone.utc),
                        data={"heartbeat": True}
                    )
                    yield heartbeat
                    
        except Exception as e:
            logger.error(f"Error in global subscription: {str(e)}")
        finally:
            # Clean up subscription
            self._global_subscribers.discard(queue)
            logger.info("Unsubscribed from all execution changes")
    
    async def get_execution_state_history(
        self,
        execution_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get state change history for an execution.
        
        Args:
            execution_id: Execution identifier
            limit: Maximum number of history entries to return
            
        Returns:
            List of state change history entries
        """
        try:
            cursor = self.state_history_collection.find(
                {"execution_id": execution_id}
            ).sort("timestamp", -1).limit(limit)
            
            history = []
            async for doc in cursor:
                doc['_id'] = str(doc['_id'])
                history.append(doc)
            
            logger.debug(f"Retrieved state history for execution: {execution_id} ({len(history)} entries)")
            return history
            
        except Exception as e:
            logger.error(f"Failed to get execution state history: {execution_id} - {str(e)}")
            return []
    
    async def recover_execution_state(self, execution_id: str) -> Optional[ExecutionTraceModel]:
        """
        Recover execution state from database and validate consistency.
        
        Args:
            execution_id: Execution identifier
            
        Returns:
            ExecutionTraceModel: Recovered execution state or None if not found
        """
        try:
            logger.info(f"Recovering execution state: {execution_id}")
            
            # Load execution from database
            execution = await self._load_execution_state(execution_id)
            if not execution:
                logger.warning(f"Execution not found for recovery: {execution_id}")
                return None
            
            # Validate state consistency
            await self._validate_state_consistency(execution)
            
            logger.info(f"Execution state recovered successfully: {execution_id}")
            return execution
            
        except Exception as e:
            logger.error(f"Failed to recover execution state: {execution_id} - {str(e)}")
            return None
    
    async def get_active_executions(self) -> List[Dict[str, Any]]:
        """
        Get all currently active (non-terminal) executions.
        
        Returns:
            List of active execution summaries
        """
        try:
            active_statuses = [
                ExecutionStatus.PENDING,
                ExecutionStatus.QUEUED,
                ExecutionStatus.RUNNING,
                ExecutionStatus.RETRYING
            ]
            
            cursor = self.collection.find(
                {"status": {"$in": active_statuses}},
                {
                    "execution_id": 1,
                    "status": 1,
                    "execution_type": 1,
                    "triggered_by": 1,
                    "triggered_at": 1,
                    "statistics": 1
                }
            )
            
            active_executions = []
            async for doc in cursor:
                doc['execution_id'] = str(doc['_id'])
                del doc['_id']
                active_executions.append(doc)
            
            logger.debug(f"Retrieved active executions: {len(active_executions)}")
            return active_executions
            
        except Exception as e:
            logger.error(f"Failed to get active executions: {str(e)}")
            return []
    
    # Private Helper Methods
    
    async def _load_execution_state(self, execution_id: str) -> Optional[ExecutionTraceModel]:
        """Load execution state from database."""
        try:
            doc = await self.collection.find_one({"_id": ObjectId(execution_id)})
            if doc:
                doc['execution_id'] = str(doc['_id'])
                return ExecutionTraceModel(**doc)
            return None
        except Exception as e:
            logger.error(f"Failed to load execution state: {execution_id} - {str(e)}")
            return None
    
    def _is_valid_transition(self, current_status: ExecutionStatus, new_status: ExecutionStatus) -> bool:
        """Check if state transition is valid."""
        return new_status in self.valid_transitions.get(current_status, [])
    
    def _is_terminal_state(self, status: ExecutionStatus) -> bool:
        """Check if status is a terminal state."""
        return status in [
            ExecutionStatus.PASSED,
            ExecutionStatus.FAILED,
            ExecutionStatus.CANCELLED,
            ExecutionStatus.TIMEOUT,
            ExecutionStatus.ABORTED
        ]
    
    async def _record_state_change(
        self,
        execution_id: str,
        old_status: ExecutionStatus,
        new_status: ExecutionStatus,
        user_id: Optional[str],
        metadata: Optional[Dict[str, Any]]
    ) -> None:
        """Record state change in history collection."""
        try:
            history_entry = {
                "execution_id": execution_id,
                "old_status": old_status,
                "new_status": new_status,
                "timestamp": datetime.now(timezone.utc),
                "user_id": user_id,
                "metadata": metadata or {}
            }
            
            await self.state_history_collection.insert_one(history_entry)
            
        except Exception as e:
            logger.error(f"Failed to record state change: {execution_id} - {str(e)}")
    
    async def _broadcast_state_change(
        self,
        execution_id: str,
        old_status: ExecutionStatus,
        new_status: ExecutionStatus,
        user_id: Optional[str],
        metadata: Optional[Dict[str, Any]]
    ) -> None:
        """Broadcast state change event to subscribers."""
        try:
            # Determine event type based on new status
            event_type = self._get_event_type_for_status(new_status)
            
            event = StateChangeEvent(
                event_type=event_type,
                execution_id=execution_id,
                timestamp=datetime.now(timezone.utc),
                data={
                    'old_status': old_status,
                    'new_status': new_status,
                    'metadata': metadata or {}
                },
                user_id=user_id
            )
            
            await self._notify_subscribers(event)
            
        except Exception as e:
            logger.error(f"Failed to broadcast state change: {execution_id} - {str(e)}")
    
    def _get_event_type_for_status(self, status: ExecutionStatus) -> StateChangeEventType:
        """Get appropriate event type for execution status."""
        status_event_map = {
            ExecutionStatus.RUNNING: StateChangeEventType.EXECUTION_STARTED,
            ExecutionStatus.PASSED: StateChangeEventType.EXECUTION_COMPLETED,
            ExecutionStatus.FAILED: StateChangeEventType.EXECUTION_FAILED,
            ExecutionStatus.CANCELLED: StateChangeEventType.EXECUTION_CANCELLED,
            ExecutionStatus.TIMEOUT: StateChangeEventType.EXECUTION_FAILED,
            ExecutionStatus.ABORTED: StateChangeEventType.EXECUTION_FAILED
        }
        
        return status_event_map.get(status, StateChangeEventType.PROGRESS_UPDATE)
    
    async def _notify_subscribers(self, event: StateChangeEvent) -> None:
        """Notify all relevant subscribers of state change event."""
        try:
            # Notify execution-specific subscribers
            execution_subscribers = self._subscribers.get(event.execution_id, set())
            for queue in execution_subscribers.copy():  # Copy to avoid modification during iteration
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    logger.warning(f"Subscriber queue full for execution: {event.execution_id}")
                    # Remove full queue to prevent memory leaks
                    execution_subscribers.discard(queue)
                except Exception as e:
                    logger.error(f"Failed to notify execution subscriber: {str(e)}")
                    execution_subscribers.discard(queue)
            
            # Notify global subscribers
            for queue in self._global_subscribers.copy():
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    logger.warning("Global subscriber queue full")
                    self._global_subscribers.discard(queue)
                except Exception as e:
                    logger.error(f"Failed to notify global subscriber: {str(e)}")
                    self._global_subscribers.discard(queue)
                    
        except Exception as e:
            logger.error(f"Failed to notify subscribers: {str(e)}")
    
    async def _validate_state_consistency(self, execution: ExecutionTraceModel) -> None:
        """Validate execution state consistency."""
        try:
            # Check if completed executions have completion timestamp
            if self._is_terminal_state(execution.status) and not execution.completed_at:
                logger.warning(f"Terminal execution missing completion timestamp: {execution.execution_id}")
                # Fix by adding completion timestamp
                await self.collection.update_one(
                    {"_id": ObjectId(execution.execution_id)},
                    {"$set": {"completed_at": datetime.now(timezone.utc)}}
                )
            
            # Check statistics consistency
            if execution.statistics:
                stats = execution.statistics
                if stats.completed_steps > stats.total_steps:
                    logger.warning(f"Inconsistent statistics for execution: {execution.execution_id}")
                    # Could implement automatic correction here
            
        except Exception as e:
            logger.error(f"State consistency validation failed: {execution.execution_id} - {str(e)}")


class ExecutionStateServiceFactory:
    """Factory for creating ExecutionStateService instances."""
    
    @staticmethod
    def create(database: AsyncIOMotorDatabase) -> ExecutionStateService:
        """Create ExecutionStateService instance with database dependency."""
        return ExecutionStateService(database) 
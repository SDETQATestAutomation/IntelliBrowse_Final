"""
Execution State Tracker - Persistent DAG state management and tracking

This module implements the ExecutionStateTracker responsible for:
- Updating persistent DAG state after node transitions
- Storing start time, end time, duration, result summary
- Detecting unresolved nodes or blocked transitions
- Raising OrchestrationStallException or InvalidStateTransitionError with metadata
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum

from motor.motor_asyncio import AsyncIOMotorCollection
from ..models.orchestration_models import (
    OrchestrationJobModel,
    OrchestrationNodeModel,
    JobStatus,
    OrchestrationException
)
from ..services.base_orchestration_service import BaseOrchestrationService


class StateTransitionError(OrchestrationException):
    """Exception raised for invalid state transitions"""
    
    def __init__(self, message: str, job_id: str, node_id: str, current_state: str, target_state: str):
        self.job_id = job_id
        self.node_id = node_id
        self.current_state = current_state
        self.target_state = target_state
        super().__init__(message, {
            "job_id": job_id,
            "node_id": node_id,
            "current_state": current_state,
            "target_state": target_state
        })


class ExecutionGraphStallError(OrchestrationException):
    """Exception raised when execution graph becomes stalled"""
    
    def __init__(self, message: str, job_id: str, stalled_nodes: List[str], metadata: Dict[str, Any] = None):
        self.job_id = job_id
        self.stalled_nodes = stalled_nodes
        self.metadata = metadata or {}
        super().__init__(message, {
            "job_id": job_id,
            "stalled_nodes": stalled_nodes,
            "metadata": self.metadata
        })


@dataclass
class ExecutionGraphModel:
    """Model for persistent execution graph state"""
    job_id: str
    graph_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_ms: Optional[int] = None
    total_nodes: int = 0
    completed_nodes: int = 0
    failed_nodes: int = 0
    running_nodes: int = 0
    pending_nodes: int = 0
    node_states: Dict[str, str] = field(default_factory=dict)
    node_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    execution_metadata: Dict[str, Any] = field(default_factory=dict)
    error_summary: Optional[Dict[str, Any]] = None


@dataclass
class NodeStateTransition:
    """Model for node state transitions"""
    job_id: str
    node_id: str
    from_state: str
    to_state: str
    timestamp: datetime
    duration_ms: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error_details: Optional[Dict[str, Any]] = None


class ExecutionStateTracker(BaseOrchestrationService):
    """
    Execution State Tracker - Manages persistent DAG state and transitions
    
    Responsible for:
    - DAG state initialization and persistence
    - Node state transition tracking
    - Execution progress monitoring
    - Stall detection and error reporting
    - State recovery and synchronization
    """
    
    def __init__(
        self,
        db_collection: AsyncIOMotorCollection,
        stall_detection_interval: int = 30,
        logger: Optional[logging.Logger] = None
    ):
        super().__init__(logger)
        self.db_collection = db_collection
        self.stall_detection_interval = stall_detection_interval
        self.active_graphs: Dict[str, ExecutionGraphModel] = {}
        self.state_lock = asyncio.Lock()
        self.transition_history: Dict[str, List[NodeStateTransition]] = {}
        
        # Valid state transitions
        self.valid_transitions = {
            "pending": ["ready", "cancelled"],
            "ready": ["running", "cancelled", "skipped"],
            "running": ["completed", "failed", "cancelled"],
            "completed": [],  # Terminal state
            "failed": ["running"],  # Allow retry
            "cancelled": [],  # Terminal state
            "skipped": []  # Terminal state
        }
    
    async def initialize_dag_state(
        self,
        job_id: str,
        dag_graph: 'DAGExecutionGraph'  # From dag_execution_engine
    ) -> str:
        """
        Initialize persistent DAG state for execution tracking
        
        Args:
            job_id: The job identifier
            dag_graph: The DAG execution graph
            
        Returns:
            Graph ID for the initialized state
        """
        graph_id = f"graph_{job_id}_{int(datetime.now(timezone.utc).timestamp())}"
        
        # Create execution graph model
        execution_graph = ExecutionGraphModel(
            job_id=job_id,
            graph_id=graph_id,
            status="initializing",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            total_nodes=len(dag_graph.nodes),
            node_states={node_id: "pending" for node_id in dag_graph.nodes},
            execution_metadata={
                "max_parallel_nodes": getattr(dag_graph.semaphore, '_value', 10),
                "dependency_count": sum(len(deps) for deps in dag_graph.dependencies.values())
            }
        )
        
        # Store in memory and database
        async with self.state_lock:
            self.active_graphs[job_id] = execution_graph
            self.transition_history[job_id] = []
        
        # Persist to database
        await self._persist_graph_state(execution_graph)
        
        self.logger.info(
            f"Initialized DAG state for job {job_id} with {execution_graph.total_nodes} nodes",
            extra={"job_id": job_id, "graph_id": graph_id, "total_nodes": execution_graph.total_nodes}
        )
        
        return graph_id
    
    async def update_node_state(
        self,
        job_id: str,
        node_id: str,
        new_state: Union[str, 'ExecutionStage'],  # From dag_execution_engine
        metadata: Dict[str, Any] = None
    ) -> None:
        """
        Update the state of a specific node
        
        Args:
            job_id: The job identifier
            node_id: The node identifier
            new_state: The new state for the node
            metadata: Additional metadata for the transition
            
        Raises:
            StateTransitionError: When state transition is invalid
        """
        # Convert enum to string if needed
        if hasattr(new_state, 'value'):
            new_state = new_state.value
        
        async with self.state_lock:
            execution_graph = self.active_graphs.get(job_id)
            if not execution_graph:
                self.logger.error(f"No active graph found for job {job_id}")
                return
            
            current_state = execution_graph.node_states.get(node_id, "unknown")
            
            # Validate state transition
            if not self._is_valid_transition(current_state, new_state):
                raise StateTransitionError(
                    f"Invalid state transition for node {node_id}: {current_state} -> {new_state}",
                    job_id,
                    node_id,
                    current_state,
                    new_state
                )
            
            # Record transition
            transition = NodeStateTransition(
                job_id=job_id,
                node_id=node_id,
                from_state=current_state,
                to_state=new_state,
                timestamp=datetime.now(timezone.utc),
                metadata=metadata or {}
            )
            
            # Update state
            execution_graph.node_states[node_id] = new_state
            execution_graph.updated_at = datetime.now(timezone.utc)
            
            # Update node results if provided
            if metadata:
                if node_id not in execution_graph.node_results:
                    execution_graph.node_results[node_id] = {}
                execution_graph.node_results[node_id].update(metadata)
            
            # Update counters
            self._update_node_counters(execution_graph)
            
            # Store transition history
            if job_id not in self.transition_history:
                self.transition_history[job_id] = []
            self.transition_history[job_id].append(transition)
            
            # Handle specific state transitions
            if new_state == "running" and not execution_graph.start_time:
                execution_graph.start_time = datetime.now(timezone.utc)
                execution_graph.status = "running"
            
            # Calculate duration for completed/failed transitions
            if new_state in ["completed", "failed"] and "start_time" in (metadata or {}):
                start_time = metadata["start_time"]
                if isinstance(start_time, datetime):
                    duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
                    transition.duration_ms = duration_ms
        
        # Persist updated state
        await self._persist_graph_state(execution_graph)
        
        self.logger.info(
            f"Node state updated: {node_id} {current_state} -> {new_state}",
            extra={
                "job_id": job_id,
                "node_id": node_id,
                "from_state": current_state,
                "to_state": new_state
            }
        )
        
        # Check for stall conditions
        await self._check_stall_conditions(job_id)
    
    async def finalize_dag_execution(
        self,
        job_id: str,
        final_status: Union[str, JobStatus],
        execution_result: Dict[str, Any]
    ) -> None:
        """
        Finalize DAG execution and update final state
        
        Args:
            job_id: The job identifier
            final_status: The final execution status
            execution_result: The execution results
        """
        # Convert enum to string if needed
        if hasattr(final_status, 'value'):
            final_status = final_status.value
        
        async with self.state_lock:
            execution_graph = self.active_graphs.get(job_id)
            if not execution_graph:
                self.logger.error(f"No active graph found for job {job_id}")
                return
            
            # Update final state
            execution_graph.status = final_status
            execution_graph.end_time = datetime.now(timezone.utc)
            execution_graph.updated_at = execution_graph.end_time
            
            # Calculate total duration
            if execution_graph.start_time:
                execution_graph.duration_ms = int(
                    (execution_graph.end_time - execution_graph.start_time).total_seconds() * 1000
                )
            
            # Store execution results
            execution_graph.execution_metadata.update({
                "final_result": execution_result,
                "execution_summary": {
                    "total_nodes": execution_graph.total_nodes,
                    "completed_nodes": execution_graph.completed_nodes,
                    "failed_nodes": execution_graph.failed_nodes,
                    "success_rate": execution_graph.completed_nodes / execution_graph.total_nodes if execution_graph.total_nodes > 0 else 0
                }
            })
        
        # Persist final state
        await self._persist_graph_state(execution_graph)
        
        self.logger.info(
            f"DAG execution finalized for job {job_id} - Status: {final_status}, "
            f"Duration: {execution_graph.duration_ms}ms",
            extra={
                "job_id": job_id,
                "final_status": final_status,
                "duration_ms": execution_graph.duration_ms,
                "completed_nodes": execution_graph.completed_nodes,
                "failed_nodes": execution_graph.failed_nodes
            }
        )
    
    async def record_dag_failure(
        self,
        job_id: str,
        error_message: str,
        error_metadata: Dict[str, Any] = None
    ) -> None:
        """
        Record DAG execution failure
        
        Args:
            job_id: The job identifier
            error_message: The error message
            error_metadata: Additional error metadata
        """
        async with self.state_lock:
            execution_graph = self.active_graphs.get(job_id)
            if not execution_graph:
                self.logger.error(f"No active graph found for job {job_id}")
                return
            
            # Update failure state
            execution_graph.status = "failed"
            execution_graph.end_time = datetime.now(timezone.utc)
            execution_graph.updated_at = execution_graph.end_time
            execution_graph.error_summary = {
                "error_message": error_message,
                "error_timestamp": execution_graph.end_time.isoformat(),
                "error_metadata": error_metadata or {}
            }
            
            # Calculate duration if possible
            if execution_graph.start_time:
                execution_graph.duration_ms = int(
                    (execution_graph.end_time - execution_graph.start_time).total_seconds() * 1000
                )
        
        # Persist failure state
        await self._persist_graph_state(execution_graph)
        
        self.logger.error(
            f"DAG execution failed for job {job_id}: {error_message}",
            extra={
                "job_id": job_id,
                "error_message": error_message,
                "error_metadata": error_metadata
            }
        )
    
    async def get_execution_state(self, job_id: str) -> Optional[ExecutionGraphModel]:
        """Get current execution state for a job"""
        
        async with self.state_lock:
            return self.active_graphs.get(job_id)
    
    async def get_node_transition_history(self, job_id: str, node_id: str = None) -> List[NodeStateTransition]:
        """Get node state transition history"""
        
        transitions = self.transition_history.get(job_id, [])
        
        if node_id:
            transitions = [t for t in transitions if t.node_id == node_id]
        
        return transitions
    
    def _is_valid_transition(self, current_state: str, new_state: str) -> bool:
        """Check if a state transition is valid"""
        
        valid_next_states = self.valid_transitions.get(current_state, [])
        return new_state in valid_next_states or current_state == new_state
    
    def _update_node_counters(self, execution_graph: ExecutionGraphModel) -> None:
        """Update node state counters"""
        
        state_counts = {}
        for state in execution_graph.node_states.values():
            state_counts[state] = state_counts.get(state, 0) + 1
        
        execution_graph.completed_nodes = state_counts.get("completed", 0)
        execution_graph.failed_nodes = state_counts.get("failed", 0)
        execution_graph.running_nodes = state_counts.get("running", 0)
        execution_graph.pending_nodes = state_counts.get("pending", 0)
    
    async def _check_stall_conditions(self, job_id: str) -> None:
        """Check for execution stall conditions"""
        
        execution_graph = self.active_graphs.get(job_id)
        if not execution_graph:
            return
        
        # Check if execution is stalled
        total_active = execution_graph.running_nodes + execution_graph.pending_nodes
        
        if total_active > 0 and execution_graph.running_nodes == 0:
            # No running nodes but pending nodes exist - potential stall
            pending_nodes = [
                node_id for node_id, state in execution_graph.node_states.items()
                if state == "pending"
            ]
            
            # Check if pending nodes have all dependencies met
            stalled_nodes = []
            for node_id in pending_nodes:
                # For now, consider all pending nodes as potentially stalled
                # In a full implementation, this would check actual dependencies
                stalled_nodes.append(node_id)
            
            if stalled_nodes:
                self.logger.warning(
                    f"Potential stall detected for job {job_id}: {len(stalled_nodes)} stalled nodes",
                    extra={
                        "job_id": job_id,
                        "stalled_nodes": stalled_nodes,
                        "total_pending": len(pending_nodes)
                    }
                )
    
    async def _persist_graph_state(self, execution_graph: ExecutionGraphModel) -> None:
        """Persist execution graph state to database"""
        
        try:
            # Convert to document format
            doc = {
                "job_id": execution_graph.job_id,
                "graph_id": execution_graph.graph_id,
                "status": execution_graph.status,
                "created_at": execution_graph.created_at,
                "updated_at": execution_graph.updated_at,
                "start_time": execution_graph.start_time,
                "end_time": execution_graph.end_time,
                "duration_ms": execution_graph.duration_ms,
                "total_nodes": execution_graph.total_nodes,
                "completed_nodes": execution_graph.completed_nodes,
                "failed_nodes": execution_graph.failed_nodes,
                "running_nodes": execution_graph.running_nodes,
                "pending_nodes": execution_graph.pending_nodes,
                "node_states": execution_graph.node_states,
                "node_results": execution_graph.node_results,
                "execution_metadata": execution_graph.execution_metadata,
                "error_summary": execution_graph.error_summary
            }
            
            # Upsert document
            await self.db_collection.replace_one(
                {"job_id": execution_graph.job_id},
                doc,
                upsert=True
            )
            
        except Exception as e:
            self.logger.error(
                f"Failed to persist graph state for job {execution_graph.job_id}: {str(e)}",
                extra={"job_id": execution_graph.job_id},
                exc_info=True
            )
    
    async def load_graph_state(self, job_id: str) -> Optional[ExecutionGraphModel]:
        """Load execution graph state from database"""
        
        try:
            doc = await self.db_collection.find_one({"job_id": job_id})
            
            if not doc:
                return None
            
            # Convert from document format
            execution_graph = ExecutionGraphModel(
                job_id=doc["job_id"],
                graph_id=doc["graph_id"],
                status=doc["status"],
                created_at=doc["created_at"],
                updated_at=doc["updated_at"],
                start_time=doc.get("start_time"),
                end_time=doc.get("end_time"),
                duration_ms=doc.get("duration_ms"),
                total_nodes=doc["total_nodes"],
                completed_nodes=doc["completed_nodes"],
                failed_nodes=doc["failed_nodes"],
                running_nodes=doc["running_nodes"],
                pending_nodes=doc["pending_nodes"],
                node_states=doc["node_states"],
                node_results=doc["node_results"],
                execution_metadata=doc["execution_metadata"],
                error_summary=doc.get("error_summary")
            )
            
            # Store in memory
            async with self.state_lock:
                self.active_graphs[job_id] = execution_graph
            
            return execution_graph
            
        except Exception as e:
            self.logger.error(
                f"Failed to load graph state for job {job_id}: {str(e)}",
                extra={"job_id": job_id},
                exc_info=True
            )
            return None
    
    async def cleanup_completed_graphs(self, retention_hours: int = 24) -> int:
        """Clean up completed execution graphs older than retention period"""
        
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=retention_hours)
        
        try:
            # Remove from database
            result = await self.db_collection.delete_many({
                "status": {"$in": ["completed", "failed", "cancelled"]},
                "updated_at": {"$lt": cutoff_time}
            })
            
            # Remove from memory
            async with self.state_lock:
                to_remove = []
                for job_id, graph in self.active_graphs.items():
                    if (graph.status in ["completed", "failed", "cancelled"] and 
                        graph.updated_at < cutoff_time):
                        to_remove.append(job_id)
                
                for job_id in to_remove:
                    del self.active_graphs[job_id]
                    self.transition_history.pop(job_id, None)
            
            self.logger.info(f"Cleaned up {result.deleted_count} completed execution graphs")
            return result.deleted_count
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup completed graphs: {str(e)}", exc_info=True)
            return 0
    
    async def get_execution_statistics(self) -> Dict[str, Any]:
        """Get execution statistics across all active graphs"""
        
        async with self.state_lock:
            stats = {
                "active_graphs": len(self.active_graphs),
                "total_nodes": sum(graph.total_nodes for graph in self.active_graphs.values()),
                "running_nodes": sum(graph.running_nodes for graph in self.active_graphs.values()),
                "completed_nodes": sum(graph.completed_nodes for graph in self.active_graphs.values()),
                "failed_nodes": sum(graph.failed_nodes for graph in self.active_graphs.values()),
                "status_distribution": {}
            }
            
            # Calculate status distribution
            for graph in self.active_graphs.values():
                status = graph.status
                stats["status_distribution"][status] = stats["status_distribution"].get(status, 0) + 1
        
        return stats 
"""
DAG Execution Engine - Core orchestrator for execution graph traversal and execution

This module implements the main DAG execution engine responsible for:
- Traversing DAG nodes respecting dependency edges
- Dispatching node execution to NodeRunnerService
- Managing state transitions and execution flow
- Handling async patterns and parallel execution
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from ..models.orchestration_models import (
    OrchestrationJobModel, 
    OrchestrationNodeModel,
    JobStatus,
    NodeType
)
from ..services.base_orchestration_service import BaseOrchestrationService
from .node_runner_service import NodeRunnerService
from .execution_state_tracker import ExecutionStateTracker


class ExecutionStage(Enum):
    """Execution stage enumeration for DAG processing"""
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class OrchestrationStallException(Exception):
    """Exception raised when orchestration becomes stalled"""
    
    def __init__(self, message: str, stalled_nodes: List[str], metadata: Dict[str, Any] = None):
        self.stalled_nodes = stalled_nodes
        self.metadata = metadata or {}
        super().__init__(message)


class InvalidStateTransitionError(Exception):
    """Exception raised for invalid state transitions"""
    
    def __init__(self, message: str, node_id: str, current_state: str, target_state: str):
        self.node_id = node_id
        self.current_state = current_state
        self.target_state = target_state
        super().__init__(message)


class NodeExecutionError(Exception):
    """Exception raised during node execution"""
    
    def __init__(self, message: str, node_id: str, error_details: Dict[str, Any] = None):
        self.node_id = node_id
        self.error_details = error_details or {}
        super().__init__(message)


class GraphExecutionHalt(Exception):
    """Exception raised when graph execution must be halted"""
    
    def __init__(self, message: str, reason: str, affected_nodes: List[str] = None):
        self.reason = reason
        self.affected_nodes = affected_nodes or []
        super().__init__(message)


@dataclass
class ExecutionContext:
    """Execution context for DAG processing"""
    job_id: str
    trace_id: str
    execution_mode: str = "normal"
    timeout_seconds: Optional[int] = None
    max_parallel_nodes: int = 10
    retry_enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NodeExecutionResult:
    """Result of node execution"""
    node_id: str
    status: ExecutionStage
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: Optional[int] = None
    result_data: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    retry_count: int = 0


@dataclass
class DAGExecutionGraph:
    """In-memory representation of DAG execution state"""
    nodes: Dict[str, OrchestrationNodeModel]
    dependencies: Dict[str, List[str]]  # node_id -> list of dependency node_ids
    node_states: Dict[str, ExecutionStage]
    execution_results: Dict[str, NodeExecutionResult]
    ready_queue: asyncio.Queue
    semaphore: asyncio.Semaphore
    
    def __post_init__(self):
        if not hasattr(self, 'ready_queue'):
            self.ready_queue = asyncio.Queue()
        if not hasattr(self, 'semaphore'):
            self.semaphore = asyncio.Semaphore(10)  # Default limit


class DAGExecutionEngine(BaseOrchestrationService):
    """
    DAG Execution Engine - Main orchestrator for execution graph processing
    
    Responsible for:
    - DAG traversal respecting dependency edges
    - Node execution dispatching
    - State transition management
    - Async execution coordination
    - Error handling and recovery
    """
    
    def __init__(
        self,
        node_runner_service: NodeRunnerService,
        state_tracker: ExecutionStateTracker,
        logger: Optional[logging.Logger] = None
    ):
        super().__init__(logger)
        self.node_runner = node_runner_service
        self.state_tracker = state_tracker
        self.active_executions: Dict[str, DAGExecutionGraph] = {}
        self.execution_lock = asyncio.Lock()
        
    async def execute_dag(
        self,
        job: OrchestrationJobModel,
        execution_context: ExecutionContext
    ) -> Dict[str, Any]:
        """
        Execute a DAG represented by an OrchestrationJobModel
        
        Args:
            job: The orchestration job containing DAG definition
            execution_context: Execution context and parameters
            
        Returns:
            Execution results dictionary
            
        Raises:
            OrchestrationStallException: When execution becomes stalled
            GraphExecutionHalt: When execution must be halted
            NodeExecutionError: When critical node execution fails
        """
        self.logger.info(
            f"Starting DAG execution for job {job.job_id}",
            extra={"trace_id": execution_context.trace_id, "job_id": job.job_id}
        )
        
        try:
            # Build execution graph
            dag_graph = await self._build_execution_graph(job, execution_context)
            
            # Validate DAG structure
            await self._validate_dag_structure(dag_graph)
            
            # Store execution graph
            async with self.execution_lock:
                self.active_executions[job.job_id] = dag_graph
            
            # Initialize state tracking
            await self.state_tracker.initialize_dag_state(job.job_id, dag_graph)
            
            # Execute DAG
            execution_result = await self._execute_graph(dag_graph, execution_context)
            
            # Update final state
            await self.state_tracker.finalize_dag_execution(
                job.job_id, 
                execution_result["status"],
                execution_result
            )
            
            return execution_result
            
        except Exception as e:
            self.logger.error(
                f"DAG execution failed for job {job.job_id}: {str(e)}",
                extra={"trace_id": execution_context.trace_id, "job_id": job.job_id},
                exc_info=True
            )
            
            # Update failure state
            await self.state_tracker.record_dag_failure(
                job.job_id,
                str(e),
                {"error_type": type(e).__name__}
            )
            
            raise
        finally:
            # Cleanup
            async with self.execution_lock:
                self.active_executions.pop(job.job_id, None)
    
    async def _build_execution_graph(
        self,
        job: OrchestrationJobModel,
        context: ExecutionContext
    ) -> DAGExecutionGraph:
        """Build in-memory execution graph from job definition"""
        
        # Extract nodes from job (assuming they're stored in job.execution_graph)
        nodes = {}
        dependencies = {}
        node_states = {}
        execution_results = {}
        
        # Build nodes dictionary
        if hasattr(job, 'execution_graph') and job.execution_graph:
            for node_data in job.execution_graph.get('nodes', []):
                node = OrchestrationNodeModel(**node_data)
                nodes[node.node_id] = node
                dependencies[node.node_id] = node.depends_on or []
                node_states[node.node_id] = ExecutionStage.PENDING
                
        # Create semaphore for parallel execution control
        semaphore = asyncio.Semaphore(context.max_parallel_nodes)
        ready_queue = asyncio.Queue()
        
        dag_graph = DAGExecutionGraph(
            nodes=nodes,
            dependencies=dependencies,
            node_states=node_states,
            execution_results=execution_results,
            ready_queue=ready_queue,
            semaphore=semaphore
        )
        
        # Find initially ready nodes (no dependencies)
        await self._identify_ready_nodes(dag_graph)
        
        return dag_graph
    
    async def _validate_dag_structure(self, dag_graph: DAGExecutionGraph) -> None:
        """Validate DAG structure for cycles and consistency"""
        
        # Cycle detection using DFS
        visited = set()
        rec_stack = set()
        
        def has_cycle(node_id: str) -> bool:
            if node_id in rec_stack:
                return True
            if node_id in visited:
                return False
                
            visited.add(node_id)
            rec_stack.add(node_id)
            
            for dep in dag_graph.dependencies.get(node_id, []):
                if has_cycle(dep):
                    return True
            
            rec_stack.remove(node_id)
            return False
        
        # Check for cycles
        for node_id in dag_graph.nodes:
            if node_id not in visited:
                if has_cycle(node_id):
                    raise GraphExecutionHalt(
                        f"Cycle detected in DAG involving node {node_id}",
                        "cycle_detected",
                        [node_id]
                    )
        
        # Validate dependency references
        for node_id, deps in dag_graph.dependencies.items():
            for dep in deps:
                if dep not in dag_graph.nodes:
                    raise GraphExecutionHalt(
                        f"Node {node_id} references non-existent dependency {dep}",
                        "invalid_dependency",
                        [node_id, dep]
                    )
        
        self.logger.info(f"DAG validation passed for {len(dag_graph.nodes)} nodes")
    
    async def _identify_ready_nodes(self, dag_graph: DAGExecutionGraph) -> None:
        """Identify nodes that are ready for execution"""
        
        for node_id, node in dag_graph.nodes.items():
            if dag_graph.node_states[node_id] == ExecutionStage.PENDING:
                # Check if all dependencies are completed
                deps_completed = True
                for dep in dag_graph.dependencies.get(node_id, []):
                    if dag_graph.node_states.get(dep) != ExecutionStage.COMPLETED:
                        deps_completed = False
                        break
                
                if deps_completed:
                    dag_graph.node_states[node_id] = ExecutionStage.READY
                    await dag_graph.ready_queue.put(node_id)
                    
                    self.logger.debug(
                        f"Node {node_id} marked as ready for execution",
                        extra={"node_id": node_id}
                    )
    
    async def _execute_graph(
        self,
        dag_graph: DAGExecutionGraph,
        context: ExecutionContext
    ) -> Dict[str, Any]:
        """Execute the DAG graph with parallel processing"""
        
        start_time = datetime.now(timezone.utc)
        completed_nodes = 0
        failed_nodes = 0
        total_nodes = len(dag_graph.nodes)
        
        # Worker tasks for parallel execution
        workers = []
        
        try:
            # Start worker tasks
            for i in range(min(context.max_parallel_nodes, total_nodes)):
                worker_task = asyncio.create_task(
                    self._execution_worker(dag_graph, context, f"worker-{i}")
                )
                workers.append(worker_task)
            
            # Monitor execution progress
            while completed_nodes + failed_nodes < total_nodes:
                await asyncio.sleep(0.1)  # Small delay to prevent busy waiting
                
                # Count completed/failed nodes
                completed_nodes = sum(
                    1 for state in dag_graph.node_states.values()
                    if state == ExecutionStage.COMPLETED
                )
                failed_nodes = sum(
                    1 for state in dag_graph.node_states.values()
                    if state == ExecutionStage.FAILED
                )
                
                # Check for stall condition
                running_nodes = sum(
                    1 for state in dag_graph.node_states.values()
                    if state == ExecutionStage.RUNNING
                )
                
                if running_nodes == 0 and dag_graph.ready_queue.empty():
                    # Check if there are pending nodes that should be ready
                    await self._identify_ready_nodes(dag_graph)
                    
                    if dag_graph.ready_queue.empty() and completed_nodes + failed_nodes < total_nodes:
                        # Stall detected
                        stalled_nodes = [
                            node_id for node_id, state in dag_graph.node_states.items()
                            if state == ExecutionStage.PENDING
                        ]
                        raise OrchestrationStallException(
                            f"Execution stalled with {len(stalled_nodes)} pending nodes",
                            stalled_nodes,
                            {"completed": completed_nodes, "failed": failed_nodes}
                        )
            
            # Cancel workers
            for worker in workers:
                worker.cancel()
            
            # Wait for workers to finish
            await asyncio.gather(*workers, return_exceptions=True)
            
            end_time = datetime.now(timezone.utc)
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # Determine overall status
            if failed_nodes > 0:
                overall_status = JobStatus.FAILED
            elif completed_nodes == total_nodes:
                overall_status = JobStatus.COMPLETED
            else:
                overall_status = JobStatus.ABORTED
            
            execution_result = {
                "status": overall_status,
                "start_time": start_time,
                "end_time": end_time,
                "duration_ms": duration_ms,
                "completed_nodes": completed_nodes,
                "failed_nodes": failed_nodes,
                "total_nodes": total_nodes,
                "node_results": dict(dag_graph.execution_results)
            }
            
            self.logger.info(
                f"DAG execution completed - Status: {overall_status}, "
                f"Completed: {completed_nodes}/{total_nodes}, Duration: {duration_ms}ms",
                extra={"trace_id": context.trace_id, "job_id": context.job_id}
            )
            
            return execution_result
            
        except asyncio.CancelledError:
            # Handle cancellation
            for worker in workers:
                worker.cancel()
            
            await self._handle_execution_cancellation(dag_graph, context)
            raise
        
        except Exception as e:
            # Handle execution failure
            for worker in workers:
                worker.cancel()
            
            self.logger.error(
                f"Graph execution failed: {str(e)}",
                extra={"trace_id": context.trace_id, "job_id": context.job_id},
                exc_info=True
            )
            raise
    
    async def _execution_worker(
        self,
        dag_graph: DAGExecutionGraph,
        context: ExecutionContext,
        worker_id: str
    ) -> None:
        """Worker task for executing nodes from the ready queue"""
        
        self.logger.debug(f"Execution worker {worker_id} started")
        
        try:
            while True:
                try:
                    # Get next ready node with timeout
                    node_id = await asyncio.wait_for(
                        dag_graph.ready_queue.get(),
                        timeout=5.0
                    )
                    
                    if node_id is None:  # Shutdown signal
                        break
                    
                    # Execute node
                    await self._execute_node(dag_graph, node_id, context)
                    
                    # Mark task as done
                    dag_graph.ready_queue.task_done()
                    
                    # Check for newly ready nodes
                    await self._identify_ready_nodes(dag_graph)
                    
                except asyncio.TimeoutError:
                    # Timeout waiting for nodes - check if we should continue
                    continue
                    
                except Exception as e:
                    self.logger.error(
                        f"Worker {worker_id} encountered error: {str(e)}",
                        exc_info=True
                    )
                    # Continue processing other nodes
                    continue
                    
        except asyncio.CancelledError:
            self.logger.debug(f"Execution worker {worker_id} cancelled")
            raise
        
        finally:
            self.logger.debug(f"Execution worker {worker_id} finished")
    
    async def _execute_node(
        self,
        dag_graph: DAGExecutionGraph,
        node_id: str,
        context: ExecutionContext
    ) -> None:
        """Execute a single node"""
        
        node = dag_graph.nodes[node_id]
        
        # Acquire semaphore for parallel execution control
        async with dag_graph.semaphore:
            try:
                # Update state to running
                dag_graph.node_states[node_id] = ExecutionStage.RUNNING
                start_time = datetime.now(timezone.utc)
                
                await self.state_tracker.update_node_state(
                    context.job_id,
                    node_id,
                    ExecutionStage.RUNNING,
                    {"start_time": start_time}
                )
                
                self.logger.info(
                    f"Executing node {node_id} of type {node.node_type}",
                    extra={"trace_id": context.trace_id, "node_id": node_id}
                )
                
                # Execute node through NodeRunner
                result = await self.node_runner.execute_node(node, context)
                
                end_time = datetime.now(timezone.utc)
                duration_ms = int((end_time - start_time).total_seconds() * 1000)
                
                # Create execution result
                execution_result = NodeExecutionResult(
                    node_id=node_id,
                    status=ExecutionStage.COMPLETED,
                    start_time=start_time,
                    end_time=end_time,
                    duration_ms=duration_ms,
                    result_data=result
                )
                
                # Update states
                dag_graph.node_states[node_id] = ExecutionStage.COMPLETED
                dag_graph.execution_results[node_id] = execution_result
                
                await self.state_tracker.update_node_state(
                    context.job_id,
                    node_id,
                    ExecutionStage.COMPLETED,
                    {
                        "end_time": end_time,
                        "duration_ms": duration_ms,
                        "result_data": result
                    }
                )
                
                self.logger.info(
                    f"Node {node_id} completed successfully in {duration_ms}ms",
                    extra={"trace_id": context.trace_id, "node_id": node_id}
                )
                
            except Exception as e:
                # Handle node execution failure
                end_time = datetime.now(timezone.utc)
                duration_ms = int((end_time - start_time).total_seconds() * 1000)
                
                execution_result = NodeExecutionResult(
                    node_id=node_id,
                    status=ExecutionStage.FAILED,
                    start_time=start_time,
                    end_time=end_time,
                    duration_ms=duration_ms,
                    error_message=str(e)
                )
                
                # Update states
                dag_graph.node_states[node_id] = ExecutionStage.FAILED
                dag_graph.execution_results[node_id] = execution_result
                
                await self.state_tracker.update_node_state(
                    context.job_id,
                    node_id,
                    ExecutionStage.FAILED,
                    {
                        "end_time": end_time,
                        "duration_ms": duration_ms,
                        "error_message": str(e),
                        "error_type": type(e).__name__
                    }
                )
                
                self.logger.error(
                    f"Node {node_id} failed after {duration_ms}ms: {str(e)}",
                    extra={"trace_id": context.trace_id, "node_id": node_id},
                    exc_info=True
                )
                
                # For critical nodes, halt execution
                if getattr(node, 'critical', False):
                    raise GraphExecutionHalt(
                        f"Critical node {node_id} failed",
                        "critical_node_failure",
                        [node_id]
                    )
    
    async def _handle_execution_cancellation(
        self,
        dag_graph: DAGExecutionGraph,
        context: ExecutionContext
    ) -> None:
        """Handle execution cancellation and cleanup"""
        
        self.logger.info(
            f"Handling execution cancellation for job {context.job_id}",
            extra={"trace_id": context.trace_id, "job_id": context.job_id}
        )
        
        # Update remaining running nodes to cancelled
        for node_id, state in dag_graph.node_states.items():
            if state == ExecutionStage.RUNNING:
                dag_graph.node_states[node_id] = ExecutionStage.CANCELLED
                
                await self.state_tracker.update_node_state(
                    context.job_id,
                    node_id,
                    ExecutionStage.CANCELLED,
                    {"cancelled_at": datetime.now(timezone.utc)}
                )
    
    async def get_execution_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get current execution status for a job"""
        
        async with self.execution_lock:
            dag_graph = self.active_executions.get(job_id)
            
            if not dag_graph:
                return None
            
            status = {
                "job_id": job_id,
                "total_nodes": len(dag_graph.nodes),
                "node_states": dict(dag_graph.node_states),
                "execution_results": {
                    node_id: {
                        "status": result.status.value,
                        "duration_ms": result.duration_ms,
                        "start_time": result.start_time.isoformat() if result.start_time else None,
                        "end_time": result.end_time.isoformat() if result.end_time else None
                    }
                    for node_id, result in dag_graph.execution_results.items()
                }
            }
            
            return status
    
    async def cancel_execution(self, job_id: str) -> bool:
        """Cancel an active execution"""
        
        async with self.execution_lock:
            dag_graph = self.active_executions.get(job_id)
            
            if not dag_graph:
                return False
            
            # Signal cancellation by putting None in the queue
            await dag_graph.ready_queue.put(None)
            
            self.logger.info(
                f"Cancellation requested for job {job_id}",
                extra={"job_id": job_id}
            )
            
            return True 
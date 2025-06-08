"""
Node Runner Service - Individual node stage execution with timeout and context management

This module implements the NodeRunnerService responsible for:
- Running individual node stages (test case execution, validation, notification trigger)
- Injecting test item/test case/test suite references as needed
- Timeout-aware execution using anyio with fallback recovery
- Emitting state updates to DAG engine and logging subsystem
"""

import asyncio
import logging
import anyio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Callable, Type
from dataclasses import dataclass, field
from enum import Enum

from ..models.orchestration_models import (
    OrchestrationNodeModel,
    NodeType,
    OrchestrationException
)
from ..services.base_orchestration_service import BaseOrchestrationService


class NodeExecutionStrategy(Enum):
    """Node execution strategy enumeration"""
    DIRECT = "direct"
    QUEUED = "queued" 
    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"
    CONDITIONAL = "conditional"


class NodeRunnerException(OrchestrationException):
    """Exception raised during node execution"""
    
    def __init__(self, message: str, node_id: str, node_type: str, execution_details: Dict[str, Any] = None):
        self.node_id = node_id
        self.node_type = node_type
        self.execution_details = execution_details or {}
        super().__init__(message, {"node_id": node_id, "node_type": node_type})


class NodeTimeoutException(NodeRunnerException):
    """Exception raised when node execution times out"""
    
    def __init__(self, node_id: str, timeout_seconds: int, execution_time: float):
        self.timeout_seconds = timeout_seconds
        self.execution_time = execution_time
        super().__init__(
            f"Node {node_id} execution timed out after {execution_time:.2f}s (limit: {timeout_seconds}s)",
            node_id,
            "timeout",
            {"timeout_seconds": timeout_seconds, "execution_time": execution_time}
        )


@dataclass
class NodeExecutionContext:
    """Execution context for individual node processing"""
    job_id: str
    node_id: str
    trace_id: str
    test_suite_id: Optional[str] = None
    test_case_id: Optional[str] = None
    test_item_id: Optional[str] = None
    execution_mode: str = "normal"
    timeout_seconds: Optional[int] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NodeConfiguration:
    """Configuration for node execution"""
    node_type: NodeType
    execution_strategy: NodeExecutionStrategy
    timeout_seconds: int = 300  # 5 minutes default
    retryable: bool = True
    critical: bool = False
    parallel_allowed: bool = True
    dependencies_strict: bool = True
    resource_requirements: Dict[str, Any] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NodeExecutionResult:
    """Result of node execution"""
    node_id: str
    status: str
    start_time: datetime
    end_time: datetime
    duration_ms: int
    result_data: Dict[str, Any] = field(default_factory=dict)
    output_artifacts: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)


class NodeRunnerService(BaseOrchestrationService):
    """
    Node Runner Service - Executes individual DAG nodes with context injection and timeout management
    
    Responsible for:
    - Individual node stage execution
    - Context injection (test suite/case/item references)
    - Timeout-aware execution with anyio
    - State update emission
    - Error handling and recovery
    """
    
    def __init__(
        self,
        default_timeout: int = 300,
        max_retry_attempts: int = 3,
        logger: Optional[logging.Logger] = None
    ):
        super().__init__(logger)
        self.default_timeout = default_timeout
        self.max_retry_attempts = max_retry_attempts
        self.node_handlers: Dict[NodeType, Callable] = {}
        self.execution_strategies: Dict[NodeExecutionStrategy, Callable] = {}
        self.active_executions: Dict[str, asyncio.Task] = {}
        self._initialize_handlers()
        self._initialize_strategies()
    
    def _initialize_handlers(self) -> None:
        """Initialize node type handlers"""
        self.node_handlers = {
            NodeType.TEST_EXECUTION: self._execute_test_node,
            NodeType.VALIDATION: self._execute_validation_node,
            NodeType.NOTIFICATION: self._execute_notification_node,
            NodeType.DATA_PROCESSING: self._execute_data_processing_node,
            NodeType.CONDITIONAL: self._execute_conditional_node,
            NodeType.SYNCHRONIZATION: self._execute_synchronization_node,
            NodeType.CLEANUP: self._execute_cleanup_node,
            NodeType.SETUP: self._execute_setup_node
        }
    
    def _initialize_strategies(self) -> None:
        """Initialize execution strategies"""
        self.execution_strategies = {
            NodeExecutionStrategy.DIRECT: self._execute_direct,
            NodeExecutionStrategy.QUEUED: self._execute_queued,
            NodeExecutionStrategy.PARALLEL: self._execute_parallel,
            NodeExecutionStrategy.SEQUENTIAL: self._execute_sequential,
            NodeExecutionStrategy.CONDITIONAL: self._execute_conditional_strategy
        }
    
    async def execute_node(
        self,
        node: OrchestrationNodeModel,
        context: 'ExecutionContext'  # From dag_execution_engine
    ) -> Dict[str, Any]:
        """
        Execute a single node with timeout and context management
        
        Args:
            node: The orchestration node to execute
            context: Execution context from DAG engine
            
        Returns:
            Execution result dictionary
            
        Raises:
            NodeRunnerException: When node execution fails
            NodeTimeoutException: When node execution times out
        """
        # Create node-specific execution context
        node_context = NodeExecutionContext(
            job_id=context.job_id,
            node_id=node.node_id,
            trace_id=context.trace_id,
            execution_mode=context.execution_mode,
            timeout_seconds=getattr(node, 'timeout_seconds', self.default_timeout),
            metadata=context.metadata.copy()
        )
        
        # Inject test references based on node configuration
        await self._inject_test_references(node, node_context)
        
        self.logger.info(
            f"Starting execution of node {node.node_id} (type: {node.node_type})",
            extra={
                "trace_id": context.trace_id,
                "node_id": node.node_id,
                "node_type": node.node_type.value
            }
        )
        
        start_time = datetime.now(timezone.utc)
        
        try:
            # Get node configuration
            node_config = self._get_node_configuration(node)
            
            # Execute with timeout using anyio
            with anyio.fail_after(node_config.timeout_seconds):
                result_data = await self._execute_with_strategy(node, node_context, node_config)
            
            end_time = datetime.now(timezone.utc)
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            execution_result = NodeExecutionResult(
                node_id=node.node_id,
                status="completed",
                start_time=start_time,
                end_time=end_time,
                duration_ms=duration_ms,
                result_data=result_data
            )
            
            self.logger.info(
                f"Node {node.node_id} executed successfully in {duration_ms}ms",
                extra={
                    "trace_id": context.trace_id,
                    "node_id": node.node_id,
                    "duration_ms": duration_ms
                }
            )
            
            # Emit state update
            await self._emit_state_update(node_context, "completed", execution_result)
            
            return result_data
            
        except anyio.get_cancelled_exc_class():
            # Handle timeout
            end_time = datetime.now(timezone.utc)
            execution_time = (end_time - start_time).total_seconds()
            
            await self._emit_state_update(node_context, "timeout", {
                "execution_time": execution_time,
                "timeout_seconds": node_config.timeout_seconds
            })
            
            raise NodeTimeoutException(
                node.node_id,
                node_config.timeout_seconds,
                execution_time
            )
            
        except Exception as e:
            # Handle execution failure
            end_time = datetime.now(timezone.utc)
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            self.logger.error(
                f"Node {node.node_id} execution failed after {duration_ms}ms: {str(e)}",
                extra={
                    "trace_id": context.trace_id,
                    "node_id": node.node_id,
                    "duration_ms": duration_ms
                },
                exc_info=True
            )
            
            # Emit failure state update
            await self._emit_state_update(node_context, "failed", {
                "error_message": str(e),
                "error_type": type(e).__name__,
                "duration_ms": duration_ms
            })
            
            raise NodeRunnerException(
                f"Node execution failed: {str(e)}",
                node.node_id,
                node.node_type.value,
                {"original_error": str(e), "duration_ms": duration_ms}
            )
    
    async def _inject_test_references(
        self,
        node: OrchestrationNodeModel,
        context: NodeExecutionContext
    ) -> None:
        """Inject test item/case/suite references based on node configuration"""
        
        # Extract test references from node configuration
        if hasattr(node, 'configuration') and node.configuration:
            config = node.configuration
            
            if 'test_suite_id' in config:
                context.test_suite_id = config['test_suite_id']
            
            if 'test_case_id' in config:
                context.test_case_id = config['test_case_id']
                
            if 'test_item_id' in config:
                context.test_item_id = config['test_item_id']
        
        # Log injected references
        references = []
        if context.test_suite_id:
            references.append(f"suite:{context.test_suite_id}")
        if context.test_case_id:
            references.append(f"case:{context.test_case_id}")
        if context.test_item_id:
            references.append(f"item:{context.test_item_id}")
            
        if references:
            self.logger.debug(
                f"Injected test references for node {node.node_id}: {', '.join(references)}",
                extra={"node_id": node.node_id, "test_references": references}
            )
    
    def _get_node_configuration(self, node: OrchestrationNodeModel) -> NodeConfiguration:
        """Get node configuration with defaults"""
        
        config = getattr(node, 'configuration', {}) or {}
        
        return NodeConfiguration(
            node_type=node.node_type,
            execution_strategy=NodeExecutionStrategy(
                config.get('execution_strategy', NodeExecutionStrategy.DIRECT.value)
            ),
            timeout_seconds=config.get('timeout_seconds', self.default_timeout),
            retryable=config.get('retryable', True),
            critical=config.get('critical', False),
            parallel_allowed=config.get('parallel_allowed', True),
            dependencies_strict=config.get('dependencies_strict', True),
            resource_requirements=config.get('resource_requirements', {}),
            parameters=config.get('parameters', {})
        )
    
    async def _execute_with_strategy(
        self,
        node: OrchestrationNodeModel,
        context: NodeExecutionContext,
        config: NodeConfiguration
    ) -> Dict[str, Any]:
        """Execute node using specified strategy"""
        
        strategy_handler = self.execution_strategies.get(config.execution_strategy)
        if not strategy_handler:
            raise NodeRunnerException(
                f"Unknown execution strategy: {config.execution_strategy}",
                node.node_id,
                node.node_type.value
            )
        
        return await strategy_handler(node, context, config)
    
    async def _execute_direct(
        self,
        node: OrchestrationNodeModel,
        context: NodeExecutionContext,
        config: NodeConfiguration
    ) -> Dict[str, Any]:
        """Execute node directly using node type handler"""
        
        handler = self.node_handlers.get(node.node_type)
        if not handler:
            raise NodeRunnerException(
                f"No handler found for node type: {node.node_type}",
                node.node_id,
                node.node_type.value
            )
        
        return await handler(node, context, config)
    
    async def _execute_queued(
        self,
        node: OrchestrationNodeModel,
        context: NodeExecutionContext,
        config: NodeConfiguration
    ) -> Dict[str, Any]:
        """Execute node through async queue"""
        
        # For now, delegate to direct execution
        # In a full implementation, this would use a job queue system
        return await self._execute_direct(node, context, config)
    
    async def _execute_parallel(
        self,
        node: OrchestrationNodeModel,
        context: NodeExecutionContext,
        config: NodeConfiguration
    ) -> Dict[str, Any]:
        """Execute node with parallel sub-tasks"""
        
        # For now, delegate to direct execution
        # In a full implementation, this would handle parallel sub-task execution
        return await self._execute_direct(node, context, config)
    
    async def _execute_sequential(
        self,
        node: OrchestrationNodeModel,
        context: NodeExecutionContext,
        config: NodeConfiguration
    ) -> Dict[str, Any]:
        """Execute node with sequential sub-tasks"""
        
        # For now, delegate to direct execution
        # In a full implementation, this would handle sequential sub-task execution
        return await self._execute_direct(node, context, config)
    
    async def _execute_conditional_strategy(
        self,
        node: OrchestrationNodeModel,
        context: NodeExecutionContext,
        config: NodeConfiguration
    ) -> Dict[str, Any]:
        """Execute node with conditional logic"""
        
        # Evaluate conditions first
        conditions = config.parameters.get('conditions', [])
        
        for condition in conditions:
            if await self._evaluate_condition(condition, context):
                # Execute the conditional action
                return await self._execute_direct(node, context, config)
        
        # No conditions met, skip execution
        return {
            "status": "skipped",
            "reason": "conditions_not_met",
            "evaluated_conditions": len(conditions)
        }
    
    async def _evaluate_condition(self, condition: Dict[str, Any], context: NodeExecutionContext) -> bool:
        """Evaluate a conditional expression"""
        
        # Simple condition evaluation (can be extended)
        condition_type = condition.get('type', 'always')
        
        if condition_type == 'always':
            return True
        elif condition_type == 'never':
            return False
        elif condition_type == 'metadata_exists':
            key = condition.get('key')
            return key in context.metadata
        elif condition_type == 'metadata_equals':
            key = condition.get('key')
            expected_value = condition.get('value')
            return context.metadata.get(key) == expected_value
        
        # Default to true for unknown conditions
        return True
    
    # Node type handlers
    
    async def _execute_test_node(
        self,
        node: OrchestrationNodeModel,
        context: NodeExecutionContext,
        config: NodeConfiguration
    ) -> Dict[str, Any]:
        """Execute test execution node"""
        
        self.logger.info(
            f"Executing test node {node.node_id}",
            extra={
                "node_id": node.node_id,
                "test_suite_id": context.test_suite_id,
                "test_case_id": context.test_case_id
            }
        )
        
        # Simulate test execution
        await asyncio.sleep(0.1)  # Simulate work
        
        return {
            "node_type": "test_execution",
            "test_suite_id": context.test_suite_id,
            "test_case_id": context.test_case_id,
            "test_item_id": context.test_item_id,
            "execution_status": "passed",
            "test_results": {
                "assertions_passed": 5,
                "assertions_failed": 0,
                "execution_time_ms": 150
            }
        }
    
    async def _execute_validation_node(
        self,
        node: OrchestrationNodeModel,
        context: NodeExecutionContext,
        config: NodeConfiguration
    ) -> Dict[str, Any]:
        """Execute validation node"""
        
        self.logger.info(
            f"Executing validation node {node.node_id}",
            extra={"node_id": node.node_id}
        )
        
        # Simulate validation
        await asyncio.sleep(0.05)  # Simulate work
        
        return {
            "node_type": "validation",
            "validation_status": "passed",
            "validation_results": {
                "rules_evaluated": 3,
                "rules_passed": 3,
                "rules_failed": 0
            }
        }
    
    async def _execute_notification_node(
        self,
        node: OrchestrationNodeModel,
        context: NodeExecutionContext,
        config: NodeConfiguration
    ) -> Dict[str, Any]:
        """Execute notification trigger node"""
        
        self.logger.info(
            f"Executing notification node {node.node_id}",
            extra={"node_id": node.node_id}
        )
        
        # Simulate notification
        await asyncio.sleep(0.02)  # Simulate work
        
        return {
            "node_type": "notification",
            "notification_status": "sent",
            "notification_results": {
                "channels_notified": ["email", "slack"],
                "recipients_count": 3,
                "notification_id": f"notif_{node.node_id}_{context.trace_id}"
            }
        }
    
    async def _execute_data_processing_node(
        self,
        node: OrchestrationNodeModel,
        context: NodeExecutionContext,
        config: NodeConfiguration
    ) -> Dict[str, Any]:
        """Execute data processing node"""
        
        self.logger.info(
            f"Executing data processing node {node.node_id}",
            extra={"node_id": node.node_id}
        )
        
        # Simulate data processing
        await asyncio.sleep(0.08)  # Simulate work
        
        return {
            "node_type": "data_processing",
            "processing_status": "completed",
            "processing_results": {
                "records_processed": 100,
                "transformations_applied": 5,
                "output_size_bytes": 2048
            }
        }
    
    async def _execute_conditional_node(
        self,
        node: OrchestrationNodeModel,
        context: NodeExecutionContext,
        config: NodeConfiguration
    ) -> Dict[str, Any]:
        """Execute conditional logic node"""
        
        self.logger.info(
            f"Executing conditional node {node.node_id}",
            extra={"node_id": node.node_id}
        )
        
        # Evaluate conditions
        conditions = config.parameters.get('conditions', [])
        conditions_met = sum(1 for condition in conditions if await self._evaluate_condition(condition, context))
        
        return {
            "node_type": "conditional",
            "conditions_total": len(conditions),
            "conditions_met": conditions_met,
            "execution_path": "primary" if conditions_met > 0 else "fallback"
        }
    
    async def _execute_synchronization_node(
        self,
        node: OrchestrationNodeModel,
        context: NodeExecutionContext,
        config: NodeConfiguration
    ) -> Dict[str, Any]:
        """Execute synchronization point node"""
        
        self.logger.info(
            f"Executing synchronization node {node.node_id}",
            extra={"node_id": node.node_id}
        )
        
        # Simulate synchronization wait
        await asyncio.sleep(0.03)  # Simulate work
        
        return {
            "node_type": "synchronization",
            "sync_status": "completed",
            "sync_results": {
                "barrier_reached": True,
                "waiting_time_ms": 30,
                "synchronized_nodes": config.parameters.get('sync_nodes', [])
            }
        }
    
    async def _execute_cleanup_node(
        self,
        node: OrchestrationNodeModel,
        context: NodeExecutionContext,
        config: NodeConfiguration
    ) -> Dict[str, Any]:
        """Execute cleanup node"""
        
        self.logger.info(
            f"Executing cleanup node {node.node_id}",
            extra={"node_id": node.node_id}
        )
        
        # Simulate cleanup
        await asyncio.sleep(0.04)  # Simulate work
        
        return {
            "node_type": "cleanup",
            "cleanup_status": "completed",
            "cleanup_results": {
                "resources_cleaned": 5,
                "temp_files_removed": 3,
                "memory_freed_mb": 128
            }
        }
    
    async def _execute_setup_node(
        self,
        node: OrchestrationNodeModel,
        context: NodeExecutionContext,
        config: NodeConfiguration
    ) -> Dict[str, Any]:
        """Execute setup node"""
        
        self.logger.info(
            f"Executing setup node {node.node_id}",
            extra={"node_id": node.node_id}
        )
        
        # Simulate setup
        await asyncio.sleep(0.06)  # Simulate work
        
        return {
            "node_type": "setup",
            "setup_status": "completed",
            "setup_results": {
                "resources_initialized": 3,
                "configurations_applied": 2,
                "environment_ready": True
            }
        }
    
    async def _emit_state_update(
        self,
        context: NodeExecutionContext,
        status: str,
        details: Dict[str, Any]
    ) -> None:
        """Emit state update to logging subsystem"""
        
        state_update = {
            "job_id": context.job_id,
            "node_id": context.node_id,
            "trace_id": context.trace_id,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details
        }
        
        self.logger.info(
            f"Node state update: {context.node_id} -> {status}",
            extra=state_update
        )
        
        # In a full implementation, this would emit to an event bus or message queue
        # For now, we just log the state update
    
    async def get_active_executions(self) -> List[Dict[str, Any]]:
        """Get list of currently active node executions"""
        
        active = []
        for node_id, task in self.active_executions.items():
            if not task.done():
                active.append({
                    "node_id": node_id,
                    "status": "running",
                    "start_time": getattr(task, '_start_time', None)
                })
        
        return active
    
    async def cancel_node_execution(self, node_id: str) -> bool:
        """Cancel a specific node execution"""
        
        task = self.active_executions.get(node_id)
        if task and not task.done():
            task.cancel()
            self.logger.info(f"Cancelled execution of node {node_id}")
            return True
        
        return False 
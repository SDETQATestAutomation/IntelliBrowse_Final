"""
Test Execution Engine - Execution Orchestrator Service

Provides central coordination for test execution lifecycle including:
- Execution workflow orchestration
- Test runner coordination
- State transition management
- Result collection and processing
- Error handling and recovery

Implements the hybrid state-event architecture from creative phase decisions.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, AsyncIterator
from bson import ObjectId

from motor.motor_asyncio import AsyncIOMotorDatabase

from ..models.execution_trace_model import (
    ExecutionTraceModel,
    ExecutionStatus,
    ExecutionType,
    StepStatus,
    StepResultModel,
    ExecutionStatistics,
    ExecutionError,
    StepExecutionError,
    ExecutionTimeoutError,
    StateTransitionError
)
from ..schemas.execution_schemas import (
    ExecutionContextSchema,
    ExecutionConfigSchema,
    ExecutionProgressResponse
)

logger = logging.getLogger(__name__)


class ExecutionOrchestrator:
    """
    Central orchestrator for test execution lifecycle management.
    
    Coordinates between test runners, state management, and result processing
    to provide reliable execution workflow with comprehensive error handling.
    """
    
    def __init__(self, database: AsyncIOMotorDatabase):
        self.database = database
        self.collection = database.execution_traces
        
        # State transition matrix for validation
        self.valid_transitions = {
            ExecutionStatus.PENDING: [ExecutionStatus.QUEUED, ExecutionStatus.CANCELLED],
            ExecutionStatus.QUEUED: [ExecutionStatus.RUNNING, ExecutionStatus.CANCELLED],
            ExecutionStatus.RUNNING: [ExecutionStatus.PASSED, ExecutionStatus.FAILED, 
                                    ExecutionStatus.CANCELLED, ExecutionStatus.TIMEOUT],
            ExecutionStatus.PASSED: [ExecutionStatus.RETRYING],  # Allow rerun
            ExecutionStatus.FAILED: [ExecutionStatus.RETRYING],
            ExecutionStatus.CANCELLED: [],  # Terminal state
            ExecutionStatus.TIMEOUT: [ExecutionStatus.RETRYING],
            ExecutionStatus.RETRYING: [ExecutionStatus.RUNNING, ExecutionStatus.ABORTED],
            ExecutionStatus.ABORTED: []  # Terminal state
        }
        
        logger.info("ExecutionOrchestrator initialized")
    
    async def orchestrate_execution(
        self,
        execution_id: str,
        execution_context: ExecutionContextSchema,
        execution_config: ExecutionConfigSchema
    ) -> ExecutionProgressResponse:
        """
        Orchestrate complete execution lifecycle for a test execution.
        
        Args:
            execution_id: Execution identifier
            execution_context: Execution context configuration
            execution_config: Execution configuration settings
            
        Returns:
            ExecutionProgressResponse: Final execution progress
            
        Raises:
            ExecutionError: If orchestration fails
            StateTransitionError: If invalid state transition occurs
        """
        try:
            logger.info(f"Starting execution orchestration: {execution_id}")
            
            # Load execution trace
            execution = await self._load_execution(execution_id)
            if not execution:
                raise ExecutionError(f"Execution not found: {execution_id}")
            
            # Validate execution can be started
            await self._validate_execution_start(execution)
            
            # Transition to running state
            await self._transition_execution_state(execution_id, ExecutionStatus.RUNNING)
            
            # Execute based on type
            if execution.execution_type == ExecutionType.TEST_CASE:
                result = await self._orchestrate_test_case_execution(execution, execution_context, execution_config)
            elif execution.execution_type == ExecutionType.TEST_SUITE:
                result = await self._orchestrate_test_suite_execution(execution, execution_context, execution_config)
            else:
                raise ExecutionError(f"Unsupported execution type: {execution.execution_type}")
            
            logger.info(f"Execution orchestration completed: {execution_id}")
            return result
            
        except Exception as e:
            logger.error(f"Execution orchestration failed: {execution_id} - {str(e)}")
            await self._handle_execution_error(execution_id, e)
            raise
    
    async def _orchestrate_test_case_execution(
        self,
        execution: ExecutionTraceModel,
        context: ExecutionContextSchema,
        config: ExecutionConfigSchema
    ) -> ExecutionProgressResponse:
        """Orchestrate single test case execution."""
        try:
            logger.info(f"Orchestrating test case execution: {execution.execution_id}")
            
            # Load test case details
            test_case = await self._load_test_case(execution.test_case_id)
            if not test_case:
                raise ExecutionError(f"Test case not found: {execution.test_case_id}")
            
            # Initialize execution statistics
            total_steps = len(test_case.get('steps', []))
            statistics = ExecutionStatistics(
                total_steps=total_steps,
                completed_steps=0,
                progress_percentage=0.0,
                estimated_remaining_ms=total_steps * config.step_timeout_ms
            )
            
            # Update execution with initial statistics
            await self._update_execution_statistics(execution.execution_id, statistics)
            
            # Execute test steps
            step_results = []
            for i, step in enumerate(test_case.get('steps', [])):
                try:
                    # Execute individual step
                    step_result = await self._execute_test_step(
                        execution.execution_id,
                        step,
                        i,
                        context,
                        config
                    )
                    step_results.append(step_result)
                    
                    # Update progress
                    completed = i + 1
                    progress = (completed / total_steps) * 100
                    remaining_steps = total_steps - completed
                    estimated_remaining = remaining_steps * config.step_timeout_ms
                    
                    statistics.completed_steps = completed
                    statistics.progress_percentage = progress
                    statistics.estimated_remaining_ms = estimated_remaining
                    
                    await self._update_execution_statistics(execution.execution_id, statistics)
                    
                    # Check for failure and fail_fast
                    if step_result.status == StepStatus.FAILED and config.fail_fast:
                        logger.warning(f"Failing fast due to step failure: {execution.execution_id}")
                        break
                        
                except Exception as step_error:
                    logger.error(f"Step execution failed: {execution.execution_id} step {i} - {str(step_error)}")
                    if config.fail_fast:
                        raise
                    # Continue with next step if fail_fast is disabled
            
            # Determine overall execution result
            overall_status = self._determine_execution_status(step_results)
            await self._transition_execution_state(execution.execution_id, overall_status)
            
            # Build final progress response
            return await self._build_progress_response(execution.execution_id, statistics)
            
        except Exception as e:
            logger.error(f"Test case execution orchestration failed: {execution.execution_id} - {str(e)}")
            raise ExecutionError(f"Test case execution failed: {str(e)}")
    
    async def _orchestrate_test_suite_execution(
        self,
        execution: ExecutionTraceModel,
        context: ExecutionContextSchema,
        config: ExecutionConfigSchema
    ) -> ExecutionProgressResponse:
        """Orchestrate test suite execution."""
        try:
            logger.info(f"Orchestrating test suite execution: {execution.execution_id}")
            
            # Load test suite details
            test_suite = await self._load_test_suite(execution.test_suite_id)
            if not test_suite:
                raise ExecutionError(f"Test suite not found: {execution.test_suite_id}")
            
            # Get test cases in suite
            test_cases = test_suite.get('test_cases', [])
            total_cases = len(test_cases)
            
            if total_cases == 0:
                logger.warning(f"Test suite has no test cases: {execution.test_suite_id}")
                await self._transition_execution_state(execution.execution_id, ExecutionStatus.PASSED)
                return await self._build_progress_response(execution.execution_id, ExecutionStatistics())
            
            # Initialize suite statistics
            statistics = ExecutionStatistics(
                total_steps=total_cases,  # Each test case is a "step" in suite execution
                completed_steps=0,
                progress_percentage=0.0,
                estimated_remaining_ms=total_cases * 300000  # 5 min per test case estimate
            )
            
            await self._update_execution_statistics(execution.execution_id, statistics)
            
            # Execute test cases
            suite_config = execution.suite_config or {}
            parallel_execution = suite_config.get('parallel_execution', False)
            continue_on_failure = suite_config.get('continue_on_failure', True)
            
            case_results = []
            if parallel_execution:
                case_results = await self._execute_test_cases_parallel(
                    execution, test_cases, context, config, statistics
                )
            else:
                case_results = await self._execute_test_cases_sequential(
                    execution, test_cases, context, config, statistics, continue_on_failure
                )
            
            # Determine overall suite result
            overall_status = self._determine_suite_status(case_results)
            await self._transition_execution_state(execution.execution_id, overall_status)
            
            # Build final progress response
            return await self._build_progress_response(execution.execution_id, statistics)
            
        except Exception as e:
            logger.error(f"Test suite execution orchestration failed: {execution.execution_id} - {str(e)}")
            raise ExecutionError(f"Test suite execution failed: {str(e)}")
    
    async def _execute_test_step(
        self,
        execution_id: str,
        step: Dict[str, Any],
        step_order: int,
        context: ExecutionContextSchema,
        config: ExecutionConfigSchema
    ) -> StepResultModel:
        """Execute individual test step with comprehensive error handling."""
        step_id = step.get('step_id', f"step_{step_order}")
        step_name = step.get('name', f"Step {step_order + 1}")
        
        logger.debug(f"Executing step: {execution_id} - {step_name}")
        
        step_result = StepResultModel(
            step_id=step_id,
            step_name=step_name,
            step_order=step_order,
            status=StepStatus.RUNNING,
            started_at=datetime.now(timezone.utc)
        )
        
        try:
            # Simulate step execution (in real implementation, this would call test runners)
            # For now, we'll simulate based on step configuration
            
            # Add step input data
            step_result.input_data = step.get('input_data', {})
            step_result.expected_result = step.get('expected_result', {})
            
            # Simulate execution time
            import asyncio
            execution_time_ms = step.get('estimated_duration_ms', 1000)
            await asyncio.sleep(execution_time_ms / 1000.0)
            
            # Simulate result (90% success rate for demo)
            import random
            success = random.random() > 0.1
            
            if success:
                step_result.status = StepStatus.PASSED
                step_result.actual_result = {"status": "success", "message": "Step completed successfully"}
            else:
                step_result.status = StepStatus.FAILED
                step_result.error_details = {
                    "error_type": "AssertionError",
                    "error_message": "Expected result did not match actual result",
                    "stack_trace": "Simulated stack trace for demo"
                }
            
            step_result.completed_at = datetime.now(timezone.utc)
            step_result.duration_ms = int((step_result.completed_at - step_result.started_at).total_seconds() * 1000)
            
            logger.debug(f"Step execution completed: {step_name} - {step_result.status}")
            return step_result
            
        except Exception as e:
            logger.error(f"Step execution error: {step_name} - {str(e)}")
            step_result.status = StepStatus.FAILED
            step_result.completed_at = datetime.now(timezone.utc)
            step_result.duration_ms = int((step_result.completed_at - step_result.started_at).total_seconds() * 1000)
            step_result.error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "stack_trace": "Error during step execution"
            }
            return step_result
    
    async def _execute_test_cases_sequential(
        self,
        execution: ExecutionTraceModel,
        test_cases: List[Dict[str, Any]],
        context: ExecutionContextSchema,
        config: ExecutionConfigSchema,
        statistics: ExecutionStatistics,
        continue_on_failure: bool
    ) -> List[Dict[str, Any]]:
        """Execute test cases sequentially."""
        case_results = []
        
        for i, test_case in enumerate(test_cases):
            try:
                # Create sub-execution for test case
                case_result = await self._execute_single_test_case(
                    execution.execution_id,
                    test_case,
                    context,
                    config
                )
                case_results.append(case_result)
                
                # Update progress
                completed = i + 1
                progress = (completed / len(test_cases)) * 100
                statistics.completed_steps = completed
                statistics.progress_percentage = progress
                
                await self._update_execution_statistics(execution.execution_id, statistics)
                
                # Check continue on failure
                if case_result.get('status') == 'FAILED' and not continue_on_failure:
                    logger.warning(f"Stopping suite execution due to test case failure: {execution.execution_id}")
                    break
                    
            except Exception as e:
                logger.error(f"Test case execution failed: {test_case.get('test_case_id')} - {str(e)}")
                if not continue_on_failure:
                    raise
        
        return case_results
    
    async def _execute_test_cases_parallel(
        self,
        execution: ExecutionTraceModel,
        test_cases: List[Dict[str, Any]],
        context: ExecutionContextSchema,
        config: ExecutionConfigSchema,
        statistics: ExecutionStatistics
    ) -> List[Dict[str, Any]]:
        """Execute test cases in parallel."""
        import asyncio
        
        # Create tasks for parallel execution
        tasks = []
        for test_case in test_cases:
            task = self._execute_single_test_case(
                execution.execution_id,
                test_case,
                context,
                config
            )
            tasks.append(task)
        
        # Execute all tasks concurrently
        case_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results and handle exceptions
        processed_results = []
        for i, result in enumerate(case_results):
            if isinstance(result, Exception):
                logger.error(f"Parallel test case execution failed: {test_cases[i].get('test_case_id')} - {str(result)}")
                processed_results.append({
                    'test_case_id': test_cases[i].get('test_case_id'),
                    'status': 'FAILED',
                    'error': str(result)
                })
            else:
                processed_results.append(result)
        
        # Update final statistics
        statistics.completed_steps = len(test_cases)
        statistics.progress_percentage = 100.0
        await self._update_execution_statistics(execution.execution_id, statistics)
        
        return processed_results
    
    async def _execute_single_test_case(
        self,
        parent_execution_id: str,
        test_case: Dict[str, Any],
        context: ExecutionContextSchema,
        config: ExecutionConfigSchema
    ) -> Dict[str, Any]:
        """Execute a single test case within a suite."""
        test_case_id = test_case.get('test_case_id')
        logger.debug(f"Executing test case: {test_case_id} in suite {parent_execution_id}")
        
        try:
            # Simulate test case execution
            import asyncio
            import random
            
            # Simulate execution time (1-5 seconds)
            execution_time = random.uniform(1.0, 5.0)
            await asyncio.sleep(execution_time)
            
            # Simulate result (85% success rate for test cases)
            success = random.random() > 0.15
            
            result = {
                'test_case_id': test_case_id,
                'status': 'PASSED' if success else 'FAILED',
                'duration_ms': int(execution_time * 1000),
                'executed_at': datetime.now(timezone.utc).isoformat()
            }
            
            if not success:
                result['error'] = 'Simulated test case failure for demo'
            
            logger.debug(f"Test case execution completed: {test_case_id} - {result['status']}")
            return result
            
        except Exception as e:
            logger.error(f"Test case execution error: {test_case_id} - {str(e)}")
            return {
                'test_case_id': test_case_id,
                'status': 'FAILED',
                'error': str(e),
                'executed_at': datetime.now(timezone.utc).isoformat()
            }
    
    # Helper Methods
    
    async def _load_execution(self, execution_id: str) -> Optional[ExecutionTraceModel]:
        """Load execution trace from database."""
        try:
            doc = await self.collection.find_one({"_id": ObjectId(execution_id)})
            if doc:
                doc['execution_id'] = str(doc['_id'])
                return ExecutionTraceModel(**doc)
            return None
        except Exception as e:
            logger.error(f"Failed to load execution: {execution_id} - {str(e)}")
            return None
    
    async def _load_test_case(self, test_case_id: str) -> Optional[Dict[str, Any]]:
        """Load test case details from test case service."""
        try:
            # In real implementation, this would call the test case service
            # For now, return a mock test case
            return {
                'test_case_id': test_case_id,
                'title': f'Test Case {test_case_id}',
                'steps': [
                    {
                        'step_id': f'{test_case_id}_step_1',
                        'name': 'Setup test data',
                        'estimated_duration_ms': 1000
                    },
                    {
                        'step_id': f'{test_case_id}_step_2', 
                        'name': 'Execute test action',
                        'estimated_duration_ms': 2000
                    },
                    {
                        'step_id': f'{test_case_id}_step_3',
                        'name': 'Verify results',
                        'estimated_duration_ms': 1000
                    }
                ]
            }
        except Exception as e:
            logger.error(f"Failed to load test case: {test_case_id} - {str(e)}")
            return None
    
    async def _load_test_suite(self, test_suite_id: str) -> Optional[Dict[str, Any]]:
        """Load test suite details from test suite service."""
        try:
            # In real implementation, this would call the test suite service
            # For now, return a mock test suite
            return {
                'test_suite_id': test_suite_id,
                'title': f'Test Suite {test_suite_id}',
                'test_cases': [
                    {'test_case_id': f'{test_suite_id}_case_1'},
                    {'test_case_id': f'{test_suite_id}_case_2'},
                    {'test_case_id': f'{test_suite_id}_case_3'}
                ]
            }
        except Exception as e:
            logger.error(f"Failed to load test suite: {test_suite_id} - {str(e)}")
            return None
    
    async def _validate_execution_start(self, execution: ExecutionTraceModel) -> None:
        """Validate execution can be started."""
        if execution.status not in [ExecutionStatus.PENDING, ExecutionStatus.QUEUED]:
            raise StateTransitionError(
                f"Cannot start execution in status: {execution.status}"
            )
    
    async def _transition_execution_state(
        self,
        execution_id: str,
        new_status: ExecutionStatus
    ) -> None:
        """Transition execution to new state with validation."""
        try:
            # Load current execution
            execution = await self._load_execution(execution_id)
            if not execution:
                raise ExecutionError(f"Execution not found: {execution_id}")
            
            # Validate transition
            current_status = execution.status
            if new_status not in self.valid_transitions.get(current_status, []):
                raise StateTransitionError(
                    f"Invalid state transition: {current_status} -> {new_status}"
                )
            
            # Update status in database
            update_data = {
                'status': new_status,
                'updated_at': datetime.now(timezone.utc)
            }
            
            # Add completion timestamp for terminal states
            if new_status in [ExecutionStatus.PASSED, ExecutionStatus.FAILED, 
                            ExecutionStatus.CANCELLED, ExecutionStatus.TIMEOUT, ExecutionStatus.ABORTED]:
                update_data['completed_at'] = datetime.now(timezone.utc)
            
            await self.collection.update_one(
                {"_id": ObjectId(execution_id)},
                {"$set": update_data}
            )
            
            logger.info(f"Execution state transition: {execution_id} {current_status} -> {new_status}")
            
        except Exception as e:
            logger.error(f"State transition failed: {execution_id} - {str(e)}")
            raise
    
    async def _update_execution_statistics(
        self,
        execution_id: str,
        statistics: ExecutionStatistics
    ) -> None:
        """Update execution statistics in database."""
        try:
            await self.collection.update_one(
                {"_id": ObjectId(execution_id)},
                {"$set": {
                    "statistics": statistics.model_dump(),
                    "updated_at": datetime.now(timezone.utc)
                }}
            )
        except Exception as e:
            logger.error(f"Failed to update execution statistics: {execution_id} - {str(e)}")
    
    async def _handle_execution_error(self, execution_id: str, error: Exception) -> None:
        """Handle execution error and update state."""
        try:
            error_status = ExecutionStatus.FAILED
            if isinstance(error, ExecutionTimeoutError):
                error_status = ExecutionStatus.TIMEOUT
            elif isinstance(error, StateTransitionError):
                error_status = ExecutionStatus.ABORTED
            
            await self._transition_execution_state(execution_id, error_status)
            
            # Log error details
            await self.collection.update_one(
                {"_id": ObjectId(execution_id)},
                {"$set": {
                    "error_details": {
                        "error_type": type(error).__name__,
                        "error_message": str(error),
                        "occurred_at": datetime.now(timezone.utc).isoformat()
                    }
                }}
            )
            
        except Exception as e:
            logger.error(f"Failed to handle execution error: {execution_id} - {str(e)}")
    
    def _determine_execution_status(self, step_results: List[StepResultModel]) -> ExecutionStatus:
        """Determine overall execution status from step results."""
        if not step_results:
            return ExecutionStatus.PASSED
        
        failed_steps = [r for r in step_results if r.status == StepStatus.FAILED]
        if failed_steps:
            return ExecutionStatus.FAILED
        
        return ExecutionStatus.PASSED
    
    def _determine_suite_status(self, case_results: List[Dict[str, Any]]) -> ExecutionStatus:
        """Determine overall suite status from test case results."""
        if not case_results:
            return ExecutionStatus.PASSED
        
        failed_cases = [r for r in case_results if r.get('status') == 'FAILED']
        if failed_cases:
            return ExecutionStatus.FAILED
        
        return ExecutionStatus.PASSED
    
    async def _build_progress_response(
        self,
        execution_id: str,
        statistics: ExecutionStatistics
    ) -> ExecutionProgressResponse:
        """Build execution progress response."""
        execution = await self._load_execution(execution_id)
        if not execution:
            raise ExecutionError(f"Execution not found: {execution_id}")
        
        return ExecutionProgressResponse(
            execution_id=execution_id,
            status=execution.status,
            progress_percentage=statistics.progress_percentage,
            current_step=None,  # Would be populated in real implementation
            estimated_remaining_ms=statistics.estimated_remaining_ms,
            last_update=datetime.now(timezone.utc),
            statistics=statistics
        )


class ExecutionOrchestratorFactory:
    """Factory for creating ExecutionOrchestrator instances."""
    
    @staticmethod
    def create(database: AsyncIOMotorDatabase) -> ExecutionOrchestrator:
        """Create ExecutionOrchestrator instance with database dependency."""
        return ExecutionOrchestrator(database) 
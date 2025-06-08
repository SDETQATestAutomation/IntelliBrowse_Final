"""
Test Execution Engine - Test Runner Service

Provides extensible test runner framework for different test types including:
- Generic test runner for standard test cases
- BDD test runner for behavior-driven tests
- Manual test runner for manual test execution
- Step-by-step execution with progress tracking
- Result collection and validation

Implements the hybrid state-event architecture from creative phase decisions.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, AsyncIterator
from abc import ABC, abstractmethod
from enum import Enum

from motor.motor_asyncio import AsyncIOMotorDatabase

from ..models.execution_trace_model import (
    ExecutionType,
    StepStatus,
    StepResultModel,
    ExecutionStatistics,
    StepExecutionError,
    ExecutionTimeoutError
)
from ..schemas.execution_schemas import (
    ExecutionContextSchema,
    ExecutionConfigSchema
)

logger = logging.getLogger(__name__)


class TestRunnerType(str, Enum):
    """Types of test runners available"""
    GENERIC = "generic"
    BDD = "bdd"
    MANUAL = "manual"
    API = "api"
    UI = "ui"


class BaseTestRunner(ABC):
    """
    Abstract base class for all test runners.
    
    Defines the interface that all test runners must implement
    for consistent execution behavior across different test types.
    """
    
    def __init__(self, runner_type: TestRunnerType):
        self.runner_type = runner_type
        self.logger = logging.getLogger(f"{__name__}.{runner_type}")
    
    @abstractmethod
    async def execute_test(
        self,
        test_case: Dict[str, Any],
        context: ExecutionContextSchema,
        config: ExecutionConfigSchema
    ) -> List[StepResultModel]:
        """
        Execute a complete test case.
        
        Args:
            test_case: Test case definition with steps
            context: Execution context
            config: Execution configuration
            
        Returns:
            List of step results
        """
        pass
    
    @abstractmethod
    async def execute_step(
        self,
        step: Dict[str, Any],
        step_order: int,
        context: ExecutionContextSchema,
        config: ExecutionConfigSchema
    ) -> StepResultModel:
        """
        Execute a single test step.
        
        Args:
            step: Step definition
            step_order: Order of step in test case
            context: Execution context
            config: Execution configuration
            
        Returns:
            Step execution result
        """
        pass
    
    @abstractmethod
    async def validate_test_case(
        self,
        test_case: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate test case structure for this runner type.
        
        Args:
            test_case: Test case to validate
            
        Returns:
            Validation result with errors if any
        """
        pass
    
    def _create_step_result(
        self,
        step: Dict[str, Any],
        step_order: int,
        status: StepStatus = StepStatus.PENDING
    ) -> StepResultModel:
        """Create initial step result model."""
        return StepResultModel(
            step_id=step.get('step_id', f"step_{step_order}"),
            step_name=step.get('name', f"Step {step_order + 1}"),
            step_order=step_order,
            status=status,
            started_at=datetime.now(timezone.utc) if status == StepStatus.RUNNING else None
        )


class GenericTestRunner(BaseTestRunner):
    """
    Generic test runner for standard test cases.
    
    Handles basic test execution with action-based steps,
    data validation, and result verification.
    """
    
    def __init__(self):
        super().__init__(TestRunnerType.GENERIC)
    
    async def execute_test(
        self,
        test_case: Dict[str, Any],
        context: ExecutionContextSchema,
        config: ExecutionConfigSchema
    ) -> List[StepResultModel]:
        """Execute generic test case with sequential step execution."""
        self.logger.info(f"Executing generic test case: {test_case.get('test_case_id')}")
        
        steps = test_case.get('steps', [])
        step_results = []
        
        for i, step in enumerate(steps):
            try:
                step_result = await self.execute_step(step, i, context, config)
                step_results.append(step_result)
                
                # Stop on failure if fail_fast is enabled
                if step_result.status == StepStatus.FAILED and config.fail_fast:
                    self.logger.warning(f"Stopping execution due to step failure (fail_fast enabled)")
                    break
                    
            except Exception as e:
                self.logger.error(f"Step execution failed: {step.get('name')} - {str(e)}")
                failed_step = self._create_step_result(step, i, StepStatus.FAILED)
                failed_step.error_details = {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "stack_trace": "Error during step execution"
                }
                step_results.append(failed_step)
                
                if config.fail_fast:
                    break
        
        self.logger.info(f"Generic test execution completed: {len(step_results)} steps")
        return step_results
    
    async def execute_step(
        self,
        step: Dict[str, Any],
        step_order: int,
        context: ExecutionContextSchema,
        config: ExecutionConfigSchema
    ) -> StepResultModel:
        """Execute individual generic test step."""
        step_result = self._create_step_result(step, step_order, StepStatus.RUNNING)
        
        try:
            self.logger.debug(f"Executing generic step: {step_result.step_name}")
            
            # Extract step data
            action = step.get('action', 'verify')
            input_data = step.get('input_data', {})
            expected_result = step.get('expected_result', {})
            
            step_result.input_data = input_data
            step_result.expected_result = expected_result
            
            # Simulate step execution based on action type
            actual_result = await self._execute_generic_action(
                action, input_data, context, config
            )
            
            step_result.actual_result = actual_result
            
            # Verify results
            verification_passed = await self._verify_step_result(
                expected_result, actual_result
            )
            
            step_result.status = StepStatus.PASSED if verification_passed else StepStatus.FAILED
            
            if not verification_passed:
                step_result.error_details = {
                    "error_type": "AssertionError",
                    "error_message": "Expected result did not match actual result",
                    "expected": expected_result,
                    "actual": actual_result
                }
            
            step_result.completed_at = datetime.now(timezone.utc)
            step_result.duration_ms = int(
                (step_result.completed_at - step_result.started_at).total_seconds() * 1000
            )
            
            self.logger.debug(f"Generic step completed: {step_result.step_name} - {step_result.status}")
            return step_result
            
        except Exception as e:
            self.logger.error(f"Generic step execution error: {step_result.step_name} - {str(e)}")
            step_result.status = StepStatus.FAILED
            step_result.completed_at = datetime.now(timezone.utc)
            step_result.duration_ms = int(
                (step_result.completed_at - step_result.started_at).total_seconds() * 1000
            )
            step_result.error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "stack_trace": "Error during generic step execution"
            }
            return step_result
    
    async def validate_test_case(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """Validate generic test case structure."""
        errors = []
        warnings = []
        
        # Check required fields
        if not test_case.get('test_case_id'):
            errors.append("test_case_id is required")
        
        if not test_case.get('title'):
            warnings.append("title is recommended")
        
        # Validate steps
        steps = test_case.get('steps', [])
        if not steps:
            errors.append("At least one step is required")
        
        for i, step in enumerate(steps):
            if not step.get('name'):
                errors.append(f"Step {i}: name is required")
            
            if not step.get('action'):
                warnings.append(f"Step {i}: action is recommended")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    async def _execute_generic_action(
        self,
        action: str,
        input_data: Dict[str, Any],
        context: ExecutionContextSchema,
        config: ExecutionConfigSchema
    ) -> Dict[str, Any]:
        """Execute generic action and return result."""
        import asyncio
        import random
        
        # Simulate execution time
        execution_time = random.uniform(0.5, 2.0)
        await asyncio.sleep(execution_time)
        
        # Simulate different action types
        if action == "navigate":
            return {
                "status": "success",
                "url": input_data.get("url", "https://example.com"),
                "page_title": "Example Page"
            }
        elif action == "click":
            return {
                "status": "success",
                "element": input_data.get("element", "button"),
                "clicked": True
            }
        elif action == "input":
            return {
                "status": "success",
                "field": input_data.get("field", "input"),
                "value": input_data.get("value", "test data")
            }
        elif action == "verify":
            # 90% success rate for verification
            success = random.random() > 0.1
            return {
                "status": "success" if success else "failed",
                "verified": success,
                "message": "Verification passed" if success else "Verification failed"
            }
        else:
            return {
                "status": "success",
                "action": action,
                "message": f"Action {action} executed successfully"
            }
    
    async def _verify_step_result(
        self,
        expected: Dict[str, Any],
        actual: Dict[str, Any]
    ) -> bool:
        """Verify step result against expected outcome."""
        if not expected:
            return True  # No expectations means success
        
        # Simple verification logic
        for key, expected_value in expected.items():
            if key not in actual:
                return False
            if actual[key] != expected_value:
                return False
        
        return True


class BDDTestRunner(BaseTestRunner):
    """
    BDD (Behavior-Driven Development) test runner.
    
    Handles Gherkin-style test execution with Given-When-Then steps
    and scenario-based test organization.
    """
    
    def __init__(self):
        super().__init__(TestRunnerType.BDD)
    
    async def execute_test(
        self,
        test_case: Dict[str, Any],
        context: ExecutionContextSchema,
        config: ExecutionConfigSchema
    ) -> List[StepResultModel]:
        """Execute BDD test case with scenario-based execution."""
        self.logger.info(f"Executing BDD test case: {test_case.get('test_case_id')}")
        
        scenarios = test_case.get('scenarios', [])
        if not scenarios:
            # Treat as single scenario
            scenarios = [{"steps": test_case.get('steps', [])}]
        
        all_step_results = []
        
        for scenario_idx, scenario in enumerate(scenarios):
            scenario_steps = scenario.get('steps', [])
            
            for step_idx, step in enumerate(scenario_steps):
                global_step_order = len(all_step_results)
                
                try:
                    step_result = await self.execute_step(
                        step, global_step_order, context, config
                    )
                    all_step_results.append(step_result)
                    
                    # Stop scenario on failure if fail_fast is enabled
                    if step_result.status == StepStatus.FAILED and config.fail_fast:
                        self.logger.warning(f"Stopping BDD scenario due to step failure")
                        break
                        
                except Exception as e:
                    self.logger.error(f"BDD step execution failed: {step.get('name')} - {str(e)}")
                    failed_step = self._create_step_result(step, global_step_order, StepStatus.FAILED)
                    failed_step.error_details = {
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "scenario_index": scenario_idx
                    }
                    all_step_results.append(failed_step)
                    
                    if config.fail_fast:
                        break
        
        self.logger.info(f"BDD test execution completed: {len(all_step_results)} steps")
        return all_step_results
    
    async def execute_step(
        self,
        step: Dict[str, Any],
        step_order: int,
        context: ExecutionContextSchema,
        config: ExecutionConfigSchema
    ) -> StepResultModel:
        """Execute individual BDD step (Given/When/Then)."""
        step_result = self._create_step_result(step, step_order, StepStatus.RUNNING)
        
        try:
            self.logger.debug(f"Executing BDD step: {step_result.step_name}")
            
            # Extract BDD-specific data
            step_type = step.get('type', 'given')  # given, when, then
            step_text = step.get('text', step.get('name', ''))
            step_data = step.get('data', {})
            
            step_result.input_data = {
                "type": step_type,
                "text": step_text,
                "data": step_data
            }
            
            # Execute based on step type
            actual_result = await self._execute_bdd_step(
                step_type, step_text, step_data, context, config
            )
            
            step_result.actual_result = actual_result
            
            # BDD steps are generally pass/fail based on execution success
            step_result.status = StepStatus.PASSED if actual_result.get('success', True) else StepStatus.FAILED
            
            if not actual_result.get('success', True):
                step_result.error_details = {
                    "error_type": "BDDStepError",
                    "error_message": actual_result.get('error', 'BDD step failed'),
                    "step_type": step_type,
                    "step_text": step_text
                }
            
            step_result.completed_at = datetime.now(timezone.utc)
            step_result.duration_ms = int(
                (step_result.completed_at - step_result.started_at).total_seconds() * 1000
            )
            
            self.logger.debug(f"BDD step completed: {step_result.step_name} - {step_result.status}")
            return step_result
            
        except Exception as e:
            self.logger.error(f"BDD step execution error: {step_result.step_name} - {str(e)}")
            step_result.status = StepStatus.FAILED
            step_result.completed_at = datetime.now(timezone.utc)
            step_result.duration_ms = int(
                (step_result.completed_at - step_result.started_at).total_seconds() * 1000
            )
            step_result.error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "stack_trace": "Error during BDD step execution"
            }
            return step_result
    
    async def validate_test_case(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """Validate BDD test case structure."""
        errors = []
        warnings = []
        
        # Check required fields
        if not test_case.get('test_case_id'):
            errors.append("test_case_id is required")
        
        # Check for scenarios or steps
        scenarios = test_case.get('scenarios', [])
        steps = test_case.get('steps', [])
        
        if not scenarios and not steps:
            errors.append("Either scenarios or steps must be provided")
        
        # Validate scenarios
        for i, scenario in enumerate(scenarios):
            scenario_steps = scenario.get('steps', [])
            if not scenario_steps:
                errors.append(f"Scenario {i}: at least one step is required")
            
            # Check for proper BDD structure
            step_types = [step.get('type', 'given') for step in scenario_steps]
            if not any(t in ['given', 'when', 'then'] for t in step_types):
                warnings.append(f"Scenario {i}: should include Given/When/Then steps")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    async def _execute_bdd_step(
        self,
        step_type: str,
        step_text: str,
        step_data: Dict[str, Any],
        context: ExecutionContextSchema,
        config: ExecutionConfigSchema
    ) -> Dict[str, Any]:
        """Execute BDD step based on type and text."""
        import asyncio
        import random
        
        # Simulate execution time
        execution_time = random.uniform(0.3, 1.5)
        await asyncio.sleep(execution_time)
        
        # Simulate BDD step execution
        success_rate = 0.85  # 85% success rate for BDD steps
        success = random.random() < success_rate
        
        result = {
            "success": success,
            "step_type": step_type,
            "step_text": step_text,
            "execution_time": execution_time
        }
        
        if not success:
            result["error"] = f"BDD step failed: {step_text}"
        
        return result


class ManualTestRunner(BaseTestRunner):
    """
    Manual test runner for human-executed test cases.
    
    Provides framework for manual test execution with
    step-by-step guidance and result collection.
    """
    
    def __init__(self):
        super().__init__(TestRunnerType.MANUAL)
    
    async def execute_test(
        self,
        test_case: Dict[str, Any],
        context: ExecutionContextSchema,
        config: ExecutionConfigSchema
    ) -> List[StepResultModel]:
        """Execute manual test case with guided steps."""
        self.logger.info(f"Executing manual test case: {test_case.get('test_case_id')}")
        
        steps = test_case.get('steps', [])
        step_results = []
        
        for i, step in enumerate(steps):
            try:
                step_result = await self.execute_step(step, i, context, config)
                step_results.append(step_result)
                
                # Manual tests typically continue even on failure
                # unless explicitly configured otherwise
                
            except Exception as e:
                self.logger.error(f"Manual step execution failed: {step.get('name')} - {str(e)}")
                failed_step = self._create_step_result(step, i, StepStatus.FAILED)
                failed_step.error_details = {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "stack_trace": "Error during manual step execution"
                }
                step_results.append(failed_step)
        
        self.logger.info(f"Manual test execution completed: {len(step_results)} steps")
        return step_results
    
    async def execute_step(
        self,
        step: Dict[str, Any],
        step_order: int,
        context: ExecutionContextSchema,
        config: ExecutionConfigSchema
    ) -> StepResultModel:
        """Execute manual test step (simulated for demo)."""
        step_result = self._create_step_result(step, step_order, StepStatus.RUNNING)
        
        try:
            self.logger.debug(f"Executing manual step: {step_result.step_name}")
            
            # Extract manual step data
            instructions = step.get('instructions', step.get('description', ''))
            expected_outcome = step.get('expected_outcome', {})
            
            step_result.input_data = {
                "instructions": instructions,
                "expected_outcome": expected_outcome
            }
            
            # Simulate manual execution (in real implementation, this would wait for user input)
            actual_result = await self._simulate_manual_execution(
                instructions, expected_outcome, context, config
            )
            
            step_result.actual_result = actual_result
            step_result.status = StepStatus.PASSED if actual_result.get('passed', True) else StepStatus.FAILED
            
            if not actual_result.get('passed', True):
                step_result.error_details = {
                    "error_type": "ManualTestFailure",
                    "error_message": actual_result.get('failure_reason', 'Manual test step failed'),
                    "instructions": instructions
                }
            
            step_result.completed_at = datetime.now(timezone.utc)
            step_result.duration_ms = int(
                (step_result.completed_at - step_result.started_at).total_seconds() * 1000
            )
            
            self.logger.debug(f"Manual step completed: {step_result.step_name} - {step_result.status}")
            return step_result
            
        except Exception as e:
            self.logger.error(f"Manual step execution error: {step_result.step_name} - {str(e)}")
            step_result.status = StepStatus.FAILED
            step_result.completed_at = datetime.now(timezone.utc)
            step_result.duration_ms = int(
                (step_result.completed_at - step_result.started_at).total_seconds() * 1000
            )
            step_result.error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "stack_trace": "Error during manual step execution"
            }
            return step_result
    
    async def validate_test_case(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """Validate manual test case structure."""
        errors = []
        warnings = []
        
        # Check required fields
        if not test_case.get('test_case_id'):
            errors.append("test_case_id is required")
        
        # Validate steps
        steps = test_case.get('steps', [])
        if not steps:
            errors.append("At least one step is required")
        
        for i, step in enumerate(steps):
            if not step.get('name'):
                errors.append(f"Step {i}: name is required")
            
            if not step.get('instructions') and not step.get('description'):
                errors.append(f"Step {i}: instructions or description is required")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    async def _simulate_manual_execution(
        self,
        instructions: str,
        expected_outcome: Dict[str, Any],
        context: ExecutionContextSchema,
        config: ExecutionConfigSchema
    ) -> Dict[str, Any]:
        """Simulate manual test execution (for demo purposes)."""
        import asyncio
        import random
        
        # Simulate manual execution time (longer than automated)
        execution_time = random.uniform(5.0, 15.0)
        await asyncio.sleep(execution_time / 10.0)  # Reduced for demo
        
        # Simulate manual test result (80% success rate)
        passed = random.random() < 0.8
        
        result = {
            "passed": passed,
            "instructions": instructions,
            "execution_time": execution_time,
            "tester_notes": "Simulated manual test execution"
        }
        
        if not passed:
            result["failure_reason"] = "Manual verification failed - simulated failure"
        
        return result


class TestRunnerService:
    """
    Service for managing test runners and coordinating test execution.
    
    Provides factory methods for creating appropriate test runners
    and orchestrating test execution across different test types.
    """
    
    def __init__(self, database: AsyncIOMotorDatabase):
        self.database = database
        
        # Initialize test runners
        self.runners = {
            TestRunnerType.GENERIC: GenericTestRunner(),
            TestRunnerType.BDD: BDDTestRunner(),
            TestRunnerType.MANUAL: ManualTestRunner()
        }
        
        logger.info("TestRunnerService initialized with runners: %s", list(self.runners.keys()))
    
    async def execute_test_case(
        self,
        test_case: Dict[str, Any],
        context: ExecutionContextSchema,
        config: ExecutionConfigSchema
    ) -> List[StepResultModel]:
        """
        Execute test case using appropriate runner based on test type.
        
        Args:
            test_case: Test case definition
            context: Execution context
            config: Execution configuration
            
        Returns:
            List of step execution results
        """
        test_type = test_case.get('test_type', 'GENERIC').lower()
        runner_type = TestRunnerType(test_type) if test_type in TestRunnerType.__members__.values() else TestRunnerType.GENERIC
        
        runner = self.runners.get(runner_type)
        if not runner:
            raise ValueError(f"No runner available for test type: {test_type}")
        
        logger.info(f"Executing test case with {runner_type} runner: {test_case.get('test_case_id')}")
        
        # Validate test case before execution
        validation_result = await runner.validate_test_case(test_case)
        if not validation_result.get('valid', False):
            raise ValueError(f"Test case validation failed: {validation_result.get('errors', [])}")
        
        # Execute test case
        return await runner.execute_test(test_case, context, config)
    
    async def validate_test_case(
        self,
        test_case: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate test case structure for appropriate runner.
        
        Args:
            test_case: Test case to validate
            
        Returns:
            Validation result
        """
        test_type = test_case.get('test_type', 'GENERIC').lower()
        runner_type = TestRunnerType(test_type) if test_type in TestRunnerType.__members__.values() else TestRunnerType.GENERIC
        
        runner = self.runners.get(runner_type)
        if not runner:
            return {
                "valid": False,
                "errors": [f"No runner available for test type: {test_type}"],
                "warnings": []
            }
        
        return await runner.validate_test_case(test_case)
    
    def get_available_runners(self) -> List[str]:
        """Get list of available test runner types."""
        return list(self.runners.keys())
    
    def get_runner_info(self, runner_type: TestRunnerType) -> Dict[str, Any]:
        """Get information about a specific test runner."""
        runner = self.runners.get(runner_type)
        if not runner:
            return {"error": f"Runner not found: {runner_type}"}
        
        return {
            "type": runner_type,
            "class": runner.__class__.__name__,
            "description": runner.__class__.__doc__.strip() if runner.__class__.__doc__ else "No description available"
        }


class TestRunnerServiceFactory:
    """Factory for creating TestRunnerService instances."""
    
    @staticmethod
    def create(database: AsyncIOMotorDatabase) -> TestRunnerService:
        """Create TestRunnerService instance with database dependency."""
        return TestRunnerService(database) 
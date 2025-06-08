"""
Test Execution Engine - Service Package

Provides business logic services for the Test Execution Engine including:
- Execution orchestration and lifecycle management
- Test runner framework for different test types
- State management and real-time tracking
- Result processing and aggregation
- Queue management and background processing
- Monitoring and observability services

All services follow clean architecture principles with proper dependency injection,
async operations, and comprehensive error handling.
"""

from .execution_service import ExecutionService, ExecutionServiceFactory
from .execution_orchestrator import ExecutionOrchestrator, ExecutionOrchestratorFactory
from .execution_state_service import ExecutionStateService, ExecutionStateServiceFactory
from .test_runner_service import TestRunnerService, TestRunnerServiceFactory
from .result_processor_service import ResultProcessorService, ResultProcessorServiceFactory
from .execution_queue_service import ExecutionQueueService, ExecutionQueueServiceFactory
from .execution_monitoring_service import ExecutionMonitoringService, ExecutionMonitoringServiceFactory

__all__ = [
    # Main Services
    "ExecutionService",
    "ExecutionOrchestrator", 
    "ExecutionStateService",
    "TestRunnerService",
    "ResultProcessorService",
    "ExecutionQueueService",
    "ExecutionMonitoringService",
    
    # Service Factories
    "ExecutionServiceFactory",
    "ExecutionOrchestratorFactory",
    "ExecutionStateServiceFactory", 
    "TestRunnerServiceFactory",
    "ResultProcessorServiceFactory",
    "ExecutionQueueServiceFactory",
    "ExecutionMonitoringServiceFactory"
] 
"""
Test Execution Engine - Model Package

Provides MongoDB models for the Test Execution Engine including:
- ExecutionTraceModel: Main execution tracking model with smart partitioning
- StepResultModel: Individual step execution results
- ExecutionStatistics: Real-time and historical execution metrics  
- Supporting enums and data structures

All models follow the BaseMongoModel pattern with UTC timestamps,
version management, and optimized MongoDB indexing strategies.
"""

from .execution_trace_model import (
    ExecutionTraceModel,
    StepResultModel,
    ExecutionStatistics,
    ExecutionStatus,
    StepStatus,
    ExecutionType,
    ResourceUsageMetrics,
    StepErrorDetails,
    ExecutionError,
    StepExecutionError,
    ExecutionTimeoutError,
    StateTransitionError,
    ResourceAllocationError
)

__all__ = [
    # Core Models
    "ExecutionTraceModel",
    "StepResultModel", 
    "ExecutionStatistics",
    
    # Enums
    "ExecutionStatus",
    "StepStatus", 
    "ExecutionType",
    
    # Supporting Models
    "ResourceUsageMetrics",
    "StepErrorDetails",
    
    # Exceptions
    "ExecutionError",
    "StepExecutionError",
    "ExecutionTimeoutError", 
    "StateTransitionError",
    "ResourceAllocationError"
] 
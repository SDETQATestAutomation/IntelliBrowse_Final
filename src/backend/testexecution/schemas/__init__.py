"""
Test Execution Engine - Schema Package

Provides Pydantic schemas for the Test Execution Engine including:
- Request schemas for execution operations (start, monitor, control)
- Response schemas with flexible field inclusion for performance
- Validation schemas for input data and business rules
- Pagination and filtering support for list operations

All schemas follow clean architecture principles with proper validation,
type safety, and OpenAPI documentation integration.
"""

from .execution_schemas import (
    # Request Schemas
    StartExecutionRequest,
    StartTestCaseExecutionRequest,
    StartTestSuiteExecutionRequest,
    UpdateExecutionStatusRequest,
    FilterExecutionsRequest,
    
    # Response Schemas
    ExecutionTraceResponse,
    ExecutionListResponse,
    ExecutionStatsResponse,
    StepResultResponse,
    ExecutionProgressResponse,
    
    # Supporting Schemas
    ExecutionContextSchema,
    ExecutionConfigSchema,
    PaginationMeta,
    FilterMeta,
    SortMeta,
    
    # Field Inclusion Control
    ExecutionFieldInclusion,
    StepFieldInclusion,
    
    # Additional Enums
    ReportFormat,
    ResultSeverity
)

__all__ = [
    # Request Schemas
    "StartExecutionRequest",
    "StartTestCaseExecutionRequest", 
    "StartTestSuiteExecutionRequest",
    "UpdateExecutionStatusRequest",
    "FilterExecutionsRequest",
    
    # Response Schemas
    "ExecutionTraceResponse",
    "ExecutionListResponse",
    "ExecutionStatsResponse", 
    "StepResultResponse",
    "ExecutionProgressResponse",
    
    # Supporting Schemas
    "ExecutionContextSchema",
    "ExecutionConfigSchema",
    "PaginationMeta",
    "FilterMeta",
    "SortMeta",
    
    # Field Inclusion Control
    "ExecutionFieldInclusion",
    "StepFieldInclusion",
    
    # Additional Enums
    "ReportFormat",
    "ResultSeverity"
] 
"""
Test Case Schemas Package

Exports request/response schemas and validation models for test case management.
"""

from .test_case_schemas import (
    # Request schemas
    CreateTestCaseRequest,
    UpdateTestCaseRequest,
    FilterTestCasesRequest,
    UpdateStepsRequest,
    UpdateStatusRequest,
    BulkTagRequest,
    
    # Response schemas
    TestCaseResponse,
    TestCaseListResponse,
    TestCaseStatsResponse,
    
    # Step schemas
    TestCaseStepRequest,
    TestCaseStepResponse,
    
    # Attachment schemas
    AttachmentRefRequest,
    AttachmentRefResponse,
    
    # Base schemas (re-export for convenience)
    BaseResponse,
    PaginatedResponse,
)

__all__ = [
    # Request schemas
    "CreateTestCaseRequest",
    "UpdateTestCaseRequest", 
    "FilterTestCasesRequest",
    "UpdateStepsRequest",
    "UpdateStatusRequest",
    "BulkTagRequest",
    
    # Response schemas
    "TestCaseResponse",
    "TestCaseListResponse",
    "TestCaseStatsResponse",
    
    # Step schemas
    "TestCaseStepRequest",
    "TestCaseStepResponse",
    
    # Attachment schemas
    "AttachmentRefRequest",
    "AttachmentRefResponse",
    
    # Base schemas
    "BaseResponse",
    "PaginatedResponse",
] 
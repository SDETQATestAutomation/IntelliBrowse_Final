"""
Assert Response Schemas for IntelliBrowse MCP Server.

This module defines the Pydantic schemas for network response assertion operations,
including request validation, response formatting, and assertion result handling.
Part of the IntelliBrowse MCP Server implementation.

Author: IntelliBrowse Team
Created: 2025-01-18
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
import re


class AssertResponseRequest(BaseModel):
    """
    Request schema for asserting network response properties.
    
    Validates responses captured by expect_response against specified criteria.
    """
    
    session_id: str = Field(
        ...,
        description="Active browser session ID",
        min_length=1,
        max_length=100
    )
    
    response_id: str = Field(
        ...,
        description="Response ID from expect_response",
        min_length=1,
        max_length=100
    )
    
    status_code: Optional[int] = Field(
        default=None,
        description="Expected HTTP status code",
        ge=100,
        le=599
    )
    
    contains_text: Optional[str] = Field(
        default=None,
        description="Text that must be present in response body",
        max_length=1000
    )
    
    contains_pattern: Optional[str] = Field(
        default=None,
        description="Regex pattern that must match response body",
        max_length=500
    )
    
    headers: Optional[Dict[str, str]] = Field(
        default=None,
        description="Response headers that must match (key-value pairs)"
    )
    
    json_path_assertions: Optional[Dict[str, Any]] = Field(
        default=None,
        description="JSON path assertions for response body (path: expected_value)"
    )
    
    response_time_max_ms: Optional[int] = Field(
        default=None,
        description="Maximum acceptable response time in milliseconds",
        ge=1
    )
    
    content_type: Optional[str] = Field(
        default=None,
        description="Expected content-type header value",
        max_length=100
    )
    
    timeout_ms: Optional[int] = Field(
        default=5000,
        description="Assertion timeout in milliseconds",
        ge=1000,
        le=60000
    )
    
    @field_validator('contains_pattern')

    
    @classmethod
    def validate_contains_pattern(cls, v):
        """Validate regex pattern syntax."""
        if v is None:
            return v
        
        try:
            re.compile(v)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")
        
        return v


class AssertionResult(BaseModel):
    """
    Schema for individual assertion result.
    """
    
    assertion_type: str = Field(
        ...,
        description="Type of assertion (status_code, contains_text, header, etc.)"
    )
    
    expected: Any = Field(
        ...,
        description="Expected value"
    )
    
    actual: Any = Field(
        ...,
        description="Actual value found"
    )
    
    passed: bool = Field(
        ...,
        description="Whether the assertion passed"
    )
    
    message: str = Field(
        ...,
        description="Detailed assertion result message"
    )
    
    path: Optional[str] = Field(
        default=None,
        description="JSON path or header name for structured assertions"
    )


class CapturedResponse(BaseModel):
    """
    Schema for captured response data.
    """
    
    status: int = Field(
        ...,
        description="HTTP status code"
    )
    
    status_text: str = Field(
        ...,
        description="HTTP status text"
    )
    
    headers: Dict[str, str] = Field(
        ...,
        description="Response headers"
    )
    
    body: Optional[str] = Field(
        default=None,
        description="Response body content"
    )
    
    url: str = Field(
        ...,
        description="Request URL"
    )
    
    method: str = Field(
        ...,
        description="HTTP method"
    )
    
    response_time_ms: Optional[int] = Field(
        default=None,
        description="Response time in milliseconds"
    )
    
    timestamp: str = Field(
        ...,
        description="ISO timestamp when response was captured"
    )


class AssertResponseResponse(BaseModel):
    """
    Response schema for network response assertion.
    """
    
    success: bool = Field(
        ...,
        description="Whether all assertions passed"
    )
    
    response_id: str = Field(
        ...,
        description="Response ID that was asserted"
    )
    
    assertions: List[AssertionResult] = Field(
        ...,
        description="Results of all assertions performed"
    )
    
    total_assertions: int = Field(
        ...,
        description="Total number of assertions performed"
    )
    
    passed_assertions: int = Field(
        ...,
        description="Number of assertions that passed"
    )
    
    failed_assertions: int = Field(
        ...,
        description="Number of assertions that failed"
    )
    
    captured_response: Optional[CapturedResponse] = Field(
        default=None,
        description="The captured response data that was asserted"
    )
    
    expectation_status: str = Field(
        ...,
        description="Status of the expectation (fulfilled, expired, failed)"
    )
    
    session_info: Dict[str, Any] = Field(
        ...,
        description="Session context information"
    )
    
    assertion_time: str = Field(
        ...,
        description="ISO timestamp when assertions were performed"
    )
    
    message: str = Field(
        ...,
        description="Overall assertion result message"
    )
    
    error: Optional[str] = Field(
        default=None,
        description="Error message if operation failed"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the assertions"
    )


class AssertResponseError(BaseModel):
    """
    Error response schema for assertion failures.
    """
    
    success: bool = Field(
        default=False,
        description="Always false for error responses"
    )
    
    error: str = Field(
        ...,
        description="Error message describing what went wrong"
    )
    
    error_type: str = Field(
        ...,
        description="Type of error (session_not_found, response_not_found, timeout, etc.)"
    )
    
    session_id: Optional[str] = Field(
        default=None,
        description="Session ID that was requested"
    )
    
    response_id: Optional[str] = Field(
        default=None,
        description="Response ID that was being asserted"
    )
    
    timestamp: str = Field(
        ...,
        description="ISO timestamp when error occurred"
    )
    
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional error details"
    ) 
"""
Expect Response Schemas for IntelliBrowse MCP Server.

This module defines the Pydantic schemas for network response expectation operations,
including request validation, response formatting, and monitoring capabilities.
Part of the IntelliBrowse MCP Server implementation.

Author: IntelliBrowse Team
Created: 2025-01-18
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
import re


class ExpectResponseRequest(BaseModel):
    """
    Request schema for setting up network response expectations.
    
    Supports URL pattern matching, HTTP method filtering, and timeout management.
    """
    
    session_id: str = Field(
        ...,
        description="Active browser session ID",
        min_length=1,
        max_length=100
    )
    
    url_pattern: str = Field(
        ...,
        description="URL pattern to match (regex supported)",
        min_length=1,
        max_length=1000
    )
    
    method: Optional[str] = Field(
        default="GET",
        description="HTTP method to match (GET, POST, PUT, DELETE, PATCH, etc.)"
    )
    
    timeout_ms: Optional[int] = Field(
        default=30000,
        description="Wait timeout in milliseconds",
        ge=1000,
        le=300000
    )
    
    response_id: Optional[str] = Field(
        default=None,
        description="Unique ID for this expectation (auto-generated if not provided)",
        max_length=100
    )
    
    match_headers: Optional[Dict[str, str]] = Field(
        default=None,
        description="Request headers that must match"
    )
    
    match_body_pattern: Optional[str] = Field(
        default=None,
        description="Regex pattern for request body matching",
        max_length=500
    )
    
    expected_status_codes: Optional[List[int]] = Field(
        default=None,
        description="Expected HTTP status codes (e.g., [200, 201, 204])"
    )
    
    capture_response_body: Optional[bool] = Field(
        default=True,
        description="Whether to capture the response body"
    )
    
    capture_response_headers: Optional[bool] = Field(
        default=True,
        description="Whether to capture response headers"
    )
    
    @field_validator('method')

    
    @classmethod
    def validate_http_method(cls, v):
        """Validate HTTP method."""
        if v is None:
            return "GET"
        
        valid_methods = {
            'GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS', 'TRACE'
        }
        
        method_upper = v.upper()
        if method_upper not in valid_methods:
            raise ValueError(f"Invalid HTTP method: {v}. Valid methods: {', '.join(sorted(valid_methods))}")
        
        return method_upper
    
    @field_validator('url_pattern')

    
    @classmethod
    def validate_url_pattern(cls, v):
        """Validate URL pattern regex syntax."""
        try:
            re.compile(v)
        except re.error as e:
            raise ValueError(f"Invalid URL pattern regex: {e}")
        
        return v
    
    @field_validator('match_body_pattern')

    
    @classmethod
    def validate_body_pattern(cls, v):
        """Validate body pattern regex syntax."""
        if v is None:
            return v
        
        try:
            re.compile(v)
        except re.error as e:
            raise ValueError(f"Invalid body pattern regex: {e}")
        
        return v
    
    @field_validator('expected_status_codes')

    
    @classmethod
    def validate_status_codes(cls, v):
        """Validate status codes."""
        if v is None:
            return v
        
        for code in v:
            if not isinstance(code, int) or code < 100 or code > 599:
                raise ValueError(f"Invalid HTTP status code: {code}. Must be between 100 and 599")
        
        return v


class NetworkExpectation(BaseModel):
    """
    Schema for network expectation tracking.
    """
    
    response_id: str = Field(
        ...,
        description="Unique ID for this expectation"
    )
    
    url_pattern: str = Field(
        ...,
        description="URL pattern being monitored"
    )
    
    method: str = Field(
        ...,
        description="HTTP method being monitored"
    )
    
    timeout_ms: int = Field(
        ...,
        description="Timeout in milliseconds"
    )
    
    created_at: str = Field(
        ...,
        description="ISO timestamp when expectation was created"
    )
    
    expires_at: str = Field(
        ...,
        description="ISO timestamp when expectation expires"
    )
    
    status: str = Field(
        ...,
        description="Expectation status (waiting, fulfilled, expired, failed)"
    )
    
    match_criteria: Dict[str, Any] = Field(
        ...,
        description="All matching criteria for this expectation"
    )
    
    capture_settings: Dict[str, bool] = Field(
        ...,
        description="Response capture settings"
    )


class ExpectResponseResponse(BaseModel):
    """
    Response schema for setting up network response expectations.
    """
    
    success: bool = Field(
        ...,
        description="Whether the expectation was set up successfully"
    )
    
    response_id: str = Field(
        ...,
        description="Unique ID for this expectation"
    )
    
    expectation: NetworkExpectation = Field(
        ...,
        description="Details of the created expectation"
    )
    
    monitoring_started: bool = Field(
        ...,
        description="Whether network monitoring has been started"
    )
    
    session_info: Dict[str, Any] = Field(
        ...,
        description="Session context information"
    )
    
    setup_time: str = Field(
        ...,
        description="ISO timestamp when expectation was set up"
    )
    
    message: str = Field(
        ...,
        description="Operation result message"
    )
    
    error: Optional[str] = Field(
        default=None,
        description="Error message if operation failed"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the operation"
    )


class ExpectResponseError(BaseModel):
    """
    Error response schema for expect response failures.
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
        description="Type of error (session_not_found, invalid_pattern, setup_failed, etc.)"
    )
    
    session_id: Optional[str] = Field(
        default=None,
        description="Session ID that was requested"
    )
    
    response_id: Optional[str] = Field(
        default=None,
        description="Response ID that was being set up"
    )
    
    timestamp: str = Field(
        ...,
        description="ISO timestamp when error occurred"
    )
    
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional error details"
    ) 
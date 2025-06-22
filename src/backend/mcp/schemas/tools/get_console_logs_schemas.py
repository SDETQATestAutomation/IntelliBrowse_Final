"""
Get Console Logs Schemas for IntelliBrowse MCP Server.

This module defines the Pydantic schemas for browser console log retrieval operations,
including request validation, response formatting, and filtering capabilities.
Part of the IntelliBrowse MCP Server implementation.

Author: IntelliBrowse Team
Created: 2025-01-18
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
import re


class GetConsoleLogsRequest(BaseModel):
    """
    Request schema for retrieving browser console logs.
    
    Supports advanced filtering by log types, timestamps, patterns, and pagination.
    """
    
    session_id: str = Field(
        ...,
        description="Active browser session ID",
        min_length=1,
        max_length=100
    )
    
    log_types: Optional[List[str]] = Field(
        default=None,
        description="Filter by log types (log, error, warn, info, debug, trace, assert, clear, count, countReset, dir, dirxml, group, groupCollapsed, groupEnd, profile, profileEnd, table, time, timeEnd, timeLog, timeStamp)"
    )
    
    since: Optional[str] = Field(
        default=None,
        description="ISO timestamp for logs after this time (e.g., '2025-01-18T10:30:00Z')"
    )
    
    limit: Optional[int] = Field(
        default=100,
        description="Maximum number of logs to return",
        ge=1,
        le=10000
    )
    
    search_pattern: Optional[str] = Field(
        default=None,
        description="Regex pattern for log content filtering",
        max_length=500
    )
    
    clear_after_read: Optional[bool] = Field(
        default=False,
        description="Clear console logs after retrieval"
    )
    
    include_stack_traces: Optional[bool] = Field(
        default=True,
        description="Include stack traces for error logs"
    )
    
    @field_validator('log_types')

    
    @classmethod
    def validate_log_types(cls, v):
        """Validate log types against known console log types."""
        if v is None:
            return v
        
        valid_types = {
            'log', 'error', 'warn', 'info', 'debug', 'trace', 'assert', 'clear',
            'count', 'countReset', 'dir', 'dirxml', 'group', 'groupCollapsed',
            'groupEnd', 'profile', 'profileEnd', 'table', 'time', 'timeEnd',
            'timeLog', 'timeStamp'
        }
        
        for log_type in v:
            if log_type not in valid_types:
                raise ValueError(f"Invalid log type: {log_type}. Valid types: {', '.join(sorted(valid_types))}")
        
        return v
    
    @field_validator('since')

    
    @classmethod
    def validate_since_timestamp(cls, v):
        """Validate ISO timestamp format."""
        if v is None:
            return v
        
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
        except ValueError:
            raise ValueError("Invalid timestamp format. Use ISO format like '2025-01-18T10:30:00Z'")
        
        return v
    
    @field_validator('search_pattern')

    
    @classmethod
    def validate_search_pattern(cls, v):
        """Validate regex pattern syntax."""
        if v is None:
            return v
        
        try:
            re.compile(v)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")
        
        return v


class ConsoleLogEntry(BaseModel):
    """
    Schema for individual console log entry.
    """
    
    type: str = Field(
        ...,
        description="Log type (log, error, warn, info, debug, etc.)"
    )
    
    timestamp: str = Field(
        ...,
        description="ISO timestamp when log was created"
    )
    
    message: str = Field(
        ...,
        description="Log message content"
    )
    
    args: Optional[List[Any]] = Field(
        default=None,
        description="Additional arguments passed to console method"
    )
    
    url: Optional[str] = Field(
        default=None,
        description="URL of the page where log occurred"
    )
    
    line_number: Optional[int] = Field(
        default=None,
        description="Line number where log occurred"
    )
    
    column_number: Optional[int] = Field(
        default=None,
        description="Column number where log occurred"
    )
    
    stack_trace: Optional[str] = Field(
        default=None,
        description="Stack trace for error logs"
    )
    
    source: Optional[str] = Field(
        default=None,
        description="Source context (e.g., 'javascript', 'network', 'security')"
    )


class GetConsoleLogsResponse(BaseModel):
    """
    Response schema for console logs retrieval.
    """
    
    success: bool = Field(
        ...,
        description="Whether the operation was successful"
    )
    
    logs: List[ConsoleLogEntry] = Field(
        ...,
        description="Retrieved console log entries"
    )
    
    total_count: int = Field(
        ...,
        description="Total number of logs available (before limit)"
    )
    
    filtered_count: int = Field(
        ...,
        description="Number of logs after filtering"
    )
    
    retrieved_count: int = Field(
        ...,
        description="Number of logs actually retrieved (after limit)"
    )
    
    filters_applied: Dict[str, Any] = Field(
        ...,
        description="Summary of filters that were applied"
    )
    
    cleared_after_read: bool = Field(
        ...,
        description="Whether logs were cleared after reading"
    )
    
    session_info: Dict[str, Any] = Field(
        ...,
        description="Session context information"
    )
    
    retrieval_time: str = Field(
        ...,
        description="ISO timestamp when logs were retrieved"
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


class GetConsoleLogsError(BaseModel):
    """
    Error response schema for console logs retrieval failures.
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
        description="Type of error (session_not_found, invalid_filter, timeout, etc.)"
    )
    
    session_id: Optional[str] = Field(
        default=None,
        description="Session ID that was requested"
    )
    
    timestamp: str = Field(
        ...,
        description="ISO timestamp when error occurred"
    )
    
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional error details"
    ) 
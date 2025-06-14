"""
Core exception classes for IntelliBrowse MCP Server.

This module defines custom exceptions for MCP server operations,
including authentication, authorization, session management, and context errors.
"""

from typing import Optional, Dict, Any


class MCPServerError(Exception):
    """Base exception for MCP server errors."""
    
    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON serialization."""
        return {
            "error_type": self.__class__.__name__,
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details
        }


class AuthenticationError(MCPServerError):
    """Authentication-related errors."""
    
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(message, **kwargs)


class AuthorizationError(MCPServerError):
    """Authorization-related errors."""
    
    def __init__(self, message: str = "Authorization failed", **kwargs):
        super().__init__(message, **kwargs)


class SessionError(MCPServerError):
    """Session management errors."""
    
    def __init__(self, message: str = "Session error", **kwargs):
        super().__init__(message, **kwargs)


class ContextError(MCPServerError):
    """Context management errors."""
    
    def __init__(self, message: str = "Context error", **kwargs):
        super().__init__(message, **kwargs)


class ToolExecutionError(MCPServerError):
    """Tool execution errors."""
    
    def __init__(self, message: str = "Tool execution failed", **kwargs):
        super().__init__(message, **kwargs)


class ResourceError(MCPServerError):
    """Resource access errors."""
    
    def __init__(self, message: str = "Resource error", **kwargs):
        super().__init__(message, **kwargs)


class ConfigurationError(MCPServerError):
    """Configuration-related errors."""
    
    def __init__(self, message: str = "Configuration error", **kwargs):
        super().__init__(message, **kwargs)


class ValidationError(MCPServerError):
    """Data validation errors."""
    
    def __init__(self, message: str = "Validation error", **kwargs):
        super().__init__(message, **kwargs) 
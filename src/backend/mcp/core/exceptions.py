"""
Core Exception Classes for IntelliBrowse MCP Server

This module defines comprehensive exception hierarchy for the MCP server,
providing detailed error information and proper exception handling patterns.

Exception Hierarchy:
- MCPError (base)
  - MCPConnectionError
  - MCPOperationError
  - MCPValidationError
  - MCPAuthenticationError
  - MCPAuthorizationError
  - VectorStoreError
    - VectorStoreConnectionError
    - VectorStoreOperationError
  - BrowserError
  - AIError
"""

from typing import Any, Dict, Optional


class MCPError(Exception):
    """
    Base exception class for all MCP server errors.
    
    Provides structured error information including error codes,
    context data, and user-friendly messages.
    """
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        """
        Initialize MCP error.
        
        Args:
            message: Human-readable error message
            error_code: Unique error code for identification
            context: Additional context information
            original_error: Original exception that caused this error
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__.upper()
        self.context = context or {}
        self.original_error = original_error
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary format."""
        return {
            "error_type": self.__class__.__name__,
            "error_code": self.error_code,
            "message": self.message,
            "context": self.context,
            "original_error": str(self.original_error) if self.original_error else None
        }
    
    def __str__(self) -> str:
        """String representation of the error."""
        parts = [f"{self.__class__.__name__}: {self.message}"]
        if self.error_code:
            parts.append(f"[{self.error_code}]")
        if self.context:
            parts.append(f"Context: {self.context}")
        return " | ".join(parts)


class MCPConnectionError(MCPError):
    """Exception raised for connection-related errors."""
    
    def __init__(
        self,
        message: str,
        service: Optional[str] = None,
        endpoint: Optional[str] = None,
        **kwargs
    ):
        context = kwargs.get("context", {})
        if service:
            context["service"] = service
        if endpoint:
            context["endpoint"] = endpoint
        kwargs["context"] = context
        super().__init__(message, **kwargs)


class MCPOperationError(MCPError):
    """Exception raised for operation-related errors."""
    
    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        resource: Optional[str] = None,
        **kwargs
    ):
        context = kwargs.get("context", {})
        if operation:
            context["operation"] = operation
        if resource:
            context["resource"] = resource
        kwargs["context"] = context
        super().__init__(message, **kwargs)


class MCPValidationError(MCPError):
    """Exception raised for validation errors."""
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        **kwargs
    ):
        context = kwargs.get("context", {})
        if field:
            context["field"] = field
        if value is not None:
            context["value"] = str(value)[:100]  # Truncate long values
        kwargs["context"] = context
        super().__init__(message, **kwargs)


class MCPAuthenticationError(MCPError):
    """Exception raised for authentication failures."""
    
    def __init__(
        self,
        message: str = "Authentication failed",
        auth_method: Optional[str] = None,
        **kwargs
    ):
        context = kwargs.get("context", {})
        if auth_method:
            context["auth_method"] = auth_method
        kwargs["context"] = context
        super().__init__(message, error_code="AUTH_FAILED", **kwargs)


class MCPAuthorizationError(MCPError):
    """Exception raised for authorization failures."""
    
    def __init__(
        self,
        message: str = "Insufficient permissions",
        required_permission: Optional[str] = None,
        user_permissions: Optional[list] = None,
        **kwargs
    ):
        context = kwargs.get("context", {})
        if required_permission:
            context["required_permission"] = required_permission
        if user_permissions:
            context["user_permissions"] = user_permissions
        kwargs["context"] = context
        super().__init__(message, error_code="AUTHORIZATION_FAILED", **kwargs)


class VectorStoreError(MCPError):
    """Base exception for vector store operations."""
    
    def __init__(
        self,
        message: str,
        collection: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs
    ):
        context = kwargs.get("context", {})
        if collection:
            context["collection"] = collection
        if operation:
            context["operation"] = operation
        kwargs["context"] = context
        super().__init__(message, **kwargs)


class VectorStoreConnectionError(VectorStoreError):
    """Exception raised for vector store connection errors."""
    
    def __init__(
        self,
        message: str,
        database_type: str = "ChromaDB",
        connection_url: Optional[str] = None,
        **kwargs
    ):
        context = kwargs.get("context", {})
        context["database_type"] = database_type
        if connection_url:
            # Don't include sensitive connection details in logs
            context["connection_url"] = connection_url.split("@")[-1] if "@" in connection_url else connection_url
        kwargs["context"] = context
        super().__init__(message, error_code="VECTOR_STORE_CONNECTION_FAILED", **kwargs)


class VectorStoreOperationError(VectorStoreError):
    """Exception raised for vector store operation errors."""
    
    def __init__(
        self,
        message: str,
        operation_type: Optional[str] = None,
        affected_records: Optional[int] = None,
        **kwargs
    ):
        context = kwargs.get("context", {})
        if operation_type:
            context["operation_type"] = operation_type
        if affected_records is not None:
            context["affected_records"] = affected_records
        kwargs["context"] = context
        super().__init__(message, error_code="VECTOR_STORE_OPERATION_FAILED", **kwargs)


class BrowserError(MCPError):
    """Exception raised for browser automation errors."""
    
    def __init__(
        self,
        message: str,
        browser_type: Optional[str] = None,
        page_url: Optional[str] = None,
        element_selector: Optional[str] = None,
        **kwargs
    ):
        context = kwargs.get("context", {})
        if browser_type:
            context["browser_type"] = browser_type
        if page_url:
            context["page_url"] = page_url
        if element_selector:
            context["element_selector"] = element_selector
        kwargs["context"] = context
        super().__init__(message, **kwargs)


class BrowserConnectionError(BrowserError):
    """Exception raised for browser connection errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, error_code="BROWSER_CONNECTION_FAILED", **kwargs)


class BrowserTimeoutError(BrowserError):
    """Exception raised for browser timeout errors."""
    
    def __init__(
        self,
        message: str,
        timeout_ms: Optional[int] = None,
        **kwargs
    ):
        context = kwargs.get("context", {})
        if timeout_ms:
            context["timeout_ms"] = timeout_ms
        kwargs["context"] = context
        super().__init__(message, error_code="BROWSER_TIMEOUT", **kwargs)


class ElementNotFoundError(BrowserError):
    """Exception raised when a DOM element cannot be found."""
    
    def __init__(
        self,
        message: str,
        selector: Optional[str] = None,
        selector_type: Optional[str] = None,
        **kwargs
    ):
        context = kwargs.get("context", {})
        if selector:
            context["selector"] = selector
        if selector_type:
            context["selector_type"] = selector_type
        kwargs["context"] = context
        super().__init__(message, error_code="ELEMENT_NOT_FOUND", **kwargs)


class AIError(MCPError):
    """Exception raised for AI/LLM operation errors."""
    
    def __init__(
        self,
        message: str,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        tokens_used: Optional[int] = None,
        **kwargs
    ):
        context = kwargs.get("context", {})
        if model:
            context["model"] = model
        if provider:
            context["provider"] = provider
        if tokens_used:
            context["tokens_used"] = tokens_used
        kwargs["context"] = context
        super().__init__(message, **kwargs)


class AIQuotaExceededError(AIError):
    """Exception raised when AI service quota is exceeded."""
    
    def __init__(
        self,
        message: str = "AI service quota exceeded",
        quota_type: Optional[str] = None,
        reset_time: Optional[str] = None,
        **kwargs
    ):
        context = kwargs.get("context", {})
        if quota_type:
            context["quota_type"] = quota_type
        if reset_time:
            context["reset_time"] = reset_time
        kwargs["context"] = context
        super().__init__(message, error_code="AI_QUOTA_EXCEEDED", **kwargs)


class AIModelUnavailableError(AIError):
    """Exception raised when AI model is unavailable."""
    
    def __init__(
        self,
        message: str,
        model_name: Optional[str] = None,
        **kwargs
    ):
        context = kwargs.get("context", {})
        if model_name:
            context["model_name"] = model_name
        kwargs["context"] = context
        super().__init__(message, error_code="AI_MODEL_UNAVAILABLE", **kwargs)


class ConfigurationError(MCPError):
    """Exception raised for configuration-related errors."""
    
    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        config_file: Optional[str] = None,
        **kwargs
    ):
        context = kwargs.get("context", {})
        if config_key:
            context["config_key"] = config_key
        if config_file:
            context["config_file"] = config_file
        kwargs["context"] = context
        super().__init__(message, error_code="CONFIGURATION_ERROR", **kwargs)


class SessionError(MCPError):
    """Exception raised for session management errors."""
    
    def __init__(
        self,
        message: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs
    ):
        context = kwargs.get("context", {})
        if session_id:
            context["session_id"] = session_id
        if user_id:
            context["user_id"] = user_id
        kwargs["context"] = context
        super().__init__(message, **kwargs)


class SessionExpiredError(SessionError):
    """Exception raised when a session has expired."""
    
    def __init__(
        self,
        message: str = "Session has expired",
        expiry_time: Optional[str] = None,
        **kwargs
    ):
        context = kwargs.get("context", {})
        if expiry_time:
            context["expiry_time"] = expiry_time
        kwargs["context"] = context
        super().__init__(message, error_code="SESSION_EXPIRED", **kwargs)


class RateLimitError(MCPError):
    """Exception raised when rate limits are exceeded."""
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        limit: Optional[int] = None,
        reset_time: Optional[str] = None,
        **kwargs
    ):
        context = kwargs.get("context", {})
        if limit:
            context["limit"] = limit
        if reset_time:
            context["reset_time"] = reset_time
        kwargs["context"] = context
        super().__init__(message, error_code="RATE_LIMIT_EXCEEDED", **kwargs)


class ContextError(MCPError):
    """Exception raised for context management errors."""
    pass


class AIAgentError(MCPError):
    """Exception raised for AI agent orchestration errors."""
    pass


class NLPProcessingError(MCPError):
    """Exception raised for natural language processing errors."""
    pass


class ToolExecutionError(MCPError):
    """Exception raised for tool execution errors."""
    
    def __init__(
        self,
        message: str,
        tool_name: Optional[str] = None,
        tool_args: Optional[Dict[str, Any]] = None,
        execution_time: Optional[float] = None,
        **kwargs
    ):
        context = kwargs.get("context", {})
        if tool_name:
            context["tool_name"] = tool_name
        if tool_args:
            context["tool_args"] = tool_args
        if execution_time:
            context["execution_time"] = execution_time
        kwargs["context"] = context
        super().__init__(message, error_code="TOOL_EXECUTION_ERROR", **kwargs)


# Utility functions for exception handling
def wrap_exception(
    original_error: Exception,
    message: Optional[str] = None,
    error_class: type = MCPError,
    **kwargs
) -> MCPError:
    """
    Wrap an existing exception in an MCP exception.
    
    Args:
        original_error: The original exception to wrap
        message: Custom message (defaults to original error message)
        error_class: MCP exception class to use
        **kwargs: Additional arguments for the MCP exception
    
    Returns:
        MCP exception wrapping the original error
    """
    if message is None:
        message = str(original_error)
    
    kwargs["original_error"] = original_error
    return error_class(message, **kwargs)


def is_retryable_error(error: Exception) -> bool:
    """
    Check if an error is retryable.
    
    Args:
        error: Exception to check
    
    Returns:
        True if the error is retryable, False otherwise
    """
    retryable_errors = (
        MCPConnectionError,
        VectorStoreConnectionError,
        BrowserConnectionError,
        BrowserTimeoutError,
        AIQuotaExceededError
    )
    
    return isinstance(error, retryable_errors) or (
        isinstance(error, MCPError) and
        error.error_code in [
            "TEMPORARY_ERROR",
            "SERVICE_UNAVAILABLE",
            "TIMEOUT",
            "RATE_LIMIT_EXCEEDED"
        ]
    )


def get_error_summary(error: Exception) -> Dict[str, Any]:
    """
    Get a summary of an error suitable for logging or API responses.
    
    Args:
        error: Exception to summarize
    
    Returns:
        Dictionary containing error summary
    """
    if isinstance(error, MCPError):
        return error.to_dict()
    
    return {
        "error_type": type(error).__name__,
        "error_code": "GENERIC_ERROR",
        "message": str(error),
        "context": {},
        "original_error": None
    } 
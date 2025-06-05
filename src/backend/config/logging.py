"""
Logging configuration for IntelliBrowse backend.
Uses loguru for structured logging with file rotation and request correlation.
"""

import os
import sys
import logging
from typing import Dict, Any, Optional
from loguru import logger

from .constants import (
    LOG_FORMAT,
    LOG_ROTATION,
    LOG_RETENTION,
    LOG_LEVEL_CONSOLE,
    LOG_LEVEL_FILE,
)
from .env import get_settings


class InterceptHandler:
    """
    Intercept standard logging messages and redirect to loguru.
    This allows other libraries to use loguru for consistent logging.
    """

    def emit(self, record):
        # Get corresponding loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def format_record(record: Dict[str, Any]) -> str:
    """
    Custom formatter for loguru records.
    Adds request ID correlation when available.
    """
    format_string = LOG_FORMAT

    # Add request ID if available in extra
    if record.get("extra", {}).get("request_id"):
        format_string = format_string.replace(
            "{message}", "[{extra[request_id]}] {message}"
        )

    # Add additional context for errors
    if record["level"].name in ["ERROR", "CRITICAL"] and record.get("extra", {}).get("error_details"):
        format_string += " | Details: {extra[error_details]}"

    return format_string + "\n"


def setup_logging() -> None:
    """
    Configure logging for the application.
    Sets up console and file handlers with appropriate levels and formatting.
    """
    settings = get_settings()

    # Remove default handler
    logger.remove()

    # Configure console handler
    logger.add(
        sys.stdout,
        level=settings.log_level,
        format=format_record,
        colorize=True,
        backtrace=True,
        diagnose=True,
    )

    # Configure file handler if enabled
    if settings.log_to_file:
        # Ensure log directory exists
        log_dir = os.path.dirname(settings.log_file_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        logger.add(
            settings.log_file_path,
            level=settings.log_level_file,
            format=format_record,
            rotation=LOG_ROTATION,
            retention=LOG_RETENTION,
            compression="zip",
            backtrace=True,
            diagnose=True,
            enqueue=True,  # Makes logging thread-safe
        )

    # Log startup message
    logger.info(
        f"Logging configured - Console: {settings.log_level}, "
        f"File: {settings.log_level_file if settings.log_to_file else 'Disabled'}"
    )


def get_logger(name: str) -> logger:
    """
    Get a logger instance for a specific module.
    
    Args:
        name: Usually __name__ of the calling module
        
    Returns:
        Configured logger instance
    """
    return logger.bind(name=name)


def log_request_start(request_id: str, method: str, path: str, client_ip: str) -> None:
    """
    Log the start of an API request.
    
    Args:
        request_id: Unique request identifier
        method: HTTP method
        path: Request path
        client_ip: Client IP address
    """
    logger.info(
        f"Request started: {method} {path}",
        extra={
            "request_id": request_id,
            "http_method": method,
            "path": path,
            "client_ip": client_ip,
        }
    )


def log_request_end(
    request_id: str, 
    method: str, 
    path: str, 
    status_code: int, 
    duration_ms: float
) -> None:
    """
    Log the end of an API request.
    
    Args:
        request_id: Unique request identifier
        method: HTTP method
        path: Request path
        status_code: HTTP status code
        duration_ms: Request duration in milliseconds
    """
    level = "ERROR" if status_code >= 400 else "INFO"
    
    logger.log(
        level,
        f"Request completed: {method} {path} - {status_code} ({duration_ms:.2f}ms)",
        extra={
            "request_id": request_id,
            "http_method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": duration_ms,
        }
    )


def log_error(
    error: Exception, 
    context: str, 
    request_id: Optional[str] = None,
    extra_details: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log an error with context and optional request correlation.
    
    Args:
        error: The exception that occurred
        context: Context description (e.g., "user_authentication", "database_query")
        request_id: Optional request ID for correlation
        extra_details: Additional details to include
    """
    extra = {
        "context": context,
        "error_type": type(error).__name__,
        "error_details": str(error),
    }
    
    if request_id:
        extra["request_id"] = request_id
        
    if extra_details:
        extra.update(extra_details)
    
    logger.error(
        f"Error in {context}: {str(error)}",
        extra=extra
    )


def log_security_event(
    event_type: str, 
    details: Dict[str, Any], 
    request_id: Optional[str] = None
) -> None:
    """
    Log security-related events.
    
    Args:
        event_type: Type of security event (e.g., "authentication_failure", "suspicious_request")
        details: Event details
        request_id: Optional request ID for correlation
    """
    extra = {
        "security_event": event_type,
        "event_details": details,
    }
    
    if request_id:
        extra["request_id"] = request_id
    
    logger.warning(
        f"Security event: {event_type}",
        extra=extra
    )


# Configure logging when module is imported
if not logger._core.handlers:
    setup_logging()
    

# Export main logger for direct use
__all__ = [
    "logger",
    "get_logger", 
    "log_request_start",
    "log_request_end", 
    "log_error",
    "log_security_event",
    "setup_logging",
] 
"""
Pydantic response schemas for IntelliBrowse backend.
Provides consistent API response structure across all endpoints.
"""

from datetime import datetime
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field


# Generic type for response data
T = TypeVar('T')


class BaseResponse(BaseModel, Generic[T]):
    """
    Base response model for all API endpoints.
    Provides consistent structure with success flag, data, and message.
    """
    
    success: bool = Field(
        description="Indicates if the request was successful"
    )
    data: Optional[T] = Field(
        default=None,
        description="Response data payload"
    )
    message: str = Field(
        description="Human-readable message describing the result"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when the response was generated"
    )


class SuccessResponse(BaseResponse[T]):
    """
    Success response model.
    Used when an operation completes successfully.
    """
    
    success: bool = Field(default=True)
    
    def __init__(self, data: T = None, message: str = "Operation completed successfully", **kwargs):
        super().__init__(
            success=True,
            data=data,
            message=message,
            **kwargs
        )


class ErrorResponse(BaseResponse[None]):
    """
    Error response model.
    Used when an operation fails or encounters an error.
    """
    
    success: bool = Field(default=False)
    data: None = Field(default=None)
    error_code: Optional[str] = Field(
        default=None,
        description="Application-specific error code"
    )
    error_details: Optional[dict] = Field(
        default=None,
        description="Additional error details for debugging"
    )
    
    def __init__(
        self, 
        message: str = "An error occurred",
        error_code: Optional[str] = None,
        error_details: Optional[dict] = None,
        **kwargs
    ):
        super().__init__(
            success=False,
            data=None,
            message=message,
            error_code=error_code,
            error_details=error_details,
            **kwargs
        )


class HealthData(BaseModel):
    """
    Health check response data model.
    Contains system status and uptime information.
    """
    
    status: str = Field(
        description="System health status (healthy, degraded, unhealthy)"
    )
    uptime_seconds: float = Field(
        description="System uptime in seconds"
    )
    version: str = Field(
        description="Application version"
    )
    environment: str = Field(
        description="Current environment (development, staging, production)"
    )
    checks: Optional[dict] = Field(
        default=None,
        description="Individual component health checks"
    )


class HealthResponse(SuccessResponse[HealthData]):
    """
    Health check endpoint response.
    Extends SuccessResponse with HealthData.
    """
    
    def __init__(self, health_data: HealthData, message: str, **kwargs):
        super().__init__(
            data=health_data,
            message=message,
            **kwargs
        )


# Utility functions for creating responses
def create_success_response(
    data: Any = None, 
    message: str = "Operation completed successfully"
) -> SuccessResponse:
    """
    Create a success response with optional data and message.
    
    Args:
        data: Response data payload
        message: Success message
        
    Returns:
        SuccessResponse instance
    """
    return SuccessResponse(data=data, message=message)


def create_error_response(
    message: str = "An error occurred",
    error_code: Optional[str] = None,
    error_details: Optional[dict] = None
) -> ErrorResponse:
    """
    Create an error response with message and optional details.
    
    Args:
        message: Error message
        error_code: Application-specific error code
        error_details: Additional error details
        
    Returns:
        ErrorResponse instance
    """
    return ErrorResponse(
        message=message,
        error_code=error_code,
        error_details=error_details
    )


def create_health_response(
    status: str,
    uptime_seconds: float,
    version: str,
    environment: str,
    message: str,
    checks: Optional[dict] = None
) -> HealthResponse:
    """
    Create a health check response.
    
    Args:
        status: Health status
        uptime_seconds: Uptime in seconds
        version: Application version
        environment: Current environment
        message: Health message
        checks: Optional component checks
        
    Returns:
        HealthResponse instance
    """
    health_data = HealthData(
        status=status,
        uptime_seconds=uptime_seconds,
        version=version,
        environment=environment,
        checks=checks
    )
    
    return HealthResponse(health_data=health_data, message=message) 
"""
Authentication response schemas for API endpoints.
Defines Pydantic models for standardized authentication responses.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

from ...schemas.response import BaseResponse


class TokenResponse(BaseModel):
    """
    Schema for JWT token response.
    
    Contains access token and metadata for successful authentication.
    """
    
    access_token: str = Field(
        ...,
        description="JWT access token for authenticated requests",
        example="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
    )
    token_type: str = Field(
        default="bearer",
        description="Token type (always 'bearer' for JWT)",
        example="bearer"
    )
    expires_in: int = Field(
        ...,
        description="Token expiry time in seconds",
        example=3600
    )
    expires_at: datetime = Field(
        ...,
        description="Token expiry timestamp",
        example="2024-12-31T23:59:59Z"
    )
    
    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                "token_type": "bearer",
                "expires_in": 3600,
                "expires_at": "2024-12-31T23:59:59Z"
            }
        }


class UserResponse(BaseModel):
    """
    Schema for user information response.
    
    Contains safe user data (excludes sensitive information like password).
    """
    
    id: str = Field(
        ...,
        description="User unique identifier",
        example="60f7b1b9e4b0c8a4f8e6d1a2"
    )
    email: str = Field(
        ...,
        description="User email address",
        example="user@example.com"
    )
    created_at: datetime = Field(
        ...,
        description="Account creation timestamp",
        example="2024-01-15T10:30:00Z"
    )
    updated_at: Optional[datetime] = Field(
        None,
        description="Last update timestamp",
        example="2024-01-20T14:45:00Z"
    )
    is_active: bool = Field(
        default=True,
        description="Account active status",
        example=True
    )
    login_count: int = Field(
        default=0,
        description="Number of successful logins",
        example=15
    )
    last_login: Optional[datetime] = Field(
        None,
        description="Last successful login timestamp",
        example="2024-01-25T09:15:00Z"
    )
    
    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "id": "60f7b1b9e4b0c8a4f8e6d1a2",
                "email": "user@example.com",
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-20T14:45:00Z",
                "is_active": True,
                "login_count": 15,
                "last_login": "2024-01-25T09:15:00Z"
            }
        }


class AuthResponse(BaseResponse):
    """
    Schema for authentication success response.
    
    Extends the base response with authentication-specific data including
    JWT token and user information.
    """
    
    data: Dict[str, Any] = Field(
        ...,
        description="Authentication response data containing token and user info"
    )
    
    @classmethod
    def create_success(
        cls,
        token: TokenResponse,
        user: UserResponse,
        message: str = "Authentication successful"
    ) -> "AuthResponse":
        """
        Create successful authentication response.
        
        Args:
            token: JWT token information
            user: User information
            message: Success message
            
        Returns:
            AuthResponse with token and user data
        """
        return cls(
            success=True,
            data={
                "token": token.model_dump(),
                "user": user.model_dump()
            },
            message=message,
            timestamp=datetime.utcnow()
        )
    
    @classmethod
    def create_login_success(
        cls,
        token: TokenResponse,
        user: UserResponse
    ) -> "AuthResponse":
        """Create successful login response."""
        return cls.create_success(
            token=token,
            user=user,
            message="Login successful"
        )
    
    @classmethod
    def create_signup_success(
        cls,
        token: TokenResponse,
        user: UserResponse
    ) -> "AuthResponse":
        """Create successful signup response."""
        return cls.create_success(
            token=token,
            user=user,
            message="User registration successful"
        )
    
    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {
                    "token": {
                        "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                        "token_type": "bearer",
                        "expires_in": 3600,
                        "expires_at": "2024-12-31T23:59:59Z"
                    },
                    "user": {
                        "id": "60f7b1b9e4b0c8a4f8e6d1a2",
                        "email": "user@example.com",
                        "created_at": "2024-01-15T10:30:00Z",
                        "is_active": True,
                        "login_count": 1,
                        "last_login": "2024-01-25T09:15:00Z"
                    }
                },
                "message": "Authentication successful",
                "timestamp": "2024-01-25T09:15:00Z"
            }
        }


class AuthErrorResponse(BaseResponse):
    """
    Schema for authentication error responses.
    
    Provides standardized error responses for authentication failures.
    """
    
    success: bool = Field(default=False, description="Always False for error responses")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Error data (usually None)")
    
    @classmethod
    def create_invalid_credentials(cls) -> "AuthErrorResponse":
        """Create invalid credentials error response."""
        return cls(
            success=False,
            data=None,
            message="Invalid email or password",
            timestamp=datetime.utcnow()
        )
    
    @classmethod
    def create_user_exists(cls, email: str) -> "AuthErrorResponse":
        """Create user already exists error response."""
        return cls(
            success=False,
            data=None,
            message=f"User with email {email} already exists",
            timestamp=datetime.utcnow()
        )
    
    @classmethod
    def create_user_not_found(cls) -> "AuthErrorResponse":
        """Create user not found error response."""
        return cls(
            success=False,
            data=None,
            message="User not found",
            timestamp=datetime.utcnow()
        )
    
    @classmethod
    def create_token_invalid(cls) -> "AuthErrorResponse":
        """Create invalid token error response."""
        return cls(
            success=False,
            data=None,
            message="Invalid or expired token",
            timestamp=datetime.utcnow()
        )
    
    @classmethod
    def create_token_expired(cls) -> "AuthErrorResponse":
        """Create token expired error response."""
        return cls(
            success=False,
            data=None,
            message="Token has expired",
            timestamp=datetime.utcnow()
        )
    
    @classmethod
    def create_validation_error(cls, details: str) -> "AuthErrorResponse":
        """Create validation error response."""
        return cls(
            success=False,
            data=None,
            message=f"Validation error: {details}",
            timestamp=datetime.utcnow()
        )
    
    @classmethod
    def create_internal_error(cls) -> "AuthErrorResponse":
        """Create internal server error response."""
        return cls(
            success=False,
            data=None,
            message="Internal server error during authentication",
            timestamp=datetime.utcnow()
        )
    
    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "success": False,
                "data": None,
                "message": "Invalid email or password",
                "timestamp": "2024-01-25T09:15:00Z"
            }
        }


class RefreshTokenResponse(BaseModel):
    """
    Schema for refresh token response.
    
    For future implementation of refresh token functionality.
    """
    
    access_token: str = Field(
        ...,
        description="New JWT access token",
        example="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
    )
    token_type: str = Field(
        default="bearer",
        description="Token type",
        example="bearer"
    )
    expires_in: int = Field(
        ...,
        description="Token expiry time in seconds",
        example=3600
    )
    
    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                "token_type": "bearer",
                "expires_in": 3600
            }
        } 
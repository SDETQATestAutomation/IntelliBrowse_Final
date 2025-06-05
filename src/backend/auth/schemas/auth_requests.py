"""
Authentication request schemas for API endpoints.
Defines Pydantic models for validating incoming authentication requests.
"""

from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional


class LoginRequest(BaseModel):
    """
    Schema for user login requests.
    
    Validates email format and password presence for authentication endpoints.
    """
    
    email: EmailStr = Field(
        ..., 
        description="User email address",
        example="user@example.com"
    )
    password: str = Field(
        ..., 
        min_length=1,
        max_length=128,
        description="User password",
        example="SecurePassword123"
    )
    remember_me: Optional[bool] = Field(
        default=False,
        description="Extend token expiry (future feature)",
        example=False
    )
    
    @validator("email")
    def validate_email_not_empty(cls, v):
        """Ensure email is not empty after validation."""
        if not v or not v.strip():
            raise ValueError("Email cannot be empty")
        return v.strip().lower()
    
    @validator("password")
    def validate_password_not_empty(cls, v):
        """Ensure password is not empty."""
        if not v or not v.strip():
            raise ValueError("Password cannot be empty")
        return v
    
    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "SecurePassword123",
                "remember_me": False
            }
        }


class SignupRequest(BaseModel):
    """
    Schema for user registration requests.
    
    Validates email format and password strength requirements for new user creation.
    """
    
    email: EmailStr = Field(
        ..., 
        description="User email address (must be unique)",
        example="newuser@example.com"
    )
    password: str = Field(
        ..., 
        min_length=8,
        max_length=128,
        description="User password (8-128 characters with strength requirements)",
        example="SecurePassword123"
    )
    confirm_password: str = Field(
        ..., 
        min_length=8,
        max_length=128,
        description="Password confirmation (must match password)",
        example="SecurePassword123"
    )
    
    @validator("email")
    def validate_email_format(cls, v):
        """Validate and normalize email address."""
        if not v or not v.strip():
            raise ValueError("Email cannot be empty")
        
        email = v.strip().lower()
        
        # Additional email validation
        if len(email) > 254:  # RFC 5321 limit
            raise ValueError("Email address too long")
        
        return email
    
    @validator("password")
    def validate_password_strength(cls, v):
        """Validate password meets strength requirements."""
        if not v:
            raise ValueError("Password cannot be empty")
        
        password = v.strip()
        
        # Length validation
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")
        
        if len(password) > 128:
            raise ValueError("Password must not exceed 128 characters")
        
        # Strength requirements
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)
        
        if not has_upper:
            raise ValueError("Password must contain at least one uppercase letter")
        
        if not has_lower:
            raise ValueError("Password must contain at least one lowercase letter")
        
        if not has_digit:
            raise ValueError("Password must contain at least one digit")
        
        # Optional: Require special character (can be enabled later)
        # if not has_special:
        #     raise ValueError("Password must contain at least one special character")
        
        return password
    
    @validator("confirm_password")
    def validate_password_confirmation(cls, v, values):
        """Validate password confirmation matches password."""
        if not v:
            raise ValueError("Password confirmation cannot be empty")
        
        password = values.get("password")
        if password and v != password:
            raise ValueError("Password confirmation does not match password")
        
        return v
    
    def validate_passwords_match(self) -> bool:
        """Additional validation method for password matching."""
        return self.password == self.confirm_password
    
    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "email": "newuser@example.com",
                "password": "SecurePassword123",
                "confirm_password": "SecurePassword123"
            }
        }


class RefreshTokenRequest(BaseModel):
    """
    Schema for token refresh requests.
    
    For future implementation of refresh token functionality.
    """
    
    refresh_token: str = Field(
        ...,
        description="Refresh token for obtaining new access token",
        example="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
    )
    
    @validator("refresh_token")
    def validate_refresh_token(cls, v):
        """Validate refresh token is not empty."""
        if not v or not v.strip():
            raise ValueError("Refresh token cannot be empty")
        return v.strip()
    
    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
            }
        }


class PasswordResetRequest(BaseModel):
    """
    Schema for password reset requests.
    
    For future implementation of password reset functionality.
    """
    
    email: EmailStr = Field(
        ...,
        description="Email address for password reset",
        example="user@example.com"
    )
    
    @validator("email")
    def validate_email_not_empty(cls, v):
        """Ensure email is not empty after validation."""
        if not v or not v.strip():
            raise ValueError("Email cannot be empty")
        return v.strip().lower()
    
    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "email": "user@example.com"
            }
        } 
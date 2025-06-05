"""
Authentication routes for FastAPI endpoints.
Defines authentication API endpoints with proper documentation and validation.
"""

from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Body, Header
from fastapi.security import HTTPBearer
from pydantic import Field

from ...config.logging import get_logger
from ..schemas.auth_requests import SignupRequest, LoginRequest
from ..schemas.auth_responses import AuthResponse, AuthErrorResponse
from ..controllers.auth_controller import get_auth_controller

logger = get_logger(__name__)

# Create auth router
router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
    responses={
        401: {"description": "Unauthorized"},
        500: {"description": "Internal server error"},
    }
)

# HTTP Bearer security scheme for protected endpoints
security = HTTPBearer()


@router.post(
    "/signup",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="User Registration",
    description="Register a new user account with email and password",
    responses={
        201: {
            "description": "User registered successfully",
            "content": {
                "application/json": {
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
                                "login_count": 0
                            }
                        },
                        "message": "User registration successful",
                        "timestamp": "2024-01-15T10:30:00Z"
                    }
                }
            }
        },
        400: {
            "description": "Validation error or weak password",
            "content": {
                "application/json": {
                    "examples": {
                        "weak_password": {
                            "summary": "Weak password",
                            "value": {
                                "detail": {
                                    "message": "Password does not meet strength requirements",
                                    "feedback": ["Password must contain at least one uppercase letter"],
                                    "strength": "weak"
                                }
                            }
                        },
                        "validation_error": {
                            "summary": "Validation error",
                            "value": {
                                "detail": [
                                    {
                                        "loc": ["body", "email"],
                                        "msg": "field required",
                                        "type": "value_error.missing"
                                    }
                                ]
                            }
                        }
                    }
                }
            }
        },
        409: {
            "description": "User already exists",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "User with email user@example.com already exists"
                    }
                }
            }
        }
    }
)
async def signup(
    signup_data: SignupRequest = Body(
        ...,
        description="User registration data including email and password",
        example={
            "email": "user@example.com",
            "password": "SecurePassword123",
            "confirm_password": "SecurePassword123"
        }
    )
) -> AuthResponse:
    """
    Register a new user account.
    
    Creates a new user account with secure password hashing and returns
    a JWT token for immediate authentication.
    
    **Password Requirements:**
    - At least 8 characters long
    - Contains uppercase letter
    - Contains lowercase letter  
    - Contains at least one digit
    - Password confirmation must match
    
    **Security Features:**
    - Bcrypt password hashing with 12 rounds
    - Email uniqueness validation
    - Comprehensive password strength validation
    - JWT token with configurable expiry
    """
    controller = get_auth_controller()
    return await controller.signup_handler(signup_data)


@router.post(
    "/login",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    summary="User Login",
    description="Authenticate user with email and password",
    responses={
        200: {
            "description": "Login successful",
            "content": {
                "application/json": {
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
                                "login_count": 15,
                                "last_login": "2024-01-25T09:15:00Z"
                            }
                        },
                        "message": "Login successful",
                        "timestamp": "2024-01-25T09:15:00Z"
                    }
                }
            }
        },
        401: {
            "description": "Authentication failed",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_credentials": {
                            "summary": "Invalid credentials",
                            "value": {
                                "detail": "Invalid email or password"
                            }
                        },
                        "inactive_account": {
                            "summary": "Inactive account",
                            "value": {
                                "detail": "Account is inactive"
                            }
                        }
                    }
                }
            }
        }
    }
)
async def login(
    login_data: LoginRequest = Body(
        ...,
        description="User login credentials",
        example={
            "email": "user@example.com",
            "password": "SecurePassword123",
            "remember_me": False
        }
    )
) -> AuthResponse:
    """
    Authenticate user and return JWT token.
    
    Validates user credentials and returns a JWT token for authenticated
    access to protected endpoints.
    
    **Security Features:**
    - Secure password verification using bcrypt
    - Generic error messages to prevent user enumeration
    - Login tracking (count and timestamp)
    - Account status validation
    - Comprehensive audit logging
    """
    controller = get_auth_controller()
    return await controller.login_handler(login_data)


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Authentication Service Health Check",
    description="Check the health status of authentication services",
    responses={
        200: {
            "description": "Health check results",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "database": {
                            "status": "healthy",
                            "response_time_ms": 12.5,
                            "user_count": 42,
                            "connected": True
                        },
                        "password_hashing": "healthy",
                        "jwt_operations": "healthy"
                    }
                }
            }
        }
    }
)
async def auth_health() -> Dict[str, Any]:
    """
    Perform authentication service health check.
    
    Tests the health of authentication components including:
    - Database connectivity and performance
    - Password hashing operations
    - JWT token operations
    - Service dependencies
    """
    controller = get_auth_controller()
    return await controller.health_check_handler()


@router.get(
    "/token-info",
    status_code=status.HTTP_200_OK,
    summary="Token Information",
    description="Get information about the provided JWT token",
    responses={
        200: {
            "description": "Token information",
            "content": {
                "application/json": {
                    "example": {
                        "valid": True,
                        "user": {
                            "id": "60f7b1b9e4b0c8a4f8e6d1a2",
                            "email": "user@example.com",
                            "created_at": "2024-01-15T10:30:00Z",
                            "is_active": True,
                            "login_count": 15,
                            "last_login": "2024-01-25T09:15:00Z"
                        },
                        "message": "Token is valid"
                    }
                }
            }
        },
        401: {
            "description": "Invalid or expired token",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid or expired token"
                    }
                }
            }
        }
    }
)
async def token_info(
    authorization: str = Header(
        ...,
        description="JWT token in 'Bearer <token>' format",
        example="Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
    )
) -> Dict[str, Any]:
    """
    Get information about a JWT token.
    
    Validates the provided JWT token and returns information about
    the associated user. Useful for debugging and token inspection.
    
    **Usage:**
    Include the JWT token in the Authorization header:
    `Authorization: Bearer <your-jwt-token>`
    """
    # Extract token from Authorization header
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Use 'Bearer <token>'"
        )
    
    token = authorization[7:]  # Remove "Bearer " prefix
    
    controller = get_auth_controller()
    return await controller.token_info_handler(token)


# Additional endpoint for logout (placeholder for future enhancement)
@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="User Logout (Placeholder)",
    description="Logout user (token invalidation - future enhancement)",
    responses={
        200: {
            "description": "Logout successful",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Logout successful",
                        "timestamp": "2024-01-25T09:15:00Z"
                    }
                }
            }
        }
    }
)
async def logout(
    token: str = Depends(security)
) -> Dict[str, Any]:
    """
    Logout user (future enhancement).
    
    **Note:** This is a placeholder endpoint for future token invalidation
    functionality. Currently, JWT tokens are stateless and expire naturally.
    
    For enhanced security, consider implementing:
    - Token blacklisting
    - Refresh token revocation
    - Session management
    """
    logger.info(
        "Logout endpoint called (placeholder)",
        extra={"endpoint": "POST /auth/logout"}
    )
    
    return {
        "message": "Logout successful (token will expire naturally)",
        "note": "Token invalidation not yet implemented"
    } 
"""
JWT Bearer dependency for route protection.
Provides FastAPI dependency for JWT token validation and user authentication.
"""

from typing import Optional
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ...config.logging import get_logger
from ..schemas.auth_responses import UserResponse
from ..services.auth_service import get_auth_service

logger = get_logger(__name__)

# HTTP Bearer security scheme
security = HTTPBearer(auto_error=False)


class JWTBearer:
    """
    JWT Bearer dependency for FastAPI route protection.
    
    Provides authentication dependency that validates JWT tokens
    and returns authenticated user information.
    """
    
    def __init__(self, auto_error: bool = True):
        """
        Initialize JWT Bearer dependency.
        
        Args:
            auto_error: Whether to raise HTTP exception on auth failure
        """
        self.auto_error = auto_error
        self.auth_service = get_auth_service()
    
    async def __call__(
        self, 
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
    ) -> UserResponse:
        """
        Validate JWT token and return authenticated user.
        
        Args:
            credentials: HTTP authorization credentials
            
        Returns:
            Authenticated user model
            
        Raises:
            HTTPException: If authentication fails and auto_error is True
        """
        if not credentials:
            if self.auto_error:
                logger.warning(
                    "Authentication failed - no credentials provided",
                    extra={"endpoint": "protected_route"}
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication credentials required",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return None
        
        if credentials.scheme.lower() != "bearer":
            if self.auto_error:
                logger.warning(
                    f"Authentication failed - invalid scheme: {credentials.scheme}",
                    extra={"scheme": credentials.scheme}
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication scheme. Use Bearer token",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return None
        
        # Verify token and get user
        user = await self.auth_service.verify_token(credentials.credentials)
        
        if not user:
            if self.auto_error:
                logger.warning(
                    "Authentication failed - invalid or expired token",
                    extra={"token_prefix": credentials.credentials[:20] + "..."}
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return None
        
        logger.debug(
            f"Authentication successful for user: {user.email}",
            extra={
                "user_id": user.id,
                "email": user.email,
                "is_active": user.is_active,
            }
        )
        
        return user


class OptionalJWTBearer(JWTBearer):
    """
    Optional JWT Bearer dependency for routes that support both authenticated and unauthenticated access.
    
    Returns user if valid token is provided, None otherwise.
    Does not raise exceptions for missing or invalid tokens.
    """
    
    def __init__(self):
        """Initialize optional JWT Bearer dependency."""
        super().__init__(auto_error=False)


# Global instances for common use cases
jwt_bearer = JWTBearer()
optional_jwt_bearer = OptionalJWTBearer()


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> UserResponse:
    """
    FastAPI dependency to get current authenticated user.
    
    Args:
        credentials: HTTP authorization credentials
        
    Returns:
        Authenticated user model
        
    Raises:
        HTTPException: If authentication fails
        
    Usage:
        @app.get("/protected")
        async def protected_endpoint(user: UserResponse = Depends(get_current_user)):
            return {"user_id": user.id, "email": user.email}
    """
    return await jwt_bearer(credentials)


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[UserResponse]:
    """
    FastAPI dependency to get current user if authenticated (optional).
    
    Args:
        credentials: HTTP authorization credentials
        
    Returns:
        Authenticated user model if token is valid, None otherwise
        
    Usage:
        @app.get("/semi-protected")
        async def semi_protected_endpoint(user: Optional[UserResponse] = Depends(get_current_user_optional)):
            if user:
                return {"authenticated": True, "user_id": user.id}
            else:
                return {"authenticated": False, "message": "Public access"}
    """
    return await optional_jwt_bearer(credentials)


async def get_current_active_user(
    user: UserResponse = Depends(get_current_user)
) -> UserResponse:
    """
    FastAPI dependency to get current authenticated and active user.
    
    Args:
        user: Authenticated user from get_current_user
        
    Returns:
        Active user model
        
    Raises:
        HTTPException: If user is inactive
        
    Usage:
        @app.get("/active-only")
        async def active_only_endpoint(user: UserResponse = Depends(get_current_active_user)):
            return {"user_id": user.id, "status": "active"}
    """
    if not user.is_active:
        logger.warning(
            f"Access denied - inactive user: {user.email}",
            extra={
                "user_id": user.id,
                "email": user.email,
                "is_active": user.is_active,
            }
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )
    
    return user


# Admin role check (placeholder for future role-based access)
async def get_admin_user(
    user: UserResponse = Depends(get_current_active_user)
) -> UserResponse:
    """
    FastAPI dependency to get current admin user (placeholder).
    
    Args:
        user: Active authenticated user
        
    Returns:
        Admin user model
        
    Raises:
        HTTPException: If user is not admin
        
    Note:
        This is a placeholder for future role-based access control.
        Currently allows all active users.
    """
    # TODO: Implement role-based access control
    # For now, all active users are considered "admin" 
    # In future: check user.role == "admin" or similar
    
    logger.debug(
        f"Admin access granted to: {user.email} (role checking not implemented)",
        extra={
            "user_id": user.id,
            "email": user.email,
        }
    )
    
    return user 
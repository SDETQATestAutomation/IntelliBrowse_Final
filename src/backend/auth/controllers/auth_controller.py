"""
Authentication controller for handling authentication requests.
Provides request handling and validation for authentication endpoints.
"""

from typing import Dict, Any
from fastapi import HTTPException, status

from ...config.logging import get_logger
from ..schemas.auth_requests import SignupRequest, LoginRequest
from ..schemas.auth_responses import AuthResponse, TokenResponse, UserResponse
from ..services.auth_service import get_auth_service

logger = get_logger(__name__)


class AuthController:
    """
    Authentication controller for handling authentication requests.
    
    Handles HTTP request processing, validation, and response formatting
    for authentication endpoints with comprehensive error handling.
    """
    
    def __init__(self):
        self.auth_service = get_auth_service()
    
    async def signup_handler(self, signup_data: SignupRequest) -> AuthResponse:
        """
        Handle user registration requests.
        
        Args:
            signup_data: Validated user registration data
            
        Returns:
            AuthResponse with token and user information
            
        Raises:
            HTTPException: If registration fails
        """
        try:
            logger.info(
                f"Processing signup request for: {signup_data.email}",
                extra={
                    "email": signup_data.email,
                    "endpoint": "POST /auth/signup",
                }
            )
            
            # Call auth service to register user
            result = await self.auth_service.register_user(signup_data)
            
            # Create successful response
            response = AuthResponse.create_signup_success(
                token=result["token"],
                user=result["user"]
            )
            
            logger.info(
                f"Signup successful for: {signup_data.email}",
                extra={
                    "email": signup_data.email,
                    "user_id": result["user"].id,
                    "response_status": "success",
                }
            )
            
            return response
            
        except HTTPException as e:
            # Log and re-raise HTTP exceptions from service layer
            logger.warning(
                f"Signup failed for {signup_data.email}: {e.detail}",
                extra={
                    "email": signup_data.email,
                    "status_code": e.status_code,
                    "detail": e.detail,
                }
            )
            raise e
            
        except Exception as e:
            # Log unexpected errors
            logger.error(
                f"Unexpected error in signup handler for {signup_data.email}: {str(e)}",
                extra={
                    "email": signup_data.email,
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
            )
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error during registration"
            )
    
    async def login_handler(self, login_data: LoginRequest) -> AuthResponse:
        """
        Handle user login requests.
        
        Args:
            login_data: Validated user login credentials
            
        Returns:
            AuthResponse with token and user information
            
        Raises:
            HTTPException: If login fails
        """
        try:
            logger.info(
                f"Processing login request for: {login_data.email}",
                extra={
                    "email": login_data.email,
                    "endpoint": "POST /auth/login",
                    "remember_me": login_data.remember_me,
                }
            )
            
            # Call auth service to authenticate user
            result = await self.auth_service.authenticate_user(login_data)
            
            # Create successful response
            response = AuthResponse.create_login_success(
                token=result["token"],
                user=result["user"]
            )
            
            logger.info(
                f"Login successful for: {login_data.email}",
                extra={
                    "email": login_data.email,
                    "user_id": result["user"].id,
                    "login_count": result["user"].login_count,
                    "response_status": "success",
                }
            )
            
            return response
            
        except HTTPException as e:
            # Log and re-raise HTTP exceptions from service layer
            logger.warning(
                f"Login failed for {login_data.email}: {e.detail}",
                extra={
                    "email": login_data.email,
                    "status_code": e.status_code,
                    "detail": e.detail,
                }
            )
            raise e
            
        except Exception as e:
            # Log unexpected errors
            logger.error(
                f"Unexpected error in login handler for {login_data.email}: {str(e)}",
                extra={
                    "email": login_data.email,
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
            )
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error during authentication"
            )
    
    async def health_check_handler(self) -> Dict[str, Any]:
        """
        Handle authentication service health check requests.
        
        Returns:
            Dictionary with health check results
        """
        try:
            logger.debug(
                "Processing auth health check request",
                extra={"endpoint": "GET /auth/health"}
            )
            
            # Get health status from auth service
            health_data = await self.auth_service.health_check()
            
            logger.debug(
                f"Auth health check completed: {health_data.get('status', 'unknown')}",
                extra={
                    "health_status": health_data.get("status"),
                    "response_status": "success",
                }
            )
            
            return health_data
            
        except Exception as e:
            logger.error(
                f"Error in auth health check handler: {str(e)}",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
            )
            
            return {
                "status": "unhealthy",
                "error": str(e),
            }
    
    async def token_info_handler(self, token: str) -> Dict[str, Any]:
        """
        Handle token information requests (for debugging/admin use).
        
        Args:
            token: JWT token to inspect
            
        Returns:
            Dictionary with token information
            
        Raises:
            HTTPException: If token is invalid
        """
        try:
            logger.debug(
                "Processing token info request",
                extra={"endpoint": "GET /auth/token-info"}
            )
            
            # Verify token and get user
            user_model = await self.auth_service.verify_token(token)
            
            if not user_model:
                logger.warning(
                    "Token info request failed - invalid token",
                    extra={"token_valid": False}
                )
                
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token"
                )
            
            # Create user response
            user_response = UserResponse(
                id=user_model.id,
                email=user_model.email,
                created_at=user_model.created_at,
                updated_at=user_model.updated_at,
                is_active=user_model.is_active,
                login_count=user_model.login_count,
                last_login=user_model.last_login
            )
            
            logger.debug(
                f"Token info request successful for user: {user_model.email}",
                extra={
                    "user_id": user_model.id,
                    "email": user_model.email,
                    "token_valid": True,
                }
            )
            
            return {
                "valid": True,
                "user": user_response.model_dump(),
                "message": "Token is valid"
            }
            
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
            
        except Exception as e:
            logger.error(
                f"Error in token info handler: {str(e)}",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
            )
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error during token verification"
            )


# Global auth controller instance
_auth_controller = None


def get_auth_controller() -> AuthController:
    """
    Get the global auth controller instance.
    Uses singleton pattern for consistency.
    
    Returns:
        AuthController instance
    """
    global _auth_controller
    if _auth_controller is None:
        _auth_controller = AuthController()
    return _auth_controller 
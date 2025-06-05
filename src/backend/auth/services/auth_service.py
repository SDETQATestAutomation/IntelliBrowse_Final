"""
Authentication service for user registration and login operations.
Provides business logic for secure user authentication with JWT tokens.
"""

from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import HTTPException, status

from ...config.logging import get_logger
from ..schemas.auth_requests import SignupRequest, LoginRequest
from ..schemas.auth_responses import TokenResponse, UserResponse, AuthResponse
from ...models.user_model import UserModel, UserCreateModel
from ..utils.password_handler import get_password_handler
from ..utils.jwt_handler import get_jwt_handler
from .database_service import get_database_service

logger = get_logger(__name__)


class AuthService:
    """
    Authentication service for user registration and login operations.
    
    Handles user registration, authentication, and token generation with
    comprehensive security measures and error handling.
    """
    
    def __init__(self):
        self.password_handler = get_password_handler()
        self.jwt_handler = get_jwt_handler()
        self.db_service = get_database_service()
    
    async def register_user(self, signup_data: SignupRequest) -> Dict[str, Any]:
        """
        Register new user with secure password hashing.
        
        Args:
            signup_data: User registration data
            
        Returns:
            Dictionary with token and user information
            
        Raises:
            HTTPException: If registration fails
        """
        try:
            logger.info(
                f"User registration attempt: {signup_data.email}",
                extra={"email": signup_data.email}
            )
            
            # Validate password strength
            password_validation = self.password_handler.validate_password_strength(
                signup_data.password
            )
            
            if not password_validation["is_valid"]:
                error_msg = "Password does not meet strength requirements"
                feedback = password_validation.get("feedback", [])
                
                logger.warning(
                    f"Registration failed - weak password: {signup_data.email}",
                    extra={
                        "email": signup_data.email,
                        "password_strength": password_validation["strength"],
                        "feedback": feedback,
                    }
                )
                
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "message": error_msg,
                        "feedback": feedback,
                        "strength": password_validation["strength"],
                    }
                )
            
            # Check if user already exists
            if await self.db_service.user_exists_by_email(signup_data.email):
                logger.warning(
                    f"Registration failed - user exists: {signup_data.email}",
                    extra={"email": signup_data.email}
                )
                
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"User with email {signup_data.email} already exists"
                )
            
            # Hash password
            hashed_password = self.password_handler.hash_password(signup_data.password)
            
            # Create user in database
            user_create = UserCreateModel(
                email=signup_data.email,
                password=signup_data.password  # This won't be stored
            )
            
            user_model = await self.db_service.create_user(user_create, hashed_password)
            
            # Generate JWT token
            token_data = self.jwt_handler.generate_token(
                user_id=user_model.id,
                email=user_model.email
            )
            
            # Create response models
            token_response = TokenResponse(
                access_token=token_data["access_token"],
                token_type=token_data["token_type"],
                expires_in=token_data["expires_in"],
                expires_at=token_data["expires_at"]
            )
            
            user_response = UserResponse(
                id=user_model.id,
                email=user_model.email,
                created_at=user_model.created_at,
                updated_at=user_model.updated_at,
                is_active=user_model.is_active,
                login_count=user_model.login_count,
                last_login=user_model.last_login
            )
            
            logger.info(
                f"User registration successful: {signup_data.email}",
                extra={
                    "user_id": user_model.id,
                    "email": user_model.email,
                    "password_strength": password_validation["strength"],
                }
            )
            
            return {
                "token": token_response,
                "user": user_response,
                "message": "User registration successful"
            }
            
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
            
        except Exception as e:
            logger.error(
                f"User registration failed: {signup_data.email} - {str(e)}",
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
    
    async def authenticate_user(self, login_data: LoginRequest) -> Dict[str, Any]:
        """
        Authenticate user and generate JWT token.
        
        Args:
            login_data: User login credentials
            
        Returns:
            Dictionary with token and user information
            
        Raises:
            HTTPException: If authentication fails
        """
        try:
            logger.info(
                f"User authentication attempt: {login_data.email}",
                extra={"email": login_data.email}
            )
            
            # Get user from database
            user_model = await self.db_service.get_user_by_email(login_data.email)
            
            if not user_model:
                logger.warning(
                    f"Authentication failed - user not found: {login_data.email}",
                    extra={"email": login_data.email}
                )
                
                # Use generic error message for security
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password"
                )
            
            # Check if user is active
            if not user_model.is_active:
                logger.warning(
                    f"Authentication failed - inactive user: {login_data.email}",
                    extra={
                        "email": login_data.email,
                        "user_id": user_model.id,
                    }
                )
                
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Account is inactive"
                )
            
            # Verify password
            if not self.password_handler.verify_password(
                login_data.password, 
                user_model.hashed_password
            ):
                logger.warning(
                    f"Authentication failed - invalid password: {login_data.email}",
                    extra={
                        "email": login_data.email,
                        "user_id": user_model.id,
                    }
                )
                
                # Use generic error message for security
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password"
                )
            
            # Update login information
            await self.db_service.update_user_login_info(user_model.id)
            
            # Generate JWT token
            token_data = self.jwt_handler.generate_token(
                user_id=user_model.id,
                email=user_model.email,
                additional_claims={
                    "login_count": user_model.login_count + 1,
                }
            )
            
            # Create response models
            token_response = TokenResponse(
                access_token=token_data["access_token"],
                token_type=token_data["token_type"],
                expires_in=token_data["expires_in"],
                expires_at=token_data["expires_at"]
            )
            
            # Update user model with new login info for response
            user_model.login_count += 1
            user_model.last_login = datetime.utcnow()
            user_model.updated_at = datetime.utcnow()
            
            user_response = UserResponse(
                id=user_model.id,
                email=user_model.email,
                created_at=user_model.created_at,
                updated_at=user_model.updated_at,
                is_active=user_model.is_active,
                login_count=user_model.login_count,
                last_login=user_model.last_login
            )
            
            logger.info(
                f"User authentication successful: {login_data.email}",
                extra={
                    "user_id": user_model.id,
                    "email": user_model.email,
                    "login_count": user_model.login_count,
                }
            )
            
            return {
                "token": token_response,
                "user": user_response,
                "message": "Login successful"
            }
            
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
            
        except Exception as e:
            logger.error(
                f"User authentication failed: {login_data.email} - {str(e)}",
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
    
    async def verify_token(self, token: str) -> Optional[UserModel]:
        """
        Verify JWT token and return user information.
        
        Args:
            token: JWT token string
            
        Returns:
            User model if token is valid, None otherwise
        """
        try:
            # Verify token
            payload = self.jwt_handler.verify_token(token)
            
            if not payload:
                logger.debug("Token verification failed - invalid token")
                return None
            
            user_id = payload.get("sub")
            if not user_id:
                logger.warning(
                    "Token verification failed - missing user ID",
                    extra={"payload": payload}
                )
                return None
            
            # Get user from database
            user_model = await self.db_service.get_user_by_id(user_id)
            
            if not user_model:
                logger.warning(
                    f"Token verification failed - user not found: {user_id}",
                    extra={"user_id": user_id}
                )
                return None
            
            if not user_model.is_active:
                logger.warning(
                    f"Token verification failed - inactive user: {user_id}",
                    extra={
                        "user_id": user_id,
                        "email": user_model.email,
                    }
                )
                return None
            
            logger.debug(
                f"Token verification successful: {user_model.email}",
                extra={
                    "user_id": user_id,
                    "email": user_model.email,
                }
            )
            
            return user_model
            
        except Exception as e:
            logger.error(
                f"Token verification error: {str(e)}",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
            )
            return None
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform authentication service health check.
        
        Returns:
            Health check results
        """
        try:
            # Check database connectivity
            db_health = await self.db_service.health_check()
            
            # Test password hashing
            test_hash = self.password_handler.hash_password("test123")
            hash_verify = self.password_handler.verify_password("test123", test_hash)
            
            # Test JWT operations
            test_token = self.jwt_handler.generate_token("test_user", "test@example.com")
            token_verify = self.jwt_handler.verify_token(test_token["access_token"])
            
            auth_status = "healthy" if (
                db_health.get("status") == "healthy" and
                hash_verify and
                token_verify is not None
            ) else "degraded"
            
            return {
                "status": auth_status,
                "database": db_health,
                "password_hashing": "healthy" if hash_verify else "unhealthy",
                "jwt_operations": "healthy" if token_verify else "unhealthy",
            }
            
        except Exception as e:
            logger.error(
                f"Authentication service health check failed: {str(e)}",
                extra={"error": str(e)}
            )
            return {
                "status": "unhealthy",
                "error": str(e),
            }


# Global authentication service instance
_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    """
    Get the global authentication service instance.
    Uses singleton pattern for consistency.
    
    Returns:
        AuthService instance
    """
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service 
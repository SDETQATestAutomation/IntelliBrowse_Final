"""
JWT token handler for authentication system.
Provides JWT token generation, validation, and parsing functionality.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union
from jose import jwt, JWTError
from pydantic import ValidationError

from ...config.env import get_settings
from ...config.logging import get_logger

logger = get_logger(__name__)


class JWTHandler:
    """
    JWT token handler for authentication operations.
    
    Handles JWT token generation, validation, and parsing with proper
    error handling and security considerations.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.secret_key = self.settings.jwt_secret_key
        self.algorithm = self.settings.jwt_algorithm
        self.expiry_minutes = self.settings.jwt_expiry_minutes
    
    def generate_token(
        self, 
        user_id: str, 
        email: str,
        additional_claims: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate JWT access token for authenticated user.
        
        Args:
            user_id: User unique identifier
            email: User email address
            additional_claims: Optional additional JWT claims
            
        Returns:
            Dictionary containing token and metadata
            
        Raises:
            Exception: If token generation fails
        """
        try:
            # Calculate expiry times
            now = datetime.utcnow()
            expires_delta = timedelta(minutes=self.expiry_minutes)
            expires_at = now + expires_delta
            
            # Prepare JWT payload
            payload = {
                "sub": user_id,  # Subject (user ID)
                "email": email,
                "iat": now,  # Issued at
                "exp": expires_at,  # Expires at
                "type": "access",  # Token type
            }
            
            # Add additional claims if provided
            if additional_claims:
                payload.update(additional_claims)
            
            # Generate token
            access_token = jwt.encode(
                payload, 
                self.secret_key, 
                algorithm=self.algorithm
            )
            
            logger.info(
                f"JWT token generated for user {email}",
                extra={
                    "user_id": user_id,
                    "user_email": email,
                    "expires_at": expires_at.isoformat(),
                    "algorithm": self.algorithm,
                }
            )
            
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": int(expires_delta.total_seconds()),
                "expires_at": expires_at,
                "user_id": user_id,
                "email": email,
            }
            
        except Exception as e:
            logger.error(
                f"Failed to generate JWT token for user {email}: {str(e)}",
                extra={
                    "user_id": user_id,
                    "user_email": email,
                    "error": str(e),
                }
            )
            raise Exception(f"Token generation failed: {str(e)}")
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify and decode JWT token.
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded token payload if valid, None if invalid
        """
        try:
            # Remove 'Bearer ' prefix if present
            if token.startswith("Bearer "):
                token = token[7:]
            
            # Decode and verify token
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            
            # Validate required claims
            required_claims = ["sub", "email", "exp", "iat"]
            for claim in required_claims:
                if claim not in payload:
                    logger.warning(
                        f"JWT token missing required claim: {claim}",
                        extra={"missing_claim": claim}
                    )
                    return None
            
            # Check if token is expired (additional check)
            exp_timestamp = payload.get("exp")
            if exp_timestamp and datetime.utcfromtimestamp(exp_timestamp) < datetime.utcnow():
                logger.warning(
                    "JWT token is expired",
                    extra={
                        "user_id": payload.get("sub"),
                        "expired_at": datetime.utcfromtimestamp(exp_timestamp).isoformat(),
                    }
                )
                return None
            
            logger.debug(
                f"JWT token verified for user {payload.get('email')}",
                extra={
                    "user_id": payload.get("sub"),
                    "user_email": payload.get("email"),
                }
            )
            
            return payload
            
        except JWTError as e:
            logger.warning(
                f"JWT token verification failed: {str(e)}",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
            )
            return None
        except Exception as e:
            logger.error(
                f"Unexpected error during JWT token verification: {str(e)}",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
            )
            return None
    
    def extract_user_id(self, token: str) -> Optional[str]:
        """
        Extract user ID from JWT token.
        
        Args:
            token: JWT token string
            
        Returns:
            User ID if token is valid, None otherwise
        """
        payload = self.verify_token(token)
        return payload.get("sub") if payload else None
    
    def extract_user_email(self, token: str) -> Optional[str]:
        """
        Extract user email from JWT token.
        
        Args:
            token: JWT token string
            
        Returns:
            User email if token is valid, None otherwise
        """
        payload = self.verify_token(token)
        return payload.get("email") if payload else None
    
    def get_token_expiry(self, token: str) -> Optional[datetime]:
        """
        Get token expiry datetime from JWT token.
        
        Args:
            token: JWT token string
            
        Returns:
            Token expiry datetime if valid, None otherwise
        """
        payload = self.verify_token(token)
        if not payload:
            return None
        
        exp_timestamp = payload.get("exp")
        if exp_timestamp:
            return datetime.utcfromtimestamp(exp_timestamp)
        
        return None
    
    def is_token_expired(self, token: str) -> bool:
        """
        Check if JWT token is expired.
        
        Args:
            token: JWT token string
            
        Returns:
            True if token is expired or invalid, False otherwise
        """
        expiry = self.get_token_expiry(token)
        if not expiry:
            return True  # Invalid token is considered expired
        
        return expiry < datetime.utcnow()
    
    def get_remaining_time(self, token: str) -> Optional[timedelta]:
        """
        Get remaining time before token expires.
        
        Args:
            token: JWT token string
            
        Returns:
            Remaining time as timedelta if valid, None otherwise
        """
        expiry = self.get_token_expiry(token)
        if not expiry:
            return None
        
        remaining = expiry - datetime.utcnow()
        return remaining if remaining.total_seconds() > 0 else timedelta(0)
    
    def refresh_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Refresh JWT token (generate new token with same claims).
        
        Args:
            token: Current JWT token string
            
        Returns:
            New token data if successful, None otherwise
        """
        payload = self.verify_token(token)
        if not payload:
            return None
        
        user_id = payload.get("sub")
        email = payload.get("email")
        
        if not user_id or not email:
            logger.warning(
                "Cannot refresh token: missing user information in payload",
                extra={"payload": payload}
            )
            return None
        
        # Generate new token with same user information
        return self.generate_token(user_id, email)
    
    def validate_token_format(self, token: str) -> bool:
        """
        Validate JWT token format without full verification.
        
        Args:
            token: JWT token string
            
        Returns:
            True if format is valid (3 parts separated by dots)
        """
        if not token or not isinstance(token, str):
            return False
        
        # Remove 'Bearer ' prefix if present
        if token.startswith("Bearer "):
            token = token[7:]
        
        # JWT should have 3 parts separated by dots
        parts = token.split(".")
        return len(parts) == 3 and all(part for part in parts)


# Global JWT handler instance
_jwt_handler: Optional[JWTHandler] = None


def get_jwt_handler() -> JWTHandler:
    """
    Get the global JWT handler instance.
    Uses singleton pattern for consistency.
    
    Returns:
        JWTHandler instance
    """
    global _jwt_handler
    if _jwt_handler is None:
        _jwt_handler = JWTHandler()
    return _jwt_handler 
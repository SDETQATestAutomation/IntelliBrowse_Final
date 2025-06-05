"""
Authentication dependencies for route protection.
Provides JWT token validation and user authentication dependencies.
"""

from .jwt_bearer import (
    JWTBearer,
    OptionalJWTBearer,
    jwt_bearer,
    optional_jwt_bearer,
    get_current_user,
    get_current_user_optional,
    get_current_active_user,
    get_admin_user,
)

__all__ = [
    "JWTBearer",
    "OptionalJWTBearer",
    "jwt_bearer",
    "optional_jwt_bearer",
    "get_current_user",
    "get_current_user_optional",
    "get_current_active_user",
    "get_admin_user",
] 
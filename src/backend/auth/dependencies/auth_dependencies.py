"""
Authentication dependencies for FastAPI routes.

Re-exports authentication functions for consistent import paths across the application.
"""

from .jwt_bearer import (
    get_current_user,
    get_current_user_optional,
    get_current_active_user,
    get_admin_user,
    jwt_bearer,
    optional_jwt_bearer
)

__all__ = [
    "get_current_user",
    "get_current_user_optional", 
    "get_current_active_user",
    "get_admin_user",
    "jwt_bearer",
    "optional_jwt_bearer"
] 
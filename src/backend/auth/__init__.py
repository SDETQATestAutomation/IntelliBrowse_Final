"""
Authentication module for IntelliBrowse backend.

This module provides JWT-based authentication with secure password hashing,
user registration, login functionality, and route protection middleware.

Components:
- routes: FastAPI router with auth endpoints
- controllers: Request handling and validation
- services: Authentication business logic and database operations
- schemas: Pydantic models for requests/responses
- models: MongoDB user document models
- utils: JWT token handling and password utilities
- dependencies: Middleware for route protection
"""

from .routes.auth_routes import router as auth_router
from .dependencies.jwt_bearer import (
    get_current_user,
    get_current_user_optional,
    get_current_active_user,
    get_admin_user,
)
from .services.auth_service import get_auth_service
from .services.database_service import get_database_service

__all__ = [
    "auth_router",
    "get_current_user",
    "get_current_user_optional", 
    "get_current_active_user",
    "get_admin_user",
    "get_auth_service",
    "get_database_service",
] 
"""
Authentication routes for FastAPI endpoints.
Defines authentication API endpoints with proper documentation and validation.
"""

from .auth_routes import router as auth_router

__all__ = ["auth_router"] 
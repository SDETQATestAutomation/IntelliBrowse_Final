"""
Authentication controllers for request handling and validation.
Provides HTTP request processing for authentication endpoints.
"""

from .auth_controller import AuthController, get_auth_controller

__all__ = [
    "AuthController",
    "get_auth_controller",
] 
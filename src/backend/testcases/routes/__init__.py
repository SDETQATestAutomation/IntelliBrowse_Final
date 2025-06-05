"""
Test Case Routes Package

FastAPI route definitions for the Test Case Management system.
Implements RESTful API endpoints with JWT authentication, OpenAPI documentation,
and comprehensive request/response handling.
"""

from .test_case_routes import router

__all__ = [
    "router",
] 
"""
Scheduled Task Runner Engine - Routes Package

Implements FastAPI HTTP endpoints for the scheduler module with comprehensive
OpenAPI documentation, JWT authentication, and proper HTTP status codes.

Key Routes:
- scheduler_routes: Main API router for scheduler endpoints
- Authentication required for all endpoints
- Full OpenAPI documentation with examples
"""

from .scheduler_routes import router

__all__ = [
    "router"
] 
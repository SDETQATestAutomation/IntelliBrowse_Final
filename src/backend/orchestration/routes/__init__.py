"""
Orchestration Routes Module

This module provides FastAPI route definitions for the orchestration engine,
exposing HTTP endpoints that integrate with the OrchestrationController.
Routes follow RESTful conventions and IntelliBrowse API standards.

Routes:
- POST /orchestration/job - Submit new orchestration job
- GET /orchestration/job/{job_id} - Get job status and details  
- DELETE /orchestration/job/{job_id} - Cancel running job
- GET /orchestration/jobs - List jobs with filtering and pagination
- GET /orchestration/health - Service health check

Features:
- FastAPI router with proper prefix and tags
- JWT authentication on all endpoints
- Comprehensive OpenAPI documentation
- Dependency injection for controller integration
- Structured error handling and logging
"""

from .orchestration_routes import router

__all__ = [
    "router"
] 
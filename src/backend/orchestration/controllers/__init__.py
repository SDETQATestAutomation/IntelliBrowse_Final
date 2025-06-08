"""
Orchestration Controllers Module

This module provides HTTP controllers for the orchestration engine, implementing
the API boundary layer for external system interactions. Controllers handle
request validation, authentication, and routing to appropriate service layers.

Controllers:
- OrchestrationController: Main orchestration job management
- JobCancellationError: Exception for job cancellation failures
- OrchestrationControllerFactory: Dependency injection factory

Features:
- JWT-based authentication enforcement
- Comprehensive request/response validation
- Structured error handling with FastAPI integration
- Audit logging with correlation tracking
- SRP compliance with service layer delegation
"""

from .orchestration_controller import (
    OrchestrationController,
    JobCancellationError,
    OrchestrationControllerFactory
)

__all__ = [
    "OrchestrationController",
    "JobCancellationError", 
    "OrchestrationControllerFactory"
] 
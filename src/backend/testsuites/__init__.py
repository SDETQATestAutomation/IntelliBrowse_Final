"""
Test Suite Management Module

This module provides comprehensive test suite management capabilities including:
- Suite-level control (title, tags, priority, status)
- Per-suite test item configuration (order, skip flags, custom tags, notes)
- Bulk operations with partial success handling
- Performance monitoring and observability
- Optional enhancements (soft deletion, tag normalization, optimistic concurrency)

Module Architecture:
- routes/: FastAPI route definitions with OpenAPI documentation
- controllers/: HTTP request/response handling layer
- services/: Business logic and database operations
- schemas/: Pydantic request/response models
- models/: MongoDB document models and database integration

Follows Clean Architecture principles with clear separation of concerns.
"""

__version__ = "1.0.0" 
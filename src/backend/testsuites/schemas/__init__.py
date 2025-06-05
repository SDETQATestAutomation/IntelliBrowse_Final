"""
Test Suite Schemas Package

Pydantic request and response models for test suite management with:
- Request validation and data transformation
- Response models with field inclusion control
- OpenAPI documentation and examples
- Multi-test type integration support
- Base models for DRY reuse patterns

Module Architecture:
- test_suite_requests.py: Request validation models
- test_suite_responses.py: Response formatting models  
- Base models and enums for reusable components

Follows established patterns from auth and test item schemas.
"""

__version__ = "1.0.0" 
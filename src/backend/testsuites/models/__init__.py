"""
Test Suite Models Package

Exports MongoDB models, validation classes, and utilities for test suite management.
Provides centralized access to all model-related components with proper typing.
"""

from .test_suite_model import (
    # Base model for DRY principles
    BaseMongoModel,
    
    # Main document model
    TestSuiteModel,
    
    # Embedded models
    SuiteItemConfig,
    
    # Enums
    TestSuiteStatus,
    TestSuitePriority,
    
    # Operations and utilities
    TestSuiteModelOperations,
)

from .indexes import (
    # Index management
    TestSuiteIndexManager,
    
    # Convenience functions
    ensure_test_suite_indexes,
    validate_test_suite_indexes,
)

__all__ = [
    # Base model
    "BaseMongoModel",
    
    # Main model
    "TestSuiteModel",
    
    # Embedded models
    "SuiteItemConfig",
    
    # Enums
    "TestSuiteStatus", 
    "TestSuitePriority",
    
    # Operations
    "TestSuiteModelOperations",
    
    # Index management
    "TestSuiteIndexManager",
    "ensure_test_suite_indexes",
    "validate_test_suite_indexes",
] 
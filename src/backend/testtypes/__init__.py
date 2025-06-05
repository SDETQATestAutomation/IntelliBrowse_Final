"""
Test Types Package

Multi-test type support for IntelliBrowse using Factory Pattern with Dynamic Type Loading.
Supports GENERIC, BDD, and MANUAL test types with type-specific validation and data models.
"""

from .enums import TestType
from .models.base import TestTypeData, BDDTestData, ManualTestData, GenericTestData, BDDBlock
from .validators.factory import TestTypeValidatorFactory
from .validators.base import ValidationError

__version__ = "1.0.0"

# Public API exports
__all__ = [
    # Enums
    "TestType",
    
    # Data Models
    "TestTypeData",
    "BDDTestData", 
    "ManualTestData",
    "GenericTestData",
    "BDDBlock",
    
    # Validation
    "TestTypeValidatorFactory",
    "ValidationError",
]

# Factory instance for convenience
validator_factory = TestTypeValidatorFactory() 
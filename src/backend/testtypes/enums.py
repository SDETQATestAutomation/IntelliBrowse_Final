"""
Test Type Enumerations

Defines the supported test types for IntelliBrowse multi-test type system.
"""

from enum import Enum


class TestType(str, Enum):
    """
    Test type enumeration for multi-test type support.
    
    Each test type has specific characteristics:
    - GENERIC: AI/rule-based automated tests optimized for automation
    - BDD: Behavior-driven tests following Gherkin syntax (Feature/Scenario/Given-When-Then)
    - MANUAL: Human-authored test cases with documentation and manual execution metadata
    """
    
    GENERIC = "generic"
    BDD = "bdd"
    MANUAL = "manual"
    
    @classmethod
    def get_default(cls) -> "TestType":
        """Return the default test type for backward compatibility."""
        return cls.GENERIC
    
    @classmethod
    def get_all_types(cls) -> list["TestType"]:
        """Return all available test types."""
        return [cls.GENERIC, cls.BDD, cls.MANUAL]
    
    def __str__(self) -> str:
        """String representation of the test type."""
        return self.value 
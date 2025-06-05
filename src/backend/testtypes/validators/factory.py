"""
Test Type Validator Factory

Central factory for managing and delegating validation to type-specific validators.
Implements caching for performance optimization and provides unified validation interface.
"""

from typing import Dict, Any, Type
from .base import BaseValidator, ValidationError
from .bdd_validator import BDDValidator
from .manual_validator import ManualValidator
from .generic_validator import GenericValidator
from ..enums import TestType
from ...config.logging import get_logger

logger = get_logger(__name__)


class TestTypeValidatorFactory:
    """
    Factory class for managing test type validators.
    
    Provides centralized access to type-specific validators with caching
    for performance optimization. Delegates validation to appropriate
    validators based on test type.
    """
    
    # Registry mapping test types to validator classes
    _validators = {
        TestType.GENERIC: GenericValidator,
        TestType.BDD: BDDValidator,
        TestType.MANUAL: ManualValidator,
    }
    
    # Cache for validator instances (performance optimization)
    _validator_cache: Dict[TestType, BaseValidator] = {}
    
    @classmethod
    def get_validator(cls, test_type: TestType) -> BaseValidator:
        """
        Get validator instance for the specified test type.
        
        Uses caching to avoid repeated instantiation for performance.
        
        Args:
            test_type: Test type to get validator for
            
        Returns:
            BaseValidator instance for the test type
            
        Raises:
            ValueError: If test type is not supported
        """
        if test_type not in cls._validators:
            available_types = ", ".join([t.value for t in cls._validators.keys()])
            raise ValueError(
                f"No validator found for test type: {test_type}. "
                f"Available types: {available_types}"
            )
        
        # Check cache first
        if test_type not in cls._validator_cache:
            validator_class = cls._validators[test_type]
            cls._validator_cache[test_type] = validator_class()
            logger.debug(f"Created new validator instance for test type: {test_type}")
        
        return cls._validator_cache[test_type]
    
    @classmethod
    def validate_type_data(cls, test_type: TestType, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate type-specific data using the appropriate validator.
        
        Args:
            test_type: Test type for validation
            data: Raw type-specific data to validate
            
        Returns:
            Validated and cleaned data dictionary
            
        Raises:
            ValueError: If test type is not supported
            ValidationError: If validation fails
        """
        try:
            # Get appropriate validator
            validator = cls.get_validator(test_type)
            
            # Validate data
            validated_data = validator.validate(data)
            
            logger.info(
                f"Successfully validated {test_type} test data",
                extra={
                    "test_type": test_type.value if hasattr(test_type, 'value') else str(test_type),
                    "data_size": len(str(data)),
                    "validator": validator.__class__.__name__
                }
            )
            
            return validated_data
            
        except ValidationError as e:
            logger.error(
                f"Validation failed for {test_type} test data: {e.message}",
                extra={
                    "test_type": test_type.value if hasattr(test_type, 'value') else str(test_type),
                    "error": e.message,
                    "validation_errors": e.errors
                }
            )
            raise
        except Exception as e:
            error_msg = f"Unexpected error during {test_type} validation: {str(e)}"
            logger.error(error_msg, extra={
                "test_type": test_type.value if hasattr(test_type, 'value') else str(test_type), 
                "error": str(e)
            })
            raise ValidationError(error_msg)
    
    @classmethod
    def get_schema(cls, test_type: TestType) -> Type:
        """
        Get Pydantic schema class for the specified test type.
        
        Args:
            test_type: Test type to get schema for
            
        Returns:
            Pydantic BaseModel class for the test type
            
        Raises:
            ValueError: If test type is not supported
        """
        validator = cls.get_validator(test_type)
        return validator.get_schema()
    
    @classmethod
    def clear_cache(cls) -> None:
        """
        Clear the validator cache.
        
        Useful for testing or when validators need to be refreshed.
        """
        cls._validator_cache.clear()
        logger.debug("Cleared validator cache")
    
    @classmethod
    def get_supported_types(cls) -> list[TestType]:
        """
        Get list of supported test types.
        
        Returns:
            List of supported TestType enums
        """
        return list(cls._validators.keys())
    
    @classmethod
    def is_type_supported(cls, test_type: TestType) -> bool:
        """
        Check if a test type is supported.
        
        Args:
            test_type: Test type to check
            
        Returns:
            True if test type is supported, False otherwise
        """
        return test_type in cls._validators
    
    @classmethod
    def get_cache_info(cls) -> Dict[str, Any]:
        """
        Get information about the validator cache.
        
        Returns:
            Dictionary with cache statistics
        """
        return {
            "cached_validators": len(cls._validator_cache),
            "supported_types": len(cls._validators),
            "cached_types": [t.value for t in cls._validator_cache.keys()],
            "total_types": [t.value for t in cls._validators.keys()]
        } 
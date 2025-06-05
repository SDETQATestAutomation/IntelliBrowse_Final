"""
Base Validator Abstract Class

Defines the interface for all type-specific validators in the multi-test type system.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Type
from pydantic import BaseModel

from ...config.logging import get_logger

logger = get_logger(__name__)


class ValidationError(Exception):
    """Custom exception for type-specific validation errors."""
    
    def __init__(self, message: str, errors: Dict[str, Any] = None):
        self.message = message
        self.errors = errors or {}
        super().__init__(self.message)


class BaseValidator(ABC):
    """
    Abstract base class for all test type validators.
    
    Each test type (GENERIC, BDD, MANUAL) must implement a validator
    that extends this base class and provides type-specific validation logic.
    """
    
    def __init__(self):
        """Initialize the validator."""
        self.logger = logger
    
    @abstractmethod
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and return cleaned type-specific data.
        
        Args:
            data: Raw type-specific data dictionary
            
        Returns:
            Validated and cleaned data dictionary
            
        Raises:
            ValidationError: If validation fails
        """
        pass
    
    @abstractmethod
    def get_schema(self) -> Type[BaseModel]:
        """
        Return the Pydantic schema class for this test type.
        
        Returns:
            Pydantic BaseModel class for type validation
        """
        pass
    
    def _validate_with_schema(self, data: Dict[str, Any], schema_class: Type[BaseModel]) -> Dict[str, Any]:
        """
        Common validation logic using Pydantic schema.
        
        Args:
            data: Data to validate
            schema_class: Pydantic model class for validation
            
        Returns:
            Validated data dictionary
            
        Raises:
            ValidationError: If schema validation fails
        """
        try:
            # Validate using Pydantic schema
            validated_model = schema_class(**data)
            
            # Return as dictionary for consistent interface
            return validated_model.dict()
            
        except Exception as e:
            error_msg = f"Schema validation failed: {str(e)}"
            self.logger.error(error_msg, extra={"data": data, "schema": schema_class.__name__})
            
            # Extract Pydantic validation errors if available
            errors = {}
            if hasattr(e, 'errors'):
                errors = {str(err['loc']): err['msg'] for err in e.errors()}
            
            raise ValidationError(error_msg, errors)
    
    def _log_validation_success(self, test_type: str, data_size: int) -> None:
        """Log successful validation."""
        self.logger.info(
            f"Successfully validated {test_type} test data",
            extra={"test_type": test_type, "data_size": data_size}
        )
    
    def _log_validation_failure(self, test_type: str, error: str) -> None:
        """Log validation failure."""
        self.logger.error(
            f"Validation failed for {test_type} test data: {error}",
            extra={"test_type": test_type, "error": error}
        ) 
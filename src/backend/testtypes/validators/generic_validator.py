"""
Generic Test Type Validator

Implements validation logic for Generic (AI/Rule-based) test data including
AI confidence scores, natural language steps, and selector hints.
"""

from typing import Dict, Any, List, Type
from pydantic import BaseModel

from .base import BaseValidator, ValidationError
from ..models.base import GenericTestData
from ..enums import TestType


class GenericValidator(BaseValidator):
    """
    Validator for Generic test type data.
    
    Validates generic-specific fields including AI confidence scores,
    natural language steps, selector hints, and automation metadata.
    """
    
    # Valid automation priority levels
    VALID_AUTOMATION_PRIORITIES = {"high", "medium", "low"}
    
    # Maximum limits
    MAX_STEPS_COUNT = 50
    MAX_SELECTOR_HINTS_COUNT = 30
    MAX_STEP_LENGTH = 500
    
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate Generic test data.
        
        Args:
            data: Raw Generic test data
            
        Returns:
            Validated Generic test data
            
        Raises:
            ValidationError: If Generic validation fails
        """
        try:
            # First validate with Pydantic schema
            validated_data = self._validate_with_schema(data, GenericTestData)
            
            # Additional Generic-specific validations
            self._validate_ai_confidence_score(validated_data.get("ai_confidence_score"))
            self._validate_natural_language_steps(validated_data.get("natural_language_steps", []))
            self._validate_selector_hints(validated_data.get("selector_hints", {}))
            self._validate_automation_priority(validated_data.get("automation_priority"))
            self._validate_complexity_score(validated_data.get("complexity_score"))
            
            self._log_validation_success("GENERIC", len(str(validated_data)))
            return validated_data
            
        except ValidationError:
            raise
        except Exception as e:
            error_msg = f"Generic validation failed: {str(e)}"
            self._log_validation_failure("GENERIC", error_msg)
            raise ValidationError(error_msg)
    
    def get_schema(self) -> Type[BaseModel]:
        """Return the Generic test data schema."""
        return GenericTestData
    
    def _validate_ai_confidence_score(self, ai_confidence_score: float = None) -> None:
        """
        Validate AI confidence score.
        
        Args:
            ai_confidence_score: AI confidence score to validate
            
        Raises:
            ValidationError: If AI confidence score is invalid
        """
        if ai_confidence_score is not None:
            if not 0.0 <= ai_confidence_score <= 1.0:
                raise ValidationError("AI confidence score must be between 0.0 and 1.0")
            
            # Warn about very low confidence scores
            if ai_confidence_score < 0.3:
                self.logger.warning(
                    f"Generic test has very low AI confidence score: {ai_confidence_score}",
                    extra={"ai_confidence_score": ai_confidence_score}
                )
    
    def _validate_natural_language_steps(self, natural_language_steps: List[str]) -> None:
        """
        Validate natural language steps.
        
        Args:
            natural_language_steps: List of natural language steps to validate
            
        Raises:
            ValidationError: If natural language steps are invalid
        """
        if len(natural_language_steps) > self.MAX_STEPS_COUNT:
            raise ValidationError(f"Cannot have more than {self.MAX_STEPS_COUNT} natural language steps")
        
        for i, step in enumerate(natural_language_steps):
            if not step or not step.strip():
                raise ValidationError(f"Natural language step at position {i} cannot be empty")
            
            if len(step) > self.MAX_STEP_LENGTH:
                raise ValidationError(f"Natural language step at position {i} cannot exceed {self.MAX_STEP_LENGTH} characters")
            
            # Check for meaningful content
            if not any(c.isalnum() for c in step):
                raise ValidationError(f"Natural language step at position {i} must contain meaningful content")
            
            # Check for minimum word count
            words = step.strip().split()
            if len(words) < 2:
                raise ValidationError(f"Natural language step at position {i} should contain at least 2 words")
        
        # Check for duplicate steps
        unique_steps = set(step.strip().lower() for step in natural_language_steps)
        if len(unique_steps) != len(natural_language_steps):
            raise ValidationError("Duplicate natural language steps are not allowed")
    
    def _validate_selector_hints(self, selector_hints: Dict[str, str]) -> None:
        """
        Validate selector hints.
        
        Args:
            selector_hints: Dictionary of selector hints to validate
            
        Raises:
            ValidationError: If selector hints are invalid
        """
        if len(selector_hints) > self.MAX_SELECTOR_HINTS_COUNT:
            raise ValidationError(f"Cannot have more than {self.MAX_SELECTOR_HINTS_COUNT} selector hints")
        
        for element_name, selector in selector_hints.items():
            # Validate element name
            if not element_name or not element_name.strip():
                raise ValidationError("Selector hint element name cannot be empty")
            
            if len(element_name) > 100:
                raise ValidationError(f"Selector hint element name '{element_name}' cannot exceed 100 characters")
            
            # Element name should be valid identifier-like
            if not all(c.isalnum() or c in ['_', '-'] for c in element_name):
                raise ValidationError(f"Selector hint element name '{element_name}' should contain only alphanumeric, underscore, or hyphen characters")
            
            # Validate selector
            if not selector or not selector.strip():
                raise ValidationError(f"Selector hint for '{element_name}' cannot be empty")
            
            if len(selector) > 500:
                raise ValidationError(f"Selector hint for '{element_name}' cannot exceed 500 characters")
            
            # Basic CSS selector validation
            self._validate_css_selector_syntax(element_name, selector.strip())
        
        # Check for duplicate selectors
        unique_selectors = set(selector.strip().lower() for selector in selector_hints.values())
        if len(unique_selectors) != len(selector_hints):
            raise ValidationError("Duplicate selector values are not allowed")
    
    def _validate_css_selector_syntax(self, element_name: str, selector: str) -> None:
        """
        Validate CSS selector syntax.
        
        Args:
            element_name: Name of the element for error reporting
            selector: CSS selector to validate
            
        Raises:
            ValidationError: If CSS selector syntax is invalid
        """
        # Basic CSS selector validation
        invalid_chars = ['<', '>', '{', '}', '|', '\\']
        for char in invalid_chars:
            if char in selector:
                raise ValidationError(f"Selector hint for '{element_name}' contains invalid character: {char}")
        
        # Check for common selector patterns
        valid_patterns = [
            selector.startswith('#'),  # ID selector
            selector.startswith('.'),  # Class selector
            selector.startswith('['),  # Attribute selector
            any(tag in selector for tag in ['input', 'button', 'div', 'span', 'a', 'form']),  # Element selectors
            'data-testid' in selector,  # Data attribute
            'xpath=' in selector.lower(),  # XPath (though not CSS)
        ]
        
        if not any(valid_patterns):
            self.logger.warning(
                f"Selector hint for '{element_name}' may not be a valid CSS selector: {selector}",
                extra={"element_name": element_name, "selector": selector}
            )
    
    def _validate_automation_priority(self, automation_priority: str = None) -> None:
        """
        Validate automation priority.
        
        Args:
            automation_priority: Automation priority to validate
            
        Raises:
            ValidationError: If automation priority is invalid
        """
        if automation_priority is not None:
            if automation_priority.lower() not in self.VALID_AUTOMATION_PRIORITIES:
                raise ValidationError(
                    f"Invalid automation priority '{automation_priority}'. "
                    f"Valid options: {', '.join(self.VALID_AUTOMATION_PRIORITIES)}"
                )
    
    def _validate_complexity_score(self, complexity_score: float = None) -> None:
        """
        Validate complexity score.
        
        Args:
            complexity_score: Complexity score to validate
            
        Raises:
            ValidationError: If complexity score is invalid
        """
        if complexity_score is not None:
            if not 0.0 <= complexity_score <= 1.0:
                raise ValidationError("Complexity score must be between 0.0 and 1.0")
            
            # Warn about very high complexity scores
            if complexity_score > 0.8:
                self.logger.warning(
                    f"Generic test has very high complexity score: {complexity_score}",
                    extra={"complexity_score": complexity_score}
                ) 
"""
Manual Test Type Validator

Implements validation logic for Manual test data including manual notes,
expected outcomes, screenshots, and execution metadata.
"""

from typing import Dict, Any, List, Type
from pydantic import BaseModel
import re

from .base import BaseValidator, ValidationError
from ..models.base import ManualTestData
from ..enums import TestType


class ManualValidator(BaseValidator):
    """
    Validator for Manual test type data.
    
    Validates manual-specific fields including manual notes, expected outcomes,
    screenshot URLs, execution time estimates, and prerequisites.
    """
    
    # URL pattern for basic URL validation
    URL_PATTERN = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE
    )
    
    # Maximum limits
    MAX_NOTES_LENGTH = 5000
    MAX_OUTCOMES_LENGTH = 2000
    MAX_PREREQUISITES_COUNT = 20
    MAX_SCREENSHOT_COUNT = 10
    
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate Manual test data.
        
        Args:
            data: Raw Manual test data
            
        Returns:
            Validated Manual test data
            
        Raises:
            ValidationError: If Manual validation fails
        """
        try:
            # First validate with Pydantic schema
            validated_data = self._validate_with_schema(data, ManualTestData)
            
            # Additional Manual-specific validations
            self._validate_manual_notes(validated_data.get("manual_notes", ""))
            self._validate_expected_outcomes(validated_data.get("expected_outcomes", ""))
            self._validate_screenshot_urls(validated_data.get("screenshot_urls", []))
            self._validate_execution_time(validated_data.get("execution_time_estimate"))
            self._validate_prerequisites(validated_data.get("prerequisites", []))
            self._validate_test_data_requirements(validated_data.get("test_data_requirements"))
            
            self._log_validation_success("MANUAL", len(str(validated_data)))
            return validated_data
            
        except ValidationError:
            raise
        except Exception as e:
            error_msg = f"Manual validation failed: {str(e)}"
            self._log_validation_failure("MANUAL", error_msg)
            raise ValidationError(error_msg)
    
    def get_schema(self) -> Type[BaseModel]:
        """Return the Manual test data schema."""
        return ManualTestData
    
    def _validate_manual_notes(self, manual_notes: str) -> None:
        """
        Validate manual test notes.
        
        Args:
            manual_notes: Manual test notes to validate
            
        Raises:
            ValidationError: If manual notes are invalid
        """
        if not manual_notes or not manual_notes.strip():
            raise ValidationError("Manual notes cannot be empty")
        
        if len(manual_notes) > self.MAX_NOTES_LENGTH:
            raise ValidationError(f"Manual notes cannot exceed {self.MAX_NOTES_LENGTH} characters")
        
        # Check for meaningful content (not just whitespace/special characters)
        if not any(c.isalnum() for c in manual_notes):
            raise ValidationError("Manual notes must contain meaningful content")
        
        # Check for minimum content requirement
        words = manual_notes.strip().split()
        if len(words) < 3:
            raise ValidationError("Manual notes should contain at least 3 words for clarity")
    
    def _validate_expected_outcomes(self, expected_outcomes: str) -> None:
        """
        Validate expected outcomes.
        
        Args:
            expected_outcomes: Expected outcomes to validate
            
        Raises:
            ValidationError: If expected outcomes are invalid
        """
        if not expected_outcomes or not expected_outcomes.strip():
            raise ValidationError("Expected outcomes cannot be empty")
        
        if len(expected_outcomes) > self.MAX_OUTCOMES_LENGTH:
            raise ValidationError(f"Expected outcomes cannot exceed {self.MAX_OUTCOMES_LENGTH} characters")
        
        # Check for meaningful content
        if not any(c.isalnum() for c in expected_outcomes):
            raise ValidationError("Expected outcomes must contain meaningful content")
        
        # Check for minimum content requirement
        words = expected_outcomes.strip().split()
        if len(words) < 2:
            raise ValidationError("Expected outcomes should contain at least 2 words for clarity")
    
    def _validate_screenshot_urls(self, screenshot_urls: List[str]) -> None:
        """
        Validate screenshot URLs.
        
        Args:
            screenshot_urls: List of screenshot URLs to validate
            
        Raises:
            ValidationError: If screenshot URLs are invalid
        """
        if len(screenshot_urls) > self.MAX_SCREENSHOT_COUNT:
            raise ValidationError(f"Cannot have more than {self.MAX_SCREENSHOT_COUNT} screenshots")
        
        for i, url in enumerate(screenshot_urls):
            if not url or not url.strip():
                raise ValidationError(f"Screenshot URL at position {i} cannot be empty")
            
            # Basic URL format validation
            if not self.URL_PATTERN.match(url.strip()):
                raise ValidationError(f"Invalid URL format for screenshot at position {i}: {url}")
            
            # Check URL length
            if len(url) > 2000:
                raise ValidationError(f"Screenshot URL at position {i} is too long (max 2000 characters)")
        
        # Check for duplicate URLs
        unique_urls = set(url.strip().lower() for url in screenshot_urls)
        if len(unique_urls) != len(screenshot_urls):
            raise ValidationError("Duplicate screenshot URLs are not allowed")
    
    def _validate_execution_time(self, execution_time_estimate: int = None) -> None:
        """
        Validate execution time estimate.
        
        Args:
            execution_time_estimate: Execution time in minutes
            
        Raises:
            ValidationError: If execution time is invalid
        """
        if execution_time_estimate is not None:
            if execution_time_estimate < 1:
                raise ValidationError("Execution time estimate must be at least 1 minute")
            
            if execution_time_estimate > 480:  # 8 hours
                raise ValidationError("Execution time estimate cannot exceed 8 hours (480 minutes)")
            
            # Reasonable validation - warn about very long manual tests
            if execution_time_estimate > 240:  # 4 hours
                self.logger.warning(
                    f"Manual test has very long execution time: {execution_time_estimate} minutes",
                    extra={"execution_time": execution_time_estimate}
                )
    
    def _validate_prerequisites(self, prerequisites: List[str]) -> None:
        """
        Validate test prerequisites.
        
        Args:
            prerequisites: List of prerequisites to validate
            
        Raises:
            ValidationError: If prerequisites are invalid
        """
        if len(prerequisites) > self.MAX_PREREQUISITES_COUNT:
            raise ValidationError(f"Cannot have more than {self.MAX_PREREQUISITES_COUNT} prerequisites")
        
        for i, prerequisite in enumerate(prerequisites):
            if not prerequisite or not prerequisite.strip():
                raise ValidationError(f"Prerequisite at position {i} cannot be empty")
            
            if len(prerequisite) > 200:
                raise ValidationError(f"Prerequisite at position {i} cannot exceed 200 characters")
            
            # Check for meaningful content
            if not any(c.isalnum() for c in prerequisite):
                raise ValidationError(f"Prerequisite at position {i} must contain meaningful content")
        
        # Check for duplicate prerequisites
        unique_prereqs = set(prereq.strip().lower() for prereq in prerequisites)
        if len(unique_prereqs) != len(prerequisites):
            raise ValidationError("Duplicate prerequisites are not allowed")
    
    def _validate_test_data_requirements(self, test_data_requirements: str = None) -> None:
        """
        Validate test data requirements.
        
        Args:
            test_data_requirements: Test data requirements to validate
            
        Raises:
            ValidationError: If test data requirements are invalid
        """
        if test_data_requirements is not None:
            if not test_data_requirements.strip():
                raise ValidationError("Test data requirements cannot be empty if provided")
            
            if len(test_data_requirements) > 1000:
                raise ValidationError("Test data requirements cannot exceed 1000 characters")
            
            # Check for meaningful content
            if not any(c.isalnum() for c in test_data_requirements):
                raise ValidationError("Test data requirements must contain meaningful content") 
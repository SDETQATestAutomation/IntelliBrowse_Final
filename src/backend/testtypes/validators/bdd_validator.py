"""
BDD Test Type Validator

Implements validation logic for BDD (Behavior-Driven Development) test data
with Gherkin syntax validation and BDD block structure checking.
"""

from typing import Dict, Any, List, Type
from pydantic import BaseModel

from .base import BaseValidator, ValidationError
from ..models.base import BDDTestData, BDDBlock
from ..enums import TestType


class BDDValidator(BaseValidator):
    """
    Validator for BDD test type data.
    
    Validates BDD-specific fields including feature name, scenario name,
    BDD blocks with Gherkin syntax, and ensures proper Given/When/Then structure.
    """
    
    # Valid BDD block types according to Gherkin syntax
    VALID_BDD_BLOCK_TYPES = {"given", "when", "then", "and", "but", "background", "scenario"}
    
    # Required block types for a complete BDD scenario
    REQUIRED_BLOCK_TYPES = {"given", "when", "then"}
    
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate BDD test data.
        
        Args:
            data: Raw BDD test data
            
        Returns:
            Validated BDD test data
            
        Raises:
            ValidationError: If BDD validation fails
        """
        try:
            # First validate with Pydantic schema
            validated_data = self._validate_with_schema(data, BDDTestData)
            
            # Additional BDD-specific validations
            self._validate_bdd_blocks(validated_data.get("bdd_blocks", []))
            self._validate_gherkin_structure(validated_data.get("bdd_blocks", []))
            self._validate_feature_scenario_names(
                validated_data.get("feature_name", ""),
                validated_data.get("scenario_name", "")
            )
            
            self._log_validation_success("BDD", len(str(validated_data)))
            return validated_data
            
        except ValidationError:
            raise
        except Exception as e:
            error_msg = f"BDD validation failed: {str(e)}"
            self._log_validation_failure("BDD", error_msg)
            raise ValidationError(error_msg)
    
    def get_schema(self) -> Type[BaseModel]:
        """Return the BDD test data schema."""
        return BDDTestData
    
    def _validate_bdd_blocks(self, bdd_blocks: List[Dict[str, Any]]) -> None:
        """
        Validate BDD blocks structure and content.
        
        Args:
            bdd_blocks: List of BDD block dictionaries
            
        Raises:
            ValidationError: If BDD blocks are invalid
        """
        if not bdd_blocks:
            raise ValidationError("BDD test must have at least one BDD block")
        
        for i, block in enumerate(bdd_blocks):
            block_type = block.get("type", "").lower()
            content = block.get("content", "")
            
            # Validate block type
            if block_type not in self.VALID_BDD_BLOCK_TYPES:
                raise ValidationError(
                    f"Invalid BDD block type '{block.get('type')}' at position {i}. "
                    f"Valid types: {', '.join(self.VALID_BDD_BLOCK_TYPES)}"
                )
            
            # Validate block content
            if not content or not content.strip():
                raise ValidationError(f"BDD block at position {i} must have non-empty content")
            
            # Validate content length
            if len(content) > 500:
                raise ValidationError(f"BDD block content at position {i} exceeds 500 characters")
    
    def _validate_gherkin_structure(self, bdd_blocks: List[Dict[str, Any]]) -> None:
        """
        Validate Gherkin structure has proper Given/When/Then flow.
        
        Args:
            bdd_blocks: List of BDD block dictionaries
            
        Raises:
            ValidationError: If Gherkin structure is invalid
        """
        block_types = {block.get("type", "").lower() for block in bdd_blocks}
        
        # Check for required block types
        missing_types = self.REQUIRED_BLOCK_TYPES - block_types
        if missing_types:
            raise ValidationError(
                f"BDD scenario must contain {', '.join(self.REQUIRED_BLOCK_TYPES)} blocks. "
                f"Missing: {', '.join(missing_types)}"
            )
        
        # Validate logical flow (Given before When before Then)
        last_given_pos = -1
        last_when_pos = -1
        last_then_pos = -1
        
        for i, block in enumerate(bdd_blocks):
            block_type = block.get("type", "").lower()
            
            if block_type == "given":
                last_given_pos = i
            elif block_type == "when":
                last_when_pos = i
                if last_given_pos == -1:
                    raise ValidationError("'When' block found before any 'Given' block")
            elif block_type == "then":
                last_then_pos = i
                if last_when_pos == -1:
                    raise ValidationError("'Then' block found before any 'When' block")
        
        # Ensure logical ordering
        if last_given_pos > last_when_pos and last_when_pos != -1:
            raise ValidationError("'Given' blocks should generally come before 'When' blocks")
        
        if last_when_pos > last_then_pos and last_then_pos != -1:
            raise ValidationError("'When' blocks should generally come before 'Then' blocks")
    
    def _validate_feature_scenario_names(self, feature_name: str, scenario_name: str) -> None:
        """
        Validate feature and scenario names follow BDD conventions.
        
        Args:
            feature_name: Feature name to validate
            scenario_name: Scenario name to validate
            
        Raises:
            ValidationError: If names don't follow BDD conventions
        """
        # Feature name validation
        if not feature_name or not feature_name.strip():
            raise ValidationError("Feature name cannot be empty")
        
        if len(feature_name) > 200:
            raise ValidationError("Feature name cannot exceed 200 characters")
        
        # Scenario name validation
        if not scenario_name or not scenario_name.strip():
            raise ValidationError("Scenario name cannot be empty")
        
        if len(scenario_name) > 200:
            raise ValidationError("Scenario name cannot exceed 200 characters")
        
        # Check for reasonable naming patterns
        if feature_name.lower().strip() == scenario_name.lower().strip():
            raise ValidationError("Feature name and scenario name should be different")
        
        # Validate that names don't contain only special characters
        if not any(c.isalnum() for c in feature_name):
            raise ValidationError("Feature name must contain at least one alphanumeric character")
        
        if not any(c.isalnum() for c in scenario_name):
            raise ValidationError("Scenario name must contain at least one alphanumeric character") 
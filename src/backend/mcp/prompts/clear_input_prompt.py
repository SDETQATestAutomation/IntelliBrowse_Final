"""
Clear Input Field Prompt for IntelliBrowse MCP Server.

This module provides prompt templates for guiding LLM operations related to
clearing input fields and form elements, supporting form reset workflows
and validation testing scenarios.
"""

import sys
from pathlib import Path

# Add parent directory to path for MCP server import
sys.path.append(str(Path(__file__).parent.parent))
try:
    from server_instance import mcp_server
except ImportError:
    # Fallback for when running directly from mcp directory
    from server_instance import mcp_server


@mcp_server.prompt()
def clear_input_field_prompt(field_name: str, field_type: str = "input", context: str = "") -> str:
    """
    Returns a prompt guiding the LLM to clear the content of a specific form field.
    
    This prompt template helps users understand how to perform field clearing
    operations and provides context for form reset workflows.
    
    Args:
        field_name: The name or description of the field to clear
        field_type: The type of field being cleared (input, textarea, etc.)
        context: Additional context about the clearing operation
    
    Returns:
        Formatted prompt string for input field clearing operation guidance
    """
    context_section = f"\n\nAdditional Context:\n{context}" if context else ""
    
    return f"""Clear the content of the '{field_name}' {field_type} field.

This will perform a comprehensive field clearing operation which can be used for:
- Form reset workflows to clear existing input
- Preparing fields for new data entry
- Testing field clearing and validation behavior
- Ensuring clean state before automated form filling
- Resetting search fields or filter inputs

The clearing operation includes comprehensive validation and features:
- Element existence and visibility verification
- Field type compatibility checking (text, email, password, etc.)
- Editable state validation (not readonly/disabled)
- Original value capture for audit tracking
- Post-clear verification to ensure field was actually cleared
- Detailed operation timing and metadata collection

Clearing behavior details:
- Method: Uses Playwright's fill() method with empty string
- Verification: Automatic verification that field value is empty after clearing
- Safety: Validates element state before attempting to clear
- Audit: Tracks original value and clearing success for compliance

Field compatibility:
- Input types: text, email, password, search, url, tel, number, date, time
- Textarea elements: Multi-line text fields
- ContentEditable elements: Rich text editors and custom inputs
- Validation: Ensures only clearable field types are processed

Best practices for reliable field clearing:
- Use stable selectors (ID, data attributes) when possible
- Allow sufficient timeout for dynamic form elements
- Verify clearing success through subsequent form validation
- Consider form validation that may prevent clearing
- Use force option only when necessary for special cases

The operation provides detailed metadata including clearing timing, original value tracking, element properties, and verification status for comprehensive test reporting.{context_section}"""


@mcp_server.prompt()
def form_reset_prompt(form_name: str, fields: list = None) -> str:
    """
    Returns a prompt for resetting multiple form fields or an entire form.
    
    Args:
        form_name: The name or description of the form to reset
        fields: Optional list of specific fields to reset
    
    Returns:
        Formatted prompt string for form reset operation guidance
    """
    if fields:
        field_list = ", ".join(f"'{field}'" for field in fields)
        return f"""Reset the following fields in the '{form_name}' form: {field_list}.

This operation will clear the content of each specified field, preparing the form for new input. Each field will be individually validated and cleared using the clear_input_field tool with comprehensive verification.

Form reset workflow:
1. Validate form accessibility and state
2. Clear each specified field individually
3. Verify each clearing operation
4. Collect metadata for each field operation
5. Provide comprehensive reset summary

Best practices for form reset:
- Clear fields in logical order (top to bottom, left to right)
- Verify each field clearing before proceeding
- Handle any field-specific validation or restrictions
- Consider any form-level validation that may affect clearing
- Use appropriate timeouts for dynamic forms"""
    else:
        return f"""Reset all clearable fields in the '{form_name}' form.

This operation will identify and clear all appropriate input fields, textarea elements, and editable content within the specified form. Each field will be validated for clearability and cleared individually.

Complete form reset workflow:
1. Identify all clearable fields within the form
2. Validate each field's state and type
3. Clear each field using appropriate methods
4. Verify clearing success for each field
5. Handle any field-specific errors or restrictions
6. Provide comprehensive reset report

Field identification criteria:
- Input elements with clearable types (text, email, password, etc.)
- Textarea elements for multi-line content
- ContentEditable elements for rich text
- Exclude non-clearable inputs (checkbox, radio, hidden, etc.)

The operation provides detailed reporting on each field processed, including any fields that could not be cleared and the reasons why."""


@mcp_server.prompt()
def field_validation_prompt(field_name: str, validation_type: str = "clearing") -> str:
    """
    Returns a prompt for validating field state before or after clearing operations.
    
    Args:
        field_name: The name or description of the field to validate
        validation_type: The type of validation (clearing, accessibility, state)
    
    Returns:
        Formatted prompt string for field validation guidance
    """
    validation_details = {
        "clearing": "validation focuses on clearability, editability, and current value state",
        "accessibility": "validation focuses on visibility, enabled state, and user interaction capability",
        "state": "validation focuses on current value, readonly status, and element properties"
    }
    
    detail = validation_details.get(validation_type, "validation focuses on general field state and properties")
    
    return f"""Validate the '{field_name}' field for {validation_type} operations.

This validation will examine the field's current state and properties to ensure it's ready for the intended operation. The {detail}.

Validation criteria for {validation_type}:
- Element existence and DOM attachment
- Visibility and display state
- Enabled/disabled status
- Readonly attribute status
- Field type compatibility
- Current value state
- Element bounds and positioning

Validation process:
1. Locate the field using appropriate selectors
2. Check element state and properties
3. Verify field type and compatibility
4. Assess any restrictions or limitations
5. Report validation results with recommendations

The validation provides comprehensive feedback on field readiness, any identified issues, and recommendations for successful operation completion.""" 
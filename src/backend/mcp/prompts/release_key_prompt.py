"""
Release Key Prompt for IntelliBrowse MCP Server.

This module provides prompt templates for guiding LLM operations related to
keyboard key release operations, supporting complex key combinations, accessibility
testing, and advanced keyboard interaction workflows.
"""

import sys
from pathlib import Path
from typing import List

# Add parent directory to path for MCP server import
sys.path.append(str(Path(__file__).parent.parent))
try:
    from server_instance import mcp_server
except ImportError:
    # Fallback for when running directly from mcp directory
    from server_instance import mcp_server


@mcp_server.prompt()
def release_key_prompt(key_name: str, selector: str = "", context: str = "") -> str:
    """
    Returns a prompt guiding the LLM to release a held-down keyboard key.
    
    This prompt template helps users understand how to perform key release operations
    and provides context for complex keyboard interaction workflows.
    
    Args:
        key_name: The name of the key to release
        selector: Optional element selector to focus before key release
        context: Additional context about the key release operation
    
    Returns:
        Formatted prompt string for key release operation guidance
    """
    # Build focus instruction
    focus_instruction = f" after focusing on element '{selector}'" if selector else ""
    
    # Build context section
    context_section = f"\n\nAdditional Context:\n{context}" if context else ""
    
    return f"""Release the '{key_name}' key{focus_instruction}.

This will perform a keyboard key release operation which is essential for:
- Ending held key combinations and complex keyboard sequences
- Accessibility testing and keyboard-only navigation workflows
- Precise control over modifier key states in automation
- Cleanup after complex key press sequences
- Testing key release event handlers and keyboard state management

The key release operation includes comprehensive features:
- Element focus management before key release (if selector provided)
- Key validation to ensure supported key names
- Session-based key release history tracking for audit compliance
- Detailed operation timing and metadata collection
- Browser and page state validation before key release

Key release behavior details:
- Method: Uses Playwright's keyboard.up() API for precise key release simulation
- Focus: Automatic element focusing if selector is provided
- Timing: Configurable delay after key release for UI responsiveness
- Validation: Ensures only releasable keys are processed

Supported releasable key types:
- Modifier keys: Control, Shift, Alt, Meta (most common for release operations)
- Special keys: Enter, Tab, Escape, Space, Arrow keys, Function keys
- Character keys: Letters (a-z, A-Z), numbers (0-9), symbols
- Navigation keys: Home, End, PageUp, PageDown
- Function keys: F1-F12 for application-specific functions

Best practices for reliable key release operations:
- Use standard key names (e.g., 'Shift', not 'shift')
- Provide stable selectors when element focus is needed
- Allow sufficient timeout for element focus operations
- Consider the current keyboard state when releasing keys
- Use in conjunction with press_key for complex key combinations

The operation provides detailed metadata including key release timing, element focus status, and operation verification for comprehensive test reporting and debugging.

Common use cases:
- Release modifier keys after complex shortcuts (e.g., release 'Control' after Ctrl+C)
- End held-down navigation keys for accessibility testing
- Clean up keyboard state after automation sequences
- Test application behavior when keys are released in specific orders
- Implement precise timing control in keyboard interaction workflows{context_section}"""


@mcp_server.prompt()
def modifier_release_prompt(modifier_keys: List[str], selector: str = "", purpose: str = "") -> str:
    """
    Returns a prompt for releasing multiple modifier keys in sequence.
    
    Args:
        modifier_keys: List of modifier keys to release (e.g., ['Control', 'Shift'])
        selector: Optional element selector to focus before release
        purpose: The purpose or expected result of releasing the modifiers
    
    Returns:
        Formatted prompt string for modifier release operation guidance
    """
    if len(modifier_keys) == 0:
        return "No modifier keys specified for release."
    
    modifier_list = "', '".join(modifier_keys)
    focus_instruction = f" while focused on element '{selector}'" if selector else ""
    purpose_description = f" to {purpose}" if purpose else ""
    
    return f"""Release the modifier keys '{modifier_list}'{focus_instruction}{purpose_description}.

This modifier release operation will:
1. Focus on the specified element (if selector provided)
2. Release each modifier key in the specified order
3. Verify the release operation for each key
4. Apply any specified delay after each release
5. Track the release sequence for audit and debugging

Modifier key release scenarios:
- End complex keyboard shortcuts (release Control after Ctrl+C operation)
- Clean up held modifier keys after automation sequences
- Test accessibility behavior when modifiers are released
- Ensure proper keyboard state management in applications
- Implement precise timing control in keyboard workflows

Modifier release execution features:
- Sequential release of multiple modifier keys
- Element focus management for context-specific releases
- Comprehensive validation of modifier key names
- Detailed timing and operation metadata
- Error handling for unsuccessful release operations

Best practices for modifier key releases:
- Release modifier keys in reverse order of how they were pressed
- Ensure the target application or element is properly focused
- Allow sufficient delay between releases for application processing
- Verify the expected keyboard state after release operations
- Consider using release_key individually for precise control

The modifier release sequence will be executed with appropriate validation and timing to ensure reliable operation across different applications and keyboard interaction contexts."""


@mcp_server.prompt()
def key_combination_cleanup_prompt(held_keys: List[str], selector: str = "") -> str:
    """
    Returns a prompt for cleaning up after complex key combinations.
    
    Args:
        held_keys: List of keys that may still be held down
        selector: Optional element selector to focus during cleanup
    
    Returns:
        Formatted prompt string for key combination cleanup guidance
    """
    if len(held_keys) == 0:
        return "No held keys specified for cleanup."
    
    keys_list = "', '".join(held_keys)
    focus_instruction = f" in element '{selector}'" if selector else ""
    
    return f"""Clean up held keys '{keys_list}'{focus_instruction} by releasing them systematically.

This cleanup operation will:
- Release any keys that may still be held down from previous operations
- Ensure proper keyboard state management and prevent stuck keys
- Verify that all specified keys are properly released
- Track the cleanup sequence for audit and debugging purposes

Key combination cleanup scenarios:
- After complex multi-key shortcuts or automation sequences
- When switching between different UI contexts or applications
- Following accessibility testing with held modifier keys
- Before starting new keyboard interaction sequences
- When recovering from interrupted or failed keyboard operations

Cleanup operation features:
- Systematic release of all specified keys
- Element focus management for context-appropriate cleanup
- Verification that keys are properly released
- Comprehensive error handling for stuck or unresponsive keys
- Detailed operation logging for debugging and audit compliance

Best practices for key combination cleanup:
- Release modifier keys before releasing primary keys
- Allow sufficient time between releases for application processing
- Verify the keyboard state is clean before proceeding with new operations
- Use in error recovery scenarios or between test sequences
- Monitor for any keys that fail to release properly

The cleanup operation ensures a clean keyboard state and prevents interference with subsequent keyboard interactions or automation workflows."""


@mcp_server.prompt()
def accessibility_key_release_prompt(key_name: str, interaction_type: str = "", selector: str = "") -> str:
    """
    Returns a prompt for accessibility-focused key release operations.
    
    Args:
        key_name: The name of the key to release for accessibility testing
        interaction_type: Type of accessibility interaction being tested
        selector: Optional element selector for accessibility context
    
    Returns:
        Formatted prompt string for accessibility key release guidance
    """
    focus_instruction = f" while focused on element '{selector}'" if selector else ""
    interaction_context = f" during {interaction_type} testing" if interaction_type else ""
    
    return f"""Release the '{key_name}' key{focus_instruction}{interaction_context} for accessibility compliance testing.

This accessibility-focused key release operation supports:
- Keyboard-only navigation workflows and testing
- Screen reader compatibility and proper keyboard event handling
- Testing of custom keyboard interaction implementations
- Verification of proper focus management and key state handling
- Compliance with WCAG keyboard accessibility guidelines

Accessibility key release considerations:
- Ensure proper focus management and visual feedback
- Verify that key release events are properly handled by assistive technologies
- Test keyboard interaction patterns that mirror real user behavior
- Validate that application state updates correctly after key release
- Check for proper focus trapping and keyboard navigation flows

Key release accessibility features:
- Element focus management with accessibility context awareness
- Proper timing to allow for assistive technology processing
- Comprehensive validation of keyboard event handling
- Integration with screen reader and accessibility testing workflows
- Support for complex accessibility testing scenarios

Best practices for accessibility key release testing:
- Test with actual assistive technologies when possible
- Verify visual and programmatic focus indicators
- Ensure proper keyboard event propagation and handling
- Test with different accessibility user interaction patterns
- Validate compliance with platform accessibility guidelines

The accessibility-focused key release ensures proper keyboard interaction behavior for users relying on keyboard navigation and assistive technologies.""" 
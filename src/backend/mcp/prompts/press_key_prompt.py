"""
Press Key Prompt for IntelliBrowse MCP Server.

This module provides prompt templates for guiding LLM operations related to
keyboard interactions and key press operations, supporting navigation workflows,
form control, and keyboard automation scenarios.
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
def press_key_prompt(key_name: str, selector: str = "", modifiers: List[str] = None, context: str = "") -> str:
    """
    Returns a prompt guiding the LLM to press a keyboard key.
    
    This prompt template helps users understand how to perform keyboard interactions
    and provides context for key press automation workflows.
    
    Args:
        key_name: The name of the key to press
        selector: Optional element selector to focus before key press
        modifiers: Optional list of modifier keys
        context: Additional context about the key press operation
    
    Returns:
        Formatted prompt string for key press operation guidance
    """
    if modifiers is None:
        modifiers = []
    
    # Build key combination string
    if modifiers:
        key_combination = "+".join(modifiers + [key_name])
    else:
        key_combination = key_name
    
    # Build focus instruction
    focus_instruction = f" after focusing on element '{selector}'" if selector else ""
    
    # Build context section
    context_section = f"\n\nAdditional Context:\n{context}" if context else ""
    
    return f"""Press the '{key_combination}' key{focus_instruction}.

This will perform a comprehensive keyboard interaction which can be used for:
- Navigation and form control (Enter, Tab, Arrow keys)
- Text editing operations (Backspace, Delete, Insert)
- Shortcut key combinations (Ctrl+C, Ctrl+V, Alt+Tab)
- Function key operations (F1-F12 for application functions)
- Special key interactions (Escape, Space, Page navigation)

The key press operation includes comprehensive features:
- Element focus management before key press (if selector provided)
- Support for modifier key combinations (Control, Shift, Alt, Meta)
- Key validation to ensure supported key names and combinations
- Session-based key press history tracking for audit compliance
- Detailed operation timing and metadata collection
- Browser and page state validation before key press

Key press behavior details:
- Method: Uses Playwright's keyboard API for realistic key simulation
- Focus: Automatic element focusing if selector is provided
- Timing: Configurable delay after key press for UI responsiveness
- Modifiers: Support for standard modifier keys in proper sequence

Supported key types:
- Special keys: Enter, Tab, Escape, Space, Arrow keys, Function keys
- Character keys: Letters (a-z, A-Z), numbers (0-9), symbols
- Navigation keys: Home, End, PageUp, PageDown
- Editing keys: Backspace, Delete, Insert
- Modifier keys: Control, Shift, Alt, Meta

Best practices for reliable key press operations:
- Use standard key names (e.g., 'Enter', not 'Return')
- Provide stable selectors when element focus is needed
- Allow sufficient timeout for element focus operations
- Use appropriate modifier combinations for shortcuts
- Consider page state and context when pressing navigation keys

The operation provides detailed metadata including key press timing, element focus status, modifier usage, and operation verification for comprehensive test reporting.{context_section}"""


@mcp_server.prompt()
def keyboard_shortcut_prompt(shortcut_keys: List[str], purpose: str = "", selector: str = "") -> str:
    """
    Returns a prompt for executing keyboard shortcuts and key combinations.
    
    Args:
        shortcut_keys: List of keys in the shortcut (e.g., ['Control', 'C'])
        purpose: The purpose or action the shortcut performs
        selector: Optional element selector to focus before shortcut
    
    Returns:
        Formatted prompt string for keyboard shortcut operation guidance
    """
    if len(shortcut_keys) == 0:
        return "No keys specified for keyboard shortcut."
    
    # Separate modifiers from the main key
    modifiers = shortcut_keys[:-1] if len(shortcut_keys) > 1 else []
    main_key = shortcut_keys[-1]
    
    shortcut_display = "+".join(shortcut_keys)
    focus_instruction = f" while focused on element '{selector}'" if selector else ""
    purpose_description = f" to {purpose}" if purpose else ""
    
    return f"""Execute the keyboard shortcut '{shortcut_display}'{focus_instruction}{purpose_description}.

This shortcut operation will:
1. Focus on the specified element (if selector provided)
2. Press and hold modifier keys in sequence: {', '.join(modifiers) if modifiers else 'None'}
3. Press the main key: {main_key}
4. Release modifier keys in reverse order
5. Apply any specified delay after the operation

Common keyboard shortcuts and their purposes:
- Ctrl+C, Ctrl+V: Copy and paste operations
- Ctrl+Z, Ctrl+Y: Undo and redo operations
- Ctrl+A: Select all content
- Ctrl+S: Save operation
- Ctrl+F: Find/search operation
- Alt+Tab: Switch between applications/windows
- Ctrl+Shift+I: Open developer tools
- F1-F12: Function key operations (help, refresh, etc.)

Keyboard shortcut execution features:
- Proper modifier key sequence (press down, execute, release up)
- Element focus management for context-specific shortcuts
- Comprehensive validation of key combinations
- Detailed timing and operation metadata
- Error handling for unsupported key combinations

Best practices for keyboard shortcuts:
- Ensure the target element is focused for context-specific shortcuts
- Use standard modifier key combinations for cross-platform compatibility
- Allow sufficient delay for applications to process the shortcut
- Verify the expected result after shortcut execution
- Consider alternative methods if shortcuts fail or are not supported"""


@mcp_server.prompt()
def navigation_key_prompt(navigation_action: str, selector: str = "", steps: int = 1) -> str:
    """
    Returns a prompt for navigation key operations (Arrow keys, Tab, Enter, etc.).
    
    Args:
        navigation_action: Type of navigation (up, down, left, right, next, previous, submit)
        selector: Optional element selector to focus before navigation
        steps: Number of steps to navigate (for arrow keys)
    
    Returns:
        Formatted prompt string for navigation key operation guidance
    """
    # Map navigation actions to keys
    navigation_mapping = {
        "up": "ArrowUp",
        "down": "ArrowDown",
        "left": "ArrowLeft",
        "right": "ArrowRight",
        "next": "Tab",
        "previous": "Shift+Tab",
        "submit": "Enter",
        "cancel": "Escape",
        "home": "Home",
        "end": "End",
        "page_up": "PageUp",
        "page_down": "PageDown"
    }
    
    key_sequence = navigation_mapping.get(navigation_action.lower(), navigation_action)
    focus_instruction = f" in element '{selector}'" if selector else ""
    steps_description = f" {steps} time(s)" if steps > 1 and navigation_action.lower() in ["up", "down", "left", "right"] else ""
    
    return f"""Navigate {navigation_action}{focus_instruction} using the '{key_sequence}' key{steps_description}.

This navigation operation will:
- Focus on the specified element (if selector provided)
- Execute the navigation key press with proper timing
- Track the navigation action for audit and debugging
- Provide detailed operation metadata and results

Navigation key functions:
- Arrow keys: Move cursor or selection within elements
- Tab: Move to next focusable element in tab order
- Shift+Tab: Move to previous focusable element
- Enter: Submit forms or activate focused elements
- Escape: Cancel operations or close dialogs
- Home/End: Move to beginning/end of content
- PageUp/PageDown: Scroll content by page increments

Navigation contexts and best practices:
- Form fields: Use Tab to move between fields, Arrow keys within fields
- Lists and grids: Use Arrow keys to navigate between items
- Menus: Use Arrow keys and Enter to navigate and select
- Text areas: Use Arrow keys for cursor movement, Home/End for line navigation
- Dialogs: Use Tab for navigation, Enter to confirm, Escape to cancel

Navigation operation features:
- Intelligent key selection based on navigation action
- Element focus management for proper context
- Support for repeated navigation steps
- Comprehensive error handling and recovery
- Detailed operation tracking and metadata collection

The navigation will be executed with appropriate timing and validation to ensure reliable operation across different UI components and contexts."""


@mcp_server.prompt()
def function_key_prompt(function_number: int, purpose: str = "", selector: str = "") -> str:
    """
    Returns a prompt for function key operations (F1-F12).
    
    Args:
        function_number: Function key number (1-12)
        purpose: The purpose or expected action of the function key
        selector: Optional element selector to focus before function key press
    
    Returns:
        Formatted prompt string for function key operation guidance
    """
    if not 1 <= function_number <= 12:
        return f"Invalid function key number: {function_number}. Must be between 1 and 12."
    
    function_key = f"F{function_number}"
    focus_instruction = f" while focused on element '{selector}'" if selector else ""
    purpose_description = f" for {purpose}" if purpose else ""
    
    # Common function key purposes
    common_purposes = {
        1: "Help or documentation",
        2: "Rename or edit mode",
        3: "Search or find next",
        4: "Address bar (in browsers)",
        5: "Refresh or reload",
        6: "Move cursor to address bar",
        7: "Spell check (in some applications)",
        8: "Extended selection mode",
        9: "Recalculate (in spreadsheets)",
        10: "Menu activation",
        11: "Full screen mode",
        12: "Save As dialog"
    }
    
    default_purpose = common_purposes.get(function_number, "application-specific function")
    
    return f"""Press the '{function_key}' function key{focus_instruction}{purpose_description}.

This function key operation will execute application-specific functionality. Common purposes for {function_key}:
- Default purpose: {default_purpose}
- Context-dependent actions based on the focused application or element
- Application shortcuts and specialized functions

Function key operation details:
- Key: {function_key}
- Context: {'Element-specific' if selector else 'Global application context'}
- Purpose: {purpose if purpose else default_purpose}

Function key behavior considerations:
- Function keys may behave differently in different applications
- Some function keys may require specific application focus
- Browser function keys may be intercepted by the browser itself
- Function keys may be disabled or remapped in some environments

Function key execution features:
- Proper timing for application response
- Element focus management for context-specific actions
- Comprehensive error handling for unsupported operations
- Detailed operation metadata and result tracking
- Validation of function key support in the current context

Best practices for function key operations:
- Verify the expected behavior in the current application context
- Consider alternative methods if function keys are intercepted
- Allow sufficient time for application response after function key press
- Test function key behavior in the target environment
- Document function key purposes for maintenance and debugging

The function key will be executed with appropriate validation and timing to ensure reliable operation across different applications and contexts.""" 
"""
Release Key Prompt for IntelliBrowse MCP Server.

This prompt provides guidance for releasing held-down keyboard keys,
particularly useful for modifier key combinations, long-press scenarios,
and accessibility testing workflows.
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from main import mcp_server


@mcp_server.prompt()
def release_key_prompt(key: str, description: str = "") -> str:
    """
    Generate guidance for releasing a specific keyboard key.
    
    This prompt helps users understand the context and purpose of key release
    operations, especially for modifier keys and complex keyboard interactions.
    
    Args:
        key: The key to be released (e.g., 'Shift', 'Control', 'Alt')
        description: Optional additional context about the key release scenario
    
    Returns:
        Formatted prompt text with guidance for the key release operation
    """
    
    # Key-specific guidance
    key_guidance = {
        "Shift": "Release the Shift key to end capitalization or symbol input mode",
        "Control": "Release the Control key to end keyboard shortcut combination",
        "Alt": "Release the Alt key to end alternative input mode or shortcut combination",
        "Meta": "Release the Meta/Cmd key to end system-level shortcut combination",
        "Enter": "Release the Enter key after long-press or held activation",
        "Space": "Release the Space key after long-press action",
        "Tab": "Release the Tab key to end navigation or focus sequence",
        "Escape": "Release the Escape key after modal or action cancellation",
        "F1": "Release the F1 function key after help activation",
        "F5": "Release the F5 function key after refresh action",
        "ArrowUp": "Release the Arrow Up key to end continuous navigation",
        "ArrowDown": "Release the Arrow Down key to end continuous navigation",
        "ArrowLeft": "Release the Arrow Left key to end continuous navigation", 
        "ArrowRight": "Release the Arrow Right key to end continuous navigation"
    }
    
    base_guidance = key_guidance.get(key, f"Release the '{key}' key to end its held state")
    
    prompt_text = f"""Release the '{key}' key in the browser. {base_guidance}.

Common Release Key Scenarios:
- Modifier Key Combinations: Release modifier keys (Shift, Control, Alt) after keyboard shortcuts
- Long-Press Actions: Release keys that were held down for extended periods
- Accessibility Testing: Test key release events for screen readers and assistive technologies
- Gaming/Interactive Applications: Release action keys in browser-based games or interactive content
- Form Navigation: Release navigation keys (Tab, Arrow keys) after sequential element focusing

Key Release Guidelines:
- Ensure the key was previously pressed/held before attempting to release
- Release modifier keys in reverse order of pressing for complex combinations
- Consider element focus if the key release should target a specific form field or control
- Use verification to confirm the key release was processed correctly
- Apply post-release delays if the application needs time to process the key event

{f'Context: {description}' if description else ''}

The release operation will:
1. Focus the target element (if selector provided)
2. Release the '{key}' key using keyboard.up()
3. Verify the release operation (if verification enabled)
4. Apply any specified delay after the release
5. Return detailed operation results and timing information"""

    return prompt_text


@mcp_server.prompt()
def modifier_key_release_prompt(modifiers: str = "Control,Shift") -> str:
    """
    Generate guidance for releasing multiple modifier keys in sequence.
    
    Args:
        modifiers: Comma-separated list of modifier keys to release
    
    Returns:
        Formatted prompt text for releasing multiple modifier keys
    """
    
    modifier_list = [mod.strip() for mod in modifiers.split(",")]
    
    prompt_text = f"""Release modifier keys in sequence: {', '.join(modifier_list)}.

Modifier Key Release Best Practices:
- Release modifier keys in reverse order of pressing (LIFO - Last In, First Out)
- Common release sequence: Meta/Cmd → Alt → Control → Shift
- Allow brief delays between releases for complex key combinations
- Verify each release before proceeding to the next modifier

Typical Modifier Combinations:
- Ctrl+Shift: Text selection and formatting operations
- Ctrl+Alt: System shortcuts and application commands  
- Meta+Shift: Window management and system navigation
- Ctrl+Alt+Shift: Advanced shortcuts and developer tools

For each modifier key:
1. Identify the current held state
2. Release in the appropriate sequence
3. Verify the release was successful
4. Continue to the next modifier if applicable

This ensures clean release of complex keyboard combinations and prevents stuck modifier states."""

    return prompt_text


@mcp_server.prompt()
def accessibility_key_release_prompt(scenario: str = "screen_reader") -> str:
    """
    Generate guidance for key release operations in accessibility testing scenarios.
    
    Args:
        scenario: The accessibility testing scenario (e.g., 'screen_reader', 'keyboard_navigation')
    
    Returns:
        Formatted prompt text for accessibility-focused key release testing
    """
    
    scenarios = {
        "screen_reader": {
            "title": "Screen Reader Key Release Testing",
            "keys": ["Control", "Alt", "Shift", "Insert", "F6"],
            "purpose": "Test screen reader navigation and announcement key combinations"
        },
        "keyboard_navigation": {
            "title": "Keyboard Navigation Key Release Testing", 
            "keys": ["Tab", "Shift", "Enter", "Space", "ArrowUp", "ArrowDown"],
            "purpose": "Test keyboard-only navigation and interaction patterns"
        },
        "voice_control": {
            "title": "Voice Control Key Release Testing",
            "keys": ["Control", "Alt", "F2", "F4", "Escape"],
            "purpose": "Test voice control software key release recognition"
        }
    }
    
    scenario_info = scenarios.get(scenario, {
        "title": "General Accessibility Key Release Testing",
        "keys": ["Tab", "Shift", "Control", "Alt", "Enter"],
        "purpose": "Test general accessibility key release patterns"
    })
    
    prompt_text = f"""{scenario_info['title']}

Purpose: {scenario_info['purpose']}

Key accessibility considerations for key release:
- Ensure key release events are properly announced by screen readers
- Test that release events don't interfere with continuous navigation
- Verify that modifier key releases don't break accessibility shortcuts
- Confirm that release timing allows assistive technology to process events

Common accessibility keys to test: {', '.join(scenario_info['keys'])}

Testing Approach:
1. Press and hold the accessibility key
2. Navigate or perform the intended action while key is held
3. Release the key and verify the state change is announced
4. Test that subsequent accessibility features work correctly
5. Document any timing or interaction issues

This testing ensures that key release operations are compatible with assistive technologies and accessibility standards."""

    return prompt_text 
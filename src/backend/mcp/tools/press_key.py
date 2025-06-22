"""
Press Key Tool for IntelliBrowse MCP Server.

This module provides keyboard key press simulation functionality for Playwright 
browser sessions, enabling keyboard interaction automation with comprehensive 
validation, modifier key support, and detailed operation tracking for automation workflows.

Key Features:
- Single key press simulation using Playwright keyboard events
- Support for modifier keys (Control, Shift, Alt, Meta)
- Optional element focus before key press
- Comprehensive key validation and mapping
- Session-based key press history tracking for audit compliance
- Element state validation and interaction verification
- Error handling with structured responses and classification
- Support for special keys (Enter, Tab, Arrow keys, Function keys, etc.)

Author: IntelliBrowse MCP Server
Version: 1.0.0
"""

import time
from datetime import datetime
from typing import Dict, Any, Optional, List
import structlog
from playwright.async_api import Page, Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError
from pydantic import ValidationError

# Import the main MCP server instance
try:
    from server_instance import mcp_server
except ImportError:
    # Fallback for when running directly from mcp directory
    from server_instance import mcp_server

# Import schemas - use absolute import to avoid relative import issues
try:
    from schemas.tools.press_key_schemas import PressKeyRequest, PressKeyResponse
except ImportError:
    # Fallback for when running directly from mcp directory
    from schemas.tools.press_key_schemas import PressKeyRequest, PressKeyResponse

# Import browser session utilities - use absolute import
try:
    from tools.browser_session import browser_sessions
except ImportError:
    # Fallback for when running directly from mcp directory
    from tools.browser_session import browser_sessions

logger = structlog.get_logger("intellibrowse.mcp.tools.press_key")

# Valid modifier keys for keyboard combinations
VALID_MODIFIERS = [
    "Control", "Shift", "Alt", "Meta", "ControlOrMeta"
]

# Common special keys mapping for validation
SPECIAL_KEYS = {
    # Navigation keys
    "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight",
    "Home", "End", "PageUp", "PageDown",
    
    # Editing keys
    "Enter", "Tab", "Escape", "Space", "Backspace", "Delete",
    "Insert",
    
    # Function keys
    "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",
    
    # Numpad keys
    "NumpadEnter", "NumpadAdd", "NumpadSubtract", "NumpadMultiply", "NumpadDivide",
    "Numpad0", "Numpad1", "Numpad2", "Numpad3", "Numpad4", "Numpad5", 
    "Numpad6", "Numpad7", "Numpad8", "Numpad9", "NumpadDecimal",
    
    # Media keys
    "AudioVolumeUp", "AudioVolumeDown", "AudioVolumeMute",
    "MediaTrackNext", "MediaTrackPrevious", "MediaPlayPause", "MediaStop",
    
    # Lock keys
    "CapsLock", "NumLock", "ScrollLock",
    
    # Context menu
    "ContextMenu"
}

# Character keys - letters, numbers, symbols that can be typed directly
CHARACTER_KEYS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
SYMBOL_KEYS = set("!@#$%^&*()_+-=[]{}|\\:;\"'<>?,./`~")

# Maximum reasonable delay between modifier and key press
MAX_KEY_DELAY_MS = 5000


@mcp_server.tool()
async def press_key(
    session_id: str,
    key: str,
    selector: Optional[str] = None,
    modifiers: Optional[List[str]] = None,
    timeout_ms: Optional[int] = 5000,
    delay_after_ms: Optional[int] = 0,
    focus_first: Optional[bool] = True
) -> Dict[str, Any]:
    """
    Simulate pressing a keyboard key with optional modifiers and element focus.
    
    This tool provides comprehensive keyboard interaction simulation for Playwright 
    browser sessions, with support for special keys, modifier combinations, element 
    focus management, and detailed operation tracking for automation workflows.
    
    Args:
        session_id: Browser session identifier for the target session
        key: Key to press (e.g., 'Enter', 'Tab', 'ArrowRight', 'a', 'F1')
        selector: Optional CSS selector to focus before pressing key
        modifiers: Optional list of modifier keys (['Control', 'Shift', 'Alt', 'Meta'])
        timeout_ms: Maximum time to wait for element focus in milliseconds (default: 5000)
        delay_after_ms: Delay after key press in milliseconds (default: 0)
        focus_first: Whether to focus the element before key press if selector provided (default: True)
    
    Returns:
        Dict containing key press operation status, timing, and comprehensive metadata
    """
    start_time = time.monotonic()
    
    # Normalize modifiers to empty list if None
    if modifiers is None:
        modifiers = []
    
    logger.info(
        "Starting key press operation",
        session_id=session_id,
        key=key,
        selector=selector,
        modifiers=modifiers,
        timeout_ms=timeout_ms,
        delay_after_ms=delay_after_ms,
        focus_first=focus_first
    )
    
    try:
        # Validate request using Pydantic schema
        request = PressKeyRequest(
            session_id=session_id,
            key=key,
            selector=selector,
            modifiers=modifiers,
            timeout_ms=timeout_ms,
            delay_after_ms=delay_after_ms,
            focus_first=focus_first
        )
        
        # Validate key format
        if not key or not key.strip():
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Empty key provided")
            return PressKeyResponse(
                success=False,
                session_id=session_id,
                key=key,
                selector=selector,
                message="Key cannot be empty",
                key_pressed=False,
                focused_element=False,
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "INVALID_KEY",
                    "error_details": "Empty or whitespace-only key",
                    "operation_time_ms": elapsed_ms
                }
            ).dict()
        
        # Validate key is supported
        key_valid = (
            key in SPECIAL_KEYS or 
            key in CHARACTER_KEYS or 
            key in SYMBOL_KEYS or
            len(key) == 1  # Allow single character keys
        )
        
        if not key_valid:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Unsupported key", key=key)
            return PressKeyResponse(
                success=False,
                session_id=session_id,
                key=key,
                selector=selector,
                message=f"Unsupported key: '{key}'. Use standard key names like 'Enter', 'Tab', 'ArrowLeft', etc.",
                key_pressed=False,
                focused_element=False,
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "UNSUPPORTED_KEY",
                    "key": key,
                    "supported_special_keys": list(SPECIAL_KEYS),
                    "operation_time_ms": elapsed_ms
                }
            ).dict()
        
        # Validate modifiers
        for modifier in modifiers:
            if modifier not in VALID_MODIFIERS:
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                logger.error("Invalid modifier", modifier=modifier)
                return PressKeyResponse(
                    success=False,
                    session_id=session_id,
                    key=key,
                    selector=selector,
                    message=f"Invalid modifier key: '{modifier}'. Supported modifiers: {VALID_MODIFIERS}",
                    key_pressed=False,
                    focused_element=False,
                    elapsed_ms=elapsed_ms,
                    metadata={
                        "error": "INVALID_MODIFIER",
                        "invalid_modifier": modifier,
                        "valid_modifiers": VALID_MODIFIERS,
                        "operation_time_ms": elapsed_ms
                    }
                ).dict()
        
        # Check if session exists
        if session_id not in browser_sessions:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Browser session not found", session_id=session_id)
            return PressKeyResponse(
                success=False,
                session_id=session_id,
                key=key,
                selector=selector,
                message=f"Browser session {session_id} not found",
                key_pressed=False,
                focused_element=False,
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "SESSION_NOT_FOUND",
                    "session_id": session_id,
                    "operation_time_ms": elapsed_ms
                }
            ).dict()
        
        session = browser_sessions[session_id]
        page: Page = session["page"]
        
        # Verify page is still active
        try:
            await page.title()  # Simple check to ensure page is responsive
        except PlaywrightError as e:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Page is not active", session_id=session_id, error=str(e))
            return PressKeyResponse(
                success=False,
                session_id=session_id,
                key=key,
                selector=selector,
                message=f"Page is not active or accessible: {str(e)}",
                key_pressed=False,
                focused_element=False,
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "PAGE_NOT_ACTIVE",
                    "error_details": str(e),
                    "operation_time_ms": elapsed_ms
                }
            ).dict()
        
        # Handle element focus if selector is provided
        focused_element = False
        element_info = {}
        
        if selector and focus_first:
            try:
                logger.info("Focusing element before key press", selector=selector, timeout_ms=timeout_ms)
                
                # Wait for element to be present and visible
                element = await page.wait_for_selector(
                    selector,
                    timeout=timeout_ms,
                    state="visible"
                )
                
                if not element:
                    elapsed_ms = int((time.monotonic() - start_time) * 1000)
                    logger.error("Element not found for focus", selector=selector)
                    return PressKeyResponse(
                        success=False,
                        session_id=session_id,
                        key=key,
                        selector=selector,
                        message=f"Element not found for focus: {selector}",
                        key_pressed=False,
                        focused_element=False,
                        elapsed_ms=elapsed_ms,
                        metadata={
                            "error": "ELEMENT_NOT_FOUND",
                            "selector": selector,
                            "timeout_ms": timeout_ms,
                            "operation_time_ms": elapsed_ms
                        }
                    ).dict()
                
                # Focus the element
                await element.focus(timeout=timeout_ms)
                focused_element = True
                
                # Get element information for metadata
                try:
                    element_tag = await element.evaluate("el => el.tagName.toLowerCase()")
                    element_type = await element.evaluate("el => el.type || ''")
                    element_id = await element.evaluate("el => el.id || ''")
                    element_class = await element.evaluate("el => el.className || ''")
                    element_bounds = await element.bounding_box()
                    
                    element_info = {
                        "tag": element_tag,
                        "type": element_type,
                        "id": element_id,
                        "class": element_class,
                        "bounds": element_bounds,
                        "focused": True
                    }
                except PlaywrightError:
                    element_info = {"focused": True}
                
                logger.info("Element focused successfully", selector=selector, element_tag=element_tag)
                
            except PlaywrightTimeoutError as te:
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                logger.error("Element focus timed out", selector=selector, timeout_ms=timeout_ms, error=str(te))
                return PressKeyResponse(
                    success=False,
                    session_id=session_id,
                    key=key,
                    selector=selector,
                    message=f"Element focus timed out after {timeout_ms}ms: {selector}",
                    key_pressed=False,
                    focused_element=False,
                    elapsed_ms=elapsed_ms,
                    metadata={
                        "error": "FOCUS_TIMEOUT",
                        "selector": selector,
                        "timeout_ms": timeout_ms,
                        "error_details": str(te),
                        "operation_time_ms": elapsed_ms
                    }
                ).dict()
                
            except PlaywrightError as pe:
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                error_message = str(pe)
                logger.error("Element focus failed", selector=selector, error=error_message)
                return PressKeyResponse(
                    success=False,
                    session_id=session_id,
                    key=key,
                    selector=selector,
                    message=f"Element focus failed: {error_message}",
                    key_pressed=False,
                    focused_element=False,
                    elapsed_ms=elapsed_ms,
                    metadata={
                        "error": "FOCUS_FAILED",
                        "selector": selector,
                        "error_details": error_message,
                        "operation_time_ms": elapsed_ms
                    }
                ).dict()
        
        # Perform the key press operation
        key_press_start_time = time.monotonic()
        key_pressed = False
        
        try:
            logger.info("Performing key press", key=key, modifiers=modifiers)
            
            # Press modifier keys down
            if modifiers:
                for modifier in modifiers:
                    await page.keyboard.down(modifier)
                    logger.debug("Modifier key down", modifier=modifier)
            
            # Press the main key
            await page.keyboard.press(key)
            key_pressed = True
            
            # Release modifier keys
            if modifiers:
                for modifier in reversed(modifiers):  # Release in reverse order
                    await page.keyboard.up(modifier)
                    logger.debug("Modifier key up", modifier=modifier)
            
            key_press_elapsed_ms = int((time.monotonic() - key_press_start_time) * 1000)
            
            # Apply post-key-press delay if specified
            if delay_after_ms > 0:
                await page.wait_for_timeout(delay_after_ms)
            
            # Update session key press history
            if "key_history" not in session:
                session["key_history"] = []
            
            key_operation = {
                "timestamp": datetime.utcnow().isoformat(),
                "key": key,
                "modifiers": modifiers,
                "selector": selector,
                "focused_element": focused_element,
                "key_press_time_ms": key_press_elapsed_ms,
                "delay_after_ms": delay_after_ms,
                "success": True
            }
            
            session["key_history"].append(key_operation)
            
            # Keep only last 50 key press operations
            if len(session["key_history"]) > 50:
                session["key_history"] = session["key_history"][-50:]
            
            # Calculate total elapsed time
            total_elapsed_ms = int((time.monotonic() - start_time) * 1000)
            
            # Prepare success message
            if modifiers:
                modifier_str = "+".join(modifiers)
                message = f"Successfully pressed key combination '{modifier_str}+{key}'"
            else:
                message = f"Successfully pressed key '{key}'"
            
            if selector and focused_element:
                message += f" on element '{selector}'"
            
            # Get page context
            try:
                page_url = await page.url()
                page_title = await page.title()
            except PlaywrightError:
                page_url = ""
                page_title = ""
            
            # Collect comprehensive metadata
            metadata = {
                "operation_type": "press_key",
                "timestamp": datetime.utcnow().isoformat(),
                "session_id": session_id,
                "key_details": {
                    "key": key,
                    "modifiers": modifiers,
                    "key_type": "special" if key in SPECIAL_KEYS else "character",
                    "modifier_count": len(modifiers)
                },
                "element_interaction": {
                    "selector": selector,
                    "focused_element": focused_element,
                    "focus_first": focus_first,
                    "element_info": element_info
                },
                "timing": {
                    "total_operation_ms": total_elapsed_ms,
                    "key_press_ms": key_press_elapsed_ms,
                    "delay_after_ms": delay_after_ms,
                    "focus_time_ms": total_elapsed_ms - key_press_elapsed_ms - delay_after_ms
                },
                "page_context": {
                    "url": page_url,
                    "title": page_title
                }
            }
            
            logger.info(
                "Key press operation completed successfully",
                key=key,
                modifiers=modifiers,
                selector=selector,
                focused_element=focused_element,
                total_elapsed_ms=total_elapsed_ms
            )
            
            # Return successful response
            return PressKeyResponse(
                success=True,
                session_id=session_id,
                key=key,
                selector=selector,
                message=message,
                key_pressed=key_pressed,
                focused_element=focused_element,
                modifiers_used=modifiers,
                elapsed_ms=total_elapsed_ms,
                metadata=metadata
            ).dict()
            
        except PlaywrightError as pe:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            error_message = str(pe)
            logger.error("Key press operation failed", key=key, modifiers=modifiers, error=error_message)
            return PressKeyResponse(
                success=False,
                session_id=session_id,
                key=key,
                selector=selector,
                message=f"Key press operation failed: {error_message}",
                key_pressed=key_pressed,
                focused_element=focused_element,
                modifiers_used=modifiers,
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "KEY_PRESS_FAILED",
                    "error_details": error_message,
                    "operation_time_ms": elapsed_ms,
                    "key": key,
                    "modifiers": modifiers
                }
            ).dict()
            
    except ValidationError as ve:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        validation_errors = str(ve)
        logger.error("Request validation failed", error=validation_errors, elapsed_ms=elapsed_ms)
        return PressKeyResponse(
            success=False,
            session_id=session_id,
            key=key,
            selector=selector,
            message=f"Request validation failed: {validation_errors}",
            key_pressed=False,
            focused_element=False,
            modifiers_used=modifiers or [],
            elapsed_ms=elapsed_ms,
            metadata={
                "error": "VALIDATION_ERROR",
                "validation_details": validation_errors,
                "operation_time_ms": elapsed_ms
            }
        ).dict()
        
    except Exception as e:
        # Handle any unexpected errors
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        error_message = str(e)
        
        logger.error(
            "Unexpected error during key press operation",
            session_id=session_id,
            key=key,
            selector=selector,
            error=error_message,
            elapsed_ms=elapsed_ms
        )
        
        return PressKeyResponse(
            success=False,
            session_id=session_id,
            key=key,
            selector=selector,
            message=f"Unexpected error during key press operation: {error_message}",
            key_pressed=False,
            focused_element=False,
            modifiers_used=modifiers or [],
            elapsed_ms=elapsed_ms,
            metadata={
                "error": "UNEXPECTED_ERROR",
                "error_details": error_message,
                "operation_time_ms": elapsed_ms
            }
        ).dict()


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
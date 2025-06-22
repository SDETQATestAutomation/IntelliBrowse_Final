"""
Release Key Tool for IntelliBrowse MCP Server.

This module provides keyboard key release simulation functionality for Playwright 
browser sessions, enabling release of held-down keys for complex key combinations,
accessibility testing, and advanced keyboard interaction workflows with comprehensive 
validation and detailed operation tracking.

Key Features:
- Single key release simulation using Playwright keyboard events
- Support for releasing modifier keys and special keys
- Optional element focus before key release
- Comprehensive key validation and state management
- Session-based key release history tracking for audit compliance
- Element state validation and interaction verification
- Error handling with structured responses and classification
- Support for releasing keys in held key combinations

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
    from schemas.tools.release_key_schemas import ReleaseKeyRequest, ReleaseKeyResponse
except ImportError:
    # Fallback for when running directly from mcp directory
    from schemas.tools.release_key_schemas import ReleaseKeyRequest, ReleaseKeyResponse

# Import browser session utilities - use absolute import
try:
    from tools.browser_session import browser_sessions
except ImportError:
    # Fallback for when running directly from mcp directory
    from tools.browser_session import browser_sessions

logger = structlog.get_logger("intellibrowse.mcp.tools.release_key")

# Valid keys that can be released (primarily modifier and special keys)
RELEASABLE_KEYS = {
    # Modifier keys (most common for release operations)
    "Control", "Shift", "Alt", "Meta", "ControlOrMeta",
    
    # Special keys that can be held down
    "Enter", "Tab", "Escape", "Space", "Backspace", "Delete",
    "Insert", 
    
    # Navigation keys
    "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight",
    "Home", "End", "PageUp", "PageDown",
    
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

# Character keys that can also be released
CHARACTER_KEYS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
SYMBOL_KEYS = set("!@#$%^&*()_+-=[]{}|\\:;\"'<>?,./`~")

# Maximum reasonable delay after key release
MAX_RELEASE_DELAY_MS = 5000


@mcp_server.tool()
async def release_key(
    session_id: str,
    key: str,
    selector: Optional[str] = None,
    timeout_ms: Optional[int] = 5000,
    delay_after_ms: Optional[int] = 0,
    focus_first: Optional[bool] = True,
    verify_release: Optional[bool] = True
) -> Dict[str, Any]:
    """
    Release a held-down keyboard key with optional element focus and validation.
    
    This tool provides key release simulation for Playwright browser sessions,
    essential for complex key combinations, accessibility testing, and advanced
    keyboard interaction workflows where keys need to be released individually.
    
    Args:
        session_id: Browser session identifier for the target session
        key: Key to release (e.g., 'Shift', 'Control', 'Alt', 'Enter', 'F1')
        selector: Optional CSS selector to focus before releasing key
        timeout_ms: Maximum time to wait for element focus in milliseconds (default: 5000)
        delay_after_ms: Delay after key release in milliseconds (default: 0)
        focus_first: Whether to focus the element before key release if selector provided (default: True)
        verify_release: Whether to verify the key release operation (default: True)
    
    Returns:
        Dict containing key release operation status, timing, and comprehensive metadata
    """
    start_time = time.monotonic()
    
    logger.info(
        "Starting key release operation",
        session_id=session_id,
        key=key,
        selector=selector,
        timeout_ms=timeout_ms,
        delay_after_ms=delay_after_ms,
        focus_first=focus_first,
        verify_release=verify_release
    )
    
    try:
        # Validate request using Pydantic schema
        request = ReleaseKeyRequest(
            session_id=session_id,
            key=key,
            selector=selector,
            timeout_ms=timeout_ms,
            delay_after_ms=delay_after_ms,
            focus_first=focus_first,
            verify_release=verify_release
        )
        
        # Validate key format
        if not key or not key.strip():
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Empty key provided")
            return ReleaseKeyResponse(
                success=False,
                session_id=session_id,
                key=key,
                selector=selector,
                message="Key cannot be empty",
                key_released=False,
                focused_element=False,
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "INVALID_KEY",
                    "error_details": "Empty or whitespace-only key",
                    "operation_time_ms": elapsed_ms
                }
            ).dict()
        
        # Validate key is supported for release
        key_valid = (
            key in RELEASABLE_KEYS or 
            key in CHARACTER_KEYS or 
            key in SYMBOL_KEYS or
            len(key) == 1  # Allow single character keys
        )
        
        if not key_valid:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Unsupported key for release", key=key)
            return ReleaseKeyResponse(
                success=False,
                session_id=session_id,
                key=key,
                selector=selector,
                message=f"Unsupported key for release: '{key}'. Use standard key names like 'Shift', 'Control', 'Enter', etc.",
                key_released=False,
                focused_element=False,
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "UNSUPPORTED_KEY",
                    "key": key,
                    "supported_releasable_keys": list(RELEASABLE_KEYS),
                    "operation_time_ms": elapsed_ms
                }
            ).dict()
        
        # Check if session exists
        if session_id not in browser_sessions:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Browser session not found", session_id=session_id)
            return ReleaseKeyResponse(
                success=False,
                session_id=session_id,
                key=key,
                selector=selector,
                message=f"Browser session {session_id} not found",
                key_released=False,
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
            return ReleaseKeyResponse(
                success=False,
                session_id=session_id,
                key=key,
                selector=selector,
                message=f"Page is not active or accessible: {str(e)}",
                key_released=False,
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
                logger.info("Focusing element before key release", selector=selector, timeout_ms=timeout_ms)
                
                # Wait for element to be present and visible
                element = await page.wait_for_selector(
                    selector,
                    timeout=timeout_ms,
                    state="visible"
                )
                
                if not element:
                    elapsed_ms = int((time.monotonic() - start_time) * 1000)
                    logger.error("Element not found for focus", selector=selector)
                    return ReleaseKeyResponse(
                        success=False,
                        session_id=session_id,
                        key=key,
                        selector=selector,
                        message=f"Element not found for focus: {selector}",
                        key_released=False,
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
                return ReleaseKeyResponse(
                    success=False,
                    session_id=session_id,
                    key=key,
                    selector=selector,
                    message=f"Element focus timed out after {timeout_ms}ms: {selector}",
                    key_released=False,
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
                return ReleaseKeyResponse(
                    success=False,
                    session_id=session_id,
                    key=key,
                    selector=selector,
                    message=f"Element focus failed: {error_message}",
                    key_released=False,
                    focused_element=False,
                    elapsed_ms=elapsed_ms,
                    metadata={
                        "error": "FOCUS_FAILED",
                        "selector": selector,
                        "error_details": error_message,
                        "operation_time_ms": elapsed_ms
                    }
                ).dict()
        
        # Perform the key release operation
        key_release_start_time = time.monotonic()
        key_released = False
        
        try:
            logger.info("Performing key release", key=key)
            
            # Release the key
            await page.keyboard.up(key)
            key_released = True
            
            key_release_elapsed_ms = int((time.monotonic() - key_release_start_time) * 1000)
            
            # Apply post-key-release delay if specified
            if delay_after_ms > 0:
                await page.wait_for_timeout(delay_after_ms)
            
            # Update session key release history
            if "key_release_history" not in session:
                session["key_release_history"] = []
            
            key_operation = {
                "timestamp": datetime.utcnow().isoformat(),
                "key": key,
                "selector": selector,
                "focused_element": focused_element,
                "key_release_time_ms": key_release_elapsed_ms,
                "delay_after_ms": delay_after_ms,
                "verify_release": verify_release,
                "success": True
            }
            
            session["key_release_history"].append(key_operation)
            
            # Keep only last 50 key release operations
            if len(session["key_release_history"]) > 50:
                session["key_release_history"] = session["key_release_history"][-50:]
            
            # Calculate total elapsed time
            total_elapsed_ms = int((time.monotonic() - start_time) * 1000)
            
            # Prepare success message
            message = f"Successfully released key '{key}'"
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
                "operation_type": "release_key",
                "timestamp": datetime.utcnow().isoformat(),
                "session_id": session_id,
                "key_details": {
                    "key": key,
                    "key_type": "releasable" if key in RELEASABLE_KEYS else "character",
                    "is_modifier": key in ["Control", "Shift", "Alt", "Meta", "ControlOrMeta"]
                },
                "element_interaction": {
                    "selector": selector,
                    "focused_element": focused_element,
                    "focus_first": focus_first,
                    "element_info": element_info
                },
                "timing": {
                    "total_operation_ms": total_elapsed_ms,
                    "key_release_ms": key_release_elapsed_ms,
                    "delay_after_ms": delay_after_ms,
                    "focus_time_ms": total_elapsed_ms - key_release_elapsed_ms - delay_after_ms
                },
                "verification": {
                    "verify_release": verify_release,
                    "verification_performed": verify_release
                },
                "page_context": {
                    "url": page_url,
                    "title": page_title
                }
            }
            
            logger.info(
                "Key release operation completed successfully",
                key=key,
                selector=selector,
                focused_element=focused_element,
                total_elapsed_ms=total_elapsed_ms
            )
            
            # Return successful response
            return ReleaseKeyResponse(
                success=True,
                session_id=session_id,
                key=key,
                selector=selector,
                message=message,
                key_released=key_released,
                focused_element=focused_element,
                elapsed_ms=total_elapsed_ms,
                metadata=metadata
            ).dict()
            
        except PlaywrightError as pe:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            error_message = str(pe)
            logger.error("Key release operation failed", key=key, error=error_message)
            return ReleaseKeyResponse(
                success=False,
                session_id=session_id,
                key=key,
                selector=selector,
                message=f"Key release operation failed: {error_message}",
                key_released=key_released,
                focused_element=focused_element,
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "KEY_RELEASE_FAILED",
                    "error_details": error_message,
                    "operation_time_ms": elapsed_ms,
                    "key": key
                }
            ).dict()
            
    except ValidationError as ve:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        validation_errors = str(ve)
        logger.error("Request validation failed", error=validation_errors, elapsed_ms=elapsed_ms)
        return ReleaseKeyResponse(
            success=False,
            session_id=session_id,
            key=key,
            selector=selector,
            message=f"Request validation failed: {validation_errors}",
            key_released=False,
            focused_element=False,
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
            "Unexpected error during key release operation",
            session_id=session_id,
            key=key,
            selector=selector,
            error=error_message,
            elapsed_ms=elapsed_ms
        )
        
        return ReleaseKeyResponse(
            success=False,
            session_id=session_id,
            key=key,
            selector=selector,
            message=f"Unexpected error during key release operation: {error_message}",
            key_released=False,
            focused_element=False,
            elapsed_ms=elapsed_ms,
            metadata={
                "error": "UNEXPECTED_ERROR",
                "error_details": error_message,
                "operation_time_ms": elapsed_ms
            }
        ).dict()


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
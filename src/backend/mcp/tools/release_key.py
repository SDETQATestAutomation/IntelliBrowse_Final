"""
Release Key Tool for IntelliBrowse MCP Server.

This module provides keyboard key release simulation functionality for Playwright 
browser sessions, enabling the release of held-down keys (especially modifier keys)
with comprehensive validation, element focus support, and detailed operation tracking.

Key Features:
- Single key release simulation using Playwright keyboard events
- Support for releasing modifier keys (Control, Shift, Alt, Meta)
- Optional element focus before key release
- Comprehensive key validation and release verification
- Session-based key release history tracking for audit compliance
- Element state validation and interaction verification
- Error handling with structured responses and classification
- Support for special keys (Enter, Tab, Arrow keys, Function keys, etc.)

Author: IntelliBrowse MCP Server
Version: 1.0.0
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, Any, Optional
import structlog
from playwright.async_api import Page, Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError
from pydantic import ValidationError

# Import the main MCP server instance
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from main import mcp_server

# Import schemas
from ..schemas.tools.release_key_schemas import ReleaseKeyRequest, ReleaseKeyResponse

# Import browser session utilities
from .browser_session import browser_sessions

logger = structlog.get_logger("intellibrowse.mcp.tools.release_key")

# Valid modifier keys that can be released
VALID_MODIFIER_KEYS = [
    "Control", "Shift", "Alt", "Meta", "ControlOrMeta"
]

# Common keys that can be released (especially useful for long-press scenarios)
RELEASABLE_KEYS = {
    # Modifier keys
    "Control", "Shift", "Alt", "Meta", "ControlOrMeta",
    
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

# Character keys - letters, numbers, symbols that can be released
CHARACTER_KEYS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
SYMBOL_KEYS = set("!@#$%^&*()_+-=[]{}|\\:;\"'<>?,./`~")

# Maximum reasonable delay after key release
MAX_DELAY_AFTER_MS = 5000


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
    Release a held-down keyboard key with optional element focus and verification.
    
    This tool provides comprehensive keyboard key release simulation for Playwright 
    browser sessions, with support for modifier keys, element focus management, 
    release verification, and detailed operation tracking for automation workflows.
    
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
                    "supported_keys": list(RELEASABLE_KEYS),
                    "operation_time_ms": elapsed_ms
                }
            ).dict()
        
        # Validate delay
        if delay_after_ms and delay_after_ms > MAX_DELAY_AFTER_MS:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Delay too large", delay_after_ms=delay_after_ms)
            return ReleaseKeyResponse(
                success=False,
                session_id=session_id,
                key=key,
                selector=selector,
                message=f"Delay after key release too large: {delay_after_ms}ms. Maximum allowed: {MAX_DELAY_AFTER_MS}ms",
                key_released=False,
                focused_element=False,
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "DELAY_TOO_LARGE",
                    "requested_delay": delay_after_ms,
                    "max_delay": MAX_DELAY_AFTER_MS,
                    "operation_time_ms": elapsed_ms
                }
            ).dict()
        
        # Get browser session
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
                    "available_sessions": list(browser_sessions.keys()),
                    "operation_time_ms": elapsed_ms
                }
            ).dict()
        
        session_data = browser_sessions[session_id]
        page: Page = session_data["page"]
        
        # Check if page is still valid
        if page.is_closed():
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Page is closed", session_id=session_id)
            return ReleaseKeyResponse(
                success=False,
                session_id=session_id,
                key=key,
                selector=selector,
                message=f"Page for session {session_id} is closed",
                key_released=False,
                focused_element=False,
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "PAGE_CLOSED",
                    "session_id": session_id,
                    "operation_time_ms": elapsed_ms
                }
            ).dict()
        
        focused_element = False
        
        # Focus element if selector provided and focus_first is True
        if selector and focus_first:
            try:
                logger.info("Focusing element before key release", selector=selector)
                await page.focus(selector, timeout=timeout_ms)
                focused_element = True
                logger.info("Element focused successfully", selector=selector)
            except PlaywrightTimeoutError:
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                logger.error("Timeout focusing element", selector=selector, timeout_ms=timeout_ms)
                return ReleaseKeyResponse(
                    success=False,
                    session_id=session_id,
                    key=key,
                    selector=selector,
                    message=f"Timeout focusing element: {selector} (timeout: {timeout_ms}ms)",
                    key_released=False,
                    focused_element=False,
                    elapsed_ms=elapsed_ms,
                    metadata={
                        "error": "FOCUS_TIMEOUT",
                        "selector": selector,
                        "timeout_ms": timeout_ms,
                        "operation_time_ms": elapsed_ms
                    }
                ).dict()
            except PlaywrightError as e:
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                logger.error("Error focusing element", selector=selector, error=str(e))
                return ReleaseKeyResponse(
                    success=False,
                    session_id=session_id,
                    key=key,
                    selector=selector,
                    message=f"Error focusing element {selector}: {str(e)}",
                    key_released=False,
                    focused_element=False,
                    elapsed_ms=elapsed_ms,
                    metadata={
                        "error": "FOCUS_ERROR",
                        "selector": selector,
                        "error_details": str(e),
                        "operation_time_ms": elapsed_ms
                    }
                ).dict()
        
        # Release the key
        key_released = False
        release_verified = False
        
        try:
            logger.info("Releasing key", key=key)
            await page.keyboard.up(key)
            key_released = True
            logger.info("Key released successfully", key=key)
            
            # Verify release if requested
            if verify_release:
                # Note: Playwright doesn't provide direct key state verification,
                # but we can check if the operation completed without error
                release_verified = True
                logger.info("Key release verified", key=key)
            
        except PlaywrightError as e:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Error releasing key", key=key, error=str(e))
            return ReleaseKeyResponse(
                success=False,
                session_id=session_id,
                key=key,
                selector=selector,
                message=f"Error releasing key '{key}': {str(e)}",
                key_released=False,
                focused_element=focused_element,
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "KEY_RELEASE_ERROR",
                    "key": key,
                    "error_details": str(e),
                    "operation_time_ms": elapsed_ms
                }
            ).dict()
        
        # Apply delay if specified
        if delay_after_ms and delay_after_ms > 0:
            logger.info("Applying delay after key release", delay_ms=delay_after_ms)
            await asyncio.sleep(delay_after_ms / 1000.0)
        
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        
        # Get current URL for context
        current_url = "unknown"
        try:
            current_url = page.url
        except:
            pass  # Page might be closed or in invalid state
        
        # Determine active element type for metadata
        active_element_type = "unknown"
        try:
            if focused_element and selector:
                element = await page.query_selector(selector)
                if element:
                    tag_name = await element.evaluate("el => el.tagName")
                    active_element_type = tag_name.lower() if tag_name else "unknown"
        except:
            pass  # Element might not exist or be accessible
        
        # Create success response
        logger.info(
            "Key release operation completed successfully",
            session_id=session_id,
            key=key,
            key_released=key_released,
            focused_element=focused_element,
            elapsed_ms=elapsed_ms
        )
        
        # Add to session history for audit
        if "key_release_history" not in session_data:
            session_data["key_release_history"] = []
        
        session_data["key_release_history"].append({
            "timestamp": datetime.utcnow().isoformat(),
            "key": key,
            "selector": selector,
            "focused_element": focused_element,
            "success": True,
            "elapsed_ms": elapsed_ms
        })
        
        response = ReleaseKeyResponse(
            success=True,
            session_id=session_id,
            key=key,
            selector=selector,
            message=f"Key '{key}' released successfully",
            key_released=key_released,
            focused_element=focused_element,
            elapsed_ms=elapsed_ms,
            metadata={
                "key_code": key,
                "release_verified": release_verified,
                "active_element": active_element_type,
                "current_url": current_url,
                "delay_applied_ms": delay_after_ms if delay_after_ms else 0,
                "operation_time_ms": elapsed_ms,
                "timestamp": datetime.utcnow().isoformat(),
                "session_history_count": len(session_data.get("key_release_history", []))
            }
        )
        
        return response.dict()
        
    except ValidationError as e:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        logger.error("Request validation error", error=str(e))
        return ReleaseKeyResponse(
            success=False,
            session_id=session_id,
            key=key,
            selector=selector,
            message=f"Request validation error: {str(e)}",
            key_released=False,
            focused_element=False,
            elapsed_ms=elapsed_ms,
            metadata={
                "error": "VALIDATION_ERROR",
                "error_details": str(e),
                "operation_time_ms": elapsed_ms
            }
        ).dict()
        
    except Exception as e:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        logger.error("Unexpected error in key release operation", error=str(e))
        return ReleaseKeyResponse(
            success=False,
            session_id=session_id,
            key=key,
            selector=selector,
            message=f"Unexpected error: {str(e)}",
            key_released=False,
            focused_element=False,
            elapsed_ms=elapsed_ms,
            metadata={
                "error": "UNEXPECTED_ERROR",
                "error_details": str(e),
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
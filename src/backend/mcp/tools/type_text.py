"""
Type Text Tool for IntelliBrowse MCP Server.

This module provides character-by-character text typing functionality for Playwright 
browser sessions, enabling realistic user input simulation with keystroke timing,
comprehensive validation, and detailed operation tracking for automation workflows.

Key Features:
- Character-by-character typing simulation using Playwright keyboard events
- Configurable keystroke delays for realistic typing behavior
- Comprehensive element validation (type, editable state, visibility)
- Element clearing before typing with verification
- Detailed operation metadata and timing information
- Session-based typing history tracking for audit compliance
- Error handling with structured responses and classification
- Support for all typeable HTML input types and contentEditable elements

Author: IntelliBrowse MCP Server
Version: 1.0.0
"""

import time
from datetime import datetime
from typing import Dict, Any, Optional
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
    from schemas.tools.type_text_schemas import TypeTextRequest, TypeTextResponse
except ImportError:
    # Fallback for when running directly from mcp directory
    from schemas.tools.type_text_schemas import TypeTextRequest, TypeTextResponse

# Import browser session utilities - use absolute import
try:
    from tools.browser_session import browser_sessions
except ImportError:
    # Fallback for when running directly from mcp directory
    from tools.browser_session import browser_sessions

logger = structlog.get_logger("intellibrowse.mcp.tools.type_text")

# Valid input element types that can accept text typing
TYPEABLE_INPUT_TYPES = [
    "text", "email", "password", "search", "url", "tel", "number",
    "date", "datetime-local", "month", "week", "time", "textarea"
]

# Maximum reasonable typing delay to prevent excessive operation times
MAX_TYPING_DELAY_MS = 1000

# Minimum and maximum text length limits for safety
MIN_TEXT_LENGTH = 0
MAX_TEXT_LENGTH = 10000


@mcp_server.tool()
async def type_text(
    session_id: str,
    selector: str,
    text: str,
    timeout_ms: Optional[int] = 5000,
    clear_before: Optional[bool] = True,
    delay_ms: Optional[int] = 0
) -> Dict[str, Any]:
    """
    Type text character by character into an input or editable element.
    
    This tool provides realistic text typing simulation for Playwright browser sessions,
    with character-by-character input, keystroke timing control, element validation,
    and comprehensive operation tracking for automation workflows that require
    realistic user input behavior.
    
    Args:
        session_id: Browser session identifier for the target session
        selector: CSS selector targeting the element to type into
        text: Text content to type character by character (supports unicode characters)
        timeout_ms: Maximum time to wait for element availability in milliseconds (default: 5000)
        clear_before: Whether to clear existing content before typing (default: True)
        delay_ms: Delay between individual keystrokes in milliseconds (default: 0, max: 1000)
    
    Returns:
        Dict containing typing operation status, timing, and comprehensive metadata
    """
    start_time = time.monotonic()
    
    logger.info(
        "Starting type text operation",
        session_id=session_id,
        selector=selector,
        text_length=len(text),
        timeout_ms=timeout_ms,
        clear_before=clear_before,
        delay_ms=delay_ms
    )
    
    try:
        # Validate request using Pydantic schema
        request = TypeTextRequest(
            session_id=session_id,
            selector=selector,
            text=text,
            timeout_ms=timeout_ms,
            clear_before=clear_before,
            delay_ms=delay_ms
        )
        
        # Validate text length
        if len(text) > MAX_TEXT_LENGTH:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Text too long", text_length=len(text), max_length=MAX_TEXT_LENGTH)
            return TypeTextResponse(
                success=False,
                selector=selector,
                text=text,
                message=f"Text length {len(text)} exceeds maximum allowed length {MAX_TEXT_LENGTH}",
                cleared_before=False,
                characters_typed=0,
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "TEXT_TOO_LONG",
                    "text_length": len(text),
                    "max_length": MAX_TEXT_LENGTH,
                    "operation_time_ms": elapsed_ms
                }
            ).dict()
        
        # Validate typing delay
        if delay_ms > MAX_TYPING_DELAY_MS:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Typing delay too high", delay_ms=delay_ms, max_delay=MAX_TYPING_DELAY_MS)
            return TypeTextResponse(
                success=False,
                selector=selector,
                text=text,
                message=f"Typing delay {delay_ms}ms exceeds maximum allowed delay {MAX_TYPING_DELAY_MS}ms",
                cleared_before=False,
                characters_typed=0,
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "DELAY_TOO_HIGH",
                    "delay_ms": delay_ms,
                    "max_delay_ms": MAX_TYPING_DELAY_MS,
                    "operation_time_ms": elapsed_ms
                }
            ).dict()
        
        # Validate selector format (basic check)
        if not selector or not selector.strip():
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Empty selector provided")
            return TypeTextResponse(
                success=False,
                selector=selector,
                text=text,
                message="Selector cannot be empty",
                cleared_before=False,
                characters_typed=0,
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "INVALID_SELECTOR",
                    "error_details": "Empty or whitespace-only selector",
                    "operation_time_ms": elapsed_ms
                }
            ).dict()
        
        # Check if session exists
        if session_id not in browser_sessions:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Browser session not found", session_id=session_id)
            return TypeTextResponse(
                success=False,
                selector=selector,
                text=text,
                message=f"Browser session {session_id} not found",
                cleared_before=False,
                characters_typed=0,
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
            return TypeTextResponse(
                success=False,
                selector=selector,
                text=text,
                message=f"Page is not active or accessible: {str(e)}",
                cleared_before=False,
                characters_typed=0,
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "PAGE_NOT_ACTIVE",
                    "error_details": str(e),
                    "operation_time_ms": elapsed_ms
                }
            ).dict()
        
        # Locate and validate the element
        try:
            logger.info("Locating element", selector=selector, timeout_ms=timeout_ms)
            
            # Wait for element to be present and visible
            element = await page.wait_for_selector(
                selector,
                timeout=timeout_ms,
                state="visible"
            )
            
            if not element:
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                logger.error("Element not found", selector=selector)
                return TypeTextResponse(
                    success=False,
                    selector=selector,
                    text=text,
                    message=f"Element not found: {selector}",
                    cleared_before=False,
                    characters_typed=0,
                    elapsed_ms=elapsed_ms,
                    metadata={
                        "error": "ELEMENT_NOT_FOUND",
                        "selector": selector,
                        "timeout_ms": timeout_ms,
                        "operation_time_ms": elapsed_ms
                    }
                ).dict()
            
            # Get element properties for validation and metadata
            element_tag = await element.evaluate("el => el.tagName.toLowerCase()")
            element_type = await element.evaluate("el => el.type || ''")
            element_readonly = await element.evaluate("el => el.readOnly || false")
            element_disabled = await element.evaluate("el => el.disabled || false")
            element_visible = await element.is_visible()
            element_enabled = await element.is_enabled()
            
            # Get current value before typing
            try:
                current_value = await element.evaluate("el => el.value || el.textContent || ''")
            except PlaywrightError:
                current_value = ""
            
            # Validate element is typeable
            is_typeable_input = (
                element_tag in ["input", "textarea"] or
                (element_tag == "input" and element_type.lower() in TYPEABLE_INPUT_TYPES) or
                await element.evaluate("el => el.isContentEditable")
            )
            
            if not is_typeable_input:
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                logger.error("Element is not typeable", 
                           selector=selector, tag=element_tag, type=element_type)
                return TypeTextResponse(
                    success=False,
                    selector=selector,
                    text=text,
                    message=f"Element {selector} is not typeable (tag: {element_tag}, type: {element_type})",
                    cleared_before=False,
                    characters_typed=0,
                    elapsed_ms=elapsed_ms,
                    metadata={
                        "error": "ELEMENT_NOT_TYPEABLE",
                        "element_tag": element_tag,
                        "element_type": element_type,
                        "is_editable": await element.evaluate("el => el.isContentEditable"),
                        "operation_time_ms": elapsed_ms
                    }
                ).dict()
            
            # Check if element is editable
            if element_readonly or element_disabled or not element_enabled:
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                logger.error("Element is not editable", 
                           selector=selector, readonly=element_readonly, disabled=element_disabled)
                return TypeTextResponse(
                    success=False,
                    selector=selector,
                    text=text,
                    message=f"Element {selector} is not editable (readonly: {element_readonly}, disabled: {element_disabled})",
                    cleared_before=False,
                    characters_typed=0,
                    elapsed_ms=elapsed_ms,
                    metadata={
                        "error": "ELEMENT_NOT_EDITABLE",
                        "element_readonly": element_readonly,
                        "element_disabled": element_disabled,
                        "element_enabled": element_enabled,
                        "operation_time_ms": elapsed_ms
                    }
                ).dict()
            
            # Get element bounds for metadata
            try:
                element_bounds = await element.bounding_box()
                bounds_metadata = element_bounds if element_bounds else {"x": 0, "y": 0, "width": 0, "height": 0}
            except PlaywrightError:
                bounds_metadata = {"x": 0, "y": 0, "width": 0, "height": 0}
            
            # Focus the element before typing
            try:
                await element.focus()
                logger.info("Element focused for typing", selector=selector)
            except PlaywrightError as e:
                logger.warning("Failed to focus element", selector=selector, error=str(e))
            
            # Perform typing operation
            typing_start_time = time.monotonic()
            
            try:
                logger.info("Performing typing operation", 
                          selector=selector, clear_before=clear_before, text_length=len(text))
                
                # Clear element first if requested
                actual_cleared = False
                if clear_before and current_value:
                    await element.clear(timeout=timeout_ms)
                    actual_cleared = True
                    logger.info("Element cleared before typing", selector=selector)
                
                # Type the text character by character
                characters_typed = 0
                if text:  # Only type if text is not empty
                    if delay_ms > 0:
                        # Character-by-character typing with delay
                        for char in text:
                            await page.keyboard.type(char)
                            characters_typed += 1
                            if delay_ms > 0:
                                await page.wait_for_timeout(delay_ms)
                    else:
                        # Use Playwright's optimized type method for speed
                        await element.type(text, timeout=timeout_ms)
                        characters_typed = len(text)
                    
                    logger.info("Text typing completed", 
                              selector=selector, characters_typed=characters_typed)
                
                # Calculate timing
                typing_elapsed_ms = int((time.monotonic() - typing_start_time) * 1000)
                total_elapsed_ms = int((time.monotonic() - start_time) * 1000)
                
                # Verify the typing operation by checking final value
                try:
                    final_value = await element.evaluate("el => el.value || el.textContent || ''")
                    typing_successful = (final_value.endswith(text) if text else 
                                       (final_value != current_value or actual_cleared))
                except PlaywrightError:
                    final_value = ""
                    typing_successful = True  # Assume success if we can't verify
                
                # Collect comprehensive metadata
                try:
                    page_title = await page.title()
                    page_url = page.url
                except PlaywrightError:
                    page_title = "Unknown"
                    page_url = "Unknown"
                
                metadata = {
                    "element_tag": element_tag,
                    "element_type": element_type,
                    "element_bounds": bounds_metadata,
                    "element_visible": element_visible,
                    "element_enabled": element_enabled,
                    "element_readonly": element_readonly,
                    "element_disabled": element_disabled,
                    "previous_value": current_value,
                    "final_value": final_value,
                    "text_length": len(text),
                    "typing_verified": typing_successful,
                    "typing_delay_ms": delay_ms,
                    "typing_operation_time_ms": typing_elapsed_ms,
                    "total_operation_time_ms": total_elapsed_ms,
                    "page_title": page_title,
                    "page_url": page_url,
                    "session_id": session_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "browser_type": session.get("browser_type", "unknown")
                }
                
                # Update session metadata with typing history
                if "typing_history" not in session:
                    session["typing_history"] = []
                
                session["typing_history"].append({
                    "selector": selector,
                    "text_length": len(text),
                    "characters_typed": characters_typed,
                    "timestamp": datetime.utcnow().isoformat(),
                    "success": typing_successful,
                    "cleared_before": actual_cleared,
                    "delay_ms": delay_ms,
                    "elapsed_ms": total_elapsed_ms
                })
                
                # Keep only last 20 typing entries
                session["typing_history"] = session["typing_history"][-20:]
                
                # Create success message
                message = f"Text typed successfully"
                if actual_cleared:
                    message += " (cleared first)"
                if delay_ms > 0:
                    message += f" with {delay_ms}ms keystroke delay"
                
                # Log successful typing for audit compliance
                logger.info(
                    "Typing operation completed successfully",
                    session_id=session_id,
                    selector=selector,
                    text_length=len(text),
                    characters_typed=characters_typed,
                    cleared_before=actual_cleared,
                    elapsed_ms=total_elapsed_ms,
                    typing_verified=typing_successful
                )
                
                # Return successful response
                return TypeTextResponse(
                    success=True,
                    selector=selector,
                    text=text,
                    message=message,
                    cleared_before=actual_cleared,
                    characters_typed=characters_typed,
                    elapsed_ms=total_elapsed_ms,
                    metadata=metadata
                ).dict()
                
            except PlaywrightTimeoutError as te:
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                logger.error("Typing operation timed out", 
                           selector=selector, timeout_ms=timeout_ms, error=str(te))
                return TypeTextResponse(
                    success=False,
                    selector=selector,
                    text=text,
                    message=f"Typing operation timed out after {timeout_ms}ms: {str(te)}",
                    cleared_before=False,
                    characters_typed=0,
                    elapsed_ms=elapsed_ms,
                    metadata={
                        "error": "TYPING_TIMEOUT",
                        "timeout_ms": timeout_ms,
                        "error_details": str(te),
                        "operation_time_ms": elapsed_ms
                    }
                ).dict()
                
            except PlaywrightError as pe:
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                error_message = str(pe)
                logger.error("Typing operation failed", 
                           selector=selector, error=error_message)
                return TypeTextResponse(
                    success=False,
                    selector=selector,
                    text=text,
                    message=f"Typing operation failed: {error_message}",
                    cleared_before=False,
                    characters_typed=0,
                    elapsed_ms=elapsed_ms,
                    metadata={
                        "error": "TYPING_OPERATION_FAILED",
                        "error_details": error_message,
                        "operation_time_ms": elapsed_ms,
                        "element_tag": element_tag,
                        "element_type": element_type
                    }
                ).dict()
                
        except PlaywrightTimeoutError as te:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Element location timed out", 
                       selector=selector, timeout_ms=timeout_ms, error=str(te))
            return TypeTextResponse(
                success=False,
                selector=selector,
                text=text,
                message=f"Element not found within {timeout_ms}ms: {selector}",
                cleared_before=False,
                characters_typed=0,
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "ELEMENT_LOCATION_TIMEOUT",
                    "timeout_ms": timeout_ms,
                    "error_details": str(te),
                    "operation_time_ms": elapsed_ms
                }
            ).dict()
            
        except PlaywrightError as pe:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            error_message = str(pe)
            logger.error("Element location failed", 
                       selector=selector, error=error_message)
            return TypeTextResponse(
                success=False,
                selector=selector,
                text=text,
                message=f"Element location failed: {error_message}",
                cleared_before=False,
                characters_typed=0,
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "ELEMENT_LOCATION_FAILED",
                    "error_details": error_message,
                    "operation_time_ms": elapsed_ms
                }
            ).dict()
            
    except ValidationError as ve:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        validation_errors = str(ve)
        logger.error("Request validation failed", error=validation_errors, elapsed_ms=elapsed_ms)
        return TypeTextResponse(
            success=False,
            selector=selector,
            text=text,
            message=f"Request validation failed: {validation_errors}",
            cleared_before=False,
            characters_typed=0,
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
            "Unexpected error during typing operation",
            session_id=session_id,
            selector=selector,
            error=error_message,
            elapsed_ms=elapsed_ms
        )
        
        return TypeTextResponse(
            success=False,
            selector=selector,
            text=text,
            message=f"Unexpected error during typing operation: {error_message}",
            cleared_before=False,
            characters_typed=0,
            elapsed_ms=elapsed_ms,
            metadata={
                "error": "UNEXPECTED_ERROR",
                "error_details": error_message,
                "operation_time_ms": elapsed_ms
            }
        ).dict()


@mcp_server.prompt()
def type_text_prompt(field_name: str, input_text: str, typing_speed: str = "normal") -> str:
    """
    Returns a prompt guiding the LLM to type text into a specific form element.
    
    This prompt template helps users understand how to perform realistic text typing
    operations and provides context for form automation workflows that require
    character-by-character input simulation.
    
    Args:
        field_name: The name or description of the field to type into
        input_text: The text to be typed into the field
        typing_speed: The speed of typing (slow, normal, fast)
    
    Returns:
        Formatted prompt string for text typing operation guidance
    """
    speed_delays = {
        "slow": "100ms",
        "normal": "50ms", 
        "fast": "10ms"
    }
    
    delay_description = speed_delays.get(typing_speed, "50ms")
    
    return f"""Type '{input_text}' into the '{field_name}' field using realistic keystroke simulation.

This will perform a character-by-character typing operation which can be used for:
- Realistic user input simulation for forms with real-time validation
- Testing input event handlers and keystroke-based functionality  
- Simulating natural typing behavior for user experience testing
- Form filling with typing delays for fields that respond to keypress events
- Search suggestions and autocomplete testing with progressive input

The typing operation includes comprehensive validation and features:
- Element existence and visibility verification
- Input type compatibility checking (text, email, password, etc.)
- Editable state validation (not readonly/disabled)
- Optional content clearing before typing
- Configurable keystroke delay ({delay_description} for {typing_speed} speed)
- Character-by-character progress tracking
- Final value verification and typing success validation

Typing behavior details:
- Speed: {typing_speed.title()} typing with {delay_description} delay between keystrokes
- Method: Character-by-character simulation using Playwright keyboard events
- Focus: Automatic element focusing before typing begins
- Verification: Post-typing validation to ensure text was entered correctly

Best practices for reliable text typing:
- Use stable selectors (ID, data attributes) when possible
- Allow sufficient timeout for dynamic form elements
- Consider clearing existing content for clean input
- Use appropriate typing speed for forms with validation
- Verify typing success through subsequent assertions or form submission

The operation provides detailed metadata including typing timing, character count, element properties, and operation verification for comprehensive test reporting.""" 
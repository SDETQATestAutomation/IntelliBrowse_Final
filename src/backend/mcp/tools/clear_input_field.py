"""
Clear Input Field Tool for IntelliBrowse MCP Server.

This module provides input field clearing functionality for Playwright browser sessions,
enabling form reset workflows with comprehensive error handling, validation,
and metadata collection for audit compliance.
"""

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

# Import schemas - use absolute import to avoid relative import issues
sys.path.append(str(Path(__file__).parent.parent / "schemas"))
from tool_schemas import ClearInputFieldRequest, ClearInputFieldResponse

# Import browser session utilities - use absolute import
sys.path.append(str(Path(__file__).parent))
from browser_session import browser_sessions

logger = structlog.get_logger("intellibrowse.mcp.tools.clear_input_field")

# Valid input element types that can accept clearing operations
CLEARABLE_INPUT_TYPES = [
    "text", "email", "password", "search", "url", "tel", "number", 
    "date", "datetime-local", "month", "week", "time", "textarea"
]

# Common selector validation patterns
SELECTOR_PATTERNS = {
    "id": r"^#[\w-]+$",
    "class": r"^\.[\w-]+$",  
    "attribute": r"^\[[\w-]+(=.*)?\]$",
    "tag": r"^[a-zA-Z]+$"
}


@mcp_server.tool()
async def clear_input_field(
    session_id: str,
    selector: str,
    timeout_ms: Optional[int] = 5000,
    force: Optional[bool] = False,
    verify_cleared: Optional[bool] = True
) -> Dict[str, Any]:
    """
    Clear the value of a specified input or textarea field.
    
    This tool provides comprehensive form field clearing functionality for Playwright 
    browser sessions, with element validation, state management, and detailed 
    operation tracking for automation workflows.
    
    Args:
        session_id: Browser session identifier for the target session
        selector: CSS selector targeting the element to clear (supports ID, class, attribute, complex selectors)
        timeout_ms: Maximum time to wait for element availability in milliseconds (default: 5000)
        force: Force clearing even if element appears non-editable (default: False)
        verify_cleared: Verify that the field was actually cleared after the operation (default: True)
    
    Returns:
        Dict containing clear operation status, timing, and comprehensive metadata
    """
    start_time = time.monotonic()
    
    logger.info(
        "Starting input field clear operation",
        session_id=session_id,
        selector=selector,
        timeout_ms=timeout_ms,
        force=force,
        verify_cleared=verify_cleared
    )
    
    try:
        # Validate request using Pydantic schema
        request = ClearInputFieldRequest(
            session_id=session_id,
            selector=selector,
            timeout_ms=timeout_ms,
            force=force,
            verify_cleared=verify_cleared
        )
        
        # Validate selector format (basic check)
        if not selector or not selector.strip():
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Empty selector provided")
            return ClearInputFieldResponse(
                success=False,
                selector=selector,
                message="Selector cannot be empty",
                was_cleared=False,
                original_value="",
                final_value="",
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
            return ClearInputFieldResponse(
                success=False,
                selector=selector,
                message=f"Browser session {session_id} not found",
                was_cleared=False,
                original_value="",
                final_value="",
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
            return ClearInputFieldResponse(
                success=False,
                selector=selector,
                message=f"Page is not active or accessible: {str(e)}",
                was_cleared=False,
                original_value="",
                final_value="",
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
            
            # Wait for element to be present
            element = await page.wait_for_selector(
                selector,
                timeout=timeout_ms,
                state="attached"
            )
            
            if not element:
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                logger.error("Element not found", selector=selector)
                return ClearInputFieldResponse(
                    success=False,
                    selector=selector,
                    message=f"Element not found: {selector}",
                    was_cleared=False,
                    original_value="",
                    final_value="",
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
            
            # Get current value before clearing
            try:
                original_value = await element.evaluate("el => el.value || el.textContent || ''")
            except PlaywrightError:
                original_value = ""
            
            logger.info(
                "Element located and analyzed",
                selector=selector,
                element_tag=element_tag,
                element_type=element_type,
                element_readonly=element_readonly,
                element_disabled=element_disabled,
                element_visible=element_visible,
                element_enabled=element_enabled,
                original_value_length=len(str(original_value))
            )
            
            # Validate element state unless force is enabled
            if not force:
                if not element_visible:
                    elapsed_ms = int((time.monotonic() - start_time) * 1000)
                    logger.error("Element is not visible", selector=selector)
                    return ClearInputFieldResponse(
                        success=False,
                        selector=selector,
                        message=f"Element is not visible: {selector}",
                        was_cleared=False,
                        original_value=str(original_value),
                        final_value=str(original_value),
                        elapsed_ms=elapsed_ms,
                        metadata={
                            "error": "ELEMENT_NOT_VISIBLE",
                            "element_tag": element_tag,
                            "element_type": element_type,
                            "operation_time_ms": elapsed_ms
                        }
                    ).dict()
                
                if not element_enabled:
                    elapsed_ms = int((time.monotonic() - start_time) * 1000)
                    logger.error("Element is not enabled", selector=selector)
                    return ClearInputFieldResponse(
                        success=False,
                        selector=selector,
                        message=f"Element is not enabled (disabled): {selector}",
                        was_cleared=False,
                        original_value=str(original_value),
                        final_value=str(original_value),
                        elapsed_ms=elapsed_ms,
                        metadata={
                            "error": "ELEMENT_NOT_ENABLED",
                            "element_tag": element_tag,
                            "element_type": element_type,
                            "element_disabled": element_disabled,
                            "operation_time_ms": elapsed_ms
                        }
                    ).dict()
                
                if element_readonly:
                    elapsed_ms = int((time.monotonic() - start_time) * 1000)
                    logger.error("Element is readonly", selector=selector)
                    return ClearInputFieldResponse(
                        success=False,
                        selector=selector,
                        message=f"Element is readonly and cannot be cleared: {selector}",
                        was_cleared=False,
                        original_value=str(original_value),
                        final_value=str(original_value),
                        elapsed_ms=elapsed_ms,
                        metadata={
                            "error": "ELEMENT_READONLY",
                            "element_tag": element_tag,
                            "element_type": element_type,
                            "element_readonly": element_readonly,
                            "operation_time_ms": elapsed_ms
                        }
                    ).dict()
                
                # Check if element is clearable
                if element_tag not in ["input", "textarea"] and not await element.evaluate("el => el.contentEditable === 'true'"):
                    elapsed_ms = int((time.monotonic() - start_time) * 1000)
                    logger.error("Element is not clearable", selector=selector, element_tag=element_tag)
                    return ClearInputFieldResponse(
                        success=False,
                        selector=selector,
                        message=f"Element is not clearable (unsupported element type): {element_tag}",
                        was_cleared=False,
                        original_value=str(original_value),
                        final_value=str(original_value),
                        elapsed_ms=elapsed_ms,
                        metadata={
                            "error": "ELEMENT_NOT_CLEARABLE",
                            "element_tag": element_tag,
                            "element_type": element_type,
                            "supported_elements": ["input", "textarea", "contenteditable"],
                            "operation_time_ms": elapsed_ms
                        }
                    ).dict()
                
                # For input elements, check if type is clearable
                if element_tag == "input" and element_type not in CLEARABLE_INPUT_TYPES:
                    elapsed_ms = int((time.monotonic() - start_time) * 1000)
                    logger.error("Input type is not clearable", selector=selector, element_type=element_type)
                    return ClearInputFieldResponse(
                        success=False,
                        selector=selector,
                        message=f"Input type '{element_type}' is not clearable",
                        was_cleared=False,
                        original_value=str(original_value),
                        final_value=str(original_value),
                        elapsed_ms=elapsed_ms,
                        metadata={
                            "error": "INPUT_TYPE_NOT_CLEARABLE",
                            "element_tag": element_tag,
                            "element_type": element_type,
                            "clearable_types": CLEARABLE_INPUT_TYPES,
                            "operation_time_ms": elapsed_ms
                        }
                    ).dict()
            
            # Perform the clear operation
            clear_start_time = time.monotonic()
            
            try:
                logger.info("Performing clear operation", selector=selector)
                
                # Use fill with empty string to clear the field
                await element.fill('', timeout=timeout_ms)
                
                clear_elapsed_ms = int((time.monotonic() - clear_start_time) * 1000)
                
                # Get the final value after clearing
                final_value = ""
                if verify_cleared:
                    try:
                        final_value = await element.evaluate("el => el.value || el.textContent || ''")
                    except PlaywrightError:
                        final_value = ""
                
                # Check if clearing was successful
                was_cleared = True
                clear_verification_status = "not_verified"
                
                if verify_cleared:
                    was_cleared = (final_value == "" or final_value.strip() == "")
                    clear_verification_status = "verified" if was_cleared else "failed"
                    
                    if not was_cleared:
                        logger.warning(
                            "Clear operation may have failed verification",
                            selector=selector,
                            original_value=original_value,
                            final_value=final_value
                        )
                
                # Update session clear history
                if "clear_history" not in session:
                    session["clear_history"] = []
                
                clear_operation = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "selector": selector,
                    "original_value": str(original_value),
                    "final_value": str(final_value),
                    "was_cleared": was_cleared,
                    "clear_time_ms": clear_elapsed_ms,
                    "verification": clear_verification_status,
                    "element_tag": element_tag,
                    "element_type": element_type
                }
                
                session["clear_history"].append(clear_operation)
                
                # Keep only last 20 clear operations
                if len(session["clear_history"]) > 20:
                    session["clear_history"] = session["clear_history"][-20:]
                
                # Calculate total elapsed time
                total_elapsed_ms = int((time.monotonic() - start_time) * 1000)
                
                # Prepare success message
                if was_cleared:
                    message = f"Successfully cleared field '{selector}'"
                    if original_value:
                        message += f" (removed '{original_value[:50]}{'...' if len(str(original_value)) > 50 else ''}')"
                else:
                    message = f"Clear operation completed for '{selector}' but verification failed"
                
                # Collect comprehensive metadata
                metadata = {
                    "operation_type": "clear_input_field",
                    "timestamp": datetime.utcnow().isoformat(),
                    "session_id": session_id,
                    "element_analysis": {
                        "tag": element_tag,
                        "type": element_type,
                        "readonly": element_readonly,
                        "disabled": element_disabled,
                        "visible": element_visible,
                        "enabled": element_enabled
                    },
                    "clear_operation": {
                        "original_value_length": len(str(original_value)),
                        "clear_time_ms": clear_elapsed_ms,
                        "verification_performed": verify_cleared,
                        "verification_status": clear_verification_status
                    },
                    "timing": {
                        "total_operation_ms": total_elapsed_ms,
                        "clear_operation_ms": clear_elapsed_ms,
                        "element_location_ms": total_elapsed_ms - clear_elapsed_ms
                    },
                    "page_context": {
                        "url": await page.url(),
                        "title": await page.title()
                    }
                }
                
                logger.info(
                    "Clear operation completed successfully",
                    selector=selector,
                    was_cleared=was_cleared,
                    original_value_length=len(str(original_value)),
                    final_value_length=len(str(final_value)),
                    total_elapsed_ms=total_elapsed_ms
                )
                
                # Return successful response
                return ClearInputFieldResponse(
                    success=True,
                    selector=selector,
                    message=message,
                    was_cleared=was_cleared,
                    original_value=str(original_value),
                    final_value=str(final_value),
                    elapsed_ms=total_elapsed_ms,
                    metadata=metadata
                ).dict()
                
            except PlaywrightTimeoutError as te:
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                logger.error("Clear operation timed out", 
                           selector=selector, timeout_ms=timeout_ms, error=str(te))
                return ClearInputFieldResponse(
                    success=False,
                    selector=selector,
                    message=f"Clear operation timed out after {timeout_ms}ms: {str(te)}",
                    was_cleared=False,
                    original_value=str(original_value),
                    final_value=str(original_value),
                    elapsed_ms=elapsed_ms,
                    metadata={
                        "error": "CLEAR_TIMEOUT",
                        "timeout_ms": timeout_ms,
                        "error_details": str(te),
                        "operation_time_ms": elapsed_ms
                    }
                ).dict()
                
            except PlaywrightError as pe:
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                error_message = str(pe)
                logger.error("Clear operation failed", 
                           selector=selector, error=error_message)
                return ClearInputFieldResponse(
                    success=False,
                    selector=selector,
                    message=f"Clear operation failed: {error_message}",
                    was_cleared=False,
                    original_value=str(original_value),
                    final_value=str(original_value),
                    elapsed_ms=elapsed_ms,
                    metadata={
                        "error": "CLEAR_OPERATION_FAILED",
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
            return ClearInputFieldResponse(
                success=False,
                selector=selector,
                message=f"Element not found within {timeout_ms}ms: {selector}",
                was_cleared=False,
                original_value="",
                final_value="",
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
            return ClearInputFieldResponse(
                success=False,
                selector=selector,
                message=f"Element location failed: {error_message}",
                was_cleared=False,
                original_value="",
                final_value="",
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
        return ClearInputFieldResponse(
            success=False,
            selector=selector,
            message=f"Request validation failed: {validation_errors}",
            was_cleared=False,
            original_value="",
            final_value="",
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
            "Unexpected error during clear operation",
            session_id=session_id,
            selector=selector,
            error=error_message,
            elapsed_ms=elapsed_ms
        )
        
        return ClearInputFieldResponse(
            success=False,
            selector=selector,
            message=f"Unexpected error during clear operation: {error_message}",
            was_cleared=False,
            original_value="",
            final_value="",
            elapsed_ms=elapsed_ms,
            metadata={
                "error": "UNEXPECTED_ERROR",
                "error_details": error_message,
                "operation_time_ms": elapsed_ms
            }
        ).dict()


@mcp_server.prompt()
def clear_input_field_prompt(field_name: str, field_type: str = "input") -> str:
    """
    Returns a prompt guiding the LLM to clear the content of a specific form field.
    
    This prompt template helps users understand how to perform field clearing
    operations and provides context for form reset workflows.
    
    Args:
        field_name: The name or description of the field to clear
        field_type: The type of field being cleared (input, textarea, etc.)
    
    Returns:
        Formatted prompt string for input field clearing operation guidance
    """
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

The operation provides detailed metadata including clearing timing, original value tracking, element properties, and verification status for comprehensive test reporting."""

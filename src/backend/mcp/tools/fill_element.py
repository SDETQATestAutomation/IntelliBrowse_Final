"""
Fill Element Tool for IntelliBrowse MCP Server.

This module provides element filling functionality for Playwright browser sessions,
enabling form automation workflows with comprehensive error handling, validation,
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
from tool_schemas import FillElementRequest, FillElementResponse

# Import browser session utilities - use absolute import
sys.path.append(str(Path(__file__).parent))
from browser_session import browser_sessions

logger = structlog.get_logger("intellibrowse.mcp.tools.fill_element")

# Valid input element types that can accept text input
FILLABLE_INPUT_TYPES = [
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
async def fill_element(
    session_id: str,
    selector: str,
    value: str,
    timeout_ms: Optional[int] = 5000,
    clear_first: Optional[bool] = True,
    delay_ms: Optional[int] = 0,
    force: Optional[bool] = False
) -> Dict[str, Any]:
    """
    Fill an input or editable element with text content.
    
    This tool provides comprehensive form field filling functionality for Playwright 
    browser sessions, with element validation, content management, and detailed 
    operation tracking for automation workflows.
    
    Args:
        session_id: Browser session identifier for the target session
        selector: CSS selector targeting the element to fill (supports ID, class, attribute, complex selectors)
        value: Text content to fill into the element (supports empty string for clearing)
        timeout_ms: Maximum time to wait for element availability in milliseconds (default: 5000)
        clear_first: Whether to clear existing content before filling (default: True)
        delay_ms: Post-fill delay in milliseconds for UI responsiveness (default: 0)
        force: Force filling even if element appears non-editable (default: False)
    
    Returns:
        Dict containing fill operation status, timing, and comprehensive metadata
    """
    start_time = time.monotonic()
    
    logger.info(
        "Starting element fill operation",
        session_id=session_id,
        selector=selector,
        value_length=len(value),
        timeout_ms=timeout_ms,
        clear_first=clear_first,
        delay_ms=delay_ms,
        force=force
    )
    
    try:
        # Validate request using Pydantic schema
        request = FillElementRequest(
            session_id=session_id,
            selector=selector,
            value=value,
            timeout_ms=timeout_ms,
            clear_first=clear_first,
            delay_ms=delay_ms,
            force=force
        )
        
        # Validate selector format (basic check)
        if not selector or not selector.strip():
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Empty selector provided")
            return FillElementResponse(
                success=False,
                selector=selector,
                value=value,
                message="Selector cannot be empty",
                cleared_first=False,
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
            return FillElementResponse(
                success=False,
                selector=selector,
                value=value,
                message=f"Browser session {session_id} not found",
                cleared_first=False,
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
            return FillElementResponse(
                success=False,
                selector=selector,
                value=value,
                message=f"Page is not active or accessible: {str(e)}",
                cleared_first=False,
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
                return FillElementResponse(
                    success=False,
                    selector=selector,
                    value=value,
                    message=f"Element not found: {selector}",
                    cleared_first=False,
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
            
            # Get current value before filling
            try:
                current_value = await element.evaluate("el => el.value || el.textContent || ''")
            except PlaywrightError:
                current_value = ""
            
            # Validate element is fillable
            is_fillable_input = (
                element_tag in ["input", "textarea"] or
                (element_tag == "input" and element_type.lower() in FILLABLE_INPUT_TYPES) or
                await element.evaluate("el => el.isContentEditable")
            )
            
            if not is_fillable_input and not force:
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                logger.error("Element is not fillable", 
                           selector=selector, tag=element_tag, type=element_type)
                return FillElementResponse(
                    success=False,
                    selector=selector,
                    value=value,
                    message=f"Element {selector} is not fillable (tag: {element_tag}, type: {element_type})",
                    cleared_first=False,
                    elapsed_ms=elapsed_ms,
                    metadata={
                        "error": "ELEMENT_NOT_FILLABLE",
                        "element_tag": element_tag,
                        "element_type": element_type,
                        "is_editable": await element.evaluate("el => el.isContentEditable"),
                        "force_used": force,
                        "operation_time_ms": elapsed_ms
                    }
                ).dict()
            
            # Check if element is editable
            if (element_readonly or element_disabled or not element_enabled) and not force:
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                logger.error("Element is not editable", 
                           selector=selector, readonly=element_readonly, disabled=element_disabled)
                return FillElementResponse(
                    success=False,
                    selector=selector,
                    value=value,
                    message=f"Element {selector} is not editable (readonly: {element_readonly}, disabled: {element_disabled})",
                    cleared_first=False,
                    elapsed_ms=elapsed_ms,
                    metadata={
                        "error": "ELEMENT_NOT_EDITABLE",
                        "element_readonly": element_readonly,
                        "element_disabled": element_disabled,
                        "element_enabled": element_enabled,
                        "force_used": force,
                        "operation_time_ms": elapsed_ms
                    }
                ).dict()
            
            # Check visibility
            if not element_visible and not force:
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                logger.error("Element is not visible", selector=selector)
                return FillElementResponse(
                    success=False,
                    selector=selector,
                    value=value,
                    message=f"Element {selector} is not visible",
                    cleared_first=False,
                    elapsed_ms=elapsed_ms,
                    metadata={
                        "error": "ELEMENT_NOT_VISIBLE",
                        "element_visible": element_visible,
                        "force_used": force,
                        "operation_time_ms": elapsed_ms
                    }
                ).dict()
            
            # Get element bounds for metadata
            try:
                element_bounds = await element.bounding_box()
                bounds_metadata = element_bounds if element_bounds else {"x": 0, "y": 0, "width": 0, "height": 0}
            except PlaywrightError:
                bounds_metadata = {"x": 0, "y": 0, "width": 0, "height": 0}
            
            # Perform fill operation
            fill_start_time = time.monotonic()
            
            try:
                logger.info("Performing fill operation", 
                          selector=selector, clear_first=clear_first, value_length=len(value))
                
                # Clear first if requested
                actual_cleared = False
                if clear_first and current_value:
                    await element.clear(timeout=timeout_ms)
                    actual_cleared = True
                    logger.info("Element cleared before filling", selector=selector)
                
                # Fill the element with the value
                if value:  # Only fill if value is not empty
                    await element.fill(value, timeout=timeout_ms)
                    logger.info("Element filled successfully", selector=selector, value_length=len(value))
                
                # Apply post-fill delay if requested
                if delay_ms > 0:
                    await page.wait_for_timeout(delay_ms)
                    logger.info("Post-fill delay applied", delay_ms=delay_ms)
                
                # Calculate timing
                fill_elapsed_ms = int((time.monotonic() - fill_start_time) * 1000)
                total_elapsed_ms = int((time.monotonic() - start_time) * 1000)
                
                # Verify the fill operation by checking final value
                try:
                    final_value = await element.evaluate("el => el.value || el.textContent || ''")
                    fill_successful = (final_value == value) if value else (final_value != current_value or actual_cleared)
                except PlaywrightError:
                    final_value = ""
                    fill_successful = True  # Assume success if we can't verify
                
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
                    "value_length": len(value),
                    "fill_verified": fill_successful,
                    "force_used": force,
                    "delay_applied_ms": delay_ms,
                    "fill_operation_time_ms": fill_elapsed_ms,
                    "total_operation_time_ms": total_elapsed_ms,
                    "page_title": page_title,
                    "page_url": page_url,
                    "session_id": session_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "browser_type": session.get("browser_type", "unknown")
                }
                
                # Update session metadata with fill history
                if "fill_history" not in session:
                    session["fill_history"] = []
                
                session["fill_history"].append({
                    "selector": selector,
                    "value_length": len(value),
                    "timestamp": datetime.utcnow().isoformat(),
                    "success": fill_successful,
                    "cleared_first": actual_cleared,
                    "elapsed_ms": total_elapsed_ms
                })
                
                # Keep only last 20 fill entries
                session["fill_history"] = session["fill_history"][-20:]
                
                # Create success message
                message = f"Element filled successfully"
                if actual_cleared:
                    message += " (cleared first)"
                if delay_ms > 0:
                    message += f" with {delay_ms}ms delay"
                
                # Log successful fill for audit compliance
                logger.info(
                    "Fill operation completed successfully",
                    session_id=session_id,
                    selector=selector,
                    value_length=len(value),
                    cleared_first=actual_cleared,
                    elapsed_ms=total_elapsed_ms,
                    fill_verified=fill_successful
                )
                
                # Return successful response
                return FillElementResponse(
                    success=True,
                    selector=selector,
                    value=value,
                    message=message,
                    cleared_first=actual_cleared,
                    elapsed_ms=total_elapsed_ms,
                    metadata=metadata
                ).dict()
                
            except PlaywrightTimeoutError as te:
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                logger.error("Fill operation timed out", 
                           selector=selector, timeout_ms=timeout_ms, error=str(te))
                return FillElementResponse(
                    success=False,
                    selector=selector,
                    value=value,
                    message=f"Fill operation timed out after {timeout_ms}ms: {str(te)}",
                    cleared_first=False,
                    elapsed_ms=elapsed_ms,
                    metadata={
                        "error": "FILL_TIMEOUT",
                        "timeout_ms": timeout_ms,
                        "error_details": str(te),
                        "operation_time_ms": elapsed_ms
                    }
                ).dict()
                
            except PlaywrightError as pe:
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                error_message = str(pe)
                logger.error("Fill operation failed", 
                           selector=selector, error=error_message)
                return FillElementResponse(
                    success=False,
                    selector=selector,
                    value=value,
                    message=f"Fill operation failed: {error_message}",
                    cleared_first=False,
                    elapsed_ms=elapsed_ms,
                    metadata={
                        "error": "FILL_OPERATION_FAILED",
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
            return FillElementResponse(
                success=False,
                selector=selector,
                value=value,
                message=f"Element not found within {timeout_ms}ms: {selector}",
                cleared_first=False,
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
            return FillElementResponse(
                success=False,
                selector=selector,
                value=value,
                message=f"Element location failed: {error_message}",
                cleared_first=False,
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
        return FillElementResponse(
            success=False,
            selector=selector,
            value=value,
            message=f"Request validation failed: {validation_errors}",
            cleared_first=False,
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
            "Unexpected error during fill operation",
            session_id=session_id,
            selector=selector,
            error=error_message,
            elapsed_ms=elapsed_ms
        )
        
        return FillElementResponse(
            success=False,
            selector=selector,
            value=value,
            message=f"Unexpected error during fill operation: {error_message}",
            cleared_first=False,
            elapsed_ms=elapsed_ms,
            metadata={
                "error": "UNEXPECTED_ERROR",
                "error_details": error_message,
                "operation_time_ms": elapsed_ms
            }
        ).dict()


@mcp_server.prompt()
def fill_element_prompt(field_name: str, value: str, field_type: str = "input") -> str:
    """
    Returns a prompt guiding the LLM to fill a specific form element.
    
    This prompt template helps users understand how to perform form filling operations
    and provides context for form automation workflows.
    
    Args:
        field_name: The name or description of the field to fill
        value: The value to be filled into the field
        field_type: The type of field (input, textarea, select, etc.)
    
    Returns:
        Formatted prompt string for form filling operation guidance
    """
    return f"""Fill the '{field_name}' {field_type} field with the value '{value}'.

This will perform a form filling operation which can be used for:
- Automated form completion in web applications
- User registration and login workflows
- Data entry automation for testing scenarios
- Form validation testing with various input values
- Multi-step form progression workflows

The fill operation includes comprehensive validation:
- Element existence and visibility verification
- Input type compatibility checking
- Editable state validation (not readonly/disabled)
- Content clearing options for clean data entry
- Post-fill timing controls for UI responsiveness
- Detailed error handling for various failure modes

Best practices for reliable form filling:
- Use stable selectors (ID, data attributes) when possible
- Allow sufficient timeout for dynamic form elements
- Consider clearing existing content before filling
- Add appropriate delays for forms with validation
- Verify the fill operation success through subsequent assertions

The operation provides detailed metadata including element properties, timing information, and operation verification for comprehensive test reporting.""" 
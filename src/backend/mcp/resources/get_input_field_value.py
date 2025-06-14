"""
Input Field Value Resource for IntelliBrowse MCP Server.

This module provides resource capabilities for retrieving input field values,
supporting form analysis, validation testing, and field state inspection workflows.
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional
import structlog
from playwright.async_api import Page, Error as PlaywrightError

# Add parent directory to path for MCP server import
sys.path.append(str(Path(__file__).parent.parent))
from main import mcp_server

# Import browser session utilities
sys.path.append(str(Path(__file__).parent.parent / "tools"))
from browser_session import browser_sessions

logger = structlog.get_logger("intellibrowse.mcp.resources.get_input_field_value")


@mcp_server.resource("inputvalue://{session_id}/{selector}")
async def get_input_field_value(session_id: str, selector: str) -> Dict[str, Any]:
    """
    Gets the current value of an input or textarea field.
    
    This resource provides comprehensive field value retrieval with detailed
    element analysis, supporting form inspection and validation workflows.
    
    Args:
        session_id: Browser session identifier
        selector: CSS selector targeting the input field
    
    Returns:
        Dict containing field value and comprehensive element metadata
    """
    logger.info(
        "Retrieving input field value",
        session_id=session_id,
        selector=selector
    )
    
    try:
        # Check if session exists
        if session_id not in browser_sessions:
            logger.error("Browser session not found", session_id=session_id)
            return {
                "error": "SESSION_NOT_FOUND",
                "message": f"Browser session {session_id} not found",
                "session_id": session_id,
                "selector": selector,
                "value": None,
                "metadata": {}
            }
        
        session = browser_sessions[session_id]
        page: Page = session["page"]
        
        # Verify page is still active
        try:
            await page.title()  # Simple check to ensure page is responsive
        except PlaywrightError as e:
            logger.error("Page is not active", session_id=session_id, error=str(e))
            return {
                "error": "PAGE_NOT_ACTIVE",
                "message": f"Page is not active or accessible: {str(e)}",
                "session_id": session_id,
                "selector": selector,
                "value": None,
                "metadata": {"error_details": str(e)}
            }
        
        # Locate the element
        try:
            element = await page.wait_for_selector(
                selector,
                timeout=5000,
                state="attached"
            )
            
            if not element:
                logger.error("Element not found", selector=selector)
                return {
                    "error": "ELEMENT_NOT_FOUND",
                    "message": f"Element not found: {selector}",
                    "session_id": session_id,
                    "selector": selector,
                    "value": None,
                    "metadata": {}
                }
            
            # Get element properties and value
            element_tag = await element.evaluate("el => el.tagName.toLowerCase()")
            element_type = await element.evaluate("el => el.type || ''")
            element_name = await element.evaluate("el => el.name || ''")
            element_id = await element.evaluate("el => el.id || ''")
            element_placeholder = await element.evaluate("el => el.placeholder || ''")
            element_readonly = await element.evaluate("el => el.readOnly || false")
            element_disabled = await element.evaluate("el => el.disabled || false")
            element_required = await element.evaluate("el => el.required || false")
            element_visible = await element.is_visible()
            element_enabled = await element.is_enabled()
            
            # Get the current value
            try:
                # Try different methods to get the value based on element type
                if element_tag == "input":
                    current_value = await element.evaluate("el => el.value")
                elif element_tag == "textarea":
                    current_value = await element.evaluate("el => el.value")
                elif await element.evaluate("el => el.contentEditable === 'true'"):
                    current_value = await element.evaluate("el => el.textContent || el.innerText || ''")
                else:
                    current_value = await element.evaluate("el => el.value || el.textContent || el.innerText || ''")
            except PlaywrightError:
                current_value = ""
            
            # Get element bounds for positioning information
            try:
                element_bounds = await element.bounding_box()
            except PlaywrightError:
                element_bounds = None
            
            # Get page context
            try:
                page_url = await page.url()
                page_title = await page.title()
            except PlaywrightError:
                page_url = ""
                page_title = ""
            
            # Collect comprehensive metadata
            metadata = {
                "element_analysis": {
                    "tag": element_tag,
                    "type": element_type,
                    "name": element_name,
                    "id": element_id,
                    "placeholder": element_placeholder,
                    "readonly": element_readonly,
                    "disabled": element_disabled,
                    "required": element_required,
                    "visible": element_visible,
                    "enabled": element_enabled
                },
                "value_analysis": {
                    "length": len(str(current_value)),
                    "is_empty": not bool(str(current_value).strip()),
                    "type": type(current_value).__name__
                },
                "element_bounds": element_bounds,
                "page_context": {
                    "url": page_url,
                    "title": page_title
                },
                "retrieval_info": {
                    "selector": selector,
                    "session_id": session_id,
                    "method": "playwright_evaluation"
                }
            }
            
            logger.info(
                "Input field value retrieved successfully",
                selector=selector,
                element_tag=element_tag,
                element_type=element_type,
                value_length=len(str(current_value)),
                is_empty=not bool(str(current_value).strip())
            )
            
            return {
                "selector": selector,
                "value": str(current_value),
                "session_id": session_id,
                "metadata": metadata
            }
            
        except PlaywrightError as pe:
            error_message = str(pe)
            logger.error("Element location failed", selector=selector, error=error_message)
            return {
                "error": "ELEMENT_LOCATION_FAILED",
                "message": f"Element location failed: {error_message}",
                "session_id": session_id,
                "selector": selector,
                "value": None,
                "metadata": {"error_details": error_message}
            }
            
    except Exception as e:
        # Handle any unexpected errors
        error_message = str(e)
        logger.error(
            "Unexpected error during field value retrieval",
            session_id=session_id,
            selector=selector,
            error=error_message
        )
        
        return {
            "error": "UNEXPECTED_ERROR",
            "message": f"Unexpected error during field value retrieval: {error_message}",
            "session_id": session_id,
            "selector": selector,
            "value": None,
            "metadata": {"error_details": error_message}
        }


@mcp_server.resource("inputstate://{session_id}/{selector}")
async def get_input_field_state(session_id: str, selector: str) -> Dict[str, Any]:
    """
    Gets the complete state information of an input field.
    
    This resource provides comprehensive field state analysis including
    validation status, accessibility, and interaction capabilities.
    
    Args:
        session_id: Browser session identifier
        selector: CSS selector targeting the input field
    
    Returns:
        Dict containing comprehensive field state information
    """
    logger.info(
        "Retrieving input field state",
        session_id=session_id,
        selector=selector
    )
    
    try:
        # Check if session exists
        if session_id not in browser_sessions:
            logger.error("Browser session not found", session_id=session_id)
            return {
                "error": "SESSION_NOT_FOUND",
                "message": f"Browser session {session_id} not found",
                "session_id": session_id,
                "selector": selector,
                "state": {},
                "metadata": {}
            }
        
        session = browser_sessions[session_id]
        page: Page = session["page"]
        
        # Verify page is still active
        try:
            await page.title()
        except PlaywrightError as e:
            logger.error("Page is not active", session_id=session_id, error=str(e))
            return {
                "error": "PAGE_NOT_ACTIVE",
                "message": f"Page is not active or accessible: {str(e)}",
                "session_id": session_id,
                "selector": selector,
                "state": {},
                "metadata": {"error_details": str(e)}
            }
        
        # Locate the element
        try:
            element = await page.wait_for_selector(
                selector,
                timeout=5000,
                state="attached"
            )
            
            if not element:
                return {
                    "error": "ELEMENT_NOT_FOUND",
                    "message": f"Element not found: {selector}",
                    "session_id": session_id,
                    "selector": selector,
                    "state": {},
                    "metadata": {}
                }
            
            # Get comprehensive element state
            state = {
                "basic_properties": {
                    "tag": await element.evaluate("el => el.tagName.toLowerCase()"),
                    "type": await element.evaluate("el => el.type || ''"),
                    "name": await element.evaluate("el => el.name || ''"),
                    "id": await element.evaluate("el => el.id || ''"),
                    "class": await element.evaluate("el => el.className || ''")
                },
                "attributes": {
                    "placeholder": await element.evaluate("el => el.placeholder || ''"),
                    "value": await element.evaluate("el => el.value || el.textContent || ''"),
                    "maxlength": await element.evaluate("el => el.maxLength || null"),
                    "minlength": await element.evaluate("el => el.minLength || null"),
                    "pattern": await element.evaluate("el => el.pattern || ''"),
                    "title": await element.evaluate("el => el.title || ''")
                },
                "validation": {
                    "required": await element.evaluate("el => el.required || false"),
                    "valid": await element.evaluate("el => el.validity ? el.validity.valid : true"),
                    "validation_message": await element.evaluate("el => el.validationMessage || ''")
                },
                "accessibility": {
                    "readonly": await element.evaluate("el => el.readOnly || false"),
                    "disabled": await element.evaluate("el => el.disabled || false"),
                    "visible": await element.is_visible(),
                    "enabled": await element.is_enabled(),
                    "editable": await element.is_editable(),
                    "hidden": await element.evaluate("el => el.hidden || false")
                },
                "interaction": {
                    "focused": await element.evaluate("el => el === document.activeElement"),
                    "clickable": True,  # Will be updated based on actual check
                    "fillable": True    # Will be updated based on actual check
                }
            }
            
            # Check interaction capabilities
            try:
                state["interaction"]["clickable"] = await element.is_visible() and await element.is_enabled()
                
                # Check if field is fillable
                tag = state["basic_properties"]["tag"]
                element_type = state["basic_properties"]["type"]
                readonly = state["accessibility"]["readonly"]
                disabled = state["accessibility"]["disabled"]
                
                fillable_types = ["text", "email", "password", "search", "url", "tel", "number", 
                                "date", "datetime-local", "month", "week", "time"]
                
                is_fillable = (
                    (tag == "input" and element_type in fillable_types) or
                    tag == "textarea" or
                    await element.evaluate("el => el.contentEditable === 'true'")
                ) and not readonly and not disabled
                
                state["interaction"]["fillable"] = is_fillable
                
            except PlaywrightError:
                state["interaction"]["clickable"] = False
                state["interaction"]["fillable"] = False
            
            # Get element bounds
            try:
                bounds = await element.bounding_box()
                state["geometry"] = bounds
            except PlaywrightError:
                state["geometry"] = None
            
            # Get page context
            try:
                page_url = await page.url()
                page_title = await page.title()
            except PlaywrightError:
                page_url = ""
                page_title = ""
            
            metadata = {
                "page_context": {
                    "url": page_url,
                    "title": page_title
                },
                "analysis_info": {
                    "selector": selector,
                    "session_id": session_id,
                    "timestamp": "",  # Can add timestamp if needed
                    "comprehensive": True
                }
            }
            
            logger.info(
                "Input field state retrieved successfully",
                selector=selector,
                tag=state["basic_properties"]["tag"],
                type=state["basic_properties"]["type"],
                fillable=state["interaction"]["fillable"],
                visible=state["accessibility"]["visible"]
            )
            
            return {
                "selector": selector,
                "state": state,
                "session_id": session_id,
                "metadata": metadata
            }
            
        except PlaywrightError as pe:
            error_message = str(pe)
            logger.error("Element state analysis failed", selector=selector, error=error_message)
            return {
                "error": "ELEMENT_ANALYSIS_FAILED",
                "message": f"Element state analysis failed: {error_message}",
                "session_id": session_id,
                "selector": selector,
                "state": {},
                "metadata": {"error_details": error_message}
            }
            
    except Exception as e:
        error_message = str(e)
        logger.error(
            "Unexpected error during field state analysis",
            session_id=session_id,
            selector=selector,
            error=error_message
        )
        
        return {
            "error": "UNEXPECTED_ERROR",
            "message": f"Unexpected error during field state analysis: {error_message}",
            "session_id": session_id,
            "selector": selector,
            "state": {},
            "metadata": {"error_details": error_message}
        } 
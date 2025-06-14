"""
Click Element Tool for IntelliBrowse MCP Server.

This module provides tools for performing mouse clicks on DOM elements within 
Playwright browser sessions, enabling automated user interactions and workflow progression.
"""

import time
from typing import Dict, Any, Optional
import structlog
from playwright.async_api import Page, Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError

# Import the main MCP server instance
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from main import mcp_server

# Import schemas - use modular schema imports
from src.backend.mcp.schemas.tools.click_element_schemas import ClickElementRequest, ClickElementResponse

# Import browser session utilities - use absolute import
sys.path.append(str(Path(__file__).parent))
from browser_session import browser_sessions

logger = structlog.get_logger("intellibrowse.mcp.tools.click_element")

# Valid click types
VALID_CLICK_TYPES = ["single", "double", "right"]


@mcp_server.tool()
async def click_element(
    session_id: str,
    selector: str,
    timeout_ms: Optional[int] = 5000,
    click_type: Optional[str] = "single",
    delay_ms: Optional[int] = 0,
    force: Optional[bool] = False
) -> Dict[str, Any]:
    """
    Perform a mouse click on the specified DOM element in the current browser context.
    
    This tool clicks on DOM elements within an active Playwright browser session,
    supporting different click types, timeout controls, and comprehensive error handling
    for automated user interaction workflows.
    
    Args:
        session_id: Active Playwright session identifier
        selector: CSS selector of the element to click
        timeout_ms: Timeout in milliseconds for element availability (default: 5000)
        click_type: Type of click - 'single', 'double', or 'right' (default: 'single')
        delay_ms: Delay after click in milliseconds (default: 0)
        force: Whether to force the click even if element is not actionable (default: False)
    
    Returns:
        Dict containing click operation status, metadata, and timing information
    """
    start_time = time.monotonic()
    
    logger.info(
        "Starting click element operation",
        session_id=session_id,
        selector=selector,
        timeout_ms=timeout_ms,
        click_type=click_type,
        delay_ms=delay_ms,
        force=force
    )
    
    try:
        # Validate request using Pydantic schema
        request = ClickElementRequest(
            session_id=session_id,
            selector=selector,
            timeout_ms=timeout_ms,
            click_type=click_type,
            delay_ms=delay_ms,
            force=force
        )
        
        # Validate click type
        if click_type not in VALID_CLICK_TYPES:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Invalid click type", click_type=click_type, valid_types=VALID_CLICK_TYPES)
            return ClickElementResponse(
                success=False,
                selector=selector,
                message=f"Invalid click type '{click_type}'. Valid types: {VALID_CLICK_TYPES}",
                click_type=click_type,
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "INVALID_CLICK_TYPE",
                    "valid_click_types": VALID_CLICK_TYPES,
                    "operation_time_ms": elapsed_ms
                }
            ).dict()
        
        # Check if session exists
        if session_id not in browser_sessions:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Session not found", session_id=session_id)
            return ClickElementResponse(
                success=False,
                selector=selector,
                message=f"Browser session {session_id} not found",
                click_type=click_type,
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "SESSION_NOT_FOUND",
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
            return ClickElementResponse(
                success=False,
                selector=selector,
                message=f"Page is not active or accessible: {str(e)}",
                click_type=click_type,
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "PAGE_NOT_ACTIVE",
                    "error_details": str(e),
                    "operation_time_ms": elapsed_ms
                }
            ).dict()
        
        # Wait for element to be available and visible
        try:
            logger.info("Waiting for element to be visible", selector=selector, timeout_ms=timeout_ms)
            await page.wait_for_selector(
                selector, 
                timeout=timeout_ms, 
                state="visible"
            )
        except PlaywrightTimeoutError:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.warning("Element not found or not visible", session_id=session_id, selector=selector, timeout_ms=timeout_ms)
            return ClickElementResponse(
                success=False,
                selector=selector,
                message=f"Element '{selector}' not found or not visible after {timeout_ms} ms",
                click_type=click_type,
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "ELEMENT_NOT_VISIBLE",
                    "timeout_ms": timeout_ms,
                    "operation_time_ms": elapsed_ms,
                    "page_url": page.url,
                    "page_title": await page.title() if page else "Unknown"
                }
            ).dict()
        except PlaywrightError as e:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Element wait failed", session_id=session_id, selector=selector, error=str(e))
            return ClickElementResponse(
                success=False,
                selector=selector,
                message=f"Failed to wait for element '{selector}': {str(e)}",
                click_type=click_type,
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "ELEMENT_WAIT_FAILED",
                    "error_details": str(e),
                    "operation_time_ms": elapsed_ms
                }
            ).dict()
        
        # Perform the click operation based on click type
        click_options = {"force": force} if force else {}
        
        try:
            logger.info("Performing click operation", selector=selector, click_type=click_type, force=force)
            
            if click_type == "double":
                await page.dblclick(selector, **click_options)
            elif click_type == "right":
                await page.click(selector, button="right", **click_options)
            else:  # single click (default)
                await page.click(selector, **click_options)
            
            # Get element coordinates for metadata
            try:
                element_handle = await page.query_selector(selector)
                if element_handle:
                    bbox = await element_handle.bounding_box()
                    coordinates = {
                        "x": int(bbox["x"] + bbox["width"] / 2) if bbox else None,
                        "y": int(bbox["y"] + bbox["height"] / 2) if bbox else None
                    }
                else:
                    coordinates = {"x": None, "y": None}
            except Exception:
                coordinates = {"x": None, "y": None}
            
            # Optional delay after click
            if delay_ms and delay_ms > 0:
                logger.info("Applying post-click delay", delay_ms=delay_ms)
                await page.wait_for_timeout(delay_ms)
            
            # Calculate elapsed time
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            
            # Collect comprehensive metadata
            try:
                page_title = await page.title()
                page_url = page.url
                
                # Check if element is still visible and enabled
                element_visible = await page.is_visible(selector)
                element_enabled = await page.is_enabled(selector)
                
            except PlaywrightError:
                page_title = "Unknown"
                page_url = "Unknown"
                element_visible = False
                element_enabled = False
            
            metadata = {
                "element_visible": element_visible,
                "element_enabled": element_enabled,
                "page_title": page_title,
                "page_url": page_url,
                "coordinates": coordinates,
                "browser_type": session.get("browser_type", "unknown"),
                "viewport": session.get("viewport", {}),
                "user_agent": session.get("user_agent"),
                "operation_time_ms": elapsed_ms,
                "force_click": force,
                "post_click_delay_ms": delay_ms
            }
            
            # Create success message
            message = f"Click performed successfully on element {selector}"
            if delay_ms and delay_ms > 0:
                message += f" (with {delay_ms}ms delay)"
            
            # Log successful click for audit compliance
            logger.info(
                "Click operation completed successfully",
                session_id=session_id,
                selector=selector,
                click_type=click_type,
                elapsed_ms=elapsed_ms,
                coordinates=coordinates,
                force=force
            )
            
            # Return successful response
            return ClickElementResponse(
                success=True,
                selector=selector,
                message=message,
                click_type=click_type,
                elapsed_ms=elapsed_ms,
                metadata=metadata
            ).dict()
            
        except PlaywrightError as click_error:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            error_message = str(click_error)
            
            logger.error(
                "Click operation failed",
                session_id=session_id,
                selector=selector,
                click_type=click_type,
                error=error_message,
                elapsed_ms=elapsed_ms
            )
            
            return ClickElementResponse(
                success=False,
                selector=selector,
                message=f"Click failed on '{selector}': {error_message}",
                click_type=click_type,
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "CLICK_FAILED",
                    "error_details": error_message,
                    "error_type": type(click_error).__name__,
                    "operation_time_ms": elapsed_ms,
                    "force_click": force
                }
            ).dict()
        
    except Exception as e:
        # Handle any unexpected errors
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        error_message = str(e)
        
        logger.error(
            "Unexpected error during click operation",
            session_id=session_id,
            selector=selector,
            click_type=click_type,
            error=error_message,
            elapsed_ms=elapsed_ms
        )
        
        return ClickElementResponse(
            success=False,
            selector=selector,
            message=f"Unexpected error during click operation: {error_message}",
            click_type=click_type or "single",
            elapsed_ms=elapsed_ms,
            metadata={
                "error": "UNEXPECTED_ERROR",
                "error_details": error_message,
                "operation_time_ms": elapsed_ms
            }
        ).dict()


@mcp_server.prompt()
def click_element_prompt(selector: str, click_type: str = "single") -> str:
    """
    Returns a prompt guiding the LLM to click on a given element.
    
    This prompt template helps users understand how to perform click operations
    and provides context for automated user interaction workflows.
    
    Args:
        selector: CSS selector of the element to click
        click_type: Type of click operation to perform
    
    Returns:
        Formatted prompt string for click operation guidance
    """
    click_descriptions = {
        "single": "Click on",
        "double": "Double-click on", 
        "right": "Right-click on"
    }
    
    action = click_descriptions.get(click_type, "Click on")
    
    return f"""{action} the element matching selector '{selector}' in the current browser session.

This will perform a {click_type} click operation on the specified element, which can be used for:
- Button activation and form submission
- Menu navigation and dropdown interaction
- Link following and page navigation
- User interface interaction testing
- Automated workflow progression

The operation will wait for the element to be visible and actionable before performing the click.""" 
"""
Hover Element Tool for IntelliBrowse MCP Server.

This module provides tools for performing mouse hover actions on DOM elements within 
Playwright browser sessions, enabling automated user interactions and UI state testing,
particularly for hover-dependent behaviors like menus, tooltips, and dynamic reveals.
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
from src.backend.mcp.schemas.tools.hover_element_schemas import HoverElementRequest, HoverElementResponse

# Import browser session utilities - use absolute import
sys.path.append(str(Path(__file__).parent))
from browser_session import browser_sessions

logger = structlog.get_logger("intellibrowse.mcp.tools.hover_element")


@mcp_server.tool()
async def hover_element(
    session_id: str,
    selector: str,
    timeout_ms: Optional[int] = 5000,
    delay_ms: Optional[int] = 0,
    force: Optional[bool] = False,
    position: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """
    Perform a mouse hover action on the specified DOM element in the current browser context.
    
    This tool hovers over DOM elements within an active Playwright browser session,
    supporting hover-dependent UI behaviors, menu interactions, tooltip testing,
    and comprehensive hover state validation.
    
    Args:
        session_id: Active Playwright session identifier
        selector: CSS selector of the element to hover over
        timeout_ms: Timeout in milliseconds for element availability (default: 5000)
        delay_ms: Delay after hover in milliseconds (default: 0)
        force: Whether to force the hover even if element is not actionable (default: False)
        position: Optional position to hover within the element (x, y coordinates)
    
    Returns:
        Dict containing hover operation status, metadata, and timing information
    """
    start_time = time.monotonic()
    
    logger.info(
        "Starting hover element operation",
        session_id=session_id,
        selector=selector,
        timeout_ms=timeout_ms,
        delay_ms=delay_ms,
        force=force,
        position=position
    )
    
    try:
        # Validate request using Pydantic schema
        request = HoverElementRequest(
            session_id=session_id,
            selector=selector,
            timeout_ms=timeout_ms,
            delay_ms=delay_ms,
            force=force,
            position=position
        )
        
        # Check if session exists
        if session_id not in browser_sessions:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Session not found", session_id=session_id)
            return HoverElementResponse(
                success=False,
                selector=selector,
                message=f"Browser session {session_id} not found",
                hovered=False,
                position=position,
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
            return HoverElementResponse(
                success=False,
                selector=selector,
                message=f"Page is not active or accessible: {str(e)}",
                hovered=False,
                position=position,
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
            return HoverElementResponse(
                success=False,
                selector=selector,
                message=f"Element '{selector}' not found or not visible after {timeout_ms} ms",
                hovered=False,
                position=position,
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
            return HoverElementResponse(
                success=False,
                selector=selector,
                message=f"Failed to wait for element '{selector}': {str(e)}",
                hovered=False,
                position=position,
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "ELEMENT_WAIT_FAILED",
                    "error_details": str(e),
                    "operation_time_ms": elapsed_ms
                }
            ).dict()
        
        # Perform the hover operation
        hover_options = {"force": force} if force else {}
        if position:
            hover_options["position"] = position
        
        try:
            logger.info("Performing hover operation", selector=selector, force=force, position=position)
            
            await page.hover(selector, **hover_options)
            
            # Get element coordinates and metadata for response
            try:
                element_handle = await page.query_selector(selector)
                if element_handle:
                    bbox = await element_handle.bounding_box()
                    if position:
                        hover_coordinates = {
                            "x": bbox["x"] + position["x"] if bbox else position["x"],
                            "y": bbox["y"] + position["y"] if bbox else position["y"]
                        }
                    else:
                        hover_coordinates = {
                            "x": int(bbox["x"] + bbox["width"] / 2) if bbox else None,
                            "y": int(bbox["y"] + bbox["height"] / 2) if bbox else None
                        }
                    
                    element_bounds = {
                        "x": int(bbox["x"]),
                        "y": int(bbox["y"]),
                        "width": int(bbox["width"]),
                        "height": int(bbox["height"])
                    } if bbox else None
                else:
                    hover_coordinates = position
                    element_bounds = None
            except PlaywrightError:
                hover_coordinates = position
                element_bounds = None
            
            # Optional delay after hover
            if delay_ms > 0:
                await page.wait_for_timeout(delay_ms)
                logger.info("Applied post-hover delay", delay_ms=delay_ms)
            
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            
            # Gather page context and metadata
            try:
                page_url = await page.url()
                page_title = await page.title()
                browser_info = session.get("browser_info", {})
            except PlaywrightError:
                page_url = ""
                page_title = ""
                browser_info = {}
            
            metadata = {
                "element_visible": True,
                "element_bounds": element_bounds,
                "hover_coordinates": hover_coordinates,
                "page_title": page_title,
                "page_url": page_url,
                "browser_type": browser_info.get("browser_type", "unknown"),
                "force_used": force,
                "position_specified": position is not None,
                "delay_applied_ms": delay_ms,
                "operation_time_ms": elapsed_ms
            }
            
            # Track the hover operation for state management
            try:
                from get_hovered_state import track_hover_operation
                operation_data = {
                    "success": True,
                    "selector": selector,
                    "position": hover_coordinates,
                    "force_used": force,
                    "delay_applied_ms": delay_ms,
                    "elapsed_ms": elapsed_ms
                }
                track_hover_operation(session_id, selector, operation_data)
            except ImportError:
                logger.warning("Hover state tracking not available")
            
            logger.info(
                "Hover operation completed successfully",
                selector=selector,
                elapsed_ms=elapsed_ms,
                hover_coordinates=hover_coordinates
            )
            
            return HoverElementResponse(
                success=True,
                selector=selector,
                message=f"Successfully hovered over element '{selector}'",
                hovered=True,
                position=hover_coordinates,
                elapsed_ms=elapsed_ms,
                metadata=metadata
            ).dict()
            
        except PlaywrightError as e:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            error_message = str(e)
            logger.error("Hover operation failed", selector=selector, error=error_message)
            
            return HoverElementResponse(
                success=False,
                selector=selector,
                message=f"Hover operation failed for '{selector}': {error_message}",
                hovered=False,
                position=position,
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "HOVER_OPERATION_FAILED",
                    "error_details": error_message,
                    "force_used": force,
                    "position_specified": position is not None,
                    "operation_time_ms": elapsed_ms
                }
            ).dict()
            
    except Exception as e:
        # Handle any unexpected errors
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        error_message = str(e)
        logger.error(
            "Unexpected error during hover operation",
            session_id=session_id,
            selector=selector,
            error=error_message
        )
        
        return HoverElementResponse(
            success=False,
            selector=selector,
            message=f"Hover operation failed due to unexpected error: {error_message}",
            hovered=False,
            position=position,
            elapsed_ms=elapsed_ms,
            metadata={
                "error": "UNEXPECTED_ERROR",
                "error_details": error_message,
                "operation_time_ms": elapsed_ms
            }
        ).dict()


@mcp_server.prompt()
def hover_element_prompt(selector: str, hover_type: str = "standard") -> str:
    """
    Returns a prompt guiding the LLM to hover over the specified element.
    
    This prompt template helps users understand how to perform hover operations
    and provides context for hover-dependent UI testing workflows.
    
    Args:
        selector: CSS selector of the element to hover over
        hover_type: Type of hover operation (standard, tooltip, menu, validation)
    
    Returns:
        Formatted prompt string for hover operation guidance
    """
    hover_descriptions = {
        "standard": "a standard mouse hover to trigger hover states",
        "tooltip": "a hover to display tooltips or help information",
        "menu": "a hover to open dropdown menus or navigation",
        "validation": "a hover to test hover-dependent validation or styling"
    }
    
    description = hover_descriptions.get(hover_type, "a mouse hover operation")
    
    return f"""Hover the mouse over the element with selector '{selector}' to perform {description}.

This hover operation will trigger any CSS :hover states, JavaScript hover event handlers, and dynamic content that depends on mouse positioning. The operation supports comprehensive hover testing scenarios including:

Hover Use Cases:
- Dropdown menu activation and navigation testing
- Tooltip display and content validation
- Interactive element state changes (:hover CSS effects)
- Dynamic content reveal (hidden elements, overlays)
- Form field help text and validation hints
- Image galleries and preview functionality
- Navigation menu expansion and interaction

The hover operation provides detailed positioning and timing control:
- Element targeting: Uses CSS selectors for precise element identification
- Position control: Optional specific coordinates within the element
- Force option: Bypasses actionability checks when needed
- Timeout management: Configurable wait times for element availability
- Delay support: Post-hover delays for UI state stabilization

Hover behavior details:
- Method: Uses Playwright's hover() method for authentic mouse simulation
- Positioning: Centers on element by default, supports custom coordinates
- State persistence: Hover state maintained until mouse moves elsewhere
- Validation: Ensures element visibility and actionability before hovering

Best practices for reliable hover operations:
- Use stable selectors (ID, data attributes) for consistent targeting
- Allow sufficient timeout for dynamic content loading
- Consider post-hover delays for UI animations and state changes
- Test hover effects across different browsers and devices
- Validate hover-dependent content after hover operation

The operation provides comprehensive metadata including hover coordinates, element bounds, timing information, and page context for detailed test reporting and debugging.""" 
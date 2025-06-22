"""
Scroll Page Tool for IntelliBrowse MCP Server.

This module provides page scrolling functionality for Playwright browser sessions,
enabling comprehensive scroll operations including directional scrolling, pixel-based
scrolling, element-specific scrolling, and scroll-to-element functionality with
comprehensive error handling and metadata collection.
"""

import time
from datetime import datetime
from typing import Dict, Any, Optional, List
import structlog
from playwright.async_api import Page, Error as PlaywrightError
from pydantic import ValidationError

# Import the main MCP server instance
try:
    from server_instance import mcp_server
except ImportError:
    # Fallback for when running directly from mcp directory
    from server_instance import mcp_server

# Import schemas - use absolute import to avoid relative import issues
try:
    from schemas.tools.scroll_page_schemas import ScrollPageRequest, ScrollPageResponse
except ImportError:
    # Fallback for when running directly from mcp directory
    from schemas.tools.scroll_page_schemas import ScrollPageRequest, ScrollPageResponse

# Import browser session utilities - use absolute import
try:
    from tools.browser_session import browser_sessions
except ImportError:
    # Fallback for when running directly from mcp directory
    from tools.browser_session import browser_sessions

logger = structlog.get_logger("intellibrowse.mcp.tools.scroll_page")

# Valid scroll directions
VALID_DIRECTIONS = ["up", "down", "left", "right", "top", "bottom"]

# Default scroll amounts for directional scrolling
DEFAULT_SCROLL_AMOUNTS = {
    "up": -300,
    "down": 300,
    "left": -300,
    "right": 300,
    "top": 0,  # Special case - scroll to top
    "bottom": 0  # Special case - scroll to bottom
}


@mcp_server.tool()
async def scroll_page(
    session_id: str,
    direction: Optional[str] = None,
    pixels: Optional[int] = None,
    selector: Optional[str] = None,
    to_element: Optional[bool] = False,
    timeout_ms: Optional[int] = 5000,
    smooth: Optional[bool] = False
) -> Dict[str, Any]:
    """
    Scroll the page or a specific element in the specified direction or by pixel value.
    
    This tool provides comprehensive scrolling functionality including:
    - Directional scrolling (up, down, left, right, top, bottom)
    - Pixel-based scrolling with precise control
    - Element-specific scrolling within containers
    - Scroll-to-element functionality for navigation
    - Smooth scrolling animation support
    
    Args:
        session_id: Browser session identifier for the target session
        direction: Direction to scroll ('up', 'down', 'left', 'right', 'top', 'bottom')
        pixels: Number of pixels to scroll (positive or negative)
        selector: Optional CSS selector to scroll a specific element
        to_element: If true, scrolls to the element specified by selector
        timeout_ms: Timeout for element availability (default: 5000)
        smooth: Whether to use smooth scrolling animation (default: False)
    
    Returns:
        Dict containing scroll status, position, and comprehensive metadata
    """
    start_time = time.monotonic()
    
    logger.info(
        "Starting scroll operation",
        session_id=session_id,
        direction=direction,
        pixels=pixels,
        selector=selector,
        to_element=to_element,
        timeout_ms=timeout_ms,
        smooth=smooth
    )
    
    try:
        # Validate request using Pydantic schema
        request = ScrollPageRequest(
            session_id=session_id,
            direction=direction,
            pixels=pixels,
            selector=selector,
            to_element=to_element,
            timeout_ms=timeout_ms,
            smooth=smooth
        )
        
        # Validate scroll parameters
        if not direction and pixels is None and not to_element:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("No valid scroll parameters provided")
            return ScrollPageResponse(
                success=False,
                session_id=session_id,
                scroll_position={"x": 0, "y": 0},
                scroll_type="none",
                message="No valid scroll parameters provided. Specify direction, pixels, or to_element=True",
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "INVALID_PARAMETERS",
                    "provided_params": {
                        "direction": direction,
                        "pixels": pixels,
                        "selector": selector,
                        "to_element": to_element
                    }
                }
            ).dict()
        
        # Validate direction if provided
        if direction and direction not in VALID_DIRECTIONS:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Invalid scroll direction", direction=direction, valid_directions=VALID_DIRECTIONS)
            return ScrollPageResponse(
                success=False,
                session_id=session_id,
                scroll_position={"x": 0, "y": 0},
                scroll_type="none",
                message=f"Invalid scroll direction '{direction}'. Valid directions: {VALID_DIRECTIONS}",
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "INVALID_DIRECTION",
                    "provided_direction": direction,
                    "valid_directions": VALID_DIRECTIONS
                }
            ).dict()
        
        # Check if session exists
        if session_id not in browser_sessions:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Browser session not found", session_id=session_id)
            return ScrollPageResponse(
                success=False,
                session_id=session_id,
                scroll_position={"x": 0, "y": 0},
                scroll_type="none",
                message=f"Browser session {session_id} not found",
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "SESSION_NOT_FOUND",
                    "session_id": session_id
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
            return ScrollPageResponse(
                success=False,
                session_id=session_id,
                scroll_position={"x": 0, "y": 0},
                scroll_type="none",
                message=f"Page is not active or accessible: {str(e)}",
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "PAGE_NOT_ACTIVE",
                    "error_details": str(e)
                }
            ).dict()
        
        # Get initial scroll position
        initial_position = await page.evaluate("() => ({ x: window.scrollX, y: window.scrollY })")
        
        # Initialize variables for operation tracking
        scroll_type = "none"
        scrolled_element = None
        final_position = initial_position.copy()
        
        try:
            # Handle scroll-to-element operation
            if to_element and selector:
                scroll_type = "scroll_to_element"
                scrolled_element = selector
                
                logger.info("Performing scroll-to-element operation", selector=selector)
                
                # Wait for element and scroll to it
                element = await page.wait_for_selector(
                    selector,
                    timeout=timeout_ms,
                    state="attached"
                )
                
                if not element:
                    raise PlaywrightError(f"Element not found: {selector}")
                
                # Scroll element into view
                await element.scroll_into_view_if_needed()
                
                # Get updated scroll position
                final_position = await page.evaluate("() => ({ x: window.scrollX, y: window.scrollY })")
                
            # Handle element-specific scrolling
            elif selector and (direction or pixels is not None):
                scroll_type = "element_scroll"
                scrolled_element = selector
                
                logger.info("Performing element-specific scroll", selector=selector)
                
                # Wait for element
                element = await page.wait_for_selector(
                    selector,
                    timeout=timeout_ms,
                    state="attached"
                )
                
                if not element:
                    raise PlaywrightError(f"Element not found: {selector}")
                
                # Determine scroll parameters
                if direction:
                    if direction in ["top", "bottom"]:
                        # Special cases for element scrolling
                        if direction == "top":
                            scroll_js = "el => el.scrollTo({ top: 0, behavior: '" + ("smooth" if smooth else "auto") + "' })"
                        else:  # bottom
                            scroll_js = "el => el.scrollTo({ top: el.scrollHeight, behavior: '" + ("smooth" if smooth else "auto") + "' })"
                    else:
                        # Directional scrolling
                        scroll_amount = DEFAULT_SCROLL_AMOUNTS.get(direction, 0)
                        if direction in ["up", "down"]:
                            scroll_js = f"el => el.scrollBy({{ top: {scroll_amount}, behavior: '" + ("smooth" if smooth else "auto") + "' })"
                        else:  # left, right
                            scroll_js = f"el => el.scrollBy({{ left: {scroll_amount}, behavior: '" + ("smooth" if smooth else "auto") + "' })"
                elif pixels is not None:
                    scroll_js = f"el => el.scrollBy({{ top: {pixels}, behavior: '" + ("smooth" if smooth else "auto") + "' })"
                
                # Execute element scroll
                await element.evaluate(scroll_js)
                
                # Get element scroll position
                element_position = await element.evaluate("el => ({ x: el.scrollLeft, y: el.scrollTop })")
                final_position = element_position
                
            # Handle page-level scrolling
            elif direction or pixels is not None:
                scroll_type = "page_scroll"
                
                logger.info("Performing page-level scroll")
                
                if direction:
                    if direction == "top":
                        scroll_js = "window.scrollTo({ top: 0, left: 0, behavior: '" + ("smooth" if smooth else "auto") + "' })"
                    elif direction == "bottom":
                        scroll_js = "window.scrollTo({ top: document.body.scrollHeight, left: 0, behavior: '" + ("smooth" if smooth else "auto") + "' })"
                    else:
                        scroll_amount = DEFAULT_SCROLL_AMOUNTS.get(direction, 0)
                        if direction in ["up", "down"]:
                            scroll_js = f"window.scrollBy({{ top: {scroll_amount}, behavior: '" + ("smooth" if smooth else "auto") + "' }})"
                        else:  # left, right
                            scroll_js = f"window.scrollBy({{ left: {scroll_amount}, behavior: '" + ("smooth" if smooth else "auto") + "' }})"
                elif pixels is not None:
                    scroll_js = f"window.scrollBy({{ top: {pixels}, behavior: '" + ("smooth" if smooth else "auto") + "' }})"
                
                # Execute page scroll
                await page.evaluate(scroll_js)
                
                # Wait a bit for smooth scrolling to complete
                if smooth:
                    await page.wait_for_timeout(200)
                
                # Get updated scroll position
                final_position = await page.evaluate("() => ({ x: window.scrollX, y: window.scrollY })")
            
            # Calculate elapsed time
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            
            # Calculate scroll distance
            scroll_distance = {
                "x": final_position["x"] - initial_position["x"],
                "y": final_position["y"] - initial_position["y"]
            }
            
            # Determine if scroll was successful (position changed or was already at target)
            success = True
            if direction in ["top", "bottom"] or to_element:
                # For absolute positioning, success is reaching the operation
                message = f"Successfully scrolled to {direction or 'element'}"
            elif scroll_distance["x"] != 0 or scroll_distance["y"] != 0:
                # Position changed
                if direction:
                    message = f"Successfully scrolled {direction}"
                elif pixels is not None:
                    message = f"Successfully scrolled by {pixels} pixels"
                else:
                    message = "Successfully performed scroll operation"
            else:
                # Position didn't change - could be already at limit
                message = "Scroll operation completed (no position change - may be at scroll limit)"
            
            # Collect comprehensive metadata
            try:
                page_url = await page.url()
                page_title = await page.title()
                page_viewport = await page.viewport_size()
                
                # Get scroll limits
                scroll_info = await page.evaluate("""
                    () => ({
                        maxScrollX: document.body.scrollWidth - window.innerWidth,
                        maxScrollY: document.body.scrollHeight - window.innerHeight,
                        innerWidth: window.innerWidth,
                        innerHeight: window.innerHeight,
                        scrollWidth: document.body.scrollWidth,
                        scrollHeight: document.body.scrollHeight
                    })
                """)
            except PlaywrightError:
                page_url = ""
                page_title = ""
                page_viewport = None
                scroll_info = {}
            
            metadata = {
                "scroll_operation": {
                    "type": scroll_type,
                    "direction": direction,
                    "pixels": pixels,
                    "selector": scrolled_element,
                    "to_element": to_element,
                    "smooth": smooth
                },
                "position_change": {
                    "initial": initial_position,
                    "final": final_position,
                    "distance": scroll_distance
                },
                "page_info": {
                    "url": page_url,
                    "title": page_title,
                    "viewport": page_viewport,
                    "scroll_limits": scroll_info
                },
                "timing": {
                    "elapsed_ms": elapsed_ms,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
            
            logger.info(
                "Scroll operation completed successfully",
                session_id=session_id,
                scroll_type=scroll_type,
                initial_position=initial_position,
                final_position=final_position,
                scroll_distance=scroll_distance,
                elapsed_ms=elapsed_ms
            )
            
            return ScrollPageResponse(
                success=success,
                session_id=session_id,
                scroll_position=final_position,
                scrolled_element=scrolled_element,
                scroll_type=scroll_type,
                message=message,
                elapsed_ms=elapsed_ms,
                metadata=metadata
            ).dict()
            
        except PlaywrightError as pe:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            error_message = str(pe)
            logger.error("Scroll operation failed", error=error_message, elapsed_ms=elapsed_ms)
            
            return ScrollPageResponse(
                success=False,
                session_id=session_id,
                scroll_position=initial_position,
                scrolled_element=scrolled_element,
                scroll_type=scroll_type,
                message=f"Scroll operation failed: {error_message}",
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "SCROLL_OPERATION_FAILED",
                    "error_details": error_message,
                    "initial_position": initial_position,
                    "operation_type": scroll_type
                }
            ).dict()
            
    except ValidationError as ve:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        logger.error("Request validation failed", error=str(ve))
        return ScrollPageResponse(
            success=False,
            session_id=session_id,
            scroll_position={"x": 0, "y": 0},
            scroll_type="none",
            message=f"Request validation failed: {str(ve)}",
            elapsed_ms=elapsed_ms,
            metadata={
                "error": "VALIDATION_ERROR",
                "validation_details": str(ve)
            }
        ).dict()
        
    except Exception as e:
        # Handle any unexpected errors
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        error_message = str(e)
        logger.error(
            "Unexpected error during scroll operation",
            session_id=session_id,
            error=error_message,
            elapsed_ms=elapsed_ms
        )
        
        return ScrollPageResponse(
            success=False,
            session_id=session_id,
            scroll_position={"x": 0, "y": 0},
            scroll_type="none",
            message=f"Scroll operation failed: {error_message}",
            elapsed_ms=elapsed_ms,
            metadata={
                "error": "UNEXPECTED_ERROR",
                "error_details": error_message,
                "error_type": type(e).__name__
            }
        ).dict()


@mcp_server.tool()
async def get_scroll_position(
    session_id: str,
    selector: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get the current scroll position of the page or a specific element.
    
    Args:
        session_id: Browser session identifier
        selector: Optional CSS selector to get scroll position of specific element
    
    Returns:
        Dict containing current scroll position and metadata
    """
    start_time = time.monotonic()
    
    logger.info(
        "Getting scroll position",
        session_id=session_id,
        selector=selector
    )
    
    try:
        # Check if session exists
        if session_id not in browser_sessions:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Browser session not found", session_id=session_id)
            return {
                "success": False,
                "session_id": session_id,
                "position": {"x": 0, "y": 0},
                "message": f"Browser session {session_id} not found",
                "elapsed_ms": elapsed_ms,
                "metadata": {"error": "SESSION_NOT_FOUND"}
            }
        
        session = browser_sessions[session_id]
        page: Page = session["page"]
        
        # Verify page is still active
        try:
            await page.title()
        except PlaywrightError as e:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Page is not active", session_id=session_id, error=str(e))
            return {
                "success": False,
                "session_id": session_id,
                "position": {"x": 0, "y": 0},
                "message": f"Page is not active: {str(e)}",
                "elapsed_ms": elapsed_ms,
                "metadata": {"error": "PAGE_NOT_ACTIVE", "error_details": str(e)}
            }
        
        if selector:
            # Get element scroll position
            element = await page.wait_for_selector(selector, timeout=5000, state="attached")
            if not element:
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                return {
                    "success": False,
                    "session_id": session_id,
                    "position": {"x": 0, "y": 0},
                    "message": f"Element not found: {selector}",
                    "elapsed_ms": elapsed_ms,
                    "metadata": {"error": "ELEMENT_NOT_FOUND", "selector": selector}
                }
            
            position = await element.evaluate("el => ({ x: el.scrollLeft, y: el.scrollTop })")
            scroll_info = await element.evaluate("""
                el => ({
                    maxScrollX: el.scrollWidth - el.clientWidth,
                    maxScrollY: el.scrollHeight - el.clientHeight,
                    clientWidth: el.clientWidth,
                    clientHeight: el.clientHeight,
                    scrollWidth: el.scrollWidth,
                    scrollHeight: el.scrollHeight
                })
            """)
            target_type = "element"
        else:
            # Get page scroll position
            position = await page.evaluate("() => ({ x: window.scrollX, y: window.scrollY })")
            scroll_info = await page.evaluate("""
                () => ({
                    maxScrollX: document.body.scrollWidth - window.innerWidth,
                    maxScrollY: document.body.scrollHeight - window.innerHeight,
                    innerWidth: window.innerWidth,
                    innerHeight: window.innerHeight,
                    scrollWidth: document.body.scrollWidth,
                    scrollHeight: document.body.scrollHeight
                })
            """)
            target_type = "page"
        
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        
        metadata = {
            "target_type": target_type,
            "selector": selector,
            "scroll_info": scroll_info,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.info(
            "Scroll position retrieved successfully",
            session_id=session_id,
            position=position,
            target_type=target_type,
            elapsed_ms=elapsed_ms
        )
        
        return {
            "success": True,
            "session_id": session_id,
            "position": position,
            "message": f"Successfully retrieved {target_type} scroll position",
            "elapsed_ms": elapsed_ms,
            "metadata": metadata
        }
        
    except Exception as e:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        error_message = str(e)
        logger.error(
            "Failed to get scroll position",
            session_id=session_id,
            error=error_message,
            elapsed_ms=elapsed_ms
        )
        
        return {
            "success": False,
            "session_id": session_id,
            "position": {"x": 0, "y": 0},
            "message": f"Failed to get scroll position: {error_message}",
            "elapsed_ms": elapsed_ms,
            "metadata": {"error": "OPERATION_FAILED", "error_details": error_message}
        } 
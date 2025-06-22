"""
Drag Element Tool for IntelliBrowse MCP Server.
Implements drag-and-drop functionality with precise control and comprehensive error handling.
"""

import asyncio
import time
from datetime import datetime
from typing import Optional, Dict, Any, List

import structlog
# Import the shared server instance
try:
    from server_instance import mcp_server
except ImportError:
    # Fallback for when running directly from mcp directory
    from server_instance import mcp_server


try:
    from schemas.tools.drag_element_schemas import DragElementRequest, DragElementResponse
except ImportError:
    # Fallback for when running directly from mcp directory
    from schemas.tools.drag_element_schemas import DragElementRequest, DragElementResponse
from .browser_session import browser_sessions

# Initialize structured logger
logger = structlog.get_logger(__name__)

# Get the FastMCP server instance
# Use the shared mcp_server instance (imported above)


@mcp_server.tool()
async def drag_element(
    session_id: str,
    source_selector: str,
    target_selector: Optional[str] = None,
    target_position: Optional[Dict[str, int]] = None,
    steps: Optional[int] = 10,
    timeout_ms: Optional[int] = 10000,
    force: Optional[bool] = False,
    hover_before_drag: Optional[bool] = True,
    delay_between_steps: Optional[int] = 50
) -> Dict[str, Any]:
    """
    Drag element from source to target location with smooth animation.
    
    Implements comprehensive drag-and-drop functionality with support for:
    - Target element or coordinate-based dragging
    - Smooth multi-step drag animations
    - Element actionability validation
    - Comprehensive error handling and recovery
    - Rich metadata and drag path tracking
    
    Args:
        session_id: Active browser session ID
        source_selector: CSS selector for element to drag
        target_selector: CSS selector for target element (alternative to target_position)
        target_position: Target coordinates as {"x": 100, "y": 200}
        steps: Number of intermediate steps for smooth drag (1-100)
        timeout_ms: Operation timeout in milliseconds (1000-60000)
        force: Force drag even if element not actionable
        hover_before_drag: Hover over source element before dragging
        delay_between_steps: Delay between drag steps in milliseconds (0-1000)
    
    Returns:
        Dict containing drag operation results, element details, and metadata
        
    Raises:
        ValueError: For invalid input parameters
        RuntimeError: For session or browser operation failures
    """
    
    # Validate inputs using Pydantic
    try:
        request = DragElementRequest(
            session_id=session_id,
            source_selector=source_selector,
            target_selector=target_selector,
            target_position=target_position,
            steps=steps,
            timeout_ms=timeout_ms,
            force=force,
            hover_before_drag=hover_before_drag,
            delay_between_steps=delay_between_steps
        )
    except Exception as e:
        logger.error("drag_element_validation_failed", error=str(e), session_id=session_id)
        return DragElementResponse(
            success=False,
            message=f"Invalid input parameters: {str(e)}",
            session_id=session_id,
            timestamp=datetime.utcnow().isoformat(),
            error_type="ValidationError",
            error_details={"validation_error": str(e)}
        ).dict()

    # Validate that either target_selector or target_position is provided
    if not target_selector and not target_position:
        error_msg = "Either target_selector or target_position must be provided"
        logger.error("drag_element_missing_target", session_id=session_id, error=error_msg)
        return DragElementResponse(
            success=False,
            message=error_msg,
            session_id=session_id,
            timestamp=datetime.utcnow().isoformat(),
            error_type="ValidationError",
            error_details={"missing_target": True}
        ).dict()

    operation_start_time = time.time()
    logger.info(
        "drag_element_started",
        session_id=session_id,
        source_selector=source_selector,
        target_selector=target_selector,
        target_position=target_position,
        steps=steps,
        timeout_ms=timeout_ms
    )

    try:
        # Get browser session
        if session_id not in browser_sessions:
            error_msg = f"Browser session '{session_id}' not found"
            logger.error("drag_element_session_not_found", session_id=session_id)
            return DragElementResponse(
                success=False,
                message=error_msg,
                session_id=session_id,
                timestamp=datetime.utcnow().isoformat(),
                error_type="SessionNotFound",
                error_details={"session_id": session_id}
            ).dict()

        session = browser_sessions[session_id]
        page = session["page"]

        # Verify page is accessible
        if page.is_closed():
            error_msg = f"Browser page for session '{session_id}' is closed"
            logger.error("drag_element_page_closed", session_id=session_id)
            return DragElementResponse(
                success=False,
                message=error_msg,
                session_id=session_id,
                timestamp=datetime.utcnow().isoformat(),
                error_type="PageClosed",
                error_details={"session_id": session_id}
            ).dict()

        # Wait for and validate source element
        try:
            source_element = await page.wait_for_selector(
                source_selector, 
                timeout=timeout_ms,
                state="visible" if not force else "attached"
            )
            if not source_element:
                raise Exception(f"Source element '{source_selector}' not found")
        except Exception as e:
            error_msg = f"Failed to find source element '{source_selector}': {str(e)}"
            logger.error("drag_element_source_not_found", session_id=session_id, selector=source_selector, error=str(e))
            return DragElementResponse(
                success=False,
                message=error_msg,
                session_id=session_id,
                timestamp=datetime.utcnow().isoformat(),
                error_type="ElementNotFound",
                error_details={"element": "source", "selector": source_selector, "error": str(e)}
            ).dict()

        # Get source element details
        source_box = await source_element.bounding_box()
        if not source_box:
            error_msg = f"Source element '{source_selector}' has no bounding box"
            logger.error("drag_element_source_no_box", session_id=session_id, selector=source_selector)
            return DragElementResponse(
                success=False,
                message=error_msg,
                session_id=session_id,
                timestamp=datetime.utcnow().isoformat(),
                error_type="ElementNotVisible",
                error_details={"element": "source", "selector": source_selector}
            ).dict()

        source_center = {
            "x": int(source_box["x"] + source_box["width"] / 2),
            "y": int(source_box["y"] + source_box["height"] / 2)
        }

        source_element_info = {
            "selector": source_selector,
            "position": {"x": int(source_box["x"]), "y": int(source_box["y"])},
            "size": {"width": int(source_box["width"]), "height": int(source_box["height"])},
            "center": source_center
        }

        # Determine target position
        target_element_info = None
        final_target_position = None

        if target_selector:
            # Target by element selector
            try:
                target_element = await page.wait_for_selector(
                    target_selector,
                    timeout=timeout_ms,
                    state="visible" if not force else "attached"
                )
                if not target_element:
                    raise Exception(f"Target element '{target_selector}' not found")
                
                target_box = await target_element.bounding_box()
                if not target_box:
                    raise Exception(f"Target element '{target_selector}' has no bounding box")
                
                final_target_position = {
                    "x": int(target_box["x"] + target_box["width"] / 2),
                    "y": int(target_box["y"] + target_box["height"] / 2)
                }
                
                target_element_info = {
                    "selector": target_selector,
                    "position": {"x": int(target_box["x"]), "y": int(target_box["y"])},
                    "size": {"width": int(target_box["width"]), "height": int(target_box["height"])},
                    "center": final_target_position
                }
                
            except Exception as e:
                error_msg = f"Failed to find target element '{target_selector}': {str(e)}"
                logger.error("drag_element_target_not_found", session_id=session_id, selector=target_selector, error=str(e))
                return DragElementResponse(
                    success=False,
                    message=error_msg,
                    session_id=session_id,
                    timestamp=datetime.utcnow().isoformat(),
                    error_type="ElementNotFound",
                    error_details={"element": "target", "selector": target_selector, "error": str(e)}
                ).dict()
        else:
            # Target by coordinates
            final_target_position = target_position

        # Hover over source element if requested
        if hover_before_drag:
            try:
                await source_element.hover(timeout=timeout_ms)
                logger.debug("drag_element_hovered_source", session_id=session_id, selector=source_selector)
            except Exception as e:
                logger.warning("drag_element_hover_failed", session_id=session_id, selector=source_selector, error=str(e))

        # Calculate drag path with smooth steps
        drag_path = []
        source_x, source_y = source_center["x"], source_center["y"]
        target_x, target_y = final_target_position["x"], final_target_position["y"]
        
        # Generate intermediate points for smooth drag
        for i in range(steps + 1):
            progress = i / steps
            current_x = int(source_x + (target_x - source_x) * progress)
            current_y = int(source_y + (target_y - source_y) * progress)
            drag_path.append({"x": current_x, "y": current_y})

        # Perform drag operation
        try:
            # Start drag from source element center
            await page.mouse.move(source_x, source_y)
            await page.mouse.down()
            
            # Drag through intermediate points
            for i, point in enumerate(drag_path[1:], 1):  # Skip first point (source)
                await page.mouse.move(point["x"], point["y"])
                if delay_between_steps > 0:
                    await asyncio.sleep(delay_between_steps / 1000)
                
                logger.debug(
                    "drag_element_step",
                    session_id=session_id,
                    step=i,
                    total_steps=len(drag_path) - 1,
                    position=point
                )
            
            # Release at target position
            await page.mouse.up()
            
            operation_time_ms = int((time.time() - operation_start_time) * 1000)
            
            logger.info(
                "drag_element_completed",
                session_id=session_id,
                source_selector=source_selector,
                target_selector=target_selector,
                target_position=final_target_position,
                steps_executed=len(drag_path) - 1,
                operation_time_ms=operation_time_ms
            )

            return DragElementResponse(
                success=True,
                message=f"Successfully dragged element from '{source_selector}' to target",
                source_element=source_element_info,
                target_element=target_element_info,
                target_position=final_target_position,
                drag_path=drag_path,
                operation_time_ms=operation_time_ms,
                steps_executed=len(drag_path) - 1,
                session_id=session_id,
                timestamp=datetime.utcnow().isoformat()
            ).dict()

        except Exception as e:
            error_msg = f"Failed to execute drag operation: {str(e)}"
            logger.error("drag_element_operation_failed", session_id=session_id, error=str(e))
            
            # Ensure mouse is released on failure
            try:
                await page.mouse.up()
            except:
                pass
            
            return DragElementResponse(
                success=False,
                message=error_msg,
                source_element=source_element_info,
                target_element=target_element_info,
                target_position=final_target_position,
                session_id=session_id,
                timestamp=datetime.utcnow().isoformat(),
                error_type="DragOperationFailed",
                error_details={"error": str(e)}
            ).dict()

    except Exception as e:
        operation_time_ms = int((time.time() - operation_start_time) * 1000)
        error_msg = f"Drag element operation failed: {str(e)}"
        logger.error(
            "drag_element_failed",
            session_id=session_id,
            source_selector=source_selector,
            error=str(e),
            operation_time_ms=operation_time_ms
        )

        return DragElementResponse(
            success=False,
            message=error_msg,
            session_id=session_id,
            timestamp=datetime.utcnow().isoformat(),
            error_type="UnexpectedError",
            error_details={"error": str(e), "operation_time_ms": operation_time_ms}
        ).dict()


# Tool registration will be handled by FastMCP automatically
logger.info("drag_element_tool_registered", tool="drag_element") 
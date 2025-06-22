"""
Click IFrame Element Tool for IntelliBrowse MCP Server.
Handles element interactions within iframe contexts with comprehensive error handling.
"""

import time
from datetime import datetime
from typing import Optional, Dict, Any

import structlog
# Import the shared server instance
try:
    from server_instance import mcp_server
except ImportError:
    # Fallback for when running directly from mcp directory
    from server_instance import mcp_server


try:
    from schemas.tools.click_iframe_element_schemas import ClickIFrameElementRequest, ClickIFrameElementResponse
except ImportError:
    # Fallback for when running directly from mcp directory
    from schemas.tools.click_iframe_element_schemas import ClickIFrameElementRequest, ClickIFrameElementResponse
from .browser_session import browser_sessions

# Initialize structured logger
logger = structlog.get_logger(__name__)

# Get the FastMCP server instance
# Use the shared mcp_server instance (imported above)


@mcp_server.tool()
async def click_iframe_element(
    session_id: str,
    iframe_selector: str,
    element_selector: str,
    click_type: Optional[str] = "single",
    timeout_ms: Optional[int] = 10000,
    wait_for_iframe: Optional[int] = 5000,
    force: Optional[bool] = False,
    button: Optional[str] = "left",
    click_count: Optional[int] = 1
) -> Dict[str, Any]:
    """
    Click element within an iframe with comprehensive context management.
    
    Implements iframe element interaction with support for:
    - Automatic iframe context switching
    - Multiple click types (single, double, right-click)
    - IFrame loading validation and waiting
    - Element actionability validation within iframe context
    - Comprehensive error handling and recovery
    
    Args:
        session_id: Active browser session ID
        iframe_selector: CSS selector for iframe element
        element_selector: CSS selector for element within iframe
        click_type: Type of click to perform (single, double, right)
        timeout_ms: Element wait timeout in milliseconds (1000-60000)
        wait_for_iframe: IFrame load timeout in milliseconds (1000-30000)
        force: Force click even if element not actionable
        button: Mouse button to use (left, right, middle)
        click_count: Number of clicks to perform (1-10)
    
    Returns:
        Dict containing click operation results, iframe details, and metadata
        
    Raises:
        ValueError: For invalid input parameters
        RuntimeError: For session or browser operation failures
    """
    
    # Validate inputs using Pydantic
    try:
        request = ClickIFrameElementRequest(
            session_id=session_id,
            iframe_selector=iframe_selector,
            element_selector=element_selector,
            click_type=click_type,
            timeout_ms=timeout_ms,
            wait_for_iframe=wait_for_iframe,
            force=force,
            button=button,
            click_count=click_count
        )
    except Exception as e:
        logger.error("click_iframe_element_validation_failed", error=str(e), session_id=session_id)
        return ClickIFrameElementResponse(
            success=False,
            message=f"Invalid input parameters: {str(e)}",
            session_id=session_id,
            timestamp=datetime.utcnow().isoformat(),
            error_type="ValidationError",
            error_details={"validation_error": str(e)}
        ).dict()

    operation_start_time = time.time()
    logger.info(
        "click_iframe_element_started",
        session_id=session_id,
        iframe_selector=iframe_selector,
        element_selector=element_selector,
        click_type=click_type,
        timeout_ms=timeout_ms,
        wait_for_iframe=wait_for_iframe
    )

    try:
        # Get browser session
        if session_id not in browser_sessions:
            error_msg = f"Browser session '{session_id}' not found"
            logger.error("click_iframe_element_session_not_found", session_id=session_id)
            return ClickIFrameElementResponse(
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
            logger.error("click_iframe_element_page_closed", session_id=session_id)
            return ClickIFrameElementResponse(
                success=False,
                message=error_msg,
                session_id=session_id,
                timestamp=datetime.utcnow().isoformat(),
                error_type="PageClosed",
                error_details={"session_id": session_id}
            ).dict()

        # Wait for and validate iframe element
        iframe_switch_start_time = time.time()
        try:
            iframe_element = await page.wait_for_selector(
                iframe_selector, 
                timeout=wait_for_iframe,
                state="visible" if not force else "attached"
            )
            if not iframe_element:
                raise Exception(f"IFrame element '{iframe_selector}' not found")
        except Exception as e:
            error_msg = f"Failed to find iframe element '{iframe_selector}': {str(e)}"
            logger.error("click_iframe_element_iframe_not_found", session_id=session_id, selector=iframe_selector, error=str(e))
            return ClickIFrameElementResponse(
                success=False,
                message=error_msg,
                session_id=session_id,
                timestamp=datetime.utcnow().isoformat(),
                error_type="IFrameNotFound",
                error_details={"iframe_selector": iframe_selector, "error": str(e)}
            ).dict()

        # Get iframe element details
        iframe_box = await iframe_element.bounding_box()
        iframe_element_info = None
        if iframe_box:
            iframe_element_info = {
                "selector": iframe_selector,
                "position": {"x": int(iframe_box["x"]), "y": int(iframe_box["y"])},
                "size": {"width": int(iframe_box["width"]), "height": int(iframe_box["height"])},
                "loaded": True
            }

        # Get iframe content frame
        try:
            iframe_content = await iframe_element.content_frame()
            if not iframe_content:
                raise Exception(f"Unable to access iframe content for '{iframe_selector}'")
        except Exception as e:
            error_msg = f"Failed to access iframe content '{iframe_selector}': {str(e)}"
            logger.error("click_iframe_element_content_access_failed", session_id=session_id, selector=iframe_selector, error=str(e))
            return ClickIFrameElementResponse(
                success=False,
                message=error_msg,
                iframe_element=iframe_element_info,
                iframe_loaded=False,
                session_id=session_id,
                timestamp=datetime.utcnow().isoformat(),
                error_type="IFrameContentAccessFailed",
                error_details={"iframe_selector": iframe_selector, "error": str(e)}
            ).dict()

        iframe_switch_time_ms = int((time.time() - iframe_switch_start_time) * 1000)
        
        # Wait for target element within iframe
        try:
            target_element = await iframe_content.wait_for_selector(
                element_selector,
                timeout=timeout_ms,
                state="visible" if not force else "attached"
            )
            if not target_element:
                raise Exception(f"Target element '{element_selector}' not found within iframe")
        except Exception as e:
            error_msg = f"Failed to find target element '{element_selector}' within iframe: {str(e)}"
            logger.error("click_iframe_element_target_not_found", session_id=session_id, 
                        iframe_selector=iframe_selector, element_selector=element_selector, error=str(e))
            return ClickIFrameElementResponse(
                success=False,
                message=error_msg,
                iframe_element=iframe_element_info,
                iframe_loaded=True,
                iframe_switch_time_ms=iframe_switch_time_ms,
                session_id=session_id,
                timestamp=datetime.utcnow().isoformat(),
                error_type="ElementNotFound",
                error_details={"element_selector": element_selector, "error": str(e)}
            ).dict()

        # Get target element details
        target_box = await target_element.bounding_box()
        target_element_info = None
        click_position = None
        
        if target_box:
            target_element_info = {
                "selector": element_selector,
                "position": {"x": int(target_box["x"]), "y": int(target_box["y"])},
                "size": {"width": int(target_box["width"]), "height": int(target_box["height"])}
            }
            
            # Calculate click position (center of element)
            click_position = {
                "x": int(target_box["x"] + target_box["width"] / 2),
                "y": int(target_box["y"] + target_box["height"] / 2)
            }
            
            # Try to get element text content
            try:
                element_text = await target_element.text_content()
                if element_text and element_text.strip():
                    target_element_info["text"] = element_text.strip()
            except:
                pass

        # Perform click operation
        try:
            # Configure click options
            click_options = {
                "button": button,
                "click_count": click_count if click_type == "single" else (2 if click_type == "double" else 1),
                "timeout": timeout_ms,
                "force": force
            }
            
            # Handle right-click specially
            if click_type == "right":
                click_options["button"] = "right"
                click_options["click_count"] = 1
            
            # Perform the click
            await target_element.click(**click_options)
            
            operation_time_ms = int((time.time() - operation_start_time) * 1000)
            
            logger.info(
                "click_iframe_element_completed",
                session_id=session_id,
                iframe_selector=iframe_selector,
                element_selector=element_selector,
                click_type=click_type,
                button=button,
                click_count=click_count,
                operation_time_ms=operation_time_ms,
                iframe_switch_time_ms=iframe_switch_time_ms
            )

            return ClickIFrameElementResponse(
                success=True,
                message=f"Successfully clicked element '{element_selector}' within iframe '{iframe_selector}'",
                iframe_element=iframe_element_info,
                iframe_loaded=True,
                target_element=target_element_info,
                click_type=click_type,
                button=button,
                click_count=click_count,
                click_position=click_position,
                operation_time_ms=operation_time_ms,
                iframe_switch_time_ms=iframe_switch_time_ms,
                session_id=session_id,
                timestamp=datetime.utcnow().isoformat()
            ).dict()

        except Exception as e:
            error_msg = f"Failed to click element '{element_selector}' within iframe: {str(e)}"
            logger.error("click_iframe_element_click_failed", session_id=session_id, 
                        iframe_selector=iframe_selector, element_selector=element_selector, error=str(e))
            
            return ClickIFrameElementResponse(
                success=False,
                message=error_msg,
                iframe_element=iframe_element_info,
                iframe_loaded=True,
                target_element=target_element_info,
                click_type=click_type,
                button=button,
                click_count=click_count,
                click_position=click_position,
                iframe_switch_time_ms=iframe_switch_time_ms,
                session_id=session_id,
                timestamp=datetime.utcnow().isoformat(),
                error_type="ClickOperationFailed",
                error_details={"error": str(e)}
            ).dict()

    except Exception as e:
        operation_time_ms = int((time.time() - operation_start_time) * 1000)
        error_msg = f"Click iframe element operation failed: {str(e)}"
        logger.error(
            "click_iframe_element_failed",
            session_id=session_id,
            iframe_selector=iframe_selector,
            element_selector=element_selector,
            error=str(e),
            operation_time_ms=operation_time_ms
        )

        return ClickIFrameElementResponse(
            success=False,
            message=error_msg,
            session_id=session_id,
            timestamp=datetime.utcnow().isoformat(),
            error_type="UnexpectedError",
            error_details={"error": str(e), "operation_time_ms": operation_time_ms}
        ).dict()


# Tool registration will be handled by FastMCP automatically
logger.info("click_iframe_element_tool_registered", tool="click_iframe_element") 
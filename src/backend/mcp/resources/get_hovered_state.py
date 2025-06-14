"""
Hovered State Resource for IntelliBrowse MCP Server.

This module provides resource capabilities for retrieving hover state information,
supporting hover operation auditing, UI state inspection, and hover-dependent testing workflows.
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional
import structlog
from playwright.async_api import Page, Error as PlaywrightError
import time

# Add parent directory to path for MCP server import
sys.path.append(str(Path(__file__).parent.parent))
from main import mcp_server

# Import browser session utilities
sys.path.append(str(Path(__file__).parent.parent / "tools"))
from browser_session import browser_sessions

logger = structlog.get_logger("intellibrowse.mcp.resources.get_hovered_state")

# Global hover state tracking for audit and inspection
hover_state_tracker = {}


@mcp_server.resource("hoveredstate://{session_id}/{selector}")
async def get_hovered_state(session_id: str, selector: str) -> Dict[str, Any]:
    """
    Gets the current hover state information for a specific element.
    
    This resource provides comprehensive hover state tracking with detailed
    element analysis, supporting hover operation auditing and UI state inspection.
    
    Args:
        session_id: Browser session identifier
        selector: CSS selector targeting the element
    
    Returns:
        Dict containing hover state information and comprehensive element metadata
    """
    logger.info(
        "Retrieving hover state information",
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
                "hover_state": None,
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
                "hover_state": None,
                "metadata": {"error_details": str(e)}
            }
        
        # Get tracked hover state from memory
        state_key = f"{session_id}:{selector}"
        tracked_state = hover_state_tracker.get(state_key, {})
        
        # Locate the element and analyze its current state
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
                    "hover_state": tracked_state,
                    "metadata": {}
                }
            
            # Get element properties and current state
            element_tag = await element.evaluate("el => el.tagName.toLowerCase()")
            element_id = await element.evaluate("el => el.id || ''")
            element_classes = await element.evaluate("el => el.className || ''")
            element_visible = await element.is_visible()
            element_enabled = await element.is_enabled()
            
            # Check if element is currently being hovered (best effort detection)
            try:
                # Get computed styles to detect hover states
                hover_styles = await element.evaluate("""
                    el => {
                        const styles = window.getComputedStyle(el, ':hover');
                        const normalStyles = window.getComputedStyle(el);
                        return {
                            normal: {
                                backgroundColor: normalStyles.backgroundColor,
                                color: normalStyles.color,
                                borderColor: normalStyles.borderColor,
                                transform: normalStyles.transform,
                                boxShadow: normalStyles.boxShadow,
                                opacity: normalStyles.opacity,
                                cursor: normalStyles.cursor
                            },
                            hover: {
                                backgroundColor: styles.backgroundColor,
                                color: styles.color,
                                borderColor: styles.borderColor,
                                transform: styles.transform,
                                boxShadow: styles.boxShadow,
                                opacity: styles.opacity,
                                cursor: styles.cursor
                            }
                        };
                    }
                """)
            except PlaywrightError:
                hover_styles = {"normal": {}, "hover": {}}
            
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
            
            # Determine if element appears to be in hover state
            has_hover_differences = False
            if hover_styles["normal"] and hover_styles["hover"]:
                for prop in hover_styles["normal"]:
                    if hover_styles["normal"][prop] != hover_styles["hover"][prop]:
                        has_hover_differences = True
                        break
            
            # Build comprehensive hover state information
            current_state = {
                "selector": selector,
                "element_exists": True,
                "element_visible": element_visible,
                "element_enabled": element_enabled,
                "has_hover_styles": has_hover_differences,
                "hover_styles": hover_styles,
                "element_bounds": element_bounds,
                "timestamp": time.time()
            }
            
            # Merge with tracked state
            hover_state_info = {
                "current_state": current_state,
                "tracked_state": tracked_state,
                "last_hover_operation": tracked_state.get("last_hover_operation"),
                "hover_count": tracked_state.get("hover_count", 0),
                "first_hover_time": tracked_state.get("first_hover_time"),
                "last_hover_time": tracked_state.get("last_hover_time")
            }
            
            # Collect comprehensive metadata
            metadata = {
                "element_analysis": {
                    "tag": element_tag,
                    "id": element_id,
                    "classes": element_classes,
                    "visible": element_visible,
                    "enabled": element_enabled,
                    "has_hover_styles": has_hover_differences
                },
                "hover_analysis": {
                    "has_tracked_state": bool(tracked_state),
                    "hover_count": tracked_state.get("hover_count", 0),
                    "style_differences_detected": has_hover_differences,
                    "hover_styles_available": bool(hover_styles["hover"])
                },
                "element_bounds": element_bounds,
                "page_context": {
                    "url": page_url,
                    "title": page_title
                },
                "retrieval_info": {
                    "selector": selector,
                    "session_id": session_id,
                    "method": "playwright_evaluation",
                    "timestamp": time.time()
                }
            }
            
            logger.info(
                "Hover state retrieved successfully",
                selector=selector,
                element_tag=element_tag,
                has_hover_differences=has_hover_differences,
                hover_count=tracked_state.get("hover_count", 0)
            )
            
            return {
                "selector": selector,
                "session_id": session_id,
                "hover_state": hover_state_info,
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
                "hover_state": tracked_state,
                "metadata": {"error_details": error_message}
            }
            
    except Exception as e:
        # Handle any unexpected errors
        error_message = str(e)
        logger.error(
            "Unexpected error during hover state retrieval",
            session_id=session_id,
            selector=selector,
            error=error_message
        )
        return {
            "error": "UNEXPECTED_ERROR",
            "message": f"Failed to retrieve hover state: {error_message}",
            "session_id": session_id,
            "selector": selector,
            "hover_state": None,
            "metadata": {"error_details": error_message}
        }


@mcp_server.resource("hoverhistory://{session_id}")
async def get_hover_history(session_id: str) -> Dict[str, Any]:
    """
    Gets the complete hover operation history for a browser session.
    
    This resource provides comprehensive hover operation auditing and analysis,
    supporting test reporting and hover behavior investigation.
    
    Args:
        session_id: Browser session identifier
    
    Returns:
        Dict containing complete hover history and operation statistics
    """
    logger.info("Retrieving hover history", session_id=session_id)
    
    try:
        # Check if session exists
        if session_id not in browser_sessions:
            logger.error("Browser session not found", session_id=session_id)
            return {
                "error": "SESSION_NOT_FOUND",
                "message": f"Browser session {session_id} not found",
                "session_id": session_id,
                "hover_history": [],
                "statistics": {}
            }
        
        # Collect all hover states for this session
        session_hover_states = {}
        total_hovers = 0
        
        for state_key, state_data in hover_state_tracker.items():
            if state_key.startswith(f"{session_id}:"):
                selector = state_key.replace(f"{session_id}:", "")
                session_hover_states[selector] = state_data
                total_hovers += state_data.get("hover_count", 0)
        
        # Calculate statistics
        statistics = {
            "session_id": session_id,
            "total_hover_operations": total_hovers,
            "unique_elements_hovered": len(session_hover_states),
            "active_session": session_id in browser_sessions,
            "timestamp": time.time()
        }
        
        # Add timing statistics if available
        if session_hover_states:
            hover_times = []
            for state_data in session_hover_states.values():
                if state_data.get("first_hover_time"):
                    hover_times.append(state_data["first_hover_time"])
                if state_data.get("last_hover_time"):
                    hover_times.append(state_data["last_hover_time"])
            
            if hover_times:
                statistics.update({
                    "first_hover_time": min(hover_times),
                    "last_hover_time": max(hover_times),
                    "hover_session_duration": max(hover_times) - min(hover_times) if len(hover_times) > 1 else 0
                })
        
        logger.info(
            "Hover history retrieved successfully",
            session_id=session_id,
            total_hovers=total_hovers,
            unique_elements=len(session_hover_states)
        )
        
        return {
            "session_id": session_id,
            "hover_history": session_hover_states,
            "statistics": statistics,
            "metadata": {
                "retrieval_timestamp": time.time(),
                "session_active": session_id in browser_sessions
            }
        }
        
    except Exception as e:
        error_message = str(e)
        logger.error(
            "Unexpected error during hover history retrieval",
            session_id=session_id,
            error=error_message
        )
        return {
            "error": "UNEXPECTED_ERROR",
            "message": f"Failed to retrieve hover history: {error_message}",
            "session_id": session_id,
            "hover_history": [],
            "statistics": {},
            "metadata": {"error_details": error_message}
        }


def track_hover_operation(session_id: str, selector: str, operation_data: Dict[str, Any]) -> None:
    """
    Track a hover operation for auditing and state management.
    
    This function should be called by the hover_element tool to maintain
    hover state tracking across operations.
    
    Args:
        session_id: Browser session identifier
        selector: CSS selector of the hovered element
        operation_data: Data from the hover operation
    """
    state_key = f"{session_id}:{selector}"
    current_time = time.time()
    
    if state_key not in hover_state_tracker:
        hover_state_tracker[state_key] = {
            "hover_count": 0,
            "first_hover_time": current_time,
            "last_hover_time": current_time,
            "last_hover_operation": operation_data,
            "hover_operations": []
        }
    
    # Update tracking data
    hover_state_tracker[state_key]["hover_count"] += 1
    hover_state_tracker[state_key]["last_hover_time"] = current_time
    hover_state_tracker[state_key]["last_hover_operation"] = operation_data
    hover_state_tracker[state_key]["hover_operations"].append({
        "timestamp": current_time,
        "operation_data": operation_data
    })
    
    # Keep only last 10 operations to prevent memory bloat
    if len(hover_state_tracker[state_key]["hover_operations"]) > 10:
        hover_state_tracker[state_key]["hover_operations"] = \
            hover_state_tracker[state_key]["hover_operations"][-10:]
    
    logger.info(
        "Hover operation tracked",
        session_id=session_id,
        selector=selector,
        hover_count=hover_state_tracker[state_key]["hover_count"]
    ) 
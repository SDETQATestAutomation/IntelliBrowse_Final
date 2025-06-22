"""
Last Scroll Position Resource for IntelliBrowse MCP Server.

This module provides resource capabilities for retrieving the last known scroll position
from browser sessions, supporting position tracking, session restoration, and scroll
state management for testing workflows.
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import structlog
from playwright.async_api import Page, Error as PlaywrightError

# Add parent directory to path for MCP server import
sys.path.append(str(Path(__file__).parent.parent))
try:
    from server_instance import mcp_server
except ImportError:
    # Fallback for when running directly from mcp directory
    from server_instance import mcp_server

# Import browser session utilities
sys.path.append(str(Path(__file__).parent.parent / "tools"))
try:
    from tools.browser_session import browser_sessions
except ImportError:
    # Fallback for when running directly from mcp directory
    from tools.browser_session import browser_sessions

logger = structlog.get_logger("intellibrowse.mcp.resources.get_last_scroll_position")

# In-memory storage for scroll position history (session-based)
scroll_position_history: Dict[str, List[Dict[str, Any]]] = {}


def _add_scroll_position_to_history(session_id: str, position_data: Dict[str, Any]) -> None:
    """
    Add a scroll position record to the session history.
    
    Args:
        session_id: Browser session identifier
        position_data: Scroll position data to store
    """
    if session_id not in scroll_position_history:
        scroll_position_history[session_id] = []
    
    # Limit history to last 50 positions per session
    if len(scroll_position_history[session_id]) >= 50:
        scroll_position_history[session_id].pop(0)
    
    scroll_position_history[session_id].append(position_data)


@mcp_server.resource("lastscrollposition://{session_id}")
async def get_last_scroll_position(session_id: str) -> Dict[str, Any]:
    """
    Gets the last known scroll position for a browser session.
    
    This resource provides access to the most recent scroll position data
    for a given session, including position coordinates, timing, and metadata.
    
    Args:
        session_id: Browser session identifier
    
    Returns:
        Dict containing last scroll position and comprehensive metadata
    """
    logger.info(
        "Retrieving last scroll position",
        session_id=session_id
    )
    
    try:
        # Check if session exists in browser sessions
        if session_id not in browser_sessions:
            logger.error("Browser session not found", session_id=session_id)
            return {
                "error": "SESSION_NOT_FOUND",
                "message": f"Browser session {session_id} not found",
                "session_id": session_id,
                "last_position": None,
                "metadata": {
                    "error_details": "Session does not exist in active browser sessions"
                }
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
                "last_position": None,
                "metadata": {"error_details": str(e)}
            }
        
        # Get current scroll position as the "last" position
        try:
            current_position = await page.evaluate("() => ({ x: window.scrollX, y: window.scrollY })")
            
            # Get additional scroll context
            scroll_info = await page.evaluate("""
                () => ({
                    maxScrollX: document.body.scrollWidth - window.innerWidth,
                    maxScrollY: document.body.scrollHeight - window.innerHeight,
                    innerWidth: window.innerWidth,
                    innerHeight: window.innerHeight,
                    scrollWidth: document.body.scrollWidth,
                    scrollHeight: document.body.scrollHeight,
                    documentHeight: document.documentElement.scrollHeight,
                    bodyHeight: document.body.scrollHeight
                })
            """)
            
            # Get page context
            page_url = await page.url()
            page_title = await page.title()
            page_viewport = await page.viewport_size()
            
        except PlaywrightError as pe:
            logger.error("Failed to get current scroll position", session_id=session_id, error=str(pe))
            return {
                "error": "POSITION_RETRIEVAL_FAILED",
                "message": f"Failed to retrieve current scroll position: {str(pe)}",
                "session_id": session_id,
                "last_position": None,
                "metadata": {"error_details": str(pe)}
            }
        
        # Check for historical scroll positions
        session_history = scroll_position_history.get(session_id, [])
        last_recorded_position = session_history[-1] if session_history else None
        
        # Calculate scroll percentage
        scroll_percentage = {
            "x": (current_position["x"] / scroll_info["maxScrollX"] * 100) if scroll_info["maxScrollX"] > 0 else 0,
            "y": (current_position["y"] / scroll_info["maxScrollY"] * 100) if scroll_info["maxScrollY"] > 0 else 0
        }
        
        # Determine scroll position description
        if current_position["y"] <= 10:
            position_description = "top"
        elif current_position["y"] >= scroll_info["maxScrollY"] - 10:
            position_description = "bottom"
        elif 40 <= scroll_percentage["y"] <= 60:
            position_description = "middle"
        else:
            position_description = f"{scroll_percentage['y']:.1f}% from top"
        
        # Create comprehensive position data
        position_data = {
            "coordinates": current_position,
            "percentage": scroll_percentage,
            "description": position_description,
            "timestamp": datetime.utcnow().isoformat(),
            "scroll_limits": scroll_info,
            "page_context": {
                "url": page_url,
                "title": page_title,
                "viewport": page_viewport
            }
        }
        
        # Add to history
        _add_scroll_position_to_history(session_id, position_data)
        
        # Prepare comprehensive metadata
        metadata = {
            "session_info": {
                "session_id": session_id,
                "page_active": True,
                "page_url": page_url,
                "page_title": page_title
            },
            "position_analysis": {
                "is_at_top": current_position["y"] <= 10,
                "is_at_bottom": current_position["y"] >= scroll_info["maxScrollY"] - 10,
                "is_in_middle": 40 <= scroll_percentage["y"] <= 60,
                "can_scroll_up": current_position["y"] > 0,
                "can_scroll_down": current_position["y"] < scroll_info["maxScrollY"],
                "can_scroll_left": current_position["x"] > 0,
                "can_scroll_right": current_position["x"] < scroll_info["maxScrollX"]
            },
            "scroll_context": {
                "total_scrollable_height": scroll_info["maxScrollY"],
                "total_scrollable_width": scroll_info["maxScrollX"],
                "viewport_dimensions": page_viewport,
                "document_dimensions": {
                    "width": scroll_info["scrollWidth"],
                    "height": scroll_info["scrollHeight"]
                }
            },
            "history_info": {
                "total_positions_recorded": len(session_history),
                "last_recorded_position": last_recorded_position,
                "position_changed": (
                    last_recorded_position is None or 
                    last_recorded_position["coordinates"] != current_position
                )
            },
            "retrieval_info": {
                "timestamp": datetime.utcnow().isoformat(),
                "method": "current_position_query",
                "source": "playwright_evaluation"
            }
        }
        
        logger.info(
            "Last scroll position retrieved successfully",
            session_id=session_id,
            position=current_position,
            description=position_description,
            percentage=scroll_percentage
        )
        
        return {
            "session_id": session_id,
            "last_position": position_data,
            "metadata": metadata
        }
        
    except Exception as e:
        # Handle any unexpected errors
        error_message = str(e)
        logger.error(
            "Unexpected error during last scroll position retrieval",
            session_id=session_id,
            error=error_message
        )
        
        return {
            "error": "UNEXPECTED_ERROR",
            "message": f"Failed to retrieve last scroll position: {error_message}",
            "session_id": session_id,
            "last_position": None,
            "metadata": {
                "error_details": error_message,
                "error_type": type(e).__name__
            }
        }


@mcp_server.resource("scrollhistory://{session_id}")
async def get_scroll_history(session_id: str) -> Dict[str, Any]:
    """
    Gets the complete scroll position history for a browser session.
    
    This resource provides access to all recorded scroll positions
    for a given session, supporting position analysis and testing workflows.
    
    Args:
        session_id: Browser session identifier
    
    Returns:
        Dict containing complete scroll history and analysis
    """
    logger.info(
        "Retrieving scroll position history",
        session_id=session_id
    )
    
    try:
        # Check if session exists in browser sessions
        if session_id not in browser_sessions:
            logger.error("Browser session not found", session_id=session_id)
            return {
                "error": "SESSION_NOT_FOUND",
                "message": f"Browser session {session_id} not found",
                "session_id": session_id,
                "history": [],
                "metadata": {}
            }
        
        # Get session history
        session_history = scroll_position_history.get(session_id, [])
        
        # Calculate history statistics
        if session_history:
            positions = [pos["coordinates"] for pos in session_history]
            
            # Calculate movement statistics
            total_movements = len(positions) - 1 if len(positions) > 1 else 0
            total_vertical_distance = 0
            total_horizontal_distance = 0
            
            for i in range(1, len(positions)):
                prev_pos = positions[i-1]
                curr_pos = positions[i]
                total_vertical_distance += abs(curr_pos["y"] - prev_pos["y"])
                total_horizontal_distance += abs(curr_pos["x"] - prev_pos["x"])
            
            # Find position extremes
            min_y = min(pos["y"] for pos in positions)
            max_y = max(pos["y"] for pos in positions)
            min_x = min(pos["x"] for pos in positions)
            max_x = max(pos["x"] for pos in positions)
            
            # Calculate time span
            first_timestamp = session_history[0]["timestamp"]
            last_timestamp = session_history[-1]["timestamp"]
            
            statistics = {
                "total_positions": len(session_history),
                "total_movements": total_movements,
                "vertical_distance_traveled": total_vertical_distance,
                "horizontal_distance_traveled": total_horizontal_distance,
                "position_range": {
                    "y_range": {"min": min_y, "max": max_y, "span": max_y - min_y},
                    "x_range": {"min": min_x, "max": max_x, "span": max_x - min_x}
                },
                "time_span": {
                    "first_position": first_timestamp,
                    "last_position": last_timestamp
                }
            }
        else:
            statistics = {
                "total_positions": 0,
                "total_movements": 0,
                "vertical_distance_traveled": 0,
                "horizontal_distance_traveled": 0,
                "position_range": {},
                "time_span": {}
            }
        
        # Prepare metadata
        metadata = {
            "session_id": session_id,
            "history_statistics": statistics,
            "retrieval_info": {
                "timestamp": datetime.utcnow().isoformat(),
                "total_sessions_tracked": len(scroll_position_history),
                "history_limit_per_session": 50
            }
        }
        
        logger.info(
            "Scroll history retrieved successfully",
            session_id=session_id,
            total_positions=len(session_history),
            total_movements=statistics["total_movements"]
        )
        
        return {
            "session_id": session_id,
            "history": session_history,
            "metadata": metadata
        }
        
    except Exception as e:
        # Handle any unexpected errors
        error_message = str(e)
        logger.error(
            "Unexpected error during scroll history retrieval",
            session_id=session_id,
            error=error_message
        )
        
        return {
            "error": "UNEXPECTED_ERROR",
            "message": f"Failed to retrieve scroll history: {error_message}",
            "session_id": session_id,
            "history": [],
            "metadata": {
                "error_details": error_message,
                "error_type": type(e).__name__
            }
        }


@mcp_server.resource("scrollsummary://{session_id}")
async def get_scroll_summary(session_id: str) -> Dict[str, Any]:
    """
    Gets a summary of scroll behavior and patterns for a browser session.
    
    This resource provides high-level analysis of scroll activity,
    supporting performance analysis and user behavior insights.
    
    Args:
        session_id: Browser session identifier
    
    Returns:
        Dict containing scroll behavior summary and insights
    """
    logger.info(
        "Retrieving scroll behavior summary",
        session_id=session_id
    )
    
    try:
        # Check if session exists in browser sessions
        if session_id not in browser_sessions:
            logger.error("Browser session not found", session_id=session_id)
            return {
                "error": "SESSION_NOT_FOUND",
                "message": f"Browser session {session_id} not found",
                "session_id": session_id,
                "summary": {},
                "metadata": {}
            }
        
        session = browser_sessions[session_id]
        page: Page = session["page"]
        
        # Get current page info
        try:
            page_url = await page.url()
            page_title = await page.title()
            current_position = await page.evaluate("() => ({ x: window.scrollX, y: window.scrollY })")
        except PlaywrightError as e:
            logger.error("Failed to get page info", session_id=session_id, error=str(e))
            return {
                "error": "PAGE_INFO_FAILED",
                "message": f"Failed to get page information: {str(e)}",
                "session_id": session_id,
                "summary": {},
                "metadata": {"error_details": str(e)}
            }
        
        # Get session history
        session_history = scroll_position_history.get(session_id, [])
        
        # Analyze scroll patterns
        if session_history:
            positions = [pos["coordinates"] for pos in session_history]
            
            # Analyze scroll direction preferences
            vertical_movements = []
            horizontal_movements = []
            
            for i in range(1, len(positions)):
                prev_pos = positions[i-1]
                curr_pos = positions[i]
                
                v_movement = curr_pos["y"] - prev_pos["y"]
                h_movement = curr_pos["x"] - prev_pos["x"]
                
                if v_movement != 0:
                    vertical_movements.append(v_movement)
                if h_movement != 0:
                    horizontal_movements.append(h_movement)
            
            # Calculate scroll patterns
            total_downward = sum(m for m in vertical_movements if m > 0)
            total_upward = abs(sum(m for m in vertical_movements if m < 0))
            total_rightward = sum(m for m in horizontal_movements if m > 0)
            total_leftward = abs(sum(m for m in horizontal_movements if m < 0))
            
            # Determine primary scroll direction
            if total_downward > total_upward * 2:
                primary_direction = "downward"
            elif total_upward > total_downward * 2:
                primary_direction = "upward"
            elif total_rightward > total_leftward * 2:
                primary_direction = "rightward"
            elif total_leftward > total_rightward * 2:
                primary_direction = "leftward"
            else:
                primary_direction = "mixed"
            
            # Calculate scroll efficiency (how much actual progress vs total movement)
            if positions:
                start_pos = positions[0]
                end_pos = positions[-1]
                net_vertical = abs(end_pos["y"] - start_pos["y"])
                net_horizontal = abs(end_pos["x"] - start_pos["x"])
                total_vertical = total_downward + total_upward
                total_horizontal = total_rightward + total_leftward
                
                vertical_efficiency = (net_vertical / total_vertical * 100) if total_vertical > 0 else 100
                horizontal_efficiency = (net_horizontal / total_horizontal * 100) if total_horizontal > 0 else 100
            else:
                vertical_efficiency = 0
                horizontal_efficiency = 0
            
            scroll_patterns = {
                "primary_direction": primary_direction,
                "movement_analysis": {
                    "total_downward_pixels": total_downward,
                    "total_upward_pixels": total_upward,
                    "total_rightward_pixels": total_rightward,
                    "total_leftward_pixels": total_leftward,
                    "vertical_efficiency_percent": round(vertical_efficiency, 2),
                    "horizontal_efficiency_percent": round(horizontal_efficiency, 2)
                },
                "scroll_behavior": {
                    "primarily_vertical": (total_downward + total_upward) > (total_rightward + total_leftward),
                    "primarily_horizontal": (total_rightward + total_leftward) > (total_downward + total_upward),
                    "bidirectional": abs((total_downward + total_upward) - (total_rightward + total_leftward)) < 100,
                    "total_direction_changes": len([i for i in range(1, len(vertical_movements)) 
                                                   if (vertical_movements[i] > 0) != (vertical_movements[i-1] > 0)])
                }
            }
        else:
            scroll_patterns = {
                "primary_direction": "none",
                "movement_analysis": {},
                "scroll_behavior": {}
            }
        
        # Create summary
        summary = {
            "session_activity": {
                "total_scroll_events": len(session_history),
                "current_position": current_position,
                "session_duration_tracked": len(session_history) > 0
            },
            "scroll_patterns": scroll_patterns,
            "page_context": {
                "url": page_url,
                "title": page_title
            }
        }
        
        # Prepare metadata
        metadata = {
            "session_id": session_id,
            "analysis_timestamp": datetime.utcnow().isoformat(),
            "data_points_analyzed": len(session_history),
            "analysis_quality": "high" if len(session_history) >= 10 else "medium" if len(session_history) >= 3 else "low"
        }
        
        logger.info(
            "Scroll summary generated successfully",
            session_id=session_id,
            total_events=len(session_history),
            primary_direction=scroll_patterns["primary_direction"]
        )
        
        return {
            "session_id": session_id,
            "summary": summary,
            "metadata": metadata
        }
        
    except Exception as e:
        # Handle any unexpected errors
        error_message = str(e)
        logger.error(
            "Unexpected error during scroll summary generation",
            session_id=session_id,
            error=error_message
        )
        
        return {
            "error": "UNEXPECTED_ERROR",
            "message": f"Failed to generate scroll summary: {error_message}",
            "session_id": session_id,
            "summary": {},
            "metadata": {
                "error_details": error_message,
                "error_type": type(e).__name__
            }
        } 
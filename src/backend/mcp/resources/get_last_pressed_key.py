"""
Last Pressed Key Resource for IntelliBrowse MCP Server.

This module provides resource capabilities for retrieving information about
the last pressed keys in browser sessions, supporting keyboard interaction
analysis, debugging, and automation workflow validation.
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
import structlog

# Add parent directory to path for MCP server import
sys.path.append(str(Path(__file__).parent.parent))
from main import mcp_server

# Import browser session utilities
sys.path.append(str(Path(__file__).parent.parent / "tools"))
from browser_session import browser_sessions

logger = structlog.get_logger("intellibrowse.mcp.resources.get_last_pressed_key")


@mcp_server.resource("lastkey://{session_id}")
async def get_last_pressed_key(session_id: str) -> Dict[str, Any]:
    """
    Retrieves the last key pressed in the specified browser session.
    
    This resource provides access to the most recent key press operation
    with comprehensive metadata for debugging and validation workflows.
    
    Args:
        session_id: Browser session identifier
    
    Returns:
        Dict containing last key press information and metadata
    """
    logger.info(
        "Retrieving last pressed key",
        session_id=session_id
    )
    
    try:
        # Check if session exists
        if session_id not in browser_sessions:
            logger.error("Browser session not found", session_id=session_id)
            return {
                "error": "SESSION_NOT_FOUND",
                "message": f"Browser session {session_id} not found",
                "session_id": session_id,
                "last_key": None,
                "metadata": {}
            }
        
        session = browser_sessions[session_id]
        
        # Get key press history
        key_history = session.get("key_history", [])
        
        if not key_history:
            logger.info("No key press history found", session_id=session_id)
            return {
                "session_id": session_id,
                "last_key": None,
                "message": "No key press history found for this session",
                "total_key_presses": 0,
                "metadata": {
                    "session_info": {
                        "session_id": session_id,
                        "has_key_history": False
                    }
                }
            }
        
        # Get the last key press operation
        last_operation = key_history[-1]
        
        # Extract key information
        last_key_info = {
            "key": last_operation.get("key", ""),
            "modifiers": last_operation.get("modifiers", []),
            "selector": last_operation.get("selector"),
            "timestamp": last_operation.get("timestamp", ""),
            "success": last_operation.get("success", False),
            "focused_element": last_operation.get("focused_element", False),
            "key_press_time_ms": last_operation.get("key_press_time_ms", 0),
            "delay_after_ms": last_operation.get("delay_after_ms", 0)
        }
        
        # Build key combination string for display
        if last_key_info["modifiers"]:
            key_combination = "+".join(last_key_info["modifiers"] + [last_key_info["key"]])
        else:
            key_combination = last_key_info["key"]
        
        # Get recent key press statistics
        recent_keys = [op.get("key", "") for op in key_history[-10:]]  # Last 10 keys
        successful_presses = sum(1 for op in key_history if op.get("success", False))
        
        # Calculate timing statistics
        timing_stats = {
            "fastest_press_ms": min((op.get("key_press_time_ms", 0) for op in key_history), default=0),
            "slowest_press_ms": max((op.get("key_press_time_ms", 0) for op in key_history), default=0),
            "average_press_ms": sum(op.get("key_press_time_ms", 0) for op in key_history) / len(key_history) if key_history else 0
        }
        
        metadata = {
            "session_info": {
                "session_id": session_id,
                "total_key_presses": len(key_history),
                "successful_presses": successful_presses,
                "success_rate": successful_presses / len(key_history) if key_history else 0
            },
            "key_statistics": {
                "recent_keys": recent_keys,
                "unique_keys_pressed": len(set(op.get("key", "") for op in key_history)),
                "most_common_key": max(set(op.get("key", "") for op in key_history), 
                                     key=lambda x: sum(1 for op in key_history if op.get("key") == x), 
                                     default="") if key_history else ""
            },
            "timing_statistics": timing_stats,
            "last_operation_details": last_operation
        }
        
        logger.info(
            "Last pressed key retrieved successfully",
            session_id=session_id,
            last_key=last_key_info["key"],
            key_combination=key_combination,
            total_presses=len(key_history)
        )
        
        return {
            "session_id": session_id,
            "last_key": last_key_info["key"],
            "key_combination": key_combination,
            "last_key_info": last_key_info,
            "metadata": metadata
        }
        
    except Exception as e:
        # Handle any unexpected errors
        error_message = str(e)
        logger.error(
            "Unexpected error during last key retrieval",
            session_id=session_id,
            error=error_message
        )
        
        return {
            "error": "UNEXPECTED_ERROR",
            "message": f"Unexpected error during last key retrieval: {error_message}",
            "session_id": session_id,
            "last_key": None,
            "metadata": {"error_details": error_message}
        }


@mcp_server.resource("keyhistory://{session_id}/{count}")
async def get_key_press_history(session_id: str, count: str = "10") -> Dict[str, Any]:
    """
    Retrieves the key press history for the specified browser session.
    
    This resource provides access to recent key press operations with
    comprehensive metadata for analysis and debugging workflows.
    
    Args:
        session_id: Browser session identifier
        count: Number of recent key presses to retrieve (default: 10)
    
    Returns:
        Dict containing key press history and analysis metadata
    """
    logger.info(
        "Retrieving key press history",
        session_id=session_id,
        count=count
    )
    
    try:
        # Parse count parameter
        try:
            count_int = int(count)
            if count_int < 1:
                count_int = 10
            elif count_int > 100:  # Limit to prevent excessive data
                count_int = 100
        except ValueError:
            count_int = 10
        
        # Check if session exists
        if session_id not in browser_sessions:
            logger.error("Browser session not found", session_id=session_id)
            return {
                "error": "SESSION_NOT_FOUND",
                "message": f"Browser session {session_id} not found",
                "session_id": session_id,
                "key_history": [],
                "metadata": {}
            }
        
        session = browser_sessions[session_id]
        
        # Get key press history
        key_history = session.get("key_history", [])
        
        if not key_history:
            logger.info("No key press history found", session_id=session_id)
            return {
                "session_id": session_id,
                "key_history": [],
                "total_key_presses": 0,
                "requested_count": count_int,
                "returned_count": 0,
                "metadata": {
                    "session_info": {
                        "session_id": session_id,
                        "has_key_history": False
                    }
                }
            }
        
        # Get the requested number of recent key presses
        recent_history = key_history[-count_int:] if len(key_history) > count_int else key_history
        
        # Analyze the key press patterns
        key_analysis = {}
        
        if recent_history:
            # Count key frequency
            key_frequency = {}
            modifier_frequency = {}
            selector_frequency = {}
            
            for operation in recent_history:
                key = operation.get("key", "")
                modifiers = operation.get("modifiers", [])
                selector = operation.get("selector", "")
                
                # Count keys
                key_frequency[key] = key_frequency.get(key, 0) + 1
                
                # Count modifiers
                for modifier in modifiers:
                    modifier_frequency[modifier] = modifier_frequency.get(modifier, 0) + 1
                
                # Count selectors (if not empty)
                if selector:
                    selector_frequency[selector] = selector_frequency.get(selector, 0) + 1
            
            # Calculate timing statistics
            press_times = [op.get("key_press_time_ms", 0) for op in recent_history]
            timing_analysis = {
                "fastest_press_ms": min(press_times) if press_times else 0,
                "slowest_press_ms": max(press_times) if press_times else 0,
                "average_press_ms": sum(press_times) / len(press_times) if press_times else 0,
                "total_time_ms": sum(press_times)
            }
            
            # Success rate analysis
            successful_operations = sum(1 for op in recent_history if op.get("success", False))
            success_rate = successful_operations / len(recent_history) if recent_history else 0
            
            key_analysis = {
                "key_frequency": dict(sorted(key_frequency.items(), key=lambda x: x[1], reverse=True)),
                "modifier_frequency": dict(sorted(modifier_frequency.items(), key=lambda x: x[1], reverse=True)),
                "selector_frequency": dict(sorted(selector_frequency.items(), key=lambda x: x[1], reverse=True)),
                "timing_analysis": timing_analysis,
                "success_analysis": {
                    "total_operations": len(recent_history),
                    "successful_operations": successful_operations,
                    "failed_operations": len(recent_history) - successful_operations,
                    "success_rate": success_rate
                }
            }
        
        # Prepare comprehensive metadata
        metadata = {
            "session_info": {
                "session_id": session_id,
                "total_key_presses": len(key_history),
                "requested_count": count_int,
                "returned_count": len(recent_history)
            },
            "key_analysis": key_analysis,
            "history_range": {
                "oldest_timestamp": recent_history[0].get("timestamp", "") if recent_history else "",
                "newest_timestamp": recent_history[-1].get("timestamp", "") if recent_history else ""
            }
        }
        
        logger.info(
            "Key press history retrieved successfully",
            session_id=session_id,
            total_history=len(key_history),
            returned_count=len(recent_history),
            requested_count=count_int
        )
        
        return {
            "session_id": session_id,
            "key_history": recent_history,
            "total_key_presses": len(key_history),
            "requested_count": count_int,
            "returned_count": len(recent_history),
            "metadata": metadata
        }
        
    except Exception as e:
        # Handle any unexpected errors
        error_message = str(e)
        logger.error(
            "Unexpected error during key history retrieval",
            session_id=session_id,
            error=error_message
        )
        
        return {
            "error": "UNEXPECTED_ERROR",
            "message": f"Unexpected error during key history retrieval: {error_message}",
            "session_id": session_id,
            "key_history": [],
            "metadata": {"error_details": error_message}
        }


@mcp_server.resource("keystats://{session_id}")
async def get_key_press_statistics(session_id: str) -> Dict[str, Any]:
    """
    Retrieves comprehensive key press statistics for the specified browser session.
    
    This resource provides detailed analysis of keyboard interaction patterns,
    performance metrics, and usage statistics for optimization and debugging.
    
    Args:
        session_id: Browser session identifier
    
    Returns:
        Dict containing comprehensive key press statistics and analysis
    """
    logger.info(
        "Retrieving key press statistics",
        session_id=session_id
    )
    
    try:
        # Check if session exists
        if session_id not in browser_sessions:
            logger.error("Browser session not found", session_id=session_id)
            return {
                "error": "SESSION_NOT_FOUND",
                "message": f"Browser session {session_id} not found",
                "session_id": session_id,
                "statistics": {},
                "metadata": {}
            }
        
        session = browser_sessions[session_id]
        
        # Get key press history
        key_history = session.get("key_history", [])
        
        if not key_history:
            return {
                "session_id": session_id,
                "statistics": {
                    "total_operations": 0,
                    "no_data": True
                },
                "metadata": {
                    "session_info": {
                        "session_id": session_id,
                        "has_key_history": False
                    }
                }
            }
        
        # Comprehensive statistical analysis
        statistics = {
            "overall_metrics": {
                "total_key_presses": len(key_history),
                "successful_presses": sum(1 for op in key_history if op.get("success", False)),
                "failed_presses": sum(1 for op in key_history if not op.get("success", False)),
                "success_rate": sum(1 for op in key_history if op.get("success", False)) / len(key_history),
                "unique_keys_used": len(set(op.get("key", "") for op in key_history))
            },
            "timing_analysis": {},
            "key_usage_patterns": {},
            "element_interaction_patterns": {},
            "modifier_usage_patterns": {},
            "error_analysis": {}
        }
        
        # Timing analysis
        press_times = [op.get("key_press_time_ms", 0) for op in key_history]
        if press_times:
            statistics["timing_analysis"] = {
                "fastest_press_ms": min(press_times),
                "slowest_press_ms": max(press_times),
                "average_press_ms": sum(press_times) / len(press_times),
                "median_press_ms": sorted(press_times)[len(press_times) // 2],
                "total_time_ms": sum(press_times)
            }
        
        # Key usage patterns
        key_counts = {}
        for operation in key_history:
            key = operation.get("key", "")
            key_counts[key] = key_counts.get(key, 0) + 1
        
        statistics["key_usage_patterns"] = {
            "most_used_keys": dict(sorted(key_counts.items(), key=lambda x: x[1], reverse=True)[:10]),
            "key_distribution": key_counts,
            "special_key_usage": sum(1 for key in key_counts.keys() if len(key) > 1),
            "character_key_usage": sum(1 for key in key_counts.keys() if len(key) == 1)
        }
        
        # Element interaction patterns
        selector_usage = {}
        focused_operations = sum(1 for op in key_history if op.get("focused_element", False))
        
        for operation in key_history:
            selector = operation.get("selector", "")
            if selector:
                selector_usage[selector] = selector_usage.get(selector, 0) + 1
        
        statistics["element_interaction_patterns"] = {
            "operations_with_focus": focused_operations,
            "operations_without_focus": len(key_history) - focused_operations,
            "focus_usage_rate": focused_operations / len(key_history),
            "unique_selectors_used": len(selector_usage),
            "most_used_selectors": dict(sorted(selector_usage.items(), key=lambda x: x[1], reverse=True)[:5])
        }
        
        # Modifier usage patterns
        modifier_counts = {}
        operations_with_modifiers = 0
        
        for operation in key_history:
            modifiers = operation.get("modifiers", [])
            if modifiers:
                operations_with_modifiers += 1
                for modifier in modifiers:
                    modifier_counts[modifier] = modifier_counts.get(modifier, 0) + 1
        
        statistics["modifier_usage_patterns"] = {
            "operations_with_modifiers": operations_with_modifiers,
            "operations_without_modifiers": len(key_history) - operations_with_modifiers,
            "modifier_usage_rate": operations_with_modifiers / len(key_history),
            "modifier_frequency": dict(sorted(modifier_counts.items(), key=lambda x: x[1], reverse=True))
        }
        
        # Error analysis
        failed_operations = [op for op in key_history if not op.get("success", False)]
        error_patterns = {}
        
        # This would need to be enhanced based on actual error tracking in the operations
        statistics["error_analysis"] = {
            "total_failures": len(failed_operations),
            "failure_rate": len(failed_operations) / len(key_history),
            "error_patterns": error_patterns  # Could be enhanced with actual error categorization
        }
        
        metadata = {
            "session_info": {
                "session_id": session_id,
                "analysis_timestamp": "",  # Could add current timestamp
                "data_completeness": "full" if len(key_history) > 0 else "empty"
            },
            "analysis_scope": {
                "total_operations_analyzed": len(key_history),
                "analysis_type": "comprehensive"
            }
        }
        
        logger.info(
            "Key press statistics retrieved successfully",
            session_id=session_id,
            total_operations=len(key_history),
            success_rate=statistics["overall_metrics"]["success_rate"]
        )
        
        return {
            "session_id": session_id,
            "statistics": statistics,
            "metadata": metadata
        }
        
    except Exception as e:
        # Handle any unexpected errors
        error_message = str(e)
        logger.error(
            "Unexpected error during statistics retrieval",
            session_id=session_id,
            error=error_message
        )
        
        return {
            "error": "UNEXPECTED_ERROR",
            "message": f"Unexpected error during statistics retrieval: {error_message}",
            "session_id": session_id,
            "statistics": {},
            "metadata": {"error_details": error_message}
        } 
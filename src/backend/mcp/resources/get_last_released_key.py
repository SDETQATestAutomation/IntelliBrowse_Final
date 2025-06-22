"""
Last Released Key Resource for IntelliBrowse MCP Server.

This module provides resource capabilities for retrieving information about
the last released keys in browser sessions, supporting keyboard interaction
analysis, debugging, and automation workflow validation.
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
import structlog

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

logger = structlog.get_logger("intellibrowse.mcp.resources.get_last_released_key")


@mcp_server.resource("lastreleasedkey://{session_id}")
async def get_last_released_key(session_id: str) -> Dict[str, Any]:
    """
    Retrieves the last key released in the specified browser session.
    
    This resource provides access to the most recent key release operation
    with comprehensive metadata for debugging and validation workflows.
    
    Args:
        session_id: Browser session identifier
    
    Returns:
        Dict containing last key release information and metadata
    """
    logger.info(
        "Retrieving last released key",
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
                "last_released_key": None,
                "metadata": {}
            }
        
        session = browser_sessions[session_id]
        
        # Get key release history
        key_release_history = session.get("key_release_history", [])
        
        if not key_release_history:
            logger.info("No key release history found", session_id=session_id)
            return {
                "session_id": session_id,
                "last_released_key": None,
                "message": "No key release history found for this session",
                "total_key_releases": 0,
                "metadata": {
                    "session_info": {
                        "session_id": session_id,
                        "has_key_release_history": False
                    }
                }
            }
        
        # Get the last key release operation
        last_operation = key_release_history[-1]
        
        # Extract key information
        last_key_info = {
            "key": last_operation.get("key", ""),
            "selector": last_operation.get("selector"),
            "timestamp": last_operation.get("timestamp", ""),
            "success": last_operation.get("success", False),
            "focused_element": last_operation.get("focused_element", False),
            "key_release_time_ms": last_operation.get("key_release_time_ms", 0),
            "delay_after_ms": last_operation.get("delay_after_ms", 0),
            "verify_release": last_operation.get("verify_release", False)
        }
        
        # Get recent key release statistics
        recent_keys = [op.get("key", "") for op in key_release_history[-10:]]  # Last 10 releases
        successful_releases = sum(1 for op in key_release_history if op.get("success", False))
        
        # Calculate timing statistics
        timing_stats = {
            "fastest_release_ms": min((op.get("key_release_time_ms", 0) for op in key_release_history), default=0),
            "slowest_release_ms": max((op.get("key_release_time_ms", 0) for op in key_release_history), default=0),
            "average_release_ms": sum(op.get("key_release_time_ms", 0) for op in key_release_history) / len(key_release_history) if key_release_history else 0
        }
        
        # Determine key type and characteristics
        key_type = "unknown"
        is_modifier = False
        if last_key_info["key"]:
            if last_key_info["key"] in ["Control", "Shift", "Alt", "Meta", "ControlOrMeta"]:
                key_type = "modifier"
                is_modifier = True
            elif len(last_key_info["key"]) == 1:
                key_type = "character"
            elif last_key_info["key"].startswith("F") and last_key_info["key"][1:].isdigit():
                key_type = "function"
            elif last_key_info["key"] in ["Enter", "Tab", "Escape", "Space", "Backspace", "Delete"]:
                key_type = "special"
            elif last_key_info["key"].startswith("Arrow"):
                key_type = "navigation"
            else:
                key_type = "other"
        
        metadata = {
            "session_info": {
                "session_id": session_id,
                "total_key_releases": len(key_release_history),
                "successful_releases": successful_releases,
                "success_rate": successful_releases / len(key_release_history) if key_release_history else 0
            },
            "key_statistics": {
                "recent_released_keys": recent_keys,
                "unique_keys_released": len(set(op.get("key", "") for op in key_release_history)),
                "most_common_released_key": max(set(op.get("key", "") for op in key_release_history), 
                                               key=lambda x: sum(1 for op in key_release_history if op.get("key") == x), 
                                               default="") if key_release_history else ""
            },
            "last_key_details": {
                "key_type": key_type,
                "is_modifier": is_modifier,
                "has_selector": bool(last_key_info["selector"]),
                "had_focus": last_key_info["focused_element"]
            },
            "timing_statistics": timing_stats,
            "last_operation_details": last_operation
        }
        
        logger.info(
            "Last released key retrieved successfully",
            session_id=session_id,
            last_key=last_key_info["key"],
            key_type=key_type,
            total_releases=len(key_release_history)
        )
        
        return {
            "session_id": session_id,
            "last_released_key": last_key_info["key"],
            "last_key_info": last_key_info,
            "metadata": metadata
        }
        
    except Exception as e:
        # Handle any unexpected errors
        error_message = str(e)
        logger.error(
            "Unexpected error during last released key retrieval",
            session_id=session_id,
            error=error_message
        )
        
        return {
            "error": "UNEXPECTED_ERROR",
            "message": f"Unexpected error during last released key retrieval: {error_message}",
            "session_id": session_id,
            "last_released_key": None,
            "metadata": {"error_details": error_message}
        }


@mcp_server.resource("releasedkeyhistory://{session_id}/{count}")
async def get_key_release_history(session_id: str, count: str = "10") -> Dict[str, Any]:
    """
    Retrieves the key release history for the specified browser session.
    
    This resource provides access to recent key release operations with
    comprehensive metadata for analysis and debugging workflows.
    
    Args:
        session_id: Browser session identifier
        count: Number of recent key releases to retrieve (default: 10)
    
    Returns:
        Dict containing key release history and analysis metadata
    """
    logger.info(
        "Retrieving key release history",
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
                "key_release_history": [],
                "metadata": {}
            }
        
        session = browser_sessions[session_id]
        
        # Get key release history
        key_release_history = session.get("key_release_history", [])
        
        if not key_release_history:
            logger.info("No key release history found", session_id=session_id)
            return {
                "session_id": session_id,
                "key_release_history": [],
                "total_key_releases": 0,
                "requested_count": count_int,
                "returned_count": 0,
                "metadata": {
                    "session_info": {
                        "session_id": session_id,
                        "has_key_release_history": False
                    }
                }
            }
        
        # Get the requested number of recent key releases
        recent_history = key_release_history[-count_int:] if len(key_release_history) > count_int else key_release_history
        
        # Analyze the key release patterns
        release_analysis = {}
        
        if recent_history:
            # Count key frequency
            key_frequency = {}
            selector_frequency = {}
            key_type_frequency = {}
            
            for operation in recent_history:
                key = operation.get("key", "")
                selector = operation.get("selector", "")
                
                # Count keys
                key_frequency[key] = key_frequency.get(key, 0) + 1
                
                # Count selectors (if not empty)
                if selector:
                    selector_frequency[selector] = selector_frequency.get(selector, 0) + 1
                
                # Classify and count key types
                if key in ["Control", "Shift", "Alt", "Meta", "ControlOrMeta"]:
                    key_type = "modifier"
                elif len(key) == 1:
                    key_type = "character"
                elif key.startswith("F") and key[1:].isdigit():
                    key_type = "function"
                elif key in ["Enter", "Tab", "Escape", "Space", "Backspace", "Delete"]:
                    key_type = "special"
                elif key.startswith("Arrow"):
                    key_type = "navigation"
                else:
                    key_type = "other"
                
                key_type_frequency[key_type] = key_type_frequency.get(key_type, 0) + 1
            
            # Calculate timing statistics
            release_times = [op.get("key_release_time_ms", 0) for op in recent_history]
            timing_analysis = {
                "fastest_release_ms": min(release_times) if release_times else 0,
                "slowest_release_ms": max(release_times) if release_times else 0,
                "average_release_ms": sum(release_times) / len(release_times) if release_times else 0,
                "total_time_ms": sum(release_times)
            }
            
            # Success rate analysis
            successful_operations = sum(1 for op in recent_history if op.get("success", False))
            success_rate = successful_operations / len(recent_history) if recent_history else 0
            
            # Focus analysis
            focused_operations = sum(1 for op in recent_history if op.get("focused_element", False))
            focus_rate = focused_operations / len(recent_history) if recent_history else 0
            
            release_analysis = {
                "key_frequency": dict(sorted(key_frequency.items(), key=lambda x: x[1], reverse=True)),
                "key_type_frequency": dict(sorted(key_type_frequency.items(), key=lambda x: x[1], reverse=True)),
                "selector_frequency": dict(sorted(selector_frequency.items(), key=lambda x: x[1], reverse=True)),
                "timing_analysis": timing_analysis,
                "success_analysis": {
                    "total_operations": len(recent_history),
                    "successful_operations": successful_operations,
                    "failed_operations": len(recent_history) - successful_operations,
                    "success_rate": success_rate
                },
                "focus_analysis": {
                    "focused_operations": focused_operations,
                    "unfocused_operations": len(recent_history) - focused_operations,
                    "focus_rate": focus_rate
                }
            }
        
        # Prepare comprehensive metadata
        metadata = {
            "session_info": {
                "session_id": session_id,
                "total_key_releases": len(key_release_history),
                "requested_count": count_int,
                "returned_count": len(recent_history)
            },
            "release_analysis": release_analysis,
            "history_range": {
                "oldest_timestamp": recent_history[0].get("timestamp", "") if recent_history else "",
                "newest_timestamp": recent_history[-1].get("timestamp", "") if recent_history else ""
            }
        }
        
        logger.info(
            "Key release history retrieved successfully",
            session_id=session_id,
            total_history=len(key_release_history),
            returned_count=len(recent_history),
            requested_count=count_int
        )
        
        return {
            "session_id": session_id,
            "key_release_history": recent_history,
            "total_key_releases": len(key_release_history),
            "requested_count": count_int,
            "returned_count": len(recent_history),
            "metadata": metadata
        }
        
    except Exception as e:
        # Handle any unexpected errors
        error_message = str(e)
        logger.error(
            "Unexpected error during key release history retrieval",
            session_id=session_id,
            error=error_message
        )
        
        return {
            "error": "UNEXPECTED_ERROR",
            "message": f"Unexpected error during key release history retrieval: {error_message}",
            "session_id": session_id,
            "key_release_history": [],
            "metadata": {"error_details": error_message}
        }


@mcp_server.resource("releasedkeystats://{session_id}")
async def get_key_release_statistics(session_id: str) -> Dict[str, Any]:
    """
    Retrieves comprehensive key release statistics for the specified browser session.
    
    This resource provides detailed analysis of keyboard release interaction patterns,
    performance metrics, and usage statistics for optimization and debugging.
    
    Args:
        session_id: Browser session identifier
    
    Returns:
        Dict containing comprehensive key release statistics and analysis
    """
    logger.info(
        "Retrieving key release statistics",
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
        
        # Get key release history
        key_release_history = session.get("key_release_history", [])
        
        if not key_release_history:
            return {
                "session_id": session_id,
                "statistics": {
                    "total_operations": 0,
                    "no_data": True
                },
                "metadata": {
                    "session_info": {
                        "session_id": session_id,
                        "has_key_release_history": False
                    }
                }
            }
        
        # Comprehensive statistical analysis
        statistics = {
            "overall_metrics": {
                "total_key_releases": len(key_release_history),
                "successful_releases": sum(1 for op in key_release_history if op.get("success", False)),
                "failed_releases": sum(1 for op in key_release_history if not op.get("success", False)),
                "success_rate": sum(1 for op in key_release_history if op.get("success", False)) / len(key_release_history),
                "unique_keys_released": len(set(op.get("key", "") for op in key_release_history))
            },
            "timing_analysis": {},
            "key_usage_patterns": {},
            "element_interaction_patterns": {},
            "key_type_patterns": {},
            "error_analysis": {}
        }
        
        # Timing analysis
        release_times = [op.get("key_release_time_ms", 0) for op in key_release_history]
        if release_times:
            statistics["timing_analysis"] = {
                "fastest_release_ms": min(release_times),
                "slowest_release_ms": max(release_times),
                "average_release_ms": sum(release_times) / len(release_times),
                "median_release_ms": sorted(release_times)[len(release_times) // 2],
                "total_time_ms": sum(release_times)
            }
        
        # Key usage patterns
        key_counts = {}
        for operation in key_release_history:
            key = operation.get("key", "")
            key_counts[key] = key_counts.get(key, 0) + 1
        
        statistics["key_usage_patterns"] = {
            "most_released_keys": dict(sorted(key_counts.items(), key=lambda x: x[1], reverse=True)[:10]),
            "key_distribution": key_counts,
            "modifier_key_releases": sum(1 for key in key_counts.keys() if key in ["Control", "Shift", "Alt", "Meta", "ControlOrMeta"]),
            "character_key_releases": sum(1 for key in key_counts.keys() if len(key) == 1),
            "special_key_releases": sum(1 for key in key_counts.keys() if key in ["Enter", "Tab", "Escape", "Space", "Backspace", "Delete"]),
            "function_key_releases": sum(1 for key in key_counts.keys() if key.startswith("F") and key[1:].isdigit())
        }
        
        # Element interaction patterns
        selector_usage = {}
        focused_operations = sum(1 for op in key_release_history if op.get("focused_element", False))
        
        for operation in key_release_history:
            selector = operation.get("selector", "")
            if selector:
                selector_usage[selector] = selector_usage.get(selector, 0) + 1
        
        statistics["element_interaction_patterns"] = {
            "operations_with_focus": focused_operations,
            "operations_without_focus": len(key_release_history) - focused_operations,
            "focus_usage_rate": focused_operations / len(key_release_history),
            "unique_selectors_used": len(selector_usage),
            "most_used_selectors": dict(sorted(selector_usage.items(), key=lambda x: x[1], reverse=True)[:5])
        }
        
        # Key type patterns
        key_type_counts = {"modifier": 0, "character": 0, "function": 0, "special": 0, "navigation": 0, "other": 0}
        
        for operation in key_release_history:
            key = operation.get("key", "")
            if key in ["Control", "Shift", "Alt", "Meta", "ControlOrMeta"]:
                key_type_counts["modifier"] += 1
            elif len(key) == 1:
                key_type_counts["character"] += 1
            elif key.startswith("F") and key[1:].isdigit():
                key_type_counts["function"] += 1
            elif key in ["Enter", "Tab", "Escape", "Space", "Backspace", "Delete"]:
                key_type_counts["special"] += 1
            elif key.startswith("Arrow"):
                key_type_counts["navigation"] += 1
            else:
                key_type_counts["other"] += 1
        
        statistics["key_type_patterns"] = {
            "key_type_distribution": key_type_counts,
            "most_common_type": max(key_type_counts.items(), key=lambda x: x[1])[0] if any(key_type_counts.values()) else "none"
        }
        
        # Error analysis
        failed_operations = [op for op in key_release_history if not op.get("success", False)]
        error_patterns = {}
        
        # This would need to be enhanced based on actual error tracking in the operations
        statistics["error_analysis"] = {
            "total_failures": len(failed_operations),
            "failure_rate": len(failed_operations) / len(key_release_history),
            "error_patterns": error_patterns  # Could be enhanced with actual error categorization
        }
        
        metadata = {
            "session_info": {
                "session_id": session_id,
                "analysis_timestamp": "",  # Could add current timestamp
                "data_completeness": "full" if len(key_release_history) > 0 else "empty"
            },
            "analysis_scope": {
                "total_operations_analyzed": len(key_release_history),
                "analysis_type": "comprehensive"
            }
        }
        
        logger.info(
            "Key release statistics retrieved successfully",
            session_id=session_id,
            total_operations=len(key_release_history),
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
            "Unexpected error during release statistics retrieval",
            session_id=session_id,
            error=error_message
        )
        
        return {
            "error": "UNEXPECTED_ERROR",
            "message": f"Unexpected error during release statistics retrieval: {error_message}",
            "session_id": session_id,
            "statistics": {},
            "metadata": {"error_details": error_message}
        } 
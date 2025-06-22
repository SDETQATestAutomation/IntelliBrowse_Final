"""
Get Console Logs Tool for IntelliBrowse MCP Server.

This module implements browser console log retrieval with advanced filtering,
pagination, and monitoring capabilities. Supports multiple log types, 
time-based filtering, pattern matching, and optional log clearing.

Features:
- Multi-type filtering (log, error, warn, info, debug, etc.)
- Time-based filtering with ISO timestamp support
- Regex pattern matching for log content
- Pagination with configurable limits
- Optional log clearing after retrieval
- Stack trace inclusion for error logs
- Comprehensive error handling and audit logging

Author: IntelliBrowse Team
Created: 2025-01-18
Part of the IntelliBrowse MCP Server implementation.
"""

import asyncio
import re
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import structlog

# Import the shared server instance
try:
    from server_instance import mcp_server
except ImportError:
    # Fallback for when running directly from mcp directory
    from server_instance import mcp_server

try:
    from schemas.tools.get_console_logs_schemas import (
        GetConsoleLogsRequest,
        GetConsoleLogsResponse,
        GetConsoleLogsError,
        ConsoleLogEntry
    )
except ImportError:
    # Fallback for when running directly from mcp directory
    from schemas.tools.get_console_logs_schemas import (
        GetConsoleLogsRequest,
        GetConsoleLogsResponse,
        GetConsoleLogsError,
        ConsoleLogEntry
    )
try:
    from tools.browser_session import browser_sessions
except ImportError:
    # Fallback for when running directly from mcp directory
    from tools.browser_session import browser_sessions

# Initialize structured logger
logger = structlog.get_logger(__name__)

# Use the shared mcp_server instance instead of creating a new one


@mcp_server.tool()
async def get_console_logs(
    session_id: str,
    log_types: Optional[List[str]] = None,
    since: Optional[str] = None,
    limit: Optional[int] = 100,
    search_pattern: Optional[str] = None,
    clear_after_read: Optional[bool] = False,
    include_stack_traces: Optional[bool] = True
) -> Dict[str, Any]:
    """
    Retrieve browser console logs with advanced filtering and pagination.
    
    This tool provides comprehensive console log retrieval with support for:
    - Multi-type filtering by log level
    - Time-based filtering with ISO timestamps
    - Regex pattern matching for log content
    - Pagination with configurable limits
    - Optional log clearing after retrieval
    - Stack trace inclusion for debugging
    
    Args:
        session_id: Active browser session ID
        log_types: Filter by log types (log, error, warn, info, debug, etc.)
        since: ISO timestamp for logs after this time
        limit: Maximum number of logs to return (1-10000)
        search_pattern: Regex pattern for log content filtering
        clear_after_read: Clear console logs after retrieval
        include_stack_traces: Include stack traces for error logs
        
    Returns:
        Dict containing retrieved logs with metadata and filtering information
        
    Raises:
        Various exceptions for session, filtering, and retrieval errors
    """
    
    # Validate request using Pydantic schema
    try:
        request = GetConsoleLogsRequest(
            session_id=session_id,
            log_types=log_types,
            since=since,
            limit=limit,
            search_pattern=search_pattern,
            clear_after_read=clear_after_read,
            include_stack_traces=include_stack_traces
        )
    except Exception as e:
        logger.error(
            "Invalid get_console_logs request",
            error=str(e),
            session_id=session_id
        )
        return GetConsoleLogsError(
            error=f"Invalid request parameters: {str(e)}",
            error_type="validation_error",
            session_id=session_id,
            timestamp=datetime.now(timezone.utc).isoformat()
        ).dict()
    
    # Log the console logs retrieval attempt
    logger.info(
        "Starting console logs retrieval",
        session_id=session_id,
        log_types=log_types,
        since=since,
        limit=limit,
        search_pattern=search_pattern,
        clear_after_read=clear_after_read
    )
    
    try:
        # Check if session exists
        if session_id not in browser_sessions:
            logger.error(
                "Session not found for console logs retrieval",
                session_id=session_id
            )
            return GetConsoleLogsError(
                error=f"Browser session '{session_id}' not found",
                error_type="session_not_found",
                session_id=session_id,
                timestamp=datetime.now(timezone.utc).isoformat()
            ).dict()
        
        session = browser_sessions[session_id]
        page = session.get("page")
        
        if not page:
            logger.error(
                "No active page in session for console logs",
                session_id=session_id
            )
            return GetConsoleLogsError(
                error=f"No active page in session '{session_id}'",
                error_type="no_active_page",
                session_id=session_id,
                timestamp=datetime.now(timezone.utc).isoformat()
            ).dict()
        
        # Get current page URL for context
        try:
            current_url = page.url
        except Exception:
            current_url = "unknown"
        
        # Initialize console log collection if not exists
        if 'console_logs' not in session:
            session['console_logs'] = []
        
        # Get all console logs from session
        all_logs = session.get('console_logs', [])
        
        # Apply time-based filtering if specified
        filtered_logs = all_logs
        if request.since:
            try:
                since_dt = datetime.fromisoformat(request.since.replace('Z', '+00:00'))
                filtered_logs = [
                    log for log in filtered_logs
                    if datetime.fromisoformat(log.get('timestamp', '').replace('Z', '+00:00')) >= since_dt
                ]
                logger.debug(
                    "Applied time-based filtering",
                    session_id=session_id,
                    since=request.since,
                    logs_after_time_filter=len(filtered_logs)
                )
            except Exception as e:
                logger.warning(
                    "Failed to apply time-based filtering",
                    session_id=session_id,
                    since=request.since,
                    error=str(e)
                )
        
        # Apply log type filtering if specified
        if request.log_types:
            filtered_logs = [
                log for log in filtered_logs
                if log.get('type', '').lower() in [t.lower() for t in request.log_types]
            ]
            logger.debug(
                "Applied log type filtering",
                session_id=session_id,
                log_types=request.log_types,
                logs_after_type_filter=len(filtered_logs)
            )
        
        # Apply pattern-based filtering if specified
        if request.search_pattern:
            try:
                pattern = re.compile(request.search_pattern, re.IGNORECASE)
                filtered_logs = [
                    log for log in filtered_logs
                    if pattern.search(log.get('message', ''))
                ]
                logger.debug(
                    "Applied pattern-based filtering",
                    session_id=session_id,
                    search_pattern=request.search_pattern,
                    logs_after_pattern_filter=len(filtered_logs)
                )
            except Exception as e:
                logger.warning(
                    "Failed to apply pattern-based filtering",
                    session_id=session_id,
                    search_pattern=request.search_pattern,
                    error=str(e)
                )
        
        # Apply limit for pagination
        total_filtered = len(filtered_logs)
        limited_logs = filtered_logs[:request.limit] if request.limit else filtered_logs
        
        # Convert logs to ConsoleLogEntry format
        formatted_logs = []
        for log in limited_logs:
            try:
                log_entry = ConsoleLogEntry(
                    type=log.get('type', 'log'),
                    timestamp=log.get('timestamp', datetime.now(timezone.utc).isoformat()),
                    message=log.get('message', ''),
                    args=log.get('args'),
                    url=log.get('url', current_url),
                    line_number=log.get('line_number'),
                    column_number=log.get('column_number'),
                    stack_trace=log.get('stack_trace') if request.include_stack_traces else None,
                    source=log.get('source', 'javascript')
                )
                formatted_logs.append(log_entry)
            except Exception as e:
                logger.warning(
                    "Failed to format log entry",
                    session_id=session_id,
                    log=log,
                    error=str(e)
                )
                continue
        
        # Clear logs after reading if requested
        logs_cleared = False
        if request.clear_after_read:
            try:
                session['console_logs'] = []
                logs_cleared = True
                logger.info(
                    "Console logs cleared after reading",
                    session_id=session_id,
                    cleared_count=len(all_logs)
                )
            except Exception as e:
                logger.warning(
                    "Failed to clear console logs",
                    session_id=session_id,
                    error=str(e)
                )
        
        # Prepare filters applied summary
        filters_applied = {
            "log_types": request.log_types,
            "since": request.since,
            "search_pattern": request.search_pattern,
            "limit": request.limit,
            "include_stack_traces": request.include_stack_traces
        }
        
        # Prepare session info
        session_info = {
            "session_id": session_id,
            "current_url": current_url,
            "browser_context": session.get("context_id", "unknown"),
            "page_title": "unknown"
        }
        
        # Try to get page title
        try:
            session_info["page_title"] = await page.title()
        except Exception:
            pass
        
        # Create successful response
        response = GetConsoleLogsResponse(
            success=True,
            logs=formatted_logs,
            total_count=len(all_logs),
            filtered_count=total_filtered,
            retrieved_count=len(formatted_logs),
            filters_applied=filters_applied,
            cleared_after_read=logs_cleared,
            session_info=session_info,
            retrieval_time=datetime.now(timezone.utc).isoformat(),
            message=f"Successfully retrieved {len(formatted_logs)} console logs",
            metadata={
                "filtering_stages": {
                    "initial_logs": len(all_logs),
                    "after_time_filter": len(filtered_logs) if request.since else len(all_logs),
                    "after_type_filter": len(filtered_logs) if request.log_types else len(filtered_logs),
                    "after_pattern_filter": total_filtered,
                    "final_retrieved": len(formatted_logs)
                },
                "performance": {
                    "retrieval_time_ms": 0  # Would be calculated in real implementation
                }
            }
        )
        
        logger.info(
            "Console logs retrieved successfully",
            session_id=session_id,
            total_logs=len(all_logs),
            filtered_logs=total_filtered,
            retrieved_logs=len(formatted_logs),
            logs_cleared=logs_cleared
        )
        
        return response.dict()
        
    except Exception as e:
        logger.error(
            "Failed to retrieve console logs",
            session_id=session_id,
            error=str(e),
            error_type=type(e).__name__
        )
        
        return GetConsoleLogsError(
            error=f"Failed to retrieve console logs: {str(e)}",
            error_type="retrieval_error",
            session_id=session_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            details={
                "exception_type": type(e).__name__,
                "error_location": "get_console_logs_tool"
            }
        ).dict()


# Helper function to initialize console log listener for a page
async def setup_console_log_listener(page, session_id: str):
    """
    Set up console log listener for a page to capture logs in real-time.
    
    Args:
        page: Playwright page object
        session_id: Browser session ID
    """
    
    async def handle_console_log(msg):
        """Handle console log messages and store them in session."""
        try:
            session = browser_sessions.get(session_id)
            if not session:
                return
            
            if 'console_logs' not in session:
                session['console_logs'] = []
            
            # Extract log information
            log_entry = {
                'type': msg.type,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'message': msg.text,
                'args': [str(arg) for arg in msg.args] if msg.args else None,
                'url': page.url,
                'line_number': None,
                'column_number': None,
                'stack_trace': None,
                'source': 'javascript'
            }
            
            # Add stack trace for error logs
            if msg.type == 'error' and msg.location:
                log_entry['line_number'] = msg.location.get('lineNumber')
                log_entry['column_number'] = msg.location.get('columnNumber')
                log_entry['url'] = msg.location.get('url', page.url)
                
                # Try to get stack trace
                try:
                    if len(msg.args) > 0:
                        error_arg = msg.args[0]
                        if hasattr(error_arg, 'jsonValue'):
                            error_value = await error_arg.jsonValue()
                            if isinstance(error_value, dict) and 'stack' in error_value:
                                log_entry['stack_trace'] = error_value['stack']
                except Exception:
                    pass
            
            # Store log entry
            session['console_logs'].append(log_entry)
            
            # Keep only last 10000 logs to prevent memory issues
            if len(session['console_logs']) > 10000:
                session['console_logs'] = session['console_logs'][-10000:]
            
            logger.debug(
                "Console log captured",
                session_id=session_id,
                log_type=msg.type,
                message=msg.text[:100] + "..." if len(msg.text) > 100 else msg.text
            )
            
        except Exception as e:
            logger.warning(
                "Failed to capture console log",
                session_id=session_id,
                error=str(e)
            )
    
    # Set up the console listener
    page.on("console", handle_console_log)
    
    logger.info(
        "Console log listener set up for session",
        session_id=session_id
    ) 
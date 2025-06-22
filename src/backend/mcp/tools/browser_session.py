"""
Browser Session Management Tool for IntelliBrowse MCP Server.

This tool manages Playwright browser sessions for browser-based test automation,
providing session lifecycle management and browser control capabilities.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
import structlog
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

# Import the main MCP server instance
try:
    from server_instance import mcp_server
except ImportError:
    # Fallback for when running directly from mcp directory
    from server_instance import mcp_server

# Import schemas
try:
    from schemas.tools.open_browser_schemas import OpenBrowserRequest, OpenBrowserResponse
except ImportError:
    # Fallback for when running directly from mcp directory
    from schemas.tools.open_browser_schemas import OpenBrowserRequest, OpenBrowserResponse
try:
    from schemas.tools.close_browser_schemas import CloseBrowserRequest, CloseBrowserResponse
except ImportError:
    # Fallback for when running directly from mcp directory
    from schemas.tools.close_browser_schemas import CloseBrowserRequest, CloseBrowserResponse
try:
    from schemas.tools.navigate_to_url_schemas import NavigateToUrlRequest, NavigateToUrlResponse
except ImportError:
    # Fallback for when running directly from mcp directory
    from schemas.tools.navigate_to_url_schemas import NavigateToUrlRequest, NavigateToUrlResponse

logger = structlog.get_logger("intellibrowse.mcp.tools.browser_session")

# Global browser session storage (in production, this should be Redis or similar)
browser_sessions: Dict[str, Dict[str, Any]] = {}


# NOTE: navigate_to_url tool has been extracted to its own dedicated file:
# src/backend/mcp/tools/navigate_to_url.py following SRP (Single Responsibility Principle)
# This maintains the architectural pattern of one tool per file for better modularity


@mcp_server.tool()
async def open_browser(
    headless: bool = True,
    browser_type: str = "chromium",
    viewport_width: int = 1920,
    viewport_height: int = 1080,
    user_agent: Optional[str] = None,
    extra_http_headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Open a new Playwright browser session and return a session identifier.
    
    This tool creates a new browser instance with the specified configuration
    and returns a session ID that can be used for subsequent browser operations.
    
    Args:
        headless: Open browser in headless mode (default: True)
        browser_type: Browser type - chromium, firefox, or webkit (default: chromium)
        viewport_width: Viewport width in pixels (default: 1920)
        viewport_height: Viewport height in pixels (default: 1080)
        user_agent: Custom user agent string (optional)
        extra_http_headers: Extra HTTP headers to set (optional)
    
    Returns:
        Dict containing session_id and browser session details
    """
    logger.info(
        "Opening browser session",
        browser_type=browser_type,
        headless=headless,
        viewport=f"{viewport_width}x{viewport_height}"
    )
    
    try:
        # Validate request
        request = OpenBrowserRequest(
            headless=headless,
            browser_type=browser_type,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            user_agent=user_agent,
            extra_http_headers=extra_http_headers or {}
        )
        
        # Start Playwright
        playwright = await async_playwright().start()
        
        # Get the specified browser type
        if browser_type == "chromium":
            browser_launcher = playwright.chromium
        elif browser_type == "firefox":
            browser_launcher = playwright.firefox
        elif browser_type == "webkit":
            browser_launcher = playwright.webkit
        else:
            raise ValueError(f"Unsupported browser type: {browser_type}")
        
        # Launch browser with specified options
        launch_options = {
            "headless": headless
        }
        
        browser = await browser_launcher.launch(**launch_options)
        
        # Create browser context with viewport and other options
        context_options = {
            "viewport": {"width": viewport_width, "height": viewport_height}
        }
        
        if user_agent:
            context_options["user_agent"] = user_agent
            
        if extra_http_headers:
            context_options["extra_http_headers"] = extra_http_headers
        
        context = await browser.new_context(**context_options)
        
        # Create a new page
        page = await context.new_page()
        
        # Generate unique session ID
        session_id = f"browser_session_{uuid.uuid4().hex[:8]}"
        
        # Store session details
        browser_sessions[session_id] = {
            "session_id": session_id,
            "playwright": playwright,
            "browser": browser,
            "context": context,
            "page": page,
            "browser_type": browser_type,
            "headless": headless,
            "viewport": {"width": viewport_width, "height": viewport_height},
            "created_at": datetime.utcnow().isoformat(),
            "user_agent": user_agent,
            "extra_http_headers": extra_http_headers or {}
        }
        
        # Log successful session creation for audit compliance
        logger.info(
            "Browser session created successfully",
            session_id=session_id,
            browser_type=browser_type,
            headless=headless,
            viewport_width=viewport_width,
            viewport_height=viewport_height
        )
        
        # Create response
        response = OpenBrowserResponse(
            session_id=session_id,
            browser_type=browser_type,
            headless=headless,
            viewport={"width": viewport_width, "height": viewport_height},
            message=f"Browser session {session_id} opened successfully",
            metadata={
                "created_at": browser_sessions[session_id]["created_at"],
                "version": "1.0.0",
                "playwright_version": playwright.version if hasattr(playwright, 'version') else "unknown",
                "total_sessions": len(browser_sessions)
            }
        )
        
        return response.dict()
        
    except Exception as e:
        logger.error("Error opening browser session", error=str(e))
        # Return error wrapped in MCP protocol format
        return {
            "error": {
                "code": "BROWSER_SESSION_ERROR",
                "message": f"Failed to open browser session: {str(e)}"
            }
        }


@mcp_server.tool()
async def get_browser_session_info(session_id: str) -> Dict[str, Any]:
    """
    Get information about an existing browser session.
    
    Args:
        session_id: Browser session identifier
    
    Returns:
        Dict containing session information or error
    """
    logger.info("Getting browser session info", session_id=session_id)
    
    try:
        if session_id not in browser_sessions:
            return {
                "error": {
                    "code": "SESSION_NOT_FOUND",
                    "message": f"Browser session {session_id} not found"
                }
            }
        
        session_data = browser_sessions[session_id]
        
        # Return session info without the actual browser objects
        session_info = {
            "session_id": session_data["session_id"],
            "browser_type": session_data["browser_type"],
            "headless": session_data["headless"],
            "viewport": session_data["viewport"],
            "created_at": session_data["created_at"],
            "user_agent": session_data.get("user_agent"),
            "extra_http_headers": session_data.get("extra_http_headers", {}),
            "status": "active"
        }
        
        logger.info("Session info retrieved", session_id=session_id)
        return {"session_info": session_info}
        
    except Exception as e:
        logger.error("Error getting session info", session_id=session_id, error=str(e))
        return {
            "error": {
                "code": "SESSION_INFO_ERROR",
                "message": f"Failed to get session info: {str(e)}"
            }
        }


@mcp_server.tool()
async def close_browser_session(session_id: str) -> Dict[str, Any]:
    """
    Close an existing browser session and clean up resources.
    
    Args:
        session_id: Browser session identifier
    
    Returns:
        Dict containing success message or error
    """
    logger.info("Closing browser session", session_id=session_id)
    
    try:
        if session_id not in browser_sessions:
            return {
                "error": {
                    "code": "SESSION_NOT_FOUND",
                    "message": f"Browser session {session_id} not found"
                }
            }
        
        session_data = browser_sessions[session_id]
        
        # Close browser resources in order
        try:
            if "page" in session_data and session_data["page"]:
                await session_data["page"].close()
        except Exception as e:
            logger.warning("Error closing page", session_id=session_id, error=str(e))
        
        try:
            if "context" in session_data and session_data["context"]:
                await session_data["context"].close()
        except Exception as e:
            logger.warning("Error closing context", session_id=session_id, error=str(e))
        
        try:
            if "browser" in session_data and session_data["browser"]:
                await session_data["browser"].close()
        except Exception as e:
            logger.warning("Error closing browser", session_id=session_id, error=str(e))
        
        try:
            if "playwright" in session_data and session_data["playwright"]:
                await session_data["playwright"].stop()
        except Exception as e:
            logger.warning("Error stopping playwright", session_id=session_id, error=str(e))
        
        # Remove session from storage
        del browser_sessions[session_id]
        
        logger.info("Browser session closed successfully", session_id=session_id)
        
        return {
            "message": f"Browser session {session_id} closed successfully",
            "session_id": session_id,
            "remaining_sessions": len(browser_sessions)
        }
        
    except Exception as e:
        logger.error("Error closing browser session", session_id=session_id, error=str(e))
        return {
            "error": {
                "code": "SESSION_CLOSE_ERROR",
                "message": f"Failed to close browser session: {str(e)}"
            }
        }


@mcp_server.tool()
async def close_browser(
    session_id: str
) -> Dict[str, Any]:
    """
    Close a Playwright browser session given a session ID with structured request/response.
    
    This tool provides a structured interface for closing browser sessions with
    proper Pydantic validation and comprehensive error handling.
    
    Args:
        session_id: The ID of the browser session to close
    
    Returns:
        Dict containing CloseBrowserResponse or error
    """
    logger.info("Closing browser session with structured response", session_id=session_id)
    
    try:
        # Validate request using Pydantic schema
        request = CloseBrowserRequest(session_id=session_id)
        
        if session_id not in browser_sessions:
            response = CloseBrowserResponse(
                closed=False,
                session_id=session_id,
                message=f"Session {session_id} not found or already closed",
                remaining_sessions=len(browser_sessions)
            )
            return response.dict()
        
        session_data = browser_sessions[session_id]
        
        # Close browser resources in order with individual error handling
        close_errors = []
        
        try:
            if "page" in session_data and session_data["page"]:
                await session_data["page"].close()
        except Exception as e:
            close_errors.append(f"page: {str(e)}")
            logger.warning("Error closing page", session_id=session_id, error=str(e))
        
        try:
            if "context" in session_data and session_data["context"]:
                await session_data["context"].close()
        except Exception as e:
            close_errors.append(f"context: {str(e)}")
            logger.warning("Error closing context", session_id=session_id, error=str(e))
        
        try:
            if "browser" in session_data and session_data["browser"]:
                await session_data["browser"].close()
        except Exception as e:
            close_errors.append(f"browser: {str(e)}")
            logger.warning("Error closing browser", session_id=session_id, error=str(e))
        
        try:
            if "playwright" in session_data and session_data["playwright"]:
                await session_data["playwright"].stop()
        except Exception as e:
            close_errors.append(f"playwright: {str(e)}")
            logger.warning("Error stopping playwright", session_id=session_id, error=str(e))
        
        # Remove session from storage
        del browser_sessions[session_id]
        
        # Log successful closure for audit compliance
        logger.info(
            "Browser session closed successfully with structured response",
            session_id=session_id,
            remaining_sessions=len(browser_sessions),
            close_errors=close_errors if close_errors else None
        )
        
        # Create structured response
        message = f"Session {session_id} successfully closed"
        if close_errors:
            message += f" (with warnings: {'; '.join(close_errors)})"
        
        response = CloseBrowserResponse(
            closed=True,
            session_id=session_id,
            message=message,
            remaining_sessions=len(browser_sessions)
        )
        
        return response.dict()
        
    except Exception as e:
        logger.error("Error closing browser session with structured response", session_id=session_id, error=str(e))
        # Return error wrapped in MCP protocol format
        return {
            "error": {
                "code": "BROWSER_SESSION_CLOSE_ERROR",
                "message": f"Failed to close session {session_id}: {str(e)}"
            }
        }


@mcp_server.tool()
async def list_browser_sessions() -> Dict[str, Any]:
    """
    List all active browser sessions.
    
    Returns:
        Dict containing list of active sessions
    """
    logger.info("Listing browser sessions")
    
    try:
        active_sessions = []
        
        for session_id, session_data in browser_sessions.items():
            active_sessions.append({
                "session_id": session_data["session_id"],
                "browser_type": session_data["browser_type"],
                "headless": session_data["headless"],
                "viewport": session_data["viewport"],
                "created_at": session_data["created_at"]
            })
        
        return {
            "active_sessions": active_sessions,
            "total_count": len(active_sessions)
        }
        
    except Exception as e:
        logger.error("Error listing browser sessions", error=str(e))
        return {
            "error": {
                "code": "SESSION_LIST_ERROR",
                "message": f"Failed to list browser sessions: {str(e)}"
            }
        }


def get_browser_session(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Helper function to get browser session objects for use by other tools.
    
    Args:
        session_id: Browser session identifier
    
    Returns:
        Session data dictionary or None if not found
    """
    return browser_sessions.get(session_id) 
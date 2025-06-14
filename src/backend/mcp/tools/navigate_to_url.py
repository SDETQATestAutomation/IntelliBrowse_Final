"""
Navigate To URL Tool for IntelliBrowse MCP Server.

This module provides URL navigation functionality for Playwright browser sessions,
enabling browser automation workflows to navigate to specific web pages with
comprehensive error handling and metadata collection.
"""

import time
from datetime import datetime
from typing import Dict, Any, Optional
from urllib.parse import urlparse
import structlog
from playwright.async_api import Page, Error as PlaywrightError
from pydantic import ValidationError

# Import the main MCP server instance
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from main import mcp_server

# Import schemas - use modular schema imports
from src.backend.mcp.schemas.tools.navigate_to_url_schemas import NavigateToUrlRequest, NavigateToUrlResponse

# Import browser session utilities - use absolute import
sys.path.append(str(Path(__file__).parent))
from browser_session import browser_sessions

logger = structlog.get_logger("intellibrowse.mcp.tools.navigate_to_url")

# Valid wait_until options for Playwright navigation
VALID_WAIT_UNTIL_OPTIONS = ["load", "domcontentloaded", "networkidle"]


@mcp_server.tool()
async def navigate_to_url(
    session_id: str,
    url: str,
    timeout_ms: Optional[int] = 10000,
    wait_until: str = "domcontentloaded"
) -> Dict[str, Any]:
    """
    Navigate the browser to a specified URL within an open session.
    
    This tool navigates an existing Playwright browser session to the specified URL
    and returns navigation status, timing, and response information. It provides
    comprehensive error handling, URL validation, and metadata collection.
    
    Args:
        session_id: Browser session identifier for the target session
        url: Destination URL to navigate to (supports auto-HTTPS scheme addition)
        timeout_ms: Navigation timeout in milliseconds (default: 10000)
        wait_until: When to consider navigation succeeded (default: "domcontentloaded")
    
    Returns:
        Dict containing navigation status, timing, and comprehensive metadata
    """
    start_time = time.monotonic()
    
    logger.info(
        "Starting URL navigation",
        session_id=session_id,
        url=url,
        timeout_ms=timeout_ms,
        wait_until=wait_until
    )
    
    try:
        # Validate request using Pydantic schema
        request = NavigateToUrlRequest(
            session_id=session_id,
            url=url,
            timeout_ms=timeout_ms,
            wait_until=wait_until
        )
        
        # Validate wait_until option
        if wait_until not in VALID_WAIT_UNTIL_OPTIONS:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Invalid wait_until option", wait_until=wait_until, valid_options=VALID_WAIT_UNTIL_OPTIONS)
            return NavigateToUrlResponse(
                navigated=False,
                http_status=None,
                final_url="",
                message=f"Invalid wait_until option '{wait_until}'. Valid options: {VALID_WAIT_UNTIL_OPTIONS}",
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "INVALID_WAIT_UNTIL",
                    "valid_options": VALID_WAIT_UNTIL_OPTIONS,
                    "provided_option": wait_until
                }
            ).dict()
        
        # Check if session exists
        if session_id not in browser_sessions:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Browser session not found", session_id=session_id)
            return NavigateToUrlResponse(
                navigated=False,
                http_status=None,
                final_url="",
                message=f"Browser session {session_id} not found",
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "SESSION_NOT_FOUND",
                    "session_id": session_id,
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
            return NavigateToUrlResponse(
                navigated=False,
                http_status=None,
                final_url="",
                message=f"Page is not active or accessible: {str(e)}",
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "PAGE_NOT_ACTIVE",
                    "error_details": str(e),
                    "operation_time_ms": elapsed_ms
                }
            ).dict()
        
        # Validate and normalize URL format
        original_url = url
        try:
            parsed_url = urlparse(url)
            if not parsed_url.scheme:
                url = f"https://{url}"  # Default to HTTPS if no scheme provided
                parsed_url = urlparse(url)
                logger.info("Auto-added HTTPS scheme", original_url=original_url, normalized_url=url)
                
            if not parsed_url.netloc:
                raise ValueError("Invalid URL format - missing domain")
                
        except Exception as e:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("URL validation failed", url=original_url, error=str(e))
            return NavigateToUrlResponse(
                navigated=False,
                http_status=None,
                final_url="",
                message=f"Invalid URL format: {str(e)}",
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "INVALID_URL",
                    "original_url": original_url,
                    "error_details": str(e),
                    "operation_time_ms": elapsed_ms
                }
            ).dict()
        
        # Perform navigation operation
        response = None
        try:
            logger.info("Performing navigation", url=url, timeout_ms=timeout_ms, wait_until=wait_until)
            
            response = await page.goto(
                url,
                timeout=timeout_ms,
                wait_until=wait_until
            )
            
            # Get final URL (may be different due to redirects)
            final_url = page.url
            
            # Get HTTP status
            http_status = response.status if response else None
            
            # Calculate elapsed time
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            
            # Determine if navigation was successful
            navigated = (http_status is not None and 200 <= http_status < 400)
            
            # Calculate redirect information
            redirect_count = 0
            redirect_chain = []
            if response and response.request:
                current_request = response.request
                while current_request.redirected_from:
                    redirect_chain.append(current_request.redirected_from.url)
                    current_request = current_request.redirected_from
                redirect_count = len(redirect_chain)
            
            # Collect comprehensive metadata
            try:
                page_title = await page.title() if navigated else None
                page_content_info = {
                    "has_content": bool(await page.content()) if navigated else False,
                    "content_length": len(await page.content()) if navigated else 0
                }
            except PlaywrightError:
                page_title = None
                page_content_info = {"has_content": False, "content_length": 0}
            
            metadata = {
                "page_title": page_title,
                "load_event_fired": navigated,
                "redirects": redirect_count,
                "redirect_chain": redirect_chain,
                "user_agent": session.get("user_agent"),
                "viewport": session.get("viewport"),
                "browser_type": session.get("browser_type"),
                "operation_time_ms": elapsed_ms,
                "url_scheme_added": (original_url != url),
                "page_content": page_content_info,
                "navigation_timing": {
                    "timeout_ms": timeout_ms,
                    "wait_until": wait_until,
                    "start_time": start_time
                }
            }
            
            # Update session metadata with navigation history
            if "navigation_history" not in session:
                session["navigation_history"] = []
            
            session["navigation_history"].append({
                "url": final_url,
                "timestamp": datetime.utcnow().isoformat(),
                "http_status": http_status,
                "elapsed_ms": elapsed_ms,
                "redirects": redirect_count,
                "success": navigated
            })
            
            # Keep only last 10 navigation entries
            session["navigation_history"] = session["navigation_history"][-10:]
            
            # Update last navigation metadata
            session["last_navigation"] = {
                "url": final_url,
                "timestamp": datetime.utcnow().isoformat(),
                "http_status": http_status,
                "elapsed_ms": elapsed_ms,
                "redirects": redirect_count,
                "success": navigated
            }
            
            # Create success/failure message
            if navigated:
                message = f"Navigation successful to {final_url}"
                if http_status:
                    message += f" (HTTP {http_status})"
                if redirect_count > 0:
                    message += f" via {redirect_count} redirect(s)"
            else:
                message = f"Navigation failed to {final_url}"
                if http_status:
                    message += f" (HTTP {http_status})"
            
            # Log navigation completion for audit compliance
            logger.info(
                "Navigation operation completed",
                session_id=session_id,
                original_url=original_url,
                final_url=final_url,
                http_status=http_status,
                elapsed_ms=elapsed_ms,
                navigated=navigated,
                redirects=redirect_count
            )
            
            # Return structured response
            return NavigateToUrlResponse(
                navigated=navigated,
                http_status=http_status,
                final_url=final_url,
                message=message,
                elapsed_ms=elapsed_ms,
                metadata=metadata
            ).dict()
            
        except Exception as nav_error:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            error_message = str(nav_error)
            error_type = type(nav_error).__name__
            
            logger.error(
                "Navigation operation failed",
                session_id=session_id,
                url=url,
                error=error_message,
                error_type=error_type,
                elapsed_ms=elapsed_ms
            )
            
            return NavigateToUrlResponse(
                navigated=False,
                http_status=None,
                final_url=page.url if page else "",
                message=f"Navigation failed: {error_message}",
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "NAVIGATION_FAILED",
                    "error_details": error_message,
                    "error_type": error_type,
                    "timeout_ms": timeout_ms,
                    "wait_until": wait_until,
                    "operation_time_ms": elapsed_ms,
                    "original_url": original_url
                }
            ).dict()
            
    except ValidationError as ve:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        validation_errors = str(ve)
        logger.error("Request validation failed", error=validation_errors, elapsed_ms=elapsed_ms)
        return NavigateToUrlResponse(
            navigated=False,
            http_status=None,
            final_url="",
            message=f"Request validation failed: {validation_errors}",
            elapsed_ms=elapsed_ms,
            metadata={
                "error": "VALIDATION_ERROR",
                "validation_details": validation_errors,
                "operation_time_ms": elapsed_ms
            }
        ).dict()
        
    except Exception as e:
        # Handle any unexpected errors
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        error_message = str(e)
        
        logger.error(
            "Unexpected error during navigation",
            session_id=session_id,
            url=url,
            error=error_message,
            elapsed_ms=elapsed_ms
        )
        
        return NavigateToUrlResponse(
            navigated=False,
            http_status=None,
            final_url="",
            message=f"Unexpected error during navigation: {error_message}",
            elapsed_ms=elapsed_ms,
            metadata={
                "error": "UNEXPECTED_ERROR",
                "error_details": error_message,
                "operation_time_ms": elapsed_ms
            }
        ).dict()


@mcp_server.prompt()
def navigate_url_prompt(url: str, wait_condition: str = "domcontentloaded") -> str:
    """
    Returns a prompt guiding the LLM to navigate to a specific URL.
    
    This prompt template helps users understand how to perform navigation operations
    and provides context for browser automation workflows.
    
    Args:
        url: The destination URL to navigate to
        wait_condition: When to consider navigation complete
    
    Returns:
        Formatted prompt string for navigation operation guidance
    """
    return f"""Navigate the browser to '{url}' and wait until {wait_condition}.

This will perform a browser navigation operation which can be used for:
- Loading web pages for testing or automation
- Redirecting browser sessions to specific application pages
- Initializing test scenarios with specific starting pages
- Workflow progression through different application states
- Page refresh or reload operations

The navigation will wait for the page to reach the '{wait_condition}' state before completing:
- 'load': Wait for the page load event (all resources loaded)
- 'domcontentloaded': Wait for DOM to be fully constructed (default)
- 'networkidle': Wait for no network requests for 500ms

The operation includes comprehensive error handling, redirect tracking, and performance timing.""" 
"""
Go Forward Tool for IntelliBrowse MCP Server.

This module provides tools for navigating forward in browser history within 
Playwright browser sessions, enabling automated navigation workflow testing.
"""

import time
from typing import Dict, Any, Optional
import structlog
from playwright.async_api import Page, Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError

# Import the main MCP server instance
try:
    from server_instance import mcp_server
except ImportError:
    # Fallback for when running directly from mcp directory
    from server_instance import mcp_server

# Import schemas - use absolute import to avoid relative import issues
try:
    from schemas.tools.go_forward_schemas import GoForwardRequest, GoForwardResponse
except ImportError:
    # Fallback for when running directly from mcp directory
    from schemas.tools.go_forward_schemas import GoForwardRequest, GoForwardResponse

# Import browser session utilities - use absolute import
try:
    from tools.browser_session import browser_sessions
except ImportError:
    # Fallback for when running directly from mcp directory
    from tools.browser_session import browser_sessions

logger = structlog.get_logger("intellibrowse.mcp.tools.go_forward")

# Valid wait conditions
VALID_WAIT_CONDITIONS = ["load", "domcontentloaded", "networkidle"]


@mcp_server.tool()
async def go_forward(
    session_id: str,
    timeout_ms: Optional[int] = 5000,
    wait_until: Optional[str] = "load"
) -> Dict[str, Any]:
    """
    Navigate forward in browser history within the current browser context.
    
    This tool performs forward navigation in browser history within an active Playwright 
    browser session, supporting different wait conditions and comprehensive error handling
    for automated navigation workflow testing.
    
    Args:
        session_id: Active Playwright session identifier
        timeout_ms: Navigation timeout in milliseconds (default: 5000)
        wait_until: Wait condition - 'load', 'domcontentloaded', 'networkidle' (default: 'load')
    
    Returns:
        Dict containing navigation status, URL changes, and metadata
    """
    start_time = time.monotonic()
    
    logger.info(
        "Starting forward navigation operation",
        session_id=session_id,
        timeout_ms=timeout_ms,
        wait_until=wait_until
    )
    
    try:
        # Validate request using Pydantic schema
        request = GoForwardRequest(
            session_id=session_id,
            timeout_ms=timeout_ms,
            wait_until=wait_until
        )
        
        # Validate wait condition
        if wait_until not in VALID_WAIT_CONDITIONS:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Invalid wait condition", wait_until=wait_until, valid_conditions=VALID_WAIT_CONDITIONS)
            return GoForwardResponse(
                success=False,
                message=f"Invalid wait condition '{wait_until}'. Valid conditions: {VALID_WAIT_CONDITIONS}",
                navigation_occurred=False,
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "INVALID_WAIT_CONDITION",
                    "valid_conditions": VALID_WAIT_CONDITIONS,
                    "operation_time_ms": elapsed_ms
                }
            ).dict()
        
        # Check if session exists
        if session_id not in browser_sessions:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Session not found", session_id=session_id)
            return GoForwardResponse(
                success=False,
                message=f"Browser session {session_id} not found",
                navigation_occurred=False,
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "SESSION_NOT_FOUND",
                    "operation_time_ms": elapsed_ms
                }
            ).dict()
        
        session = browser_sessions[session_id]
        page: Page = session["page"]
        
        # Get current URL before navigation
        try:
            previous_url = page.url
            page_title = await page.title()
        except PlaywrightError as e:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Page is not active", session_id=session_id, error=str(e))
            return GoForwardResponse(
                success=False,
                message=f"Page is not active or accessible: {str(e)}",
                navigation_occurred=False,
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "PAGE_NOT_ACTIVE",
                    "error_details": str(e),
                    "operation_time_ms": elapsed_ms
                }
            ).dict()
        
        # Check if forward navigation is possible
        try:
            # Check if we can go forward by evaluating browser history state
            # Note: This is a best-effort check as browser history API is limited
            history_length = await page.evaluate("() => window.history.length")
            current_state = await page.evaluate("() => window.history.state")
            
            logger.info("History state check", history_length=history_length, current_state=current_state)
            
            # This is a heuristic check - we can't reliably determine if forward navigation is possible
            # But we'll try anyway and handle the failure gracefully
            
        except PlaywrightError as e:
            logger.warning("Could not check forward history availability", error=str(e))
            # Continue with navigation attempt even if history check fails
        
        # Perform forward navigation
        try:
            logger.info("Performing forward navigation", current_url=previous_url, wait_until=wait_until)
            
            # Prepare wait options
            wait_options = {"timeout": timeout_ms}
            if wait_until == "networkidle":
                wait_options["wait_until"] = "networkidle"
            elif wait_until == "domcontentloaded":
                wait_options["wait_until"] = "domcontentloaded"
            else:  # load (default)
                wait_options["wait_until"] = "load"
            
            # Perform navigation
            response = await page.go_forward(**wait_options)
            
            # Get new URL and page information
            try:
                current_url = page.url
                new_page_title = await page.title()
                
                # Check if navigation actually occurred
                navigation_occurred = current_url != previous_url
                
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                
                if navigation_occurred:
                    logger.info(
                        "Forward navigation completed successfully",
                        session_id=session_id,
                        previous_url=previous_url,
                        current_url=current_url,
                        elapsed_ms=elapsed_ms
                    )
                    
                    return GoForwardResponse(
                        success=True,
                        message="Successfully navigated forward",
                        previous_url=previous_url,
                        current_url=current_url,
                        navigation_occurred=True,
                        elapsed_ms=elapsed_ms,
                        metadata={
                            "wait_until": wait_until,
                            "operation_time_ms": elapsed_ms,
                            "page_title": new_page_title,
                            "history_available": True,
                            "response_status": getattr(response, 'status', None) if response else None
                        }
                    ).dict()
                else:
                    logger.warning("No navigation occurred during forward operation", current_url=current_url)
                    return GoForwardResponse(
                        success=True,
                        message="Forward navigation completed but no URL change occurred",
                        previous_url=previous_url,
                        current_url=current_url,
                        navigation_occurred=False,
                        elapsed_ms=elapsed_ms,
                        metadata={
                            "wait_until": wait_until,
                            "operation_time_ms": elapsed_ms,
                            "page_title": new_page_title,
                            "warning": "NO_URL_CHANGE"
                        }
                    ).dict()
                    
            except PlaywrightError as e:
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                logger.error("Failed to get page information after navigation", error=str(e))
                return GoForwardResponse(
                    success=False,
                    message=f"Navigation may have succeeded but failed to get page information: {str(e)}",
                    previous_url=previous_url,
                    navigation_occurred=True,  # Assume navigation occurred
                    elapsed_ms=elapsed_ms,
                    metadata={
                        "error": "POST_NAVIGATION_ERROR",
                        "error_details": str(e),
                        "operation_time_ms": elapsed_ms
                    }
                ).dict()
                
        except PlaywrightTimeoutError:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Forward navigation timed out", session_id=session_id, timeout_ms=timeout_ms, wait_until=wait_until)
            return GoForwardResponse(
                success=False,
                message=f"Forward navigation timed out after {timeout_ms} ms",
                previous_url=previous_url,
                navigation_occurred=False,
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "NAVIGATION_TIMEOUT",
                    "timeout_ms": timeout_ms,
                    "wait_until": wait_until,
                    "operation_time_ms": elapsed_ms
                }
            ).dict()
            
        except PlaywrightError as e:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            
            # Check if the error is due to no forward history
            if "Cannot go forward" in str(e) or "No forward history" in str(e):
                logger.warning("No forward history available", session_id=session_id, current_url=previous_url)
                return GoForwardResponse(
                    success=False,
                    message="No forward history available for navigation",
                    previous_url=previous_url,
                    current_url=previous_url,
                    navigation_occurred=False,
                    elapsed_ms=elapsed_ms,
                    metadata={
                        "error": "NO_FORWARD_HISTORY",
                        "operation_time_ms": elapsed_ms,
                        "page_title": page_title
                    }
                ).dict()
            else:
                logger.error("Forward navigation failed", session_id=session_id, error=str(e))
                return GoForwardResponse(
                    success=False,
                    message=f"Failed to navigate forward: {str(e)}",
                    previous_url=previous_url,
                    navigation_occurred=False,
                    elapsed_ms=elapsed_ms,
                    metadata={
                        "error": "NAVIGATION_FAILED",
                        "error_details": str(e),
                        "operation_time_ms": elapsed_ms
                    }
                ).dict()
    
    except Exception as e:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        logger.error("Unexpected error in forward navigation operation", session_id=session_id, error=str(e))
        return GoForwardResponse(
            success=False,
            message=f"Unexpected error during forward navigation: {str(e)}",
            navigation_occurred=False,
            elapsed_ms=elapsed_ms,
            metadata={
                "error": "UNEXPECTED_ERROR",
                "error_details": str(e),
                "operation_time_ms": elapsed_ms
            }
        ).dict()


@mcp_server.prompt()
def go_forward_prompt() -> str:
    """
    Generate guidance for browser forward navigation.
    
    Returns:
        Formatted prompt with forward navigation guidance
    """
    prompt = """
# Go Forward Tool Usage Guide

## Purpose
Navigate forward in browser history for automated navigation workflow testing.

## Basic Usage
```python
await go_forward(
    session_id="your_session_id",
    timeout_ms=5000,
    wait_until="load"
)
```

## Parameters
- **session_id**: Active browser session ID (required)
- **timeout_ms**: Navigation timeout in milliseconds (default: 5000)
- **wait_until**: Wait condition after navigation (default: "load")

## Wait Conditions

### Load (Default)
Wait for the load event to be fired:
```python
await go_forward(
    session_id="your_session_id",
    wait_until="load"
)
```

### DOM Content Loaded
Wait for DOM content to be loaded (faster):
```python
await go_forward(
    session_id="your_session_id",
    wait_until="domcontentloaded"
)
```

### Network Idle
Wait for no network requests for 500ms:
```python
await go_forward(
    session_id="your_session_id",
    wait_until="networkidle"
)
```

## Best Practices
1. Only use after going back in history
2. Use appropriate wait conditions based on page complexity
3. Handle cases where no forward history exists
4. Monitor navigation success through the response
5. Use reasonable timeout values (5-10 seconds typically)

## Common Use Cases
- Redo navigation after going back
- Testing browser forward button functionality
- Navigation flow verification
- User journey forward progression
- Browser history state testing

## Response Data
The tool returns:
- **success**: Whether navigation was successful
- **previous_url**: URL before navigation
- **current_url**: URL after navigation
- **navigation_occurred**: Whether URL actually changed
- **elapsed_ms**: Time taken for navigation
- **metadata**: Additional navigation information

## Error Handling
The tool provides comprehensive error handling for:
- Session not found
- Page not active
- No forward history available
- Navigation timeout
- Network errors
- Invalid wait conditions

## Navigation Flow Example
```python
# 1. Navigate to page 1
await navigate_to_url(session_id="session_123", url="https://example.com/page1")

# 2. Navigate to page 2
await navigate_to_url(session_id="session_123", url="https://example.com/page2")

# 3. Navigate to page 3
await navigate_to_url(session_id="session_123", url="https://example.com/page3")

# 4. Go back to page 2
await go_back(session_id="session_123")

# 5. Go forward to page 3 again
result = await go_forward(session_id="session_123")

# 6. Verify navigation
if result["success"] and result["navigation_occurred"]:
    print(f"Successfully navigated forward to: {result['current_url']}")
else:
    print(f"Navigation issue: {result['message']}")
```

## Important Notes
- Forward navigation only works if you've previously gone back in history
- No forward history exists at the "latest" page in your session
- Some single-page applications may not trigger URL changes
- The tool waits for the specified condition before considering navigation complete
- Always check the `navigation_occurred` flag to verify actual navigation

## Typical Error Scenarios
- **No Forward History**: User hasn't gone back, so no forward navigation possible
- **Page Not Active**: Browser session closed or page crashed
- **Timeout**: Page took too long to load after navigation
- **Network Error**: Connection issues during navigation
"""
    return prompt 
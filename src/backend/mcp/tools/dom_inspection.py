"""
DOM Inspection Tools for IntelliBrowse MCP Server.

This module provides tools for extracting and analyzing DOM content from 
Playwright browser sessions, enabling AI-driven page analysis and element discovery.
"""

import time
from typing import Dict, Any, Optional
import structlog
from playwright.async_api import Page, Error as PlaywrightError

# Import the main MCP server instance
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from main import mcp_server

# Import schemas - use absolute import to avoid relative import issues
sys.path.append(str(Path(__file__).parent.parent / "schemas"))
from tool_schemas import GetPageDomRequest, GetPageDomResponse

# Import browser session utilities - use absolute import
sys.path.append(str(Path(__file__).parent))
from browser_session import browser_sessions

logger = structlog.get_logger("intellibrowse.mcp.tools.dom_inspection")


@mcp_server.tool()
async def get_page_dom(
    session_id: str,
    selector: Optional[str] = None,
    outer_html: Optional[bool] = False,
    max_length: Optional[int] = 100_000
) -> Dict[str, Any]:
    """
    Retrieve page DOM or HTML content from the current browser context.
    
    This tool extracts DOM content from an active Playwright browser session,
    supporting both full page HTML and targeted element extraction with
    performance controls and comprehensive metadata.
    
    Args:
        session_id: Active Playwright session identifier
        selector: Optional CSS selector to target a specific element
        outer_html: Return outerHTML (default: innerHTML) if selector is specified
        max_length: Maximum HTML content length to return (truncate if exceeded)
    
    Returns:
        Dict containing HTML content, metadata, and extraction details
    """
    start_time = time.monotonic()
    
    logger.info(
        "Starting DOM extraction",
        session_id=session_id,
        selector=selector,
        outer_html=outer_html,
        max_length=max_length
    )
    
    try:
        # Validate request using Pydantic schema
        request = GetPageDomRequest(
            session_id=session_id,
            selector=selector,
            outer_html=outer_html,
            max_length=max_length
        )
        
        # Check if session exists
        if session_id not in browser_sessions:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Session not found", session_id=session_id)
            return GetPageDomResponse(
                html_content="",
                truncated=False,
                selector_used=selector,
                message=f"Browser session {session_id} not found",
                content_length=0,
                metadata={
                    "error": "SESSION_NOT_FOUND",
                    "extraction_time_ms": elapsed_ms,
                    "extraction_type": "error"
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
            return GetPageDomResponse(
                html_content="",
                truncated=False,
                selector_used=selector,
                message=f"Page is not active or accessible: {str(e)}",
                content_length=0,
                metadata={
                    "error": "PAGE_NOT_ACTIVE",
                    "extraction_time_ms": elapsed_ms,
                    "extraction_type": "error"
                }
            ).dict()
        
        # Extract DOM content based on selector presence
        html_content = ""
        extraction_type = ""
        element_count = 0
        
        try:
            if selector:
                # Element-specific DOM extraction
                extraction_type = "element_selector"
                
                # Check if element exists
                element_handle = await page.query_selector(selector)
                if not element_handle:
                    elapsed_ms = int((time.monotonic() - start_time) * 1000)
                    logger.warning("Element not found", session_id=session_id, selector=selector)
                    return GetPageDomResponse(
                        html_content="",
                        truncated=False,
                        selector_used=selector,
                        message=f"Element not found for selector: {selector}",
                        content_length=0,
                        metadata={
                            "error": "ELEMENT_NOT_FOUND",
                            "extraction_time_ms": elapsed_ms,
                            "extraction_type": extraction_type,
                            "page_url": page.url,
                            "page_title": await page.title()
                        }
                    ).dict()
                
                # Extract HTML content
                if outer_html:
                    html_content = await page.eval_on_selector(selector, "el => el.outerHTML")
                else:
                    html_content = await page.eval_on_selector(selector, "el => el.innerHTML")
                
                # Count child elements for metadata
                element_count = await page.eval_on_selector(
                    selector, 
                    "el => el.querySelectorAll('*').length"
                )
                
            else:
                # Full page HTML extraction
                extraction_type = "full_page"
                html_content = await page.content()
                
                # Count all elements for metadata
                element_count = await page.evaluate("document.querySelectorAll('*').length")
        
        except PlaywrightError as e:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("DOM extraction failed", session_id=session_id, error=str(e))
            return GetPageDomResponse(
                html_content="",
                truncated=False,
                selector_used=selector,
                message=f"DOM extraction failed: {str(e)}",
                content_length=0,
                metadata={
                    "error": "EXTRACTION_FAILED",
                    "error_details": str(e),
                    "extraction_time_ms": elapsed_ms,
                    "extraction_type": extraction_type
                }
            ).dict()
        
        # Handle content length and truncation
        original_length = len(html_content)
        truncated = False
        
        if max_length and original_length > max_length:
            html_content = html_content[:max_length] + "\n<!-- [TRUNCATED] -->"
            truncated = True
            logger.info(
                "DOM content truncated",
                session_id=session_id,
                original_length=original_length,
                truncated_length=max_length
            )
        
        # Calculate elapsed time
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        
        # Collect comprehensive metadata
        try:
            page_title = await page.title()
            page_url = page.url
        except PlaywrightError:
            page_title = "Unknown"
            page_url = "Unknown"
        
        metadata = {
            "extraction_type": extraction_type,
            "page_title": page_title,
            "page_url": page_url,
            "element_count": element_count,
            "extraction_time_ms": elapsed_ms,
            "original_content_length": original_length,
            "browser_type": session.get("browser_type", "unknown"),
            "viewport": session.get("viewport", {}),
            "user_agent": session.get("user_agent")
        }
        
        # Create success message
        if selector:
            message = f"DOM retrieved successfully for selector {selector}"
            if truncated:
                message += f" (truncated from {original_length} to {max_length} characters)"
        else:
            message = "Full page DOM retrieved successfully"
            if truncated:
                message += f" (truncated from {original_length} to {max_length} characters)"
        
        # Log successful extraction for audit compliance
        logger.info(
            "DOM extraction completed successfully",
            session_id=session_id,
            selector=selector,
            content_length=len(html_content),
            truncated=truncated,
            elapsed_ms=elapsed_ms,
            extraction_type=extraction_type
        )
        
        # Return successful response
        return GetPageDomResponse(
            html_content=html_content,
            truncated=truncated,
            selector_used=selector,
            message=message,
            content_length=len(html_content),
            metadata=metadata
        ).dict()
        
    except Exception as e:
        # Handle any unexpected errors
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        error_message = str(e)
        
        logger.error(
            "Unexpected error during DOM extraction",
            session_id=session_id,
            selector=selector,
            error=error_message,
            elapsed_ms=elapsed_ms
        )
        
        return GetPageDomResponse(
            html_content="",
            truncated=False,
            selector_used=selector,
            message=f"Unexpected error during DOM extraction: {error_message}",
            content_length=0,
            metadata={
                "error": "UNEXPECTED_ERROR",
                "error_details": error_message,
                "extraction_time_ms": elapsed_ms,
                "extraction_type": "error"
            }
        ).dict()


@mcp_server.prompt()
def get_dom_prompt(selector: Optional[str] = None) -> str:
    """
    Returns a prompt guiding the LLM to extract DOM content for a page or element.
    
    This prompt template helps users understand how to request DOM extraction
    and provides context for AI-driven page analysis tasks.
    
    Args:
        selector: Optional CSS selector for targeted extraction
    
    Returns:
        Formatted prompt string for DOM extraction guidance
    """
    if selector:
        return f"""Extract the DOM (HTML) content of the element matching '{selector}'.

This will return the HTML structure of the specific element, which can be used for:
- Element analysis and validation
- Selector generation and testing  
- Dynamic content inspection
- UI component structure review

The extraction will include all child elements and their attributes within the selected element."""
    
    return """Extract the full HTML content of the current web page.

This will return the complete DOM structure, which can be used for:
- Comprehensive page analysis
- Element discovery and mapping
- Content validation and testing
- Automated test case generation
- Page structure documentation

The extraction includes all HTML elements, attributes, and content currently loaded in the browser.""" 
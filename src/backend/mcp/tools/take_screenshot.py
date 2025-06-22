"""
Take Screenshot Tool for IntelliBrowse MCP Server.

This module provides tools for capturing page or element screenshots within 
Playwright browser sessions, enabling automated visual validation and documentation workflows.
"""

import time
import base64
import os
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
import structlog
from playwright.async_api import Page, Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError

# Import the main MCP server instance
import sys
from pathlib import Path as PathLib
sys.path.append(str(PathLib(__file__).parent.parent))
try:
    from server_instance import mcp_server
except ImportError:
    # Fallback for when running directly from mcp directory
    from server_instance import mcp_server

# Import schemas - use absolute import to avoid relative import issues
sys.path.append(str(PathLib(__file__).parent.parent / "schemas"))
try:
    from schemas.tools.take_screenshot_schemas import TakeScreenshotRequest, TakeScreenshotResponse
except ImportError:
    # Fallback for when running directly from mcp directory
    from schemas.tools.take_screenshot_schemas import TakeScreenshotRequest, TakeScreenshotResponse

# Import browser session utilities - use absolute import
sys.path.append(str(PathLib(__file__).parent))
try:
    from tools.browser_session import browser_sessions
except ImportError:
    # Fallback for when running directly from mcp directory
    from tools.browser_session import browser_sessions

logger = structlog.get_logger("intellibrowse.mcp.tools.take_screenshot")

# Screenshot storage configuration
SCREENSHOTS_DIR = os.getenv("SCREENSHOTS_DIR", "./screenshots")
MAX_FILE_SIZE_MB = int(os.getenv("MAX_SCREENSHOT_SIZE_MB", "10"))
VALID_FORMATS = ["png", "jpeg", "jpg"]


@mcp_server.tool()
async def take_screenshot(
    session_id: str,
    element_selector: Optional[str] = None,
    full_page: Optional[bool] = False,
    format: Optional[str] = "png",
    quality: Optional[int] = 90,
    timeout_ms: Optional[int] = 5000,
    store_base64: Optional[bool] = True,
    save_to_file: Optional[bool] = False,
    filename: Optional[str] = None
) -> Dict[str, Any]:
    """
    Capture screenshot of page or specific element in the current browser context.
    
    This tool captures screenshots within an active Playwright browser session,
    supporting element-specific or full-page capture with comprehensive storage options
    and metadata collection for automated visual validation and documentation workflows.
    
    Args:
        session_id: Active Playwright session identifier
        element_selector: CSS selector of specific element to capture (optional)
        full_page: Capture full scrollable page (default: False)
        format: Image format - 'png', 'jpeg', or 'jpg' (default: 'png')
        quality: JPEG quality 1-100 (ignored for PNG, default: 90)
        timeout_ms: Timeout in milliseconds for element availability (default: 5000)
        store_base64: Include base64 encoded image in response (default: True)
        save_to_file: Save screenshot to file system (default: False)
        filename: Custom filename for saved screenshot (optional)
    
    Returns:
        Dict containing screenshot data, file information, and metadata
    """
    start_time = time.monotonic()
    
    logger.info(
        "Starting screenshot capture operation",
        session_id=session_id,
        element_selector=element_selector,
        full_page=full_page,
        format=format,
        quality=quality,
        timeout_ms=timeout_ms,
        store_base64=store_base64,
        save_to_file=save_to_file,
        filename=filename
    )
    
    try:
        # Validate request using Pydantic schema
        request = TakeScreenshotRequest(
            session_id=session_id,
            element_selector=element_selector,
            full_page=full_page,
            format=format,
            quality=quality,
            timeout_ms=timeout_ms,
            store_base64=store_base64,
            save_to_file=save_to_file,
            filename=filename
        )
        
        # Normalize format
        format = format.lower()
        if format == "jpg":
            format = "jpeg"
        
        # Check if session exists
        if session_id not in browser_sessions:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Session not found", session_id=session_id)
            return TakeScreenshotResponse(
                success=False,
                message=f"Browser session {session_id} not found",
                format=format,
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "SESSION_NOT_FOUND",
                    "operation_time_ms": elapsed_ms
                }
            ).dict()
        
        session = browser_sessions[session_id]
        page: Page = session["page"]
        
        # Verify page is still active
        try:
            page_title = await page.title()
            page_url = page.url
        except PlaywrightError as e:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Page is not active", session_id=session_id, error=str(e))
            return TakeScreenshotResponse(
                success=False,
                message=f"Page is not active or accessible: {str(e)}",
                format=format,
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "PAGE_NOT_ACTIVE",
                    "error_details": str(e),
                    "operation_time_ms": elapsed_ms
                }
            ).dict()
        
        # Wait for element if selector is provided
        if element_selector:
            try:
                logger.info("Waiting for element to be visible", selector=element_selector, timeout_ms=timeout_ms)
                await page.wait_for_selector(
                    element_selector, 
                    timeout=timeout_ms, 
                    state="visible"
                )
            except PlaywrightTimeoutError:
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                logger.warning("Element not found or not visible", session_id=session_id, selector=element_selector, timeout_ms=timeout_ms)
                return TakeScreenshotResponse(
                    success=False,
                    message=f"Element '{element_selector}' not found or not visible after {timeout_ms} ms",
                    element_selector=element_selector,
                    format=format,
                    elapsed_ms=elapsed_ms,
                    metadata={
                        "error": "ELEMENT_NOT_VISIBLE",
                        "timeout_ms": timeout_ms,
                        "operation_time_ms": elapsed_ms,
                        "page_url": page_url,
                        "page_title": page_title
                    }
                ).dict()
            except PlaywrightError as e:
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                logger.error("Element wait failed", session_id=session_id, selector=element_selector, error=str(e))
                return TakeScreenshotResponse(
                    success=False,
                    message=f"Failed to wait for element '{element_selector}': {str(e)}",
                    element_selector=element_selector,
                    format=format,
                    elapsed_ms=elapsed_ms,
                    metadata={
                        "error": "ELEMENT_WAIT_FAILED",
                        "error_details": str(e),
                        "operation_time_ms": elapsed_ms
                    }
                ).dict()
        
        # Prepare screenshot options
        screenshot_options = {
            "type": format,
            "full_page": full_page if not element_selector else False  # Element screenshots can't be full page
        }
        
        if format == "jpeg":
            screenshot_options["quality"] = quality
        
        # Generate filename if needed
        if save_to_file or filename:
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                element_suffix = f"_element" if element_selector else ""
                full_page_suffix = f"_fullpage" if full_page else ""
                filename = f"screenshot_{timestamp}{element_suffix}{full_page_suffix}.{format}"
            
            # Ensure screenshots directory exists
            os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
            file_path = os.path.join(SCREENSHOTS_DIR, filename)
        else:
            file_path = None
        
        # Capture screenshot
        try:
            logger.info("Capturing screenshot", element_selector=element_selector, full_page=full_page, format=format)
            
            if element_selector:
                # Element-specific screenshot
                element = page.locator(element_selector)
                screenshot_bytes = await element.screenshot(**screenshot_options)
            else:
                # Page screenshot
                screenshot_bytes = await page.screenshot(**screenshot_options)
            
            # Check file size
            file_size_bytes = len(screenshot_bytes)
            if file_size_bytes > MAX_FILE_SIZE_MB * 1024 * 1024:
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                logger.error("Screenshot too large", file_size_mb=file_size_bytes / (1024 * 1024), max_size_mb=MAX_FILE_SIZE_MB)
                return TakeScreenshotResponse(
                    success=False,
                    message=f"Screenshot size ({file_size_bytes / (1024 * 1024):.1f}MB) exceeds maximum allowed size ({MAX_FILE_SIZE_MB}MB)",
                    format=format,
                    file_size_bytes=file_size_bytes,
                    elapsed_ms=elapsed_ms,
                    metadata={
                        "error": "FILE_TOO_LARGE",
                        "max_size_mb": MAX_FILE_SIZE_MB,
                        "operation_time_ms": elapsed_ms
                    }
                ).dict()
            
            # Save to file if requested
            if save_to_file and file_path:
                try:
                    with open(file_path, 'wb') as f:
                        f.write(screenshot_bytes)
                    logger.info("Screenshot saved to file", file_path=file_path, size_bytes=file_size_bytes)
                except Exception as e:
                    logger.error("Failed to save screenshot file", file_path=file_path, error=str(e))
                    file_path = None  # Clear file path on save failure
            
            # Encode to base64 if requested
            screenshot_base64 = None
            if store_base64:
                try:
                    screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
                except Exception as e:
                    logger.error("Failed to encode screenshot to base64", error=str(e))
            
            # Try to get image dimensions (best effort)
            dimensions = None
            try:
                if format == "png":
                    # Simple PNG dimension extraction
                    if len(screenshot_bytes) >= 24:
                        width = int.from_bytes(screenshot_bytes[16:20], 'big')
                        height = int.from_bytes(screenshot_bytes[20:24], 'big')
                        dimensions = {"width": width, "height": height}
            except Exception:
                pass  # Dimensions are optional
            
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            
            logger.info(
                "Screenshot captured successfully",
                session_id=session_id,
                element_selector=element_selector,
                full_page=full_page,
                format=format,
                file_size_bytes=file_size_bytes,
                dimensions=dimensions,
                elapsed_ms=elapsed_ms
            )
            
            return TakeScreenshotResponse(
                success=True,
                message="Screenshot captured successfully",
                screenshot_base64=screenshot_base64,
                file_path=file_path,
                filename=filename,
                format=format,
                file_size_bytes=file_size_bytes,
                dimensions=dimensions,
                element_selector=element_selector,
                elapsed_ms=elapsed_ms,
                metadata={
                    "full_page": full_page,
                    "operation_time_ms": elapsed_ms,
                    "page_url": page_url,
                    "page_title": page_title,
                    "base64_included": store_base64,
                    "file_saved": save_to_file and file_path is not None
                }
            ).dict()
            
        except PlaywrightError as e:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Screenshot capture failed", session_id=session_id, error=str(e))
            return TakeScreenshotResponse(
                success=False,
                message=f"Failed to capture screenshot: {str(e)}",
                element_selector=element_selector,
                format=format,
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "SCREENSHOT_FAILED",
                    "error_details": str(e),
                    "operation_time_ms": elapsed_ms,
                    "full_page": full_page
                }
            ).dict()
    
    except Exception as e:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        logger.error("Unexpected error in screenshot operation", session_id=session_id, error=str(e))
        return TakeScreenshotResponse(
            success=False,
            message=f"Unexpected error during screenshot capture: {str(e)}",
            format=format or "png",
            elapsed_ms=elapsed_ms,
            metadata={
                "error": "UNEXPECTED_ERROR",
                "error_details": str(e),
                "operation_time_ms": elapsed_ms
            }
        ).dict()


@mcp_server.prompt()
def take_screenshot_prompt(element_selector: Optional[str] = None, full_page: bool = False) -> str:
    """
    Generate guidance for capturing screenshots of pages or elements.
    
    Args:
        element_selector: CSS selector of specific element (optional)
        full_page: Whether to capture full page (optional)
    
    Returns:
        Formatted prompt with screenshot guidance
    """
    prompt = f"""
# Take Screenshot Tool Usage Guide

## Purpose
Capture screenshots of web pages or specific elements for visual validation and documentation.

## Screenshot Types

### Full Page Screenshot
```python
await take_screenshot(
    session_id="your_session_id",
    full_page=True,
    format="png",
    store_base64=True,
    save_to_file=True
)
```

### Element Screenshot
```python
await take_screenshot(
    session_id="your_session_id",
    element_selector="{element_selector or '#target-element'}",
    format="png",
    store_base64=True
)
```

### Viewport Screenshot (Default)
```python
await take_screenshot(
    session_id="your_session_id",
    format="png",
    store_base64=True
)
```

## Parameters
- **session_id**: Active browser session ID
- **element_selector**: CSS selector for specific element (optional)
- **full_page**: Capture full scrollable page (default: False)
- **format**: Image format - 'png', 'jpeg', 'jpg' (default: 'png')
- **quality**: JPEG quality 1-100 (default: 90, ignored for PNG)
- **timeout_ms**: Element wait timeout (default: 5000ms)
- **store_base64**: Include base64 in response (default: True)
- **save_to_file**: Save to file system (default: False)
- **filename**: Custom filename (optional, auto-generated if not provided)

## Format Options

### PNG (Lossless)
```python
await take_screenshot(
    session_id="your_session_id",
    format="png",
    store_base64=True
)
```

### JPEG (Compressed)
```python
await take_screenshot(
    session_id="your_session_id",
    format="jpeg",
    quality=85,  # 1-100
    store_base64=True
)
```

## Storage Options

### Base64 Response Only
```python
result = await take_screenshot(
    session_id="your_session_id",
    store_base64=True,
    save_to_file=False
)
# Access via result["screenshot_base64"]
```

### File System Storage
```python
await take_screenshot(
    session_id="your_session_id",
    save_to_file=True,
    filename="my_screenshot.png",
    store_base64=False  # Saves space in response
)
```

## Best Practices
1. Use PNG for pixel-perfect captures (e.g., UI testing)
2. Use JPEG for general documentation (smaller file size)
3. Use element screenshots for focused validation
4. Use full_page for complete page documentation
5. Set appropriate quality for JPEG (80-95 for most cases)
6. Consider file size limits for base64 responses

## Common Use Cases
- Visual regression testing
- UI component documentation
- Bug report screenshots  
- Test evidence capture
- Page layout validation
- Element visibility verification

## Response Data
The tool returns:
- **screenshot_base64**: Base64 encoded image data
- **file_path**: Path to saved file (if applicable)
- **dimensions**: Image width/height
- **file_size_bytes**: Screenshot size
- **metadata**: Additional capture information

## Error Handling
The tool provides comprehensive error handling for:
- Session not found
- Element not found or not visible
- Page not active
- File size limits exceeded
- File system errors
- Image encoding failures
"""
    return prompt 
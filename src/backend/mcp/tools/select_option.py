"""
Select Option Tool for IntelliBrowse MCP Server.

This module provides tools for selecting option(s) in dropdown/select elements within 
Playwright browser sessions, enabling automated form interactions and data selection workflows.
"""

import time
from typing import Dict, Any, Optional, List, Union
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
    from schemas.tools.select_option_schemas import SelectOptionRequest, SelectOptionResponse
except ImportError:
    # Fallback for when running directly from mcp directory
    from schemas.tools.select_option_schemas import SelectOptionRequest, SelectOptionResponse

# Import browser session utilities - use absolute import
try:
    from tools.browser_session import browser_sessions
except ImportError:
    # Fallback for when running directly from mcp directory
    from tools.browser_session import browser_sessions

logger = structlog.get_logger("intellibrowse.mcp.tools.select_option")


@mcp_server.tool()
async def select_option(
    session_id: str,
    selector: str,
    value: Optional[Union[str, List[str]]] = None,
    label: Optional[Union[str, List[str]]] = None,
    index: Optional[Union[int, List[int]]] = None,
    timeout_ms: Optional[int] = 5000,
    multiple: Optional[bool] = False
) -> Dict[str, Any]:
    """
    Select option(s) in dropdown/select elements in the current browser context.
    
    This tool handles option selection in HTML select elements within an active Playwright 
    browser session, supporting single and multiple selections with comprehensive validation
    and error handling for automated form interaction workflows.
    
    Args:
        session_id: Active Playwright session identifier
        selector: CSS selector of the select element
        value: Option value(s) to select (string or list of strings)
        label: Option label/text(s) to select (string or list of strings)
        index: Option index(es) to select - 0-based (integer or list of integers)
        timeout_ms: Timeout in milliseconds for element availability (default: 5000)
        multiple: Allow multiple selections (default: False)
    
    Returns:
        Dict containing selection operation status, selected options, and metadata
    """
    start_time = time.monotonic()
    
    logger.info(
        "Starting select option operation",
        session_id=session_id,
        selector=selector,
        value=value,
        label=label,
        index=index,
        timeout_ms=timeout_ms,
        multiple=multiple
    )
    
    try:
        # Validate request using Pydantic schema
        request = SelectOptionRequest(
            session_id=session_id,
            selector=selector,
            value=value,
            label=label,
            index=index,
            timeout_ms=timeout_ms,
            multiple=multiple
        )
        
        # Validate that at least one selection criterion is provided
        if not any([value, label, index]):
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("No selection criteria provided")
            return SelectOptionResponse(
                success=False,
                selector=selector,
                message="At least one selection criterion (value, label, or index) must be provided",
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "NO_SELECTION_CRITERIA",
                    "operation_time_ms": elapsed_ms
                }
            ).dict()
        
        # Check if session exists
        if session_id not in browser_sessions:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Session not found", session_id=session_id)
            return SelectOptionResponse(
                success=False,
                selector=selector,
                message=f"Browser session {session_id} not found",
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
            await page.title()  # Simple check to ensure page is responsive
        except PlaywrightError as e:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Page is not active", session_id=session_id, error=str(e))
            return SelectOptionResponse(
                success=False,
                selector=selector,
                message=f"Page is not active or accessible: {str(e)}",
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "PAGE_NOT_ACTIVE",
                    "error_details": str(e),
                    "operation_time_ms": elapsed_ms
                }
            ).dict()
        
        # Wait for select element to be available and visible
        try:
            logger.info("Waiting for select element to be visible", selector=selector, timeout_ms=timeout_ms)
            await page.wait_for_selector(
                selector, 
                timeout=timeout_ms, 
                state="visible"
            )
        except PlaywrightTimeoutError:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.warning("Select element not found or not visible", session_id=session_id, selector=selector, timeout_ms=timeout_ms)
            return SelectOptionResponse(
                success=False,
                selector=selector,
                message=f"Select element '{selector}' not found or not visible after {timeout_ms} ms",
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "ELEMENT_NOT_VISIBLE",
                    "timeout_ms": timeout_ms,
                    "operation_time_ms": elapsed_ms,
                    "page_url": page.url,
                    "page_title": await page.title() if page else "Unknown"
                }
            ).dict()
        except PlaywrightError as e:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Select element wait failed", session_id=session_id, selector=selector, error=str(e))
            return SelectOptionResponse(
                success=False,
                selector=selector,
                message=f"Failed to wait for select element '{selector}': {str(e)}",
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "ELEMENT_WAIT_FAILED",
                    "error_details": str(e),
                    "operation_time_ms": elapsed_ms
                }
            ).dict()
        
        # Verify element is actually a select element
        try:
            element_tag = await page.locator(selector).get_attribute("tagName")
            if element_tag and element_tag.upper() != "SELECT":
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                logger.error("Element is not a select element", selector=selector, tag_name=element_tag)
                return SelectOptionResponse(
                    success=False,
                    selector=selector,
                    message=f"Element '{selector}' is not a select element (found: {element_tag})",
                    elapsed_ms=elapsed_ms,
                    metadata={
                        "error": "NOT_SELECT_ELEMENT",
                        "actual_tag": element_tag,
                        "operation_time_ms": elapsed_ms
                    }
                ).dict()
        except PlaywrightError as e:
            logger.warning("Could not verify element tag", selector=selector, error=str(e))
        
        # Check if multiple selection is allowed
        try:
            is_multiple = await page.locator(selector).get_attribute("multiple") is not None
            if multiple and not is_multiple:
                logger.warning("Multiple selection requested but element doesn't support it", selector=selector)
        except PlaywrightError:
            is_multiple = False
        
        # Get all available options for metadata
        options_metadata = {}
        try:
            options = await page.locator(f"{selector} option").all()
            options_metadata["total_options"] = len(options)
            options_metadata["multiple_allowed"] = is_multiple
        except PlaywrightError:
            options_metadata["total_options"] = 0
            options_metadata["multiple_allowed"] = False
        
        # Perform the selection operation
        selected_values = []
        selected_labels = []
        selected_indices = []
        
        try:
            logger.info("Performing option selection", selector=selector)
            
            # Build selection options for Playwright
            selection_options = []
            
            # Handle value-based selection
            if value is not None:
                values_list = value if isinstance(value, list) else [value]
                for val in values_list:
                    selection_options.append({"value": str(val)})
            
            # Handle label-based selection
            elif label is not None:
                labels_list = label if isinstance(label, list) else [label]
                for lbl in labels_list:
                    selection_options.append({"label": str(lbl)})
            
            # Handle index-based selection
            elif index is not None:
                indices_list = index if isinstance(index, list) else [index]
                for idx in indices_list:
                    selection_options.append({"index": int(idx)})
            
            # Perform the actual selection
            await page.select_option(selector, selection_options)
            
            # Get the actual selected values for response
            try:
                selected_option_elements = await page.locator(f"{selector} option:checked").all()
                for option_element in selected_option_elements:
                    option_value = await option_element.get_attribute("value")
                    option_text = await option_element.text_content()
                    option_index = await option_element.evaluate("el => Array.from(el.parentNode.children).indexOf(el)")
                    
                    if option_value:
                        selected_values.append(option_value)
                    if option_text:
                        selected_labels.append(option_text.strip())
                    if option_index >= 0:
                        selected_indices.append(option_index)
            except PlaywrightError as e:
                logger.warning("Could not retrieve selected option details", error=str(e))
            
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            
            logger.info(
                "Option selection completed successfully",
                session_id=session_id,
                selector=selector,
                selected_values=selected_values,
                selected_labels=selected_labels,
                selected_indices=selected_indices,
                elapsed_ms=elapsed_ms
            )
            
            return SelectOptionResponse(
                success=True,
                selector=selector,
                message=f"Successfully selected {len(selected_values)} option(s)",
                selected_values=selected_values,
                selected_labels=selected_labels,
                selected_indices=selected_indices,
                elapsed_ms=elapsed_ms,
                metadata={
                    "element_visible": True,
                    "operation_time_ms": elapsed_ms,
                    **options_metadata,
                    "page_url": page.url,
                    "page_title": await page.title() if page else "Unknown"
                }
            ).dict()
            
        except PlaywrightError as e:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Option selection failed", session_id=session_id, selector=selector, error=str(e))
            return SelectOptionResponse(
                success=False,
                selector=selector,
                message=f"Failed to select option in '{selector}': {str(e)}",
                elapsed_ms=elapsed_ms,
                metadata={
                    "error": "SELECTION_FAILED",
                    "error_details": str(e),
                    "operation_time_ms": elapsed_ms,
                    **options_metadata
                }
            ).dict()
    
    except Exception as e:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        logger.error("Unexpected error in select option operation", session_id=session_id, selector=selector, error=str(e))
        return SelectOptionResponse(
            success=False,
            selector=selector,
            message=f"Unexpected error during option selection: {str(e)}",
            elapsed_ms=elapsed_ms,
            metadata={
                "error": "UNEXPECTED_ERROR",
                "error_details": str(e),
                "operation_time_ms": elapsed_ms
            }
        ).dict()


@mcp_server.prompt()
def select_option_prompt(selector: str, value: Optional[str] = None, label: Optional[str] = None) -> str:
    """
    Generate guidance for selecting options in dropdown/select elements.
    
    Args:
        selector: CSS selector of the select element
        value: Option value to select (optional)
        label: Option label to select (optional)
    
    Returns:
        Formatted prompt with selection guidance
    """
    prompt = f"""
# Select Option Tool Usage Guide

## Purpose
Select option(s) in dropdown/select elements for automated form interactions.

## Target Element
**Selector**: `{selector}`

## Selection Methods
You can select options using any of these methods:

### By Value
```python
await select_option(
    session_id="your_session_id",
    selector="{selector}",
    value="{value or 'option_value'}"
)
```

### By Label/Text
```python
await select_option(
    session_id="your_session_id",
    selector="{selector}",
    label="{label or 'Option Text'}"
)
```

### By Index (0-based)
```python
await select_option(
    session_id="your_session_id",
    selector="{selector}",
    index=0  # First option
)
```

### Multiple Selection
For multi-select elements:
```python
await select_option(
    session_id="your_session_id",
    selector="{selector}",
    value=["value1", "value2"],
    multiple=True
)
```

## Parameters
- **session_id**: Active browser session ID
- **selector**: CSS selector of the select element
- **value**: Option value(s) to select
- **label**: Option label/text(s) to select  
- **index**: Option index(es) to select (0-based)
- **timeout_ms**: Wait timeout (default: 5000ms)
- **multiple**: Enable multiple selections (default: False)

## Best Practices
1. Use specific CSS selectors to target the correct select element
2. Prefer value-based selection for consistency
3. Use label-based selection for user-friendly option identification
4. Check if the select element supports multiple selection before using multiple=True
5. Always handle the response to verify successful selection

## Common Use Cases
- Country/region selection in forms
- Category filtering in e-commerce
- Date/time selection dropdowns
- Multi-select tag/category selection
- Configuration option selection

## Error Handling  
The tool provides comprehensive error handling for:
- Session not found
- Element not found or not visible
- Invalid element type (not a select)
- Selection operation failures
- Multiple selection on single-select elements
"""
    return prompt 
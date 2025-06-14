"""
DOM Resource Provider - Page Structure and Element Context

This resource provider exposes DOM snapshots, page structure information,
and element context data for LLM analysis and tool operations.
"""

import sys
from pathlib import Path
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
import json
import asyncio
from datetime import datetime

# Add the MCP server root to Python path
sys.path.append(str(Path(__file__).parent.parent))

from main import mcp_server
from schemas.context_schemas import SessionContext
import structlog

logger = structlog.get_logger("intellibrowse.mcp.resources.dom")


class DOMSnapshot(BaseModel):
    """DOM snapshot data structure."""
    
    page_url: str = Field(description="URL of the page")
    title: str = Field(description="Page title")
    timestamp: datetime = Field(description="When the snapshot was taken")
    html_content: str = Field(description="HTML content of the page")
    viewport_size: Dict[str, int] = Field(description="Viewport dimensions")
    scroll_position: Dict[str, int] = Field(description="Current scroll position")
    interactive_elements: List[Dict[str, Any]] = Field(description="List of interactive elements")
    form_data: List[Dict[str, Any]] = Field(description="Form elements and their state")
    metadata: Dict[str, Any] = Field(description="Additional page metadata")


class DOMResourceProvider:
    """Provider for DOM-related resources."""
    
    @staticmethod
    async def get_dom_snapshot(page_id: str) -> DOMSnapshot:
        """
        Retrieve DOM snapshot for a specific page.
        
        Args:
            page_id: Unique identifier for the page/session
            
        Returns:
            DOMSnapshot with complete page structure information
        """
        logger.info("Retrieving DOM snapshot", page_id=page_id)
        
        try:
            # In a real implementation, this would:
            # 1. Connect to the browser session
            # 2. Extract DOM content via Playwright/Selenium
            # 3. Analyze interactive elements
            # 4. Capture current state
            
            # Placeholder implementation with sample data
            snapshot = DOMSnapshot(
                page_url=f"https://example.com/page/{page_id}",
                title=f"Test Page {page_id}",
                timestamp=datetime.now(),
                html_content=DOMResourceProvider._get_sample_dom_content(page_id),
                viewport_size={"width": 1920, "height": 1080},
                scroll_position={"x": 0, "y": 0},
                interactive_elements=DOMResourceProvider._extract_interactive_elements(page_id),
                form_data=DOMResourceProvider._extract_form_data(page_id),
                metadata={
                    "page_load_time": 1.23,
                    "dom_size": 15642,
                    "element_count": 284,
                    "javascript_errors": [],
                    "performance_metrics": {
                        "first_contentful_paint": 0.8,
                        "largest_contentful_paint": 1.1,
                        "cumulative_layout_shift": 0.02
                    }
                }
            )
            
            logger.info("DOM snapshot retrieved successfully", 
                       page_id=page_id,
                       element_count=len(snapshot.interactive_elements))
            
            return snapshot
            
        except Exception as e:
            logger.error("Error retrieving DOM snapshot", 
                        page_id=page_id, 
                        error=str(e))
            raise
    
    @staticmethod
    def _get_sample_dom_content(page_id: str) -> str:
        """Generate sample DOM content for testing."""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Page {page_id}</title>
</head>
<body>
    <header id="header" class="main-header">
        <nav class="navbar">
            <div class="nav-brand">IntelliBrowse Test</div>
            <ul class="nav-menu">
                <li><a href="#home" data-test-id="nav-home">Home</a></li>
                <li><a href="#about" data-test-id="nav-about">About</a></li>
                <li><a href="#contact" data-test-id="nav-contact">Contact</a></li>
            </ul>
        </nav>
    </header>
    
    <main id="main-content">
        <section class="hero-section">
            <h1 id="page-title">Welcome to Test Page {page_id}</h1>
            <p class="hero-description">This is a sample page for testing automation.</p>
        </section>
        
        <section class="form-section">
            <h2>Sample Form</h2>
            <form id="test-form" action="/submit" method="post">
                <div class="form-group">
                    <label for="username">Username:</label>
                    <input type="text" id="username" name="username" data-test-id="input-username" required>
                </div>
                
                <div class="form-group">
                    <label for="email">Email:</label>
                    <input type="email" id="email" name="email" data-test-id="input-email" required>
                </div>
                
                <div class="form-group">
                    <label for="country">Country:</label>
                    <select id="country" name="country" data-test-id="select-country">
                        <option value="">Select Country</option>
                        <option value="us">United States</option>
                        <option value="uk">United Kingdom</option>
                        <option value="ca">Canada</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label>
                        <input type="checkbox" id="terms" name="terms" data-test-id="checkbox-terms">
                        I agree to the terms and conditions
                    </label>
                </div>
                
                <div class="form-actions">
                    <button type="submit" id="submit-btn" class="btn btn-primary" data-test-id="btn-submit">
                        Submit
                    </button>
                    <button type="reset" id="reset-btn" class="btn btn-secondary" data-test-id="btn-reset">
                        Reset
                    </button>
                </div>
            </form>
        </section>
        
        <section class="content-section">
            <h2>Dynamic Content</h2>
            <div id="dynamic-content" class="loading" data-test-id="dynamic-content">
                Loading...
            </div>
            <button id="load-content" class="btn btn-outline" data-test-id="btn-load-content">
                Load Content
            </button>
        </section>
    </main>
    
    <footer id="footer" class="main-footer">
        <p>&copy; 2024 IntelliBrowse Test Suite</p>
    </footer>
</body>
</html>"""
    
    @staticmethod
    def _extract_interactive_elements(page_id: str) -> List[Dict[str, Any]]:
        """Extract interactive elements from the page."""
        return [
            {
                "id": "nav-home",
                "tag": "a",
                "type": "link",
                "selector": "[data-test-id='nav-home']",
                "text": "Home",
                "href": "#home",
                "visible": True,
                "enabled": True,
                "attributes": {
                    "href": "#home",
                    "data-test-id": "nav-home"
                }
            },
            {
                "id": "username",
                "tag": "input",
                "type": "text",
                "selector": "#username",
                "label": "Username",
                "required": True,
                "visible": True,
                "enabled": True,
                "value": "",
                "attributes": {
                    "type": "text",
                    "name": "username",
                    "data-test-id": "input-username",
                    "required": True
                }
            },
            {
                "id": "email",
                "tag": "input",
                "type": "email",
                "selector": "#email",
                "label": "Email",
                "required": True,
                "visible": True,
                "enabled": True,
                "value": "",
                "attributes": {
                    "type": "email",
                    "name": "email",
                    "data-test-id": "input-email",
                    "required": True
                }
            },
            {
                "id": "country",
                "tag": "select",
                "type": "select",
                "selector": "#country",
                "label": "Country",
                "visible": True,
                "enabled": True,
                "value": "",
                "options": [
                    {"value": "", "text": "Select Country"},
                    {"value": "us", "text": "United States"},
                    {"value": "uk", "text": "United Kingdom"},
                    {"value": "ca", "text": "Canada"}
                ],
                "attributes": {
                    "name": "country",
                    "data-test-id": "select-country"
                }
            },
            {
                "id": "terms",
                "tag": "input",
                "type": "checkbox",
                "selector": "#terms",
                "label": "I agree to the terms and conditions",
                "visible": True,
                "enabled": True,
                "checked": False,
                "attributes": {
                    "type": "checkbox",
                    "name": "terms",
                    "data-test-id": "checkbox-terms"
                }
            },
            {
                "id": "submit-btn",
                "tag": "button",
                "type": "submit",
                "selector": "#submit-btn",
                "text": "Submit",
                "visible": True,
                "enabled": True,
                "attributes": {
                    "type": "submit",
                    "class": "btn btn-primary",
                    "data-test-id": "btn-submit"
                }
            },
            {
                "id": "load-content",
                "tag": "button",
                "type": "button",
                "selector": "#load-content",
                "text": "Load Content",
                "visible": True,
                "enabled": True,
                "attributes": {
                    "class": "btn btn-outline",
                    "data-test-id": "btn-load-content"
                }
            }
        ]
    
    @staticmethod
    def _extract_form_data(page_id: str) -> List[Dict[str, Any]]:
        """Extract form elements and their current state."""
        return [
            {
                "form_id": "test-form",
                "action": "/submit",
                "method": "post",
                "fields": [
                    {
                        "name": "username",
                        "type": "text",
                        "value": "",
                        "required": True,
                        "validation_state": "neutral"
                    },
                    {
                        "name": "email",
                        "type": "email",
                        "value": "",
                        "required": True,
                        "validation_state": "neutral"
                    },
                    {
                        "name": "country",
                        "type": "select",
                        "value": "",
                        "required": False,
                        "validation_state": "neutral"
                    },
                    {
                        "name": "terms",
                        "type": "checkbox",
                        "checked": False,
                        "required": False,
                        "validation_state": "neutral"
                    }
                ],
                "submit_enabled": True,
                "validation_errors": []
            }
        ]


@mcp_server.resource("dom://{page_id}")
async def get_dom_snapshot_resource(page_id: str) -> str:
    """
    MCP Resource: Get DOM snapshot for a specific page.
    
    This resource provides complete DOM structure information including
    interactive elements, form state, and page metadata for LLM analysis.
    
    Args:
        page_id: Unique identifier for the page/session
        
    Returns:
        JSON string containing DOM snapshot data
    """
    logger.info("DOM resource requested", page_id=page_id)
    
    try:
        # Get DOM snapshot
        snapshot = await DOMResourceProvider.get_dom_snapshot(page_id)
        
        # Convert to JSON for MCP resource response
        resource_data = {
            "resource_type": "dom_snapshot",
            "page_id": page_id,
            "timestamp": snapshot.timestamp.isoformat(),
            "data": snapshot.dict()
        }
        
        logger.info("DOM resource provided successfully", page_id=page_id)
        return json.dumps(resource_data, indent=2)
        
    except Exception as e:
        logger.error("Error providing DOM resource", 
                    page_id=page_id, 
                    error=str(e))
        
        # Return error response
        error_response = {
            "resource_type": "dom_snapshot",
            "page_id": page_id,
            "error": f"Failed to retrieve DOM snapshot: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }
        return json.dumps(error_response, indent=2)


@mcp_server.resource("dom://elements/{page_id}")
async def get_interactive_elements_resource(page_id: str) -> str:
    """
    MCP Resource: Get interactive elements for a specific page.
    
    This resource provides a focused view of interactive elements
    that can be targeted for automation actions.
    
    Args:
        page_id: Unique identifier for the page/session
        
    Returns:
        JSON string containing interactive elements data
    """
    logger.info("Interactive elements resource requested", page_id=page_id)
    
    try:
        # Get DOM snapshot
        snapshot = await DOMResourceProvider.get_dom_snapshot(page_id)
        
        # Extract only interactive elements
        resource_data = {
            "resource_type": "interactive_elements",
            "page_id": page_id,
            "page_url": snapshot.page_url,
            "timestamp": snapshot.timestamp.isoformat(),
            "elements": snapshot.interactive_elements,
            "summary": {
                "total_elements": len(snapshot.interactive_elements),
                "by_type": {}
            }
        }
        
        # Calculate element type summary
        type_counts = {}
        for element in snapshot.interactive_elements:
            elem_type = element.get("type", "unknown")
            type_counts[elem_type] = type_counts.get(elem_type, 0) + 1
        resource_data["summary"]["by_type"] = type_counts
        
        logger.info("Interactive elements resource provided successfully", 
                   page_id=page_id,
                   element_count=len(snapshot.interactive_elements))
        
        return json.dumps(resource_data, indent=2)
        
    except Exception as e:
        logger.error("Error providing interactive elements resource", 
                    page_id=page_id, 
                    error=str(e))
        
        # Return error response
        error_response = {
            "resource_type": "interactive_elements",
            "page_id": page_id,
            "error": f"Failed to retrieve interactive elements: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }
        return json.dumps(error_response, indent=2)


@mcp_server.resource("dom://forms/{page_id}")
async def get_form_data_resource(page_id: str) -> str:
    """
    MCP Resource: Get form data and state for a specific page.
    
    This resource provides detailed information about forms,
    their fields, current state, and validation status.
    
    Args:
        page_id: Unique identifier for the page/session
        
    Returns:
        JSON string containing form data and state
    """
    logger.info("Form data resource requested", page_id=page_id)
    
    try:
        # Get DOM snapshot
        snapshot = await DOMResourceProvider.get_dom_snapshot(page_id)
        
        # Extract form data
        resource_data = {
            "resource_type": "form_data",
            "page_id": page_id,
            "page_url": snapshot.page_url,
            "timestamp": snapshot.timestamp.isoformat(),
            "forms": snapshot.form_data,
            "summary": {
                "total_forms": len(snapshot.form_data),
                "total_fields": sum(len(form.get("fields", [])) for form in snapshot.form_data),
                "forms_with_errors": sum(1 for form in snapshot.form_data 
                                       if form.get("validation_errors", []))
            }
        }
        
        logger.info("Form data resource provided successfully", 
                   page_id=page_id,
                   form_count=len(snapshot.form_data))
        
        return json.dumps(resource_data, indent=2)
        
    except Exception as e:
        logger.error("Error providing form data resource", 
                    page_id=page_id, 
                    error=str(e))
        
        # Return error response
        error_response = {
            "resource_type": "form_data",
            "page_id": page_id,
            "error": f"Failed to retrieve form data: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }
        return json.dumps(error_response, indent=2) 
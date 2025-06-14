"""
Get Page DOM Tool Schemas

Schemas for the DOM extraction tool that retrieves HTML content
from browser sessions with optional element targeting and size limits.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class GetPageDomRequest(BaseModel):
    """Request schema for getting page DOM content."""
    
    session_id: str = Field(description="Active Playwright session ID")
    selector: Optional[str] = Field(default=None, description="Optional CSS selector to target a specific element")
    outer_html: Optional[bool] = Field(default=False, description="Return outerHTML (default: innerHTML) if selector is specified")
    max_length: Optional[int] = Field(default=100_000, description="Maximum HTML content length to return (truncate if exceeded)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_12345",
                "selector": ".main-content",
                "outer_html": True,
                "max_length": 50000
            }
        }


class GetPageDomResponse(BaseModel):
    """Response schema for page DOM content retrieval."""
    
    html_content: str = Field(description="The requested DOM content")
    truncated: bool = Field(default=False, description="True if output was truncated to max_length")
    selector_used: Optional[str] = Field(default=None, description="Selector used for DOM extraction, if any")
    message: str = Field(description="Status or result message")
    content_length: int = Field(description="Length of the HTML content returned")
    metadata: Dict[str, Any] = Field(default={}, description="Additional DOM extraction metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "html_content": "<div class='main-content'><h1>Welcome</h1><p>Content here...</p></div>",
                "truncated": False,
                "selector_used": ".main-content",
                "message": "DOM content extracted successfully",
                "content_length": 1250,
                "metadata": {
                    "extraction_time": 0.15,
                    "element_count": 45,
                    "document_ready_state": "complete"
                }
            }
        } 
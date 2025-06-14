"""
Open Browser Tool Schemas

Schemas for the browser session initialization tool that creates new
Playwright browser sessions with configurable options.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class OpenBrowserRequest(BaseModel):
    """Request schema for opening a new browser session."""
    
    headless: bool = Field(default=True, description="Open browser in headless mode")
    browser_type: str = Field(default="chromium", description="Browser type (chromium, firefox, webkit)")
    viewport_width: int = Field(default=1920, description="Viewport width in pixels")
    viewport_height: int = Field(default=1080, description="Viewport height in pixels")
    user_agent: Optional[str] = Field(default=None, description="Custom user agent string")
    extra_http_headers: Optional[Dict[str, str]] = Field(default=None, description="Extra HTTP headers")
    
    class Config:
        json_schema_extra = {
            "example": {
                "headless": True,
                "browser_type": "chromium",
                "viewport_width": 1920,
                "viewport_height": 1080,
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "extra_http_headers": {"Accept-Language": "en-US,en;q=0.9"}
            }
        }


class OpenBrowserResponse(BaseModel):
    """Response schema for opening a new browser session."""
    
    session_id: str = Field(description="Unique browser session identifier")
    browser_type: str = Field(description="Browser type that was launched")
    headless: bool = Field(description="Whether browser was launched in headless mode")
    viewport: Dict[str, int] = Field(description="Viewport dimensions")
    message: str = Field(description="Success message")
    metadata: Dict[str, Any] = Field(default={}, description="Additional session metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_12345",
                "browser_type": "chromium",
                "headless": True,
                "viewport": {"width": 1920, "height": 1080},
                "message": "Browser session opened successfully",
                "metadata": {
                    "created_at": "2024-01-08T10:00:00Z",
                    "user_agent": "Mozilla/5.0...",
                    "version": "chromium/120.0.0.0"
                }
            }
        } 
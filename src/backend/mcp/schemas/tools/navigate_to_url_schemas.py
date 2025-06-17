"""
Navigate to URL Tool Schemas.

Pydantic schemas for navigating to a URL within a browser session request and response validation.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class NavigateToUrlRequest(BaseModel):
    """Request schema for navigating to a URL within a browser session."""
    
    session_id: str = Field(description="Browser session ID")
    url: str = Field(description="Destination URL to navigate to")
    timeout_ms: Optional[int] = Field(default=10000, description="Navigation timeout in milliseconds")
    wait_until: str = Field(default="domcontentloaded", description="When to consider navigation succeeded (load, domcontentloaded, networkidle)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_12345",
                "url": "https://example.com/login",
                "timeout_ms": 10000,
                "wait_until": "domcontentloaded"
            }
        }


class NavigateToUrlResponse(BaseModel):
    """Response schema for URL navigation."""
    
    navigated: bool = Field(description="Whether navigation was successful")
    http_status: Optional[int] = Field(description="HTTP response status code")
    final_url: str = Field(description="Final URL after navigation (may differ due to redirects)")
    message: str = Field(description="Navigation status message")
    elapsed_ms: int = Field(description="Time taken for navigation in milliseconds")
    metadata: Dict[str, Any] = Field(default={}, description="Additional navigation metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "navigated": True,
                "http_status": 200,
                "final_url": "https://example.com/login",
                "message": "Navigation completed successfully",
                "elapsed_ms": 1250,
                "metadata": {
                    "redirects": 0,
                    "load_time": 1.25,
                    "dom_ready": True
                }
            }
        } 
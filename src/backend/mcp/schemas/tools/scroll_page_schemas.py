"""
Scroll Page Tool Schemas

Schemas for the page scrolling tool that performs scroll operations
with directional control, element targeting, and smooth scrolling options.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class ScrollPageRequest(BaseModel):
    """Request schema for scroll page operation."""
    
    session_id: str = Field(description="Active Playwright session ID")
    direction: Optional[str] = Field(default=None, description="Direction to scroll: 'up', 'down', 'left', 'right', 'top', 'bottom'")
    pixels: Optional[int] = Field(default=None, description="Number of pixels to scroll (positive or negative)")
    selector: Optional[str] = Field(default=None, description="Optional CSS selector to scroll a specific element")
    to_element: Optional[bool] = Field(default=False, description="If true, scrolls to the element specified by selector")
    timeout_ms: Optional[int] = Field(default=5000, description="Timeout in milliseconds for element availability")
    smooth: Optional[bool] = Field(default=False, description="Whether to use smooth scrolling animation")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_12345",
                "direction": "down",
                "pixels": 500,
                "selector": None,
                "to_element": False,
                "timeout_ms": 5000,
                "smooth": True
            }
        }


class ScrollPageResponse(BaseModel):
    """Response schema for scroll page operation."""
    
    success: bool = Field(description="Whether the scroll operation was successful")
    session_id: str = Field(description="Session ID where the scroll was performed")
    scroll_position: Dict[str, int] = Field(description="Final scroll position (x, y coordinates)")
    scrolled_element: Optional[str] = Field(default=None, description="Element that was scrolled (if selector was used)")
    scroll_type: str = Field(description="Type of scroll operation performed")
    message: str = Field(description="Status or error message")
    elapsed_ms: int = Field(description="Time taken for the scroll operation in milliseconds")
    metadata: Dict[str, Any] = Field(default={}, description="Additional scroll operation metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "session_id": "session_12345",
                "scroll_position": {"x": 0, "y": 750},
                "scrolled_element": None,
                "scroll_type": "directional_scroll",
                "message": "Scrolled down successfully",
                "elapsed_ms": 200,
                "metadata": {
                    "direction": "down",
                    "pixels_scrolled": 500,
                    "smooth_scroll": True,
                    "viewport_height": 1080
                }
            }
        } 
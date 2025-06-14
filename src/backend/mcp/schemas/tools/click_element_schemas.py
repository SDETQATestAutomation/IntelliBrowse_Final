"""
Click Element Tool Schemas

Schemas for the element clicking tool that performs various types of clicks
on DOM elements with configurable timing and force options.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class ClickElementRequest(BaseModel):
    """Request schema for clicking a DOM element."""
    
    session_id: str = Field(description="Active Playwright session ID")
    selector: str = Field(description="CSS selector of the element to click")
    timeout_ms: Optional[int] = Field(default=5000, description="Timeout in milliseconds for element availability")
    click_type: Optional[str] = Field(default="single", description="Type of click: 'single', 'double', 'right'")
    delay_ms: Optional[int] = Field(default=0, description="Delay after click in milliseconds")
    force: Optional[bool] = Field(default=False, description="Whether to force the click even if element is not actionable")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_12345",
                "selector": "#submit-btn",
                "timeout_ms": 5000,
                "click_type": "single",
                "delay_ms": 100,
                "force": False
            }
        }


class ClickElementResponse(BaseModel):
    """Response schema for element click operation."""
    
    success: bool = Field(description="Whether the click was performed successfully")
    selector: str = Field(description="Selector used for the click")
    message: str = Field(description="Status or error message")
    click_type: str = Field(description="Type of click that was performed")
    elapsed_ms: int = Field(description="Time taken for the click operation in milliseconds")
    metadata: Dict[str, Any] = Field(default={}, description="Additional click operation metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "selector": "#submit-btn",
                "message": "Element clicked successfully",
                "click_type": "single",
                "elapsed_ms": 250,
                "metadata": {
                    "element_visible": True,
                    "element_enabled": True,
                    "coordinates": {"x": 150, "y": 300}
                }
            }
        } 
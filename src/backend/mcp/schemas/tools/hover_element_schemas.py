"""
Hover Element Tool Schemas

Schemas for the element hovering tool that performs mouse hover operations
on DOM elements with position control, timing, and force options.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class HoverElementRequest(BaseModel):
    """Request schema for hovering over a DOM element."""
    
    session_id: str = Field(description="Active Playwright session ID")
    selector: str = Field(description="CSS selector of the element to hover over")
    timeout_ms: Optional[int] = Field(default=5000, description="Timeout in milliseconds for element availability")
    delay_ms: Optional[int] = Field(default=0, description="Delay after hover in milliseconds")
    force: Optional[bool] = Field(default=False, description="Whether to force the hover even if element is not actionable")
    position: Optional[Dict[str, float]] = Field(default=None, description="Optional position to hover within the element (x, y coordinates)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_12345",
                "selector": ".dropdown-trigger",
                "timeout_ms": 5000,
                "delay_ms": 200,
                "force": False,
                "position": {"x": 50, "y": 25}
            }
        }


class HoverElementResponse(BaseModel):
    """Response schema for element hover operation."""
    
    success: bool = Field(description="Whether the hover was performed successfully")
    selector: str = Field(description="Selector used for the hover")
    message: str = Field(description="Status or error message")
    hovered: bool = Field(description="Whether the hover operation was executed")
    position: Optional[Dict[str, float]] = Field(default=None, description="Position where hover was performed")
    elapsed_ms: int = Field(description="Time taken for the hover operation in milliseconds")
    metadata: Dict[str, Any] = Field(default={}, description="Additional hover operation metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "selector": ".dropdown-trigger",
                "message": "Element hovered successfully",
                "hovered": True,
                "position": {"x": 50, "y": 25},
                "elapsed_ms": 120,
                "metadata": {
                    "element_visible": True,
                    "hover_effect_triggered": True,
                    "dropdown_opened": True
                }
            }
        } 
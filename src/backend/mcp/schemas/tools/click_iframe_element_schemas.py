"""
Click IFrame Element Schemas for IntelliBrowse MCP Server.
Provides comprehensive Pydantic models for iframe element interactions with validation.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class ClickIFrameElementRequest(BaseModel):
    """Request schema for click_iframe_element tool."""
    
    session_id: str = Field(
        ..., 
        description="Active browser session ID",
        min_length=1
    )
    iframe_selector: str = Field(
        ..., 
        description="CSS selector for iframe element",
        min_length=1
    )
    element_selector: str = Field(
        ..., 
        description="CSS selector for element within iframe",
        min_length=1
    )
    click_type: Optional[str] = Field(
        "single", 
        description="Type of click to perform (single, double, right)"
    )
    timeout_ms: Optional[int] = Field(
        10000, 
        description="Element wait timeout in milliseconds",
        ge=1000,
        le=60000
    )
    wait_for_iframe: Optional[int] = Field(
        5000, 
        description="IFrame load timeout in milliseconds",
        ge=1000,
        le=30000
    )
    force: Optional[bool] = Field(
        False, 
        description="Force click even if element not actionable"
    )
    button: Optional[str] = Field(
        "left", 
        description="Mouse button to use (left, right, middle)"
    )
    click_count: Optional[int] = Field(
        1, 
        description="Number of clicks to perform",
        ge=1,
        le=10
    )

    @field_validator('click_type')


    @classmethod
    def validate_click_type(cls, v):
        """Validate click type parameter."""
        valid_types = ['single', 'double', 'right']
        if v not in valid_types:
            raise ValueError(f"click_type must be one of: {valid_types}")
        return v

    @field_validator('button')


    @classmethod
    def validate_button(cls, v):
        """Validate mouse button parameter."""
        valid_buttons = ['left', 'right', 'middle']
        if v not in valid_buttons:
            raise ValueError(f"button must be one of: {valid_buttons}")
        return v

    @field_validator('iframe_selector', 'element_selector')


    @classmethod
    def validate_selectors(cls, v):
        """Validate CSS selectors."""
        if v is not None and len(v.strip()) == 0:
            raise ValueError("Selector cannot be empty")
        return v

    class Config:
        """Pydantic config."""
        extra = "forbid"
        schema_extra = {
            "example": {
                "session_id": "session_123",
                "iframe_selector": "#content-frame",
                "element_selector": "button.submit",
                "click_type": "single",
                "timeout_ms": 10000,
                "wait_for_iframe": 5000,
                "force": False,
                "button": "left",
                "click_count": 1
            }
        }


class ClickIFrameElementResponse(BaseModel):
    """Response schema for click_iframe_element tool."""
    
    success: bool = Field(..., description="Whether click operation succeeded")
    message: str = Field(..., description="Operation result message")
    
    # IFrame details
    iframe_element: Optional[Dict[str, Any]] = Field(None, description="IFrame element details")
    iframe_loaded: Optional[bool] = Field(None, description="Whether iframe was loaded successfully")
    
    # Target element details
    target_element: Optional[Dict[str, Any]] = Field(None, description="Target element details")
    
    # Click operation details
    click_type: Optional[str] = Field(None, description="Type of click performed")
    button: Optional[str] = Field(None, description="Mouse button used")
    click_count: Optional[int] = Field(None, description="Number of clicks performed")
    click_position: Optional[Dict[str, int]] = Field(None, description="Click coordinates")
    
    # Operation metadata
    operation_time_ms: Optional[int] = Field(None, description="Total operation time")
    iframe_switch_time_ms: Optional[int] = Field(None, description="Time to switch to iframe context")
    
    # Session and timing
    session_id: str = Field(..., description="Browser session ID")
    timestamp: str = Field(..., description="Operation timestamp")
    
    # Error details (if any)
    error_type: Optional[str] = Field(None, description="Error type if operation failed")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Detailed error information")

    class Config:
        """Pydantic config."""
        extra = "forbid"
        schema_extra = {
            "example": {
                "success": True,
                "message": "Successfully clicked element within iframe",
                "iframe_element": {
                    "selector": "#content-frame",
                    "position": {"x": 50, "y": 100},
                    "size": {"width": 800, "height": 600},
                    "loaded": True
                },
                "iframe_loaded": True,
                "target_element": {
                    "selector": "button.submit",
                    "position": {"x": 150, "y": 200},
                    "size": {"width": 120, "height": 40},
                    "text": "Submit"
                },
                "click_type": "single",
                "button": "left",
                "click_count": 1,
                "click_position": {"x": 210, "y": 220},
                "operation_time_ms": 1500,
                "iframe_switch_time_ms": 300,
                "session_id": "session_123",
                "timestamp": "2024-01-18T12:00:00Z"
            }
        } 
"""
Drag Element Schemas for IntelliBrowse MCP Server.
Provides comprehensive Pydantic models for drag-and-drop operations with validation.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator


class DragElementRequest(BaseModel):
    """Request schema for drag_element tool."""
    
    session_id: str = Field(
        ..., 
        description="Active browser session ID",
        min_length=1
    )
    source_selector: str = Field(
        ..., 
        description="CSS selector for element to drag",
        min_length=1
    )
    target_selector: Optional[str] = Field(
        None, 
        description="CSS selector for target element (alternative to target_position)"
    )
    target_position: Optional[Dict[str, int]] = Field(
        None, 
        description="Target coordinates as {'x': 100, 'y': 200}"
    )
    steps: Optional[int] = Field(
        10, 
        description="Number of intermediate steps for smooth drag",
        ge=1,
        le=100
    )
    timeout_ms: Optional[int] = Field(
        10000, 
        description="Operation timeout in milliseconds",
        ge=1000,
        le=60000
    )
    force: Optional[bool] = Field(
        False, 
        description="Force drag even if element not actionable"
    )
    hover_before_drag: Optional[bool] = Field(
        True, 
        description="Hover over source element before dragging"
    )
    delay_between_steps: Optional[int] = Field(
        50, 
        description="Delay between drag steps in milliseconds",
        ge=0,
        le=1000
    )

    @field_validator('target_position')


    @classmethod
    def validate_target_position(cls, v):
        """Validate target position coordinates."""
        if v is not None:
            if not isinstance(v, dict):
                raise ValueError("target_position must be a dictionary")
            if 'x' not in v or 'y' not in v:
                raise ValueError("target_position must contain 'x' and 'y' keys")
            if not isinstance(v['x'], int) or not isinstance(v['y'], int):
                raise ValueError("target_position coordinates must be integers")
            if v['x'] < 0 or v['y'] < 0:
                raise ValueError("target_position coordinates must be non-negative")
        return v

    @field_validator('target_selector', 'source_selector')


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
                "source_selector": "#draggable-item",
                "target_selector": "#drop-zone",
                "steps": 15,
                "timeout_ms": 15000,
                "force": False,
                "hover_before_drag": True,
                "delay_between_steps": 100
            }
        }


class DragElementResponse(BaseModel):
    """Response schema for drag_element tool."""
    
    success: bool = Field(..., description="Whether drag operation succeeded")
    message: str = Field(..., description="Operation result message")
    
    # Drag operation details
    source_element: Optional[Dict[str, Any]] = Field(None, description="Source element details")
    target_element: Optional[Dict[str, Any]] = Field(None, description="Target element details")
    target_position: Optional[Dict[str, int]] = Field(None, description="Final target position")
    
    # Operation metadata
    drag_path: Optional[List[Dict[str, int]]] = Field(None, description="Drag path coordinates")
    operation_time_ms: Optional[int] = Field(None, description="Total drag operation time")
    steps_executed: Optional[int] = Field(None, description="Number of drag steps executed")
    
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
                "message": "Successfully dragged element from source to target",
                "source_element": {
                    "selector": "#draggable-item",
                    "position": {"x": 100, "y": 150},
                    "size": {"width": 80, "height": 60}
                },
                "target_element": {
                    "selector": "#drop-zone",
                    "position": {"x": 300, "y": 200},
                    "size": {"width": 120, "height": 100}
                },
                "target_position": {"x": 300, "y": 200},
                "drag_path": [
                    {"x": 100, "y": 150},
                    {"x": 150, "y": 170},
                    {"x": 200, "y": 180},
                    {"x": 250, "y": 190},
                    {"x": 300, "y": 200}
                ],
                "operation_time_ms": 1250,
                "steps_executed": 15,
                "session_id": "session_123",
                "timestamp": "2024-01-18T12:00:00Z"
            }
        } 
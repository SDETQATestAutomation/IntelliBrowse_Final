"""
Press Key Tool Schemas.

Pydantic schemas for pressing keyboard keys request and response validation.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class PressKeyRequest(BaseModel):
    """Request schema for pressing keyboard keys."""
    
    session_id: str = Field(description="Active Playwright session ID")
    key: str = Field(description="Key to press (e.g., 'Enter', 'Tab', 'ArrowRight', 'a', 'F1')")
    selector: Optional[str] = Field(default=None, description="Optional CSS selector to focus before pressing key")
    modifiers: Optional[List[str]] = Field(default=[], description="Modifier keys (e.g., ['Control', 'Shift', 'Alt', 'Meta'])")
    timeout_ms: Optional[int] = Field(default=5000, description="Timeout in milliseconds for element focus")
    delay_after_ms: Optional[int] = Field(default=0, description="Delay after key press in milliseconds")
    focus_first: Optional[bool] = Field(default=True, description="Whether to focus element before key press if selector provided")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_12345",
                "key": "Enter",
                "selector": "#submit-form",
                "modifiers": [],
                "timeout_ms": 5000,
                "delay_after_ms": 100,
                "focus_first": True
            }
        }


class PressKeyResponse(BaseModel):
    """Response schema for key press operation."""
    
    success: bool = Field(description="Whether the key was pressed successfully")
    session_id: str = Field(description="Session ID where the key was pressed")
    key: str = Field(description="Key that was pressed")
    selector: Optional[str] = Field(description="Selector that was focused (if any)")
    message: str = Field(description="Status or error message")
    key_pressed: bool = Field(description="Whether the key press operation was executed")
    focused_element: bool = Field(description="Whether an element was focused before key press")
    modifiers_used: List[str] = Field(default=[], description="Modifier keys that were used")
    elapsed_ms: int = Field(description="Time taken for the key press operation in milliseconds")
    metadata: Dict[str, Any] = Field(default={}, description="Additional key press operation metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "session_id": "session_12345",
                "key": "Enter",
                "selector": "#submit-form",
                "message": "Key pressed successfully",
                "key_pressed": True,
                "focused_element": True,
                "modifiers_used": [],
                "elapsed_ms": 120,
                "metadata": {
                    "key_code": 13,
                    "element_type": "form",
                    "form_submitted": True
                }
            }
        } 
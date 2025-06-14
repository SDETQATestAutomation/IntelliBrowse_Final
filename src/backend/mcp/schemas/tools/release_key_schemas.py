"""
Release Key Tool Schemas

Schemas for the key release tool that releases held-down keyboard keys
with support for element focusing, verification, and configurable timing.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class ReleaseKeyRequest(BaseModel):
    """Request schema for releasing held-down keyboard keys."""
    
    session_id: str = Field(description="Active Playwright session ID")
    key: str = Field(description="Key to release (e.g., 'Shift', 'Control', 'Alt', 'Enter', 'F1')")
    selector: Optional[str] = Field(default=None, description="Optional CSS selector to focus before releasing key")
    timeout_ms: Optional[int] = Field(default=5000, description="Timeout in milliseconds for element focus")
    delay_after_ms: Optional[int] = Field(default=0, description="Delay after key release in milliseconds")
    focus_first: Optional[bool] = Field(default=True, description="Whether to focus element before key release if selector provided")
    verify_release: Optional[bool] = Field(default=True, description="Whether to verify the key release operation")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_12345",
                "key": "Shift",
                "selector": "#text-input",
                "timeout_ms": 5000,
                "delay_after_ms": 50,
                "focus_first": True,
                "verify_release": True
            }
        }


class ReleaseKeyResponse(BaseModel):
    """Response schema for key release operation."""
    
    success: bool = Field(description="Whether the key was released successfully")
    session_id: str = Field(description="Session ID where the key was released")
    key: str = Field(description="Key that was released")
    selector: Optional[str] = Field(description="Selector that was focused (if any)")
    message: str = Field(description="Status or error message")
    key_released: bool = Field(description="Whether the key release operation was executed")
    focused_element: bool = Field(description="Whether an element was focused before key release")
    elapsed_ms: int = Field(description="Time taken for the key release operation in milliseconds")
    metadata: Dict[str, Any] = Field(default={}, description="Additional key release operation metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "session_id": "session_12345",
                "key": "Shift",
                "selector": "#text-input",
                "message": "Key released successfully",
                "key_released": True,
                "focused_element": True,
                "elapsed_ms": 80,
                "metadata": {
                    "key_code": "Shift",
                    "release_verified": True,
                    "active_element": "input"
                }
            }
        } 
"""
Clear Input Field Tool Schemas

Schemas for the input field clearing tool that clears text content
from input fields with verification and force options.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class ClearInputFieldRequest(BaseModel):
    """Request schema for clearing input field values."""
    
    session_id: str = Field(description="Active Playwright session ID")
    selector: str = Field(description="CSS selector of the input element to clear")
    timeout_ms: Optional[int] = Field(default=5000, description="Timeout in milliseconds for element availability")
    force: Optional[bool] = Field(default=False, description="Whether to force clearing even if element is not editable")
    verify_cleared: Optional[bool] = Field(default=True, description="Whether to verify that the field was actually cleared")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_12345",
                "selector": "#search-input",
                "timeout_ms": 5000,
                "force": False,
                "verify_cleared": True
            }
        }


class ClearInputFieldResponse(BaseModel):
    """Response schema for input field clearing operation."""
    
    success: bool = Field(description="Whether the field was cleared successfully")
    selector: str = Field(description="Selector used for the clearing operation")
    message: str = Field(description="Status or error message")
    was_cleared: bool = Field(description="Whether the field was actually cleared")
    original_value: str = Field(description="Original value that was in the field before clearing")
    final_value: str = Field(description="Final value in the field after clearing attempt")
    elapsed_ms: int = Field(description="Time taken for the clearing operation in milliseconds")
    metadata: Dict[str, Any] = Field(default={}, description="Additional clearing operation metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "selector": "#search-input",
                "message": "Input field cleared successfully",
                "was_cleared": True,
                "original_value": "previous search term",
                "final_value": "",
                "elapsed_ms": 120,
                "metadata": {
                    "element_type": "search",
                    "clear_method": "select_all_delete",
                    "verified": True
                }
            }
        } 
"""
Fill Element Tool Schemas.

Pydantic schemas for filling input elements with text request and response validation.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class FillElementRequest(BaseModel):
    """Request schema for filling input elements with text."""
    
    session_id: str = Field(description="Active Playwright session ID")
    selector: str = Field(description="CSS selector of the input element to fill")
    value: str = Field(description="Text value to fill into the element")
    timeout_ms: Optional[int] = Field(default=5000, description="Timeout in milliseconds for element availability")
    clear_first: Optional[bool] = Field(default=True, description="Whether to clear the element before filling")
    delay_ms: Optional[int] = Field(default=0, description="Delay after filling in milliseconds")
    force: Optional[bool] = Field(default=False, description="Whether to force filling even if element is not editable")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_12345",
                "selector": "#username",
                "value": "john.doe@example.com",
                "timeout_ms": 5000,
                "clear_first": True,
                "delay_ms": 50,
                "force": False
            }
        }


class FillElementResponse(BaseModel):
    """Response schema for element fill operation."""
    
    success: bool = Field(description="Whether the element was filled successfully")
    selector: str = Field(description="Selector used for the fill operation")
    value: str = Field(description="Value that was filled into the element")
    message: str = Field(description="Status or error message")
    cleared_first: bool = Field(description="Whether the element was cleared before filling")
    elapsed_ms: int = Field(description="Time taken for the fill operation in milliseconds")
    metadata: Dict[str, Any] = Field(default={}, description="Additional fill operation metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "selector": "#username",
                "value": "john.doe@example.com",
                "message": "Element filled successfully",
                "cleared_first": True,
                "elapsed_ms": 120,
                "metadata": {
                    "element_type": "input",
                    "original_value": "",
                    "final_value": "john.doe@example.com"
                }
            }
        } 
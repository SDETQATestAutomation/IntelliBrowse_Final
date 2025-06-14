"""
Type Text Tool Schemas

Schemas for the text typing tool that types text character by character
into input elements with configurable delays and clearing options.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class TypeTextRequest(BaseModel):
    """Request schema for typing text into input elements character by character."""
    
    session_id: str = Field(description="Active Playwright session ID")
    selector: str = Field(description="CSS selector of the input element to type into")
    text: str = Field(description="Text content to type character by character")
    timeout_ms: Optional[int] = Field(default=5000, description="Timeout in milliseconds for element availability")
    clear_before: Optional[bool] = Field(default=True, description="Whether to clear the element before typing")
    delay_ms: Optional[int] = Field(default=0, description="Delay between keystrokes in milliseconds")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_12345",
                "selector": "#password",
                "text": "mySecurePassword123",
                "timeout_ms": 5000,
                "clear_before": True,
                "delay_ms": 50
            }
        }


class TypeTextResponse(BaseModel):
    """Response schema for text typing operation."""
    
    success: bool = Field(description="Whether the text was typed successfully")
    selector: str = Field(description="Selector used for the typing operation")
    text: str = Field(description="Text that was typed into the element")
    message: str = Field(description="Status or error message")
    cleared_before: bool = Field(description="Whether the element was cleared before typing")
    characters_typed: int = Field(description="Number of characters that were typed")
    elapsed_ms: int = Field(description="Time taken for the typing operation in milliseconds")
    metadata: Dict[str, Any] = Field(default={}, description="Additional typing operation metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "selector": "#password",
                "text": "mySecurePassword123",
                "message": "Text typed successfully",
                "cleared_before": True,
                "characters_typed": 19,
                "elapsed_ms": 1450,
                "metadata": {
                    "typing_speed": "50ms_per_char",
                    "element_type": "password",
                    "keystrokes_sent": 19
                }
            }
        } 
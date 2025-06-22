"""
Go Forward Tool Schemas.

Pydantic schemas for browser history forward navigation request and response validation.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class GoForwardRequest(BaseModel):
    """Request schema for browser history forward navigation."""
    
    session_id: str = Field(description="Active Playwright session ID")
    timeout_ms: Optional[int] = Field(default=5000, description="Navigation timeout in milliseconds")
    wait_until: Optional[str] = Field(default="load", description="Wait condition: 'load', 'domcontentloaded', 'networkidle'")
    
    @field_validator('wait_until')

    
    @classmethod
    def validate_wait_until(cls, v):
        """Validate wait condition."""
        valid_conditions = ['load', 'domcontentloaded', 'networkidle']
        if v not in valid_conditions:
            raise ValueError(f"wait_until must be one of: {valid_conditions}")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_12345",
                "timeout_ms": 5000,
                "wait_until": "load"
            }
        }


class GoForwardResponse(BaseModel):
    """Response schema for browser forward navigation operation."""
    
    success: bool = Field(description="Whether the forward navigation was successful")
    message: str = Field(description="Status or error message")
    previous_url: Optional[str] = Field(default=None, description="URL before navigation")
    current_url: Optional[str] = Field(default=None, description="URL after navigation")
    navigation_occurred: bool = Field(description="Whether actual navigation took place")
    elapsed_ms: int = Field(description="Time taken for the navigation operation in milliseconds")
    metadata: Dict[str, Any] = Field(default={}, description="Additional navigation operation metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Successfully navigated forward",
                "previous_url": "https://example.com/page1",
                "current_url": "https://example.com/page2",
                "navigation_occurred": True,
                "elapsed_ms": 250,
                "metadata": {
                    "wait_until": "load",
                    "page_title": "Page 2",
                    "history_available": True
                }
            }
        } 
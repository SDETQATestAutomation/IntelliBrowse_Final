"""
Close Browser Tool Schemas.

Pydantic schemas for closing a browser session request and response validation.
"""

from typing import Dict, Any
from pydantic import BaseModel, Field


class CloseBrowserRequest(BaseModel):
    """Request schema for closing a browser session."""
    
    session_id: str = Field(description="ID of the browser session to close")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_12345"
            }
        }


class CloseBrowserResponse(BaseModel):
    """Response schema for closing a browser session."""
    
    closed: bool = Field(description="Whether the session was successfully closed")
    session_id: str = Field(description="The session ID that was closed")
    message: str = Field(description="Status message")
    remaining_sessions: int = Field(description="Number of remaining active sessions")
    
    class Config:
        json_schema_extra = {
            "example": {
                "closed": True,
                "session_id": "session_12345",
                "message": "Browser session closed successfully",
                "remaining_sessions": 2
            }
        } 
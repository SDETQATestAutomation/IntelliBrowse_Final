"""
Take Screenshot Tool Schemas.

Pydantic schemas for capturing page or element screenshots request and response validation.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class TakeScreenshotRequest(BaseModel):
    """Request schema for capturing page or element screenshots."""
    
    session_id: str = Field(description="Active Playwright session ID")
    element_selector: Optional[str] = Field(default=None, description="CSS selector of specific element to capture (optional)")
    full_page: Optional[bool] = Field(default=False, description="Capture full scrollable page")
    format: Optional[str] = Field(default="png", description="Image format: 'png' or 'jpeg'")
    quality: Optional[int] = Field(default=90, description="JPEG quality (1-100, ignored for PNG)")
    timeout_ms: Optional[int] = Field(default=5000, description="Timeout in milliseconds for element availability")
    store_base64: Optional[bool] = Field(default=True, description="Include base64 encoded image in response")
    save_to_file: Optional[bool] = Field(default=False, description="Save screenshot to file system")
    filename: Optional[str] = Field(default=None, description="Custom filename for saved screenshot")
    
    @field_validator('format')

    
    @classmethod
    def validate_format(cls, v):
        """Validate image format."""
        if v.lower() not in ['png', 'jpeg', 'jpg']:
            raise ValueError("Format must be 'png', 'jpeg', or 'jpg'")
        return v.lower()
    
    @field_validator('quality')

    
    @classmethod
    def validate_quality(cls, v):
        """Validate JPEG quality."""
        if not 1 <= v <= 100:
            raise ValueError("Quality must be between 1 and 100")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_12345",
                "element_selector": "#main-content",
                "full_page": False,
                "format": "png",
                "quality": 90,
                "timeout_ms": 5000,
                "store_base64": True,
                "save_to_file": False,
                "filename": "screenshot.png"
            }
        }


class TakeScreenshotResponse(BaseModel):
    """Response schema for screenshot capture operation."""
    
    success: bool = Field(description="Whether the screenshot was captured successfully")
    message: str = Field(description="Status or error message")
    screenshot_base64: Optional[str] = Field(default=None, description="Base64 encoded screenshot data")
    file_path: Optional[str] = Field(default=None, description="Path to saved screenshot file")
    filename: Optional[str] = Field(default=None, description="Generated or provided filename")
    format: str = Field(description="Image format used")
    file_size_bytes: Optional[int] = Field(default=None, description="Screenshot file size in bytes")
    dimensions: Optional[Dict[str, int]] = Field(default=None, description="Image dimensions (width, height)")
    element_selector: Optional[str] = Field(default=None, description="Element selector used (if any)")
    elapsed_ms: int = Field(description="Time taken for the screenshot operation in milliseconds")
    metadata: Dict[str, Any] = Field(default={}, description="Additional screenshot operation metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Screenshot captured successfully",
                "screenshot_base64": "iVBORw0KGgoAAAANSUhEUgAA...",
                "file_path": "/screenshots/screenshot_20250118_123456.png",
                "filename": "screenshot_20250118_123456.png",
                "format": "png",
                "file_size_bytes": 15420,
                "dimensions": {"width": 1200, "height": 800},
                "element_selector": "#main-content",
                "elapsed_ms": 450,
                "metadata": {
                    "full_page": False,
                    "page_url": "https://example.com",
                    "page_title": "Example Page"
                }
            }
        } 
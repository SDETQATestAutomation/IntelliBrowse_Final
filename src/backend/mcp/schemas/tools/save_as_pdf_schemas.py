"""
Save as PDF Schemas for IntelliBrowse MCP Server.

This module defines the Pydantic schemas for PDF generation operations,
including request validation, response formatting, and PDF configuration.
Part of the IntelliBrowse MCP Server implementation.

Author: IntelliBrowse Team
Created: 2025-01-18
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, field_validator
from datetime import datetime


class MarginSettings(BaseModel):
    """
    Schema for PDF margin settings.
    """
    
    top: Optional[str] = Field(
        default="1cm",
        description="Top margin (e.g., '1cm', '0.5in', '10px')"
    )
    
    bottom: Optional[str] = Field(
        default="1cm",
        description="Bottom margin (e.g., '1cm', '0.5in', '10px')"
    )
    
    left: Optional[str] = Field(
        default="1cm",
        description="Left margin (e.g., '1cm', '0.5in', '10px')"
    )
    
    right: Optional[str] = Field(
        default="1cm",
        description="Right margin (e.g., '1cm', '0.5in', '10px')"
    )


class SaveAsPdfRequest(BaseModel):
    """
    Request schema for generating PDF from web pages.
    
    Supports various PDF formats, orientations, margins, and advanced options.
    """
    
    session_id: str = Field(
        ...,
        description="Active browser session ID",
        min_length=1,
        max_length=100
    )
    
    filename: Optional[str] = Field(
        default=None,
        description="Output filename (auto-generated if not provided)",
        max_length=255
    )
    
    format: Optional[str] = Field(
        default="A4",
        description="Paper format (A4, A3, A2, A1, A0, Letter, Legal, Tabloid, Ledger)"
    )
    
    orientation: Optional[str] = Field(
        default="portrait",
        description="Page orientation (portrait, landscape)"
    )
    
    margin: Optional[MarginSettings] = Field(
        default=None,
        description="Margin settings for the PDF"
    )
    
    print_background: Optional[bool] = Field(
        default=True,
        description="Include background graphics and colors"
    )
    
    scale: Optional[float] = Field(
        default=1.0,
        description="Page scale factor",
        ge=0.1,
        le=2.0
    )
    
    page_ranges: Optional[str] = Field(
        default=None,
        description="Page ranges to include (e.g., '1-3,5,8-10')",
        max_length=100
    )
    
    width: Optional[str] = Field(
        default=None,
        description="Custom page width (overrides format)",
        max_length=20
    )
    
    height: Optional[str] = Field(
        default=None,
        description="Custom page height (overrides format)",
        max_length=20
    )
    
    prefer_css_page_size: Optional[bool] = Field(
        default=False,
        description="Use CSS-defined page size"
    )
    
    display_header_footer: Optional[bool] = Field(
        default=False,
        description="Display header and footer"
    )
    
    header_template: Optional[str] = Field(
        default=None,
        description="HTML template for header",
        max_length=1000
    )
    
    footer_template: Optional[str] = Field(
        default=None,
        description="HTML template for footer",
        max_length=1000
    )
    
    wait_for_selector: Optional[str] = Field(
        default=None,
        description="Wait for specific selector before generating PDF",
        max_length=500
    )
    
    wait_timeout: Optional[int] = Field(
        default=30000,
        description="Wait timeout in milliseconds",
        ge=1000,
        le=120000
    )
    
    @field_validator('format')

    
    @classmethod
    def validate_format(cls, v):
        """Validate PDF format."""
        valid_formats = {
            'A4', 'A3', 'A2', 'A1', 'A0', 'Letter', 'Legal', 'Tabloid', 'Ledger'
        }
        
        if v not in valid_formats:
            raise ValueError(f"Invalid format: {v}. Valid formats: {', '.join(sorted(valid_formats))}")
        
        return v
    
    @field_validator('orientation')

    
    @classmethod
    def validate_orientation(cls, v):
        """Validate page orientation."""
        valid_orientations = {'portrait', 'landscape'}
        
        if v not in valid_orientations:
            raise ValueError(f"Invalid orientation: {v}. Valid orientations: {', '.join(sorted(valid_orientations))}")
        
        return v
    
    @field_validator('filename')

    
    @classmethod
    def validate_filename(cls, v):
        """Validate filename."""
        if v is None:
            return v
        
        # Check for invalid characters
        invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
        for char in invalid_chars:
            if char in v:
                raise ValueError(f"Filename contains invalid character: {char}")
        
        # Ensure .pdf extension
        if not v.lower().endswith('.pdf'):
            v = v + '.pdf'
        
        return v
    
    @field_validator('page_ranges')

    
    @classmethod
    def validate_page_ranges(cls, v):
        """Validate page ranges format."""
        if v is None:
            return v
        
        # Basic validation for page ranges format
        import re
        if not re.match(r'^[\d,-]+$', v):
            raise ValueError("Invalid page ranges format. Use format like '1-3,5,8-10'")
        
        return v


class PdfMetadata(BaseModel):
    """
    Schema for PDF metadata.
    """
    
    file_path: str = Field(
        ...,
        description="Full path to the generated PDF file"
    )
    
    file_size_bytes: int = Field(
        ...,
        description="File size in bytes"
    )
    
    page_count: Optional[int] = Field(
        default=None,
        description="Number of pages in the PDF"
    )
    
    dimensions: Dict[str, Any] = Field(
        ...,
        description="PDF dimensions and settings"
    )
    
    generation_time_ms: int = Field(
        ...,
        description="Time taken to generate PDF in milliseconds"
    )
    
    source_url: str = Field(
        ...,
        description="URL of the page that was converted to PDF"
    )
    
    created_at: str = Field(
        ...,
        description="ISO timestamp when PDF was created"
    )


class SaveAsPdfResponse(BaseModel):
    """
    Response schema for PDF generation.
    """
    
    success: bool = Field(
        ...,
        description="Whether the PDF was generated successfully"
    )
    
    filename: str = Field(
        ...,
        description="Generated PDF filename"
    )
    
    file_path: str = Field(
        ...,
        description="Full path to the generated PDF file"
    )
    
    file_size_bytes: int = Field(
        ...,
        description="File size in bytes"
    )
    
    pdf_metadata: PdfMetadata = Field(
        ...,
        description="Detailed PDF metadata"
    )
    
    session_info: Dict[str, Any] = Field(
        ...,
        description="Session context information"
    )
    
    generation_time: str = Field(
        ...,
        description="ISO timestamp when PDF was generated"
    )
    
    message: str = Field(
        ...,
        description="Operation result message"
    )
    
    error: Optional[str] = Field(
        default=None,
        description="Error message if operation failed"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the operation"
    )


class SaveAsPdfError(BaseModel):
    """
    Error response schema for PDF generation failures.
    """
    
    success: bool = Field(
        default=False,
        description="Always false for error responses"
    )
    
    error: str = Field(
        ...,
        description="Error message describing what went wrong"
    )
    
    error_type: str = Field(
        ...,
        description="Type of error (session_not_found, generation_failed, file_error, etc.)"
    )
    
    session_id: Optional[str] = Field(
        default=None,
        description="Session ID that was requested"
    )
    
    filename: Optional[str] = Field(
        default=None,
        description="Filename that was being generated"
    )
    
    timestamp: str = Field(
        ...,
        description="ISO timestamp when error occurred"
    )
    
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional error details"
    ) 
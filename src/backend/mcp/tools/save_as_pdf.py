"""
Save as PDF Tool for IntelliBrowse MCP Server.

This module implements PDF generation from web pages with enterprise-grade features.
Supports various paper formats, orientations, margins, custom dimensions,
header/footer templates, and comprehensive file management.

Features:
- Multiple paper formats (A4, Letter, Legal, etc.)
- Portrait and landscape orientations
- Custom margins and dimensions
- Background graphics control
- Page scaling and range selection
- Header and footer templates
- Wait conditions for dynamic content
- Enterprise file management
- Comprehensive error handling and audit logging

Author: IntelliBrowse Team
Created: 2025-01-18
Part of the IntelliBrowse MCP Server implementation.
"""

import asyncio
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional
import structlog

# Import the shared server instance
try:
    from server_instance import mcp_server
except ImportError:
    # Fallback for when running directly from mcp directory
    from server_instance import mcp_server

try:
    from schemas.tools.save_as_pdf_schemas import (
        SaveAsPdfRequest,
        SaveAsPdfResponse,
        SaveAsPdfError,
        PdfMetadata,
        MarginSettings
    )
except ImportError:
    # Fallback for when running directly from mcp directory
    from schemas.tools.save_as_pdf_schemas import (
        SaveAsPdfRequest,
        SaveAsPdfResponse,
        SaveAsPdfError,
        PdfMetadata,
        MarginSettings
    )
try:
    from tools.browser_session import browser_sessions
except ImportError:
    # Fallback for when running directly from mcp directory
    from tools.browser_session import browser_sessions
try:
    from config.settings import get_settings
except ImportError:
    # Fallback for when running directly from mcp directory
    from config.settings import get_settings

# Initialize structured logger
logger = structlog.get_logger(__name__)

# Use the shared mcp_server instance instead of creating a new one

# Get application settings
settings = get_settings()


@mcp_server.tool()
async def save_as_pdf(
    session_id: str,
    filename: Optional[str] = None,
    format: Optional[str] = "A4",
    orientation: Optional[str] = "portrait",
    margin: Optional[Dict[str, str]] = None,
    print_background: Optional[bool] = True,
    scale: Optional[float] = 1.0,
    page_ranges: Optional[str] = None,
    width: Optional[str] = None,
    height: Optional[str] = None,
    prefer_css_page_size: Optional[bool] = False,
    display_header_footer: Optional[bool] = False,
    header_template: Optional[str] = None,
    footer_template: Optional[str] = None,
    wait_for_selector: Optional[str] = None,
    wait_timeout: Optional[int] = 30000
) -> Dict[str, Any]:
    """
    Generate PDF from current web page with enterprise features.
    
    This tool provides comprehensive PDF generation capabilities with support for
    various formats, orientations, margins, custom dimensions, and advanced options
    for enterprise document generation workflows.
    
    Args:
        session_id: Active browser session ID
        filename: Output filename (auto-generated if not provided)
        format: Paper format (A4, A3, Letter, Legal, etc.)
        orientation: Page orientation (portrait, landscape)
        margin: Margin settings (top, bottom, left, right)
        print_background: Include background graphics and colors
        scale: Page scale factor (0.1-2.0)
        page_ranges: Page ranges to include (e.g., '1-3,5,8-10')
        width: Custom page width (overrides format)
        height: Custom page height (overrides format)
        prefer_css_page_size: Use CSS-defined page size
        display_header_footer: Display header and footer
        header_template: HTML template for header
        footer_template: HTML template for footer
        wait_for_selector: Wait for specific selector before generating
        wait_timeout: Wait timeout in milliseconds
        
    Returns:
        Dict containing PDF generation results and file metadata
        
    Raises:
        Various exceptions for session, generation, and file system errors
    """
    
    # Convert margin dict to MarginSettings if provided
    margin_settings = None
    if margin:
        margin_settings = MarginSettings(**margin)
    
    # Validate request using Pydantic schema
    try:
        request = SaveAsPdfRequest(
            session_id=session_id,
            filename=filename,
            format=format,
            orientation=orientation,
            margin=margin_settings,
            print_background=print_background,
            scale=scale,
            page_ranges=page_ranges,
            width=width,
            height=height,
            prefer_css_page_size=prefer_css_page_size,
            display_header_footer=display_header_footer,
            header_template=header_template,
            footer_template=footer_template,
            wait_for_selector=wait_for_selector,
            wait_timeout=wait_timeout
        )
    except Exception as e:
        logger.error(
            "Invalid save_as_pdf request",
            error=str(e),
            session_id=session_id
        )
        return SaveAsPdfError(
            error=f"Invalid request parameters: {str(e)}",
            error_type="validation_error",
            session_id=session_id,
            timestamp=datetime.now(timezone.utc).isoformat()
        ).dict()
    
    # Log the PDF generation attempt
    logger.info(
        "Starting PDF generation",
        session_id=session_id,
        filename=request.filename,
        format=request.format,
        orientation=request.orientation
    )
    
    start_time = time.time()
    
    try:
        # Check if session exists
        if session_id not in browser_sessions:
            logger.error(
                "Session not found for PDF generation",
                session_id=session_id
            )
            return SaveAsPdfError(
                error=f"Browser session '{session_id}' not found",
                error_type="session_not_found",
                session_id=session_id,
                timestamp=datetime.now(timezone.utc).isoformat()
            ).dict()
        
        session = browser_sessions[session_id]
        page = session.get("page")
        
        if not page:
            logger.error(
                "No active page in session for PDF generation",
                session_id=session_id
            )
            return SaveAsPdfError(
                error=f"No active page in session '{session_id}'",
                error_type="no_active_page",
                session_id=session_id,
                timestamp=datetime.now(timezone.utc).isoformat()
            ).dict()
        
        # Get current page URL for context
        try:
            current_url = page.url
            page_title = await page.title()
        except Exception:
            current_url = "unknown"
            page_title = "unknown"
        
        # Generate filename if not provided
        if not request.filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_title = "".join(c for c in page_title[:50] if c.isalnum() or c in (' ', '-', '_')).strip()
            if not safe_title:
                safe_title = "webpage"
            request.filename = f"{safe_title}_{timestamp}.pdf"
        
        # Ensure filename has .pdf extension
        if not request.filename.lower().endswith('.pdf'):
            request.filename += '.pdf'
        
        # Create PDF directory if it doesn't exist
        pdf_dir = Path(getattr(settings, 'PDF_DIR', './pdfs'))
        pdf_dir.mkdir(parents=True, exist_ok=True)
        
        # Full file path
        file_path = pdf_dir / request.filename
        
        # Check if file already exists and create unique name if needed
        counter = 1
        original_path = file_path
        while file_path.exists():
            stem = original_path.stem
            suffix = original_path.suffix
            file_path = original_path.parent / f"{stem}_{counter}{suffix}"
            counter += 1
        
        # Update filename to match actual file path
        actual_filename = file_path.name
        
        # Wait for selector if specified
        if request.wait_for_selector:
            try:
                logger.debug(
                    "Waiting for selector before PDF generation",
                    session_id=session_id,
                    selector=request.wait_for_selector,
                    timeout=request.wait_timeout
                )
                await page.wait_for_selector(
                    request.wait_for_selector, 
                    timeout=request.wait_timeout
                )
            except Exception as e:
                logger.warning(
                    "Wait for selector failed, proceeding with PDF generation",
                    session_id=session_id,
                    selector=request.wait_for_selector,
                    error=str(e)
                )
        
        # Prepare PDF options
        pdf_options = {
            "path": str(file_path),
            "format": request.format,
            "landscape": request.orientation == "landscape",
            "print_background": request.print_background,
            "scale": request.scale,
            "prefer_css_page_size": request.prefer_css_page_size,
            "display_header_footer": request.display_header_footer
        }
        
        # Add custom dimensions if specified
        if request.width and request.height:
            pdf_options["width"] = request.width
            pdf_options["height"] = request.height
            # Remove format when using custom dimensions
            del pdf_options["format"]
        
        # Add margins if specified
        if request.margin:
            pdf_options["margin"] = {
                "top": request.margin.top,
                "bottom": request.margin.bottom,
                "left": request.margin.left,
                "right": request.margin.right
            }
        
        # Add page ranges if specified
        if request.page_ranges:
            pdf_options["page_ranges"] = request.page_ranges
        
        # Add header/footer templates if specified
        if request.header_template:
            pdf_options["header_template"] = request.header_template
        
        if request.footer_template:
            pdf_options["footer_template"] = request.footer_template
        
        # Generate PDF
        logger.debug(
            "Generating PDF with options",
            session_id=session_id,
            pdf_options=pdf_options
        )
        
        await page.pdf(**pdf_options)
        
        # Calculate generation time
        generation_time_ms = int((time.time() - start_time) * 1000)
        
        # Get file size
        file_size = file_path.stat().st_size
        
        # Create PDF metadata
        dimensions = {
            "format": request.format,
            "orientation": request.orientation,
            "scale": request.scale
        }
        
        if request.width and request.height:
            dimensions["custom_width"] = request.width
            dimensions["custom_height"] = request.height
        
        if request.margin:
            dimensions["margins"] = {
                "top": request.margin.top,
                "bottom": request.margin.bottom,
                "left": request.margin.left,
                "right": request.margin.right
            }
        
        pdf_metadata = PdfMetadata(
            file_path=str(file_path),
            file_size_bytes=file_size,
            dimensions=dimensions,
            generation_time_ms=generation_time_ms,
            source_url=current_url,
            created_at=datetime.now(timezone.utc).isoformat()
        )
        
        # Prepare session info
        session_info = {
            "session_id": session_id,
            "current_url": current_url,
            "page_title": page_title,
            "browser_context": session.get("context_id", "unknown")
        }
        
        # Create successful response
        response = SaveAsPdfResponse(
            success=True,
            filename=actual_filename,
            file_path=str(file_path),
            file_size_bytes=file_size,
            pdf_metadata=pdf_metadata,
            session_info=session_info,
            generation_time=datetime.now(timezone.utc).isoformat(),
            message=f"PDF '{actual_filename}' generated successfully ({file_size} bytes)",
            metadata={
                "generation_time_ms": generation_time_ms,
                "pdf_options": pdf_options,
                "file_format": "PDF",
                "compression": "standard"
            }
        )
        
        logger.info(
            "PDF generated successfully",
            session_id=session_id,
            filename=actual_filename,
            file_size=file_size,
            generation_time_ms=generation_time_ms,
            source_url=current_url
        )
        
        return response.dict()
        
    except Exception as e:
        logger.error(
            "Failed to generate PDF",
            session_id=session_id,
            filename=request.filename,
            error=str(e),
            error_type=type(e).__name__
        )
        
        return SaveAsPdfError(
            error=f"Failed to generate PDF: {str(e)}",
            error_type="generation_error",
            session_id=session_id,
            filename=request.filename,
            timestamp=datetime.now(timezone.utc).isoformat(),
            details={
                "exception_type": type(e).__name__,
                "error_location": "save_as_pdf_tool",
                "generation_time_ms": int((time.time() - start_time) * 1000)
            }
        ).dict()


# Helper function to estimate PDF page count (if needed for future enhancements)
def estimate_page_count(page_height: int, content_height: int, format: str) -> int:
    """
    Estimate the number of pages in the PDF based on content height.
    
    Args:
        page_height: Height of a single page in pixels
        content_height: Total content height in pixels
        format: Paper format (for reference)
        
    Returns:
        Estimated number of pages
    """
    if page_height <= 0:
        return 1
    
    pages = max(1, int((content_height + page_height - 1) / page_height))
    return pages 
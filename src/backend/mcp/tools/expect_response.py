"""
Expect Response Tool for IntelliBrowse MCP Server.

This module implements network response expectation setup with monitoring capabilities.
Supports URL pattern matching, HTTP method filtering, request/response capture,
and comprehensive timeout management for network testing scenarios.

Features:
- URL pattern matching with regex support
- HTTP method filtering (GET, POST, PUT, DELETE, etc.)
- Request header and body pattern matching
- Expected status code validation
- Response body and header capture
- Timeout management with automatic cleanup
- Comprehensive error handling and audit logging

Author: IntelliBrowse Team
Created: 2025-01-18
Part of the IntelliBrowse MCP Server implementation.
"""

import asyncio
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
import structlog

# Import the shared server instance
try:
    from server_instance import mcp_server
except ImportError:
    # Fallback for when running directly from mcp directory
    from server_instance import mcp_server

try:
    from schemas.tools.expect_response_schemas import (
        ExpectResponseRequest,
        ExpectResponseResponse,
        ExpectResponseError,
        NetworkExpectation
    )
except ImportError:
    # Fallback for when running directly from mcp directory
    from schemas.tools.expect_response_schemas import (
        ExpectResponseRequest,
        ExpectResponseResponse,
        ExpectResponseError,
        NetworkExpectation
    )
try:
    from tools.browser_session import browser_sessions
except ImportError:
    # Fallback for when running directly from mcp directory
    from tools.browser_session import browser_sessions

# Initialize structured logger
logger = structlog.get_logger(__name__)

# Use the shared mcp_server instance instead of creating a new one


@mcp_server.tool()
async def expect_response(
    session_id: str,
    url_pattern: str,
    method: Optional[str] = "GET",
    timeout_ms: Optional[int] = 30000,
    response_id: Optional[str] = None,
    match_headers: Optional[Dict[str, str]] = None,
    match_body_pattern: Optional[str] = None,
    expected_status_codes: Optional[List[int]] = None,
    capture_response_body: Optional[bool] = True,
    capture_response_headers: Optional[bool] = True
) -> Dict[str, Any]:
    """
    Set up expectation for network response monitoring.
    
    This tool establishes network monitoring for specific URL patterns and HTTP methods,
    allowing automated waiting for expected network responses during browser automation.
    
    Args:
        session_id: Active browser session ID
        url_pattern: URL pattern to match (regex supported)
        method: HTTP method to match (GET, POST, PUT, DELETE, etc.)
        timeout_ms: Wait timeout in milliseconds (1000-300000)
        response_id: Unique ID for this expectation (auto-generated if not provided)
        match_headers: Request headers that must match
        match_body_pattern: Regex pattern for request body matching
        expected_status_codes: Expected HTTP status codes
        capture_response_body: Whether to capture the response body
        capture_response_headers: Whether to capture response headers
        
    Returns:
        Dict containing expectation details and monitoring status
        
    Raises:
        Various exceptions for session, pattern validation, and setup errors
    """
    
    # Validate request using Pydantic schema
    try:
        request = ExpectResponseRequest(
            session_id=session_id,
            url_pattern=url_pattern,
            method=method,
            timeout_ms=timeout_ms,
            response_id=response_id,
            match_headers=match_headers,
            match_body_pattern=match_body_pattern,
            expected_status_codes=expected_status_codes,
            capture_response_body=capture_response_body,
            capture_response_headers=capture_response_headers
        )
    except Exception as e:
        logger.error(
            "Invalid expect_response request",
            error=str(e),
            session_id=session_id
        )
        return ExpectResponseError(
            error=f"Invalid request parameters: {str(e)}",
            error_type="validation_error",
            session_id=session_id,
            timestamp=datetime.now(timezone.utc).isoformat()
        ).dict()
    
    # Generate response ID if not provided
    if not request.response_id:
        request.response_id = f"response_{uuid.uuid4().hex[:12]}"
    
    # Log the expectation setup attempt
    logger.info(
        "Setting up network response expectation",
        session_id=session_id,
        response_id=request.response_id,
        url_pattern=request.url_pattern,
        method=request.method,
        timeout_ms=request.timeout_ms
    )
    
    try:
        # Check if session exists
        if session_id not in browser_sessions:
            logger.error(
                "Session not found for response expectation",
                session_id=session_id
            )
            return ExpectResponseError(
                error=f"Browser session '{session_id}' not found",
                error_type="session_not_found",
                session_id=session_id,
                response_id=request.response_id,
                timestamp=datetime.now(timezone.utc).isoformat()
            ).dict()
        
        session = browser_sessions[session_id]
        page = session.get("page")
        
        if not page:
            logger.error(
                "No active page in session for response expectation",
                session_id=session_id
            )
            return ExpectResponseError(
                error=f"No active page in session '{session_id}'",
                error_type="no_active_page",
                session_id=session_id,
                response_id=request.response_id,
                timestamp=datetime.now(timezone.utc).isoformat()
            ).dict()
        
        # Get current page URL for context
        try:
            current_url = page.url
        except Exception:
            current_url = "unknown"
        
        # Initialize network expectations if not exists
        if 'network_expectations' not in session:
            session['network_expectations'] = {}
        
        # Check if response_id already exists
        if request.response_id in session['network_expectations']:
            logger.warning(
                "Response ID already exists, replacing expectation",
                session_id=session_id,
                response_id=request.response_id
            )
        
        # Calculate expiration time
        created_at = datetime.now(timezone.utc)
        expires_at = created_at + timedelta(milliseconds=request.timeout_ms)
        
        # Prepare match criteria
        match_criteria = {
            "url_pattern": request.url_pattern,
            "method": request.method,
            "match_headers": request.match_headers,
            "match_body_pattern": request.match_body_pattern,
            "expected_status_codes": request.expected_status_codes
        }
        
        # Prepare capture settings
        capture_settings = {
            "capture_response_body": request.capture_response_body,
            "capture_response_headers": request.capture_response_headers
        }
        
        # Create network expectation
        expectation = NetworkExpectation(
            response_id=request.response_id,
            url_pattern=request.url_pattern,
            method=request.method,
            timeout_ms=request.timeout_ms,
            created_at=created_at.isoformat(),
            expires_at=expires_at.isoformat(),
            status="waiting",
            match_criteria=match_criteria,
            capture_settings=capture_settings
        )
        
        # Store the expectation with additional runtime data
        session['network_expectations'][request.response_id] = {
            **expectation.dict(),
            'fulfilled': False,
            'captured_request': None,
            'captured_response': None,
            'match_time': None,
            'error': None
        }
        
        # Set up network monitoring if not already active
        if not session.get('network_monitoring_active', False):
            await setup_network_monitoring(page, session_id)
            session['network_monitoring_active'] = True
        
        # Prepare session info
        session_info = {
            "session_id": session_id,
            "current_url": current_url,
            "browser_context": session.get("context_id", "unknown"),
            "page_title": "unknown",
            "network_monitoring_active": session.get('network_monitoring_active', False),
            "total_expectations": len(session['network_expectations'])
        }
        
        # Try to get page title
        try:
            session_info["page_title"] = await page.title()
        except Exception:
            pass
        
        # Create successful response
        response = ExpectResponseResponse(
            success=True,
            response_id=request.response_id,
            expectation=expectation,
            monitoring_started=session.get('network_monitoring_active', False),
            session_info=session_info,
            setup_time=created_at.isoformat(),
            message=f"Network response expectation '{request.response_id}' set up successfully",
            metadata={
                "url_pattern_compiled": True,
                "body_pattern_compiled": bool(request.match_body_pattern),
                "timeout_ms": request.timeout_ms,
                "expires_at": expires_at.isoformat(),
                "match_criteria_count": sum(1 for v in match_criteria.values() if v is not None)
            }
        )
        
        logger.info(
            "Network response expectation set up successfully",
            session_id=session_id,
            response_id=request.response_id,
            url_pattern=request.url_pattern,
            method=request.method,
            expires_at=expires_at.isoformat()
        )
        
        return response.dict()
        
    except Exception as e:
        logger.error(
            "Failed to set up network response expectation",
            session_id=session_id,
            response_id=request.response_id,
            error=str(e),
            error_type=type(e).__name__
        )
        
        return ExpectResponseError(
            error=f"Failed to set up response expectation: {str(e)}",
            error_type="setup_error",
            session_id=session_id,
            response_id=request.response_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            details={
                "exception_type": type(e).__name__,
                "error_location": "expect_response_tool"
            }
        ).dict()


# Helper function to set up network monitoring for a page
async def setup_network_monitoring(page, session_id: str):
    """
    Set up network monitoring for a page to capture requests and responses.
    
    Args:
        page: Playwright page object
        session_id: Browser session ID
    """
    
    async def handle_request(request):
        """Handle network requests and check against expectations."""
        try:
            session = browser_sessions.get(session_id)
            if not session or 'network_expectations' not in session:
                return
            
            current_time = datetime.now(timezone.utc)
            
            # Check each active expectation
            for response_id, expectation in session['network_expectations'].items():
                if expectation['status'] != 'waiting':
                    continue
                
                # Check if expectation has expired
                expires_at = datetime.fromisoformat(expectation['expires_at'].replace('Z', '+00:00'))
                if current_time > expires_at:
                    expectation['status'] = 'expired'
                    logger.debug(
                        "Network expectation expired",
                        session_id=session_id,
                        response_id=response_id
                    )
                    continue
                
                # Check URL pattern match
                url_pattern = expectation['match_criteria']['url_pattern']
                try:
                    if not re.search(url_pattern, request.url):
                        continue
                except Exception:
                    continue
                
                # Check method match
                if expectation['match_criteria']['method'] != request.method:
                    continue
                
                # Check header matches if specified
                match_headers = expectation['match_criteria'].get('match_headers')
                if match_headers:
                    headers_match = True
                    for header_name, header_value in match_headers.items():
                        request_header = request.headers.get(header_name.lower())
                        if request_header != header_value:
                            headers_match = False
                            break
                    if not headers_match:
                        continue
                
                # Check body pattern match if specified
                match_body_pattern = expectation['match_criteria'].get('match_body_pattern')
                if match_body_pattern:
                    try:
                        request_body = request.post_data or ""
                        if not re.search(match_body_pattern, request_body):
                            continue
                    except Exception:
                        continue
                
                # Request matches the expectation - capture it
                captured_request = {
                    'url': request.url,
                    'method': request.method,
                    'headers': dict(request.headers),
                    'body': request.post_data,
                    'timestamp': current_time.isoformat()
                }
                
                expectation['captured_request'] = captured_request
                expectation['match_time'] = current_time.isoformat()
                
                logger.debug(
                    "Network request matched expectation",
                    session_id=session_id,
                    response_id=response_id,
                    url=request.url,
                    method=request.method
                )
                
        except Exception as e:
            logger.warning(
                "Error handling network request",
                session_id=session_id,
                error=str(e)
            )
    
    async def handle_response(response):
        """Handle network responses and check against expectations."""
        try:
            session = browser_sessions.get(session_id)
            if not session or 'network_expectations' not in session:
                return
            
            request = response.request
            current_time = datetime.now(timezone.utc)
            
            # Find matching expectation
            for response_id, expectation in session['network_expectations'].items():
                if (expectation['status'] == 'waiting' and 
                    expectation.get('captured_request') and
                    expectation['captured_request']['url'] == request.url and
                    expectation['captured_request']['method'] == request.method):
                    
                    # Check expected status codes if specified
                    expected_codes = expectation['match_criteria'].get('expected_status_codes')
                    if expected_codes and response.status not in expected_codes:
                        expectation['status'] = 'failed'
                        expectation['error'] = f"Status code {response.status} not in expected codes {expected_codes}"
                        logger.debug(
                            "Network response status code mismatch",
                            session_id=session_id,
                            response_id=response_id,
                            actual_status=response.status,
                            expected_codes=expected_codes
                        )
                        continue
                    
                    # Capture response data
                    captured_response = {
                        'status': response.status,
                        'status_text': response.status_text,
                        'headers': dict(response.headers),
                        'timestamp': current_time.isoformat()
                    }
                    
                    # Capture response body if requested
                    if expectation['capture_settings']['capture_response_body']:
                        try:
                            captured_response['body'] = await response.text()
                        except Exception:
                            captured_response['body'] = None
                    
                    expectation['captured_response'] = captured_response
                    expectation['status'] = 'fulfilled'
                    expectation['fulfilled'] = True
                    
                    logger.info(
                        "Network response expectation fulfilled",
                        session_id=session_id,
                        response_id=response_id,
                        url=request.url,
                        status=response.status
                    )
                    break
                    
        except Exception as e:
            logger.warning(
                "Error handling network response",
                session_id=session_id,
                error=str(e)
            )
    
    # Set up the network listeners
    page.on("request", handle_request)
    page.on("response", handle_response)
    
    logger.info(
        "Network monitoring set up for session",
        session_id=session_id
    ) 
"""
Assert Response Tool for IntelliBrowse MCP Server.

This module implements network response assertion with comprehensive validation capabilities.
Works in conjunction with expect_response to validate captured network responses
against various criteria including status codes, content, headers, and JSON paths.

Features:
- HTTP status code validation
- Response content text and pattern matching
- Response header validation
- JSON path assertions for structured responses
- Response time validation
- Content-type validation
- Comprehensive error handling and audit logging

Author: IntelliBrowse Team
Created: 2025-01-18
Part of the IntelliBrowse MCP Server implementation.
"""

import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import structlog
import jsonpath_ng

# Import the shared server instance
try:
    from server_instance import mcp_server
except ImportError:
    # Fallback for when running directly from mcp directory
    from server_instance import mcp_server

try:
    from schemas.tools.assert_response_schemas import (
        AssertResponseRequest,
        AssertResponseResponse,
        AssertResponseError,
        AssertionResult,
        CapturedResponse
    )
except ImportError:
    # Fallback for when running directly from mcp directory
    from schemas.tools.assert_response_schemas import (
        AssertResponseRequest,
        AssertResponseResponse,
        AssertResponseError,
        AssertionResult,
        CapturedResponse
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
async def assert_response(
    session_id: str,
    response_id: str,
    status_code: Optional[int] = None,
    contains_text: Optional[str] = None,
    contains_pattern: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    json_path_assertions: Optional[Dict[str, Any]] = None,
    response_time_max_ms: Optional[int] = None,
    content_type: Optional[str] = None,
    timeout_ms: Optional[int] = 5000
) -> Dict[str, Any]:
    """
    Assert network response properties against expected criteria.
    
    This tool validates responses captured by expect_response against various criteria,
    providing comprehensive assertion capabilities for network testing scenarios.
    
    Args:
        session_id: Active browser session ID
        response_id: Response ID from expect_response
        status_code: Expected HTTP status code
        contains_text: Text that must be present in response body
        contains_pattern: Regex pattern that must match response body
        headers: Response headers that must match
        json_path_assertions: JSON path assertions for response body
        response_time_max_ms: Maximum acceptable response time
        content_type: Expected content-type header value
        timeout_ms: Assertion timeout in milliseconds
        
    Returns:
        Dict containing assertion results and detailed validation information
        
    Raises:
        Various exceptions for session, response, and assertion errors
    """
    
    # Validate request using Pydantic schema
    try:
        request = AssertResponseRequest(
            session_id=session_id,
            response_id=response_id,
            status_code=status_code,
            contains_text=contains_text,
            contains_pattern=contains_pattern,
            headers=headers,
            json_path_assertions=json_path_assertions,
            response_time_max_ms=response_time_max_ms,
            content_type=content_type,
            timeout_ms=timeout_ms
        )
    except Exception as e:
        logger.error(
            "Invalid assert_response request",
            error=str(e),
            session_id=session_id,
            response_id=response_id
        )
        return AssertResponseError(
            error=f"Invalid request parameters: {str(e)}",
            error_type="validation_error",
            session_id=session_id,
            response_id=response_id,
            timestamp=datetime.now(timezone.utc).isoformat()
        ).dict()
    
    # Log the assertion attempt
    logger.info(
        "Starting network response assertion",
        session_id=session_id,
        response_id=response_id,
        status_code=status_code,
        timeout_ms=timeout_ms
    )
    
    try:
        # Check if session exists
        if session_id not in browser_sessions:
            logger.error(
                "Session not found for response assertion",
                session_id=session_id
            )
            return AssertResponseError(
                error=f"Browser session '{session_id}' not found",
                error_type="session_not_found",
                session_id=session_id,
                response_id=response_id,
                timestamp=datetime.now(timezone.utc).isoformat()
            ).dict()
        
        session = browser_sessions[session_id]
        page = session.get("page")
        
        if not page:
            logger.error(
                "No active page in session for response assertion",
                session_id=session_id
            )
            return AssertResponseError(
                error=f"No active page in session '{session_id}'",
                error_type="no_active_page",
                session_id=session_id,
                response_id=response_id,
                timestamp=datetime.now(timezone.utc).isoformat()
            ).dict()
        
        # Check if network expectations exist
        if 'network_expectations' not in session:
            logger.error(
                "No network expectations found in session",
                session_id=session_id
            )
            return AssertResponseError(
                error=f"No network expectations found in session '{session_id}'",
                error_type="no_expectations",
                session_id=session_id,
                response_id=response_id,
                timestamp=datetime.now(timezone.utc).isoformat()
            ).dict()
        
        # Check if specific response ID exists
        if response_id not in session['network_expectations']:
            logger.error(
                "Response ID not found in expectations",
                session_id=session_id,
                response_id=response_id
            )
            return AssertResponseError(
                error=f"Response ID '{response_id}' not found in expectations",
                error_type="response_not_found",
                session_id=session_id,
                response_id=response_id,
                timestamp=datetime.now(timezone.utc).isoformat()
            ).dict()
        
        expectation = session['network_expectations'][response_id]
        expectation_status = expectation.get('status', 'unknown')
        
        # Check if expectation is fulfilled
        if expectation_status != 'fulfilled':
            logger.error(
                "Network expectation not fulfilled",
                session_id=session_id,
                response_id=response_id,
                expectation_status=expectation_status
            )
            return AssertResponseError(
                error=f"Network expectation '{response_id}' is not fulfilled (status: {expectation_status})",
                error_type="expectation_not_fulfilled",
                session_id=session_id,
                response_id=response_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
                details={"expectation_status": expectation_status}
            ).dict()
        
        # Get captured response data
        captured_response_data = expectation.get('captured_response')
        captured_request_data = expectation.get('captured_request')
        
        if not captured_response_data:
            logger.error(
                "No captured response data found",
                session_id=session_id,
                response_id=response_id
            )
            return AssertResponseError(
                error=f"No captured response data found for '{response_id}'",
                error_type="no_response_data",
                session_id=session_id,
                response_id=response_id,
                timestamp=datetime.now(timezone.utc).isoformat()
            ).dict()
        
        # Calculate response time if available
        response_time_ms = None
        if captured_request_data and captured_response_data:
            try:
                request_time = datetime.fromisoformat(captured_request_data['timestamp'].replace('Z', '+00:00'))
                response_time = datetime.fromisoformat(captured_response_data['timestamp'].replace('Z', '+00:00'))
                response_time_ms = int((response_time - request_time).total_seconds() * 1000)
            except Exception:
                pass
        
        # Create captured response object
        captured_response = CapturedResponse(
            status=captured_response_data['status'],
            status_text=captured_response_data.get('status_text', ''),
            headers=captured_response_data.get('headers', {}),
            body=captured_response_data.get('body'),
            url=captured_request_data.get('url', '') if captured_request_data else '',
            method=captured_request_data.get('method', '') if captured_request_data else '',
            response_time_ms=response_time_ms,
            timestamp=captured_response_data['timestamp']
        )
        
        # Perform assertions
        assertions = []
        
        # Status code assertion
        if request.status_code is not None:
            passed = captured_response.status == request.status_code
            assertions.append(AssertionResult(
                assertion_type="status_code",
                expected=request.status_code,
                actual=captured_response.status,
                passed=passed,
                message=f"Status code {'matches' if passed else 'does not match'} expected value"
            ))
        
        # Contains text assertion
        if request.contains_text is not None:
            response_body = captured_response.body or ""
            passed = request.contains_text in response_body
            assertions.append(AssertionResult(
                assertion_type="contains_text",
                expected=request.contains_text,
                actual=f"Present: {passed}",
                passed=passed,
                message=f"Response body {'contains' if passed else 'does not contain'} expected text"
            ))
        
        # Contains pattern assertion
        if request.contains_pattern is not None:
            response_body = captured_response.body or ""
            try:
                passed = bool(re.search(request.contains_pattern, response_body))
                assertions.append(AssertionResult(
                    assertion_type="contains_pattern",
                    expected=request.contains_pattern,
                    actual=f"Match found: {passed}",
                    passed=passed,
                    message=f"Response body {'matches' if passed else 'does not match'} expected pattern"
                ))
            except Exception as e:
                assertions.append(AssertionResult(
                    assertion_type="contains_pattern",
                    expected=request.contains_pattern,
                    actual=f"Error: {str(e)}",
                    passed=False,
                    message=f"Pattern matching failed: {str(e)}"
                ))
        
        # Header assertions
        if request.headers:
            for header_name, expected_value in request.headers.items():
                actual_value = captured_response.headers.get(header_name.lower())
                passed = actual_value == expected_value
                assertions.append(AssertionResult(
                    assertion_type="header",
                    expected=expected_value,
                    actual=actual_value,
                    passed=passed,
                    message=f"Header '{header_name}' {'matches' if passed else 'does not match'} expected value",
                    path=header_name
                ))
        
        # Content-type assertion
        if request.content_type is not None:
            actual_content_type = captured_response.headers.get('content-type', '')
            passed = request.content_type.lower() in actual_content_type.lower()
            assertions.append(AssertionResult(
                assertion_type="content_type",
                expected=request.content_type,
                actual=actual_content_type,
                passed=passed,
                message=f"Content-type {'matches' if passed else 'does not match'} expected value"
            ))
        
        # Response time assertion
        if request.response_time_max_ms is not None and response_time_ms is not None:
            passed = response_time_ms <= request.response_time_max_ms
            assertions.append(AssertionResult(
                assertion_type="response_time",
                expected=f"<= {request.response_time_max_ms}ms",
                actual=f"{response_time_ms}ms",
                passed=passed,
                message=f"Response time {'is within' if passed else 'exceeds'} acceptable limit"
            ))
        
        # JSON path assertions
        if request.json_path_assertions and captured_response.body:
            try:
                response_json = json.loads(captured_response.body)
                for json_path, expected_value in request.json_path_assertions.items():
                    try:
                        jsonpath_expr = jsonpath_ng.parse(json_path)
                        matches = jsonpath_expr.find(response_json)
                        
                        if matches:
                            actual_value = matches[0].value
                            passed = actual_value == expected_value
                        else:
                            actual_value = None
                            passed = False
                        
                        assertions.append(AssertionResult(
                            assertion_type="json_path",
                            expected=expected_value,
                            actual=actual_value,
                            passed=passed,
                            message=f"JSON path '{json_path}' {'matches' if passed else 'does not match'} expected value",
                            path=json_path
                        ))
                    except Exception as e:
                        assertions.append(AssertionResult(
                            assertion_type="json_path",
                            expected=expected_value,
                            actual=f"Error: {str(e)}",
                            passed=False,
                            message=f"JSON path assertion failed: {str(e)}",
                            path=json_path
                        ))
            except json.JSONDecodeError as e:
                assertions.append(AssertionResult(
                    assertion_type="json_path",
                    expected="Valid JSON response",
                    actual=f"JSON parse error: {str(e)}",
                    passed=False,
                    message=f"Response body is not valid JSON: {str(e)}"
                ))
        
        # Calculate assertion results
        total_assertions = len(assertions)
        passed_assertions = sum(1 for a in assertions if a.passed)
        failed_assertions = total_assertions - passed_assertions
        all_passed = failed_assertions == 0
        
        # Get current page URL for context
        try:
            current_url = page.url
        except Exception:
            current_url = "unknown"
        
        # Prepare session info
        session_info = {
            "session_id": session_id,
            "current_url": current_url,
            "browser_context": session.get("context_id", "unknown"),
            "page_title": "unknown",
            "network_monitoring_active": session.get('network_monitoring_active', False)
        }
        
        # Try to get page title
        try:
            session_info["page_title"] = await page.title()
        except Exception:
            pass
        
        # Create successful response
        response = AssertResponseResponse(
            success=all_passed,
            response_id=response_id,
            assertions=assertions,
            total_assertions=total_assertions,
            passed_assertions=passed_assertions,
            failed_assertions=failed_assertions,
            captured_response=captured_response,
            expectation_status=expectation_status,
            session_info=session_info,
            assertion_time=datetime.now(timezone.utc).isoformat(),
            message=f"Assertion {'passed' if all_passed else 'failed'}: {passed_assertions}/{total_assertions} assertions passed",
            metadata={
                "response_time_ms": response_time_ms,
                "response_size_bytes": len(captured_response.body) if captured_response.body else 0,
                "assertion_types": list(set(a.assertion_type for a in assertions))
            }
        )
        
        logger.info(
            "Network response assertion completed",
            session_id=session_id,
            response_id=response_id,
            all_passed=all_passed,
            passed_assertions=passed_assertions,
            total_assertions=total_assertions
        )
        
        return response.dict()
        
    except Exception as e:
        logger.error(
            "Failed to assert network response",
            session_id=session_id,
            response_id=response_id,
            error=str(e),
            error_type=type(e).__name__
        )
        
        return AssertResponseError(
            error=f"Failed to assert response: {str(e)}",
            error_type="assertion_error",
            session_id=session_id,
            response_id=response_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            details={
                "exception_type": type(e).__name__,
                "error_location": "assert_response_tool"
            }
        ).dict() 
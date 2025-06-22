"""
MCP Server Test Configuration and Fixtures

Provides comprehensive test fixtures and configuration for end-to-end testing
of all MCP primitives (tools, prompts, resources) with real server integration.
"""

import pytest
import asyncio
import httpx
import structlog
import time
import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, AsyncMock, patch
import tempfile


# Test Configuration
MCP_BASE_URL = "http://127.0.0.1:8001"
MCP_SSE_ENDPOINT = f"{MCP_BASE_URL}/sse"
TEST_TIMEOUT = 30.0
REQUEST_TIMEOUT = 20.0

# Configure test logger
logger = structlog.get_logger("intellibrowse.mcp.tests")


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def mcp_server_health():
    """Verify MCP server is running and healthy before tests."""
    max_retries = 10
    retry_delay = 2.0
    
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Try to connect to the SSE endpoint
                response = await client.get(f"{MCP_BASE_URL}/health", timeout=5.0)
                if response.status_code == 200:
                    logger.info("MCP server is healthy and ready for testing")
                    return True
        except Exception as e:
            logger.warning(f"MCP server health check attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
    
    pytest.fail(f"MCP server not accessible at {MCP_BASE_URL} after {max_retries} attempts")


@pytest.fixture
async def http_client():
    """Create an async HTTP client for testing."""
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:8001",
        timeout=30.0,
        follow_redirects=True
    ) as client:
        yield client


@pytest.fixture
async def browser_session():
    """Create a browser session for testing browser tools."""
    session_data = {
        "method": "tools/call",
        "params": {
            "name": "browser_session",
            "arguments": {
                "action": "create",
                "browser_type": "chromium",
                "headless": True,
                "viewport": {"width": 1920, "height": 1080}
            }
        },
        "id": 1,
        "jsonrpc": "2.0"
    }
    
    async with httpx.AsyncClient(base_url=MCP_BASE_URL, timeout=REQUEST_TIMEOUT) as client:
        response = await client.post("/sse", json=session_data)
        
        if response.status_code != 200:
            pytest.fail(f"Failed to create browser session: {response.status_code}")
        
        result = response.json()
        if "error" in result:
            pytest.fail(f"Browser session creation error: {result['error']}")
        
        session_id = result.get("result", {}).get("session_id")
        if not session_id:
            pytest.fail("No session_id returned from browser session creation")
        
        yield session_id
        
        # Cleanup: Close browser session
        cleanup_data = {
            "method": "tools/call",
            "params": {
                "name": "browser_session",
                "arguments": {
                    "action": "close",
                    "session_id": session_id
                }
            },
            "id": 999,
            "jsonrpc": "2.0"
        }
        
        try:
            await client.post("/sse", json=cleanup_data)
        except Exception as e:
            logger.warning(f"Browser session cleanup failed: {e}")


@pytest.fixture
def sample_test_data():
    """Sample data for testing various MCP tools."""
    return {
        "urls": [
            "https://httpbin.org/html",
            "https://httpbin.org/forms/post",
            "https://example.com"
        ],
        "selectors": [
            "body",
            "h1",
            "input[type='text']",
            "button",
            "form"
        ],
        "javascript_safe": [
            "document.title",
            "window.location.href",
            "document.readyState",
            "document.body.tagName"
        ],
        "javascript_restricted": [
            "alert('test')",
            "document.cookie = 'test=value'",
            "localStorage.setItem('test', 'value')",
            "fetch('/api/admin')"
        ],
        "test_text": "This is test text for automation",
        "keys": ["Enter", "Tab", "Escape", "ArrowDown"],
        "coordinates": {"x": 100, "y": 200}
    }


@pytest.fixture
def mcp_request_builder():
    """Helper to build MCP JSON-RPC requests."""
    request_id = 0
    
    def build_request(method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        nonlocal request_id
        request_id += 1
        
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method
        }
        
        if params:
            request["params"] = params
            
        return request
    
    return build_request


@pytest.fixture
def tool_request_builder(mcp_request_builder):
    """Helper to build tool call requests."""
    def build_tool_request(tool_name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        return mcp_request_builder(
            "tools/call",
            {
                "name": tool_name,
                "arguments": arguments or {}
            }
        )
    
    return build_tool_request


@pytest.fixture
def prompt_request_builder(mcp_request_builder):
    """Helper to build prompt requests."""
    def build_prompt_request(prompt_name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        return mcp_request_builder(
            "prompts/get",
            {
                "name": prompt_name,
                "arguments": arguments or {}
            }
        )
    
    return build_prompt_request


@pytest.fixture
def resource_request_builder(mcp_request_builder):
    """Helper to build resource requests."""
    def build_resource_request(uri: str) -> Dict[str, Any]:
        return mcp_request_builder(
            "resources/read",
            {
                "uri": uri
            }
        )
    
    return build_resource_request


@pytest.fixture
async def test_context():
    """Create test execution context for sharing data between tests."""
    context = {
        "session_ids": [],
        "created_files": [],
        "test_results": {},
        "errors": []
    }
    
    yield context
    
    # Cleanup created files
    for file_path in context.get("created_files", []):
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.warning(f"Failed to cleanup file {file_path}: {e}")


@pytest.fixture
def temp_directory():
    """Create temporary directory for file operations testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


class MCPTestHelper:
    """Helper class for MCP testing utilities."""
    
    @staticmethod
    async def make_mcp_request(
        client: httpx.AsyncClient,
        request_data: Dict[str, Any],
        expect_success: bool = True
    ) -> Dict[str, Any]:
        """Make MCP request and validate response."""
        response = await client.post("/sse", json=request_data)
        
        if response.status_code != 200:
            raise AssertionError(f"HTTP error {response.status_code}: {response.text}")
        
        result = response.json()
        
        if expect_success and "error" in result:
            raise AssertionError(f"MCP error: {result['error']}")
        
        return result
    
    @staticmethod
    def validate_mcp_response(response: Dict[str, Any], expected_fields: List[str] = None):
        """Validate MCP response structure."""
        assert "jsonrpc" in response, "Missing jsonrpc field"
        assert response["jsonrpc"] == "2.0", "Invalid jsonrpc version"
        assert "id" in response, "Missing id field"
        
        if expected_fields:
            result = response.get("result", {})
            for field in expected_fields:
                assert field in result, f"Missing expected field: {field}"
    
    @staticmethod
    def validate_tool_response(response: Dict[str, Any]):
        """Validate tool response structure."""
        MCPTestHelper.validate_mcp_response(response, ["content"])
        
        result = response["result"]
        assert isinstance(result["content"], list), "Tool content must be a list"
        
        for item in result["content"]:
            assert "type" in item, "Content item missing type"
            assert "text" in item, "Content item missing text"


@pytest.fixture
def mcp_helper():
    """Provide MCP test helper utilities."""
    return MCPTestHelper


# Pytest configuration
pytest_plugins = ["pytest_asyncio"]


def pytest_addoption(parser):
    """Add custom pytest options."""
    parser.addoption(
        "--mcp-server",
        action="store",
        default=MCP_BASE_URL,
        help="MCP server base URL"
    )
    parser.addoption(
        "--skip-server-check",
        action="store_true",
        default=False,
        help="Skip MCP server health check"
    )


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "browser: mark test as requiring browser session"
    )


@pytest.fixture(autouse=True)
def test_logging():
    """Configure logging for tests."""
    structlog.configure(
        processors=[
            structlog.testing.LogCapture(),
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,
    ) 
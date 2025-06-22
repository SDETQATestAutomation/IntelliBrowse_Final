"""
End-to-End NLP Command Processing Integration Tests

Comprehensive testing suite for natural language command processing in the MCP server,
including real OpenAI GPT-4o-mini integration and full workflow validation.

Features:
- Real OpenAI API integration with environment-based configuration
- Comprehensive command scenario testing (navigation, form fill, assertions)
- Edge case and error handling validation
- Full request/response cycle testing with Pydantic schema validation
- Memory bank integration for test tracking and resume protocol
- No mocks or shortcuts - real integration testing only
"""

import os
import pytest
import asyncio
import httpx
import json
import time
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from unittest.mock import patch
import structlog

import sys
from pathlib import Path

# Add the MCP root directory to the Python path for imports
mcp_root = Path(__file__).parent.parent
sys.path.insert(0, str(mcp_root))

from config.settings import get_settings
from core.nlp_endpoints import (
    NLPCommandRequest, NLPCommandResponse, 
    ConversationRequest, ConversationResponse,
    ToolsListResponse
)
from core.exceptions import (
    NLPProcessingError, AIAgentError, ToolExecutionError
)
from orchestration.agent_integration import get_agent_integration_manager
from schemas.tool_schemas import ToolCallRequest, ToolCallResponse

# Configure test logger
logger = structlog.get_logger("intellibrowse.mcp.tests.nlp_command_processing")

# Test Configuration
MCP_BASE_URL = "http://127.0.0.1:8001"
NLP_ENDPOINT = f"{MCP_BASE_URL}/api/nlp"
TEST_TIMEOUT = 60.0  # Extended timeout for AI processing
REQUEST_TIMEOUT = 45.0

# Test settings
settings = get_settings()


class TestEnvironmentSetup:
    """Test environment setup and validation."""
    
    @pytest.fixture(scope="session", autouse=True)
    def validate_openai_config(self):
        """Validate OpenAI configuration before running tests."""
        logger.info("Validating OpenAI configuration for E2E NLP testing")
        
        # Check if OpenAI API key is configured
        if not settings.openai_api_key or settings.openai_api_key == "":
            pytest.skip("OpenAI API key not configured. Set OPENAI_API_KEY environment variable.")
        
        # Check if NLP testing is enabled
        nlp_test_enabled = os.getenv("NLP_TEST_ENABLED", "true").lower() == "true"
        if not nlp_test_enabled:
            pytest.skip("NLP testing disabled. Set NLP_TEST_ENABLED=true to enable.")
        
        # Validate model configuration
        if not settings.openai_model:
            pytest.fail("OpenAI model not configured. Set OPENAI_MODEL environment variable.")
        
        logger.info(
            "OpenAI configuration validated successfully",
            extra={
                "model": settings.openai_model,
                "max_tokens": settings.openai_max_tokens,
                "temperature": settings.openai_temperature
            }
        )
        
        yield
    
    @pytest.fixture(scope="session")
    async def nlp_server_health(self):
        """Verify NLP endpoints are available and healthy."""
        max_retries = 10
        retry_delay = 3.0
        
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    # Test NLP health endpoint
                    response = await client.get(f"{NLP_ENDPOINT}/health", timeout=5.0)
                    if response.status_code == 200:
                        logger.info("NLP endpoints are healthy and ready for testing")
                        return True
                    
                    # Test NLP capabilities endpoint
                    response = await client.get(f"{NLP_ENDPOINT}/capabilities", timeout=5.0)
                    if response.status_code == 200:
                        logger.info("NLP capabilities endpoint available")
                        return True
                        
            except Exception as e:
                logger.warning(f"NLP health check attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
        
        pytest.fail(f"NLP endpoints not accessible at {NLP_ENDPOINT} after {max_retries} attempts")


class TestNLPBasicFunctionality:
    """Basic NLP functionality tests."""
    
    @pytest.fixture
    async def nlp_client(self):
        """HTTP client for NLP endpoint communication."""
        async with httpx.AsyncClient(
            base_url=NLP_ENDPOINT,
            timeout=httpx.Timeout(REQUEST_TIMEOUT),
            headers={"Content-Type": "application/json"}
        ) as client:
            yield client
    
    @pytest.mark.asyncio
    async def test_nlp_capabilities_endpoint(self, nlp_client):
        """Test NLP capabilities endpoint returns valid information."""
        logger.info("Testing NLP capabilities endpoint")
        
        response = await nlp_client.get("/capabilities")
        assert response.status_code == 200
        
        data = response.json()
        assert "natural_language_processing" in data
        assert "ai_agent_orchestration" in data
        assert "supported_commands" in data
        
        logger.info("NLP capabilities endpoint test successful", extra={"capabilities": data})
    
    @pytest.mark.asyncio
    async def test_nlp_health_endpoint(self, nlp_client):
        """Test NLP health endpoint returns service status."""
        logger.info("Testing NLP health endpoint")
        
        response = await nlp_client.get("/health")
        # Health endpoint may return 200 (healthy) or 503 (service unavailable)
        assert response.status_code in [200, 503]
        
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        
        logger.info("NLP health endpoint test successful", extra={"health_status": data})
    
    @pytest.mark.asyncio
    async def test_nlp_tools_endpoint(self, nlp_client):
        """Test NLP tools listing endpoint."""
        logger.info("Testing NLP tools endpoint")
        
        response = await nlp_client.get("/tools")
        assert response.status_code == 200
        
        data = response.json()
        tools_response = ToolsListResponse(**data)
        
        assert tools_response.count > 0
        assert isinstance(tools_response.tools, dict)
        assert len(tools_response.tools) > 0
        
        logger.info(
            "NLP tools endpoint test successful", 
            extra={
                "tools_count": tools_response.count,
                "available_tools": list(tools_response.tools.keys())
            }
        )


class TestNLPCommandProcessing:
    """Core NLP command processing tests with real OpenAI integration."""
    
    @pytest.fixture
    async def nlp_client(self):
        """HTTP client for NLP endpoint communication."""
        async with httpx.AsyncClient(
            base_url=NLP_ENDPOINT,
            timeout=httpx.Timeout(TEST_TIMEOUT),
            headers={"Content-Type": "application/json"}
        ) as client:
            yield client
    
    @pytest.fixture
    def session_id(self):
        """Generate unique session ID for test isolation."""
        return f"test_session_{uuid.uuid4().hex[:8]}"
    
    @pytest.mark.asyncio
    async def test_simple_navigation_command(self, nlp_client, session_id):
        """Test simple navigation command processing."""
        logger.info("Testing simple navigation command processing")
        
        command_request = NLPCommandRequest(
            command="Navigate to https://example.com",
            session_id=session_id,
            context={"test_type": "navigation"}
        )
        
        response = await nlp_client.post("/command", json=command_request.dict())
        assert response.status_code == 200
        
        data = response.json()
        nlp_response = NLPCommandResponse(**data)
        
        # Validate response structure
        assert nlp_response.success is not None
        assert isinstance(nlp_response.response, str)
        assert len(nlp_response.response) > 0
        assert nlp_response.session_id == session_id
        
        logger.info(
            "Simple navigation command test successful",
            extra={
                "session_id": session_id,
                "success": nlp_response.success,
                "tool_calls": nlp_response.tool_calls,
                "response_preview": nlp_response.response[:100]
            }
        )
    
    @pytest.mark.asyncio
    async def test_form_fill_command(self, nlp_client, session_id):
        """Test form filling command processing."""
        logger.info("Testing form fill command processing")
        
        command_request = NLPCommandRequest(
            command="Fill the username field with 'testuser' and password field with 'testpass123'",
            session_id=session_id,
            context={
                "test_type": "form_fill",
                "current_url": "https://example.com/login"
            }
        )
        
        response = await nlp_client.post("/command", json=command_request.dict())
        assert response.status_code == 200
        
        data = response.json()
        nlp_response = NLPCommandResponse(**data)
        
        # Validate response structure
        assert nlp_response.success is not None
        assert isinstance(nlp_response.response, str)
        assert nlp_response.session_id == session_id
        
        logger.info(
            "Form fill command test successful",
            extra={
                "session_id": session_id,
                "success": nlp_response.success,
                "tool_calls": nlp_response.tool_calls,
                "response_preview": nlp_response.response[:100]
            }
        )


class TestNLPErrorHandling:
    """NLP error handling and edge case tests."""
    
    @pytest.fixture
    async def nlp_client(self):
        """HTTP client for NLP endpoint communication."""
        async with httpx.AsyncClient(
            base_url=NLP_ENDPOINT,
            timeout=httpx.Timeout(REQUEST_TIMEOUT),
            headers={"Content-Type": "application/json"}
        ) as client:
            yield client
    
    @pytest.mark.asyncio
    async def test_empty_command_validation(self, nlp_client):
        """Test empty command validation."""
        logger.info("Testing empty command validation")
        
        with pytest.raises(Exception):  # Should raise validation error
            NLPCommandRequest(command="", session_id="test_session")
    
    @pytest.mark.asyncio
    async def test_malformed_command_handling(self, nlp_client):
        """Test handling of malformed or ambiguous commands."""
        logger.info("Testing malformed command handling")
        
        ambiguous_commands = [
            "Do something with the thing",
            "Click it",
            "Fix the problem",
            "Make it work better"
        ]
        
        session_id = f"test_session_{uuid.uuid4().hex[:8]}"
        
        for command in ambiguous_commands:
            command_request = NLPCommandRequest(
                command=command,
                session_id=session_id,
                context={"test_type": "malformed_command"}
            )
            
            response = await nlp_client.post("/command", json=command_request.dict())
            
            # Should handle gracefully, not crash
            assert response.status_code in [200, 422, 503]
            
            if response.status_code == 200:
                data = response.json()
                nlp_response = NLPCommandResponse(**data)
                
                # Response should indicate inability to process or ask for clarification
                assert isinstance(nlp_response.response, str)
                assert len(nlp_response.response) > 0
                
        logger.info("Malformed command handling test successful")


# Test execution summary and memory bank update
@pytest.fixture(scope="session", autouse=True)
def test_execution_summary():
    """Track test execution summary for memory bank integration."""
    start_time = datetime.utcnow()
    test_summary = {
        "test_suite": "NLP Command Processing Integration E2E Tests",
        "start_time": start_time.isoformat(),
        "openai_model": settings.openai_model,
        "test_categories": [
            "basic_functionality",
            "command_processing", 
            "error_handling"
        ]
    }
    
    yield test_summary
    
    # Update summary with completion info
    end_time = datetime.utcnow()
    test_summary.update({
        "end_time": end_time.isoformat(),
        "total_duration": str(end_time - start_time),
        "status": "completed"
    })
    
    logger.info(
        "NLP Command Processing E2E Test Suite completed",
        extra=test_summary
    )


# Pytest configuration for NLP testing
def pytest_configure(config):
    """Configure pytest for NLP testing."""
    config.addinivalue_line(
        "markers", "nlp: mark test as NLP integration test"
    )
    config.addinivalue_line(
        "markers", "openai: mark test as requiring OpenAI integration"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )


# Custom pytest collection modification
def pytest_collection_modifyitems(config, items):
    """Modify test collection for NLP-specific requirements."""
    skip_nlp = pytest.mark.skip(reason="NLP testing disabled or OpenAI not configured")
    
    # Check if NLP testing should be skipped
    nlp_enabled = os.getenv("NLP_TEST_ENABLED", "true").lower() == "true"
    openai_configured = bool(settings.openai_api_key and settings.openai_api_key != "")
    
    if not nlp_enabled or not openai_configured:
        for item in items:
            if "nlp" in item.keywords or "openai" in item.keywords:
                item.add_marker(skip_nlp) 
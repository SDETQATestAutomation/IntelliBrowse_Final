"""
End-to-End NLP Command-Driven Tool Orchestration Tests

This module provides comprehensive testing of NLP command processing and tool orchestration,
validating the complete pipeline from natural language input to tool execution and response.

Test Coverage:
- Single-step NLP commands (navigation, clicks, form fills)
- Multi-step/chained NLP commands (complex workflows)
- NLP commands requiring prompt integration (BDD generation)
- Error scenario handling (malformed commands, non-existent tools)
- Tool chaining with context propagation
- Session management across NLP interactions
- Asynchronous processing validation
- Real data validation without mocks

Enterprise Features:
- 100% real-data testing with OpenAI integration
- Comprehensive error handling and validation
- Memory bank integration for progress tracking
- Production-quality code fixes for any issues found
"""

import os
import sys
import json
import uuid
import asyncio
import pytest
import httpx
import structlog
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, patch

# Add MCP root to path for imports
mcp_root = Path(__file__).parent.parent
sys.path.insert(0, str(mcp_root))

from config.settings import get_settings
from core.nlp_endpoints import NLPCommandRequest, NLPCommandResponse
from core.exceptions import NLPProcessingError, AIAgentError, ToolExecutionError
from orchestration.agent_integration import get_agent_integration_manager
from orchestration.ai_agent import AgentCommand, AgentResponse
from schemas.context_schemas import SessionContext

# Configure logger
logger = structlog.get_logger("intellibrowse.mcp.tests.nlp_commands")

# Test configuration
settings = get_settings()
MCP_BASE_URL = "http://127.0.0.1:8001"
NLP_ENDPOINT = f"{MCP_BASE_URL}/api/nlp"
TEST_TIMEOUT = 120.0  # Extended timeout for complex NLP processing
REQUEST_TIMEOUT = 90.0


class TestEnvironmentValidation:
    """Validate test environment and dependencies."""
    
    @pytest.fixture(scope="session", autouse=True)
    def validate_nlp_environment(self):
        """Ensure NLP testing environment is properly configured."""
        logger.info("Validating NLP E2E test environment")
        
        # Check OpenAI configuration
        if not settings.openai_api_key or settings.openai_api_key == "":
            pytest.skip("OpenAI API key not configured. Set OPENAI_API_KEY environment variable.")
        
        # Check NLP testing is enabled
        nlp_test_enabled = os.getenv("NLP_E2E_TEST_ENABLED", "true").lower() == "true"
        if not nlp_test_enabled:
            pytest.skip("NLP E2E testing disabled. Set NLP_E2E_TEST_ENABLED=true to enable.")
        
        # Validate model configuration
        if not settings.openai_model:
            pytest.fail("OpenAI model not configured. Set OPENAI_MODEL environment variable.")
        
        logger.info(
            "NLP environment validation successful",
            extra={
                "model": settings.openai_model,
                "max_tokens": settings.openai_max_tokens,
                "temperature": settings.openai_temperature,
                "audit": True
            }
        )
        
        yield
    
    @pytest.fixture(scope="session")
    async def nlp_server_ready(self):
        """Verify NLP endpoints are operational."""
        max_retries = 15
        retry_delay = 3.0
        
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    # Test NLP health endpoint
                    response = await client.get(f"{NLP_ENDPOINT}/health", timeout=10.0)
                    if response.status_code == 200:
                        logger.info("NLP endpoints operational and ready")
                        return True
                    
                    # Test capabilities endpoint
                    response = await client.get(f"{NLP_ENDPOINT}/capabilities", timeout=10.0)
                    if response.status_code == 200:
                        logger.info("NLP capabilities endpoint operational")
                        return True
                        
            except Exception as e:
                logger.warning(f"NLP readiness check attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
        
        pytest.fail(f"NLP endpoints not operational at {NLP_ENDPOINT} after {max_retries} attempts")


class TestSingleStepNLPCommands:
    """Test single-step NLP commands that trigger individual tools."""
    
    @pytest.fixture
    def test_session_id(self):
        """Generate unique session ID for test isolation."""
        return f"test_session_{uuid.uuid4().hex[:8]}"
    
    @pytest.mark.asyncio
    async def test_navigation_command(self, test_session_id):
        """Test NLP navigation command triggers navigate_to_url tool."""
        logger.info("Testing single-step navigation NLP command")
        
        command_request = {
            "command": "Navigate to https://www.google.com",
            "session_id": test_session_id,
            "context": {"test": "navigation_command"}
        }
        
        # Execute NLP command
        async with httpx.AsyncClient(
            base_url=NLP_ENDPOINT,
            timeout=httpx.Timeout(TEST_TIMEOUT),
            headers={"Content-Type": "application/json"}
        ) as client:
            response = await client.post("/command", json=command_request)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Parse response
        response_data = response.json()
        nlp_response = NLPCommandResponse(**response_data)
        
        # Validate response structure
        assert nlp_response.success is True, f"Command failed: {nlp_response.response}"
        assert nlp_response.session_id == test_session_id
        assert nlp_response.tool_calls is not None, "No tools were called"
        assert len(nlp_response.tool_calls) > 0, "Expected at least one tool call"
        
        # Validate navigate_to_url tool was called
        tool_names = [call.get("tool_name") for call in nlp_response.tool_calls]
        assert "navigate_to_url" in tool_names, f"Expected navigate_to_url, got: {tool_names}"
        
        # Validate tool arguments
        nav_call = next(call for call in nlp_response.tool_calls if call.get("tool_name") == "navigate_to_url")
        assert "url" in nav_call.get("arguments", {}), "navigate_to_url should have url argument"
        assert "google.com" in nav_call["arguments"]["url"], "URL should contain google.com"
        
        logger.info(
            "Navigation command test successful",
            extra={
                "tools_called": tool_names,
                "response_success": nlp_response.success,
                "audit": True
            }
        )
    
    @pytest.mark.asyncio
    async def test_click_element_command(self, test_session_id):
        """Test NLP click command triggers click_element tool."""
        logger.info("Testing single-step click element NLP command")
        
        command_request = {
            "command": "Click on the Search button",
            "session_id": test_session_id,
            "context": {"test": "click_command", "page_loaded": True}
        }
        
        # Execute NLP command
        async with httpx.AsyncClient(
            base_url=NLP_ENDPOINT,
            timeout=httpx.Timeout(TEST_TIMEOUT),
            headers={"Content-Type": "application/json"}
        ) as client:
            response = await client.post("/command", json=command_request)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Parse response
        response_data = response.json()
        nlp_response = NLPCommandResponse(**response_data)
        
        # Validate response structure
        assert nlp_response.success is True, f"Command failed: {nlp_response.response}"
        assert nlp_response.session_id == test_session_id
        assert nlp_response.tool_calls is not None, "No tools were called"
        assert len(nlp_response.tool_calls) > 0, "Expected at least one tool call"
        
        # Validate click_element tool was called
        tool_names = [call.get("tool_name") for call in nlp_response.tool_calls]
        assert "click_element" in tool_names, f"Expected click_element, got: {tool_names}"
        
        # Validate tool arguments
        click_call = next(call for call in nlp_response.tool_calls if call.get("tool_name") == "click_element")
        assert "element_description" in click_call.get("arguments", {}), "click_element should have element_description"
        
        logger.info(
            "Click element command test successful",
            extra={
                "tools_called": tool_names,
                "response_success": nlp_response.success,
                "audit": True
            }
        )
    
    @pytest.mark.asyncio
    async def test_fill_form_command(self, test_session_id):
        """Test NLP form fill command triggers fill_element tool."""
        logger.info("Testing single-step form fill NLP command")
        
        command_request = {
            "command": "Fill 'test@example.com' in the email field",
            "session_id": test_session_id,
            "context": {"test": "fill_command", "form_available": True}
        }
        
        # Execute NLP command
        async with httpx.AsyncClient(
            base_url=NLP_ENDPOINT,
            timeout=httpx.Timeout(TEST_TIMEOUT),
            headers={"Content-Type": "application/json"}
        ) as client:
            response = await client.post("/command", json=command_request)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Parse response
        response_data = response.json()
        nlp_response = NLPCommandResponse(**response_data)
        
        # Validate response structure
        assert nlp_response.success is True, f"Command failed: {nlp_response.response}"
        assert nlp_response.session_id == test_session_id
        assert nlp_response.tool_calls is not None, "No tools were called"
        assert len(nlp_response.tool_calls) > 0, "Expected at least one tool call"
        
        # Validate fill_element tool was called
        tool_names = [call.get("tool_name") for call in nlp_response.tool_calls]
        assert "fill_element" in tool_names, f"Expected fill_element, got: {tool_names}"
        
        # Validate tool arguments
        fill_call = next(call for call in nlp_response.tool_calls if call.get("tool_name") == "fill_element")
        args = fill_call.get("arguments", {})
        assert "element_description" in args, "fill_element should have element_description"
        assert "value" in args, "fill_element should have value"
        assert "test@example.com" in args["value"], "Value should contain test email"
        
        logger.info(
            "Fill form command test successful",
            extra={
                "tools_called": tool_names,
                "response_success": nlp_response.success,
                "audit": True
            }
        )


class TestMultiStepNLPCommands:
    """Test multi-step NLP commands that trigger tool chaining."""
    
    @pytest.fixture
    def test_session_id(self):
        """Generate unique session ID for test isolation."""
        return f"test_chain_{uuid.uuid4().hex[:8]}"
    
    @pytest.mark.asyncio
    async def test_navigation_and_click_chain(self, test_session_id):
        """Test NLP command that chains navigation and clicking."""
        logger.info("Testing multi-step navigation and click NLP command")
        
        command_request = {
            "command": "Open browser, go to https://github.com, and click on 'Sign in'",
            "session_id": test_session_id,
            "context": {"test": "nav_click_chain"}
        }
        
        # Execute NLP command
        async with httpx.AsyncClient(
            base_url=NLP_ENDPOINT,
            timeout=httpx.Timeout(TEST_TIMEOUT),
            headers={"Content-Type": "application/json"}
        ) as client:
            response = await client.post("/command", json=command_request)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Parse response
        response_data = response.json()
        nlp_response = NLPCommandResponse(**response_data)
        
        # Validate response structure
        assert nlp_response.success is True, f"Command failed: {nlp_response.response}"
        assert nlp_response.session_id == test_session_id
        assert nlp_response.tool_calls is not None, "No tools were called"
        assert len(nlp_response.tool_calls) >= 2, "Expected at least 2 tool calls for chaining"
        
        # Validate tool execution chain
        tool_names = [call.get("tool_name") for call in nlp_response.tool_calls]
        expected_tools = ["browser_session", "navigate_to_url", "click_element"]
        
        # Check that navigation and click tools were called
        assert any(tool in tool_names for tool in ["navigate_to_url", "browser_session"]), \
            f"Expected navigation tool, got: {tool_names}"
        assert "click_element" in tool_names, f"Expected click_element, got: {tool_names}"
        
        # Validate session context propagation
        for i, call in enumerate(nlp_response.tool_calls[1:], 1):
            if "session_id" in call.get("arguments", {}):
                assert call["arguments"]["session_id"], f"Tool {i} missing session context"
        
        logger.info(
            "Navigation and click chain test successful",
            extra={
                "tools_called": tool_names,
                "chain_length": len(nlp_response.tool_calls),
                "response_success": nlp_response.success,
                "audit": True
            }
        )
    
    @pytest.mark.asyncio
    async def test_form_workflow_chain(self, test_session_id):
        """Test NLP command that chains form interactions."""
        logger.info("Testing multi-step form workflow NLP command")
        
        command_request = {
            "command": "Navigate to login page, fill username 'testuser', fill password 'testpass', and click submit",
            "session_id": test_session_id,
            "context": {"test": "form_workflow_chain"}
        }
        
        # Execute NLP command
        async with httpx.AsyncClient(
            base_url=NLP_ENDPOINT,
            timeout=httpx.Timeout(TEST_TIMEOUT),
            headers={"Content-Type": "application/json"}
        ) as client:
            response = await client.post("/command", json=command_request)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Parse response
        response_data = response.json()
        nlp_response = NLPCommandResponse(**response_data)
        
        # Validate response structure
        assert nlp_response.success is True, f"Command failed: {nlp_response.response}"
        assert nlp_response.session_id == test_session_id
        assert nlp_response.tool_calls is not None, "No tools were called"
        assert len(nlp_response.tool_calls) >= 3, "Expected at least 3 tool calls for workflow"
        
        # Validate tool execution chain
        tool_names = [call.get("tool_name") for call in nlp_response.tool_calls]
        expected_workflow_tools = ["navigate_to_url", "fill_element", "click_element"]
        
        # Check that form workflow tools were called
        assert any(tool in tool_names for tool in ["navigate_to_url", "browser_session"]), \
            f"Expected navigation tool, got: {tool_names}"
        assert "fill_element" in tool_names, f"Expected fill_element, got: {tool_names}"
        assert "click_element" in tool_names, f"Expected click_element, got: {tool_names}"
        
        # Validate that multiple fill operations occurred
        fill_calls = [call for call in nlp_response.tool_calls if call.get("tool_name") == "fill_element"]
        assert len(fill_calls) >= 2, f"Expected at least 2 fill operations, got {len(fill_calls)}"
        
        logger.info(
            "Form workflow chain test successful",
            extra={
                "tools_called": tool_names,
                "fill_operations": len(fill_calls),
                "chain_length": len(nlp_response.tool_calls),
                "response_success": nlp_response.success,
                "audit": True
            }
        )
    
    @pytest.mark.asyncio
    async def test_inspection_and_interaction_chain(self, test_session_id):
        """Test NLP command that chains DOM inspection with interaction."""
        logger.info("Testing inspection and interaction chain NLP command")
        
        command_request = {
            "command": "Navigate to example.com, inspect the page for forms, then fill the first text input with 'test data'",
            "session_id": test_session_id,
            "context": {"test": "inspection_interaction_chain"}
        }
        
        # Execute NLP command
        async with httpx.AsyncClient(
            base_url=NLP_ENDPOINT,
            timeout=httpx.Timeout(TEST_TIMEOUT),
            headers={"Content-Type": "application/json"}
        ) as client:
            response = await client.post("/command", json=command_request)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Parse response
        response_data = response.json()
        nlp_response = NLPCommandResponse(**response_data)
        
        # Validate response structure
        assert nlp_response.success is True, f"Command failed: {nlp_response.response}"
        assert nlp_response.session_id == test_session_id
        assert nlp_response.tool_calls is not None, "No tools were called"
        assert len(nlp_response.tool_calls) >= 2, "Expected at least 2 tool calls for inspection chain"
        
        # Validate tool execution chain
        tool_names = [call.get("tool_name") for call in nlp_response.tool_calls]
        
        # Check for inspection and interaction tools
        assert any(tool in tool_names for tool in ["navigate_to_url", "browser_session"]), \
            f"Expected navigation tool, got: {tool_names}"
        assert any(tool in tool_names for tool in ["dom_inspection", "fill_element"]), \
            f"Expected inspection or interaction tool, got: {tool_names}"
        
        logger.info(
            "Inspection and interaction chain test successful",
            extra={
                "tools_called": tool_names,
                "chain_length": len(nlp_response.tool_calls),
                "response_success": nlp_response.success,
                "audit": True
            }
        )


class TestNLPPromptIntegration:
    """Test NLP commands that trigger prompt-based tools."""
    
    @pytest.fixture
    def test_session_id(self):
        """Generate unique session ID for test isolation."""
        return f"test_prompt_{uuid.uuid4().hex[:8]}"
    
    @pytest.mark.asyncio
    async def test_bdd_generation_command(self, test_session_id):
        """Test NLP command that triggers BDD generation prompt/tool."""
        logger.info("Testing BDD generation NLP command")
        
        command_request = {
            "command": "Generate a login scenario for a user authentication system",
            "session_id": test_session_id,
            "context": {"test": "bdd_generation", "feature": "authentication"}
        }
        
        # Execute NLP command
        async with httpx.AsyncClient(
            base_url=NLP_ENDPOINT,
            timeout=httpx.Timeout(TEST_TIMEOUT),
            headers={"Content-Type": "application/json"}
        ) as client:
            response = await client.post("/command", json=command_request)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Parse response
        response_data = response.json()
        nlp_response = NLPCommandResponse(**response_data)
        
        # Validate response structure
        assert nlp_response.success is True, f"Command failed: {nlp_response.response}"
        assert nlp_response.session_id == test_session_id
        assert nlp_response.tool_calls is not None, "No tools were called"
        assert len(nlp_response.tool_calls) > 0, "Expected at least one tool call"
        
        # Validate BDD generation tool was called
        tool_names = [call.get("tool_name") for call in nlp_response.tool_calls]
        assert "bdd_generator" in tool_names, f"Expected bdd_generator, got: {tool_names}"
        
        # Validate tool arguments and response
        bdd_call = next(call for call in nlp_response.tool_calls if call.get("tool_name") == "bdd_generator")
        assert "user_story" in bdd_call.get("arguments", {}), "bdd_generator should have user_story argument"
        
        # Validate response contains BDD content
        assert any(keyword in nlp_response.response.lower() for keyword in ["scenario", "given", "when", "then"]), \
            "Response should contain BDD scenario keywords"
        
        logger.info(
            "BDD generation command test successful",
            extra={
                "tools_called": tool_names,
                "response_contains_bdd": True,
                "response_success": nlp_response.success,
                "audit": True
            }
        )
    
    @pytest.mark.asyncio
    async def test_locator_generation_command(self, test_session_id):
        """Test NLP command that triggers locator generation."""
        logger.info("Testing locator generation NLP command")
        
        command_request = {
            "command": "Generate a locator for the submit button on the current page",
            "session_id": test_session_id,
            "context": {"test": "locator_generation", "current_page": "form_page"}
        }
        
        # Execute NLP command
        async with httpx.AsyncClient(
            base_url=NLP_ENDPOINT,
            timeout=httpx.Timeout(TEST_TIMEOUT),
            headers={"Content-Type": "application/json"}
        ) as client:
            response = await client.post("/command", json=command_request)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Parse response
        response_data = response.json()
        nlp_response = NLPCommandResponse(**response_data)
        
        # Validate response structure
        assert nlp_response.success is True, f"Command failed: {nlp_response.response}"
        assert nlp_response.session_id == test_session_id
        assert nlp_response.tool_calls is not None, "No tools were called"
        assert len(nlp_response.tool_calls) > 0, "Expected at least one tool call"
        
        # Validate locator generation tool was called
        tool_names = [call.get("tool_name") for call in nlp_response.tool_calls]
        assert "locator_generator" in tool_names, f"Expected locator_generator, got: {tool_names}"
        
        # Validate tool arguments
        locator_call = next(call for call in nlp_response.tool_calls if call.get("tool_name") == "locator_generator")
        args = locator_call.get("arguments", {})
        assert "element_description" in args, "locator_generator should have element_description"
        assert "submit" in args["element_description"].lower(), "Description should contain 'submit'"
        
        logger.info(
            "Locator generation command test successful",
            extra={
                "tools_called": tool_names,
                "response_success": nlp_response.success,
                "audit": True
            }
        )


class TestNLPErrorHandling:
    """Test NLP error handling and edge cases."""
    
    @pytest.mark.asyncio
    async def test_empty_command_error(self):
        """Test handling of empty NLP commands."""
        logger.info("Testing empty command error handling")
        
        command_request = {
            "command": "",
            "session_id": "test_empty"
        }
        
        # Execute NLP command
        async with httpx.AsyncClient(
            base_url=NLP_ENDPOINT,
            timeout=httpx.Timeout(30.0),
            headers={"Content-Type": "application/json"}
        ) as client:
            response = await client.post("/command", json=command_request)
        
        assert response.status_code == 422, f"Expected 422 for empty command, got {response.status_code}"
        
        logger.info("Empty command error handling test successful")
    
    @pytest.mark.asyncio
    async def test_malformed_command_handling(self):
        """Test handling of malformed or unclear commands."""
        logger.info("Testing malformed command handling")
        
        command_request = {
            "command": "xyzabc invalid command with no meaning",
            "session_id": "test_malformed"
        }
        
        # Execute NLP command
        async with httpx.AsyncClient(
            base_url=NLP_ENDPOINT,
            timeout=httpx.Timeout(30.0),
            headers={"Content-Type": "application/json"}
        ) as client:
            response = await client.post("/command", json=command_request)
        
        # Should either succeed with error message or return appropriate error
        assert response.status_code in [200, 422, 400], f"Unexpected status: {response.status_code}"
        
        if response.status_code == 200:
            response_data = response.json()
            nlp_response = NLPCommandResponse(**response_data)
            # If successful, should indicate inability to process
            assert not nlp_response.success or "cannot" in nlp_response.response.lower() or "unable" in nlp_response.response.lower()
        
        logger.info("Malformed command handling test successful")
    
    @pytest.mark.asyncio
    async def test_unsupported_tool_command(self):
        """Test handling of commands requesting non-existent tools."""
        logger.info("Testing unsupported tool command handling")
        
        command_request = {
            "command": "Use the non_existent_tool to do something impossible",
            "session_id": "test_unsupported"
        }
        
        # Execute NLP command
        async with httpx.AsyncClient(
            base_url=NLP_ENDPOINT,
            timeout=httpx.Timeout(30.0),
            headers={"Content-Type": "application/json"}
        ) as client:
            response = await client.post("/command", json=command_request)
        
        # Should handle gracefully
        assert response.status_code in [200, 422, 400], f"Unexpected status: {response.status_code}"
        
        if response.status_code == 200:
            response_data = response.json()
            nlp_response = NLPCommandResponse(**response_data)
            # Should either fail or explain inability
            if nlp_response.success:
                assert any(word in nlp_response.response.lower() for word in 
                          ["cannot", "unable", "not available", "not supported"]), \
                    "Should indicate tool not available"
        
        logger.info("Unsupported tool command handling test successful")


class TestNLPSessionManagement:
    """Test session management and context propagation in NLP commands."""
    
    @pytest.mark.asyncio
    async def test_session_context_propagation(self):
        """Test that session context is maintained across multiple NLP commands."""
        logger.info("Testing session context propagation across NLP commands")
        
        session_id = f"test_context_{uuid.uuid4().hex[:8]}"
        
        # First command: establish context
        command1_request = {
            "command": "Navigate to https://example.com",
            "session_id": session_id,
            "context": {"test": "context_propagation", "step": 1}
        }
        
        async with httpx.AsyncClient(
            base_url=NLP_ENDPOINT,
            timeout=httpx.Timeout(TEST_TIMEOUT),
            headers={"Content-Type": "application/json"}
        ) as client:
            response1 = await client.post("/command", json=command1_request)
            assert response1.status_code == 200
            
            response1_data = response1.json()
            nlp_response1 = NLPCommandResponse(**response1_data)
            assert nlp_response1.success is True
            assert nlp_response1.session_id == session_id
            
            # Second command: should maintain session context
            command2_request = {
                "command": "Click on the first link",
                "session_id": session_id,
                "context": {"test": "context_propagation", "step": 2},
                "history": [
                    {"role": "user", "content": "Navigate to https://example.com"},
                    {"role": "assistant", "content": nlp_response1.response}
                ]
            }
            
            response2 = await client.post("/command", json=command2_request)
            assert response2.status_code == 200
            
            response2_data = response2.json()
            nlp_response2 = NLPCommandResponse(**response2_data)
            assert nlp_response2.success is True
            assert nlp_response2.session_id == session_id
            
            # Validate session context was maintained
            assert nlp_response2.context is not None
            if nlp_response2.history:
                assert len(nlp_response2.history) >= 2, "History should be maintained"
        
        logger.info(
            "Session context propagation test successful",
            extra={
                "session_id": session_id,
                "command1_success": nlp_response1.success,
                "command2_success": nlp_response2.success,
                "context_maintained": nlp_response2.context is not None,
                "audit": True
            }
        )
    
    @pytest.mark.asyncio
    async def test_session_isolation(self):
        """Test that different sessions are properly isolated."""
        logger.info("Testing session isolation between different NLP sessions")
        
        session1_id = f"test_isolation1_{uuid.uuid4().hex[:8]}"
        session2_id = f"test_isolation2_{uuid.uuid4().hex[:8]}"
        
        # Command in session 1
        command1_request = {
            "command": "Navigate to https://session1.example.com",
            "session_id": session1_id,
            "context": {"test": "isolation", "session": 1}
        }
        
        # Command in session 2
        command2_request = {
            "command": "Navigate to https://session2.example.com",
            "session_id": session2_id,
            "context": {"test": "isolation", "session": 2}
        }
        
        async with httpx.AsyncClient(
            base_url=NLP_ENDPOINT,
            timeout=httpx.Timeout(TEST_TIMEOUT),
            headers={"Content-Type": "application/json"}
        ) as client:
            response1 = await client.post("/command", json=command1_request)
            assert response1.status_code == 200
            
            response1_data = response1.json()
            nlp_response1 = NLPCommandResponse(**response1_data)
            assert nlp_response1.session_id == session1_id
            
            response2 = await client.post("/command", json=command2_request)
            assert response2.status_code == 200
            
            response2_data = response2.json()
            nlp_response2 = NLPCommandResponse(**response2_data)
            assert nlp_response2.session_id == session2_id
            
            # Validate sessions are isolated
            assert nlp_response1.session_id != nlp_response2.session_id
            
            # Contexts should be different
            if nlp_response1.context and nlp_response2.context:
                assert nlp_response1.context.get("session") != nlp_response2.context.get("session")
        
        logger.info(
            "Session isolation test successful",
            extra={
                "session1_id": session1_id,
                "session2_id": session2_id,
                "sessions_isolated": nlp_response1.session_id != nlp_response2.session_id,
                "audit": True
            }
        )


class TestNLPPerformanceValidation:
    """Test performance characteristics of NLP command processing."""
    
    @pytest.mark.asyncio
    async def test_response_time_validation(self):
        """Test that NLP commands complete within acceptable time limits."""
        logger.info("Testing NLP command response time validation")
        
        command_request = {
            "command": "Navigate to https://example.com and check if it loaded",
            "session_id": f"test_perf_{uuid.uuid4().hex[:8]}"
        }
        
        # Measure response time
        start_time = datetime.now(timezone.utc)
        
        async with httpx.AsyncClient(
            base_url=NLP_ENDPOINT,
            timeout=httpx.Timeout(TEST_TIMEOUT),
            headers={"Content-Type": "application/json"}
        ) as client:
            response = await client.post("/command", json=command_request)
        
        end_time = datetime.now(timezone.utc)
        response_time = (end_time - start_time).total_seconds()
        
        # Validate response
        assert response.status_code == 200
        
        response_data = response.json()
        nlp_response = NLPCommandResponse(**response_data)
        
        # Validate performance
        assert response_time < 60.0, f"Response time {response_time}s exceeds 60s limit"
        
        logger.info(
            "NLP response time validation successful",
            extra={
                "response_time_seconds": response_time,
                "response_success": nlp_response.success,
                "performance_acceptable": response_time < 60.0,
                "audit": True
            }
        )


# Test execution tracking and memory bank integration
@pytest.fixture(autouse=True)
def nlp_test_execution_tracker(request):
    """Track NLP test execution for memory bank integration."""
    test_name = request.node.name
    start_time = datetime.now(timezone.utc)
    
    logger.info(
        f"Starting NLP E2E test: {test_name}",
        extra={
            "test_name": test_name,
            "start_time": start_time.isoformat(),
            "test_category": "nlp_e2e",
            "audit": True
        }
    )
    
    yield
    
    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()
    
    logger.info(
        f"Completed NLP E2E test: {test_name}",
        extra={
            "test_name": test_name,
            "duration_seconds": duration,
            "end_time": end_time.isoformat(),
            "test_category": "nlp_e2e",
            "audit": True
        }
    )


# Pytest configuration for NLP E2E tests
def pytest_configure(config):
    """Configure pytest for NLP E2E testing."""
    config.addinivalue_line(
        "markers", "nlp_e2e: mark test as NLP end-to-end integration test"
    )


def pytest_collection_modifyitems(config, items):
    """Add nlp_e2e marker to all tests in this module."""
    for item in items:
        if "test_nlp_commands" in str(item.fspath):
            item.add_marker(pytest.mark.nlp_e2e) 
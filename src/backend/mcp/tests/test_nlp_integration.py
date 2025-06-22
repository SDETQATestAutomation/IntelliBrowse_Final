"""
NLP Command Integration Tests with Direct Module Testing

This module provides comprehensive testing of NLP command processing and tool orchestration
by testing the logic directly without requiring a running server. This ensures we can validate
the complete pipeline including:

- NLP command parsing and validation
- Tool orchestration and chaining
- Agent integration and response generation
- Session management and context propagation
- Error handling and edge cases

Features:
- Direct testing of orchestration modules
- Mock-based testing for external dependencies
- Comprehensive validation of NLP → Tool → Response pipeline
- Production-quality error handling validation
"""

import asyncio
import json
import uuid
import pytest
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

# Add MCP root to path for imports
mcp_root = Path(__file__).parent.parent
sys.path.insert(0, str(mcp_root))

try:
    from core.nlp_endpoints import NLPCommandRequest, NLPCommandResponse
    from core.exceptions import NLPProcessingError, AIAgentError, ToolExecutionError
    from orchestration.agent_integration import AgentIntegrationManager
    from orchestration.ai_agent import AIAgentOrchestrator, AgentCommand, AgentResponse
    from schemas.context_schemas import SessionContext
except ImportError as e:
    pytest.skip(f"Required modules not available: {e}", allow_module_level=True)

import structlog

# Configure logger
logger = structlog.get_logger("intellibrowse.mcp.tests.nlp_integration")


class TestNLPAgentIntegration:
    """Test NLP command processing through agent integration layer."""
    
    @pytest.fixture
    def mock_tools(self):
        """Mock tool registry for testing."""
        return {
            "navigate_to_url": {
                "description": "Navigate browser to a specific URL",
                "schema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL to navigate to"}
                    },
                    "required": ["url"]
                }
            },
            "click_element": {
                "description": "Click on a web element",
                "schema": {
                    "type": "object",
                    "properties": {
                        "element_description": {"type": "string", "description": "Element to click"}
                    },
                    "required": ["element_description"]
                }
            },
            "fill_element": {
                "description": "Fill an input field with text",
                "schema": {
                    "type": "object",
                    "properties": {
                        "element_description": {"type": "string", "description": "Input field to fill"},
                        "value": {"type": "string", "description": "Text to fill"}
                    },
                    "required": ["element_description", "value"]
                }
            },
            "bdd_generator": {
                "description": "Generate BDD scenarios",
                "schema": {
                    "type": "object",
                    "properties": {
                        "user_story": {"type": "string", "description": "User story"}
                    },
                    "required": ["user_story"]
                }
            },
            "locator_generator": {
                "description": "Generate element locators",
                "schema": {
                    "type": "object",
                    "properties": {
                        "element_description": {"type": "string", "description": "Element description"}
                    },
                    "required": ["element_description"]
                }
            }
        }
    
    @pytest.fixture
    def mock_tool_executor(self):
        """Mock tool executor that simulates successful tool execution."""
        async def execute_tool(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
            # Simulate successful tool execution based on tool type
            if tool_name == "navigate_to_url":
                return {
                    "success": True,
                    "message": f"Successfully navigated to {args.get('url')}",
                    "data": {"current_url": args.get('url'), "page_loaded": True}
                }
            elif tool_name == "click_element":
                return {
                    "success": True,
                    "message": f"Successfully clicked {args.get('element_description')}",
                    "data": {"element_clicked": True, "element_description": args.get('element_description')}
                }
            elif tool_name == "fill_element":
                return {
                    "success": True,
                    "message": f"Successfully filled {args.get('element_description')} with {args.get('value')}",
                    "data": {"element_filled": True, "value": args.get('value')}
                }
            elif tool_name == "bdd_generator":
                return {
                    "success": True,
                    "message": "Generated BDD scenario successfully",
                    "data": {
                        "scenario": f"Scenario: Test scenario for {args.get('user_story')}\nGiven I have a system\nWhen I perform an action\nThen I should see the result",
                        "validation_passed": True
                    }
                }
            elif tool_name == "locator_generator":
                return {
                    "success": True,
                    "message": f"Generated locator for {args.get('element_description')}",
                    "data": {
                        "locator": f"css=[data-testid='{args.get('element_description').lower().replace(' ', '-')}']",
                        "strategy": "css"
                    }
                }
            else:
                return {
                    "success": False,
                    "message": f"Unknown tool: {tool_name}",
                    "error": {"code": "UNKNOWN_TOOL", "message": f"Tool {tool_name} not found"}
                }
        
        return execute_tool
    
    @pytest.fixture
    def agent_integration_manager(self, mock_tools, mock_tool_executor):
        """Create agent integration manager with mocked dependencies."""
        manager = AgentIntegrationManager()
        
        # Mock the AI agent orchestrator
        mock_orchestrator = AsyncMock(spec=AIAgentOrchestrator)
        manager.agent_orchestrator = mock_orchestrator
        manager.tool_registry = mock_tools
        manager.tool_executor = mock_tool_executor
        manager.initialized = True
        
        return manager
    
    @pytest.mark.asyncio
    async def test_single_navigation_command(self, agent_integration_manager):
        """Test single-step navigation command processing."""
        logger.info("Testing single navigation command processing")
        
        command = "Navigate to https://www.google.com"
        session_id = f"test_nav_{uuid.uuid4().hex[:8]}"
        
        # Mock the AI orchestrator response
        expected_response = AgentResponse(
            response="I'll navigate to https://www.google.com for you.",
            success=True,
            session_id=session_id,
            tool_calls=[{
                "tool_name": "navigate_to_url",
                "arguments": {"url": "https://www.google.com"},
                "result": {
                    "success": True,
                    "message": "Successfully navigated to https://www.google.com"
                }
            }],
            metadata={"command_type": "navigation", "tools_executed": 1}
        )
        
        agent_integration_manager.agent_orchestrator.process_command.return_value = expected_response
        
        # Execute command
        result = await agent_integration_manager.process_natural_language_command(
            command=command,
            session_id=session_id
        )
        
        # Validate response
        assert result.success is True
        assert result.session_id == session_id
        assert result.tool_calls is not None
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["tool_name"] == "navigate_to_url"
        assert "google.com" in result.tool_calls[0]["arguments"]["url"]
        
        logger.info("Single navigation command test successful")
    
    @pytest.mark.asyncio
    async def test_multi_step_form_workflow(self, agent_integration_manager):
        """Test multi-step form workflow command processing."""
        logger.info("Testing multi-step form workflow command processing")
        
        command = "Navigate to login page, fill username 'testuser', fill password 'testpass', and click submit"
        session_id = f"test_workflow_{uuid.uuid4().hex[:8]}"
        
        # Mock the AI orchestrator response for chained workflow
        expected_response = AgentResponse(
            response="I'll help you complete the login workflow step by step.",
            success=True,
            session_id=session_id,
            tool_calls=[
                {
                    "tool_name": "navigate_to_url",
                    "arguments": {"url": "https://example.com/login"},
                    "result": {"success": True, "message": "Navigated to login page"}
                },
                {
                    "tool_name": "fill_element",
                    "arguments": {"element_description": "username field", "value": "testuser"},
                    "result": {"success": True, "message": "Filled username field"}
                },
                {
                    "tool_name": "fill_element",
                    "arguments": {"element_description": "password field", "value": "testpass"},
                    "result": {"success": True, "message": "Filled password field"}
                },
                {
                    "tool_name": "click_element",
                    "arguments": {"element_description": "submit button"},
                    "result": {"success": True, "message": "Clicked submit button"}
                }
            ],
            metadata={"command_type": "workflow", "tools_executed": 4}
        )
        
        agent_integration_manager.agent_orchestrator.process_command.return_value = expected_response
        
        # Execute command
        result = await agent_integration_manager.process_natural_language_command(
            command=command,
            session_id=session_id
        )
        
        # Validate response
        assert result.success is True
        assert result.session_id == session_id
        assert result.tool_calls is not None
        assert len(result.tool_calls) == 4
        
        # Validate tool sequence
        tool_names = [call["tool_name"] for call in result.tool_calls]
        assert "navigate_to_url" in tool_names
        assert "fill_element" in tool_names
        assert "click_element" in tool_names
        
        # Validate fill operations
        fill_calls = [call for call in result.tool_calls if call["tool_name"] == "fill_element"]
        assert len(fill_calls) == 2
        
        # Check that username and password were filled
        values_filled = [call["arguments"]["value"] for call in fill_calls]
        assert "testuser" in values_filled
        assert "testpass" in values_filled
        
        logger.info("Multi-step form workflow test successful")
    
    @pytest.mark.asyncio
    async def test_bdd_generation_command(self, agent_integration_manager):
        """Test BDD generation command processing."""
        logger.info("Testing BDD generation command processing")
        
        command = "Generate a login scenario for a user authentication system"
        session_id = f"test_bdd_{uuid.uuid4().hex[:8]}"
        
        # Mock the AI orchestrator response for BDD generation
        expected_response = AgentResponse(
            response="I've generated a comprehensive BDD scenario for user authentication.",
            success=True,
            session_id=session_id,
            tool_calls=[{
                "tool_name": "bdd_generator",
                "arguments": {"user_story": "login scenario for a user authentication system"},
                "result": {
                    "success": True,
                    "message": "Generated BDD scenario successfully",
                    "data": {
                        "scenario": "Scenario: User Login\nGiven I am on the login page\nWhen I enter valid credentials\nThen I should be logged in successfully",
                        "validation_passed": True
                    }
                }
            }],
            metadata={"command_type": "generation", "tools_executed": 1}
        )
        
        agent_integration_manager.agent_orchestrator.process_command.return_value = expected_response
        
        # Execute command
        result = await agent_integration_manager.process_natural_language_command(
            command=command,
            session_id=session_id
        )
        
        # Validate response
        assert result.success is True
        assert result.session_id == session_id
        assert result.tool_calls is not None
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["tool_name"] == "bdd_generator"
        
        # Validate BDD content
        bdd_result = result.tool_calls[0]["result"]
        assert "scenario" in bdd_result["data"]
        assert any(keyword in bdd_result["data"]["scenario"].lower() for keyword in ["given", "when", "then"])
        
        logger.info("BDD generation command test successful")
    
    @pytest.mark.asyncio
    async def test_locator_generation_command(self, agent_integration_manager):
        """Test locator generation command processing."""
        logger.info("Testing locator generation command processing")
        
        command = "Generate a locator for the submit button on the current page"
        session_id = f"test_locator_{uuid.uuid4().hex[:8]}"
        
        # Mock the AI orchestrator response for locator generation
        expected_response = AgentResponse(
            response="I've generated a reliable locator for the submit button.",
            success=True,
            session_id=session_id,
            tool_calls=[{
                "tool_name": "locator_generator",
                "arguments": {"element_description": "submit button"},
                "result": {
                    "success": True,
                    "message": "Generated locator for submit button",
                    "data": {
                        "locator": "css=[data-testid='submit-button']",
                        "strategy": "css"
                    }
                }
            }],
            metadata={"command_type": "generation", "tools_executed": 1}
        )
        
        agent_integration_manager.agent_orchestrator.process_command.return_value = expected_response
        
        # Execute command
        result = await agent_integration_manager.process_natural_language_command(
            command=command,
            session_id=session_id
        )
        
        # Validate response
        assert result.success is True
        assert result.session_id == session_id
        assert result.tool_calls is not None
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["tool_name"] == "locator_generator"
        
        # Validate locator content
        locator_result = result.tool_calls[0]["result"]
        assert "locator" in locator_result["data"]
        assert "submit" in locator_result["data"]["locator"].lower()
        
        logger.info("Locator generation command test successful")
    
    @pytest.mark.asyncio
    async def test_error_handling_invalid_command(self, agent_integration_manager):
        """Test error handling for invalid commands."""
        logger.info("Testing error handling for invalid commands")
        
        command = "xyzabc invalid command with no meaning"
        session_id = f"test_error_{uuid.uuid4().hex[:8]}"
        
        # Mock the AI orchestrator to return an error response
        error_response = AgentResponse(
            response="I'm unable to understand this command. Could you please rephrase it?",
            success=False,
            session_id=session_id,
            tool_calls=[],
            metadata={"command_type": "error", "error_reason": "unrecognized_command"}
        )
        
        agent_integration_manager.agent_orchestrator.process_command.return_value = error_response
        
        # Execute command
        result = await agent_integration_manager.process_natural_language_command(
            command=command,
            session_id=session_id
        )
        
        # Validate error response
        assert result.success is False
        assert result.session_id == session_id
        assert "unable" in result.response.lower() or "understand" in result.response.lower()
        
        logger.info("Error handling test successful")
    
    @pytest.mark.asyncio
    async def test_session_context_propagation(self, agent_integration_manager):
        """Test session context propagation across multiple commands."""
        logger.info("Testing session context propagation")
        
        session_id = f"test_context_{uuid.uuid4().hex[:8]}"
        
        # First command
        command1 = "Navigate to https://example.com"
        response1 = AgentResponse(
            response="Navigated to example.com",
            success=True,
            session_id=session_id,
            context={"current_url": "https://example.com", "page_loaded": True},
            tool_calls=[{
                "tool_name": "navigate_to_url",
                "arguments": {"url": "https://example.com"},
                "result": {"success": True, "message": "Navigation successful"}
            }],
            metadata={"command_sequence": 1}
        )
        
        agent_integration_manager.agent_orchestrator.process_command.return_value = response1
        
        result1 = await agent_integration_manager.process_natural_language_command(
            command=command1,
            session_id=session_id
        )
        
        # Second command with context from first
        command2 = "Click on the first link"
        response2 = AgentResponse(
            response="Clicked on the first link",
            success=True,
            session_id=session_id,
            context={"current_url": "https://example.com/page1", "page_loaded": True},
            history=[
                {"role": "user", "content": command1},
                {"role": "assistant", "content": response1.response},
                {"role": "user", "content": command2},
                {"role": "assistant", "content": "Clicked on the first link"}
            ],
            tool_calls=[{
                "tool_name": "click_element",
                "arguments": {"element_description": "first link"},
                "result": {"success": True, "message": "Click successful"}
            }],
            metadata={"command_sequence": 2}
        )
        
        agent_integration_manager.agent_orchestrator.process_command.return_value = response2
        
        result2 = await agent_integration_manager.process_natural_language_command(
            command=command2,
            session_id=session_id,
            context=result1.context,
            history=result1.history
        )
        
        # Validate context propagation
        assert result1.session_id == result2.session_id == session_id
        assert result1.success is True
        assert result2.success is True
        assert result2.context is not None
        if result2.history:
            assert len(result2.history) >= 2
        
        logger.info("Session context propagation test successful")


class TestNLPCommandValidation:
    """Test NLP command validation and schema compliance."""
    
    @pytest.mark.asyncio
    async def test_valid_command_request_creation(self):
        """Test creation of valid NLP command requests."""
        logger.info("Testing valid NLP command request creation")
        
        # Test basic command request
        request = NLPCommandRequest(
            command="Navigate to https://www.google.com",
            session_id="test_session_123"
        )
        
        assert request.command == "Navigate to https://www.google.com"
        assert request.session_id == "test_session_123"
        assert request.context is None
        assert request.history is None
        
        # Test command request with context and history
        request_with_context = NLPCommandRequest(
            command="Click on the search button",
            session_id="test_session_456",
            context={"page_loaded": True, "current_url": "https://google.com"},
            history=[
                {"role": "user", "content": "Navigate to Google"},
                {"role": "assistant", "content": "Navigated successfully"}
            ]
        )
        
        assert request_with_context.context["page_loaded"] is True
        assert len(request_with_context.history) == 2
        
        logger.info("Valid command request creation test successful")
    
    @pytest.mark.asyncio
    async def test_invalid_command_validation(self):
        """Test validation of invalid NLP commands."""
        logger.info("Testing invalid command validation")
        
        # Test empty command
        with pytest.raises(Exception):  # Pydantic validation error
            NLPCommandRequest(command="", session_id="test")
        
        # Test whitespace-only command
        with pytest.raises(ValueError, match="Command cannot be empty"):
            NLPCommandRequest(command="   ", session_id="test")
        
        # Test command that's too long
        long_command = "x" * 10001
        with pytest.raises(ValueError):
            NLPCommandRequest(command=long_command, session_id="test")
        
        logger.info("Invalid command validation test successful")
    
    @pytest.mark.asyncio
    async def test_response_model_creation(self):
        """Test creation of NLP response models."""
        logger.info("Testing NLP response model creation")
        
        # Test basic response
        response = NLPCommandResponse(
            response="Command executed successfully",
            success=True,
            session_id="test_session"
        )
        
        assert response.success is True
        assert response.session_id == "test_session"
        assert response.tool_calls is None
        
        # Test response with tool calls
        response_with_tools = NLPCommandResponse(
            response="Navigated to Google and clicked search",
            success=True,
            session_id="test_session",
            tool_calls=[
                {
                    "tool_name": "navigate_to_url",
                    "arguments": {"url": "https://google.com"},
                    "result": {"success": True}
                },
                {
                    "tool_name": "click_element",
                    "arguments": {"element_description": "search button"},
                    "result": {"success": True}
                }
            ],
            metadata={"tools_executed": 2, "execution_time": 1.5}
        )
        
        assert len(response_with_tools.tool_calls) == 2
        assert response_with_tools.metadata["tools_executed"] == 2
        
        logger.info("Response model creation test successful")


# Test execution tracking
@pytest.fixture(autouse=True)
def nlp_integration_test_tracker(request):
    """Track NLP integration test execution."""
    test_name = request.node.name
    start_time = datetime.now(timezone.utc)
    
    logger.info(
        f"Starting NLP integration test: {test_name}",
        extra={
            "test_name": test_name,
            "start_time": start_time.isoformat(),
            "test_category": "nlp_integration",
            "audit": True
        }
    )
    
    yield
    
    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()
    
    logger.info(
        f"Completed NLP integration test: {test_name}",
        extra={
            "test_name": test_name,
            "duration_seconds": duration,
            "end_time": end_time.isoformat(),
            "test_category": "nlp_integration",
            "audit": True
        }
    )


# Pytest configuration
def pytest_configure(config):
    """Configure pytest for NLP integration testing."""
    config.addinivalue_line(
        "markers", "nlp_integration: mark test as NLP integration test"
    )


def pytest_collection_modifyitems(config, items):
    """Add nlp_integration marker to all tests in this module."""
    for item in items:
        if "test_nlp_integration" in str(item.fspath):
            item.add_marker(pytest.mark.nlp_integration) 
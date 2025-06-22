"""
Test suite for IntelliBrowse MCP REST API Layer

Comprehensive tests for REST API endpoints, including integration testing,
error handling, and enterprise-grade validation patterns.
"""

import asyncio
import json
import pytest
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient
from fastapi.testclient import TestClient

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.rest_api import app, command_processor, CommandProcessor
from config.settings import MCPSettings

# Test Configuration
TEST_SETTINGS = {
    "mcp_host": "127.0.0.1",
    "mcp_port": 8001,
    "mcp_rest_port": 8002,
    "openai_api_key": "test-key",
    "mongodb_url": "mongodb://localhost:27017",
    "mongodb_database": "test_db",
    "log_level": "DEBUG"
}

@pytest.fixture
def test_client():
    """Create test client for REST API."""
    return TestClient(app)

@pytest.fixture
def mock_settings():
    """Mock MCP settings for testing."""
    with patch("core.rest_api.settings") as mock_settings:
        settings = MCPSettings()
        for key, value in TEST_SETTINGS.items():
            setattr(settings, key, value)
        mock_settings.return_value = settings
        yield settings

@pytest.fixture
def mock_mcp_client():
    """Mock MCP client for testing."""
    mock_client = AsyncMock()
    mock_client.list_tools.return_value = [
        MagicMock(name="bdd_generator"),
        MagicMock(name="locator_generator"),
        MagicMock(name="step_generator")
    ]
    return mock_client

@pytest.fixture
async def mock_command_processor(mock_mcp_client):
    """Mock command processor with MCP client."""
    processor = CommandProcessor()
    processor.mcp_client = mock_mcp_client
    return processor

class TestRestAPIEndpoints:
    """Test REST API endpoints functionality."""
    
    def test_health_check_endpoint(self, test_client):
        """Test health check endpoint."""
        response = test_client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "message" in data
        assert "mcp_server_status" in data
        assert "components" in data
        assert "timestamp" in data
    
    @patch.object(command_processor, 'process_command')
    def test_command_endpoint_success(self, mock_process, test_client):
        """Test successful command processing."""
        # Mock successful command processing
        mock_process.return_value = AsyncMock(
            response="Command executed successfully",
            success=True,
            history=[
                {"role": "user", "content": "click login button"},
                {"role": "assistant", "content": "Command executed successfully"}
            ],
            context=None,
            tool_calls=[{
                "tool": "click_element",
                "args": {"locator": "button[data-test='login']"},
                "result": {"success": True, "message": "Element clicked successfully"}
            }]
        )
        
        # Make request
        response = test_client.post(
            "/api/command",
            json={
                "command": "click login button",
                "history": [],
                "context": {"page_url": "https://example.com/login"}
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["response"] == "Command executed successfully"
        assert len(data["history"]) == 2
        assert len(data["tool_calls"]) == 1
    
    def test_command_endpoint_validation_error(self, test_client):
        """Test command endpoint validation errors."""
        # Test empty command
        response = test_client.post(
            "/api/command",
            json={"command": ""}
        )
        assert response.status_code == 422
        
        # Test missing command
        response = test_client.post(
            "/api/command",
            json={}
        )
        assert response.status_code == 422
        
        # Test command too long
        response = test_client.post(
            "/api/command",
            json={"command": "x" * 10001}
        )
        assert response.status_code == 422
    
    @patch.object(command_processor, 'process_command')
    def test_command_endpoint_processing_error(self, mock_process, test_client):
        """Test command processing errors."""
        # Mock processing failure
        mock_process.side_effect = Exception("Processing failed")
        
        response = test_client.post(
            "/api/command",
            json={"command": "click button"}
        )
        
        assert response.status_code == 500
        assert "Command processing failed" in response.json()["detail"]
    
    @patch.object(command_processor, 'mcp_client')
    def test_bdd_endpoint_success(self, mock_client, test_client):
        """Test successful BDD generation."""
        # Mock successful BDD generation
        mock_client.call_tool.return_value = {
            "success": True,
            "data": {
                "scenario": """Feature: User Login
  Scenario: Successful login
    Given I am on the login page
    When I enter valid credentials
    Then I should be logged in""",
                "validation_passed": True,
                "suggestions": ["Consider adding negative test cases"]
            }
        }
        
        response = test_client.post(
            "/api/generate-bdd",
            json={
                "description": "User should be able to log in with valid credentials",
                "user_story": "As a user, I want to log in",
                "acceptance_criteria": ["Login with valid email and password"]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Feature: User Login" in data["gherkin"]
        assert data["validation_passed"] is True
        assert len(data["suggestions"]) > 0
    
    def test_bdd_endpoint_validation_error(self, test_client):
        """Test BDD endpoint validation errors."""
        # Test empty description
        response = test_client.post(
            "/api/generate-bdd",
            json={"description": ""}
        )
        assert response.status_code == 422
        
        # Test missing description
        response = test_client.post(
            "/api/generate-bdd",
            json={}
        )
        assert response.status_code == 422
    
    @patch.object(command_processor, 'mcp_client')
    def test_bdd_endpoint_generation_error(self, mock_client, test_client):
        """Test BDD generation errors."""
        # Mock BDD generation failure
        mock_client.call_tool.return_value = {
            "success": False,
            "error": {"message": "Invalid user story format"}
        }
        
        response = test_client.post(
            "/api/generate-bdd",
            json={"description": "Invalid description"}
        )
        
        assert response.status_code == 400
        assert "BDD generation failed" in response.json()["detail"]

class TestCommandProcessor:
    """Test command processor functionality."""
    
    @pytest.mark.asyncio
    async def test_initialization(self, mock_settings):
        """Test command processor initialization."""
        processor = CommandProcessor()
        
        with patch.object(processor, 'mcp_client') as mock_client:
            mock_client.__aenter__ = AsyncMock()
            await processor.initialize()
            mock_client.__aenter__.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cleanup(self, mock_command_processor):
        """Test command processor cleanup."""
        await mock_command_processor.cleanup()
        mock_command_processor.mcp_client.__aexit__.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_parse_simple_command_click(self, mock_command_processor):
        """Test parsing simple click commands."""
        result = await mock_command_processor._parse_simple_command("click login button")
        
        assert result is not None
        assert result["tool"] == "click_element"
        assert result["args"]["element_description"] == "login button"
        assert result["needs_locator"] is True
    
    @pytest.mark.asyncio
    async def test_parse_simple_command_fill(self, mock_command_processor):
        """Test parsing simple fill commands."""
        result = await mock_command_processor._parse_simple_command("fill 'username' in email field")
        
        assert result is not None
        assert result["tool"] == "fill_element"
        assert result["args"]["element_description"] == "email field"
        assert result["args"]["value"] == "username"
        assert result["needs_locator"] is True
    
    @pytest.mark.asyncio
    async def test_parse_simple_command_complex(self, mock_command_processor):
        """Test parsing complex commands (should return None)."""
        result = await mock_command_processor._parse_simple_command("navigate to login page and click submit")
        assert result is None
        
        # Commands with selectors should be skipped
        result = await mock_command_processor._parse_simple_command("click #login-button")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_execute_direct_action_success(self, mock_command_processor):
        """Test successful direct action execution."""
        action = {
            "tool": "click_element",
            "args": {"element_description": "login button"},
            "needs_locator": True
        }
        
        # Mock locator generation and tool execution
        mock_command_processor.mcp_client.call_tool.side_effect = [
            {"success": True, "data": {"primary_locator": "button[data-test='login']"}},
            {"success": True, "message": "Element clicked successfully"}
        ]
        
        result = await mock_command_processor._execute_direct_action(action)
        
        assert result["success"] is True
        assert "clicked successfully" in result["message"]
        assert mock_command_processor.mcp_client.call_tool.call_count == 2
    
    @pytest.mark.asyncio
    async def test_execute_direct_action_locator_failure(self, mock_command_processor):
        """Test direct action execution with locator generation failure."""
        action = {
            "tool": "click_element",
            "args": {"element_description": "nonexistent button"},
            "needs_locator": True
        }
        
        # Mock failed locator generation
        mock_command_processor.mcp_client.call_tool.return_value = {
            "success": False,
            "error": "Element not found"
        }
        
        result = await mock_command_processor._execute_direct_action(action)
        
        assert result["success"] is False
        assert "Could not find element" in result["message"]
    
    @pytest.mark.asyncio
    async def test_process_complex_command(self, mock_command_processor):
        """Test complex command processing."""
        # Mock tool listing and step generation
        mock_command_processor.mcp_client.list_tools.return_value = [
            MagicMock(name="step_generator"),
            MagicMock(name="bdd_generator")
        ]
        
        mock_command_processor.mcp_client.call_tool.side_effect = [
            {
                "success": True,
                "data": {
                    "steps": [
                        {"tool": "navigate_to_url", "args": {"url": "https://example.com"}},
                        {"tool": "click_element", "args": {"locator": "button"}}
                    ]
                }
            },
            {"success": True, "message": "Navigation completed"},
            {"success": True, "message": "Button clicked"}
        ]
        
        result = await mock_command_processor._process_complex_command(
            "Navigate to example.com and click the submit button"
        )
        
        assert result.success is True
        assert len(result.tool_calls) == 2
        assert result.response == "Button clicked"
    
    def test_update_history(self, mock_command_processor):
        """Test conversation history update."""
        history = [{"role": "user", "content": "previous message"}]
        
        updated = mock_command_processor._update_history(
            history, "new user message", "new assistant message"
        )
        
        assert len(updated) == 3
        assert updated[-2]["role"] == "user"
        assert updated[-2]["content"] == "new user message"
        assert updated[-1]["role"] == "assistant"
        assert updated[-1]["content"] == "new assistant message"
    
    def test_update_history_truncation(self, mock_command_processor):
        """Test history truncation to prevent unbounded growth."""
        # Create history with 25 messages (exceeds limit of 20)
        large_history = []
        for i in range(25):
            large_history.append({"role": "user", "content": f"message {i}"})
        
        updated = mock_command_processor._update_history(
            large_history, "new message", "response"
        )
        
        # Should be truncated to 20 messages
        assert len(updated) == 20

class TestIntegration:
    """Integration tests for REST API with MCP server."""
    
    @pytest.mark.asyncio
    async def test_full_command_flow(self, mock_settings):
        """Test full command processing flow."""
        processor = CommandProcessor()
        
        # Mock MCP client
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        
        # Mock tool calls for locator generation and clicking
        mock_client.call_tool.side_effect = [
            {"success": True, "data": {"primary_locator": "button[data-test='submit']"}},
            {"success": True, "message": "Button clicked successfully"}
        ]
        
        processor.mcp_client = mock_client
        
        result = await processor.process_command("click submit button")
        
        assert result.success is True
        assert "successfully" in result.response.lower()
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["tool"] == "click_element"
    
    @pytest.mark.asyncio
    async def test_error_handling_flow(self, mock_settings):
        """Test error handling in command processing."""
        processor = CommandProcessor()
        
        # Mock MCP client that raises an exception
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(side_effect=Exception("Connection failed"))
        
        processor.mcp_client = None
        
        with patch.object(processor, '_init_mcp_client', side_effect=Exception("Connection failed")):
            result = await processor.process_command("click button")
            
            assert result.success is False
            assert "error" in result.response.lower()

class TestRequestValidation:
    """Test request validation and response schemas."""
    
    def test_command_request_validation(self):
        """Test CommandRequest validation."""
        from core.rest_api import CommandRequest
        
        # Valid request
        valid_request = CommandRequest(command="click button")
        assert valid_request.command == "click button"
        
        # Test command stripping
        request_with_spaces = CommandRequest(command="  click button  ")
        assert request_with_spaces.command == "click button"
        
        # Test validation error for empty command
        with pytest.raises(Exception):
            CommandRequest(command="")
        
        with pytest.raises(Exception):
            CommandRequest(command="   ")
    
    def test_bdd_request_validation(self):
        """Test BDDRequest validation."""
        from core.rest_api import BDDRequest
        
        # Valid request
        valid_request = BDDRequest(description="User login feature")
        assert valid_request.description == "User login feature"
        
        # Test description stripping
        request_with_spaces = BDDRequest(description="  User login feature  ")
        assert request_with_spaces.description == "User login feature"
        
        # Test validation error for empty description
        with pytest.raises(Exception):
            BDDRequest(description="")

# Test Configuration and Fixtures
@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 
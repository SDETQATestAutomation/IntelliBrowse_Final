"""
Unit tests for MCP Server Resources
Testing all 5 resource providers: DOM, Execution Context, Test Data, Session Artifact, Schema
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Dict, Any, List
import json
import tempfile
from pathlib import Path

# Resource imports
from ..resources.dom_resource import get_dom_snapshot, get_dom_elements, get_dom_forms
from ..resources.execution_context_resource import (
    get_execution_state, get_environment_config, 
    get_test_runner_context, get_browser_context
)
from ..resources.test_data_resource import (
    get_test_dataset, get_test_fixtures, get_validation_data,
    get_mock_data, get_filtered_dataset
)
from ..resources.session_artifact_resource import (
    get_session_screenshot, get_session_logs, get_session_report,
    get_session_traces, get_artifact_list
)
from ..resources.schema_resource import (
    get_api_schema, get_validation_schema, get_config_schema
)

class TestDOMResource:
    """Test cases for DOM Resource provider."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_dom_snapshot_success(self, sample_dom_content):
        """Test successful DOM snapshot retrieval."""
        page_id = "test-page-001"
        
        # Mock DOM storage/retrieval
        with patch('src.backend.mcp.resources.dom_resource.fetch_page_dom') as mock_fetch:
            mock_fetch.return_value = sample_dom_content
            
            result = await get_dom_snapshot(page_id)
            
            assert isinstance(result, str)
            assert "<html>" in result
            assert "test-form" in result
            assert "login-btn" in result
            mock_fetch.assert_called_once_with(page_id)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_dom_elements_success(self, sample_dom_content):
        """Test DOM elements extraction."""
        page_id = "test-page-001"
        
        with patch('src.backend.mcp.resources.dom_resource.fetch_page_dom') as mock_fetch:
            mock_fetch.return_value = sample_dom_content
            
            result = await get_dom_elements(page_id)
            
            assert isinstance(result, str)
            result_data = json.loads(result)
            
            assert "interactive_elements" in result_data
            assert "forms" in result_data
            assert "links" in result_data
            
            # Should find the form elements
            interactive = result_data["interactive_elements"]
            assert any("username" in elem.get("id", "") for elem in interactive)
            assert any("login-btn" in elem.get("id", "") for elem in interactive)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_dom_forms_success(self, sample_dom_content):
        """Test DOM forms extraction."""
        page_id = "test-page-001"
        
        with patch('src.backend.mcp.resources.dom_resource.fetch_page_dom') as mock_fetch:
            mock_fetch.return_value = sample_dom_content
            
            result = await get_dom_forms(page_id)
            
            assert isinstance(result, str)
            result_data = json.loads(result)
            
            assert "forms" in result_data
            forms = result_data["forms"]
            assert len(forms) >= 1
            
            # Check form structure
            form = forms[0]
            assert "id" in form
            assert "fields" in form
            assert "test-form" in form["id"]
            
            # Check form fields
            fields = form["fields"]
            assert any("username" in field.get("name", "") for field in fields)
            assert any("password" in field.get("name", "") for field in fields)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_dom_snapshot_not_found(self):
        """Test DOM snapshot for non-existent page."""
        page_id = "non-existent-page"
        
        with patch('src.backend.mcp.resources.dom_resource.fetch_page_dom') as mock_fetch:
            mock_fetch.side_effect = FileNotFoundError("Page not found")
            
            result = await get_dom_snapshot(page_id)
            
            assert isinstance(result, str)
            assert "error" in result.lower() or "not found" in result.lower()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_dom_elements_empty_page(self):
        """Test DOM elements extraction for empty page."""
        page_id = "empty-page"
        empty_dom = "<html><head></head><body></body></html>"
        
        with patch('src.backend.mcp.resources.dom_resource.fetch_page_dom') as mock_fetch:
            mock_fetch.return_value = empty_dom
            
            result = await get_dom_elements(page_id)
            
            assert isinstance(result, str)
            result_data = json.loads(result)
            
            assert "interactive_elements" in result_data
            assert len(result_data["interactive_elements"]) == 0

class TestExecutionContextResource:
    """Test cases for Execution Context Resource provider."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_execution_state_success(self, sample_session_context):
        """Test execution state retrieval."""
        session_id = sample_session_context.session_id
        
        with patch('src.backend.mcp.resources.execution_context_resource.get_session_manager') as mock_manager:
            mock_session = MagicMock()
            mock_session.get_execution_state.return_value = {
                "current_test": "test_login_functionality",
                "step_count": 5,
                "status": "running",
                "start_time": "2025-01-09T12:00:00Z",
                "last_action": "click_element"
            }
            mock_manager.return_value.get_session.return_value = mock_session
            
            result = await get_execution_state(session_id)
            
            assert isinstance(result, str)
            result_data = json.loads(result)
            
            assert "current_test" in result_data
            assert "step_count" in result_data
            assert "status" in result_data
            assert result_data["current_test"] == "test_login_functionality"
            assert result_data["status"] == "running"
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_environment_config_success(self):
        """Test environment configuration retrieval."""
        config_type = "browser"
        
        with patch('src.backend.mcp.resources.execution_context_resource.get_environment_settings') as mock_settings:
            mock_settings.return_value = {
                "browser_type": "chromium",
                "headless": False,
                "viewport": {"width": 1920, "height": 1080},
                "user_agent": "Mozilla/5.0 (Test Browser)",
                "timeout": 30000
            }
            
            result = await get_environment_config(config_type)
            
            assert isinstance(result, str)
            result_data = json.loads(result)
            
            assert "browser_type" in result_data
            assert "viewport" in result_data
            assert result_data["browser_type"] == "chromium"
            assert result_data["viewport"]["width"] == 1920
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_test_runner_context_success(self):
        """Test test runner context retrieval."""
        runner_id = "pytest-runner-001"
        
        with patch('src.backend.mcp.resources.execution_context_resource.get_test_runner') as mock_runner:
            mock_runner.return_value = {
                "runner_type": "pytest",
                "version": "7.4.0",
                "parallel_workers": 4,
                "test_discovery": {
                    "total_tests": 150,
                    "selected_tests": 25,
                    "filtered_tests": 10
                },
                "plugins": ["pytest-html", "pytest-xdist"],
                "configuration": {
                    "collect_only": False,
                    "verbose": True,
                    "markers": ["unit", "integration"]
                }
            }
            
            result = await get_test_runner_context(runner_id)
            
            assert isinstance(result, str)
            result_data = json.loads(result)
            
            assert "runner_type" in result_data
            assert "test_discovery" in result_data
            assert "plugins" in result_data
            assert result_data["runner_type"] == "pytest"
            assert result_data["test_discovery"]["total_tests"] == 150
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_browser_context_success(self):
        """Test browser context retrieval."""
        browser_id = "chromium-context-001"
        
        with patch('src.backend.mcp.resources.execution_context_resource.get_browser_manager') as mock_browser:
            mock_context = MagicMock()
            mock_context.get_context_info.return_value = {
                "browser_type": "chromium",
                "version": "120.0.6099.109",
                "user_data_dir": "/tmp/test-profile",
                "incognito": True,
                "pages": [
                    {
                        "url": "https://example.com/login",
                        "title": "Login Page",
                        "load_state": "domcontentloaded"
                    }
                ],
                "cookies": 5,
                "local_storage_entries": 12
            }
            mock_browser.return_value.get_context.return_value = mock_context
            
            result = await get_browser_context(browser_id)
            
            assert isinstance(result, str)
            result_data = json.loads(result)
            
            assert "browser_type" in result_data
            assert "pages" in result_data
            assert "cookies" in result_data
            assert result_data["browser_type"] == "chromium"
            assert len(result_data["pages"]) == 1
            assert result_data["pages"][0]["url"] == "https://example.com/login"

class TestTestDataResource:
    """Test cases for Test Data Resource provider."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_test_dataset_success(self):
        """Test test dataset retrieval."""
        dataset_name = "user_credentials"
        
        with patch('src.backend.mcp.resources.test_data_resource.load_dataset') as mock_load:
            mock_load.return_value = {
                "dataset_name": "user_credentials",
                "version": "1.0",
                "description": "User login credentials for testing",
                "data": [
                    {"username": "admin", "password": "admin123", "role": "administrator"},
                    {"username": "user1", "password": "user123", "role": "standard_user"},
                    {"username": "guest", "password": "guest123", "role": "guest"}
                ],
                "metadata": {
                    "created_at": "2025-01-09T10:00:00Z",
                    "record_count": 3,
                    "schema_version": "v1"
                }
            }
            
            result = await get_test_dataset(dataset_name)
            
            assert isinstance(result, str)
            result_data = json.loads(result)
            
            assert "dataset_name" in result_data
            assert "data" in result_data
            assert "metadata" in result_data
            assert result_data["dataset_name"] == "user_credentials"
            assert len(result_data["data"]) == 3
            assert result_data["data"][0]["username"] == "admin"
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_test_fixtures_success(self):
        """Test test fixtures retrieval."""
        fixture_type = "api_responses"
        
        with patch('src.backend.mcp.resources.test_data_resource.load_fixtures') as mock_fixtures:
            mock_fixtures.return_value = {
                "fixture_type": "api_responses",
                "fixtures": {
                    "successful_login": {
                        "status_code": 200,
                        "response": {"token": "abc123", "user_id": "12345"},
                        "headers": {"Content-Type": "application/json"}
                    },
                    "failed_login": {
                        "status_code": 401,
                        "response": {"error": "Invalid credentials"},
                        "headers": {"Content-Type": "application/json"}
                    },
                    "server_error": {
                        "status_code": 500,
                        "response": {"error": "Internal server error"},
                        "headers": {"Content-Type": "application/json"}
                    }
                }
            }
            
            result = await get_test_fixtures(fixture_type)
            
            assert isinstance(result, str)
            result_data = json.loads(result)
            
            assert "fixture_type" in result_data
            assert "fixtures" in result_data
            assert "successful_login" in result_data["fixtures"]
            assert "failed_login" in result_data["fixtures"]
            assert result_data["fixtures"]["successful_login"]["status_code"] == 200
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_validation_data_success(self):
        """Test validation data retrieval."""
        validation_set = "form_validation"
        
        with patch('src.backend.mcp.resources.test_data_resource.load_validation_set') as mock_validation:
            mock_validation.return_value = {
                "validation_set": "form_validation",
                "test_cases": [
                    {
                        "case_name": "valid_email",
                        "input": "user@example.com",
                        "expected_result": "valid",
                        "validation_rules": ["email_format", "domain_check"]
                    },
                    {
                        "case_name": "invalid_email_format",
                        "input": "invalid-email",
                        "expected_result": "invalid",
                        "expected_error": "Invalid email format",
                        "validation_rules": ["email_format"]
                    },
                    {
                        "case_name": "empty_email",
                        "input": "",
                        "expected_result": "invalid",
                        "expected_error": "Email is required",
                        "validation_rules": ["required_field"]
                    }
                ]
            }
            
            result = await get_validation_data(validation_set)
            
            assert isinstance(result, str)
            result_data = json.loads(result)
            
            assert "validation_set" in result_data
            assert "test_cases" in result_data
            assert len(result_data["test_cases"]) == 3
            assert result_data["test_cases"][0]["case_name"] == "valid_email"
            assert result_data["test_cases"][1]["expected_error"] == "Invalid email format"
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_mock_data_success(self):
        """Test mock data generation."""
        data_type = "user_profiles"
        count = 5
        
        with patch('src.backend.mcp.resources.test_data_resource.generate_mock_data') as mock_generator:
            mock_generator.return_value = {
                "data_type": "user_profiles",
                "count": 5,
                "generated_data": [
                    {"id": 1, "name": "John Doe", "email": "john@example.com", "age": 30},
                    {"id": 2, "name": "Jane Smith", "email": "jane@example.com", "age": 25},
                    {"id": 3, "name": "Bob Johnson", "email": "bob@example.com", "age": 35},
                    {"id": 4, "name": "Alice Brown", "email": "alice@example.com", "age": 28},
                    {"id": 5, "name": "Charlie Wilson", "email": "charlie@example.com", "age": 32}
                ],
                "generation_timestamp": "2025-01-09T12:00:00Z"
            }
            
            result = await get_mock_data(data_type, count)
            
            assert isinstance(result, str)
            result_data = json.loads(result)
            
            assert "data_type" in result_data
            assert "count" in result_data
            assert "generated_data" in result_data
            assert len(result_data["generated_data"]) == 5
            assert result_data["generated_data"][0]["name"] == "John Doe"
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_filtered_dataset_success(self):
        """Test filtered dataset retrieval."""
        dataset_name = "user_accounts"
        filters = "role=admin&status=active"
        
        with patch('src.backend.mcp.resources.test_data_resource.filter_dataset') as mock_filter:
            mock_filter.return_value = {
                "dataset_name": "user_accounts",
                "filters_applied": {"role": "admin", "status": "active"},
                "total_records": 2,
                "filtered_data": [
                    {"id": 1, "username": "admin1", "role": "admin", "status": "active"},
                    {"id": 5, "username": "admin2", "role": "admin", "status": "active"}
                ]
            }
            
            result = await get_filtered_dataset(dataset_name, filters)
            
            assert isinstance(result, str)
            result_data = json.loads(result)
            
            assert "dataset_name" in result_data
            assert "filters_applied" in result_data
            assert "total_records" in result_data
            assert result_data["total_records"] == 2
            assert all(user["role"] == "admin" for user in result_data["filtered_data"])

class TestSessionArtifactResource:
    """Test cases for Session Artifact Resource provider."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_session_screenshot_success(self, temp_chromadb_path):
        """Test session screenshot retrieval."""
        session_id = "test-session-001"
        screenshot_id = "screenshot-001"
        
        # Create temporary screenshot file
        screenshot_path = temp_chromadb_path / "screenshots" / f"{screenshot_id}.png"
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        screenshot_path.write_bytes(b"fake-png-data")
        
        with patch('src.backend.mcp.resources.session_artifact_resource.get_artifact_storage') as mock_storage:
            mock_storage.return_value.get_screenshot.return_value = {
                "screenshot_id": screenshot_id,
                "session_id": session_id,
                "timestamp": "2025-01-09T12:00:00Z",
                "file_path": str(screenshot_path),
                "file_size": 13,
                "format": "png",
                "dimensions": {"width": 1920, "height": 1080}
            }
            
            result = await get_session_screenshot(session_id, screenshot_id)
            
            assert isinstance(result, str)
            result_data = json.loads(result)
            
            assert "screenshot_id" in result_data
            assert "session_id" in result_data
            assert "timestamp" in result_data
            assert "dimensions" in result_data
            assert result_data["format"] == "png"
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_session_logs_success(self):
        """Test session logs retrieval."""
        session_id = "test-session-001"
        log_type = "execution"
        
        with patch('src.backend.mcp.resources.session_artifact_resource.get_log_manager') as mock_logs:
            mock_logs.return_value.get_session_logs.return_value = {
                "session_id": session_id,
                "log_type": log_type,
                "total_entries": 10,
                "logs": [
                    {
                        "timestamp": "2025-01-09T12:00:00Z",
                        "level": "INFO",
                        "message": "Test session started",
                        "component": "session_manager"
                    },
                    {
                        "timestamp": "2025-01-09T12:00:05Z",
                        "level": "DEBUG",
                        "message": "Navigating to login page",
                        "component": "browser_driver"
                    },
                    {
                        "timestamp": "2025-01-09T12:00:10Z",
                        "level": "INFO",
                        "message": "Element located: #username",
                        "component": "locator_service"
                    }
                ]
            }
            
            result = await get_session_logs(session_id, log_type)
            
            assert isinstance(result, str)
            result_data = json.loads(result)
            
            assert "session_id" in result_data
            assert "log_type" in result_data
            assert "total_entries" in result_data
            assert "logs" in result_data
            assert len(result_data["logs"]) == 3
            assert result_data["logs"][0]["message"] == "Test session started"
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_session_report_success(self):
        """Test session report retrieval."""
        session_id = "test-session-001"
        report_format = "json"
        
        with patch('src.backend.mcp.resources.session_artifact_resource.get_report_generator') as mock_report:
            mock_report.return_value.generate_session_report.return_value = {
                "session_id": session_id,
                "report_format": report_format,
                "generated_at": "2025-01-09T12:30:00Z",
                "summary": {
                    "total_tests": 5,
                    "passed": 4,
                    "failed": 1,
                    "skipped": 0,
                    "duration": "2m 30s"
                },
                "test_results": [
                    {"test_name": "test_login", "status": "passed", "duration": "15s"},
                    {"test_name": "test_logout", "status": "passed", "duration": "10s"},
                    {"test_name": "test_invalid_login", "status": "failed", "duration": "20s", "error": "Timeout"},
                    {"test_name": "test_profile_update", "status": "passed", "duration": "25s"},
                    {"test_name": "test_password_change", "status": "passed", "duration": "18s"}
                ]
            }
            
            result = await get_session_report(session_id, report_format)
            
            assert isinstance(result, str)
            result_data = json.loads(result)
            
            assert "session_id" in result_data
            assert "summary" in result_data
            assert "test_results" in result_data
            assert result_data["summary"]["total_tests"] == 5
            assert result_data["summary"]["passed"] == 4
            assert len(result_data["test_results"]) == 5
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_session_traces_success(self):
        """Test session traces retrieval."""
        session_id = "test-session-001"
        trace_type = "network"
        
        with patch('src.backend.mcp.resources.session_artifact_resource.get_trace_collector') as mock_trace:
            mock_trace.return_value.get_traces.return_value = {
                "session_id": session_id,
                "trace_type": trace_type,
                "collection_start": "2025-01-09T12:00:00Z",
                "collection_end": "2025-01-09T12:30:00Z",
                "traces": [
                    {
                        "timestamp": "2025-01-09T12:00:05Z",
                        "type": "request",
                        "url": "https://example.com/api/login",
                        "method": "POST",
                        "status": 200,
                        "duration": "150ms"
                    },
                    {
                        "timestamp": "2025-01-09T12:00:15Z",
                        "type": "request",
                        "url": "https://example.com/api/profile",
                        "method": "GET",
                        "status": 200,
                        "duration": "80ms"
                    }
                ]
            }
            
            result = await get_session_traces(session_id, trace_type)
            
            assert isinstance(result, str)
            result_data = json.loads(result)
            
            assert "session_id" in result_data
            assert "trace_type" in result_data
            assert "traces" in result_data
            assert len(result_data["traces"]) == 2
            assert result_data["traces"][0]["url"] == "https://example.com/api/login"

class TestSchemaResource:
    """Test cases for Schema Resource provider."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_api_schema_success(self):
        """Test API schema retrieval."""
        api_name = "user_management"
        
        with patch('src.backend.mcp.resources.schema_resource.load_api_schema') as mock_schema:
            mock_schema.return_value = {
                "api_name": "user_management",
                "version": "v1",
                "base_url": "https://api.example.com/v1",
                "endpoints": [
                    {
                        "path": "/users",
                        "method": "GET",
                        "description": "List all users",
                        "parameters": [
                            {"name": "page", "type": "integer", "required": False},
                            {"name": "limit", "type": "integer", "required": False}
                        ],
                        "responses": {
                            "200": {"description": "Users list", "schema": {"type": "array"}}
                        }
                    },
                    {
                        "path": "/users",
                        "method": "POST",
                        "description": "Create new user",
                        "request_body": {
                            "required": True,
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "username": {"type": "string"},
                                    "email": {"type": "string", "format": "email"}
                                }
                            }
                        }
                    }
                ]
            }
            
            result = await get_api_schema(api_name)
            
            assert isinstance(result, str)
            result_data = json.loads(result)
            
            assert "api_name" in result_data
            assert "endpoints" in result_data
            assert len(result_data["endpoints"]) == 2
            assert result_data["endpoints"][0]["path"] == "/users"
            assert result_data["endpoints"][0]["method"] == "GET"
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_validation_schema_success(self):
        """Test validation schema retrieval."""
        schema_name = "user_registration"
        
        with patch('src.backend.mcp.resources.schema_resource.load_validation_schema') as mock_schema:
            mock_schema.return_value = {
                "schema_name": "user_registration",
                "schema_version": "1.0",
                "type": "object",
                "required": ["username", "email", "password"],
                "properties": {
                    "username": {
                        "type": "string",
                        "minLength": 3,
                        "maxLength": 50,
                        "pattern": "^[a-zA-Z0-9_]+$"
                    },
                    "email": {
                        "type": "string",
                        "format": "email",
                        "maxLength": 255
                    },
                    "password": {
                        "type": "string",
                        "minLength": 8,
                        "pattern": "^(?=.*[a-z])(?=.*[A-Z])(?=.*\\d)"
                    },
                    "age": {
                        "type": "integer",
                        "minimum": 13,
                        "maximum": 150
                    }
                }
            }
            
            result = await get_validation_schema(schema_name)
            
            assert isinstance(result, str)
            result_data = json.loads(result)
            
            assert "schema_name" in result_data
            assert "properties" in result_data
            assert "required" in result_data
            assert "username" in result_data["properties"]
            assert "email" in result_data["properties"]
            assert result_data["properties"]["username"]["minLength"] == 3
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_config_schema_success(self):
        """Test configuration schema retrieval."""
        config_type = "test_environment"
        
        with patch('src.backend.mcp.resources.schema_resource.load_config_schema') as mock_schema:
            mock_schema.return_value = {
                "config_type": "test_environment",
                "schema_version": "2.0",
                "description": "Test environment configuration schema",
                "type": "object",
                "required": ["browser_config", "test_data_config"],
                "properties": {
                    "browser_config": {
                        "type": "object",
                        "properties": {
                            "browser_type": {"type": "string", "enum": ["chromium", "firefox", "webkit"]},
                            "headless": {"type": "boolean", "default": True},
                            "viewport": {
                                "type": "object",
                                "properties": {
                                    "width": {"type": "integer", "default": 1920},
                                    "height": {"type": "integer", "default": 1080}
                                }
                            }
                        }
                    },
                    "test_data_config": {
                        "type": "object",
                        "properties": {
                            "data_source": {"type": "string", "enum": ["file", "database", "api"]},
                            "refresh_interval": {"type": "integer", "default": 300}
                        }
                    }
                }
            }
            
            result = await get_config_schema(config_type)
            
            assert isinstance(result, str)
            result_data = json.loads(result)
            
            assert "config_type" in result_data
            assert "properties" in result_data
            assert "browser_config" in result_data["properties"]
            assert "test_data_config" in result_data["properties"]
            browser_config = result_data["properties"]["browser_config"]
            assert "browser_type" in browser_config["properties"]
            assert "chromium" in browser_config["properties"]["browser_type"]["enum"]

# Integration Tests
class TestResourcesIntegration:
    """Integration tests for resources working together."""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_resources_cross_reference(self, sample_session_context):
        """Test resources can reference each other's data."""
        session_id = sample_session_context.session_id
        
        # Mock execution context to reference session artifacts
        with patch('src.backend.mcp.resources.execution_context_resource.get_session_manager') as mock_exec, \
             patch('src.backend.mcp.resources.session_artifact_resource.get_artifact_storage') as mock_artifacts:
            
            # Setup execution context with artifact references
            mock_session = MagicMock()
            mock_session.get_execution_state.return_value = {
                "current_test": "test_login",
                "artifacts": ["screenshot-001", "log-execution"],
                "status": "running"
            }
            mock_exec.return_value.get_session.return_value = mock_session
            
            # Setup artifact data
            mock_artifacts.return_value.get_artifact_list.return_value = {
                "session_id": session_id,
                "artifacts": [
                    {"id": "screenshot-001", "type": "screenshot", "timestamp": "2025-01-09T12:00:00Z"},
                    {"id": "log-execution", "type": "logs", "timestamp": "2025-01-09T12:00:00Z"}
                ]
            }
            
            # Get execution state
            exec_result = await get_execution_state(session_id)
            exec_data = json.loads(exec_result)
            
            # Get artifact list
            artifacts_result = await get_artifact_list(session_id)
            artifacts_data = json.loads(artifacts_result)
            
            # Verify cross-reference
            assert "artifacts" in exec_data
            assert len(artifacts_data["artifacts"]) == 2
            assert exec_data["artifacts"][0] in [a["id"] for a in artifacts_data["artifacts"]]

# Performance Tests
class TestResourcesPerformance:
    """Performance tests for resource providers."""
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_resource_response_time(self, test_utils, performance_test_config):
        """Test resource response times are acceptable."""
        # Test DOM resource performance
        page_id = "test-page"
        simple_dom = "<html><body><div>Test</div></body></html>"
        
        with patch('src.backend.mcp.resources.dom_resource.fetch_page_dom') as mock_fetch:
            mock_fetch.return_value = simple_dom
            
            result, response_time = await test_utils.measure_response_time(get_dom_snapshot, page_id)
            
            assert isinstance(result, str)
            assert response_time < performance_test_config["acceptable_response_time"]
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_concurrent_resource_access(self, performance_test_config):
        """Test concurrent resource access performance."""
        import asyncio
        
        # Create multiple resource requests
        page_ids = [f"page-{i}" for i in range(performance_test_config["concurrent_requests"])]
        simple_dom = "<html><body><div>Test</div></body></html>"
        
        with patch('src.backend.mcp.resources.dom_resource.fetch_page_dom') as mock_fetch:
            mock_fetch.return_value = simple_dom
            
            # Execute concurrently
            start_time = asyncio.get_event_loop().time()
            results = await asyncio.gather(*[get_dom_snapshot(page_id) for page_id in page_ids])
            end_time = asyncio.get_event_loop().time()
            
            # Verify all responses
            assert len(results) == performance_test_config["concurrent_requests"]
            for result in results:
                assert isinstance(result, str)
                assert "<html>" in result
            
            # Check total time
            total_time = end_time - start_time
            assert total_time < performance_test_config["acceptable_response_time"] * 2

# Error Handling Tests
class TestResourcesErrorHandling:
    """Error handling tests for resource providers."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_resources_handle_missing_data(self):
        """Test resources handle missing data gracefully."""
        # Test with non-existent session
        session_id = "non-existent-session"
        
        with patch('src.backend.mcp.resources.execution_context_resource.get_session_manager') as mock_manager:
            mock_manager.return_value.get_session.return_value = None
            
            result = await get_execution_state(session_id)
            
            assert isinstance(result, str)
            # Should return error information
            assert "error" in result.lower() or "not found" in result.lower()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_resources_handle_invalid_parameters(self):
        """Test resources handle invalid parameters gracefully."""
        # Test with invalid dataset name
        invalid_dataset = ""
        
        with patch('src.backend.mcp.resources.test_data_resource.load_dataset') as mock_load:
            mock_load.side_effect = ValueError("Invalid dataset name")
            
            result = await get_test_dataset(invalid_dataset)
            
            assert isinstance(result, str)
            # Should handle error gracefully
            result_data = json.loads(result)
            assert "error" in result_data or "invalid" in str(result_data).lower()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_resources_handle_connection_errors(self):
        """Test resources handle connection errors gracefully."""
        # Test with connection failure
        api_name = "test-api"
        
        with patch('src.backend.mcp.resources.schema_resource.load_api_schema') as mock_schema:
            mock_schema.side_effect = ConnectionError("Connection refused")
            
            result = await get_api_schema(api_name)
            
            assert isinstance(result, str)
            # Should return error information
            assert "error" in result.lower() or "connection" in result.lower()

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 
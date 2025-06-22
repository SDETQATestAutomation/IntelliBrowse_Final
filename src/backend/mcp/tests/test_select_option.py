"""
Test suite for Select Option Tool.

This module contains comprehensive tests for the select_option tool functionality,
including unit tests, integration tests, and error handling validation.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

# Import the tool function
try:
    from tools.select_option import select_option
except ImportError:
    # Fallback for when running directly from mcp directory
    from tools.select_option import select_option
try:
    from schemas.tools.select_option_schemas import SelectOptionRequest, SelectOptionResponse
except ImportError:
    # Fallback for when running directly from mcp directory
    from schemas.tools.select_option_schemas import SelectOptionRequest, SelectOptionResponse


class TestSelectOptionTool:
    """Test cases for select_option tool functionality."""
    
    @pytest.fixture
    def mock_page(self):
        """Create a mock Playwright page object."""
        page = AsyncMock()
        page.title.return_value = "Test Page"
        page.url = "https://example.com/test"
        page.wait_for_selector = AsyncMock()
        page.locator.return_value.get_attribute = AsyncMock()
        page.select_option = AsyncMock()
        page.locator.return_value.all = AsyncMock(return_value=[])
        return page
    
    @pytest.fixture
    def mock_browser_session(self, mock_page):
        """Create a mock browser session."""
        return {
            "session_12345": {
                "page": mock_page,
                "browser": AsyncMock(),
                "context": AsyncMock()
            }
        }
    
    @pytest.mark.asyncio
    async def test_select_option_success_by_value(self, mock_browser_session, mock_page):
        """Test successful option selection by value."""
        # Mock browser sessions
        with patch('src.backend.mcp.tools.select_option.browser_sessions', mock_browser_session):
            # Mock successful element detection and selection
            mock_page.locator.return_value.get_attribute.return_value = "SELECT"
            mock_page.locator.return_value.all.return_value = [MagicMock() for _ in range(3)]
            
            # Mock selected option elements
            mock_selected_option = AsyncMock()
            mock_selected_option.get_attribute.return_value = "US"
            mock_selected_option.text_content.return_value = "United States"
            mock_selected_option.evaluate.return_value = 1
            mock_page.locator.return_value.all.return_value = [mock_selected_option]
            
            result = await select_option(
                session_id="session_12345",
                selector="#country-select",
                value="US",
                timeout_ms=5000
            )
            
            assert result["success"] is True
            assert result["selector"] == "#country-select"
            assert "US" in result["selected_values"]
            assert "United States" in result["selected_labels"]
            assert 1 in result["selected_indices"]
            assert result["elapsed_ms"] > 0
            
            # Verify Playwright calls
            mock_page.wait_for_selector.assert_called_once_with("#country-select", timeout=5000, state="visible")
            mock_page.select_option.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_select_option_success_by_label(self, mock_browser_session, mock_page):
        """Test successful option selection by label."""
        with patch('src.backend.mcp.tools.select_option.browser_sessions', mock_browser_session):
            # Mock successful element detection and selection
            mock_page.locator.return_value.get_attribute.return_value = "SELECT"
            
            result = await select_option(
                session_id="session_12345",
                selector="#country-select",
                label="United States",
                timeout_ms=5000
            )
            
            assert result["success"] is True
            assert result["selector"] == "#country-select"
            
            # Verify selection was called with label
            mock_page.select_option.assert_called_once()
            call_args = mock_page.select_option.call_args[0]
            assert call_args[0] == "#country-select"
            assert {"label": "United States"} in call_args[1]
    
    @pytest.mark.asyncio
    async def test_select_option_success_by_index(self, mock_browser_session, mock_page):
        """Test successful option selection by index."""
        with patch('src.backend.mcp.tools.select_option.browser_sessions', mock_browser_session):
            # Mock successful element detection and selection
            mock_page.locator.return_value.get_attribute.return_value = "SELECT"
            
            result = await select_option(
                session_id="session_12345",
                selector="#country-select",
                index=2,
                timeout_ms=5000
            )
            
            assert result["success"] is True
            assert result["selector"] == "#country-select"
            
            # Verify selection was called with index
            mock_page.select_option.assert_called_once()
            call_args = mock_page.select_option.call_args[0]
            assert call_args[0] == "#country-select"
            assert {"index": 2} in call_args[1]
    
    @pytest.mark.asyncio
    async def test_select_option_multiple_selection(self, mock_browser_session, mock_page):
        """Test multiple option selection."""
        with patch('src.backend.mcp.tools.select_option.browser_sessions', mock_browser_session):
            # Mock multiple select element
            mock_page.locator.return_value.get_attribute.side_effect = lambda attr: "SELECT" if attr == "tagName" else True
            
            result = await select_option(
                session_id="session_12345",
                selector="#multi-select",
                value=["option1", "option2"],
                multiple=True,
                timeout_ms=5000
            )
            
            assert result["success"] is True
            assert result["selector"] == "#multi-select"
            
            # Verify selection was called with multiple values
            mock_page.select_option.assert_called_once()
            call_args = mock_page.select_option.call_args[0]
            assert call_args[0] == "#multi-select"
            expected_options = [{"value": "option1"}, {"value": "option2"}]
            assert all(opt in call_args[1] for opt in expected_options)
    
    @pytest.mark.asyncio
    async def test_select_option_session_not_found(self):
        """Test error handling when session is not found."""
        with patch('src.backend.mcp.tools.select_option.browser_sessions', {}):
            result = await select_option(
                session_id="nonexistent_session",
                selector="#country-select",
                value="US"
            )
            
            assert result["success"] is False
            assert "not found" in result["message"].lower()
            assert result["metadata"]["error"] == "SESSION_NOT_FOUND"
    
    @pytest.mark.asyncio
    async def test_select_option_no_selection_criteria(self, mock_browser_session):
        """Test error handling when no selection criteria is provided."""
        with patch('src.backend.mcp.tools.select_option.browser_sessions', mock_browser_session):
            result = await select_option(
                session_id="session_12345",
                selector="#country-select"
                # No value, label, or index provided
            )
            
            assert result["success"] is False
            assert "selection criterion" in result["message"].lower()
            assert result["metadata"]["error"] == "NO_SELECTION_CRITERIA"
    
    @pytest.mark.asyncio
    async def test_select_option_element_not_visible(self, mock_browser_session, mock_page):
        """Test error handling when element is not visible."""
        with patch('src.backend.mcp.tools.select_option.browser_sessions', mock_browser_session):
            # Mock timeout error
            from playwright.async_api import TimeoutError as PlaywrightTimeoutError
            mock_page.wait_for_selector.side_effect = PlaywrightTimeoutError("Element not found")
            
            result = await select_option(
                session_id="session_12345",
                selector="#country-select",
                value="US",
                timeout_ms=5000
            )
            
            assert result["success"] is False
            assert "not found or not visible" in result["message"].lower()
            assert result["metadata"]["error"] == "ELEMENT_NOT_VISIBLE"
            assert result["metadata"]["timeout_ms"] == 5000
    
    @pytest.mark.asyncio
    async def test_select_option_not_select_element(self, mock_browser_session, mock_page):
        """Test error handling when element is not a select element."""
        with patch('src.backend.mcp.tools.select_option.browser_sessions', mock_browser_session):
            # Mock element as non-select
            mock_page.locator.return_value.get_attribute.return_value = "DIV"
            
            result = await select_option(
                session_id="session_12345",
                selector="#not-select",
                value="US"
            )
            
            assert result["success"] is False
            assert "not a select element" in result["message"].lower()
            assert result["metadata"]["error"] == "NOT_SELECT_ELEMENT"
            assert result["metadata"]["actual_tag"] == "DIV"
    
    @pytest.mark.asyncio
    async def test_select_option_page_not_active(self, mock_browser_session, mock_page):
        """Test error handling when page is not active."""
        with patch('src.backend.mcp.tools.select_option.browser_sessions', mock_browser_session):
            # Mock page title call failure
            from playwright.async_api import Error as PlaywrightError
            mock_page.title.side_effect = PlaywrightError("Page closed")
            
            result = await select_option(
                session_id="session_12345",
                selector="#country-select",
                value="US"
            )
            
            assert result["success"] is False
            assert "not active or accessible" in result["message"].lower()
            assert result["metadata"]["error"] == "PAGE_NOT_ACTIVE"
    
    @pytest.mark.asyncio
    async def test_select_option_selection_failed(self, mock_browser_session, mock_page):
        """Test error handling when selection operation fails."""
        with patch('src.backend.mcp.tools.select_option.browser_sessions', mock_browser_session):
            # Mock successful element detection but failed selection
            mock_page.locator.return_value.get_attribute.return_value = "SELECT"
            
            from playwright.async_api import Error as PlaywrightError
            mock_page.select_option.side_effect = PlaywrightError("Selection failed")
            
            result = await select_option(
                session_id="session_12345",
                selector="#country-select",
                value="US"
            )
            
            assert result["success"] is False
            assert "failed to select option" in result["message"].lower()
            assert result["metadata"]["error"] == "SELECTION_FAILED"
    
    def test_select_option_request_schema_validation(self):
        """Test SelectOptionRequest schema validation."""
        # Valid request
        request = SelectOptionRequest(
            session_id="session_123",
            selector="#select",
            value="option1",
            timeout_ms=5000,
            multiple=False
        )
        assert request.session_id == "session_123"
        assert request.selector == "#select"
        assert request.value == "option1"
        assert request.timeout_ms == 5000
        assert request.multiple is False
        
        # Request with multiple values
        request_multi = SelectOptionRequest(
            session_id="session_123",
            selector="#select",
            value=["option1", "option2"],
            multiple=True
        )
        assert request_multi.value == ["option1", "option2"]
        assert request_multi.multiple is True
    
    def test_select_option_response_schema_validation(self):
        """Test SelectOptionResponse schema validation."""
        response = SelectOptionResponse(
            success=True,
            selector="#country-select",
            message="Option selected successfully",
            selected_values=["US"],
            selected_labels=["United States"],
            selected_indices=[1],
            elapsed_ms=150,
            metadata={"total_options": 195}
        )
        
        assert response.success is True
        assert response.selector == "#country-select"
        assert response.selected_values == ["US"]
        assert response.selected_labels == ["United States"]
        assert response.selected_indices == [1]
        assert response.elapsed_ms == 150
        assert response.metadata["total_options"] == 195


if __name__ == "__main__":
    pytest.main([__file__]) 
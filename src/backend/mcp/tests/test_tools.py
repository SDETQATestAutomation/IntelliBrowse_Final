"""
Unit tests for MCP Server Tools
Testing all 5 core tools: BDD Generator, Locator Generator, Step Generator, Selector Healer, Debug Analyzer
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Dict, Any

# Tool imports
from ..tools.bdd_generator import generate_bdd_scenarios
from ..tools.locator_generator import generate_locator
from ..tools.step_generator import generate_step
from ..tools.selector_healer import heal_selector
from ..tools.debug_analyzer import analyze_debug_info

# Schema imports
from ..schemas.tools.bdd_generator_schemas import BDDGeneratorRequest, BDDGeneratorResponse
from ..schemas.tools.locator_generator_schemas import LocatorGeneratorRequest, LocatorGeneratorResponse
from ..schemas.tools.step_generator_schemas import StepGeneratorRequest, StepGeneratorResponse
from ..schemas.tools.selector_healer_schemas import SelectorHealerRequest, SelectorHealerResponse
from ..schemas.tools.debug_analyzer_schemas import DebugAnalyzerRequest, DebugAnalyzerResponse

class TestBDDGenerator:
    """Test cases for BDD Generator tool."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_bdd_scenarios_success(self, sample_bdd_request, mock_openai_client, mock_openai_response):
        """Test successful BDD scenario generation."""
        # Mock OpenAI response
        mock_openai_response["choices"][0]["message"]["content"] = """
        Feature: User Authentication
        
        Scenario: Successful user login
            Given the user is on the login page
            When the user enters valid credentials
            And clicks the login button
            Then the user should be redirected to the dashboard
            And see a welcome message
        
        Scenario: Failed login with invalid credentials
            Given the user is on the login page
            When the user enters invalid credentials
            And clicks the login button
            Then an error message should be displayed
            And the user should remain on the login page
        """
        
        mock_openai_client.chat.completions.create.return_value = MagicMock(**mock_openai_response)
        
        with patch('openai.AsyncOpenAI') as mock_client:
            mock_client.return_value = mock_openai_client
            
            response = await generate_bdd_scenarios(sample_bdd_request)
            
            assert isinstance(response, BDDGeneratorResponse)
            assert response.feature_name
            assert len(response.scenarios) >= 1
            assert response.confidence > 0.0
            assert response.gherkin_syntax
            
            # Verify OpenAI was called
            mock_openai_client.chat.completions.create.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_bdd_scenarios_with_context(self, mock_openai_client, mock_openai_response):
        """Test BDD generation with additional context."""
        request = BDDGeneratorRequest(
            user_story="As an admin, I want to manage user accounts",
            context="Admin panel functionality",
            additional_requirements=["Role-based access", "Audit logging"]
        )
        
        mock_openai_response["choices"][0]["message"]["content"] = """
        Feature: Admin User Management
        
        Scenario: Admin creates new user account
            Given the admin is logged in
            When the admin creates a new user account
            Then the account should be created successfully
            And audit log should record the action
        """
        
        mock_openai_client.chat.completions.create.return_value = MagicMock(**mock_openai_response)
        
        with patch('openai.AsyncOpenAI') as mock_client:
            mock_client.return_value = mock_openai_client
            
            response = await generate_bdd_scenarios(request)
            
            assert isinstance(response, BDDGeneratorResponse)
            assert "admin" in response.feature_name.lower()
            assert response.confidence > 0.0
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_bdd_scenarios_api_error(self, sample_bdd_request, mock_openai_client):
        """Test BDD generation with API error."""
        mock_openai_client.chat.completions.create.side_effect = Exception("API Error")
        
        with patch('openai.AsyncOpenAI') as mock_client:
            mock_client.return_value = mock_openai_client
            
            response = await generate_bdd_scenarios(sample_bdd_request)
            
            assert isinstance(response, BDDGeneratorResponse)
            assert response.confidence == 0.0
            assert "error" in response.suggestions[0].lower()

class TestLocatorGenerator:
    """Test cases for Locator Generator tool."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_locator_with_id_success(self, test_utils):
        """Test locator generation with ID strategy."""
        request = LocatorGeneratorRequest(
            dom_content='<button id="submit-btn" class="primary">Submit</button>',
            target_description="Submit button",
            strategy="id",
            context="Form submission"
        )
        
        response = await generate_locator(request)
        
        assert isinstance(response, LocatorGeneratorResponse)
        test_utils.assert_confidence_score(response, 0.7, 1.0)
        assert "submit-btn" in response.primary_locator
        assert response.locator_type in ["id", "css_selector"]
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_locator_with_data_testid(self, test_utils):
        """Test locator generation with data-testid."""
        request = LocatorGeneratorRequest(
            dom_content='<button data-testid="login-button" class="btn">Login</button>',
            target_description="Login button",
            strategy="auto",
            context="Authentication"
        )
        
        response = await generate_locator(request)
        
        assert isinstance(response, LocatorGeneratorResponse)
        test_utils.assert_confidence_score(response, 0.8, 1.0)  # data-testid should have high confidence
        assert "login-button" in response.primary_locator
        assert len(response.alternative_locators) >= 1
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_locator_complex_element(self, test_utils):
        """Test locator generation for complex element."""
        request = LocatorGeneratorRequest(
            dom_content='''
            <div class="form-group">
                <label>Username</label>
                <input type="text" name="username" placeholder="Enter username" required>
            </div>
            ''',
            target_description="Username input field",
            strategy="auto",
            context="Login form"
        )
        
        response = await generate_locator(request)
        
        assert isinstance(response, LocatorGeneratorResponse)
        test_utils.assert_confidence_score(response)
        assert response.primary_locator
        assert response.locator_explanation
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_locator_ai_fallback(self, test_utils, mock_openai_client, mock_openai_response):
        """Test AI fallback when rule-based approach fails."""
        request = LocatorGeneratorRequest(
            dom_content='<div><span>Click me</span></div>',
            target_description="Clickable text",
            strategy="auto",
            context="Complex element"
        )
        
        mock_openai_response["choices"][0]["message"]["content"] = "span:contains('Click me')"
        mock_openai_client.chat.completions.create.return_value = MagicMock(**mock_openai_response)
        
        with patch('openai.AsyncOpenAI') as mock_client:
            mock_client.return_value = mock_openai_client
            
            response = await generate_locator(request)
            
            assert isinstance(response, LocatorGeneratorResponse)
            test_utils.assert_confidence_score(response)
            assert response.primary_locator

class TestStepGenerator:
    """Test cases for Step Generator tool."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_step_action_type(self, test_utils, mock_openai_client, mock_openai_response):
        """Test step generation for action type."""
        request = StepGeneratorRequest(
            action_description="Click the submit button to complete the form",
            context="Form submission workflow",
            step_type="action",
            target_info="Submit button with ID 'submit-btn'"
        )
        
        mock_openai_response["choices"][0]["message"]["content"] = """
        **Gherkin Step**: When I click the submit button
        **Automation Code**: driver.find_element(By.ID, "submit-btn").click()
        **Framework**: Selenium WebDriver
        """
        
        mock_openai_client.chat.completions.create.return_value = MagicMock(**mock_openai_response)
        
        with patch('openai.AsyncOpenAI') as mock_client:
            mock_client.return_value = mock_openai_client
            
            response = await generate_step(request)
            
            assert isinstance(response, StepGeneratorResponse)
            test_utils.assert_confidence_score(response)
            assert response.gherkin_step
            assert response.automation_code
            assert "click" in response.gherkin_step.lower()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_step_verification_type(self, test_utils, mock_openai_client, mock_openai_response):
        """Test step generation for verification type."""
        request = StepGeneratorRequest(
            action_description="Verify that the success message is displayed",
            context="Form submission verification",
            step_type="verification",
            target_info="Success message container"
        )
        
        mock_openai_response["choices"][0]["message"]["content"] = """
        **Gherkin Step**: Then I should see the success message
        **Automation Code**: assert driver.find_element(By.CLASS_NAME, "success-message").is_displayed()
        **Framework**: Selenium with Assertions
        """
        
        mock_openai_client.chat.completions.create.return_value = MagicMock(**mock_openai_response)
        
        with patch('openai.AsyncOpenAI') as mock_client:
            mock_client.return_value = mock_openai_client
            
            response = await generate_step(request)
            
            assert isinstance(response, StepGeneratorResponse)
            test_utils.assert_confidence_score(response)
            assert response.gherkin_step
            assert "then" in response.gherkin_step.lower()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_step_with_alternatives(self, test_utils, mock_openai_client, mock_openai_response):
        """Test step generation with alternative implementations."""
        request = StepGeneratorRequest(
            action_description="Navigate to the user profile page",
            context="User profile navigation",
            step_type="navigation",
            target_info="Profile link in navigation menu"
        )
        
        mock_openai_response["choices"][0]["message"]["content"] = """
        **Gherkin Step**: When I navigate to the user profile page
        **Automation Code**: driver.get("https://example.com/profile")
        **Alternative 1**: driver.find_element(By.LINK_TEXT, "Profile").click()
        **Alternative 2**: driver.find_element(By.CSS_SELECTOR, "nav a[href*='profile']").click()
        """
        
        mock_openai_client.chat.completions.create.return_value = MagicMock(**mock_openai_response)
        
        with patch('openai.AsyncOpenAI') as mock_client:
            mock_client.return_value = mock_openai_client
            
            response = await generate_step(request)
            
            assert isinstance(response, StepGeneratorResponse)
            test_utils.assert_confidence_score(response)
            assert len(response.alternative_approaches) >= 1

class TestSelectorHealer:
    """Test cases for Selector Healer tool."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_heal_selector_simple_id_change(self, test_utils):
        """Test healing selector with simple ID change."""
        request = SelectorHealerRequest(
            broken_selector="input[id='old-username']",
            current_dom='<input type="text" id="new-username" name="username" placeholder="Username">',
            failure_context="Element not found during login test",
            original_intent="Username input field"
        )
        
        response = await heal_selector(request)
        
        assert isinstance(response, SelectorHealerResponse)
        test_utils.assert_confidence_score(response)
        assert "new-username" in response.healed_selector
        assert response.healing_strategy
        assert len(response.alternative_selectors) >= 1
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_heal_selector_attribute_change(self, test_utils):
        """Test healing selector with attribute changes."""
        request = SelectorHealerRequest(
            broken_selector="button[data-test='submit-btn']",
            current_dom='<button data-testid="submit-button" class="btn primary">Submit</button>',
            failure_context="Data attribute changed in new version",
            original_intent="Submit button"
        )
        
        response = await heal_selector(request)
        
        assert isinstance(response, SelectorHealerResponse)
        test_utils.assert_confidence_score(response)
        assert "submit-button" in response.healed_selector or "submit" in response.healed_selector.lower()
        assert response.confidence_explanation
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_heal_selector_ai_complex_case(self, test_utils, mock_openai_client, mock_openai_response):
        """Test AI-powered selector healing for complex cases."""
        request = SelectorHealerRequest(
            broken_selector="div.card:nth-child(3) > button",
            current_dom='''
            <div class="container">
                <div class="card-item">
                    <button>Action 1</button>
                </div>
                <div class="card-item">
                    <button>Action 2</button>
                </div>
                <div class="card-item featured">
                    <button data-action="primary">Primary Action</button>
                </div>
            </div>
            ''',
            failure_context="DOM structure changed, nth-child selector broke",
            original_intent="Third card's action button"
        )
        
        mock_openai_response["choices"][0]["message"]["content"] = """
        Based on the DOM analysis, the selector should target the featured card's button:
        **Healed Selector**: div.card-item.featured button
        **Alternative**: button[data-action="primary"]
        **Confidence**: 0.85
        """
        
        mock_openai_client.chat.completions.create.return_value = MagicMock(**mock_openai_response)
        
        with patch('openai.AsyncOpenAI') as mock_client:
            mock_client.return_value = mock_openai_client
            
            response = await heal_selector(request)
            
            assert isinstance(response, SelectorHealerResponse)
            test_utils.assert_confidence_score(response)
            assert "featured" in response.healed_selector or "primary" in response.healed_selector

class TestDebugAnalyzer:
    """Test cases for Debug Analyzer tool."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_analyze_element_not_found(self, test_utils, mock_openai_client, mock_openai_response):
        """Test debug analysis for element not found error."""
        request = DebugAnalyzerRequest(
            failure_type="element_not_found",
            error_message="NoSuchElementException: Unable to locate element: {'method': 'id', 'selector': 'submit-btn'}",
            test_context="Form submission test in login workflow",
            dom_snapshot='<button id="submit-button" class="primary">Submit</button>',
            execution_logs=[
                "Navigating to login page",
                "Entering username: testuser",
                "Entering password: ********",
                "Looking for submit button with ID 'submit-btn'",
                "ERROR: Element not found"
            ]
        )
        
        mock_openai_response["choices"][0]["message"]["content"] = """
        **Root Cause**: The submit button ID changed from 'submit-btn' to 'submit-button'
        **Fix Recommendation**: Update the selector to use id='submit-button'
        **Prevention**: Use data-testid attributes for more stable selectors
        **Impact**: High - blocks user authentication flow
        """
        
        mock_openai_client.chat.completions.create.return_value = MagicMock(**mock_openai_response)
        
        with patch('openai.AsyncOpenAI') as mock_client:
            mock_client.return_value = mock_openai_client
            
            response = await analyze_debug_info(request)
            
            assert isinstance(response, DebugAnalyzerResponse)
            test_utils.assert_confidence_score(response)
            assert response.root_cause
            assert response.fix_recommendations
            assert "submit-button" in response.fix_recommendations[0].lower()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_analyze_timeout_error(self, test_utils, mock_openai_client, mock_openai_response):
        """Test debug analysis for timeout error."""
        request = DebugAnalyzerRequest(
            failure_type="timeout",
            error_message="TimeoutException: Message: Element not clickable after 10 seconds",
            test_context="Waiting for page to load after form submission",
            dom_snapshot='<div class="loading-spinner active"></div>',
            execution_logs=[
                "Form submitted successfully",
                "Waiting for page transition",
                "Loading spinner still visible",
                "TIMEOUT: Element not clickable after 10 seconds"
            ]
        )
        
        mock_openai_response["choices"][0]["message"]["content"] = """
        **Root Cause**: Page loading takes longer than expected, loading spinner still active
        **Fix Recommendation**: Increase timeout or wait for loading spinner to disappear
        **Prevention**: Use explicit wait conditions for loading states
        **Performance**: Check for slow API responses or network issues
        """
        
        mock_openai_client.chat.completions.create.return_value = MagicMock(**mock_openai_response)
        
        with patch('openai.AsyncOpenAI') as mock_client:
            mock_client.return_value = mock_openai_client
            
            response = await analyze_debug_info(request)
            
            assert isinstance(response, DebugAnalyzerResponse)
            test_utils.assert_confidence_score(response)
            assert response.performance_impact
            assert "timeout" in response.root_cause.lower() or "loading" in response.root_cause.lower()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_analyze_with_suggestions(self, test_utils, mock_openai_client, mock_openai_response):
        """Test debug analysis with improvement suggestions."""
        request = DebugAnalyzerRequest(
            failure_type="assertion_error",
            error_message="AssertionError: Expected 'Welcome John' but got 'Welcome Guest'",
            test_context="User profile display after login",
            dom_snapshot='<div class="welcome-message">Welcome Guest</div>',
            execution_logs=[
                "User logged in successfully",
                "Navigating to profile page",
                "Checking welcome message",
                "ASSERTION FAILED: Expected 'Welcome John' but got 'Welcome Guest'"
            ]
        )
        
        mock_openai_response["choices"][0]["message"]["content"] = """
        **Root Cause**: Session/authentication issue - user not properly authenticated
        **Fix Recommendation**: Verify session token is valid and user data is loaded
        **Prevention**: Add session validation before profile page tests
        **Test Improvement**: Add explicit login verification step
        """
        
        mock_openai_client.chat.completions.create.return_value = MagicMock(**mock_openai_response)
        
        with patch('openai.AsyncOpenAI') as mock_client:
            mock_client.return_value = mock_openai_client
            
            response = await analyze_debug_info(request)
            
            assert isinstance(response, DebugAnalyzerResponse)
            test_utils.assert_confidence_score(response)
            assert len(response.improvement_suggestions) >= 1
            assert response.prevention_measures

# Integration Tests
class TestToolsIntegration:
    """Integration tests for tools working together."""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_tools_workflow_integration(self, test_utils, mock_openai_client, mock_openai_response):
        """Test a complete workflow using multiple tools."""
        # Mock OpenAI responses for different tools
        mock_openai_client.chat.completions.create.return_value = MagicMock(**mock_openai_response)
        
        with patch('openai.AsyncOpenAI') as mock_client:
            mock_client.return_value = mock_openai_client
            
            # 1. Generate BDD scenario
            bdd_request = BDDGeneratorRequest(
                user_story="As a user, I want to update my profile",
                context="Profile management",
                additional_requirements=["Data validation"]
            )
            bdd_response = await generate_bdd_scenarios(bdd_request)
            assert isinstance(bdd_response, BDDGeneratorResponse)
            
            # 2. Generate locator for form element
            locator_request = LocatorGeneratorRequest(
                dom_content='<input type="text" id="profile-name" name="name">',
                target_description="Profile name input",
                strategy="auto",
                context="Profile form"
            )
            locator_response = await generate_locator(locator_request)
            assert isinstance(locator_response, LocatorGeneratorResponse)
            
            # 3. Generate test step
            step_request = StepGeneratorRequest(
                action_description="Enter new name in profile form",
                context="Profile update workflow",
                step_type="action",
                target_info=locator_response.primary_locator
            )
            step_response = await generate_step(step_request)
            assert isinstance(step_response, StepGeneratorResponse)
            
            # Verify all tools produced valid responses
            test_utils.assert_confidence_score(bdd_response)
            test_utils.assert_confidence_score(locator_response)
            test_utils.assert_confidence_score(step_response)

# Performance Tests
class TestToolsPerformance:
    """Performance tests for MCP tools."""
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_tools_response_time(self, test_utils, performance_test_config):
        """Test tool response times are within acceptable limits."""
        # Test locator generation performance (rule-based, should be fast)
        request = LocatorGeneratorRequest(
            dom_content='<button id="test-btn">Test</button>',
            target_description="Test button",
            strategy="id",
            context="Performance test"
        )
        
        response, response_time = await test_utils.measure_response_time(generate_locator, request)
        
        assert isinstance(response, LocatorGeneratorResponse)
        assert response_time < performance_test_config["acceptable_response_time"]
        test_utils.assert_confidence_score(response)
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_concurrent_tool_execution(self, test_utils, performance_test_config):
        """Test concurrent tool execution performance."""
        import asyncio
        
        # Create multiple locator requests
        requests = [
            LocatorGeneratorRequest(
                dom_content=f'<button id="btn-{i}">Button {i}</button>',
                target_description=f"Button {i}",
                strategy="id",
                context="Concurrent test"
            )
            for i in range(performance_test_config["concurrent_requests"])
        ]
        
        # Execute concurrently
        start_time = asyncio.get_event_loop().time()
        responses = await asyncio.gather(*[generate_locator(req) for req in requests])
        end_time = asyncio.get_event_loop().time()
        
        # Verify all responses
        assert len(responses) == performance_test_config["concurrent_requests"]
        for response in responses:
            assert isinstance(response, LocatorGeneratorResponse)
            test_utils.assert_confidence_score(response)
        
        # Check total time is reasonable
        total_time = end_time - start_time
        assert total_time < performance_test_config["acceptable_response_time"] * 2

# Error Handling Tests
class TestToolsErrorHandling:
    """Error handling tests for MCP tools."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_tools_handle_invalid_input(self):
        """Test tools handle invalid input gracefully."""
        # Test with empty DOM content
        request = LocatorGeneratorRequest(
            dom_content="",
            target_description="Non-existent element",
            strategy="auto",
            context="Error test"
        )
        
        response = await generate_locator(request)
        assert isinstance(response, LocatorGeneratorResponse)
        assert response.confidence == 0.0
        assert "error" in response.locator_explanation.lower() or "not found" in response.locator_explanation.lower()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_tools_handle_malformed_input(self):
        """Test tools handle malformed input gracefully."""
        # Test selector healer with malformed DOM
        request = SelectorHealerRequest(
            broken_selector="invalid][selector",
            current_dom="<malformed><html><tag>",
            failure_context="Malformed input test",
            original_intent="Test element"
        )
        
        response = await heal_selector(request)
        assert isinstance(response, SelectorHealerResponse)
        # Should still return a response, even if low confidence
        assert 0.0 <= response.confidence <= 1.0
        assert response.healed_selector  # Should provide some selector

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 
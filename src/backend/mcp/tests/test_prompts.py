"""
Unit tests for MCP Server Prompts
Testing all 5 prompt templates: Bug Report, Test Scenario, Debug Analysis, Locator Explanation, Step Documentation
"""

import pytest
from unittest.mock import patch, MagicMock

# Prompt imports
from ..prompts.bug_report_prompt import generate_bug_report_prompt
from ..prompts.test_scenario_prompt import generate_test_scenario_prompt
from ..prompts.debug_analysis_prompt import generate_debug_analysis_prompt
from ..prompts.locator_explanation_prompt import generate_locator_explanation_prompt
from ..prompts.step_documentation_prompt import generate_step_documentation_prompt

class TestBugReportPrompt:
    """Test cases for Bug Report Prompt template."""
    
    @pytest.mark.unit
    def test_generate_bug_report_basic(self):
        """Test basic bug report prompt generation."""
        prompt = generate_bug_report_prompt(
            error_message="Login button not working",
            context="User authentication flow",
            severity="high"
        )
        
        assert isinstance(prompt, str)
        assert len(prompt) > 100  # Should be substantial
        assert "Login button not working" in prompt
        assert "high" in prompt.lower()
        assert "authentication" in prompt.lower()
        
        # Check for standard bug report sections
        assert "error description" in prompt.lower() or "issue description" in prompt.lower()
        assert "steps to reproduce" in prompt.lower() or "reproduction steps" in prompt.lower()
        assert "expected behavior" in prompt.lower() or "expected result" in prompt.lower()
    
    @pytest.mark.unit
    def test_generate_bug_report_with_reproduction_steps(self):
        """Test bug report prompt with reproduction steps."""
        prompt = generate_bug_report_prompt(
            error_message="Form validation not working",
            context="Contact form submission",
            severity="medium",
            reproduction_steps=[
                "Navigate to contact page",
                "Fill out form with invalid email",
                "Click submit button",
                "No validation error shown"
            ]
        )
        
        assert isinstance(prompt, str)
        assert "Form validation not working" in prompt
        assert "Navigate to contact page" in prompt
        assert "invalid email" in prompt
        assert "medium" in prompt.lower()
    
    @pytest.mark.unit
    def test_generate_bug_report_with_environment_details(self):
        """Test bug report prompt with environment information."""
        prompt = generate_bug_report_prompt(
            error_message="Page load timeout",
            context="E-commerce checkout process",
            severity="critical",
            environment_details={
                "browser": "Chrome 120.0",
                "os": "macOS 14.0",
                "resolution": "1920x1080",
                "network": "WiFi"
            }
        )
        
        assert isinstance(prompt, str)
        assert "Page load timeout" in prompt
        assert "Chrome 120.0" in prompt
        assert "macOS 14.0" in prompt
        assert "critical" in prompt.lower()
        assert "checkout" in prompt.lower()
    
    @pytest.mark.unit
    def test_generate_bug_report_minimal_input(self):
        """Test bug report prompt with minimal input."""
        prompt = generate_bug_report_prompt(
            error_message="Button click fails",
            context="UI interaction",
            severity="low"
        )
        
        assert isinstance(prompt, str)
        assert "Button click fails" in prompt
        assert "low" in prompt.lower()
        assert len(prompt) > 50  # Should still generate meaningful content

class TestTestScenarioPrompt:
    """Test cases for Test Scenario Prompt template."""
    
    @pytest.mark.unit
    def test_generate_test_scenario_functional(self):
        """Test functional test scenario prompt generation."""
        prompt = generate_test_scenario_prompt(
            feature_description="User login functionality",
            test_type="functional",
            scope="authentication system"
        )
        
        assert isinstance(prompt, str)
        assert "User login functionality" in prompt
        assert "functional" in prompt.lower()
        assert "authentication" in prompt.lower()
        
        # Check for test scenario elements
        assert "test" in prompt.lower()
        assert "scenario" in prompt.lower() or "case" in prompt.lower()
    
    @pytest.mark.unit
    def test_generate_test_scenario_integration(self):
        """Test integration test scenario prompt generation."""
        prompt = generate_test_scenario_prompt(
            feature_description="Payment processing integration",
            test_type="integration",
            scope="payment gateway",
            requirements=[
                "Test successful payment flow",
                "Test failed payment handling",
                "Test refund processing"
            ]
        )
        
        assert isinstance(prompt, str)
        assert "Payment processing integration" in prompt
        assert "integration" in prompt.lower()
        assert "successful payment flow" in prompt
        assert "refund processing" in prompt
    
    @pytest.mark.unit
    def test_generate_test_scenario_e2e(self):
        """Test end-to-end test scenario prompt generation."""
        prompt = generate_test_scenario_prompt(
            feature_description="Complete user registration workflow",
            test_type="e2e",
            scope="user onboarding",
            user_personas=["new_user", "returning_user"]
        )
        
        assert isinstance(prompt, str)
        assert "user registration workflow" in prompt.lower()
        assert "e2e" in prompt.lower() or "end-to-end" in prompt.lower()
        assert "new_user" in prompt or "returning_user" in prompt
        assert "onboarding" in prompt.lower()
    
    @pytest.mark.unit
    def test_generate_test_scenario_performance(self):
        """Test performance test scenario prompt generation."""
        prompt = generate_test_scenario_prompt(
            feature_description="Homepage loading performance",
            test_type="performance",
            scope="page load optimization",
            performance_targets={
                "load_time": "< 2 seconds",
                "first_paint": "< 1 second",
                "concurrent_users": "100"
            }
        )
        
        assert isinstance(prompt, str)
        assert "Homepage loading performance" in prompt
        assert "performance" in prompt.lower()
        assert "2 seconds" in prompt
        assert "100" in prompt
        assert "concurrent" in prompt.lower()
    
    @pytest.mark.unit
    def test_generate_test_scenario_security(self):
        """Test security test scenario prompt generation."""
        prompt = generate_test_scenario_prompt(
            feature_description="API authentication security",
            test_type="security",
            scope="API security testing",
            security_aspects=["authentication", "authorization", "input_validation", "rate_limiting"]
        )
        
        assert isinstance(prompt, str)
        assert "API authentication security" in prompt
        assert "security" in prompt.lower()
        assert "authentication" in prompt
        assert "rate_limiting" in prompt

class TestDebugAnalysisPrompt:
    """Test cases for Debug Analysis Prompt template."""
    
    @pytest.mark.unit
    def test_generate_debug_analysis_element_not_found(self):
        """Test debug analysis prompt for element not found error."""
        prompt = generate_debug_analysis_prompt(
            failure_type="element_not_found",
            error_details="NoSuchElementException: Unable to locate element with ID 'submit-btn'",
            context="Form submission test"
        )
        
        assert isinstance(prompt, str)
        assert "element_not_found" in prompt.lower() or "element not found" in prompt.lower()
        assert "NoSuchElementException" in prompt
        assert "submit-btn" in prompt
        assert "form submission" in prompt.lower()
        
        # Check for debug analysis elements
        assert "root cause" in prompt.lower() or "cause analysis" in prompt.lower()
        assert "solution" in prompt.lower() or "fix" in prompt.lower()
    
    @pytest.mark.unit
    def test_generate_debug_analysis_timeout(self):
        """Test debug analysis prompt for timeout error."""
        prompt = generate_debug_analysis_prompt(
            failure_type="timeout",
            error_details="TimeoutException: Element not clickable after 10 seconds",
            context="Page load waiting",
            execution_context={
                "wait_time": "10 seconds",
                "element_state": "loading",
                "page_url": "https://example.com/slow-page"
            }
        )
        
        assert isinstance(prompt, str)
        assert "timeout" in prompt.lower()
        assert "TimeoutException" in prompt
        assert "10 seconds" in prompt
        assert "slow-page" in prompt
        assert "loading" in prompt
    
    @pytest.mark.unit
    def test_generate_debug_analysis_assertion_error(self):
        """Test debug analysis prompt for assertion error."""
        prompt = generate_debug_analysis_prompt(
            failure_type="assertion_error",
            error_details="AssertionError: Expected 'Success' but got 'Error'",
            context="Form validation test",
            test_data={
                "expected_value": "Success",
                "actual_value": "Error",
                "field_name": "status_message"
            }
        )
        
        assert isinstance(prompt, str)
        assert "assertion" in prompt.lower()
        assert "Expected 'Success'" in prompt
        assert "got 'Error'" in prompt
        assert "status_message" in prompt
        assert "validation" in prompt.lower()
    
    @pytest.mark.unit
    def test_generate_debug_analysis_with_logs(self):
        """Test debug analysis prompt with execution logs."""
        prompt = generate_debug_analysis_prompt(
            failure_type="network_error",
            error_details="ConnectionError: Failed to establish connection",
            context="API testing",
            execution_logs=[
                "Sending GET request to /api/users",
                "Request timeout after 30 seconds",
                "Retrying connection",
                "Connection failed permanently"
            ]
        )
        
        assert isinstance(prompt, str)
        assert "network_error" in prompt.lower() or "network error" in prompt.lower()
        assert "ConnectionError" in prompt
        assert "GET request to /api/users" in prompt
        assert "30 seconds" in prompt
        assert "Retrying connection" in prompt
    
    @pytest.mark.unit
    def test_generate_debug_analysis_performance_issue(self):
        """Test debug analysis prompt for performance issues."""
        prompt = generate_debug_analysis_prompt(
            failure_type="performance_degradation",
            error_details="Test execution time exceeded 60 seconds",
            context="Performance regression testing",
            performance_metrics={
                "execution_time": "67.3 seconds",
                "baseline_time": "15.2 seconds",
                "memory_usage": "512 MB",
                "cpu_usage": "85%"
            }
        )
        
        assert isinstance(prompt, str)
        assert "performance" in prompt.lower()
        assert "67.3 seconds" in prompt
        assert "15.2 seconds" in prompt
        assert "512 MB" in prompt
        assert "85%" in prompt

class TestLocatorExplanationPrompt:
    """Test cases for Locator Explanation Prompt template."""
    
    @pytest.mark.unit
    def test_generate_locator_explanation_id(self):
        """Test locator explanation prompt for ID locator."""
        prompt = generate_locator_explanation_prompt(
            locator="#submit-button",
            locator_type="id",
            element_context="Submit button in login form"
        )
        
        assert isinstance(prompt, str)
        assert "#submit-button" in prompt
        assert "id" in prompt.lower()
        assert "submit button" in prompt.lower()
        assert "login form" in prompt.lower()
        
        # Check for explanation elements
        assert "locator" in prompt.lower()
        assert "explain" in prompt.lower() or "description" in prompt.lower()
    
    @pytest.mark.unit
    def test_generate_locator_explanation_css_selector(self):
        """Test locator explanation prompt for CSS selector."""
        prompt = generate_locator_explanation_prompt(
            locator="form.login-form input[type='email']",
            locator_type="css_selector",
            element_context="Email input field in login form",
            selector_strategy="descendant_combinator"
        )
        
        assert isinstance(prompt, str)
        assert "form.login-form input[type='email']" in prompt
        assert "css" in prompt.lower()
        assert "email input field" in prompt.lower()
        assert "descendant_combinator" in prompt or "descendant" in prompt.lower()
    
    @pytest.mark.unit
    def test_generate_locator_explanation_xpath(self):
        """Test locator explanation prompt for XPath locator."""
        prompt = generate_locator_explanation_prompt(
            locator="//div[@class='container']//button[contains(text(), 'Submit')]",
            locator_type="xpath",
            element_context="Submit button within container div",
            reliability_assessment="high"
        )
        
        assert isinstance(prompt, str)
        assert "//div[@class='container']//button[contains(text(), 'Submit')]" in prompt
        assert "xpath" in prompt.lower()
        assert "container div" in prompt.lower()
        assert "high" in prompt.lower()
    
    @pytest.mark.unit
    def test_generate_locator_explanation_data_testid(self):
        """Test locator explanation prompt for data-testid locator."""
        prompt = generate_locator_explanation_prompt(
            locator="[data-testid='user-profile-button']",
            locator_type="data_attribute",
            element_context="User profile button in navigation",
            best_practices=["Use data-testid for stable selectors", "Avoid coupling with visual design"]
        )
        
        assert isinstance(prompt, str)
        assert "data-testid='user-profile-button'" in prompt
        assert "data_attribute" in prompt.lower() or "data attribute" in prompt.lower()
        assert "user profile button" in prompt.lower()
        assert "stable selectors" in prompt
        assert "visual design" in prompt
    
    @pytest.mark.unit
    def test_generate_locator_explanation_with_alternatives(self):
        """Test locator explanation prompt with alternative locators."""
        prompt = generate_locator_explanation_prompt(
            locator="button.primary-btn",
            locator_type="css_selector",
            element_context="Primary action button",
            alternative_locators=[
                "#primary-action",
                "[data-cy='primary-button']",
                "//button[@class='primary-btn']"
            ]
        )
        
        assert isinstance(prompt, str)
        assert "button.primary-btn" in prompt
        assert "#primary-action" in prompt
        assert "data-cy='primary-button'" in prompt
        assert "//button[@class='primary-btn']" in prompt
        assert "alternative" in prompt.lower()

class TestStepDocumentationPrompt:
    """Test cases for Step Documentation Prompt template."""
    
    @pytest.mark.unit
    def test_generate_step_documentation_action(self):
        """Test step documentation prompt for action step."""
        prompt = generate_step_documentation_prompt(
            step_description="Click the submit button to complete the form",
            step_type="action",
            automation_framework="selenium"
        )
        
        assert isinstance(prompt, str)
        assert "Click the submit button" in prompt
        assert "action" in prompt.lower()
        assert "selenium" in prompt.lower()
        
        # Check for documentation elements
        assert "step" in prompt.lower()
        assert "document" in prompt.lower() or "description" in prompt.lower()
    
    @pytest.mark.unit
    def test_generate_step_documentation_verification(self):
        """Test step documentation prompt for verification step."""
        prompt = generate_step_documentation_prompt(
            step_description="Verify that the success message is displayed",
            step_type="verification",
            automation_framework="playwright",
            expected_behavior="Success message should be visible and contain confirmation text"
        )
        
        assert isinstance(prompt, str)
        assert "Verify that the success message" in prompt
        assert "verification" in prompt.lower()
        assert "playwright" in prompt.lower()
        assert "confirmation text" in prompt
    
    @pytest.mark.unit
    def test_generate_step_documentation_navigation(self):
        """Test step documentation prompt for navigation step."""
        prompt = generate_step_documentation_prompt(
            step_description="Navigate to the user dashboard",
            step_type="navigation",
            automation_framework="cypress",
            navigation_details={
                "target_url": "https://example.com/dashboard",
                "authentication_required": True,
                "wait_conditions": ["page_load", "api_response"]
            }
        )
        
        assert isinstance(prompt, str)
        assert "Navigate to the user dashboard" in prompt
        assert "navigation" in prompt.lower()
        assert "cypress" in prompt.lower()
        assert "dashboard" in prompt
        assert "authentication_required" in prompt
        assert "wait_conditions" in prompt
    
    @pytest.mark.unit
    def test_generate_step_documentation_data_input(self):
        """Test step documentation prompt for data input step."""
        prompt = generate_step_documentation_prompt(
            step_description="Enter user registration information",
            step_type="data_input",
            automation_framework="testcafe",
            input_data={
                "firstname": "John",
                "lastname": "Doe",
                "email": "john.doe@example.com",
                "password": "SecurePass123"
            }
        )
        
        assert isinstance(prompt, str)
        assert "Enter user registration information" in prompt
        assert "data_input" in prompt.lower() or "data input" in prompt.lower()
        assert "testcafe" in prompt.lower()
        assert "john.doe@example.com" in prompt
        assert "SecurePass123" in prompt
    
    @pytest.mark.unit
    def test_generate_step_documentation_with_error_handling(self):
        """Test step documentation prompt with error handling information."""
        prompt = generate_step_documentation_prompt(
            step_description="Attempt to submit form with invalid data",
            step_type="error_handling",
            automation_framework="selenium",
            error_scenarios=[
                "Invalid email format",
                "Password too short",
                "Required field missing"
            ],
            expected_errors=["ValidationError", "FormSubmissionError"]
        )
        
        assert isinstance(prompt, str)
        assert "submit form with invalid data" in prompt
        assert "error_handling" in prompt.lower() or "error handling" in prompt.lower()
        assert "Invalid email format" in prompt
        assert "ValidationError" in prompt
        assert "FormSubmissionError" in prompt
    
    @pytest.mark.unit
    def test_generate_step_documentation_with_best_practices(self):
        """Test step documentation prompt with best practices."""
        prompt = generate_step_documentation_prompt(
            step_description="Wait for element to become visible",
            step_type="wait_condition",
            automation_framework="playwright",
            best_practices=[
                "Use explicit waits instead of implicit waits",
                "Set appropriate timeout values",
                "Handle element not found gracefully"
            ]
        )
        
        assert isinstance(prompt, str)
        assert "Wait for element to become visible" in prompt
        assert "wait_condition" in prompt.lower() or "wait condition" in prompt.lower()
        assert "explicit waits" in prompt
        assert "timeout values" in prompt
        assert "element not found" in prompt

# Integration Tests
class TestPromptsIntegration:
    """Integration tests for prompts working together."""
    
    @pytest.mark.integration
    def test_prompts_cross_reference(self):
        """Test prompts can reference each other's output."""
        # Generate a debug analysis prompt first
        debug_prompt = generate_debug_analysis_prompt(
            failure_type="element_not_found",
            error_details="Button selector failed",
            context="Login test"
        )
        
        # Use the debug information to generate a locator explanation
        locator_prompt = generate_locator_explanation_prompt(
            locator="button#login-btn",
            locator_type="id",
            element_context="Login button from debug analysis",
            debugging_context=debug_prompt[:200]  # Use part of debug prompt as context
        )
        
        assert isinstance(debug_prompt, str)
        assert isinstance(locator_prompt, str)
        assert "debug analysis" in locator_prompt.lower()
        assert "login" in both_prompts[0].lower() and "login" in both_prompts[1].lower()

# Performance Tests
class TestPromptsPerformance:
    """Performance tests for prompt generation."""
    
    @pytest.mark.performance
    def test_prompt_generation_speed(self, test_utils, performance_test_config):
        """Test prompt generation is fast enough."""
        import time
        
        start_time = time.time()
        prompt = generate_test_scenario_prompt(
            feature_description="Large feature with many requirements",
            test_type="comprehensive",
            scope="full system testing",
            requirements=["req" + str(i) for i in range(100)]  # Many requirements
        )
        end_time = time.time()
        
        assert isinstance(prompt, str)
        assert len(prompt) > 500  # Should generate substantial content
        assert (end_time - start_time) < 1.0  # Should be very fast (< 1 second)
    
    @pytest.mark.performance
    def test_prompt_memory_usage(self):
        """Test prompt generation doesn't use excessive memory."""
        import sys
        
        # Generate a large prompt
        large_prompt = generate_step_documentation_prompt(
            step_description="Complex multi-step process with detailed documentation",
            step_type="complex_workflow",
            automation_framework="selenium",
            input_data={f"field_{i}": f"value_{i}" for i in range(1000)}  # Large input
        )
        
        assert isinstance(large_prompt, str)
        # Check that the prompt isn't excessively large (memory efficient)
        assert len(large_prompt) < 50000  # Reasonable size limit
        assert sys.getsizeof(large_prompt) < 100000  # Memory usage check

# Error Handling Tests
class TestPromptsErrorHandling:
    """Error handling tests for prompt generation."""
    
    @pytest.mark.unit
    def test_prompts_handle_none_input(self):
        """Test prompts handle None input gracefully."""
        prompt = generate_bug_report_prompt(
            error_message=None,
            context="Test context",
            severity="medium"
        )
        
        assert isinstance(prompt, str)
        assert len(prompt) > 10  # Should still generate some content
        assert "context" in prompt.lower()
    
    @pytest.mark.unit
    def test_prompts_handle_empty_input(self):
        """Test prompts handle empty input gracefully."""
        prompt = generate_test_scenario_prompt(
            feature_description="",
            test_type="functional",
            scope=""
        )
        
        assert isinstance(prompt, str)
        assert len(prompt) > 10  # Should still generate some content
        assert "functional" in prompt.lower()
    
    @pytest.mark.unit
    def test_prompts_handle_invalid_parameters(self):
        """Test prompts handle invalid parameters gracefully."""
        prompt = generate_locator_explanation_prompt(
            locator="",
            locator_type="invalid_type",
            element_context="Test context"
        )
        
        assert isinstance(prompt, str)
        assert "test context" in prompt.lower()
        # Should handle invalid type gracefully

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 
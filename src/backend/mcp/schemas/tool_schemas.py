"""
Tool schemas for MCP tool request/response validation.

These schemas define the input and output structures for all MCP tools
in the IntelliBrowse AI orchestration layer.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# BDD Generator Tool Schemas
class BDDGeneratorRequest(BaseModel):
    """Request schema for BDD scenario generation tool."""
    
    user_story: str = Field(description="User story description")
    context: Optional[str] = Field(default=None, description="Additional context")
    additional_requirements: List[str] = Field(default=[], description="Additional requirements")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_story": "As a user, I want to log into the application so that I can access my dashboard",
                "context": "User authentication and authorization system",
                "additional_requirements": ["Security validation", "Error handling"]
            }
        }


class BDDGeneratorResponse(BaseModel):
    """Response schema for BDD scenario generation tool."""
    
    gherkin_scenario: str = Field(description="Generated Gherkin scenario")
    confidence_score: float = Field(description="Confidence score (0.0-1.0)")
    suggestions: List[str] = Field(default=[], description="Suggestions for improvement")
    tags: List[str] = Field(default=[], description="Suggested scenario tags")
    metadata: Dict[str, Any] = Field(default={}, description="Additional metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "gherkin_scenario": "Feature: User Login\n\n  Scenario: Successful login with valid credentials\n    Given I am on the login page\n    When I enter valid credentials\n    And I click the login button\n    Then I should be redirected to the dashboard",
                "confidence_score": 0.95,
                "suggestions": ["Consider adding error scenarios", "Add data validation tests"],
                "tags": ["@login", "@authentication", "@smoke"],
                "metadata": {"generated_at": "2024-01-08T10:00:00Z", "model_version": "gpt-4"}
            }
        }


# Locator Generator Tool Schemas
class LocatorGeneratorRequest(BaseModel):
    """Request schema for element locator generation tool."""
    
    dom_snapshot: str = Field(description="DOM tree snapshot")
    element_description: str = Field(description="Natural language element description")
    locator_strategy: str = Field(default="auto", description="Preferred locator strategy")
    context_hints: Optional[List[str]] = Field(default=[], description="Context hints for better locating")
    
    class Config:
        json_schema_extra = {
            "example": {
                "dom_snapshot": "<html><body><div class='login-form'><input id='username' type='text'></div></body></html>",
                "element_description": "username input field in the login form",
                "locator_strategy": "auto",
                "context_hints": ["login form", "input field"]
            }
        }


class LocatorGeneratorResponse(BaseModel):
    """Response schema for element locator generation tool."""
    
    primary_locator: str = Field(description="Primary recommended locator")
    fallback_locators: List[str] = Field(default=[], description="Fallback locator options")
    strategy_used: str = Field(description="Strategy used for primary locator")
    confidence_score: float = Field(description="Confidence score (0.0-1.0)")
    element_analysis: Dict[str, Any] = Field(default={}, description="Element analysis details")
    
    class Config:
        json_schema_extra = {
            "example": {
                "primary_locator": "id=username",
                "fallback_locators": ["css=input[type='text']", "xpath=//input[@id='username']"],
                "strategy_used": "id",
                "confidence_score": 0.98,
                "element_analysis": {"unique_attributes": ["id"], "element_type": "input"}
            }
        }


# Step Generator Tool Schemas
class StepGeneratorRequest(BaseModel):
    """Request schema for test step generation tool."""
    
    description: str = Field(description="Natural language description of the test requirement")
    step_type: str = Field(default="gherkin", description="Type of steps to generate (gherkin, automation)")
    dom_context: Optional[str] = Field(default=None, description="DOM context for better step generation")
    existing_steps: Optional[List[str]] = Field(default=[], description="Existing steps for reference")
    
    class Config:
        json_schema_extra = {
            "example": {
                "description": "User should be able to login with valid credentials",
                "step_type": "gherkin",
                "dom_context": "<form><input id='username'/><input id='password'/><button id='login'>Login</button></form>",
                "existing_steps": ["Given I am on the login page"]
            }
        }


class StepGeneratorResponse(BaseModel):
    """Response schema for test step generation tool."""
    
    steps: List[Dict[str, Any]] = Field(description="Generated test steps with metadata")
    alternatives: List[Dict[str, Any]] = Field(default=[], description="Alternative step approaches")
    confidence: float = Field(description="Overall confidence score (0.0-1.0)")
    metadata: Dict[str, Any] = Field(default={}, description="Generation metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "steps": [
                    {
                        "type": "gherkin",
                        "keyword": "When",
                        "text": "I enter valid credentials",
                        "confidence": 0.9,
                        "step_id": "step_1"
                    }
                ],
                "alternatives": [
                    {
                        "approach": "More specific credential validation",
                        "confidence": 0.8
                    }
                ],
                "confidence": 0.85,
                "metadata": {"processing_time": 1.2, "model_used": "gpt-4"}
            }
        }


# Selector Healer Tool Schemas
class SelectorHealerRequest(BaseModel):
    """Request schema for selector healing tool."""
    
    broken_selector: str = Field(description="The broken/failing selector")
    selector_type: str = Field(default="css", description="Type of selector (css, xpath, id)")
    current_dom: Optional[str] = Field(default=None, description="Current DOM snapshot")
    original_dom: Optional[str] = Field(default=None, description="Original DOM when selector worked")
    error_message: Optional[str] = Field(default=None, description="Error message from selector failure")
    
    class Config:
        json_schema_extra = {
            "example": {
                "broken_selector": "#old-login-btn",
                "selector_type": "css",
                "current_dom": "<html><body><button class='btn login-button'>Login</button></body></html>",
                "original_dom": "<html><body><button id='old-login-btn'>Login</button></body></html>",
                "error_message": "Element not found: #old-login-btn"
            }
        }


class SelectorHealerResponse(BaseModel):
    """Response schema for selector healing tool."""
    
    healed_selectors: List[Dict[str, Any]] = Field(description="Healed selector suggestions with metadata")
    confidence: float = Field(description="Overall confidence in healing (0.0-1.0)")
    analysis: Dict[str, Any] = Field(description="Analysis of the broken selector")
    healing_strategy: Dict[str, Any] = Field(description="Recommended healing strategy")
    metadata: Dict[str, Any] = Field(default={}, description="Healing process metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "healed_selectors": [
                    {
                        "selector": ".login-button",
                        "confidence": 0.9,
                        "strategy": "class_based",
                        "reason": "Switched to stable class selector"
                    }
                ],
                "confidence": 0.85,
                "analysis": {
                    "category": "selector",
                    "fragility_score": 0.7,
                    "issues": ["ID-based selector changed"]
                },
                "healing_strategy": {
                    "recommended_approach": "progressive",
                    "risk_level": "medium"
                },
                "metadata": {"processing_time": 0.8}
            }
        }


# Debug Analyzer Tool Schemas
class DebugAnalyzerRequest(BaseModel):
    """Request schema for debug analysis tool."""
    
    error_message: str = Field(description="Error message or exception")
    error_type: Optional[str] = Field(default=None, description="Type of error (e.g., TimeoutError, ElementNotFound)")
    stack_trace: Optional[str] = Field(default=None, description="Stack trace if available")
    logs: Optional[str] = Field(default=None, description="Relevant logs")
    context: Optional[str] = Field(default=None, description="Additional context (JSON string or text)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error_message": "Element not found: id=submit-button",
                "error_type": "ElementNotFound",
                "stack_trace": "Traceback (most recent call last):\n  File 'test.py', line 45, in test_submit\n    element = driver.find_element(By.ID, 'submit-button')",
                "logs": "INFO: Navigating to /register\nWARN: Element not immediately visible",
                "context": "{\"url\": \"/register\", \"step\": \"clicking submit button\", \"browser\": \"chrome\"}"
            }
        }


class DebugAnalyzerResponse(BaseModel):
    """Response schema for debug analysis tool."""
    
    analysis: Dict[str, Any] = Field(description="Comprehensive error analysis")
    recommendations: List[Dict[str, Any]] = Field(description="Actionable recommendations")
    confidence: float = Field(description="Confidence in analysis (0.0-1.0)")
    metadata: Dict[str, Any] = Field(default={}, description="Analysis metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "analysis": {
                    "category": "selector",
                    "severity": "high", 
                    "root_causes": [
                        {
                            "cause": "Element selector outdated",
                            "probability": 0.8,
                            "evidence": "Element not found error"
                        }
                    ]
                },
                "recommendations": [
                    {
                        "priority": "high",
                        "action": "Update element selector",
                        "description": "Use selector healing tool to fix broken selector",
                        "estimated_effort": "medium"
                    }
                ],
                "confidence": 0.85,
                "metadata": {"processing_time": 1.5, "analysis_approach": "hybrid"}
            }
        }


# Legacy schemas for backward compatibility
class StepRequest(BaseModel):
    """Legacy request schema for test step generation tool."""
    
    scenario_context: str = Field(description="BDD scenario context")
    step_type: str = Field(description="Step type (given, when, then)")
    action_description: str = Field(description="Natural language action description")
    page_context: Optional[str] = Field(default=None, description="Current page context")
    
    class Config:
        json_schema_extra = {
            "example": {
                "scenario_context": "User login scenario",
                "step_type": "when",
                "action_description": "user clicks the login button",
                "page_context": "login page with form elements"
            }
        }


class StepResponse(BaseModel):
    """Legacy response schema for test step generation tool."""
    
    step_definition: str = Field(description="Generated step definition")
    implementation_code: str = Field(description="Implementation code for the step")
    parameters: List[str] = Field(default=[], description="Step parameters")
    confidence_score: float = Field(description="Confidence score (0.0-1.0)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "step_definition": "When I click the login button",
                "implementation_code": "await page.click('#login-button')",
                "parameters": [],
                "confidence_score": 0.92
            }
        }


class SelectorRequest(BaseModel):
    """Legacy request schema for selector healing tool."""
    
    broken_selector: str = Field(description="The broken/failing selector")
    current_dom: str = Field(description="Current DOM snapshot")
    expected_element_description: str = Field(description="Description of expected element")
    previous_successful_selectors: Optional[List[str]] = Field(default=[], description="Previously working selectors")
    
    class Config:
        json_schema_extra = {
            "example": {
                "broken_selector": "id=old-login-btn",
                "current_dom": "<html><body><button class='btn login-button'>Login</button></body></html>",
                "expected_element_description": "login button",
                "previous_successful_selectors": ["#login-btn", ".login-button"]
            }
        }


class SelectorResponse(BaseModel):
    """Legacy response schema for selector healing tool."""
    
    healed_selector: str = Field(description="New working selector")
    healing_strategy: str = Field(description="Strategy used for healing")
    confidence_score: float = Field(description="Confidence score (0.0-1.0)")
    alternative_selectors: List[str] = Field(default=[], description="Alternative selector options")
    healing_notes: str = Field(description="Notes about the healing process")
    
    class Config:
        json_schema_extra = {
            "example": {
                "healed_selector": "css=.login-button",
                "healing_strategy": "class_based_fallback",
                "confidence_score": 0.89,
                "alternative_selectors": ["xpath=//button[contains(text(), 'Login')]"],
                "healing_notes": "ID changed, falling back to class-based selector"
            }
        }


class DebugRequest(BaseModel):
    """Legacy request schema for debug analysis tool."""
    
    error_message: str = Field(description="Error message or exception")
    test_context: str = Field(description="Test execution context")
    stack_trace: Optional[str] = Field(default=None, description="Stack trace if available")
    browser_logs: Optional[List[str]] = Field(default=[], description="Browser console logs")
    screenshot_base64: Optional[str] = Field(default=None, description="Screenshot in base64")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error_message": "Element not found: id=submit-button",
                "test_context": "User registration flow, step: clicking submit button",
                "stack_trace": "ElementNotFoundError at line 45",
                "browser_logs": ["Console warning: Element hidden"],
                "screenshot_base64": None
            }
        }


class DebugResponse(BaseModel):
    """Legacy response schema for debug analysis tool."""
    
    root_cause_analysis: str = Field(description="Analysis of the root cause")
    suggested_fixes: List[str] = Field(description="Suggested fixes")
    confidence_score: float = Field(description="Confidence score (0.0-1.0)")
    similar_issues: List[str] = Field(default=[], description="Similar known issues")
    prevention_tips: List[str] = Field(default=[], description="Tips to prevent similar issues")
    
    class Config:
        json_schema_extra = {
            "example": {
                "root_cause_analysis": "Element selector 'id=submit-button' no longer exists. Element may have been renamed or moved.",
                "suggested_fixes": [
                    "Update selector to current element ID",
                    "Use more robust selector strategy",
                    "Add explicit wait for element"
                ],
                "confidence_score": 0.87,
                "similar_issues": ["Dynamic ID changes", "Element not loaded"],
                "prevention_tips": ["Use data attributes for stable selectors", "Implement proper waits"]
            }
        }


# Legacy schema name aliases for backward compatibility
# These provide the original class names expected by tests and legacy code

# BDD Tool Aliases
BDDRequest = BDDGeneratorRequest
BDDResponse = BDDGeneratorResponse

# Locator Tool Aliases  
LocatorRequest = LocatorGeneratorRequest
LocatorResponse = LocatorGeneratorResponse

# Browser Session Management Tool Schemas
class OpenBrowserRequest(BaseModel):
    """Request schema for opening a new browser session."""
    
    headless: bool = Field(default=True, description="Open browser in headless mode")
    browser_type: str = Field(default="chromium", description="Browser type (chromium, firefox, webkit)")
    viewport_width: int = Field(default=1920, description="Viewport width in pixels")
    viewport_height: int = Field(default=1080, description="Viewport height in pixels")
    user_agent: Optional[str] = Field(default=None, description="Custom user agent string")
    extra_http_headers: Optional[Dict[str, str]] = Field(default=None, description="Extra HTTP headers")
    
    class Config:
        json_schema_extra = {
            "example": {
                "headless": True,
                "browser_type": "chromium",
                "viewport_width": 1920,
                "viewport_height": 1080,
                "user_agent": None,
                "extra_http_headers": {"Accept-Language": "en-US,en;q=0.9"}
            }
        }


class OpenBrowserResponse(BaseModel):
    """Response schema for opening a new browser session."""
    
    session_id: str = Field(description="Unique browser session identifier")
    browser_type: str = Field(description="Browser type that was launched")
    headless: bool = Field(description="Whether browser was launched in headless mode")
    viewport: Dict[str, int] = Field(description="Viewport dimensions")
    message: str = Field(description="Success message")
    metadata: Dict[str, Any] = Field(default={}, description="Additional session metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "browser_session_12345",
                "browser_type": "chromium",
                "headless": True,
                "viewport": {"width": 1920, "height": 1080},
                "message": "Browser session opened successfully",
                "metadata": {"created_at": "2024-01-08T10:00:00Z", "version": "1.0.0"}
            }
        }


class CloseBrowserRequest(BaseModel):
    """Request schema for closing a browser session."""
    
    session_id: str = Field(description="ID of the browser session to close")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "browser_session_12345"
            }
        }


class CloseBrowserResponse(BaseModel):
    """Response schema for closing a browser session."""
    
    closed: bool = Field(description="Whether the session was successfully closed")
    session_id: str = Field(description="The session ID that was closed")
    message: str = Field(description="Status message")
    remaining_sessions: int = Field(description="Number of remaining active sessions")
    
    class Config:
        json_schema_extra = {
            "example": {
                "closed": True,
                "session_id": "browser_session_abc123",
                "message": "Browser session closed successfully",
                "remaining_sessions": 2
            }
        }


# Navigate to URL Tool Schemas
class NavigateToUrlRequest(BaseModel):
    """Request schema for navigating to a URL within a browser session."""
    
    session_id: str = Field(description="Browser session ID")
    url: str = Field(description="Destination URL to navigate to")
    timeout_ms: Optional[int] = Field(default=10000, description="Navigation timeout in milliseconds")
    wait_until: str = Field(default="domcontentloaded", description="When to consider navigation succeeded (load, domcontentloaded, networkidle)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "browser_session_abc123",
                "url": "https://www.example.com",
                "timeout_ms": 15000,
                "wait_until": "domcontentloaded"
            }
        }


class NavigateToUrlResponse(BaseModel):
    """Response schema for URL navigation."""
    
    navigated: bool = Field(description="Whether navigation was successful")
    http_status: Optional[int] = Field(description="HTTP response status code")
    final_url: str = Field(description="Final URL after navigation (may differ due to redirects)")
    message: str = Field(description="Navigation status message")
    elapsed_ms: int = Field(description="Time taken for navigation in milliseconds")
    metadata: Dict[str, Any] = Field(default={}, description="Additional navigation metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "navigated": True,
                "http_status": 200,
                "final_url": "https://example.com/dashboard",
                "message": "Navigation successful to https://example.com/dashboard (HTTP 200)",
                "elapsed_ms": 1542,
                "metadata": {
                    "page_title": "Dashboard - Example App",
                    "load_event_fired": True,
                    "redirects": 1,
                    "user_agent": "Mozilla/5.0...",
                    "viewport": {"width": 1920, "height": 1080},
                    "browser_type": "chromium"
                }
            }
        }


# DOM Inspection Tool Schemas
class GetPageDomRequest(BaseModel):
    """Request schema for getting page DOM content."""
    
    session_id: str = Field(description="Active Playwright session ID")
    selector: Optional[str] = Field(default=None, description="Optional CSS selector to target a specific element")
    outer_html: Optional[bool] = Field(default=False, description="Return outerHTML (default: innerHTML) if selector is specified")
    max_length: Optional[int] = Field(default=100_000, description="Maximum HTML content length to return (truncate if exceeded)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_123456789",
                "selector": "#login-form",
                "outer_html": True,
                "max_length": 50000
            }
        }


class GetPageDomResponse(BaseModel):
    """Response schema for page DOM content retrieval."""
    
    html_content: str = Field(description="The requested DOM content")
    truncated: bool = Field(default=False, description="True if output was truncated to max_length")
    selector_used: Optional[str] = Field(default=None, description="Selector used for DOM extraction, if any")
    message: str = Field(description="Status or result message")
    content_length: int = Field(description="Length of the HTML content returned")
    metadata: Dict[str, Any] = Field(default={}, description="Additional DOM extraction metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "html_content": "<div id='login-form'><input type='text' id='username'/><input type='password' id='password'/><button>Login</button></div>",
                "truncated": False,
                "selector_used": "#login-form",
                "message": "DOM retrieved successfully for selector #login-form",
                "content_length": 126,
                "metadata": {
                    "extraction_type": "element_selector",
                    "page_title": "Login Page",
                    "page_url": "https://example.com/login",
                    "element_count": 3,
                    "extraction_time_ms": 45
                }
            }
        }


# Click Element Tool Schemas
class ClickElementRequest(BaseModel):
    """Request schema for clicking a DOM element."""
    
    session_id: str = Field(description="Active Playwright session ID")
    selector: str = Field(description="CSS selector of the element to click")
    timeout_ms: Optional[int] = Field(default=5000, description="Timeout in milliseconds for element availability")
    click_type: Optional[str] = Field(default="single", description="Type of click: 'single', 'double', 'right'")
    delay_ms: Optional[int] = Field(default=0, description="Delay after click in milliseconds")
    force: Optional[bool] = Field(default=False, description="Whether to force the click even if element is not actionable")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_123456789",
                "selector": "#submit-btn",
                "timeout_ms": 5000,
                "click_type": "single",
                "delay_ms": 100,
                "force": False
            }
        }


class ClickElementResponse(BaseModel):
    """Response schema for element click operation."""
    
    success: bool = Field(description="Whether the click was performed successfully")
    selector: str = Field(description="Selector used for the click")
    message: str = Field(description="Status or error message")
    click_type: str = Field(description="Type of click that was performed")
    elapsed_ms: int = Field(description="Time taken for the click operation in milliseconds")
    metadata: Dict[str, Any] = Field(default={}, description="Additional click operation metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "selector": "#submit-btn",
                "message": "Click performed successfully on element #submit-btn",
                "click_type": "single",
                "elapsed_ms": 1250,
                "metadata": {
                    "element_visible": True,
                    "element_enabled": True,
                    "page_title": "Login Form",
                    "page_url": "https://example.com/login",
                    "coordinates": {"x": 150, "y": 300},
                    "browser_type": "chromium"
                }
            }
        }


# Fill Element Tool Schemas
class FillElementRequest(BaseModel):
    """Request schema for filling input elements with text."""
    
    session_id: str = Field(description="Active Playwright session ID")
    selector: str = Field(description="CSS selector of the input element to fill")
    value: str = Field(description="Text value to fill into the element")
    timeout_ms: Optional[int] = Field(default=5000, description="Timeout in milliseconds for element availability")
    clear_first: Optional[bool] = Field(default=True, description="Whether to clear the element before filling")
    delay_ms: Optional[int] = Field(default=0, description="Delay after filling in milliseconds")
    force: Optional[bool] = Field(default=False, description="Whether to force filling even if element is not editable")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "browser_session_abc123",
                "selector": "#username",
                "value": "testuser@example.com",
                "timeout_ms": 5000,
                "clear_first": True,
                "delay_ms": 100,
                "force": False
            }
        }


class FillElementResponse(BaseModel):
    """Response schema for element fill operation."""
    
    success: bool = Field(description="Whether the element was filled successfully")
    selector: str = Field(description="Selector used for the fill operation")
    value: str = Field(description="Value that was filled into the element")
    message: str = Field(description="Status or error message")
    cleared_first: bool = Field(description="Whether the element was cleared before filling")
    elapsed_ms: int = Field(description="Time taken for the fill operation in milliseconds")
    metadata: Dict[str, Any] = Field(default={}, description="Additional fill operation metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "selector": "#username",
                "value": "testuser@example.com",
                "message": "Element filled successfully",
                "cleared_first": True,
                "elapsed_ms": 123,
                "metadata": {
                    "element_type": "input",
                    "element_tag": "INPUT",
                    "input_type": "email",
                    "element_bounds": {"x": 50, "y": 100, "width": 200, "height": 30},
                    "page_title": "Login Page",
                    "session_id": "browser_session_abc123",
                    "timestamp": "2025-01-08T12:34:56.789Z",
                    "previous_value": "",
                    "value_length": 20
                }
            }
        }


# Type Text Tool Schemas
class TypeTextRequest(BaseModel):
    """Request schema for typing text into input elements character by character."""
    
    session_id: str = Field(description="Active Playwright session ID")
    selector: str = Field(description="CSS selector of the input element to type into")
    text: str = Field(description="Text content to type character by character")
    timeout_ms: Optional[int] = Field(default=5000, description="Timeout in milliseconds for element availability")
    clear_before: Optional[bool] = Field(default=True, description="Whether to clear the element before typing")
    delay_ms: Optional[int] = Field(default=0, description="Delay between keystrokes in milliseconds")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "browser_session_12345",
                "selector": "#username",
                "text": "john.doe@example.com",
                "timeout_ms": 5000,
                "clear_before": True,
                "delay_ms": 50
            }
        }


class TypeTextResponse(BaseModel):
    """Response schema for text typing operation."""
    
    success: bool = Field(description="Whether the text was typed successfully")
    selector: str = Field(description="Selector used for the typing operation")
    text: str = Field(description="Text that was typed into the element")
    message: str = Field(description="Status or error message")
    cleared_before: bool = Field(description="Whether the element was cleared before typing")
    characters_typed: int = Field(description="Number of characters that were typed")
    elapsed_ms: int = Field(description="Time taken for the typing operation in milliseconds")
    metadata: Dict[str, Any] = Field(default={}, description="Additional typing operation metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "selector": "#username",
                "text": "john.doe@example.com",
                "message": "Successfully typed 'john.doe@example.com' into '#username'",
                "cleared_before": True,
                "characters_typed": 20,
                "elapsed_ms": 1250,
                "metadata": {
                    "element_type": "email",
                    "typing_delay_ms": 50,
                    "element_bounds": {"x": 100, "y": 200, "width": 300, "height": 40}
                }
            }
        }


# Clear Input Field Tool Schemas

class ClearInputFieldRequest(BaseModel):
    """Request schema for clearing input field values."""
    
    session_id: str = Field(description="Active Playwright session ID")
    selector: str = Field(description="CSS selector of the input element to clear")
    timeout_ms: Optional[int] = Field(default=5000, description="Timeout in milliseconds for element availability")
    force: Optional[bool] = Field(default=False, description="Whether to force clearing even if element is not editable")
    verify_cleared: Optional[bool] = Field(default=True, description="Whether to verify that the field was actually cleared")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "browser_session_12345",
                "selector": "#search-input",
                "timeout_ms": 5000,
                "force": False,
                "verify_cleared": True
            }
        }


class ClearInputFieldResponse(BaseModel):
    """Response schema for input field clearing operation."""
    
    success: bool = Field(description="Whether the field was cleared successfully")
    selector: str = Field(description="Selector used for the clearing operation")
    message: str = Field(description="Status or error message")
    was_cleared: bool = Field(description="Whether the field was actually cleared")
    original_value: str = Field(description="Original value that was in the field before clearing")
    final_value: str = Field(description="Final value in the field after clearing attempt")
    elapsed_ms: int = Field(description="Time taken for the clearing operation in milliseconds")
    metadata: Dict[str, Any] = Field(default={}, description="Additional clearing operation metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "selector": "#search-input",
                "message": "Successfully cleared field '#search-input' (removed 'previous search term')",
                "was_cleared": True,
                "original_value": "previous search term",
                "final_value": "",
                "elapsed_ms": 850,
                "metadata": {
                    "element_type": "text",
                    "verification_performed": True,
                    "element_bounds": {"x": 50, "y": 100, "width": 400, "height": 35}
                }
            }
        }


# Press Key Tool Schemas

class PressKeyRequest(BaseModel):
    """Request schema for pressing keyboard keys."""
    
    session_id: str = Field(description="Active Playwright session ID")
    key: str = Field(description="Key to press (e.g., 'Enter', 'Tab', 'ArrowRight', 'a', 'F1')")
    selector: Optional[str] = Field(default=None, description="Optional CSS selector to focus before pressing key")
    modifiers: Optional[List[str]] = Field(default=[], description="Modifier keys (e.g., ['Control', 'Shift', 'Alt', 'Meta'])")
    timeout_ms: Optional[int] = Field(default=5000, description="Timeout in milliseconds for element focus")
    delay_after_ms: Optional[int] = Field(default=0, description="Delay after key press in milliseconds")
    focus_first: Optional[bool] = Field(default=True, description="Whether to focus element before key press if selector provided")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "browser_session_12345",
                "key": "Enter",
                "selector": "#submit-button",
                "modifiers": [],
                "timeout_ms": 5000,
                "delay_after_ms": 100,
                "focus_first": True
            }
        }


class PressKeyResponse(BaseModel):
    """Response schema for key press operation."""
    
    success: bool = Field(description="Whether the key was pressed successfully")
    session_id: str = Field(description="Session ID where the key was pressed")
    key: str = Field(description="Key that was pressed")
    selector: Optional[str] = Field(description="Selector that was focused (if any)")
    message: str = Field(description="Status or error message")
    key_pressed: bool = Field(description="Whether the key press operation was executed")
    focused_element: bool = Field(description="Whether an element was focused before key press")
    modifiers_used: List[str] = Field(default=[], description="Modifier keys that were used")
    elapsed_ms: int = Field(description="Time taken for the key press operation in milliseconds")
    metadata: Dict[str, Any] = Field(default={}, description="Additional key press operation metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "session_id": "browser_session_12345",
                "key": "Enter",
                "selector": "#submit-button",
                "message": "Successfully pressed key 'Enter' on element '#submit-button'",
                "key_pressed": True,
                "focused_element": True,
                "modifiers_used": [],
                "elapsed_ms": 450,
                "metadata": {
                    "key_type": "special",
                    "element_tag": "button",
                    "element_bounds": {"x": 200, "y": 300, "width": 120, "height": 40}
                }
            }
        }


# Release Key Tool Schemas

class ReleaseKeyRequest(BaseModel):
    """Request schema for releasing held-down keyboard keys."""
    
    session_id: str = Field(description="Active Playwright session ID")
    key: str = Field(description="Key to release (e.g., 'Shift', 'Control', 'Alt', 'Enter', 'F1')")
    selector: Optional[str] = Field(default=None, description="Optional CSS selector to focus before releasing key")
    timeout_ms: Optional[int] = Field(default=5000, description="Timeout in milliseconds for element focus")
    delay_after_ms: Optional[int] = Field(default=0, description="Delay after key release in milliseconds")
    focus_first: Optional[bool] = Field(default=True, description="Whether to focus element before key release if selector provided")
    verify_release: Optional[bool] = Field(default=True, description="Whether to verify the key release operation")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "browser_session_12345",
                "key": "Shift",
                "selector": "#text-input",
                "timeout_ms": 5000,
                "delay_after_ms": 100,
                "focus_first": True,
                "verify_release": True
            }
        }


class ReleaseKeyResponse(BaseModel):
    """Response schema for key release operation."""
    
    success: bool = Field(description="Whether the key was released successfully")
    session_id: str = Field(description="Session ID where the key was released")
    key: str = Field(description="Key that was released")
    selector: Optional[str] = Field(description="Selector that was focused (if any)")
    message: str = Field(description="Status or error message")
    key_released: bool = Field(description="Whether the key release operation was executed")
    focused_element: bool = Field(description="Whether an element was focused before key release")
    elapsed_ms: int = Field(description="Time taken for the key release operation in milliseconds")
    metadata: Dict[str, Any] = Field(default={}, description="Additional key release operation metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "session_id": "browser_session_12345",
                "key": "Shift",
                "selector": "#text-input",
                "message": "Successfully released key 'Shift' on element '#text-input'",
                "key_released": True,
                "focused_element": True,
                "elapsed_ms": 320,
                "metadata": {
                    "key_type": "releasable",
                    "is_modifier": True,
                    "element_tag": "input",
                    "element_bounds": {"x": 100, "y": 200, "width": 300, "height": 30}
                }
            }
        }


# Scroll Page Tool Schemas
class ScrollPageRequest(BaseModel):
    """Request schema for scroll page operation."""
    
    session_id: str = Field(description="Active Playwright session ID")
    direction: Optional[str] = Field(default=None, description="Direction to scroll: 'up', 'down', 'left', 'right', 'top', 'bottom'")
    pixels: Optional[int] = Field(default=None, description="Number of pixels to scroll (positive or negative)")
    selector: Optional[str] = Field(default=None, description="Optional CSS selector to scroll a specific element")
    to_element: Optional[bool] = Field(default=False, description="If true, scrolls to the element specified by selector")
    timeout_ms: Optional[int] = Field(default=5000, description="Timeout in milliseconds for element availability")
    smooth: Optional[bool] = Field(default=False, description="Whether to use smooth scrolling animation")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "browser_session_123",
                "direction": "down",
                "pixels": 500,
                "selector": ".content-area",
                "to_element": False,
                "timeout_ms": 5000,
                "smooth": True
            }
        }


class ScrollPageResponse(BaseModel):
    """Response schema for scroll page operation."""
    
    success: bool = Field(description="Whether the scroll operation was successful")
    session_id: str = Field(description="Session ID where the scroll was performed")
    scroll_position: Dict[str, int] = Field(description="Final scroll position (x, y coordinates)")
    scrolled_element: Optional[str] = Field(default=None, description="Element that was scrolled (if selector was used)")
    scroll_type: str = Field(description="Type of scroll operation performed")
    message: str = Field(description="Status or error message")
    elapsed_ms: int = Field(description="Time taken for the scroll operation in milliseconds")
    metadata: Dict[str, Any] = Field(default={}, description="Additional scroll operation metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "session_id": "browser_session_123",
                "scroll_position": {"x": 0, "y": 500},
                "scrolled_element": ".content-area",
                "scroll_type": "directional_scroll",
                "message": "Successfully scrolled down by 500 pixels",
                "elapsed_ms": 150,
                "metadata": {
                    "initial_position": {"x": 0, "y": 0},
                    "scroll_distance": 500,
                    "smooth_scrolling": True
                }
            }
        }


# Hover Element Tool Schemas
class HoverElementRequest(BaseModel):
    """Request schema for hovering over a DOM element."""
    
    session_id: str = Field(description="Active Playwright session ID")
    selector: str = Field(description="CSS selector of the element to hover over")
    timeout_ms: Optional[int] = Field(default=5000, description="Timeout in milliseconds for element availability")
    delay_ms: Optional[int] = Field(default=0, description="Delay after hover in milliseconds")
    force: Optional[bool] = Field(default=False, description="Whether to force the hover even if element is not actionable")
    position: Optional[Dict[str, float]] = Field(default=None, description="Optional position to hover within the element (x, y coordinates)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "browser_session_12345",
                "selector": ".dropdown-menu",
                "timeout_ms": 5000,
                "delay_ms": 100,
                "force": False,
                "position": {"x": 10, "y": 10}
            }
        }


class HoverElementResponse(BaseModel):
    """Response schema for element hover operation."""
    
    success: bool = Field(description="Whether the hover was performed successfully")
    selector: str = Field(description="Selector used for the hover")
    message: str = Field(description="Status or error message")
    hovered: bool = Field(description="Whether the hover operation was executed")
    position: Optional[Dict[str, float]] = Field(default=None, description="Position where hover was performed")
    elapsed_ms: int = Field(description="Time taken for the hover operation in milliseconds")
    metadata: Dict[str, Any] = Field(default={}, description="Additional hover operation metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "selector": ".dropdown-menu",
                "message": "Successfully hovered over element '.dropdown-menu'",
                "hovered": True,
                "position": {"x": 150, "y": 200},
                "elapsed_ms": 320,
                "metadata": {
                    "element_visible": True,
                    "element_bounds": {"x": 100, "y": 150, "width": 200, "height": 100},
                    "page_title": "Application Dashboard",
                    "page_url": "https://example.com/dashboard",
                    "browser_type": "chromium"
                }
            }
        } 
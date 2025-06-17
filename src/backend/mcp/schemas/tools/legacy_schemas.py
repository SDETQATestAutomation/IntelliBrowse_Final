"""
Legacy Tool Schemas.

Pydantic schemas for legacy tool request and response validation.
These schemas are maintained for backward compatibility.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# Legacy Step Generation Schemas
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
                "action_description": "user enters valid credentials",
                "page_context": "login page"
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
                "step_definition": "When I enter valid credentials",
                "implementation_code": "await page.fill('#username', 'testuser')",
                "parameters": ["username", "password"],
                "confidence_score": 0.9
            }
        }


# Legacy Selector Healing Schemas
class SelectorRequest(BaseModel):
    """Legacy request schema for selector healing tool."""
    
    broken_selector: str = Field(description="The broken/failing selector")
    current_dom: str = Field(description="Current DOM snapshot")
    expected_element_description: str = Field(description="Description of expected element")
    previous_successful_selectors: Optional[List[str]] = Field(default=[], description="Previously working selectors")
    
    class Config:
        json_schema_extra = {
            "example": {
                "broken_selector": "#old-submit-btn",
                "current_dom": "<html><body><button class='submit-button'>Submit</button></body></html>",
                "expected_element_description": "Submit button for form submission",
                "previous_successful_selectors": ["#submit-btn", ".submit"]
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
                "healed_selector": ".submit-button",
                "healing_strategy": "class_based_replacement",
                "confidence_score": 0.85,
                "alternative_selectors": ["button[type='submit']", "input[value='Submit']"],
                "healing_notes": "Switched from ID to class-based selector for better stability"
            }
        }


# Legacy Debug Analysis Schemas
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
                "error_message": "Element not found: #submit-button",
                "test_context": "Login form submission test",
                "stack_trace": "TimeoutError: Waiting for selector #submit-button failed",
                "browser_logs": ["Error: Button not clickable", "Warning: Deprecated API usage"],
                "screenshot_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
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
                "root_cause_analysis": "The submit button selector has changed due to DOM structure updates",
                "suggested_fixes": [
                    "Update selector to use class instead of ID",
                    "Add wait condition for element visibility",
                    "Implement retry mechanism with multiple selectors"
                ],
                "confidence_score": 0.92,
                "similar_issues": ["Button ID changes", "Dynamic content loading"],
                "prevention_tips": [
                    "Use stable selectors based on data attributes",
                    "Implement selector healing mechanisms",
                    "Regular DOM structure monitoring"
                ]
            }
        } 
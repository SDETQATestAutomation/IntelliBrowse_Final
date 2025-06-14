"""
Debug Analyzer Tool Schemas

Schemas for the debug analysis tool that analyzes errors, exceptions,
and test failures to provide root cause analysis and actionable recommendations.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


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
                "error_message": "TimeoutError: Locator 'css=#submit-btn' not found",
                "error_type": "TimeoutError",
                "stack_trace": "File test_login.py line 45 in click_submit_button",
                "logs": "Page loaded successfully, DOM ready",
                "context": "Login test execution on Chrome browser"
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
                    "category": "locator_failure",
                    "severity": "medium",
                    "root_cause": "Element selector changed or timing issue",
                    "affected_components": ["login_form", "submit_button"]
                },
                "recommendations": [
                    {
                        "priority": "high",
                        "action": "Update selector to use more stable attributes",
                        "implementation": "Use data-testid or class-based selector",
                        "confidence": 0.9
                    }
                ],
                "confidence": 0.85,
                "metadata": {
                    "analysis_time": 2.3,
                    "patterns_matched": ["timeout_error", "selector_not_found"]
                }
            }
        } 
"""
Debug Analyzer Tool Schemas.

Pydantic schemas for debug analysis tool request and response validation.
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
                "error_message": "Element not found: #submit-button",
                "error_type": "ElementNotFound",
                "stack_trace": "playwright._impl._api_types.TimeoutError: Timeout 30000ms exceeded.",
                "logs": "Browser console: Element #submit-button not visible",
                "context": "Login form automation test"
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
                    "category": "element_not_found",
                    "severity": "medium",
                    "likely_causes": ["Selector changed", "Element not yet loaded", "Timing issue"],
                    "impact": "Test execution failure"
                },
                "recommendations": [
                    {
                        "priority": "high",
                        "action": "update_selector",
                        "description": "Update selector to match current DOM structure",
                        "implementation": "Use more stable selector strategy"
                    }
                ],
                "confidence": 0.85,
                "metadata": {"analysis_time": 1.5, "patterns_matched": 3}
            }
        } 
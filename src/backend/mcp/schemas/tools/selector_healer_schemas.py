"""
Selector Healer Tool Schemas

Schemas for the selector healing tool that repairs broken/failing selectors
by analyzing DOM changes and suggesting working alternatives.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


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
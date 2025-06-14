"""
Locator Generator Tool Schemas

Schemas for the element locator generation tool that creates CSS selectors,
XPath expressions, and other locators from DOM snapshots and element descriptions.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


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
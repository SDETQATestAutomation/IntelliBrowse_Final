"""
BDD Generator Tool Schemas.

Pydantic schemas for BDD scenario generation tool request and response validation.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


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
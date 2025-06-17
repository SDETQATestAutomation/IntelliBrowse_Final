"""
Step Generator Tool Schemas.

Pydantic schemas for test step generation tool request and response validation.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


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
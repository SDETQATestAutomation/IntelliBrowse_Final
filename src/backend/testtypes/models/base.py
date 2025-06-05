"""
Base Type Data Models

Defines the base TestTypeData class and type-specific implementations
for the multi-test type system using the Factory Pattern approach.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List, Literal
from pydantic import BaseModel, Field

from ..enums import TestType


class TestTypeData(BaseModel):
    """
    Base class for all type-specific data models.
    
    This class provides common fields that all test types share,
    with type-specific data defined in subclasses.
    """
    
    type: TestType = Field(..., description="Test type classification")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, 
        description="Timestamp when type data was created"
    )
    
    class Config:
        """Pydantic model configuration."""
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class BDDBlock(BaseModel):
    """Structure for individual BDD blocks (Given/When/Then)."""
    
    type: str = Field(..., description="BDD block type (Given, When, Then, And, But)")
    content: str = Field(..., description="Block content in natural language")
    keyword: Optional[str] = Field(None, description="Gherkin keyword used")
    
    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "type": "Given",
                "content": "I am on the login page",
                "keyword": "Given"
            }
        }


class BDDTestData(TestTypeData):
    """
    BDD (Behavior-Driven Development) test type data.
    
    Supports Gherkin syntax with Feature/Scenario/Given-When-Then structure.
    """
    
    type: Literal[TestType.BDD] = Field(default=TestType.BDD, description="BDD test type")
    feature_name: str = Field(..., min_length=1, max_length=200, description="BDD feature name")
    scenario_name: str = Field(..., min_length=1, max_length=200, description="BDD scenario name")
    bdd_blocks: List[BDDBlock] = Field(..., min_items=1, description="List of BDD blocks (Given/When/Then)")
    gherkin_syntax_version: str = Field(default="1.0", description="Gherkin syntax version")
    tags: List[str] = Field(default_factory=list, description="BDD scenario tags")
    
    def get_steps_count(self) -> int:
        """Return the number of BDD blocks."""
        return len(self.bdd_blocks)
    
    def get_given_blocks(self) -> List[BDDBlock]:
        """Return all Given blocks."""
        return [block for block in self.bdd_blocks if block.type.lower() == "given"]
    
    def get_when_blocks(self) -> List[BDDBlock]:
        """Return all When blocks."""
        return [block for block in self.bdd_blocks if block.type.lower() == "when"]
    
    def get_then_blocks(self) -> List[BDDBlock]:
        """Return all Then blocks."""
        return [block for block in self.bdd_blocks if block.type.lower() == "then"]
    
    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "type": "bdd",
                "feature_name": "User Authentication",
                "scenario_name": "Successful login with valid credentials",
                "bdd_blocks": [
                    {"type": "Given", "content": "I am on the login page", "keyword": "Given"},
                    {"type": "When", "content": "I enter valid credentials", "keyword": "When"},
                    {"type": "Then", "content": "I should be logged in successfully", "keyword": "Then"}
                ],
                "gherkin_syntax_version": "1.0",
                "tags": ["smoke", "authentication"]
            }
        }


class ManualTestData(TestTypeData):
    """
    Manual test type data for human-authored test cases.
    
    Supports manual execution with documentation, screenshots, and execution metadata.
    """
    
    type: Literal[TestType.MANUAL] = Field(default=TestType.MANUAL, description="Manual test type")
    manual_notes: str = Field(..., min_length=1, description="Detailed manual test instructions")
    expected_outcomes: str = Field(..., min_length=1, description="Expected test outcomes and results")
    screenshot_urls: List[str] = Field(default_factory=list, description="URLs to test screenshots")
    execution_time_estimate: Optional[int] = Field(
        None, 
        ge=1, 
        le=480, 
        description="Estimated execution time in minutes"
    )
    prerequisites: List[str] = Field(default_factory=list, description="Test execution prerequisites")
    test_data_requirements: Optional[str] = Field(None, description="Required test data specifications")
    
    def get_estimated_duration_hours(self) -> Optional[float]:
        """Return estimated execution time in hours."""
        if self.execution_time_estimate:
            return round(self.execution_time_estimate / 60.0, 2)
        return None
    
    def has_screenshots(self) -> bool:
        """Check if manual test has associated screenshots."""
        return len(self.screenshot_urls) > 0
    
    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "type": "manual",
                "manual_notes": "Manually verify user can log in with valid credentials",
                "expected_outcomes": "User successfully logs in and sees dashboard",
                "screenshot_urls": ["https://example.com/screenshot1.png"],
                "execution_time_estimate": 15,
                "prerequisites": ["Test user account exists", "Application is running"],
                "test_data_requirements": "Valid user credentials"
            }
        }


class GenericTestData(TestTypeData):
    """
    Generic test type data for AI/rule-based automated tests.
    
    Optimized for automation with AI insights and selector optimization.
    """
    
    type: Literal[TestType.GENERIC] = Field(default=TestType.GENERIC, description="Generic test type")
    ai_confidence_score: Optional[float] = Field(
        None, 
        ge=0.0, 
        le=1.0, 
        description="AI confidence score for test generation"
    )
    natural_language_steps: List[str] = Field(
        default_factory=list, 
        description="Natural language test steps"
    )
    selector_hints: Dict[str, str] = Field(
        default_factory=dict, 
        description="DOM selector hints for automation"
    )
    automation_priority: Optional[str] = Field(
        None, 
        description="Priority level for automation (high/medium/low)"
    )
    complexity_score: Optional[float] = Field(
        None, 
        ge=0.0, 
        le=1.0, 
        description="Test complexity score"
    )
    
    def is_high_confidence(self, threshold: float = 0.8) -> bool:
        """Check if AI confidence score is above threshold."""
        return self.ai_confidence_score is not None and self.ai_confidence_score >= threshold
    
    def get_steps_count(self) -> int:
        """Return the number of natural language steps."""
        return len(self.natural_language_steps)
    
    def has_selector_hints(self) -> bool:
        """Check if generic test has selector hints."""
        return len(self.selector_hints) > 0
    
    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "type": "generic",
                "ai_confidence_score": 0.95,
                "natural_language_steps": [
                    "Navigate to login page",
                    "Enter username and password",
                    "Click login button",
                    "Verify successful login"
                ],
                "selector_hints": {
                    "username_field": "#username",
                    "password_field": "#password",
                    "login_button": "button[type='submit']"
                },
                "automation_priority": "high",
                "complexity_score": 0.3
            }
        } 
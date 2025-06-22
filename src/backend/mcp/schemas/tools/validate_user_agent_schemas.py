"""
Validate User Agent Schemas for IntelliBrowse MCP Server.
Provides comprehensive Pydantic models for user agent validation and management.
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator


class ValidateUserAgentRequest(BaseModel):
    """Request schema for validate_user_agent tool."""
    
    session_id: str = Field(
        ..., 
        description="Active browser session ID",
        min_length=1
    )
    expected_user_agent: str = Field(
        ..., 
        description="Expected user agent string to validate against",
        min_length=1,
        max_length=2000  # Reasonable limit for user agent strings
    )
    set_if_different: Optional[bool] = Field(
        False, 
        description="Update user agent if different from expected"
    )
    strict_validation: Optional[bool] = Field(
        True, 
        description="Perform strict exact match validation"
    )
    case_sensitive: Optional[bool] = Field(
        True, 
        description="Case-sensitive string comparison"
    )
    analyze_components: Optional[bool] = Field(
        True, 
        description="Analyze and extract user agent components"
    )
    timeout_ms: Optional[int] = Field(
        5000, 
        description="Operation timeout in milliseconds",
        ge=1000,
        le=30000
    )

    @field_validator('expected_user_agent')


    @classmethod
    def validate_expected_user_agent(cls, v):
        """Validate expected user agent string."""
        if not v or len(v.strip()) == 0:
            raise ValueError("Expected user agent cannot be empty")
        
        # Basic format validation - should contain typical UA components
        v_lower = v.lower()
        if not any(keyword in v_lower for keyword in ['mozilla', 'webkit', 'chrome', 'firefox', 'safari', 'opera', 'edge']):
            raise ValueError("User agent string appears to be invalid - missing browser identifier")
        
        return v.strip()

    class Config:
        """Pydantic config."""
        extra = "forbid"
        schema_extra = {
            "example": {
                "session_id": "session_123",
                "expected_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "set_if_different": False,
                "strict_validation": True,
                "case_sensitive": True,
                "analyze_components": True,
                "timeout_ms": 5000
            }
        }


class ValidateUserAgentResponse(BaseModel):
    """Response schema for validate_user_agent tool."""
    
    success: bool = Field(..., description="Whether validation operation succeeded")
    message: str = Field(..., description="Operation result message")
    
    # Validation results
    validation_passed: bool = Field(..., description="Whether user agent validation passed")
    current_user_agent: Optional[str] = Field(None, description="Current browser user agent")
    expected_user_agent: str = Field(..., description="Expected user agent string")
    
    # User agent analysis
    user_agent_analysis: Optional[Dict[str, Any]] = Field(None, description="Detailed user agent component analysis")
    differences: Optional[List[str]] = Field(None, description="Differences between current and expected")
    similarity_score: Optional[float] = Field(None, description="Similarity score (0.0-1.0)")
    
    # Update information (if set_if_different was used)
    user_agent_updated: Optional[bool] = Field(None, description="Whether user agent was updated")
    previous_user_agent: Optional[str] = Field(None, description="Previous user agent before update")
    
    # Validation configuration
    strict_validation: bool = Field(..., description="Whether strict validation was used")
    case_sensitive: bool = Field(..., description="Whether case-sensitive comparison was used")
    
    # Operation metadata
    operation_time_ms: Optional[int] = Field(None, description="Total validation operation time")
    
    # Session and timing
    session_id: str = Field(..., description="Browser session ID")
    timestamp: str = Field(..., description="Operation timestamp")
    
    # Error details (if any)
    error_type: Optional[str] = Field(None, description="Error type if operation failed")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Detailed error information")

    class Config:
        """Pydantic config."""
        extra = "forbid"
        schema_extra = {
            "example": {
                "success": True,
                "message": "User agent validation completed successfully",
                "validation_passed": True,
                "current_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "expected_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "user_agent_analysis": {
                    "browser": "Chrome",
                    "version": "120.0.0.0",
                    "platform": "Windows NT 10.0; Win64; x64",
                    "engine": "WebKit/537.36",
                    "rendering_engine": "Blink"
                },
                "differences": [],
                "similarity_score": 1.0,
                "user_agent_updated": False,
                "previous_user_agent": None,
                "strict_validation": True,
                "case_sensitive": True,
                "operation_time_ms": 125,
                "session_id": "session_123",
                "timestamp": "2024-01-18T12:00:00Z"
            }
        } 
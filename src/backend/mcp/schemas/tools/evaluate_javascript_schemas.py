"""
Evaluate JavaScript Schemas for IntelliBrowse MCP Server.
Provides comprehensive Pydantic models for secure JavaScript execution with validation.
"""

from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field, field_validator


class EvaluateJavaScriptRequest(BaseModel):
    """Request schema for evaluate_javascript tool."""
    
    session_id: str = Field(
        ..., 
        description="Active browser session ID",
        min_length=1
    )
    script: str = Field(
        ..., 
        description="JavaScript code to execute",
        min_length=1,
        max_length=10000  # Security limit on script length
    )
    args: Optional[List[Any]] = Field(
        None, 
        description="Arguments to pass to the script"
    )
    timeout_ms: Optional[int] = Field(
        5000, 
        description="Script execution timeout in milliseconds",
        ge=100,
        le=30000  # Maximum 30 seconds for security
    )
    security_context: Optional[str] = Field(
        "restricted", 
        description="Security level (restricted, elevated)"
    )
    return_by_value: Optional[bool] = Field(
        True, 
        description="Return result by value instead of handle"
    )
    await_promise: Optional[bool] = Field(
        False, 
        description="Wait for Promise resolution if script returns Promise"
    )
    world_name: Optional[str] = Field(
        None, 
        description="Isolated world name for script execution"
    )

    @field_validator('security_context')


    @classmethod
    def validate_security_context(cls, v):
        """Validate security context parameter."""
        valid_contexts = ['restricted', 'elevated']
        if v not in valid_contexts:
            raise ValueError(f"security_context must be one of: {valid_contexts}")
        return v

    @field_validator('script')


    @classmethod
    def validate_script(cls, v):
        """Validate JavaScript script content for basic security."""
        if not v or len(v.strip()) == 0:
            raise ValueError("Script cannot be empty")
        
        # Basic security checks for restricted context
        dangerous_patterns = [
            'eval(',
            'Function(',
            'setTimeout(',
            'setInterval(',
            'XMLHttpRequest',
            'fetch(',
            'import(',
            'require(',
            'process.',
            'global.',
            'window.location',
            'document.cookie',
            'localStorage.',
            'sessionStorage.',
            '__proto__',
            'constructor.constructor'
        ]
        
        script_lower = v.lower()
        for pattern in dangerous_patterns:
            if pattern.lower() in script_lower:
                raise ValueError(f"Potentially unsafe pattern detected: {pattern}")
        
        return v

    @field_validator('args')


    @classmethod
    def validate_args(cls, v):
        """Validate script arguments."""
        if v is not None:
            if len(v) > 10:  # Limit number of arguments
                raise ValueError("Maximum 10 arguments allowed")
            
            # Check for complex objects that might be dangerous
            for arg in v:
                if callable(arg):
                    raise ValueError("Function arguments not allowed")
        
        return v

    class Config:
        """Pydantic config."""
        extra = "forbid"
        schema_extra = {
            "example": {
                "session_id": "session_123",
                "script": "return document.title;",
                "args": None,
                "timeout_ms": 5000,
                "security_context": "restricted",
                "return_by_value": True,
                "await_promise": False,
                "world_name": "isolated_execution"
            }
        }


class EvaluateJavaScriptResponse(BaseModel):
    """Response schema for evaluate_javascript tool."""
    
    success: bool = Field(..., description="Whether script execution succeeded")
    message: str = Field(..., description="Operation result message")
    
    # Script execution results
    result: Optional[Any] = Field(None, description="Script execution result")
    result_type: Optional[str] = Field(None, description="Type of the result")
    
    # Security and execution context
    security_context: Optional[str] = Field(None, description="Security context used")
    script_hash: Optional[str] = Field(None, description="SHA256 hash of executed script")
    execution_world: Optional[str] = Field(None, description="Execution world/context name")
    
    # Execution metadata
    execution_time_ms: Optional[int] = Field(None, description="Script execution time")
    promise_resolved: Optional[bool] = Field(None, description="Whether Promise was resolved")
    console_logs: Optional[List[Dict[str, Any]]] = Field(None, description="Console logs during execution")
    
    # Session and timing
    session_id: str = Field(..., description="Browser session ID")
    timestamp: str = Field(..., description="Operation timestamp")
    
    # Security audit information
    security_checks: Optional[Dict[str, Any]] = Field(None, description="Security validation results")
    restricted_apis_accessed: Optional[List[str]] = Field(None, description="Restricted APIs accessed")
    
    # Error details (if any)
    error_type: Optional[str] = Field(None, description="Error type if execution failed")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Detailed error information")

    class Config:
        """Pydantic config."""
        extra = "forbid"
        schema_extra = {
            "example": {
                "success": True,
                "message": "Script executed successfully",
                "result": "IntelliBrowse - Test Automation Platform",
                "result_type": "string",
                "security_context": "restricted",
                "script_hash": "a1b2c3d4e5f6...",
                "execution_world": "isolated_execution",
                "execution_time_ms": 45,
                "promise_resolved": False,
                "console_logs": [
                    {
                        "type": "log",
                        "message": "Script execution started",
                        "timestamp": "2024-01-18T12:00:00.123Z"
                    }
                ],
                "session_id": "session_123",
                "timestamp": "2024-01-18T12:00:00Z",
                "security_checks": {
                    "dangerous_patterns": 0,
                    "api_restrictions": ["file_system", "network"],
                    "validation_passed": True
                },
                "restricted_apis_accessed": []
            }
        } 
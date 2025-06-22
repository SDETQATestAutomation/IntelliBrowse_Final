"""
Tool Schemas for IntelliBrowse MCP Server

This module defines Pydantic schemas for MCP tool requests and responses.
These schemas ensure type safety and validation for all tool operations.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


# Base schemas
class ToolRequest(BaseModel):
    """Base schema for tool requests."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    class Config:
        extra = "allow"


class ToolResponse(BaseModel):
    """Base schema for tool responses."""
    success: bool = Field(..., description="Operation success status")
    message: str = Field("", description="Response message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        extra = "allow"


# BDD Generator schemas
class BDDGeneratorRequest(ToolRequest):
    """Request schema for BDD generator tool."""
    user_story: str = Field(..., description="User story text")
    acceptance_criteria: List[str] = Field(..., description="List of acceptance criteria")
    
    
class BDDGeneratorResponse(ToolResponse):
    """Response schema for BDD generator tool."""
    scenario: Optional[str] = Field(None, description="Generated BDD scenario")
    feature: Optional[str] = Field(None, description="Generated feature file")


# Locator Generator schemas
class LocatorGeneratorRequest(ToolRequest):
    """Request schema for locator generator tool."""
    element_description: str = Field(..., description="Description of the element")
    page_context: Optional[str] = Field(None, description="Page context information")
    

class LocatorGeneratorResponse(ToolResponse):
    """Response schema for locator generator tool."""
    locators: List[Dict[str, Any]] = Field(default_factory=list, description="Generated locators")
    

# Step Generator schemas
class StepGeneratorRequest(ToolRequest):
    """Request schema for step generator tool."""
    action: str = Field(..., description="Action to generate steps for")
    

class StepGeneratorResponse(ToolResponse):
    """Response schema for step generator tool."""
    steps: List[str] = Field(default_factory=list, description="Generated test steps")


# Selector Healer schemas
class SelectorHealerRequest(ToolRequest):
    """Request schema for selector healer tool."""
    broken_selector: str = Field(..., description="Broken selector to heal")
    

class SelectorHealerResponse(ToolResponse):
    """Response schema for selector healer tool."""
    healed_selector: Optional[str] = Field(None, description="Healed selector")
    confidence: float = Field(0.0, description="Confidence in healing")


# Debug Analyzer schemas
class DebugAnalyzerRequest(ToolRequest):
    """Request schema for debug analyzer tool."""
    error_message: str = Field(..., description="Error message to analyze")
    

class DebugAnalyzerResponse(ToolResponse):
    """Response schema for debug analyzer tool."""
    analysis: Optional[str] = Field(None, description="Debug analysis")
    suggestions: List[str] = Field(default_factory=list, description="Fix suggestions")


# Browser operation schemas
class OpenBrowserRequest(ToolRequest):
    """Request schema for opening browser."""
    headless: bool = Field(True, description="Run in headless mode")
    

class OpenBrowserResponse(ToolResponse):
    """Response schema for opening browser."""
    browser_id: Optional[str] = Field(None, description="Browser instance ID")


class CloseBrowserRequest(ToolRequest):
    """Request schema for closing browser."""
    browser_id: Optional[str] = Field(None, description="Browser instance ID to close")
    

class CloseBrowserResponse(ToolResponse):
    """Response schema for closing browser."""
    pass


class NavigateToUrlRequest(ToolRequest):
    """Request schema for navigating to URL."""
    url: str = Field(..., description="URL to navigate to")
    

class NavigateToUrlResponse(ToolResponse):
    """Response schema for navigating to URL."""
    final_url: Optional[str] = Field(None, description="Final URL after navigation")


# Tool call schemas for agent integration
class ToolCallRequest(BaseModel):
    """Request schema for tool calls in agent integration."""
    tool_name: str = Field(..., description="Name of the tool to call")
    args: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments")
    session_id: Optional[str] = Field(None, description="Session identifier")
    context: Optional[Dict[str, Any]] = Field(None, description="Execution context")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        extra = "allow"


class ToolCallResponse(BaseModel):
    """Response schema for tool calls in agent integration."""
    success: bool = Field(..., description="Tool execution success status")
    result: Optional[Dict[str, Any]] = Field(None, description="Tool execution result")
    error: Optional[str] = Field(None, description="Error message if execution failed")
    tool_name: str = Field(..., description="Name of the executed tool")
    execution_time: Optional[float] = Field(None, description="Tool execution time in seconds")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        extra = "allow"


# Legacy aliases for backward compatibility
BDDRequest = BDDGeneratorRequest
BDDResponse = BDDGeneratorResponse
LocatorRequest = LocatorGeneratorRequest
LocatorResponse = LocatorGeneratorResponse
StepRequest = StepGeneratorRequest
StepResponse = StepGeneratorResponse
SelectorRequest = SelectorHealerRequest
SelectorResponse = SelectorHealerResponse
DebugRequest = DebugAnalyzerRequest
DebugResponse = DebugAnalyzerResponse 
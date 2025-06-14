"""
Pydantic schemas for IntelliBrowse MCP Server.

All request/response schemas, context models, and validation schemas
for the Model Context Protocol implementation.
"""

from .context_schemas import SessionContext, TaskContext, UserContext
from .tool_schemas import (
    # New standardized schema names
    BDDGeneratorRequest, BDDGeneratorResponse,
    LocatorGeneratorRequest, LocatorGeneratorResponse,
    StepGeneratorRequest, StepGeneratorResponse,
    SelectorHealerRequest, SelectorHealerResponse,
    DebugAnalyzerRequest, DebugAnalyzerResponse,
    OpenBrowserRequest, OpenBrowserResponse,
    CloseBrowserRequest, CloseBrowserResponse,
    
    # Legacy schema names for backward compatibility
    BDDRequest, BDDResponse,
    LocatorRequest, LocatorResponse,
    StepRequest, StepResponse,
    SelectorRequest, SelectorResponse,
    DebugRequest, DebugResponse,
    
    # Navigate to URL
    NavigateToUrlRequest,
    NavigateToUrlResponse,
)

__all__ = [
    # Context schemas
    "SessionContext",
    "TaskContext", 
    "UserContext",
    
    # New standardized tool schemas
    "BDDGeneratorRequest",
    "BDDGeneratorResponse",
    "LocatorGeneratorRequest", 
    "LocatorGeneratorResponse",
    "StepGeneratorRequest",
    "StepGeneratorResponse",
    "SelectorHealerRequest",
    "SelectorHealerResponse",
    "DebugAnalyzerRequest",
    "DebugAnalyzerResponse",
    "OpenBrowserRequest",
    "OpenBrowserResponse",
    "CloseBrowserRequest",
    "CloseBrowserResponse",
    
    # Legacy tool schemas (for backward compatibility)
    "BDDRequest",
    "BDDResponse",
    "LocatorRequest",
    "LocatorResponse",
    "StepRequest",
    "StepResponse",
    "SelectorRequest",
    "SelectorResponse",
    "DebugRequest",
    "DebugResponse",
    
    # Navigate to URL
    "NavigateToUrlRequest",
    "NavigateToUrlResponse",
] 
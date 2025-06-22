"""
Natural Language Processing Endpoints for IntelliBrowse MCP Server

This module provides REST API endpoints for natural language command processing,
integrating with the AI Agent Orchestrator for intelligent automation.

Enterprise Features:
- Natural language command processing
- Session management and context persistence
- Conversation history management
- Comprehensive error handling and validation
- Integration with AI agent orchestration
"""

from typing import Any, Dict, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field, field_validator
import structlog

try:
    from orchestration.agent_integration import get_agent_integration_manager
except ImportError:
    # Fallback for when running directly from mcp directory
    from orchestration.agent_integration import get_agent_integration_manager

try:
    from core.exceptions import AIAgentError, NLPProcessingError
except ImportError:
    # Fallback for when running directly from mcp directory
    from core.exceptions import AIAgentError, NLPProcessingError

try:
    from schemas.context_schemas import SessionContext
except ImportError:
    # Fallback for when running directly from mcp directory
    from schemas.context_schemas import SessionContext

# Configure logger
logger = structlog.get_logger("intellibrowse.mcp.core.nlp_endpoints")

# Create router
nlp_router = APIRouter(prefix="/api/nlp", tags=["Natural Language Processing"])


class NLPCommandRequest(BaseModel):
    """Request model for natural language commands."""
    command: str = Field(..., min_length=1, max_length=10000, description="Natural language command")
    session_id: Optional[str] = Field(None, description="Session identifier for context persistence")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional execution context")
    history: Optional[List[Dict[str, str]]] = Field(None, description="Conversation history")
    
    @field_validator('command')

    
    @classmethod
    def validate_command(cls, v):
        if not v.strip():
            raise ValueError("Command cannot be empty or whitespace only")
        # Basic security check
        dangerous_patterns = ['<script', 'javascript:', 'eval(', 'exec(']
        if any(pattern in v.lower() for pattern in dangerous_patterns):
            raise ValueError("Command contains potentially dangerous content")
        return v.strip()


class NLPCommandResponse(BaseModel):
    """Response model for natural language commands."""
    response: str = Field(..., description="AI agent response to the command")
    success: bool = Field(..., description="Whether the command executed successfully")
    session_id: Optional[str] = Field(None, description="Session identifier")
    context: Optional[Dict[str, Any]] = Field(None, description="Updated execution context")
    history: Optional[List[Dict[str, str]]] = Field(None, description="Updated conversation history")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(None, description="Tools that were invoked")
    workflow_id: Optional[str] = Field(None, description="Workflow identifier if workflow was created")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Response metadata")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="Response timestamp")


class ConversationRequest(BaseModel):
    """Request model for conversation management."""
    message: str = Field(..., min_length=1, max_length=5000, description="Conversation message")
    session_id: Optional[str] = Field(None, description="Session identifier")
    
    @field_validator('message')

    
    @classmethod
    def validate_message(cls, v):
        if not v.strip():
            raise ValueError("Message cannot be empty or whitespace only")
        return v.strip()


class ConversationResponse(BaseModel):
    """Response model for conversation management."""
    response: str = Field(..., description="AI assistant response")
    session_id: str = Field(..., description="Session identifier")
    conversation_id: Optional[str] = Field(None, description="Conversation identifier")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Response metadata")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="Response timestamp")


class ToolsListResponse(BaseModel):
    """Response model for available tools list."""
    tools: Dict[str, Dict[str, Any]] = Field(..., description="Available tools and their schemas")
    count: int = Field(..., description="Number of available tools")
    categories: List[str] = Field(default_factory=list, description="Tool categories")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="Response timestamp")


@nlp_router.post("/command", response_model=NLPCommandResponse, status_code=status.HTTP_200_OK)
async def process_nlp_command(
    request: NLPCommandRequest,
    agent_manager = Depends(get_agent_integration_manager)
) -> NLPCommandResponse:
    """
    Process a natural language command using AI agent orchestration.
    
    This endpoint accepts natural language commands and uses AI agent orchestration
    to determine the appropriate tools to execute and provide intelligent responses.
    
    Features:
    - Intelligent command interpretation and tool selection
    - Context-aware execution with session management
    - Conversation history tracking
    - Comprehensive error handling and validation
    """
    try:
        logger.info(
            f"Processing NLP command: {request.command[:100]}...",
            extra={
                "service": "nlp_endpoints",
                "action": "process_command",
                "session_id": request.session_id,
                "command_length": len(request.command),
                "audit": True
            }
        )
        
        # Process command using agent integration manager
        agent_response = await agent_manager.process_natural_language_command(
            command=request.command,
            session_id=request.session_id,
            context=request.context,
            history=request.history
        )
        
        # Convert agent response to API response
        response = NLPCommandResponse(
            response=agent_response.response,
            success=agent_response.success,
            session_id=agent_response.session_id,
            context=agent_response.context,
            history=agent_response.history,
            tool_calls=agent_response.tool_calls,
            workflow_id=agent_response.workflow_id,
            metadata=agent_response.metadata
        )
        
        logger.info(
            f"NLP command processed successfully",
            extra={
                "service": "nlp_endpoints",
                "action": "process_command_success",
                "session_id": agent_response.session_id,
                "success": agent_response.success,
                "tool_calls_count": len(agent_response.tool_calls or []),
                "audit": True
            }
        )
        
        return response
        
    except NLPProcessingError as e:
        logger.error(
            f"NLP processing error: {e}",
            extra={
                "service": "nlp_endpoints",
                "action": "process_command_nlp_error",
                "session_id": request.session_id,
                "error": str(e),
                "audit": True
            }
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Command processing failed: {str(e)}"
        )
    
    except AIAgentError as e:
        logger.error(
            f"AI agent error: {e}",
            extra={
                "service": "nlp_endpoints",
                "action": "process_command_agent_error",
                "session_id": request.session_id,
                "error": str(e),
                "audit": True
            }
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI agent service error: {str(e)}"
        )
    
    except Exception as e:
        logger.error(
            f"Unexpected error processing NLP command: {e}",
            extra={
                "service": "nlp_endpoints",
                "action": "process_command_error",
                "session_id": request.session_id,
                "error": str(e),
                "audit": True
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@nlp_router.post("/conversation", response_model=ConversationResponse, status_code=status.HTTP_200_OK)
async def process_conversation(
    request: ConversationRequest,
    agent_manager = Depends(get_agent_integration_manager)
) -> ConversationResponse:
    """
    Process a conversational message with context awareness.
    
    This endpoint handles casual conversation and context-aware interactions,
    maintaining conversation flow and providing helpful responses.
    """
    try:
        logger.info(
            f"Processing conversation message: {request.message[:100]}...",
            extra={
                "service": "nlp_endpoints",
                "action": "process_conversation",
                "session_id": request.session_id,
                "audit": True
            }
        )
        
        # Process as a conversation-style command
        agent_response = await agent_manager.process_natural_language_command(
            command=request.message,
            session_id=request.session_id
        )
        
        response = ConversationResponse(
            response=agent_response.response,
            session_id=agent_response.session_id or "conversation_session",
            metadata={
                "processing_method": agent_response.metadata.get("processing_method", "conversation"),
                "tool_calls_count": len(agent_response.tool_calls or []),
                "success": agent_response.success
            }
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error processing conversation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Conversation processing failed: {str(e)}"
        )


@nlp_router.get("/tools", response_model=ToolsListResponse, status_code=status.HTTP_200_OK)
async def get_available_tools(
    agent_manager = Depends(get_agent_integration_manager)
) -> ToolsListResponse:
    """
    Get list of available tools and their capabilities.
    
    Returns information about all tools available for natural language commands,
    including their descriptions, parameters, and usage examples.
    """
    try:
        logger.info(
            "Fetching available tools",
            extra={
                "service": "nlp_endpoints",
                "action": "get_tools",
                "audit": True
            }
        )
        
        tools = await agent_manager.get_available_tools()
        
        # Extract tool categories
        categories = list(set([
            tool_info.get("category", "general")
            for tool_info in tools.values()
        ]))
        
        response = ToolsListResponse(
            tools=tools,
            count=len(tools),
            categories=categories
        )
        
        logger.info(
            f"Retrieved {len(tools)} available tools",
            extra={
                "service": "nlp_endpoints",
                "action": "get_tools_success",
                "tool_count": len(tools),
                "audit": True
            }
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error fetching available tools: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch tools: {str(e)}"
        )


@nlp_router.get("/health", status_code=status.HTTP_200_OK)
async def nlp_health_check(
    agent_manager = Depends(get_agent_integration_manager)
) -> Dict[str, Any]:
    """
    Perform health check on the NLP processing system.
    
    Returns the status of the AI agent orchestration system,
    including availability of tools and processing capabilities.
    """
    try:
        health_status = await agent_manager.health_check()
        
        # Add endpoint-specific health information
        health_status.update({
            "nlp_endpoints": "healthy",
            "endpoints_available": [
                "/api/nlp/command",
                "/api/nlp/conversation",
                "/api/nlp/tools",
                "/api/nlp/health"
            ]
        })
        
        return health_status
        
    except Exception as e:
        logger.error(f"NLP health check failed: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "nlp_endpoints": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@nlp_router.get("/capabilities", status_code=status.HTTP_200_OK)
async def get_nlp_capabilities() -> Dict[str, Any]:
    """
    Get information about NLP processing capabilities.
    
    Returns details about supported command types, patterns,
    and processing features available in the system.
    """
    return {
        "supported_commands": [
            "Web navigation (navigate to URL, go to page)",
            "Element interaction (click, fill, hover, select)",
            "Page inspection (analyze DOM, find elements)",
            "Test generation (BDD scenarios, test steps)",
            "Debugging (console logs, network analysis)",
            "Content extraction (text, data, screenshots)"
        ],
        "command_patterns": [
            "Natural language descriptions",
            "Action-based commands",
            "Question and answer format",
            "Multi-step workflows"
        ],
        "features": [
            "Context-aware processing",
            "Session management",
            "Conversation history",
            "Intelligent tool selection",
            "Error handling and recovery",
            "Audit logging"
        ],
        "supported_languages": ["English"],
        "max_command_length": 10000,
        "max_conversation_length": 5000,
        "session_persistence": True,
        "timestamp": datetime.utcnow().isoformat()
    } 
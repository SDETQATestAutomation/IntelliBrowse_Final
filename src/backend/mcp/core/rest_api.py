"""
IntelliBrowse MCP Server - REST API Layer

This module provides FastAPI REST endpoints for legacy client compatibility
while maintaining enterprise-grade error handling and MCP protocol integration.
"""

import asyncio
import json
import re
from typing import Dict, List, Optional, Any
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
import structlog

try:
    from client import IntelliBrowseMCPClient
except ImportError:
    # Fallback for when running directly from mcp directory
    from client import IntelliBrowseMCPClient

try:
    from config.settings import MCPSettings
except ImportError:
    # Fallback for when running directly from mcp directory
    from config.settings import MCPSettings

try:
    from core.exceptions import MCPError
except ImportError:
    # Fallback for when running directly from mcp directory
    from core.exceptions import MCPError

try:
    from core.nlp_endpoints import nlp_router
except ImportError:
    # Fallback for when running directly from mcp directory
    from core.nlp_endpoints import nlp_router

# Configure logger
logger = structlog.get_logger("intellibrowse.mcp.rest_api")

# Initialize settings
settings = MCPSettings()

# Request/Response Models
class CommandRequest(BaseModel):
    """Request model for the /api/command endpoint."""
    command: str = Field(..., min_length=1, max_length=10000, description="Natural language command to execute")
    history: Optional[List[Dict[str, str]]] = Field(None, description="Optional conversation history")
    context: Optional[Dict[str, Any]] = Field(None, description="Optional execution context")
    
    @field_validator('command')

    
    @classmethod
    def validate_command(cls, v):
        if not v.strip():
            raise ValueError("Command cannot be empty or whitespace only")
        return v.strip()

class CommandResponse(BaseModel):
    """Response model for the /api/command endpoint."""
    response: str = Field(..., description="AI-generated response to the command")
    success: bool = Field(..., description="Whether the command executed successfully")
    history: Optional[List[Dict[str, str]]] = Field(None, description="Updated conversation history")
    context: Optional[Dict[str, Any]] = Field(None, description="Updated execution context")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(None, description="Tools that were invoked")

class BDDRequest(BaseModel):
    """Request model for the /api/generate-bdd endpoint."""
    description: str = Field(..., min_length=1, max_length=50000, description="Natural language feature description")
    user_story: Optional[str] = Field(None, description="Optional user story context")
    acceptance_criteria: Optional[List[str]] = Field(None, description="Optional acceptance criteria list")
    
    @field_validator('description')

    
    @classmethod
    def validate_description(cls, v):
        if not v.strip():
            raise ValueError("Description cannot be empty or whitespace only") 
        return v.strip()

class BDDResponse(BaseModel):
    """Response model for the /api/generate-bdd endpoint."""
    gherkin: str = Field(..., description="Generated Gherkin feature file content")
    success: bool = Field(..., description="Whether BDD generation was successful")
    validation_passed: bool = Field(..., description="Whether Gherkin syntax validation passed")
    suggestions: Optional[List[str]] = Field(None, description="Suggestions for improvement")

class HealthResponse(BaseModel):
    """Response model for health check endpoint."""
    status: str = Field(..., description="Health status")
    message: str = Field(..., description="Health status message")
    mcp_server_status: str = Field(..., description="MCP server connection status")
    components: Dict[str, str] = Field(..., description="Component health status")
    timestamp: str = Field(..., description="Health check timestamp")

# Command Processing Logic
class CommandProcessor:
    """Processes natural language commands using MCP client."""
    
    def __init__(self):
        self.mcp_client = None
        self._interaction_actions = {
            "click": "click_element",
            "hover": "hover_element", 
            "fill": "fill_element",
            "type": "type_text",
            "enter": "type_text",
            "select": "click_element",  # Can be mapped to appropriate selection tool
            "drag": "hover_element"   # Placeholder for drag operations
        }
    
    async def initialize(self):
        """Initialize MCP client connection."""
        try:
            # Construct MCP server URL based on settings
            mcp_url = f"http://{settings.mcp_host}:{settings.mcp_port}/sse"
            self.mcp_client = IntelliBrowseMCPClient(mcp_url)
            await self.mcp_client.__aenter__()
            logger.info("MCP client initialized successfully", mcp_url=mcp_url)
        except Exception as e:
            logger.error("Failed to initialize MCP client", error=str(e))
            raise MCPError(f"MCP client initialization failed: {e}")
    
    async def cleanup(self):
        """Cleanup MCP client connection."""
        if self.mcp_client:
            try:
                await self.mcp_client.__aexit__(None, None, None)
                logger.info("MCP client cleaned up successfully")
            except Exception as e:
                logger.warning("Error during MCP client cleanup", error=str(e))
    
    async def process_command(self, command: str, history: Optional[List[Dict]] = None, 
                            context: Optional[Dict] = None) -> CommandResponse:
        """
        Process natural language command using MCP tools.
        
        Args:
            command: Natural language command
            history: Optional conversation history
            context: Optional execution context
            
        Returns:
            CommandResponse with execution results
        """
        if not self.mcp_client:
            await self.initialize()
        
        try:
            # Step 1: Try heuristic command parsing for simple actions
            parsed_action = await self._parse_simple_command(command)
            
            if parsed_action:
                # Execute direct tool call for simple commands
                result = await self._execute_direct_action(parsed_action, context)
                return CommandResponse(
                    response=result.get("message", "Command executed successfully"),
                    success=result.get("success", True),
                    history=self._update_history(history, command, result.get("message", "")),
                    context=context,
                    tool_calls=[{
                        "tool": parsed_action["tool"],
                        "args": parsed_action["args"],
                        "result": result
                    }]
                )
            
            # Step 2: Use AI orchestration for complex commands
            return await self._process_complex_command(command, history, context)
            
        except Exception as e:
            logger.error("Command processing failed", command=command, error=str(e))
            return CommandResponse(
                response=f"I encountered an error processing your command: {str(e)}",
                success=False,
                history=self._update_history(history, command, f"Error: {str(e)}"),
                context=context
            )
    
    async def _parse_simple_command(self, command: str) -> Optional[Dict]:
        """Parse simple commands like 'click login button'."""
        command_lower = command.lower().strip()
        
        # Skip parsing if command contains selector-like characters
        if re.search(r'[#/\[\].]', command):
            return None
            
        # Check for interaction verbs
        for verb, tool_name in self._interaction_actions.items():
            if command_lower.startswith(verb + " "):
                target_description = command[len(verb):].strip()
                
                # Handle fill/type commands with value extraction
                if verb in ["fill", "type", "enter"]:
                    # Try to parse "fill 'value' in element" or "fill element with 'value'"
                    match1 = re.search(r'^([\'"]?)(.*?)\1\s+(?:in|into|for)\s+(.*)$', target_description, re.IGNORECASE)
                    match2 = re.search(r'^(.*?)\s+(?:with|as)\s+([\'"]?)(.*?)\2$', target_description, re.IGNORECASE)
                    
                    if match1:
                        value = match1.group(2)
                        element_desc = match1.group(3).strip()
                        return {
                            "tool": tool_name,
                            "args": {"element_description": element_desc, "value": value},
                            "needs_locator": True
                        }
                    elif match2:
                        element_desc = match2.group(1).strip()
                        value = match2.group(3)
                        return {
                            "tool": tool_name,
                            "args": {"element_description": element_desc, "value": value},
                            "needs_locator": True
                        }
                
                # Simple click/hover commands
                if target_description:
                    return {
                        "tool": tool_name,
                        "args": {"element_description": target_description},
                        "needs_locator": True
                    }
        
        return None
    
    async def _execute_direct_action(self, action: Dict, context: Optional[Dict] = None) -> Dict:
        """Execute direct tool action."""
        try:
            tool_name = action["tool"]
            args = action["args"].copy()
            
            # If action needs locator, generate it first
            if action.get("needs_locator"):
                element_desc = args.pop("element_description", "")
                if element_desc:
                    # Generate locator using vector search or locator generator
                    locator_result = await self.mcp_client.call_tool("locator_generator", {
                        "element_description": element_desc,
                        "strategy": "auto"
                    })
                    
                    if locator_result.get("success"):
                        args["locator"] = locator_result["data"]["primary_locator"]
                    else:
                        return {
                            "success": False,
                            "message": f"Could not find element: {element_desc}",
                            "error": locator_result.get("error", "Locator generation failed")
                        }
            
            # Execute the tool
            result = await self.mcp_client.call_tool(tool_name, args)
            return result
            
        except Exception as e:
            logger.error("Direct action execution failed", action=action, error=str(e))
            return {
                "success": False,
                "message": f"Action execution failed: {str(e)}",
                "error": str(e)
            }
    
    async def _process_complex_command(self, command: str, history: Optional[List[Dict]] = None,
                                     context: Optional[Dict] = None) -> CommandResponse:
        """Process complex commands using AI orchestration."""
        try:
            # Get available tools
            tools = await self.mcp_client.list_tools()
            
            # Create orchestration context
            orchestration_context = {
                "command": command,
                "available_tools": [t.name for t in tools],
                "history": history or [],
                "execution_context": context or {}
            }
            
            # Use step generator to create execution plan
            plan_result = await self.mcp_client.call_tool("step_generator", {
                "user_story": command,
                "context": orchestration_context
            })
            
            if not plan_result.get("success"):
                return CommandResponse(
                    response="I couldn't create an execution plan for your command. Please try rephrasing it.",
                    success=False,
                    history=self._update_history(history, command, "Planning failed"),
                    context=context
                )
            
            # Execute the generated steps
            steps = plan_result["data"].get("steps", [])
            tool_calls = []
            final_response = ""
            
            for step in steps:
                if "tool" in step and "args" in step:
                    step_result = await self.mcp_client.call_tool(step["tool"], step["args"])
                    tool_calls.append({
                        "tool": step["tool"],
                        "args": step["args"],
                        "result": step_result
                    })
                    
                    if not step_result.get("success"):
                        final_response = step_result.get("message", "Step execution failed")
                        break
                    else:
                        final_response = step_result.get("message", "Step completed successfully")
            
            return CommandResponse(
                response=final_response or "Command completed successfully",
                success=True,
                history=self._update_history(history, command, final_response),
                context=context,
                tool_calls=tool_calls
            )
            
        except Exception as e:
            logger.error("Complex command processing failed", command=command, error=str(e))
            return CommandResponse(
                response=f"I encountered an error processing your command: {str(e)}",
                success=False,
                history=self._update_history(history, command, f"Error: {str(e)}"),
                context=context
            )
    
    def _update_history(self, history: Optional[List[Dict]], user_message: str, 
                       assistant_message: str) -> List[Dict]:
        """Update conversation history."""
        if history is None:
            history = []
        
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": assistant_message})
        
        # Keep only last 20 messages to prevent unbounded growth
        return history[-20:]

# Global processor instance
command_processor = CommandProcessor()

# FastAPI Application
def create_rest_api() -> FastAPI:
    """
    Create and configure FastAPI application with comprehensive MCP integration.
    
    Returns:
        FastAPI: Configured application instance
    """
    app = FastAPI(
        title="IntelliBrowse MCP REST API",
        description="REST API for IntelliBrowse Model Context Protocol Server",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include NLP router for natural language processing endpoints
    app.include_router(nlp_router)
    
    @app.on_event("startup")
    async def startup_event():
        """Initialize MCP client on startup."""
        try:
            await command_processor.initialize()
            logger.info("REST API initialized successfully")
        except Exception as e:
            logger.error("REST API initialization failed", error=str(e))
            raise
    
    @app.on_event("shutdown")
    async def shutdown_event():
        """Cleanup on shutdown."""
        await command_processor.cleanup()
        logger.info("REST API shutdown complete")
    
    @app.get("/health", response_model=HealthResponse, tags=["Health"])
    async def health_check():
        """Health check endpoint."""
        try:
            # Check MCP server connection
            mcp_status = "connected"
            if command_processor.mcp_client:
                try:
                    tools = await command_processor.mcp_client.list_tools()
                    mcp_status = f"connected ({len(tools)} tools)"
                except:
                    mcp_status = "disconnected"
            else:
                mcp_status = "not_initialized"
            
            return HealthResponse(
                status="ok",
                message="IntelliBrowse MCP REST API is running",
                mcp_server_status=mcp_status,
                components={
                    "mcp_client": mcp_status,
                    "command_processor": "ok",
                    "rest_api": "ok"
                },
                timestamp=str(asyncio.get_event_loop().time())
            )
            
        except Exception as e:
            logger.error("Health check failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Health check failed: {str(e)}"
            )
    
    @app.post("/api/command", response_model=CommandResponse, tags=["Commands"])
    async def process_command_endpoint(request: CommandRequest):
        """
        Process natural language commands using MCP tools.
        
        This endpoint provides legacy compatibility for existing IntelliBrowse clients
        while leveraging the enterprise MCP architecture.
        """
        try:
            logger.info("Processing command via REST API", command=request.command[:100])
            
            result = await command_processor.process_command(
                command=request.command,
                history=request.history,
                context=request.context
            )
            
            logger.info("Command processed successfully", success=result.success)
            return result
            
        except Exception as e:
            logger.error("Command endpoint failed", error=str(e), command=request.command)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Command processing failed: {str(e)}"
            )
    
    @app.post("/api/generate-bdd", response_model=BDDResponse, tags=["BDD Generation"])
    async def generate_bdd_endpoint(request: BDDRequest):
        """
        Generate BDD/Gherkin scenarios from natural language descriptions.
        
        This endpoint provides legacy compatibility for BDD generation
        while using the enterprise MCP BDD generator tool.
        """
        try:
            logger.info("Generating BDD via REST API", description=request.description[:100])
            
            # Prepare BDD generation arguments
            bdd_args = {
                "user_story": request.user_story or request.description,
                "acceptance_criteria": request.acceptance_criteria or [],
                "context": {
                    "generation_mode": "rest_api",
                    "validation_required": True
                }
            }
            
            # Call MCP BDD generator tool
            result = await command_processor.mcp_client.call_tool("bdd_generator", bdd_args)
            
            if result.get("success"):
                return BDDResponse(
                    gherkin=result["data"].get("scenario", ""),
                    success=True,
                    validation_passed=result["data"].get("validation_passed", False),
                    suggestions=result["data"].get("suggestions", [])
                )
            else:
                error_msg = result.get("error", {}).get("message", "BDD generation failed")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"BDD generation failed: {error_msg}"
                )
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error("BDD generation endpoint failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"BDD generation failed: {str(e)}"
            )
    
    return app

# Export the app instance
app = create_rest_api() 
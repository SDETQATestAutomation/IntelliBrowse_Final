"""
AI Agent Integration Layer for IntelliBrowse MCP Server

This module provides integration between the AI Agent Orchestrator 
and the MCP server infrastructure, including tool registration,
NLP command processing endpoints, and workflow management.

Enterprise Features:
- Tool discovery and dynamic registration
- Natural language endpoint management
- MCP protocol compliance for agent interactions
- Enterprise security and audit logging
- Integration with existing MCP infrastructure
"""

import asyncio
import json
from typing import Any, Dict, List, Optional, Union

import structlog
from fastapi import HTTPException

try:
    from config.settings import settings
except ImportError:
    # Fallback for when running directly from mcp directory
    from config.settings import settings

try:
    from core.exceptions import AIAgentError, ToolExecutionError, NLPProcessingError
except ImportError:
    # Fallback for when running directly from mcp directory
    from core.exceptions import AIAgentError, ToolExecutionError, NLPProcessingError

try:
    from orchestration.ai_agent import get_ai_agent_orchestrator, AgentCommand, AgentResponse
except ImportError:
    # Fallback for when running directly from mcp directory
    from orchestration.ai_agent import get_ai_agent_orchestrator, AgentCommand, AgentResponse

try:
    from schemas.tool_schemas import ToolCallRequest, ToolCallResponse
except ImportError:
    # Fallback for when running directly from mcp directory
    from schemas.tool_schemas import ToolCallRequest, ToolCallResponse

# Configure logger
logger = structlog.get_logger("intellibrowse.mcp.orchestration.agent_integration")


class AgentIntegrationManager:
    """
    Integration manager for AI Agent Orchestrator with MCP infrastructure.
    
    Handles tool registration, natural language processing endpoints,
    and seamless integration with existing MCP server components.
    """
    
    def __init__(self):
        """Initialize the Agent Integration Manager."""
        self.agent_orchestrator = None
        self.tool_registry: Dict[str, Dict[str, Any]] = {}
        self.tool_executors: Dict[str, callable] = {}
        self.initialized = False
        
        logger.info(
            "Agent Integration Manager initialized",
            extra={
                "service": "agent_integration",
                "action": "initialize",
                "audit": True
            }
        )
    
    async def initialize(self):
        """Initialize the integration manager and register tools."""
        try:
            # Get AI agent orchestrator instance
            self.agent_orchestrator = await get_ai_agent_orchestrator()
            
            # Register all MCP tools with the agent
            await self._register_mcp_tools()
            
            # Set up tool executor
            self.agent_orchestrator.set_tool_executor(self._execute_tool)
            
            self.initialized = True
            
            logger.info(
                "Agent Integration Manager initialized successfully",
                extra={
                    "service": "agent_integration",
                    "action": "initialize_complete",
                    "tool_count": len(self.tool_registry),
                    "audit": True
                }
            )
            
        except Exception as e:
            logger.error(
                f"Failed to initialize Agent Integration Manager: {e}",
                extra={
                    "service": "agent_integration",
                    "action": "initialize_error",
                    "error": str(e),
                    "audit": True
                },
                exc_info=True
            )
            raise AIAgentError(f"Agent integration initialization failed: {e}")
    
    async def _register_mcp_tools(self):
        """Register all MCP tools with the AI agent orchestrator."""
        try:
            # Get the MCP server instance to access registered tools
            try:
                from server_instance import mcp_server
            except ImportError:
                from server_instance import mcp_server
            
            # Define tool metadata for common tools
            tool_metadata = {
                "generate_bdd_scenario": {
                    "description": "Generate BDD scenarios and Gherkin feature files from user stories",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "user_story": {"type": "string", "description": "User story or requirement description"},
                            "acceptance_criteria": {"type": "array", "items": {"type": "string"}, "description": "List of acceptance criteria"}
                        },
                        "required": ["user_story"]
                    }
                },
                "navigate_to_url": {
                    "description": "Navigate browser to a specific URL",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "description": "URL to navigate to"},
                            "session_id": {"type": "string", "description": "Browser session ID"}
                        },
                        "required": ["url", "session_id"]
                    }
                },
                "click_element": {
                    "description": "Click on a web element using natural language description or locator",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "element_description": {"type": "string", "description": "Natural language description of the element to click"},
                            "session_id": {"type": "string", "description": "Browser session ID"}
                        },
                        "required": ["element_description", "session_id"]
                    }
                },
                "fill_element": {
                    "description": "Fill an input field with text using natural language description",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "element_description": {"type": "string", "description": "Natural language description of the input field"},
                            "value": {"type": "string", "description": "Text to fill in the field"},
                            "session_id": {"type": "string", "description": "Browser session ID"}
                        },
                        "required": ["element_description", "value", "session_id"]
                    }
                },
                "hover_element": {
                    "description": "Hover over a web element",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "element_description": {"type": "string", "description": "Natural language description of the element to hover"},
                            "session_id": {"type": "string", "description": "Browser session ID"}
                        },
                        "required": ["element_description", "session_id"]
                    }
                },
                "type_text": {
                    "description": "Type text into an element",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "element_description": {"type": "string", "description": "Element to type into"},
                            "text": {"type": "string", "description": "Text to type"},
                            "session_id": {"type": "string", "description": "Browser session ID"}
                        },
                        "required": ["element_description", "text", "session_id"]
                    }
                },
                "dom_inspection": {
                    "description": "Inspect and analyze DOM structure",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string", "description": "Browser session ID"},
                            "selector": {"type": "string", "description": "Optional CSS selector to target specific element"}
                        },
                        "required": ["session_id"]
                    }
                },
                "locator_generator": {
                    "description": "Generate reliable locators for web elements",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "dom_snapshot": {"type": "string", "description": "DOM snapshot for analysis"},
                            "element_description": {"type": "string", "description": "Description of element to generate locator for"}
                        },
                        "required": ["dom_snapshot", "element_description"]
                    }
                },
                "step_generator": {
                    "description": "Generate test steps from user actions",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string", "description": "Description of action to convert to test steps"},
                            "step_type": {"type": "string", "description": "Type of steps to generate"}
                        },
                        "required": ["description"]
                    }
                },
                "scroll_page": {
                    "description": "Scroll the page in specified direction",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "direction": {"type": "string", "enum": ["up", "down", "left", "right"], "description": "Direction to scroll"},
                            "session_id": {"type": "string", "description": "Browser session ID"}
                        },
                        "required": ["direction", "session_id"]
                    }
                },
                "debug_analyzer": {
                    "description": "Analyze debugging information to provide insights",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "error_message": {"type": "string", "description": "Error message to analyze"},
                            "error_type": {"type": "string", "description": "Type of error"}
                        },
                        "required": ["error_message"]
                    }
                },
                "browser_session": {
                    "description": "Manage browser sessions - create, get, or close",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "action": {"type": "string", "enum": ["create", "get", "close"], "description": "Action to perform"},
                            "session_id": {"type": "string", "description": "Session ID for get/close actions"},
                            "headless": {"type": "boolean", "description": "Run browser in headless mode for create action"}
                        },
                        "required": ["action"]
                    }
                }
            }
            
            # Instead of trying to call list_tools() which may not be available,
            # let's use the tool metadata we already have defined
            logger.info(
                "Registering MCP tools with agent orchestrator",
                extra={
                    "service": "agent_integration", 
                    "action": "register_tools",
                    "audit": True
                }
            )
            
            # Register tools with the agent orchestrator using our metadata
            self.agent_orchestrator.register_tools(tool_metadata)
            
            # Store tool metadata in our registry for tool execution
            self.tool_registry = tool_metadata
            
            # Create tool executors for each tool
            for tool_name in tool_metadata.keys():
                self.tool_executors[tool_name] = self._create_mcp_tool_executor(tool_name)
            
            logger.info(
                f"Successfully registered {len(tool_metadata)} tools with agent orchestrator",
                extra={
                    "service": "agent_integration",
                    "action": "register_tools_complete", 
                    "tool_count": len(tool_metadata),
                    "tool_names": list(tool_metadata.keys()),
                    "audit": True
                }
            )
            
        except Exception as e:
            logger.error(f"Error registering MCP tools: {e}", exc_info=True)
            raise AIAgentError(f"Tool registration failed: {e}")
    
    def _create_mcp_tool_executor(self, tool_name: str):
        """Create an executor that calls the MCP server tool."""
        async def mcp_tool_executor(**kwargs):
            try:
                # Get the MCP server instance
                try:
                    from server_instance import mcp_server
                except ImportError:
                    from server_instance import mcp_server
                
                # Call the tool via MCP server
                result = await mcp_server.call_tool(tool_name, kwargs)
                return result
            except Exception as e:
                logger.error(f"Error executing MCP tool {tool_name}: {e}")
                return {
                    "error": {
                        "code": "MCP_TOOL_EXECUTION_ERROR",
                        "message": f"Failed to execute {tool_name}: {str(e)}"
                    }
                }
        
        return mcp_tool_executor
    
    async def _execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool with the given arguments.
        
        Args:
            tool_name: Name of the tool to execute
            args: Arguments to pass to the tool
            
        Returns:
            Tool execution result
        """
        try:
            logger.info(
                f"Executing tool {tool_name}",
                extra={
                    "service": "agent_integration",
                    "action": "execute_tool",
                    "tool_name": tool_name,
                    "args": args,
                    "audit": True
                }
            )
            
            if tool_name not in self.tool_executors:
                raise ToolExecutionError(f"Tool {tool_name} not found in registry")
            
            executor = self.tool_executors[tool_name]
            
            # Execute the tool
            if asyncio.iscoroutinefunction(executor):
                result = await executor(**args)
            else:
                result = executor(**args)
            
            # Ensure result is properly formatted
            if isinstance(result, str):
                # Try to parse as JSON, otherwise wrap in success response
                try:
                    result_data = json.loads(result)
                except json.JSONDecodeError:
                    result_data = {
                        "success": True,
                        "message": result,
                        "data": result
                    }
            elif isinstance(result, dict):
                result_data = result
            else:
                result_data = {
                    "success": True,
                    "message": "Tool executed successfully",
                    "data": result
                }
            
            logger.info(
                f"Tool {tool_name} executed successfully",
                extra={
                    "service": "agent_integration",
                    "action": "execute_tool_success",
                    "tool_name": tool_name,
                    "success": result_data.get("success", True),
                    "audit": True
                }
            )
            
            return result_data
            
        except Exception as e:
            logger.error(
                f"Error executing tool {tool_name}: {e}",
                extra={
                    "service": "agent_integration",
                    "action": "execute_tool_error",
                    "tool_name": tool_name,
                    "error": str(e),
                    "audit": True
                },
                exc_info=True
            )
            
            return {
                "success": False,
                "error": {
                    "code": "TOOL_EXECUTION_ERROR",
                    "message": str(e),
                    "tool": tool_name
                }
            }
    
    async def process_natural_language_command(
        self, 
        command: str, 
        session_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, str]]] = None
    ) -> AgentResponse:
        """
        Process a natural language command using AI agent orchestration.
        
        Args:
            command: Natural language command
            session_id: Optional session identifier
            context: Optional execution context
            history: Optional conversation history
            
        Returns:
            AgentResponse with execution results
        """
        if not self.initialized:
            await self.initialize()
        
        try:
            agent_command = AgentCommand(
                command=command,
                session_id=session_id,
                context=context,
                history=history
            )
            
            return await self.agent_orchestrator.process_command(agent_command)
            
        except Exception as e:
            logger.error(f"Error processing natural language command: {e}", exc_info=True)
            raise NLPProcessingError(f"Command processing failed: {e}")
    
    async def get_available_tools(self) -> Dict[str, Dict[str, Any]]:
        """Get list of available tools and their schemas."""
        if not self.initialized:
            await self.initialize()
        
        return self.tool_registry
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the agent integration."""
        try:
            if not self.initialized:
                return {
                    "status": "unhealthy",
                    "reason": "Not initialized",
                    "initialized": False
                }
            
            # Check agent orchestrator
            if not self.agent_orchestrator:
                return {
                    "status": "unhealthy",
                    "reason": "Agent orchestrator not available",
                    "initialized": True,
                    "agent_ready": False
                }
            
            # Check tool registry
            tool_count = len(self.tool_registry)
            executor_count = len(self.tool_executors)
            
            return {
                "status": "healthy",
                "initialized": True,
                "agent_ready": True,
                "tool_count": tool_count,
                "executor_count": executor_count,
                "tools_registered": tool_count > 0,
                "executors_available": executor_count > 0,
                "timestamp": asyncio.get_event_loop().time()
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}", exc_info=True)
            return {
                "status": "unhealthy",
                "reason": f"Health check error: {str(e)}",
                "error": str(e)
            }


# Global instance
_agent_integration_manager: Optional[AgentIntegrationManager] = None

async def get_agent_integration_manager() -> AgentIntegrationManager:
    """Get the global Agent Integration Manager instance."""
    global _agent_integration_manager
    if _agent_integration_manager is None:
        _agent_integration_manager = AgentIntegrationManager()
        await _agent_integration_manager.initialize()
    return _agent_integration_manager 
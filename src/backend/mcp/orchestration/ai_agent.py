"""
AI Agent Orchestration Engine for IntelliBrowse MCP Server

This module provides intelligent AI agent orchestration capabilities,
including context-aware tool selection, natural language command processing,
and automated workflow execution with comprehensive error handling.

Enterprise Features:
- Context-aware decision making and tool selection
- Natural language to tool mapping with intent recognition
- Conversation history management and context persistence
- Comprehensive audit logging and error handling
- Configuration-driven security and validation
- Integration with existing MCP infrastructure
"""

import asyncio
import json
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union, Callable

import structlog
from openai import AsyncOpenAI, OpenAIError, AuthenticationError, RateLimitError, APIConnectionError
from pydantic import BaseModel, Field, field_validator, validator

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
    from orchestration.context import SessionManager, WorkflowOrchestrator, ContextManager
except ImportError:
    # Fallback for when running directly from mcp directory
    from orchestration.context import SessionManager, WorkflowOrchestrator, ContextManager

try:
    from schemas.context_schemas import SessionContext, TaskContext
except ImportError:
    # Fallback for when running directly from mcp directory
    from schemas.context_schemas import SessionContext, TaskContext

try:
    from src.backend.mcp.services.vector_store_service import VectorStoreService
except ImportError:
    try:
        from services.vector_store_service import VectorStoreService
    except ImportError:
        # Create a mock VectorStoreService if import fails
        class VectorStoreService:
            @classmethod
            async def get_instance(cls):
                return cls()
            
            async def search_similar_elements(self, *args, **kwargs):
                return []

# Configure logger
logger = structlog.get_logger("intellibrowse.mcp.orchestration.ai_agent")

# Initialize OpenAI client
openai_client = AsyncOpenAI(api_key=settings.openai_api_key)


# Global instance
_ai_agent_orchestrator: Optional['AIAgentOrchestrator'] = None

async def get_ai_agent_orchestrator() -> 'AIAgentOrchestrator':
    """Get the global AI Agent Orchestrator instance."""
    global _ai_agent_orchestrator
    if _ai_agent_orchestrator is None:
        _ai_agent_orchestrator = AIAgentOrchestrator()
        await _ai_agent_orchestrator.initialize()
    return _ai_agent_orchestrator


class AgentCommand(BaseModel):
    """Pydantic model for agent command requests."""
    command: str = Field(..., min_length=1, max_length=10000, description="Natural language command")
    session_id: Optional[str] = Field(None, description="Session identifier for context")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional execution context")
    history: Optional[List[Dict[str, str]]] = Field(None, description="Conversation history")
    
    @field_validator('command')

    
    @classmethod
    def validate_command(cls, v):
        if not v.strip():
            raise ValueError("Command cannot be empty or whitespace only")
        return v.strip()


class AgentResponse(BaseModel):
    """Pydantic model for agent responses."""
    response: str = Field(..., description="AI agent response to the command")
    success: bool = Field(..., description="Whether the command executed successfully")
    session_id: Optional[str] = Field(None, description="Session identifier")
    context: Optional[Dict[str, Any]] = Field(None, description="Updated execution context")
    history: Optional[List[Dict[str, str]]] = Field(None, description="Updated conversation history")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(None, description="Tools that were invoked")
    workflow_id: Optional[str] = Field(None, description="Workflow identifier if workflow was created")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Response metadata")


class ToolSchema(BaseModel):
    """Pydantic model for tool schema definition."""
    type: str = Field(default="function", description="Tool type")
    function: Dict[str, Any] = Field(..., description="Function definition")


class AIAgentOrchestrator:
    """
    Enterprise-grade AI Agent Orchestration Engine.
    
    Provides intelligent command processing, context-aware tool selection,
    and automated workflow execution with comprehensive error handling.
    """
    
    def __init__(self):
        """Initialize the AI Agent Orchestrator."""
        self.session_manager = SessionManager()
        self.context_manager = ContextManager()
        self.workflow_orchestrator = WorkflowOrchestrator(self.session_manager)
        self.vector_store: Optional[VectorStoreService] = None
        self.available_tools: Dict[str, Dict[str, Any]] = {}
        self.tool_executor: Optional[Callable] = None
        
        # Interaction patterns for heuristic parsing
        self.interaction_patterns = {
            "click": r'\b(?:click|tap|press)\s+(?:on\s+)?(.+)',
            "fill": r'\b(?:fill|type|enter)\s+["\']?(.*?)["\']?\s+(?:in|into|for)\s+(.+)',
            "hover": r'\b(?:hover\s+(?:over\s+)?|mouseover\s+)(.+)',
            "select": r'\b(?:select|choose)\s+["\']?(.*?)["\']?\s+(?:from|in)\s+(.+)',
            "navigate": r'\b(?:go\s+to|navigate\s+to|visit|open)\s+(.+)',
            "scroll": r'\b(?:scroll\s+(?:to\s+)?|scroll\s+(?:down|up)\s+(?:to\s+)?)(.+)',
        }
        
        # System prompt template
        self.system_prompt_template = """You are an intelligent web automation assistant capable of controlling browsers and performing complex tasks.

Available Tools:
{tools}

Instructions:
- Use the provided tools to perform actions based on user requests
- Provide clear feedback based on tool execution results
- For element interactions, use natural language descriptions when locators aren't provided
- Maintain context across conversation turns
- Handle errors gracefully and provide helpful suggestions
- Be conversational and helpful in your responses

Context:
- Session ID: {session_id}
- Current URL: {current_url}
- Browser State: {browser_state}
"""
        
        logger.info(
            "AI Agent Orchestrator initialized",
            extra={
                "service": "ai_agent",
                "action": "initialize",
                "openai_model": settings.openai_model,
                "audit": True
            }
        )
    
    async def initialize(self):
        """Initialize dependencies asynchronously."""
        try:
            # Initialize vector store
            self.vector_store = await VectorStoreService.get_instance()
            
            logger.info(
                "AI Agent dependencies initialized successfully",
                extra={
                    "service": "ai_agent",
                    "action": "initialize_dependencies",
                    "vector_store_ready": self.vector_store is not None,
                    "audit": True
                }
            )
        except Exception as e:
            logger.error(
                f"Failed to initialize AI Agent dependencies: {e}",
                extra={
                    "service": "ai_agent",
                    "action": "initialize_error",
                    "error": str(e),
                    "audit": True
                },
                exc_info=True
            )
            raise AIAgentError(f"AI Agent initialization failed: {e}")
    
    def register_tools(self, tools: Dict[str, Dict[str, Any]]):
        """
        Register available tools for the agent.
        
        Args:
            tools: Dictionary mapping tool names to their schemas and metadata
        """
        self.available_tools = tools
        logger.info(
            f"Registered {len(tools)} tools for AI Agent",
            extra={
                "service": "ai_agent",
                "action": "register_tools",
                "tool_count": len(tools),
                "tool_names": list(tools.keys()),
                "audit": True
            }
        )
    
    def set_tool_executor(self, executor: Callable):
        """
        Set the tool executor function.
        
        Args:
            executor: Async function that executes tools
        """
        self.tool_executor = executor
        logger.info(
            "Tool executor set for AI Agent",
            extra={
                "service": "ai_agent",
                "action": "set_tool_executor",
                "audit": True
            }
        )
    
    async def process_command(self, command: AgentCommand) -> AgentResponse:
        """
        Process a natural language command using AI agent orchestration.
        
        Args:
            command: Agent command with natural language input
            
        Returns:
            AgentResponse with execution results
        """
        logger.info(
            f"Processing agent command: {command.command[:100]}...",
            extra={
                "service": "ai_agent",
                "action": "process_command",
                "session_id": command.session_id,
                "command_length": len(command.command),
                "audit": True
            }
        )
        
        try:
            # Ensure dependencies are initialized
            if not self.vector_store:
                await self.initialize()
            
            # Get or create session context
            session_context = await self._get_or_create_session(command.session_id, command.context)
            
            # Try heuristic parsing first for simple commands
            heuristic_result = await self._try_heuristic_processing(command, session_context)
            if heuristic_result:
                return heuristic_result
            
            # Fall back to AI orchestration for complex commands
            return await self._process_with_ai_orchestration(command, session_context)
            
        except Exception as e:
            logger.error(
                f"Error processing agent command: {e}",
                extra={
                    "service": "ai_agent",
                    "action": "process_command_error",
                    "session_id": command.session_id,
                    "error": str(e),
                    "audit": True
                },
                exc_info=True
            )
            
            return AgentResponse(
                response=f"I encountered an error processing your command: {str(e)}",
                success=False,
                session_id=command.session_id,
                context=command.context,
                history=command.history,
                metadata={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
    
    async def _get_or_create_session(self, session_id: Optional[str], context: Optional[Dict[str, Any]]) -> SessionContext:
        """Get existing session or create new one."""
        if session_id:
            session_context = await self.session_manager.get_session(session_id)
            if session_context:
                return session_context
        
        # Create new session
        try:
            from schemas.context_schemas import UserContext
        except ImportError:
            # Fallback for when running directly from mcp directory
            from schemas.context_schemas import UserContext
            
        user_context = UserContext(
            user_id="anonymous",
            username="anonymous",
            permissions=["browse", "automate"],
            metadata=context or {}
        )
        
        return await self.session_manager.create_session(
            user_context=user_context,
            session_metadata=context
        )
    
    async def _try_heuristic_processing(self, command: AgentCommand, session_context: SessionContext) -> Optional[AgentResponse]:
        """
        Try to process command using heuristic patterns for simple actions.
        
        Args:
            command: The command to process
            session_context: Current session context
            
        Returns:
            AgentResponse if heuristic processing succeeded, None otherwise
        """
        command_lower = command.command.lower().strip()
        
        # Skip heuristic if command contains selector-like characters
        if re.search(r'[#/\[\].]', command.command):
            logger.debug("Command contains selector-like characters, skipping heuristic processing")
            return None
        
        # Try to match interaction patterns
        for action, pattern in self.interaction_patterns.items():
            match = re.search(pattern, command_lower, re.IGNORECASE)
            if match:
                logger.info(f"Heuristic match found: {action}")
                return await self._execute_heuristic_action(action, match, command, session_context)
        
        return None
    
    async def _execute_heuristic_action(
        self, 
        action: str, 
        match: re.Match, 
        command: AgentCommand, 
        session_context: SessionContext
    ) -> Optional[AgentResponse]:
        """Execute a heuristic action using vector search for element location."""
        try:
            if action == "click":
                target_description = match.group(1).strip()
                return await self._execute_element_interaction("click_element", target_description, None, command, session_context)
            
            elif action == "fill":
                value = match.group(1).strip()
                target_description = match.group(2).strip()
                return await self._execute_element_interaction("fill_element", target_description, value, command, session_context)
            
            elif action == "hover":
                target_description = match.group(1).strip()
                return await self._execute_element_interaction("hover_element", target_description, None, command, session_context)
            
            elif action == "select":
                value = match.group(1).strip()
                target_description = match.group(2).strip()
                return await self._execute_element_interaction("select_option", target_description, value, command, session_context)
            
            elif action == "navigate":
                url = match.group(1).strip()
                return await self._execute_navigation_action(url, command, session_context)
            
            # Add more action handlers as needed
            
        except Exception as e:
            logger.error(f"Error executing heuristic action {action}: {e}", exc_info=True)
            return None
        
        return None
    
    async def _execute_element_interaction(
        self, 
        tool_name: str, 
        target_description: str, 
        value: Optional[str],
        command: AgentCommand, 
        session_context: SessionContext
    ) -> Optional[AgentResponse]:
        """Execute element interaction using vector search."""
        if not self.tool_executor:
            return None
        
        try:
            # Find element using vector search
            locator_result = await self._find_element_locator(target_description, tool_name, session_context)
            
            if not locator_result:
                logger.warning(f"Could not find locator for: {target_description}")
                return None
            
            # Prepare tool arguments
            tool_args = {"element_description": target_description}
            if value:
                tool_args["value"] = value
            
            # Execute the tool
            result = await self.tool_executor(tool_name, tool_args)
            
            # Parse result
            if isinstance(result, str):
                try:
                    result_data = json.loads(result)
                except json.JSONDecodeError:
                    result_data = {"success": True, "message": result}
            else:
                result_data = result
            
            # Update session context
            await self.session_manager.add_tool_execution(
                session_context.session_id,
                tool_name,
                tool_args,
                result_data
            )
            
            return AgentResponse(
                response=result_data.get("message", f"Successfully executed {tool_name}"),
                success=result_data.get("success", True),
                session_id=session_context.session_id,
                context=command.context,
                history=self._update_history(command.history, command.command, result_data.get("message", "")),
                tool_calls=[{
                    "tool": tool_name,
                    "args": tool_args,
                    "result": result_data
                }],
                metadata={
                    "processing_method": "heuristic",
                    "target_description": target_description,
                    "locator_found": locator_result is not None,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"Error executing element interaction: {e}", exc_info=True)
            return None
    
    async def _execute_navigation_action(
        self, 
        url: str, 
        command: AgentCommand, 
        session_context: SessionContext
    ) -> Optional[AgentResponse]:
        """Execute navigation action."""
        if not self.tool_executor:
            return None
        
        try:
            # Clean and validate URL
            if not url.startswith(('http://', 'https://')):
                if '.' in url:
                    url = f"https://{url}"
                else:
                    return None
            
            tool_args = {"url": url}
            result = await self.tool_executor("navigate_to_url", tool_args)
            
            # Parse result
            if isinstance(result, str):
                try:
                    result_data = json.loads(result)
                except json.JSONDecodeError:
                    result_data = {"success": True, "message": result}
            else:
                result_data = result
            
            # Update session context
            await self.session_manager.add_tool_execution(
                session_context.session_id,
                "navigate_to_url",
                tool_args,
                result_data
            )
            
            return AgentResponse(
                response=result_data.get("message", f"Successfully navigated to {url}"),
                success=result_data.get("success", True),
                session_id=session_context.session_id,
                context=command.context,
                history=self._update_history(command.history, command.command, result_data.get("message", "")),
                tool_calls=[{
                    "tool": "navigate_to_url",
                    "args": tool_args,
                    "result": result_data
                }],
                metadata={
                    "processing_method": "heuristic",
                    "url": url,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"Error executing navigation action: {e}", exc_info=True)
            return None
    
    async def _find_element_locator(
        self, 
        target_description: str, 
        action: str, 
        session_context: SessionContext
    ) -> Optional[Dict[str, Any]]:
        """Find element locator using vector search."""
        try:
            if not self.vector_store:
                return None
            
            # Query vector store for matching elements
            query_results = await self.vector_store.query_elements(
                query_description=target_description,
                n_results=5,
                context={"session_id": session_context.session_id}
            )
            
            if not query_results:
                return None
            
            # Filter results based on action type
            filtered_results = self._filter_results_by_action(query_results, action)
            
            if filtered_results:
                return filtered_results[0]
            elif query_results:
                return query_results[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding element locator: {e}", exc_info=True)
            return None
    
    def _filter_results_by_action(self, results: List[Dict[str, Any]], action: str) -> List[Dict[str, Any]]:
        """Filter vector search results based on action type."""
        if action in ["fill_element", "type_text", "clear_input_field"]:
            # Look for input-like elements
            input_types = {"textbox", "searchbox", "combobox", "input", "textarea"}
            return [
                result for result in results
                if any(
                    result.get("metadata", {}).get(key, "").lower() in input_types
                    for key in ["role", "tag", "type"]
                )
            ]
        elif action in ["click_element", "hover_element"]:
            # Look for clickable elements
            clickable_types = {"button", "link", "checkbox", "radio", "menuitem"}
            return [
                result for result in results
                if any(
                    result.get("metadata", {}).get(key, "").lower() in clickable_types
                    for key in ["role", "tag", "type"]
                )
            ]
        
        return results
    
    async def _process_with_ai_orchestration(self, command: AgentCommand, session_context: SessionContext) -> AgentResponse:
        """Process command using full AI orchestration."""
        try:
            # Prepare tool schemas for LLM
            tool_schemas = self._prepare_tool_schemas()
            
            # Build system prompt with context
            system_prompt = self._build_system_prompt(session_context)
            
            # Prepare message history
            messages = self._prepare_message_history(command.history, system_prompt, command.command)
            
            # Call LLM for tool selection and execution
            response_content, updated_messages = await self._llm_agent_call(
                messages=messages,
                tool_schemas=tool_schemas,
                session_context=session_context
            )
            
            # Update session context
            await self.session_manager.update_session(session_context)
            
            return AgentResponse(
                response=response_content,
                success=True,
                session_id=session_context.session_id,
                context=command.context,
                history=self._extract_conversation_history(updated_messages),
                metadata={
                    "processing_method": "ai_orchestration",
                    "model": settings.openai_model,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"Error in AI orchestration: {e}", exc_info=True)
            raise AIAgentError(f"AI orchestration failed: {e}")
    
    def _prepare_tool_schemas(self) -> List[Dict[str, Any]]:
        """Prepare tool schemas for LLM function calling."""
        schemas = []
        for tool_name, tool_info in self.available_tools.items():
            if "schema" in tool_info:
                schemas.append({
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "description": tool_info.get("description", ""),
                        "parameters": tool_info["schema"]
                    }
                })
        return schemas
    
    def _build_system_prompt(self, session_context: SessionContext) -> str:
        """Build system prompt with current context."""
        tools_description = "\n- ".join([
            f"{name}: {info.get('description', 'No description')}"
            for name, info in self.available_tools.items()
        ])
        
        return self.system_prompt_template.format(
            tools=tools_description,
            session_id=session_context.session_id,
            current_url=session_context.metadata.get("current_url", "Unknown"),
            browser_state=session_context.metadata.get("browser_state", "Unknown")
        )
    
    def _prepare_message_history(
        self, 
        history: Optional[List[Dict[str, str]]], 
        system_prompt: str, 
        user_command: str
    ) -> List[Dict[str, str]]:
        """Prepare message history for LLM."""
        messages = [{"role": "system", "content": system_prompt}]
        
        if history:
            messages.extend(history)
        
        # Add current user command if not already present
        if not messages or messages[-1].get("content") != user_command:
            messages.append({"role": "user", "content": user_command})
        
        return messages
    
    async def _llm_agent_call(
        self, 
        messages: List[Dict[str, str]], 
        tool_schemas: List[Dict[str, Any]],
        session_context: SessionContext
    ) -> Tuple[str, List[Dict[str, str]]]:
        """Execute LLM agent call with tool support."""
        try:
            logger.info("Calling OpenAI LLM for agent orchestration")
            
            response = await openai_client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                tools=tool_schemas if tool_schemas else None,
                tool_choice="auto" if tool_schemas else None,
                max_tokens=settings.openai_max_tokens,
                temperature=settings.openai_temperature
            )
            
            response_message = response.choices[0].message
            tool_calls = response_message.tool_calls
            
            # Add assistant response to messages
            messages.append({
                "role": "assistant",
                "content": response_message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in (tool_calls or [])
                ]
            })
            
            # Execute tool calls if any
            if tool_calls:
                logger.info(f"Executing {len(tool_calls)} tool calls")
                
                for tool_call in tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        arguments = json.loads(tool_call.function.arguments)
                        
                        # Execute tool
                        tool_result = await self.tool_executor(tool_name, arguments)
                        
                        # Add tool result to messages
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_name,
                            "content": str(tool_result)
                        })
                        
                        # Log tool execution for audit
                        await self.session_manager.add_tool_execution(
                            session_context.session_id,
                            tool_name,
                            arguments,
                            tool_result
                        )
                        
                    except Exception as e:
                        logger.error(f"Tool execution error for {tool_name}: {e}", exc_info=True)
                        error_content = json.dumps({
                            "error": {
                                "code": "TOOL_EXECUTION_FAILED",
                                "message": str(e)
                            }
                        })
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_name,
                            "content": error_content
                        })
                
                # Get final response after tool execution
                final_response = await openai_client.chat.completions.create(
                    model=settings.openai_model,
                    messages=messages,
                    max_tokens=settings.openai_max_tokens,
                    temperature=settings.openai_temperature
                )
                
                final_content = final_response.choices[0].message.content
                messages.append({
                    "role": "assistant",
                    "content": final_content
                })
                
                return final_content, messages
            
            return response_message.content or "I understand your request.", messages
            
        except OpenAIError as e:
            logger.error(f"OpenAI API error: {e}", exc_info=True)
            raise AIAgentError(f"AI service error: {e}")
        except Exception as e:
            logger.error(f"Error in LLM agent call: {e}", exc_info=True)
            raise AIAgentError(f"Agent call failed: {e}")
    
    def _update_history(
        self, 
        history: Optional[List[Dict[str, str]]], 
        user_message: str, 
        assistant_message: str
    ) -> List[Dict[str, str]]:
        """Update conversation history."""
        if history is None:
            history = []
        
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": assistant_message})
        
        # Keep only last 20 messages to manage context length
        return history[-20:]
    
    def _extract_conversation_history(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Extract conversation history from LLM messages."""
        conversation = []
        for message in messages:
            if message.get("role") in ["user", "assistant"] and message.get("content"):
                conversation.append({
                    "role": message["role"],
                    "content": message["content"]
                })
        return conversation[-20:]  # Keep last 20 messages


class AIAgent:
    """
    Simplified wrapper for AIAgentOrchestrator to maintain compatibility.
    This class provides a simpler interface for tool execution and command processing.
    """
    
    def __init__(self):
        """Initialize AIAgent with orchestrator."""
        self._orchestrator: Optional[AIAgentOrchestrator] = None
        self._initialized = False
        
    async def _ensure_initialized(self):
        """Ensure the orchestrator is initialized."""
        if not self._initialized:
            self._orchestrator = await get_ai_agent_orchestrator()
            # Register tools from the shared MCP server
            await self._register_mcp_tools()
            self._initialized = True
    
    async def _register_mcp_tools(self):
        """Register tools from the MCP server instance."""
        try:
            # Import the shared server instance with fallback
            try:
                from server_instance import mcp_server
            except ImportError:
                from server_instance import mcp_server
            
            # Extract tool information from the MCP server tool manager
            tools = {}
            if hasattr(mcp_server, '_tool_manager') and hasattr(mcp_server._tool_manager, '_tools'):
                for tool_name, tool_obj in mcp_server._tool_manager._tools.items():
                    # FastMCP Tool objects have different structure
                    tools[tool_name] = {
                        "name": tool_name,
                        "description": getattr(tool_obj, 'description', ''),
                        "function": getattr(tool_obj, 'handler', None),  # FastMCP uses 'handler' not 'func'
                        "schema": getattr(tool_obj, 'inputSchema', {})
                    }
            
            # Also try to get tools from the server module if none found
            if not tools:
                try:
                    from server import get_loaded_tools
                    loaded_tools = get_loaded_tools()
                    for tool_name, tool_obj in loaded_tools.items():
                        tools[tool_name] = {
                            "name": tool_name,
                            "description": getattr(tool_obj, 'description', ''),
                            "function": getattr(tool_obj, 'handler', getattr(tool_obj, 'func', None)),
                            "schema": getattr(tool_obj, 'inputSchema', {})
                        }
                except ImportError:
                    try:
                        from server import get_loaded_tools
                        loaded_tools = get_loaded_tools()
                        for tool_name, tool_obj in loaded_tools.items():
                            tools[tool_name] = {
                                "name": tool_name,
                                "description": getattr(tool_obj, 'description', ''),
                                "function": getattr(tool_obj, 'handler', getattr(tool_obj, 'func', None)),
                                "schema": getattr(tool_obj, 'inputSchema', {})
                            }
                    except ImportError:
                        pass
            
            # Register tools with orchestrator
            self._orchestrator.register_tools(tools)
            
            # Set tool executor
            self._orchestrator.set_tool_executor(self._execute_mcp_tool)
            
            logger.info(f"Registered {len(tools)} tools with AI Agent", tool_count=len(tools))
            
        except Exception as e:
            logger.error(f"Failed to register MCP tools: {e}", error=str(e))
    
    async def _execute_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool via the MCP server."""
        try:
            # Import with fallback paths
            try:
                from server_instance import mcp_server
            except ImportError:
                from server_instance import mcp_server
            
            # Check the tool manager for tools
            if (hasattr(mcp_server, '_tool_manager') and 
                hasattr(mcp_server._tool_manager, '_tools') and 
                tool_name in mcp_server._tool_manager._tools):
                
                tool_obj = mcp_server._tool_manager._tools[tool_name]
                tool_func = getattr(tool_obj, 'handler', getattr(tool_obj, 'func', None))
                
                if tool_func is None:
                    return {"error": f"Tool '{tool_name}' has no executable handler", "success": False}
                    
            else:
                # Try to get tools from server module
                try:
                    from server import get_loaded_tools
                    tools = get_loaded_tools()
                    if tool_name not in tools:
                        return {"error": f"Tool '{tool_name}' not found"}
                    tool_obj = tools[tool_name]
                    tool_func = getattr(tool_obj, 'handler', getattr(tool_obj, 'func', None))
                except ImportError:
                    try:
                        from server import get_loaded_tools
                        tools = get_loaded_tools()
                        if tool_name not in tools:
                            return {"error": f"Tool '{tool_name}' not found"}
                        tool_obj = tools[tool_name]
                        tool_func = getattr(tool_obj, 'handler', getattr(tool_obj, 'func', None))
                    except ImportError:
                        return {"error": f"Tool '{tool_name}' not found"}
            
            if tool_func is None:
                return {"error": f"Tool '{tool_name}' has no executable handler", "success": False}
            
            # Execute the tool function
            if asyncio.iscoroutinefunction(tool_func):
                result = await tool_func(**arguments)
            else:
                result = tool_func(**arguments)
            
            return {"result": result, "success": True}
            
        except Exception as e:
            logger.error(f"Tool execution failed: {tool_name}", error=str(e))
            return {"error": str(e), "success": False}
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a specific tool with given arguments."""
        await self._ensure_initialized()
        return await self._execute_mcp_tool(tool_name, arguments)
    
    async def process_command(self, command: str, session_id: Optional[str] = None, 
                            user_id: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process a natural language command."""
        await self._ensure_initialized()
        
        try:
            # Create AgentCommand
            agent_command = AgentCommand(
                command=command,
                session_id=session_id or f"session_{uuid.uuid4().hex[:8]}",
                context=context or {}
            )
            
            # Process with orchestrator
            response = await self._orchestrator.process_command(agent_command)
            
            return {
                "success": response.success,
                "response": response.response,
                "session_id": response.session_id,
                "tools_executed": response.tool_calls or [],
                "execution_plan": response.metadata.get("execution_plan", [])
            }
            
        except Exception as e:
            logger.error(f"Command processing failed: {command}", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "session_id": session_id
            }


# Global AI agent instance
_ai_agent_instance: Optional[AIAgent] = None

def get_ai_agent() -> AIAgent:
    """Get the global AI agent instance."""
    global _ai_agent_instance
    if _ai_agent_instance is None:
        _ai_agent_instance = AIAgent()
    return _ai_agent_instance 
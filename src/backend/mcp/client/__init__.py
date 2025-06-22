"""
IntelliBrowse MCP Client - SSE Transport Support

Based on OpenAI Agents Python SDK patterns for MCP client implementation.
Provides client-side utilities for connecting to the IntelliBrowse MCP server.
"""

from typing import Any, Dict, List, Optional, Tuple
import asyncio
import json
import logging
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.types import Tool, CallToolResult, InitializeResult
from mcp.shared.message import SessionMessage
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream

logger = logging.getLogger(__name__)


class IntelliBrowseMCPClient:
    """
    MCP Client for connecting to IntelliBrowse MCP Server via SSE transport.
    
    Based on OpenAI Agents Python SDK patterns:
    - SSE client configuration
    - Session management
    - Tool invocation
    - Error handling and cleanup
    """
    
    def __init__(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 5.0,
        sse_read_timeout: float = 300.0,  # 5 minutes
        cache_tools: bool = True,
        name: Optional[str] = None
    ):
        """
        Initialize MCP client for SSE transport.
        
        Args:
            url: Server URL (e.g., "http://127.0.0.1:8001/sse")
            headers: Optional HTTP headers
            timeout: HTTP request timeout
            sse_read_timeout: SSE connection timeout
            cache_tools: Whether to cache tools list
            name: Client name for logging
        """
        self.url = url
        self.headers = headers or {}
        self.timeout = timeout
        self.sse_read_timeout = sse_read_timeout
        self.cache_tools = cache_tools
        self.name = name or f"MCP-Client-{url}"
        
        # Internal state
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.server_info: Optional[InitializeResult] = None
        self._tools_cache: Optional[List[Tool]] = None
        self._cache_dirty = True
        
        logger.info(f"Initialized MCP client for {url}")
        
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
        
    async def connect(self):
        """Connect to the MCP server."""
        try:
            logger.info(f"Connecting to MCP server at {self.url}")
            
            # Create SSE client connection
            transport = await self.exit_stack.enter_async_context(
                sse_client(
                    url=self.url,
                    headers=self.headers,
                    timeout=self.timeout,
                    sse_read_timeout=self.sse_read_timeout
                )
            )
            
            # Extract read and write streams
            read_stream, write_stream = transport
            
            # Create client session
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            
            # Initialize server connection
            self.server_info = await self.session.initialize()
            
            logger.info(f"Connected to MCP server: {self.server_info.serverInfo.name}")
            logger.debug(f"Server capabilities: {self.server_info.capabilities}")
            
        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            await self.disconnect()
            raise
            
    async def disconnect(self):
        """Disconnect from the MCP server."""
        try:
            logger.info("Disconnecting from MCP server")
            await self.exit_stack.aclose()
            self.session = None
            self.server_info = None
            self._tools_cache = None
            self._cache_dirty = True
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
            
    async def list_tools(self) -> List[Tool]:
        """
        List available tools from the server.
        Uses caching to avoid repeated requests if enabled.
        """
        if not self.session:
            raise RuntimeError("Client not connected. Call connect() first.")
            
        # Return cached tools if available and not dirty
        if self.cache_tools and not self._cache_dirty and self._tools_cache:
            logger.debug(f"Returning {len(self._tools_cache)} cached tools")
            return self._tools_cache
            
        try:
            logger.debug("Fetching tools from server")
            tools_response = await self.session.list_tools()
            self._tools_cache = tools_response.tools
            self._cache_dirty = False
            
            logger.info(f"Retrieved {len(self._tools_cache)} tools from server")
            return self._tools_cache
            
        except Exception as e:
            logger.error(f"Failed to list tools: {e}")
            raise
            
    async def call_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> CallToolResult:
        """
        Call a tool on the server.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments as dictionary
            
        Returns:
            Tool execution result
        """
        if not self.session:
            raise RuntimeError("Client not connected. Call connect() first.")
            
        try:
            logger.debug(f"Calling tool: {tool_name}", extra={"arguments": arguments})
            result = await self.session.call_tool(tool_name, arguments)
            logger.debug(f"Tool {tool_name} completed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Tool {tool_name} failed: {e}")
            raise
            
    def invalidate_tools_cache(self):
        """Invalidate the tools cache to force refresh on next list_tools call."""
        self._cache_dirty = True
        logger.debug("Tools cache invalidated")
        
    async def ping(self) -> bool:
        """
        Ping the server to check connectivity.
        
        Returns:
            True if server is responsive, False otherwise
        """
        try:
            await self.list_tools()
            return True
        except Exception as e:
            logger.warning(f"Server ping failed: {e}")
            return False


class IntelliBrowseMCPTestClient:
    """
    Test client for IntelliBrowse MCP server testing and validation.
    Includes test utilities and example tool calls.
    """
    
    def __init__(self, base_url: str = "http://127.0.0.1:8001"):
        self.base_url = base_url
        self.sse_url = f"{base_url}/sse"
        
    async def run_basic_tests(self):
        """Run basic connectivity and tool tests."""
        logger.info("Starting basic MCP client tests")
        
        async with IntelliBrowseMCPClient(self.sse_url) as client:
            # Test 1: List tools
            logger.info("Test 1: Listing tools")
            tools = await client.list_tools()
            logger.info(f"Found {len(tools)} tools: {[t.name for t in tools]}")
            
            # Test 2: Test a simple tool if available
            if tools:
                tool = tools[0]
                logger.info(f"Test 2: Testing tool {tool.name}")
                try:
                    # Call with minimal arguments
                    result = await client.call_tool(tool.name, {})
                    logger.info(f"Tool {tool.name} result: {result}")
                except Exception as e:
                    logger.warning(f"Tool {tool.name} test failed (expected): {e}")
                    
            # Test 3: Server ping
            logger.info("Test 3: Server ping")
            is_alive = await client.ping()
            logger.info(f"Server ping result: {is_alive}")
            
        logger.info("Basic MCP client tests completed")
        
    async def run_tool_examples(self):
        """Run example tool calls for IntelliBrowse tools."""
        logger.info("Running IntelliBrowse tool examples")
        
        async with IntelliBrowseMCPClient(self.sse_url) as client:
            tools = await client.list_tools()
            tool_names = {t.name for t in tools}
            
            # Example: BDD Generator
            if "bdd_generator" in tool_names:
                logger.info("Testing BDD Generator")
                try:
                    result = await client.call_tool("bdd_generator", {
                        "user_story": "As a user, I want to login to the system",
                        "acceptance_criteria": ["Valid credentials allow login", "Invalid credentials show error"]
                    })
                    logger.info(f"BDD Generator result: {result}")
                except Exception as e:
                    logger.error(f"BDD Generator test failed: {e}")
                    
            # Example: Locator Generator  
            if "locator_generator" in tool_names:
                logger.info("Testing Locator Generator")
                try:
                    result = await client.call_tool("locator_generator", {
                        "dom_content": "<button id='submit'>Submit</button>",
                        "element_description": "submit button"
                    })
                    logger.info(f"Locator Generator result: {result}")
                except Exception as e:
                    logger.error(f"Locator Generator test failed: {e}")
                    
        logger.info("Tool examples completed")


# Convenience functions
async def create_sse_client(
    host: str = "127.0.0.1",
    port: int = 8001,
    **kwargs
) -> IntelliBrowseMCPClient:
    """Create and connect an SSE client."""
    url = f"http://{host}:{port}/sse"
    client = IntelliBrowseMCPClient(url, **kwargs)
    await client.connect()
    return client


async def test_server_connection(host: str = "127.0.0.1", port: int = 8001) -> bool:
    """Test if the MCP server is reachable."""
    try:
        async with create_sse_client(host, port) as client:
            return await client.ping()
    except Exception:
        return False


if __name__ == "__main__":
    # Run basic tests
    async def main():
        test_client = IntelliBrowseMCPTestClient()
        await test_client.run_basic_tests()
        await test_client.run_tool_examples()
        
    asyncio.run(main()) 
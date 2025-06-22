"""
IntelliBrowse MCP Server Instance

This module provides the shared FastMCP server instance used across
all MCP modules for tool, prompt, and resource registration.
"""

import structlog
from mcp.server.fastmcp import FastMCP

# Configure logging
logger = structlog.get_logger("intellibrowse.mcp.server_instance")

# Create the shared FastMCP server instance
mcp_server = FastMCP("IntelliBrowse MCP Server")

logger.info("FastMCP server instance created", server_name="IntelliBrowse MCP Server") 
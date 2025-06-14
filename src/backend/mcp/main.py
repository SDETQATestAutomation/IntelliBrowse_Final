"""
IntelliBrowse MCP Server - Main Entry Point

This is the exclusive AI orchestration layer for IntelliBrowse using the Model Context Protocol.
All AI/LLM functionality is centralized here, with no AI code elsewhere in the backend.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add the project root to Python path for imports
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from mcp.server.fastmcp import FastMCP
from mcp.server import Server
from mcp.types import Tool, Prompt, Resource
import structlog

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger("intellibrowse.mcp.server")

def setup_logging():
    """Set up structured logging and return logger."""
    return logger

def create_mcp_server():
    """Create and return MCP server instance."""
    return mcp_server

# Initialize FastMCP server
mcp_server = FastMCP(name="IntelliBrowseMCP")

# Note: FastMCP automatically handles tool/prompt/resource listing
# Individual tools, prompts, and resources register themselves via decorators

def import_primitives():
    """
    Dynamically import all primitive modules to register tools, prompts, and resources.
    This function imports modules from tools/, prompts/, and resources/ directories.
    """
    import importlib
    import pkgutil
    from pathlib import Path
    
    mcp_root = Path(__file__).parent
    
    # Import all modules from each primitive directory
    for primitive_type in ['tools', 'prompts', 'resources']:
        primitive_path = mcp_root / primitive_type
        
        if primitive_path.exists():
            logger.info(f"Loading {primitive_type} from {primitive_path}")
            
            # Add the primitive path to sys.path temporarily
            sys.path.insert(0, str(primitive_path))
            
            try:
                # Import all Python modules in the directory
                for _, module_name, _ in pkgutil.iter_modules([str(primitive_path)]):
                    if not module_name.startswith('_'):  # Skip private modules
                        module_path = f"src.backend.mcp.{primitive_type}.{module_name}"
                        try:
                            logger.info(f"Importing {module_path}")
                            importlib.import_module(module_path)
                        except Exception as e:
                            logger.error(f"Failed to import {module_path}: {e}")
            finally:
                # Remove the path from sys.path
                sys.path.remove(str(primitive_path))

async def main():
    """Main server startup function."""
    logger.info("Starting IntelliBrowse MCP Server")
    
    # Load environment configuration
    from dotenv import load_dotenv
    load_dotenv()
    
    # Import all primitive modules to register them
    try:
        import_primitives()
        logger.info("Successfully loaded all primitives")
    except Exception as e:
        logger.error(f"Error loading primitives: {e}")
        raise
    
    # Get server configuration
    host = os.getenv("MCP_HOST", "127.0.0.1")
    port = int(os.getenv("MCP_PORT", "8001"))
    
    logger.info(f"MCP Server starting on {host}:{port}")
    
    # Run the server
    await mcp_server.run(host=host, port=port, transport="sse")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1) 
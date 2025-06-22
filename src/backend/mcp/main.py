"""
IntelliBrowse MCP Server - Bootstrapping Entrypoint

This is the exclusive AI orchestration layer for IntelliBrowse using the Model Context Protocol.
All AI/LLM functionality is centralized here, with no AI code elsewhere in the backend.
"""

import os
import logging
import anyio
import structlog
from dotenv import load_dotenv
import traceback
import signal
import sys
from pathlib import Path

# Import the server instance and load primitives
try:
    from server import get_server
except ImportError:
    # Fallback for when running directly from mcp directory
    from server import get_server
try:
    from config.settings import MCPSettings
except ImportError:
    # Fallback for when running directly from mcp directory
    from config.settings import MCPSettings

# Create app instance for external imports
server = get_server()
app = server  # Export for external imports

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

logger = structlog.get_logger("intellibrowse.mcp.main")


def main():
    """
    Main server startup function with robust error handling and lifecycle management.
    Uses FastMCP synchronous API for simple stdio transport.
    """
    settings = None
    server = None
    
    try:
        # Load environment configuration from .env.example or .env
        env_path = Path(__file__).parent.parent.parent.parent / ".env.example"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
            logger.info("Loaded configuration from .env.example")
        else:
            env_fallback = Path(__file__).parent.parent.parent.parent / ".env"
            if env_fallback.exists():
                load_dotenv(dotenv_path=env_fallback)
                logger.info("Loaded configuration from .env")
            else:
                logger.warning("No .env.example or .env file found, using environment variables")
        
        # Initialize settings
        settings = MCPSettings()
        
        # Log server startup parameters
        logger.info(
            "Starting IntelliBrowse MCP Server",
            transport=settings.mcp_transport,
            enabled_tools=settings.get_enabled_tools_list()
        )
        
        # Get the FastMCP server instance
        server = get_server()
        
        # Register signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown")
            raise KeyboardInterrupt
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Run server with correct FastMCP API
        # FastMCP.run() only accepts transport and mount_path parameters
        logger.info("Starting FastMCP server with stdio transport")
        server.run(transport="stdio")
        
    except KeyboardInterrupt:
        logger.info("Server shutdown requested by user (Ctrl+C)")
    except Exception as e:
        logger.error(
            "Server startup failed",
            error=str(e),
            traceback=traceback.format_exc()
        )
        sys.exit(1)
    finally:
        # Graceful cleanup
        if server:
            logger.info("Cleaning up server resources")
            # Any additional cleanup logic would go here
        
        logger.info("Server shutdown complete")


if __name__ == "__main__":
    try:
        # FastMCP.run() manages its own event loop, so call main() directly
        main()
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Fatal server error: {e}")
        sys.exit(1) 
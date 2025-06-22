"""
IntelliBrowse MCP Server Instance

This file contains the FastMCP server instance and handles dynamic registration
of all MCP primitives (tools, prompts, resources) from their respective modules.
"""

import importlib
import importlib.util
import pkgutil
import structlog
from pathlib import Path
from typing import Dict, Any

# Import the shared server instance
try:
    from server_instance import mcp_server
except ImportError:
    # Fallback for when running directly from mcp directory
    from server_instance import mcp_server

# Configure logger
logger = structlog.get_logger("intellibrowse.mcp.server")

# Global tracking of loaded primitives
_loaded_tools = {}
_loaded_prompts = {}
_loaded_resources = {}

def _load_primitives():
    """
    Dynamically import and register all tool, prompt, and resource modules.
    Uses modular imports from tools/, prompts/, resources/ directories.
    """
    global _loaded_tools, _loaded_prompts, _loaded_resources
    
    mcp_root = Path(__file__).parent
    
    # Load primitives in order: tools, prompts, resources
    primitive_types = ["tools", "prompts", "resources"]
    
    for primitive_type in primitive_types:
        primitive_path = mcp_root / primitive_type
        
        if primitive_path.exists():
            logger.info(f"Loading {primitive_type} from {primitive_path}")
            
            # Track loaded modules
            loaded_modules = []
            failed_modules = []
            
            try:
                # Add the mcp directory to Python path to resolve imports
                import sys
                if str(mcp_root) not in sys.path:
                    sys.path.insert(0, str(mcp_root))
                    
                # Import all Python modules in the directory
                for _, module_name, _ in pkgutil.iter_modules([str(primitive_path)]):
                    if not module_name.startswith('_'):  # Skip private modules
                        try:
                            logger.debug(f"Importing {primitive_type}.{module_name}")
                            # Import using relative path from mcp directory
                            spec = importlib.util.spec_from_file_location(
                                f"{primitive_type}.{module_name}",
                                primitive_path / f"{module_name}.py"
                            )
                            module = importlib.util.module_from_spec(spec)
                            
                            # Make the mcp_server available to the module
                            module.mcp_server = mcp_server
                            
                            # Execute the module
                            spec.loader.exec_module(module)
                            loaded_modules.append(module_name)
                            
                            # Track tools in our global registry
                            if primitive_type == "tools":
                                # Force update tracking after module load
                                if hasattr(mcp_server, '_tool_manager') and hasattr(mcp_server._tool_manager, '_tools'):
                                    for tool_name in mcp_server._tool_manager._tools.keys():
                                        _loaded_tools[tool_name] = mcp_server._tool_manager._tools[tool_name]
                            
                            # Track prompts in our global registry  
                            if primitive_type == "prompts":
                                # Force update tracking after module load
                                if hasattr(mcp_server, '_prompt_manager') and hasattr(mcp_server._prompt_manager, '_prompts'):
                                    for prompt_name in mcp_server._prompt_manager._prompts.keys():
                                        _loaded_prompts[prompt_name] = mcp_server._prompt_manager._prompts[prompt_name]
                            
                            # Track resources in our global registry
                            if primitive_type == "resources":
                                # Force update tracking after module load
                                if hasattr(mcp_server, '_resource_manager') and hasattr(mcp_server._resource_manager, '_resources'):
                                    for resource_name in mcp_server._resource_manager._resources.keys():
                                        _loaded_resources[resource_name] = mcp_server._resource_manager._resources[resource_name]
                                        
                        except Exception as e:
                            logger.error(f"Failed to import {primitive_type}.{module_name}: {e}")
                            failed_modules.append((module_name, str(e)))
                            
                logger.info(
                    f"Loaded {primitive_type}",
                    loaded_count=len(loaded_modules),
                    failed_count=len(failed_modules),
                    loaded_modules=loaded_modules
                )
                                
                if failed_modules:
                    logger.warning(
                        f"Some {primitive_type} failed to load",
                        failed_modules=failed_modules
                    )
                    
            except Exception as e:
                logger.error(f"Critical error loading {primitive_type}: {e}")
                raise
        else:
            logger.warning(f"Primitive directory not found: {primitive_path}")

# Load all primitives when module is imported
try:
    _load_primitives()
    # Final sync to ensure tracking is accurate - get tools from tool manager
    if hasattr(mcp_server, '_tool_manager') and hasattr(mcp_server._tool_manager, '_tools'):
        _loaded_tools.update(mcp_server._tool_manager._tools)
        logger.info(f"Final tool sync: {len(_loaded_tools)} tools tracked from tool manager")
    if hasattr(mcp_server, '_prompt_manager') and hasattr(mcp_server._prompt_manager, '_prompts'):
        _loaded_prompts.update(mcp_server._prompt_manager._prompts)
        logger.info(f"Final prompt sync: {len(_loaded_prompts)} prompts tracked from prompt manager")
    if hasattr(mcp_server, '_resource_manager') and hasattr(mcp_server._resource_manager, '_resources'):
        _loaded_resources.update(mcp_server._resource_manager._resources)
        logger.info(f"Final resource sync: {len(_loaded_resources)} resources tracked from resource manager")
    logger.info("All MCP primitives loaded successfully")
except Exception as e:
    logger.error(f"Failed to load MCP primitives: {e}")
    raise

def get_server():
    """
    Get the FastMCP server instance with all primitives registered.
    
    Returns:
        FastMCP: The configured server instance
    """
    # Ensure our tracking is updated with latest from server managers
    global _loaded_tools, _loaded_prompts, _loaded_resources
    if hasattr(mcp_server, '_tool_manager') and hasattr(mcp_server._tool_manager, '_tools'):
        _loaded_tools.update(mcp_server._tool_manager._tools)
    if hasattr(mcp_server, '_prompt_manager') and hasattr(mcp_server._prompt_manager, '_prompts'):
        _loaded_prompts.update(mcp_server._prompt_manager._prompts)
    if hasattr(mcp_server, '_resource_manager') and hasattr(mcp_server._resource_manager, '_resources'):
        _loaded_resources.update(mcp_server._resource_manager._resources)
        
    return mcp_server

def get_loaded_tool_count() -> int:
    """Get the number of loaded tools."""
    # Ensure latest sync before returning count
    global _loaded_tools
    if hasattr(mcp_server, '_tool_manager') and hasattr(mcp_server._tool_manager, '_tools'):
        _loaded_tools.update(mcp_server._tool_manager._tools)
    return len(_loaded_tools)

def get_loaded_prompt_count() -> int:
    """Get the number of loaded prompts."""
    # Ensure latest sync before returning count
    global _loaded_prompts
    if hasattr(mcp_server, '_prompt_manager') and hasattr(mcp_server._prompt_manager, '_prompts'):
        _loaded_prompts.update(mcp_server._prompt_manager._prompts)
    return len(_loaded_prompts)

def get_loaded_resource_count() -> int:
    """Get the number of loaded resources."""
    # Ensure latest sync before returning count
    global _loaded_resources
    if hasattr(mcp_server, '_resource_manager') and hasattr(mcp_server._resource_manager, '_resources'):
        _loaded_resources.update(mcp_server._resource_manager._resources)
    return len(_loaded_resources)

def get_loaded_tools() -> Dict[str, Any]:
    """Get the loaded tools registry."""
    # Ensure latest sync before returning tools
    global _loaded_tools
    if hasattr(mcp_server, '_tool_manager') and hasattr(mcp_server._tool_manager, '_tools'):
        _loaded_tools.update(mcp_server._tool_manager._tools)
    return _loaded_tools.copy()

def get_loaded_prompts() -> Dict[str, Any]:
    """Get the loaded prompts registry."""
    # Ensure latest sync before returning prompts
    global _loaded_prompts
    if hasattr(mcp_server, '_prompt_manager') and hasattr(mcp_server._prompt_manager, '_prompts'):
        _loaded_prompts.update(mcp_server._prompt_manager._prompts)
    return _loaded_prompts.copy()

def get_loaded_resources() -> Dict[str, Any]:
    """Get the loaded resources registry."""
    # Ensure latest sync before returning resources
    global _loaded_resources
    if hasattr(mcp_server, '_resource_manager') and hasattr(mcp_server._resource_manager, '_resources'):
        _loaded_resources.update(mcp_server._resource_manager._resources)
    return _loaded_resources.copy() 
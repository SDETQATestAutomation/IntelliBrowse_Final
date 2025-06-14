"""
IntelliBrowse MCP Server - Resources Module

This module contains application-controlled resource providers that expose
context and data for LLMs. Resources provide GET-style access to application
state, test execution context, DOM snapshots, and other contextual information.
"""

from .dom_resource import DOMResourceProvider
from .execution_context_resource import ExecutionContextResourceProvider
from .test_data_resource import TestDataResourceProvider
from .session_artifact_resource import SessionArtifactResourceProvider
from .schema_resource import SchemaResourceProvider
from . import get_input_field_value
from . import get_last_pressed_key
from . import get_last_released_key
from . import get_last_scroll_position
from . import get_hovered_state

__all__ = [
    "DOMResourceProvider",
    "ExecutionContextResourceProvider", 
    "TestDataResourceProvider",
    "SessionArtifactResourceProvider",
    "SchemaResourceProvider",
    "get_input_field_value",
    "get_last_pressed_key",
    "get_last_released_key",
    "get_last_scroll_position",
    "get_hovered_state",
] 
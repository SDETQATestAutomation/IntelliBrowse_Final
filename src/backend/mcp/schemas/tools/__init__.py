"""
Tool-specific Pydantic schemas for MCP tools.

Each tool has its own schema file following the naming convention:
{tool_name}_schemas.py

This modular approach ensures Single Responsibility Principle (SRP)
and maintainable schema management per IntelliBrowse MCP standards.
"""

# Import all tool schemas for easy access
from .bdd_generator_schemas import BDDGeneratorRequest, BDDGeneratorResponse
from .locator_generator_schemas import LocatorGeneratorRequest, LocatorGeneratorResponse
from .step_generator_schemas import StepGeneratorRequest, StepGeneratorResponse
from .selector_healer_schemas import SelectorHealerRequest, SelectorHealerResponse
from .debug_analyzer_schemas import DebugAnalyzerRequest, DebugAnalyzerResponse
from .open_browser_schemas import OpenBrowserRequest, OpenBrowserResponse
from .close_browser_schemas import CloseBrowserRequest, CloseBrowserResponse
from .navigate_to_url_schemas import NavigateToUrlRequest, NavigateToUrlResponse
from .get_page_dom_schemas import GetPageDomRequest, GetPageDomResponse
from .click_element_schemas import ClickElementRequest, ClickElementResponse
from .fill_element_schemas import FillElementRequest, FillElementResponse
from .type_text_schemas import TypeTextRequest, TypeTextResponse
from .clear_input_field_schemas import ClearInputFieldRequest, ClearInputFieldResponse
from .press_key_schemas import PressKeyRequest, PressKeyResponse
from .release_key_schemas import ReleaseKeyRequest, ReleaseKeyResponse
from .scroll_page_schemas import ScrollPageRequest, ScrollPageResponse
from .hover_element_schemas import HoverElementRequest, HoverElementResponse
from .legacy_schemas import (
    StepRequest, StepResponse,
    SelectorRequest, SelectorResponse,
    DebugRequest, DebugResponse
)

__all__ = [
    # BDD Generator
    "BDDGeneratorRequest", "BDDGeneratorResponse",
    # Locator Generator
    "LocatorGeneratorRequest", "LocatorGeneratorResponse",
    # Step Generator
    "StepGeneratorRequest", "StepGeneratorResponse",
    # Selector Healer
    "SelectorHealerRequest", "SelectorHealerResponse",
    # Debug Analyzer
    "DebugAnalyzerRequest", "DebugAnalyzerResponse",
    # Browser Session Management
    "OpenBrowserRequest", "OpenBrowserResponse",
    "CloseBrowserRequest", "CloseBrowserResponse",
    # Navigation
    "NavigateToUrlRequest", "NavigateToUrlResponse",
    # DOM Inspection
    "GetPageDomRequest", "GetPageDomResponse",
    # Element Interaction
    "ClickElementRequest", "ClickElementResponse",
    "FillElementRequest", "FillElementResponse",
    "TypeTextRequest", "TypeTextResponse",
    "ClearInputFieldRequest", "ClearInputFieldResponse",
    "HoverElementRequest", "HoverElementResponse",
    # Keyboard Actions
    "PressKeyRequest", "PressKeyResponse",
    "ReleaseKeyRequest", "ReleaseKeyResponse",
    # Page Actions
    "ScrollPageRequest", "ScrollPageResponse",
    # Legacy Schemas
    "StepRequest", "StepResponse",
    "SelectorRequest", "SelectorResponse",
    "DebugRequest", "DebugResponse"
] 
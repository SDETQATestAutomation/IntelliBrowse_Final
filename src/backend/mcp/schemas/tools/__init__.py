"""
Tool schemas package - Per-tool modular schema organization.

Each tool's schemas are organized in separate files for maintainability
and following Single Responsibility Principle.
"""

# Import all tool schemas for backward compatibility
from .bdd_generator_schemas import BDDGeneratorRequest, BDDGeneratorResponse
from .locator_generator_schemas import LocatorGeneratorRequest, LocatorGeneratorResponse
from .step_generator_schemas import StepGeneratorRequest, StepGeneratorResponse
from .selector_healer_schemas import SelectorHealerRequest, SelectorHealerResponse
from .debug_analyzer_schemas import DebugAnalyzerRequest, DebugAnalyzerResponse

# Legacy schemas (to be deprecated)
from .legacy_schemas import (
    StepRequest, StepResponse,
    SelectorRequest, SelectorResponse,
    DebugRequest, DebugResponse
)

# Browser automation schemas
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

__all__ = [
    # AI Tool schemas
    "BDDGeneratorRequest", "BDDGeneratorResponse",
    "LocatorGeneratorRequest", "LocatorGeneratorResponse",
    "StepGeneratorRequest", "StepGeneratorResponse",
    "SelectorHealerRequest", "SelectorHealerResponse",
    "DebugAnalyzerRequest", "DebugAnalyzerResponse",
    
    # Legacy schemas (deprecated)
    "StepRequest", "StepResponse",
    "SelectorRequest", "SelectorResponse",
    "DebugRequest", "DebugResponse",
    
    # Browser automation schemas
    "OpenBrowserRequest", "OpenBrowserResponse",
    "CloseBrowserRequest", "CloseBrowserResponse",
    "NavigateToUrlRequest", "NavigateToUrlResponse",
    "GetPageDomRequest", "GetPageDomResponse",
    "ClickElementRequest", "ClickElementResponse",
    "FillElementRequest", "FillElementResponse",
    "TypeTextRequest", "TypeTextResponse",
    "ClearInputFieldRequest", "ClearInputFieldResponse",
    "PressKeyRequest", "PressKeyResponse",
    "ReleaseKeyRequest", "ReleaseKeyResponse",
    "ScrollPageRequest", "ScrollPageResponse",
    "HoverElementRequest", "HoverElementResponse",
] 
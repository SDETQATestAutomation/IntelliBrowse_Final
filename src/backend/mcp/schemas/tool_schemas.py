"""
DEPRECATED: Tool Schemas Compatibility Layer

⚠️  DEPRECATION NOTICE ⚠️
This file has been refactored into modular, per-tool schema files.
While this compatibility layer ensures backward compatibility, please migrate to the new structure:

NEW MODULAR STRUCTURE:
├── schemas/tools/
│   ├── __init__.py                      # Centralized imports (RECOMMENDED)
│   ├── bdd_generator_schemas.py         # BDD scenario generation schemas
│   ├── locator_generator_schemas.py     # Element locator generation schemas
│   ├── step_generator_schemas.py        # Test step generation schemas
│   ├── selector_healer_schemas.py       # Selector healing schemas
│   ├── debug_analyzer_schemas.py        # Debug analysis schemas
│   ├── legacy_schemas.py                # Legacy/deprecated schemas
│   ├── open_browser_schemas.py          # Browser session initialization schemas
│   ├── close_browser_schemas.py         # Browser session termination schemas
│   ├── navigate_to_url_schemas.py       # URL navigation schemas
│   ├── get_page_dom_schemas.py          # DOM extraction schemas
│   ├── click_element_schemas.py         # Element clicking schemas
│   ├── fill_element_schemas.py          # Form field filling schemas
│   ├── type_text_schemas.py             # Text input typing schemas
│   ├── clear_input_field_schemas.py     # Input clearing schemas
│   ├── press_key_schemas.py             # Key press event schemas
│   ├── release_key_schemas.py           # Key release event schemas
│   ├── scroll_page_schemas.py           # Page scrolling schemas
│   └── hover_element_schemas.py         # Element hovering schemas

MIGRATION EXAMPLES:

OLD (Deprecated):
    from schemas.tool_schemas import BDDGeneratorRequest, LocatorGeneratorRequest

NEW (Recommended):
    from schemas.tools import BDDGeneratorRequest, LocatorGeneratorRequest
    
OR (Specific):
    from schemas.tools.bdd_generator_schemas import BDDGeneratorRequest
    from schemas.tools.locator_generator_schemas import LocatorGeneratorRequest

BENEFITS OF NEW STRUCTURE:
- Single Responsibility Principle (SRP) compliance
- Enhanced maintainability and code navigation
- Easier testing and validation per tool
- Better IDE support with targeted imports
- Future-ready for plugin/extension systems
- Clear documentation per schema category

This compatibility layer will be removed in a future version.
"""

import warnings
from typing import TYPE_CHECKING

# Issue deprecation warning for direct imports from this file
warnings.warn(
    "Direct imports from 'tool_schemas.py' are deprecated. "
    "Please use 'from schemas.tools import ...' instead. "
    "See file documentation for migration guide.",
    DeprecationWarning,
    stacklevel=2
)

# Import all schemas from the new modular structure for backward compatibility
if TYPE_CHECKING:
    # Type hints for IDEs without runtime overhead
    from .tools import *
else:
    # Runtime imports with explicit re-exports
    from .tools.bdd_generator_schemas import BDDGeneratorRequest, BDDGeneratorResponse
    from .tools.locator_generator_schemas import LocatorGeneratorRequest, LocatorGeneratorResponse
    from .tools.step_generator_schemas import StepGeneratorRequest, StepGeneratorResponse
    from .tools.selector_healer_schemas import SelectorHealerRequest, SelectorHealerResponse
    from .tools.debug_analyzer_schemas import DebugAnalyzerRequest, DebugAnalyzerResponse
    
    # Legacy schemas for backward compatibility
    from .tools.legacy_schemas import (
        StepRequest, StepResponse,
        SelectorRequest, SelectorResponse,
        DebugRequest, DebugResponse
    )
    
    # Browser automation schemas
    from .tools.open_browser_schemas import OpenBrowserRequest, OpenBrowserResponse
    from .tools.close_browser_schemas import CloseBrowserRequest, CloseBrowserResponse
    from .tools.navigate_to_url_schemas import NavigateToUrlRequest, NavigateToUrlResponse
    from .tools.get_page_dom_schemas import GetPageDomRequest, GetPageDomResponse
    from .tools.click_element_schemas import ClickElementRequest, ClickElementResponse
    from .tools.fill_element_schemas import FillElementRequest, FillElementResponse
    from .tools.type_text_schemas import TypeTextRequest, TypeTextResponse
    from .tools.clear_input_field_schemas import ClearInputFieldRequest, ClearInputFieldResponse
    from .tools.press_key_schemas import PressKeyRequest, PressKeyResponse
    from .tools.release_key_schemas import ReleaseKeyRequest, ReleaseKeyResponse
    from .tools.scroll_page_schemas import ScrollPageRequest, ScrollPageResponse
    from .tools.hover_element_schemas import HoverElementRequest, HoverElementResponse

    # Legacy aliases for old schema names (backward compatibility)
    BDDRequest = BDDGeneratorRequest
    BDDResponse = BDDGeneratorResponse
    LocatorRequest = LocatorGeneratorRequest
    LocatorResponse = LocatorGeneratorResponse

# Explicit exports for backward compatibility
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
    
    # Legacy aliases for old schema names
    "BDDRequest", "BDDResponse",
    "LocatorRequest", "LocatorResponse",
    
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
"""
Hover Element Prompt for IntelliBrowse MCP Server.

This module provides prompt templates for guiding LLM operations related to
mouse hover actions on DOM elements, supporting hover-dependent UI behaviors,
menu interactions, tooltip testing, and comprehensive hover state validation.
"""

import sys
from pathlib import Path

# Add parent directory to path for MCP server import
sys.path.append(str(Path(__file__).parent.parent))
try:
    from server_instance import mcp_server
except ImportError:
    # Fallback for when running directly from mcp directory
    from server_instance import mcp_server


@mcp_server.prompt()
def hover_element_prompt(selector: str, hover_type: str = "standard", context: str = "") -> str:
    """
    Returns a prompt guiding the LLM to hover over the specified element.
    
    This prompt template helps users understand how to perform hover operations
    and provides context for hover-dependent UI testing workflows.
    
    Args:
        selector: CSS selector of the element to hover over
        hover_type: Type of hover operation (standard, tooltip, menu, validation)
        context: Additional context about the hover operation
    
    Returns:
        Formatted prompt string for hover operation guidance
    """
    hover_descriptions = {
        "standard": "a standard mouse hover to trigger hover states",
        "tooltip": "a hover to display tooltips or help information",
        "menu": "a hover to open dropdown menus or navigation",
        "validation": "a hover to test hover-dependent validation or styling",
        "dynamic": "a hover to reveal dynamic content or overlays"
    }
    
    description = hover_descriptions.get(hover_type, "a mouse hover operation")
    context_section = f"\n\nAdditional Context:\n{context}" if context else ""
    
    return f"""Hover the mouse over the element with selector '{selector}' to perform {description}.

This hover operation will trigger any CSS :hover states, JavaScript hover event handlers, and dynamic content that depends on mouse positioning. The operation supports comprehensive hover testing scenarios including:

Hover Use Cases:
- Dropdown menu activation and navigation testing
- Tooltip display and content validation
- Interactive element state changes (:hover CSS effects)
- Dynamic content reveal (hidden elements, overlays)
- Form field help text and validation hints
- Image galleries and preview functionality
- Navigation menu expansion and interaction
- Interactive charts and data visualization
- Context menus and right-click alternatives
- Progressive disclosure interface patterns

The hover operation provides detailed positioning and timing control:
- Element targeting: Uses CSS selectors for precise element identification
- Position control: Optional specific coordinates within the element
- Force option: Bypasses actionability checks when needed
- Timeout management: Configurable wait times for element availability
- Delay support: Post-hover delays for UI state stabilization

Hover behavior details:
- Method: Uses Playwright's hover() method for authentic mouse simulation
- Positioning: Centers on element by default, supports custom coordinates
- State persistence: Hover state maintained until mouse moves elsewhere
- Validation: Ensures element visibility and actionability before hovering

Advanced hover testing scenarios:
- Nested menu navigation (hover over parent to reveal submenu)
- Tooltip content verification and positioning
- CSS animation and transition testing on hover
- Form validation message display
- Image preview and lightbox activation
- Interactive dashboard widget behaviors
- Accessibility testing for keyboard navigation alternatives

Best practices for reliable hover operations:
- Use stable selectors (ID, data attributes) for consistent targeting
- Allow sufficient timeout for dynamic content loading
- Consider post-hover delays for UI animations and state changes
- Test hover effects across different browsers and devices
- Validate hover-dependent content after hover operation
- Account for mobile touch device behavior differences
- Test hover state persistence and cleanup

The operation provides comprehensive metadata including hover coordinates, element bounds, timing information, and page context for detailed test reporting and debugging.{context_section}"""


@mcp_server.prompt()
def dropdown_menu_hover_prompt(menu_selector: str, expected_items: list = None) -> str:
    """
    Returns a prompt for hovering over dropdown menus and validating menu items.
    
    Args:
        menu_selector: CSS selector of the menu trigger element
        expected_items: Optional list of expected menu items to validate
    
    Returns:
        Formatted prompt string for dropdown menu hover operation
    """
    items_section = ""
    if expected_items:
        items_list = ", ".join(f"'{item}'" for item in expected_items)
        items_section = f"\n\nExpected menu items to validate: {items_list}"
    
    return f"""Hover over the dropdown menu trigger element '{menu_selector}' to open the menu and test navigation functionality.

This dropdown menu hover operation will:
1. Position mouse over the menu trigger element
2. Activate hover state to reveal dropdown menu
3. Allow time for menu animation and stabilization
4. Enable subsequent menu item interaction and validation

Dropdown menu testing workflow:
- Hover trigger: Position mouse over menu trigger element
- Menu reveal: Wait for dropdown menu to become visible
- Content validation: Verify menu items and structure
- Navigation testing: Test menu item interactions
- Menu closure: Validate menu closing behavior

Menu interaction patterns:
- Parent menu hover: Reveals primary dropdown content
- Submenu navigation: Hover over items with submenus
- Menu item selection: Click on specific menu options
- Menu dismissal: Move mouse away or click elsewhere

Accessibility considerations:
- Ensure keyboard navigation alternatives exist
- Verify ARIA attributes and screen reader support
- Test tab order and focus management
- Validate escape key menu dismissal

Common menu behaviors to test:
- Smooth reveal and hide animations
- Proper z-index layering over page content
- Responsive positioning (stays within viewport)
- Touch device compatibility
- Menu item highlighting and selection states{items_section}

The hover operation includes comprehensive timing and positioning metadata to support detailed menu behavior analysis and debugging."""


@mcp_server.prompt()
def tooltip_hover_prompt(element_selector: str, tooltip_content: str = "") -> str:
    """
    Returns a prompt for hovering over elements to display and validate tooltips.
    
    Args:
        element_selector: CSS selector of the element that triggers the tooltip
        tooltip_content: Expected tooltip content to validate
    
    Returns:
        Formatted prompt string for tooltip hover testing
    """
    content_section = f"\n\nExpected tooltip content: '{tooltip_content}'" if tooltip_content else ""
    
    return f"""Hover over the element '{element_selector}' to display its tooltip and validate tooltip behavior.

This tooltip hover operation enables comprehensive tooltip testing including:

Tooltip Display Testing:
- Hover trigger: Position mouse over target element
- Tooltip appearance: Verify tooltip becomes visible after hover
- Positioning: Validate tooltip placement relative to trigger element
- Content validation: Check tooltip text, formatting, and styling
- Timing: Test tooltip display delay and fade-in animation

Tooltip Behavior Validation:
- Positioning logic: Tooltip should avoid viewport edges
- Content accuracy: Tooltip text matches expected information
- Visual styling: Colors, fonts, borders, shadows are correct
- Animation effects: Smooth fade-in/fade-out transitions
- Dismissal behavior: Tooltip hides when mouse moves away

Advanced tooltip testing scenarios:
- Multi-line tooltip content handling
- Rich content tooltips (HTML, images, links)
- Dynamic tooltip content based on element state
- Tooltip positioning in scrollable containers
- Touch device tooltip behavior (tap to show/hide)
- Keyboard accessibility (focus to show tooltip)

Tooltip accessibility verification:
- ARIA attributes (aria-describedby, role="tooltip")
- Screen reader compatibility
- High contrast mode visibility
- Keyboard navigation support
- Focus management and tab order

Performance considerations:
- Tooltip rendering performance with large content
- Memory management for dynamic tooltips
- Hover delay optimization for user experience
- Tooltip cleanup when elements are removed

Common tooltip issues to validate:
- Tooltip clipping at viewport boundaries
- Z-index conflicts with other page elements
- Tooltip flickering on mouse movement
- Incorrect positioning with page scroll
- Tooltip persistence when it shouldn't{content_section}

The hover operation provides detailed metadata including tooltip timing, positioning coordinates, and element state information for comprehensive tooltip behavior analysis."""


@mcp_server.prompt()
def interactive_element_hover_prompt(element_selector: str, expected_changes: list = None) -> str:
    """
    Returns a prompt for testing interactive element hover states and visual changes.
    
    Args:
        element_selector: CSS selector of the interactive element
        expected_changes: Optional list of expected visual or state changes on hover
    
    Returns:
        Formatted prompt string for interactive element hover testing
    """
    changes_section = ""
    if expected_changes:
        changes_list = "\n".join(f"- {change}" for change in expected_changes)
        changes_section = f"\n\nExpected hover state changes:\n{changes_list}"
    
    return f"""Test interactive hover behavior for element '{element_selector}' by hovering to trigger state changes and visual feedback.

This interactive element hover testing covers comprehensive hover state validation:

Visual State Changes:
- Color transitions: Background, text, border color changes
- Size modifications: Element scaling, padding, margin adjustments
- Shadow effects: Box-shadow appearance or modifications
- Opacity changes: Element transparency adjustments
- Transform effects: Rotation, skewing, or translation
- Cursor changes: Pointer, hand, or custom cursor display

Interactive Feedback Testing:
- Button hover states: Color, elevation, shadow changes
- Link hover effects: Underlines, color transitions
- Card hover interactions: Elevation, shadow, scale effects
- Icon hover animations: Color, rotation, or morphing
- Form input focus indicators: Border, background changes
- Navigation item highlighting: Active state indication

CSS Transition Validation:
- Smooth transition timing and easing functions
- Transition property coverage (all affected properties)
- Performance of complex animations
- Browser compatibility of transition effects
- Accessibility considerations for motion sensitivity

JavaScript Hover Event Testing:
- Event handler execution on mouseenter/mouseleave
- Proper event bubbling and propagation
- State management during hover interactions
- Dynamic content updates triggered by hover
- Performance of hover event handlers

Advanced Interactive Testing:
- Nested element hover inheritance
- Hover state conflicts between parent/child elements
- Hover state persistence during element updates
- Touch device hover simulation behavior
- Keyboard focus hover state equivalents

Accessibility and Usability:
- Sufficient color contrast in hover states
- Clear visual indication of interactive elements
- Consistent hover behavior across similar elements
- Alternative interaction methods for touch devices
- Screen reader announcements for state changes{changes_section}

The hover operation captures detailed state information before, during, and after hover to enable comprehensive interactive behavior validation and debugging.""" 
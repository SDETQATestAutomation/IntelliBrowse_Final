"""
Scroll Page Prompt for IntelliBrowse MCP Server.

This module provides prompt templates for guiding LLM operations related to
page scrolling and navigation, supporting scroll-based testing scenarios,
infinite scroll handling, and element visibility workflows.
"""

import sys
from pathlib import Path

# Add parent directory to path for MCP server import
sys.path.append(str(Path(__file__).parent.parent))
from main import mcp_server


@mcp_server.prompt()
def scroll_page_prompt(
    direction: str = "",
    pixels: int = 0,
    selector: str = "",
    element_target: bool = False
) -> str:
    """
    Returns a prompt guiding the LLM to perform scroll operations on web pages.
    
    This prompt template helps users understand how to perform various scroll
    operations and provides context for navigation and testing workflows.
    
    Args:
        direction: The scroll direction (up, down, left, right, top, bottom)
        pixels: Number of pixels to scroll (positive or negative)
        selector: CSS selector for element-specific scrolling
        element_target: Whether to scroll to a specific element
    
    Returns:
        Formatted prompt string for scroll operation guidance
    """
    # Build operation description based on parameters
    if element_target and selector:
        operation = f"scroll to the element '{selector}'"
        context_type = "element targeting"
    elif selector and (direction or pixels):
        if direction:
            operation = f"scroll the element '{selector}' {direction}"
        else:
            operation = f"scroll the element '{selector}' by {pixels} pixels"
        context_type = "element scrolling"
    elif direction:
        operation = f"scroll the page {direction}"
        context_type = "directional page scrolling"
    elif pixels:
        operation = f"scroll the page by {pixels} pixels"
        context_type = "pixel-based page scrolling"
    else:
        operation = "perform a scroll operation"
        context_type = "general scrolling"
    
    return f"""Perform a {context_type} operation to {operation}.

This scroll operation supports comprehensive web page navigation and testing scenarios:

Scroll Operation Types:
- **Directional Scrolling**: Navigate in specific directions (up, down, left, right)
- **Absolute Positioning**: Jump to page extremes (top, bottom)
- **Pixel-Based Control**: Precise scrolling by exact pixel amounts
- **Element Scrolling**: Scroll within specific containers or elements
- **Element Targeting**: Navigate directly to specific page elements

Scroll Use Cases:
- **Infinite Scroll Testing**: Trigger lazy loading and dynamic content
- **Element Visibility**: Bring specific elements into viewport for interaction
- **Form Navigation**: Scroll to form fields or sections during testing
- **Content Discovery**: Navigate through long pages or articles
- **Responsive Testing**: Verify behavior across different scroll positions
- **Performance Testing**: Analyze scroll performance and smooth scrolling

Technical Features:
- **Session Management**: Operates within existing browser sessions
- **Element Validation**: Verifies element existence before scrolling
- **Position Tracking**: Records initial and final scroll positions
- **Smooth Animation**: Optional smooth scrolling for better UX testing
- **Error Handling**: Comprehensive error detection and reporting
- **Metadata Collection**: Detailed operation timing and position data

Scroll Safety & Best Practices:
- **Timeout Protection**: Configurable timeouts for element availability
- **Page State Verification**: Ensures page is active before scrolling
- **Scroll Limits**: Respects page boundaries and scroll limits
- **Element Boundaries**: Validates element scroll capabilities
- **Performance Optimization**: Efficient scroll operations with minimal overhead

Advanced Scrolling Capabilities:
- **Container Scrolling**: Scroll within specific elements (divs, modals, lists)
- **Multi-directional**: Support for both vertical and horizontal scrolling
- **Progressive Loading**: Handle infinite scroll and lazy-loaded content
- **Position Restoration**: Track positions for test repeatability
- **Viewport Management**: Ensure elements are properly positioned in viewport

Integration with Testing Workflows:
- **Before Interaction**: Scroll elements into view before clicking/typing
- **Content Validation**: Verify content visibility after scrolling
- **Layout Testing**: Check responsive behavior during scroll
- **Animation Testing**: Validate scroll-triggered animations
- **Navigation Flows**: Support multi-step navigation scenarios

The scroll operation provides comprehensive position tracking, timing analysis, and detailed metadata for test reporting and debugging purposes. All operations include validation of scroll success and detailed error reporting for reliable automation workflows."""


@mcp_server.prompt()
def scroll_to_element_prompt(element_description: str, selector: str = "") -> str:
    """
    Returns a prompt for scrolling to bring a specific element into view.
    
    Args:
        element_description: Natural language description of the element
        selector: CSS selector for the target element
    
    Returns:
        Formatted prompt string for scroll-to-element operation guidance
    """
    selector_info = f" (selector: {selector})" if selector else ""
    
    return f"""Scroll the page to bring the '{element_description}'{selector_info} into view.

This scroll-to-element operation is essential for ensuring element visibility before interaction:

Element Targeting Benefits:
- **Automatic Navigation**: Intelligently scrolls to bring elements into viewport
- **Cross-Browser Compatibility**: Works consistently across different browsers
- **Responsive Handling**: Adapts to different screen sizes and layouts
- **Accessibility Support**: Ensures elements are properly visible for interaction

Scroll-to-Element Process:
1. **Element Location**: Locates the target element using the provided selector
2. **Visibility Check**: Determines if element is already in viewport
3. **Smart Scrolling**: Calculates optimal scroll position for element visibility
4. **Position Verification**: Confirms element is properly positioned after scrolling
5. **Interaction Readiness**: Ensures element is ready for subsequent interactions

Use Cases for Element Targeting:
- **Form Field Navigation**: Scroll to specific input fields before filling
- **Button Interactions**: Ensure buttons are visible before clicking
- **Content Verification**: Bring text or images into view for validation
- **Modal Handling**: Navigate to elements within scrollable modals
- **Table Navigation**: Scroll to specific rows or cells in large tables

Technical Implementation:
- **Smart Positioning**: Uses Playwright's scroll_into_view_if_needed for optimal positioning
- **Viewport Awareness**: Considers browser viewport size and position
- **Element State**: Validates element is attached and visible
- **Performance Optimized**: Only scrolls when necessary for viewport positioning

Integration with Testing:
- **Pre-Interaction Setup**: Essential before click, type, or validation operations
- **Visual Testing**: Ensures screenshots capture the intended element
- **Accessibility Testing**: Verifies proper element focus and visibility
- **Mobile Testing**: Critical for responsive design testing on smaller screens

The operation provides detailed feedback on scroll distance, final element position, and viewport alignment for comprehensive test reporting."""


@mcp_server.prompt()
def infinite_scroll_prompt(trigger_method: str = "bottom", iterations: int = 1) -> str:
    """
    Returns a prompt for handling infinite scroll scenarios in testing.
    
    Args:
        trigger_method: Method to trigger infinite scroll (bottom, element, manual)
        iterations: Number of scroll iterations to perform
    
    Returns:
        Formatted prompt string for infinite scroll testing guidance
    """
    return f"""Handle infinite scroll content loading using {trigger_method} trigger method for {iterations} iteration(s).

Infinite scroll testing is crucial for modern web applications with dynamic content loading:

Infinite Scroll Patterns:
- **Bottom Trigger**: Scroll to page bottom to trigger content loading
- **Element Trigger**: Scroll to specific trigger elements (loading indicators)
- **Distance Trigger**: Scroll within certain distance of page end
- **Manual Trigger**: Controlled scrolling with custom intervals

Testing Strategy for Infinite Scroll:
1. **Initial State Capture**: Record initial page content and position
2. **Scroll Trigger**: Perform scroll operation to trigger content loading
3. **Loading Detection**: Wait for new content to appear and load
4. **Content Validation**: Verify new content is properly loaded and displayed
5. **Position Tracking**: Monitor scroll position and page growth
6. **Iteration Control**: Repeat process for specified number of iterations

Content Loading Validation:
- **Element Count Monitoring**: Track increasing number of content items
- **Loading Indicators**: Watch for spinners, progress bars, or loading text
- **Network Activity**: Monitor for AJAX requests and responses
- **DOM Changes**: Detect new elements being added to the page
- **Scroll Limit Detection**: Identify when no more content is available

Performance Considerations:
- **Load Time Monitoring**: Track time taken for each content batch to load
- **Memory Usage**: Monitor browser memory consumption during scrolling
- **Scroll Performance**: Measure scroll smoothness and responsiveness
- **Error Detection**: Identify failed content loads or timeouts

Common Infinite Scroll Challenges:
- **Loading Timing**: Content may load asynchronously with varying delays
- **Scroll Position**: Page height changes as content loads
- **End Detection**: Determining when no more content is available
- **Error Handling**: Managing failed loads or network issues
- **Browser Limits**: Handling browser performance with large amounts of content

Best Practices for Infinite Scroll Testing:
- **Gradual Scrolling**: Allow time between scroll operations for content loading
- **Content Verification**: Validate that new content is unique and properly formatted
- **Error Recovery**: Handle and retry failed content loads
- **Performance Monitoring**: Track page performance degradation over time
- **Exit Conditions**: Define clear stopping criteria for scroll testing

The infinite scroll testing provides comprehensive monitoring of content loading, performance metrics, and detailed reporting on each iteration's success and timing."""


@mcp_server.prompt()
def scroll_position_validation_prompt(expected_position: str = "", tolerance: int = 10) -> str:
    """
    Returns a prompt for validating scroll positions during testing.
    
    Args:
        expected_position: Expected scroll position (top, bottom, middle, specific coordinates)
        tolerance: Acceptable pixel tolerance for position validation
    
    Returns:
        Formatted prompt string for scroll position validation guidance
    """
    position_desc = f"expected position of '{expected_position}'" if expected_position else "current scroll position"
    
    return f"""Validate the {position_desc} with a tolerance of {tolerance} pixels.

Scroll position validation is essential for ensuring precise navigation and testing accuracy:

Position Validation Types:
- **Absolute Coordinates**: Validate exact X,Y scroll coordinates
- **Relative Positions**: Check position relative to page dimensions (top, middle, bottom)
- **Element Alignment**: Verify specific elements are properly positioned in viewport
- **Scroll Percentages**: Validate position as percentage of total scrollable area

Validation Accuracy Features:
- **Pixel Tolerance**: Configurable tolerance for minor position variations
- **Cross-Browser Consistency**: Account for browser-specific scroll behavior differences
- **Responsive Adaptation**: Validate positions across different screen sizes
- **Timing Considerations**: Account for scroll animation completion

Position Validation Process:
1. **Current Position Capture**: Get actual scroll coordinates from browser
2. **Expected Position Calculation**: Calculate expected coordinates based on criteria
3. **Tolerance Comparison**: Compare actual vs expected within acceptable tolerance
4. **Validation Result**: Report success/failure with detailed position information
5. **Diagnostic Data**: Provide detailed metrics for debugging position issues

Use Cases for Position Validation:
- **Navigation Testing**: Verify proper scroll position after navigation
- **Bookmark Functionality**: Validate position restoration from saved state
- **Responsive Behavior**: Check scroll position consistency across devices
- **Animation Testing**: Verify final position after scroll animations
- **User Experience**: Ensure scroll behavior meets design specifications

Advanced Validation Scenarios:
- **Multi-Element Positioning**: Validate multiple elements are properly positioned
- **Viewport Calculations**: Consider browser viewport size in position validation
- **Scroll Container Testing**: Validate positions within scrollable containers
- **Progressive Enhancement**: Test position behavior with and without JavaScript

Error Reporting and Debugging:
- **Position Discrepancy**: Detailed reporting of actual vs expected positions
- **Tolerance Analysis**: Analysis of why position validation failed
- **Browser Information**: Include browser and viewport details in reports
- **Screenshot Integration**: Optional screenshot capture for visual validation

The validation provides comprehensive position analysis, tolerance checking, and detailed reporting for reliable scroll position testing in automated workflows.""" 
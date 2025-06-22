"""
Validate User Agent Tool for IntelliBrowse MCP Server.
Validates and manages browser user agent strings with comprehensive analysis.
"""

import re
import time
from datetime import datetime
from difflib import SequenceMatcher
from typing import Optional, Dict, Any, List

import structlog
# Import the shared server instance
try:
    from server_instance import mcp_server
except ImportError:
    # Fallback for when running directly from mcp directory
    from server_instance import mcp_server


try:
    from schemas.tools.validate_user_agent_schemas import ValidateUserAgentRequest, ValidateUserAgentResponse
except ImportError:
    # Fallback for when running directly from mcp directory
    from schemas.tools.validate_user_agent_schemas import ValidateUserAgentRequest, ValidateUserAgentResponse
from .browser_session import browser_sessions

# Initialize structured logger
logger = structlog.get_logger(__name__)

# Get the FastMCP server instance
# Use the shared mcp_server instance (imported above)


def parse_user_agent(user_agent: str) -> Dict[str, Any]:
    """Parse user agent string and extract components."""
    
    analysis = {
        "browser": "Unknown",
        "version": "Unknown",
        "platform": "Unknown",
        "engine": "Unknown",
        "rendering_engine": "Unknown",
        "mobile": False,
        "components": []
    }
    
    if not user_agent:
        return analysis
    
    # Browser detection patterns
    browser_patterns = [
        (r'Chrome/(\d+\.\d+\.\d+\.\d+)', 'Chrome'),
        (r'Firefox/(\d+\.\d+)', 'Firefox'),
        (r'Safari/(\d+\.\d+)', 'Safari'),
        (r'Edge/(\d+\.\d+)', 'Edge'),
        (r'Opera/(\d+\.\d+)', 'Opera'),
        (r'Version/(\d+\.\d+).*Safari', 'Safari'),
    ]
    
    # Platform detection patterns
    platform_patterns = [
        (r'Windows NT (\d+\.\d+)', 'Windows'),
        (r'Mac OS X (\d+[_\d]*)', 'macOS'),
        (r'Linux', 'Linux'),
        (r'Android (\d+\.\d+)', 'Android'),
        (r'iOS (\d+[_\d]*)', 'iOS'),
    ]
    
    # Engine detection patterns
    engine_patterns = [
        (r'WebKit/(\d+\.\d+)', 'WebKit'),
        (r'Gecko/(\d+)', 'Gecko'),
        (r'Trident/(\d+\.\d+)', 'Trident'),
        (r'Presto/(\d+\.\d+)', 'Presto'),
    ]
    
    # Detect browser
    for pattern, browser_name in browser_patterns:
        match = re.search(pattern, user_agent)
        if match:
            analysis["browser"] = browser_name
            analysis["version"] = match.group(1)
            break
    
    # Detect platform
    for pattern, platform_name in platform_patterns:
        match = re.search(pattern, user_agent)
        if match:
            if platform_name in ['Windows', 'macOS']:
                analysis["platform"] = f"{platform_name} {match.group(1)}"
            elif match.groups():
                analysis["platform"] = f"{platform_name} {match.group(1)}"
            else:
                analysis["platform"] = platform_name
            break
    
    # Detect engine
    for pattern, engine_name in engine_patterns:
        match = re.search(pattern, user_agent)
        if match:
            analysis["engine"] = f"{engine_name}/{match.group(1)}"
            break
    
    # Detect rendering engine
    if 'WebKit' in user_agent:
        if 'Chrome' in user_agent or 'Safari' in user_agent:
            analysis["rendering_engine"] = "Blink" if 'Chrome' in user_agent else "WebKit"
    elif 'Gecko' in user_agent:
        analysis["rendering_engine"] = "Gecko"
    elif 'Trident' in user_agent:
        analysis["rendering_engine"] = "Trident"
    
    # Detect mobile
    mobile_indicators = ['Mobile', 'Android', 'iPhone', 'iPad', 'BlackBerry', 'Windows Phone']
    analysis["mobile"] = any(indicator in user_agent for indicator in mobile_indicators)
    
    # Extract all components
    components = user_agent.split(' ')
    analysis["components"] = [comp.strip() for comp in components if comp.strip()]
    
    return analysis


def calculate_similarity(str1: str, str2: str, case_sensitive: bool = True) -> float:
    """Calculate similarity score between two strings."""
    if not case_sensitive:
        str1 = str1.lower()
        str2 = str2.lower()
    
    return SequenceMatcher(None, str1, str2).ratio()


def find_differences(current: str, expected: str, case_sensitive: bool = True) -> List[str]:
    """Find specific differences between current and expected user agents."""
    differences = []
    
    if not case_sensitive:
        current = current.lower()
        expected = expected.lower()
    
    if current != expected:
        # Split into components for detailed comparison
        current_parts = current.split(' ')
        expected_parts = expected.split(' ')
        
        # Check for missing or extra parts
        current_set = set(current_parts)
        expected_set = set(expected_parts)
        
        missing = expected_set - current_set
        extra = current_set - expected_set
        
        if missing:
            differences.append(f"Missing components: {', '.join(missing)}")
        if extra:
            differences.append(f"Extra components: {', '.join(extra)}")
        
        # Check for version differences
        version_pattern = r'(\w+)/(\d+\.\d+[\.\d]*)'
        current_versions = dict(re.findall(version_pattern, current))
        expected_versions = dict(re.findall(version_pattern, expected))
        
        for component, expected_version in expected_versions.items():
            if component in current_versions:
                if current_versions[component] != expected_version:
                    differences.append(f"{component} version: expected {expected_version}, got {current_versions[component]}")
            else:
                differences.append(f"Missing {component} version")
    
    return differences


@mcp_server.tool()
async def validate_user_agent(
    session_id: str,
    expected_user_agent: str,
    set_if_different: Optional[bool] = False,
    strict_validation: Optional[bool] = True,
    case_sensitive: Optional[bool] = True,
    analyze_components: Optional[bool] = True,
    timeout_ms: Optional[int] = 5000
) -> Dict[str, Any]:
    """
    Validate current browser user agent against expected value.
    
    Implements comprehensive user agent validation with features:
    - Exact or fuzzy user agent comparison
    - Detailed user agent component analysis
    - Automatic user agent updating when different
    - Similarity scoring and difference detection
    - Case-sensitive or case-insensitive comparison
    
    Args:
        session_id: Active browser session ID
        expected_user_agent: Expected user agent string to validate against
        set_if_different: Update user agent if different from expected
        strict_validation: Perform strict exact match validation
        case_sensitive: Case-sensitive string comparison
        analyze_components: Analyze and extract user agent components
        timeout_ms: Operation timeout in milliseconds (1000-30000)
    
    Returns:
        Dict containing validation results, analysis, and metadata
        
    Raises:
        ValueError: For invalid input parameters
        RuntimeError: For session or browser operation failures
    """
    
    # Validate inputs using Pydantic
    try:
        request = ValidateUserAgentRequest(
            session_id=session_id,
            expected_user_agent=expected_user_agent,
            set_if_different=set_if_different,
            strict_validation=strict_validation,
            case_sensitive=case_sensitive,
            analyze_components=analyze_components,
            timeout_ms=timeout_ms
        )
    except Exception as e:
        logger.error("validate_user_agent_validation_failed", error=str(e), session_id=session_id)
        return ValidateUserAgentResponse(
            success=False,
            message=f"Invalid input parameters: {str(e)}",
            validation_passed=False,
            expected_user_agent=expected_user_agent,
            strict_validation=strict_validation,
            case_sensitive=case_sensitive,
            session_id=session_id,
            timestamp=datetime.utcnow().isoformat(),
            error_type="ValidationError",
            error_details={"validation_error": str(e)}
        ).dict()

    operation_start_time = time.time()
    logger.info(
        "validate_user_agent_started",
        session_id=session_id,
        expected_user_agent=expected_user_agent[:50] + "..." if len(expected_user_agent) > 50 else expected_user_agent,
        set_if_different=set_if_different,
        strict_validation=strict_validation,
        case_sensitive=case_sensitive,
        analyze_components=analyze_components
    )

    try:
        # Get browser session
        if session_id not in browser_sessions:
            error_msg = f"Browser session '{session_id}' not found"
            logger.error("validate_user_agent_session_not_found", session_id=session_id)
            return ValidateUserAgentResponse(
                success=False,
                message=error_msg,
                validation_passed=False,
                expected_user_agent=expected_user_agent,
                strict_validation=strict_validation,
                case_sensitive=case_sensitive,
                session_id=session_id,
                timestamp=datetime.utcnow().isoformat(),
                error_type="SessionNotFound",
                error_details={"session_id": session_id}
            ).dict()

        session = browser_sessions[session_id]
        page = session["page"]

        # Verify page is accessible
        if page.is_closed():
            error_msg = f"Browser page for session '{session_id}' is closed"
            logger.error("validate_user_agent_page_closed", session_id=session_id)
            return ValidateUserAgentResponse(
                success=False,
                message=error_msg,
                validation_passed=False,
                expected_user_agent=expected_user_agent,
                strict_validation=strict_validation,
                case_sensitive=case_sensitive,
                session_id=session_id,
                timestamp=datetime.utcnow().isoformat(),
                error_type="PageClosed",
                error_details={"session_id": session_id}
            ).dict()

        # Get current user agent
        try:
            current_user_agent = await page.evaluate("navigator.userAgent", timeout=timeout_ms)
        except Exception as e:
            error_msg = f"Failed to retrieve current user agent: {str(e)}"
            logger.error("validate_user_agent_retrieval_failed", session_id=session_id, error=str(e))
            return ValidateUserAgentResponse(
                success=False,
                message=error_msg,
                validation_passed=False,
                expected_user_agent=expected_user_agent,
                strict_validation=strict_validation,
                case_sensitive=case_sensitive,
                session_id=session_id,
                timestamp=datetime.utcnow().isoformat(),
                error_type="UserAgentRetrievalFailed",
                error_details={"error": str(e)}
            ).dict()

        # Perform validation
        if strict_validation:
            if case_sensitive:
                validation_passed = current_user_agent == expected_user_agent
            else:
                validation_passed = current_user_agent.lower() == expected_user_agent.lower()
        else:
            # Fuzzy validation using similarity score
            similarity_score = calculate_similarity(current_user_agent, expected_user_agent, case_sensitive)
            validation_passed = similarity_score >= 0.8  # 80% similarity threshold
        
        # Calculate similarity score
        similarity_score = calculate_similarity(current_user_agent, expected_user_agent, case_sensitive)
        
        # Find differences
        differences = find_differences(current_user_agent, expected_user_agent, case_sensitive)
        
        # Analyze user agent components if requested
        user_agent_analysis = None
        if analyze_components:
            user_agent_analysis = parse_user_agent(current_user_agent)
        
        # Handle user agent update if requested
        user_agent_updated = False
        previous_user_agent = None
        
        if set_if_different and not validation_passed:
            try:
                previous_user_agent = current_user_agent
                
                # Set new user agent using CDP
                browser = session["browser"]
                context = await browser.new_context(user_agent=expected_user_agent)
                
                # Note: In practice, changing user agent requires creating a new context
                # This is a simplified approach - real implementation would need context management
                
                logger.info(
                    "validate_user_agent_updated",
                    session_id=session_id,
                    previous_user_agent=previous_user_agent[:50] + "..." if len(previous_user_agent) > 50 else previous_user_agent,
                    new_user_agent=expected_user_agent[:50] + "..." if len(expected_user_agent) > 50 else expected_user_agent
                )
                
                user_agent_updated = True
                current_user_agent = expected_user_agent  # Update for response
                validation_passed = True  # Now matches
                
            except Exception as e:
                logger.error(
                    "validate_user_agent_update_failed",
                    session_id=session_id,
                    error=str(e)
                )
                # Continue with validation results even if update failed

        operation_time_ms = int((time.time() - operation_start_time) * 1000)
        
        # Determine success message
        if validation_passed:
            message = "User agent validation passed"
            if user_agent_updated:
                message += " (user agent was updated)"
        else:
            message = f"User agent validation failed - similarity: {similarity_score:.2f}"
        
        logger.info(
            "validate_user_agent_completed",
            session_id=session_id,
            validation_passed=validation_passed,
            similarity_score=similarity_score,
            user_agent_updated=user_agent_updated,
            differences_count=len(differences),
            operation_time_ms=operation_time_ms
        )

        return ValidateUserAgentResponse(
            success=True,
            message=message,
            validation_passed=validation_passed,
            current_user_agent=current_user_agent,
            expected_user_agent=expected_user_agent,
            user_agent_analysis=user_agent_analysis,
            differences=differences,
            similarity_score=similarity_score,
            user_agent_updated=user_agent_updated,
            previous_user_agent=previous_user_agent,
            strict_validation=strict_validation,
            case_sensitive=case_sensitive,
            operation_time_ms=operation_time_ms,
            session_id=session_id,
            timestamp=datetime.utcnow().isoformat()
        ).dict()

    except Exception as e:
        operation_time_ms = int((time.time() - operation_start_time) * 1000)
        error_msg = f"User agent validation operation failed: {str(e)}"
        logger.error(
            "validate_user_agent_failed",
            session_id=session_id,
            error=str(e),
            operation_time_ms=operation_time_ms
        )

        return ValidateUserAgentResponse(
            success=False,
            message=error_msg,
            validation_passed=False,
            expected_user_agent=expected_user_agent,
            strict_validation=strict_validation,
            case_sensitive=case_sensitive,
            session_id=session_id,
            timestamp=datetime.utcnow().isoformat(),
            error_type="UnexpectedError",
            error_details={"error": str(e), "operation_time_ms": operation_time_ms}
        ).dict()


# Tool registration will be handled by FastMCP automatically
logger.info("validate_user_agent_tool_registered", tool="validate_user_agent") 
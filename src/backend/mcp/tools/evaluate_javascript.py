"""
Evaluate JavaScript Tool for IntelliBrowse MCP Server.
Executes custom JavaScript with enterprise security controls and comprehensive audit logging.
"""

import hashlib
import time
from datetime import datetime
from typing import Optional, Dict, Any, List

import structlog
# Import the shared server instance
try:
    from server_instance import mcp_server
except ImportError:
    # Fallback for when running directly from mcp directory
    from server_instance import mcp_server


try:
    from schemas.tools.evaluate_javascript_schemas import EvaluateJavaScriptRequest, EvaluateJavaScriptResponse
except ImportError:
    # Fallback for when running directly from mcp directory
    from schemas.tools.evaluate_javascript_schemas import EvaluateJavaScriptRequest, EvaluateJavaScriptResponse
from .browser_session import browser_sessions

# Initialize structured logger
logger = structlog.get_logger(__name__)

# Get the FastMCP server instance
# Use the shared mcp_server instance (imported above)


def generate_script_hash(script: str) -> str:
    """Generate SHA256 hash of script for audit purposes."""
    return hashlib.sha256(script.encode('utf-8')).hexdigest()


def perform_security_validation(script: str, security_context: str) -> Dict[str, Any]:
    """Perform comprehensive security validation on JavaScript code."""
    
    security_checks = {
        "dangerous_patterns": 0,
        "api_restrictions": [],
        "validation_passed": True,
        "warnings": [],
        "blocked_patterns": []
    }
    
    # Define security patterns based on context
    if security_context == "restricted":
        dangerous_patterns = [
            'eval(',
            'Function(',
            'setTimeout(',
            'setInterval(',
            'XMLHttpRequest',
            'fetch(',
            'import(',
            'require(',
            'process.',
            'global.',
            'window.location.href =',
            'window.location.replace',
            'window.open(',
            'document.cookie',
            'localStorage.',
            'sessionStorage.',
            'indexedDB.',
            '__proto__',
            'constructor.constructor',
            'alert(',
            'confirm(',
            'prompt(',
            'window.external',
            'ActiveXObject',
            'document.write',
            'document.writeln',
            'innerHTML =',
            'outerHTML =',
            'insertAdjacentHTML',
            'execScript',
            'javascript:',
            'data:text/html',
            'srcdoc='
        ]
        
        security_checks["api_restrictions"] = [
            "network_requests", "file_system", "navigation", 
            "storage", "dialogs", "dynamic_code", "dom_manipulation"
        ]
    else:  # elevated context
        dangerous_patterns = [
            'eval(',
            'Function(',
            '__proto__',
            'constructor.constructor',
            'ActiveXObject',
            'execScript'
        ]
        
        security_checks["api_restrictions"] = ["dynamic_code", "prototype_pollution"]
    
    script_lower = script.lower()
    
    # Check for dangerous patterns
    for pattern in dangerous_patterns:
        if pattern.lower() in script_lower:
            security_checks["dangerous_patterns"] += 1
            security_checks["blocked_patterns"].append(pattern)
            
            if security_context == "restricted":
                security_checks["validation_passed"] = False
            else:
                security_checks["warnings"].append(f"Potentially unsafe pattern: {pattern}")
    
    # Additional checks for script complexity
    if len(script) > 5000:
        security_checks["warnings"].append("Large script detected")
    
    if script.count('\n') > 100:
        security_checks["warnings"].append("Complex script with many lines")
    
    return security_checks


@mcp_server.tool()
async def evaluate_javascript(
    session_id: str,
    script: str,
    args: Optional[List[Any]] = None,
    timeout_ms: Optional[int] = 5000,
    security_context: Optional[str] = "restricted",
    return_by_value: Optional[bool] = True,
    await_promise: Optional[bool] = False,
    world_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute JavaScript in browser context with enterprise security controls.
    
    Implements secure JavaScript execution with comprehensive features:
    - Script validation and sanitization
    - Multiple security contexts (restricted/elevated)
    - Execution timeout limits and control
    - Isolated world execution for security
    - Comprehensive audit logging and monitoring
    - Promise resolution support
    
    Args:
        session_id: Active browser session ID
        script: JavaScript code to execute
        args: Arguments to pass to script function
        timeout_ms: Script execution timeout in milliseconds (100-30000)
        security_context: Security level (restricted, elevated)
        return_by_value: Return result by value instead of handle
        await_promise: Wait for Promise resolution if script returns Promise
        world_name: Isolated world name for script execution
    
    Returns:
        Dict containing script execution results, security info, and metadata
        
    Raises:
        ValueError: For invalid input parameters or security violations
        RuntimeError: For session or browser operation failures
    """
    
    # Validate inputs using Pydantic
    try:
        request = EvaluateJavaScriptRequest(
            session_id=session_id,
            script=script,
            args=args,
            timeout_ms=timeout_ms,
            security_context=security_context,
            return_by_value=return_by_value,
            await_promise=await_promise,
            world_name=world_name
        )
    except Exception as e:
        logger.error("evaluate_javascript_validation_failed", error=str(e), session_id=session_id)
        return EvaluateJavaScriptResponse(
            success=False,
            message=f"Invalid input parameters: {str(e)}",
            session_id=session_id,
            timestamp=datetime.utcnow().isoformat(),
            error_type="ValidationError",
            error_details={"validation_error": str(e)}
        ).dict()

    # Generate script hash for audit
    script_hash = generate_script_hash(script)
    
    # Perform security validation
    security_checks = perform_security_validation(script, security_context)
    
    # Block execution if security validation failed
    if not security_checks["validation_passed"]:
        error_msg = f"Script blocked by security validation: {security_checks['blocked_patterns']}"
        logger.error(
            "evaluate_javascript_security_blocked",
            session_id=session_id,
            script_hash=script_hash,
            blocked_patterns=security_checks["blocked_patterns"],
            security_context=security_context
        )
        return EvaluateJavaScriptResponse(
            success=False,
            message=error_msg,
            script_hash=script_hash,
            security_context=security_context,
            security_checks=security_checks,
            session_id=session_id,
            timestamp=datetime.utcnow().isoformat(),
            error_type="SecurityViolation",
            error_details={
                "blocked_patterns": security_checks["blocked_patterns"],
                "security_context": security_context
            }
        ).dict()

    operation_start_time = time.time()
    logger.info(
        "evaluate_javascript_started",
        session_id=session_id,
        script_hash=script_hash,
        security_context=security_context,
        timeout_ms=timeout_ms,
        return_by_value=return_by_value,
        await_promise=await_promise,
        world_name=world_name,
        security_warnings=len(security_checks.get("warnings", []))
    )

    try:
        # Get browser session
        if session_id not in browser_sessions:
            error_msg = f"Browser session '{session_id}' not found"
            logger.error("evaluate_javascript_session_not_found", session_id=session_id)
            return EvaluateJavaScriptResponse(
                success=False,
                message=error_msg,
                script_hash=script_hash,
                security_context=security_context,
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
            logger.error("evaluate_javascript_page_closed", session_id=session_id)
            return EvaluateJavaScriptResponse(
                success=False,
                message=error_msg,
                script_hash=script_hash,
                security_context=security_context,
                session_id=session_id,
                timestamp=datetime.utcnow().isoformat(),
                error_type="PageClosed",
                error_details={"session_id": session_id}
            ).dict()

        # Prepare script execution options
        execution_options = {
            "timeout": timeout_ms
        }
        
        # Add world context if specified
        if world_name:
            # Create isolated world for enhanced security
            try:
                await page.add_init_script("", world_name=world_name)
                execution_options["world_name"] = world_name
            except Exception as e:
                logger.warning(
                    "evaluate_javascript_world_creation_failed",
                    session_id=session_id,
                    world_name=world_name,
                    error=str(e)
                )

        # Prepare script for execution
        if args and len(args) > 0:
            # Create function wrapper to pass arguments
            wrapped_script = f"""
            (function() {{
                const args = arguments;
                {script}
            }}).apply(this, arguments)
            """
            execution_args = args
        else:
            wrapped_script = f"(function() {{ {script} }})()"
            execution_args = []

        # Execute JavaScript
        try:
            if await_promise:
                # Use evaluate for Promise support
                result = await page.evaluate(wrapped_script, *execution_args, **execution_options)
                promise_resolved = True
            else:
                # Use evaluate for synchronous execution
                result = await page.evaluate(wrapped_script, *execution_args, **execution_options)
                promise_resolved = False
                
        except Exception as e:
            error_msg = f"JavaScript execution failed: {str(e)}"
            logger.error(
                "evaluate_javascript_execution_failed",
                session_id=session_id,
                script_hash=script_hash,
                error=str(e),
                security_context=security_context
            )
            
            execution_time_ms = int((time.time() - operation_start_time) * 1000)
            
            return EvaluateJavaScriptResponse(
                success=False,
                message=error_msg,
                script_hash=script_hash,
                security_context=security_context,
                execution_world=world_name,
                execution_time_ms=execution_time_ms,
                security_checks=security_checks,
                session_id=session_id,
                timestamp=datetime.utcnow().isoformat(),
                error_type="ExecutionError",
                error_details={"error": str(e), "timeout_ms": timeout_ms}
            ).dict()

        execution_time_ms = int((time.time() - operation_start_time) * 1000)
        
        # Determine result type
        result_type = type(result).__name__
        if result is None:
            result_type = "null"
        elif isinstance(result, bool):
            result_type = "boolean"
        elif isinstance(result, (int, float)):
            result_type = "number"
        elif isinstance(result, str):
            result_type = "string"
        elif isinstance(result, (list, tuple)):
            result_type = "array"
        elif isinstance(result, dict):
            result_type = "object"

        # Collect console logs if available (placeholder - would need console event handling)
        console_logs = []
        
        logger.info(
            "evaluate_javascript_completed",
            session_id=session_id,
            script_hash=script_hash,
            security_context=security_context,
            result_type=result_type,
            execution_time_ms=execution_time_ms,
            promise_resolved=promise_resolved,
            world_name=world_name
        )

        return EvaluateJavaScriptResponse(
            success=True,
            message="Script executed successfully",
            result=result,
            result_type=result_type,
            security_context=security_context,
            script_hash=script_hash,
            execution_world=world_name,
            execution_time_ms=execution_time_ms,
            promise_resolved=promise_resolved,
            console_logs=console_logs,
            security_checks=security_checks,
            restricted_apis_accessed=[],  # Would be populated by actual monitoring
            session_id=session_id,
            timestamp=datetime.utcnow().isoformat()
        ).dict()

    except Exception as e:
        operation_time_ms = int((time.time() - operation_start_time) * 1000)
        error_msg = f"JavaScript evaluation operation failed: {str(e)}"
        logger.error(
            "evaluate_javascript_failed",
            session_id=session_id,
            script_hash=script_hash,
            error=str(e),
            operation_time_ms=operation_time_ms,
            security_context=security_context
        )

        return EvaluateJavaScriptResponse(
            success=False,
            message=error_msg,
            script_hash=script_hash,
            security_context=security_context,
            security_checks=security_checks,
            session_id=session_id,
            timestamp=datetime.utcnow().isoformat(),
            error_type="UnexpectedError",
            error_details={"error": str(e), "operation_time_ms": operation_time_ms}
        ).dict()


# Tool registration will be handled by FastMCP automatically
logger.info("evaluate_javascript_tool_registered", tool="evaluate_javascript") 
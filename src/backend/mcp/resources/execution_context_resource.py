"""
IntelliBrowse MCP Server - Execution Context Resource Provider

This module provides test execution context and environment information as MCP resources.
It exposes execution state, test runner configuration, browser context, and environment
variables to enable context-aware AI operations.

Resource URIs:
- execution://context/{session_id} - Current execution context for session
- execution://environment/{session_id} - Environment configuration
- execution://runner/{runner_type} - Test runner specific context
- execution://browser/{browser_id} - Browser instance context
"""

import json
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

try:
    from config.settings import get_settings
except ImportError:
    # Fallback for when running directly from mcp directory
    from config.settings import get_settings
try:
    from schemas.context_schemas import SessionContext, TaskContext
except ImportError:
    # Fallback for when running directly from mcp directory
    from schemas.context_schemas import SessionContext, TaskContext
import structlog

logger = structlog.get_logger(__name__)

# Import MCP server instance - will be set by main.py
mcp_server = None

def set_mcp_server(server):
    """Set the MCP server instance for resource registration."""
    global mcp_server
    mcp_server = server


class ExecutionEnvironment(BaseModel):
    """Test execution environment configuration."""
    
    python_version: str = Field(description="Python interpreter version")
    platform: str = Field(description="Operating system platform")
    browser_versions: Dict[str, str] = Field(description="Available browser versions")
    test_framework: str = Field(description="Primary test framework")
    parallel_workers: int = Field(description="Number of parallel test workers")
    timeout_config: Dict[str, int] = Field(description="Various timeout configurations")
    environment_variables: Dict[str, str] = Field(description="Relevant environment variables")
    headless_mode: bool = Field(description="Whether browser runs in headless mode")
    screenshot_on_failure: bool = Field(description="Whether to capture screenshots on test failure")
    video_recording: bool = Field(description="Whether test execution is recorded")


class BrowserContext(BaseModel):
    """Browser instance execution context."""
    
    browser_id: str = Field(description="Unique browser instance identifier")
    browser_type: str = Field(description="Browser type (chromium, firefox, webkit)")
    browser_version: str = Field(description="Browser version string")
    viewport_size: Dict[str, int] = Field(description="Browser viewport dimensions")
    user_agent: str = Field(description="Browser user agent string")
    timezone: str = Field(description="Browser timezone setting")
    locale: str = Field(description="Browser locale setting")
    permissions: List[str] = Field(description="Granted browser permissions")
    cookies: List[Dict[str, Any]] = Field(description="Current browser cookies")
    local_storage: Dict[str, str] = Field(description="Browser local storage data")
    session_storage: Dict[str, str] = Field(description="Browser session storage data")


class TestRunnerContext(BaseModel):
    """Test runner specific execution context."""
    
    runner_type: str = Field(description="Test runner type (pytest, playwright, etc.)")
    test_file: Optional[str] = Field(description="Currently executing test file")
    test_function: Optional[str] = Field(description="Currently executing test function")
    test_class: Optional[str] = Field(description="Currently executing test class")
    test_markers: List[str] = Field(description="Applied test markers/tags")
    fixtures: List[str] = Field(description="Active test fixtures")
    parameters: Dict[str, Any] = Field(description="Test parameters and data")
    retry_count: int = Field(description="Current retry attempt number")
    max_retries: int = Field(description="Maximum allowed retries")
    execution_time: float = Field(description="Current test execution time in seconds")


class ExecutionContext(BaseModel):
    """Complete test execution context information."""
    
    session_id: str = Field(description="Test session identifier")
    start_time: datetime = Field(description="Execution start timestamp")
    current_time: datetime = Field(description="Current timestamp")
    execution_duration: float = Field(description="Total execution time in seconds")
    status: str = Field(description="Current execution status")
    environment: ExecutionEnvironment = Field(description="Environment configuration")
    browser_context: Optional[BrowserContext] = Field(description="Active browser context")
    runner_context: Optional[TestRunnerContext] = Field(description="Test runner context")
    error_history: List[Dict[str, Any]] = Field(description="Recent errors and exceptions")
    performance_metrics: Dict[str, float] = Field(description="Performance measurements")
    resource_usage: Dict[str, float] = Field(description="CPU, memory, disk usage")


class ExecutionContextResourceProvider:
    """
    Provides test execution context as MCP resources.
    
    This class manages execution context data and exposes it through MCP resource URIs
    for AI tools to understand the current testing environment and state.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._execution_contexts: Dict[str, ExecutionContext] = {}
        self._browser_contexts: Dict[str, BrowserContext] = {}
        self._environment_cache: Optional[ExecutionEnvironment] = None
        self._cache_timeout = 300  # 5 minutes
        self._last_environment_update = None
        
    async def _get_execution_environment(self) -> ExecutionEnvironment:
        """Get current execution environment configuration."""
        try:
            # Cache environment info to avoid repeated system calls
            now = datetime.now(timezone.utc)
            if (self._environment_cache and self._last_environment_update and 
                (now - self._last_environment_update).total_seconds() < self._cache_timeout):
                return self._environment_cache
            
            import sys
            import platform
            import os
            
            # Get browser versions (mock data for now - would integrate with actual browser detection)
            browser_versions = {
                "chromium": "120.0.6099.109",
                "firefox": "121.0",
                "webkit": "17.4"
            }
            
            environment = ExecutionEnvironment(
                python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                platform=platform.system(),
                browser_versions=browser_versions,
                test_framework="playwright",
                parallel_workers=self.settings.session.max_concurrent_sessions,
                timeout_config={
                    "default": 30000,
                    "navigation": 10000,
                    "action": 5000,
                    "assertion": 5000
                },
                environment_variables={
                    k: v for k, v in os.environ.items() 
                    if k.startswith(('TEST_', 'PLAYWRIGHT_', 'BROWSER_'))
                },
                headless_mode=os.getenv('HEADLESS', 'true').lower() == 'true',
                screenshot_on_failure=os.getenv('SCREENSHOT_ON_FAILURE', 'true').lower() == 'true',
                video_recording=os.getenv('VIDEO_RECORDING', 'false').lower() == 'true'
            )
            
            self._environment_cache = environment
            self._last_environment_update = now
            
            logger.info("Retrieved execution environment", 
                       python_version=environment.python_version,
                       platform=environment.platform,
                       parallel_workers=environment.parallel_workers)
            
            return environment
            
        except Exception as e:
            logger.error("Failed to get execution environment", error=str(e), exc_info=True)
            # Return default environment
            return ExecutionEnvironment(
                python_version="3.12.0",
                platform="Unknown",
                browser_versions={},
                test_framework="playwright",
                parallel_workers=1,
                timeout_config={},
                environment_variables={},
                headless_mode=True,
                screenshot_on_failure=True,
                video_recording=False
            )
    
    async def _get_browser_context(self, browser_id: str) -> Optional[BrowserContext]:
        """Get browser context information."""
        try:
            # Check cache first
            if browser_id in self._browser_contexts:
                return self._browser_contexts[browser_id]
            
            # Mock browser context (would integrate with actual Playwright browser instances)
            context = BrowserContext(
                browser_id=browser_id,
                browser_type="chromium",
                browser_version="120.0.6099.109",
                viewport_size={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                timezone="America/New_York",
                locale="en-US",
                permissions=["geolocation", "notifications"],
                cookies=[],
                local_storage={},
                session_storage={}
            )
            
            # Cache the context
            self._browser_contexts[browser_id] = context
            
            logger.info("Retrieved browser context", 
                       browser_id=browser_id,
                       browser_type=context.browser_type,
                       viewport_size=context.viewport_size)
            
            return context
            
        except Exception as e:
            logger.error("Failed to get browser context", 
                        browser_id=browser_id, error=str(e), exc_info=True)
            return None
    
    async def _get_test_runner_context(self, runner_type: str) -> TestRunnerContext:
        """Get test runner specific context."""
        try:
            # Mock runner context (would integrate with actual test runner state)
            context = TestRunnerContext(
                runner_type=runner_type,
                test_file="test_example.py",
                test_function="test_login_flow",
                test_class="TestAuthentication",
                test_markers=["smoke", "auth"],
                fixtures=["browser", "page", "test_data"],
                parameters={"username": "test_user", "environment": "staging"},
                retry_count=0,
                max_retries=3,
                execution_time=5.2
            )
            
            logger.info("Retrieved test runner context", 
                       runner_type=runner_type,
                       test_function=context.test_function,
                       execution_time=context.execution_time)
            
            return context
            
        except Exception as e:
            logger.error("Failed to get test runner context", 
                        runner_type=runner_type, error=str(e), exc_info=True)
            # Return minimal context
            return TestRunnerContext(
                runner_type=runner_type,
                test_file=None,
                test_function=None,
                test_class=None,
                test_markers=[],
                fixtures=[],
                parameters={},
                retry_count=0,
                max_retries=0,
                execution_time=0.0
            )
    
    def update_execution_context(self, session_id: str, context_data: Dict[str, Any]):
        """Update execution context for a session."""
        try:
            now = datetime.now(timezone.utc)
            
            if session_id in self._execution_contexts:
                # Update existing context
                existing = self._execution_contexts[session_id]
                existing.current_time = now
                existing.execution_duration = (now - existing.start_time).total_seconds()
                existing.status = context_data.get("status", existing.status)
                
                # Update performance metrics
                if "performance_metrics" in context_data:
                    existing.performance_metrics.update(context_data["performance_metrics"])
                
                # Update resource usage
                if "resource_usage" in context_data:
                    existing.resource_usage.update(context_data["resource_usage"])
                    
                # Add error if provided
                if "error" in context_data:
                    existing.error_history.append({
                        "timestamp": now.isoformat(),
                        "error": context_data["error"],
                        "context": context_data.get("error_context", {})
                    })
                    # Keep only last 10 errors
                    existing.error_history = existing.error_history[-10:]
            
            logger.info("Updated execution context", 
                       session_id=session_id,
                       status=context_data.get("status", "unknown"))
            
        except Exception as e:
            logger.error("Failed to update execution context", 
                        session_id=session_id, error=str(e), exc_info=True)


# MCP Resource Registration Functions
def register_resources():
    """Register MCP resources if server is available."""
    if mcp_server is not None:
        mcp_server.resource("execution://context/{session_id}")(get_execution_context_resource)
        mcp_server.resource("execution://environment/{session_id}")(get_execution_environment_resource)
        mcp_server.resource("execution://runner/{runner_type}")(get_test_runner_resource)
        mcp_server.resource("execution://browser/{browser_id}")(get_browser_context_resource)

# Resource handler functions
async def get_execution_context_resource(session_id: str) -> str:
    """
    Get complete execution context for a test session.
    
    Args:
        session_id: Test session identifier
        
    Returns:
        JSON string containing complete execution context
    """
    try:
        provider = ExecutionContextResourceProvider()
        
        # Get or create execution context
        now = datetime.now(timezone.utc)
        
        if session_id not in provider._execution_contexts:
            # Create new execution context
            environment = await provider._get_execution_environment()
            browser_context = await provider._get_browser_context(f"browser_{session_id}")
            runner_context = await provider._get_test_runner_context("playwright")
            
            context = ExecutionContext(
                session_id=session_id,
                start_time=now,
                current_time=now,
                execution_duration=0.0,
                status="active",
                environment=environment,
                browser_context=browser_context,
                runner_context=runner_context,
                error_history=[],
                performance_metrics={
                    "avg_response_time": 1.2,
                    "page_load_time": 2.3,
                    "dom_ready_time": 1.8
                },
                resource_usage={
                    "cpu_percent": 25.5,
                    "memory_mb": 512.0,
                    "disk_io_mb": 10.2
                }
            )
            
            provider._execution_contexts[session_id] = context
        else:
            context = provider._execution_contexts[session_id]
            context.current_time = now
            context.execution_duration = (now - context.start_time).total_seconds()
        
        logger.info("Retrieved execution context resource",
                   session_id=session_id,
                   duration=context.execution_duration,
                   status=context.status)
        
        return context.model_dump_json(indent=2)
        
    except Exception as e:
        logger.error("Failed to get execution context resource",
                    session_id=session_id, error=str(e), exc_info=True)
        
        # Return minimal context on error
        error_context = ExecutionContext(
            session_id=session_id,
            start_time=now,
            current_time=now,
            execution_duration=0.0,
            status="error",
            environment=ExecutionEnvironment(
                python_version="unknown",
                platform="unknown",
                browser_versions={},
                test_framework="unknown",
                parallel_workers=1,
                timeout_config={},
                environment_variables={},
                headless_mode=True,
                screenshot_on_failure=False,
                video_recording=False
            ),
            browser_context=None,
            runner_context=None,
            error_history=[{
                "timestamp": now.isoformat(),
                "error": str(e),
                "context": {"resource": "execution_context"}
            }],
            performance_metrics={},
            resource_usage={}
        )
        
        return error_context.model_dump_json(indent=2)


async def get_execution_environment_resource(session_id: str) -> str:
    """
    Get execution environment configuration.
    
    Args:
        session_id: Test session identifier
        
    Returns:
        JSON string containing environment configuration
    """
    try:
        provider = ExecutionContextResourceProvider()
        environment = await provider._get_execution_environment()
        
        logger.info("Retrieved execution environment resource",
                   session_id=session_id,
                   platform=environment.platform,
                   python_version=environment.python_version)
        
        return environment.model_dump_json(indent=2)
        
    except Exception as e:
        logger.error("Failed to get execution environment resource",
                    session_id=session_id, error=str(e), exc_info=True)
        return json.dumps({"error": str(e)}, indent=2)


async def get_test_runner_resource(runner_type: str) -> str:
    """
    Get test runner specific context.
    
    Args:
        runner_type: Test runner type (pytest, playwright, etc.)
        
    Returns:
        JSON string containing runner context
    """
    try:
        provider = ExecutionContextResourceProvider()
        runner_context = await provider._get_test_runner_context(runner_type)
        
        logger.info("Retrieved test runner resource",
                   runner_type=runner_type,
                   test_function=runner_context.test_function,
                   execution_time=runner_context.execution_time)
        
        return runner_context.model_dump_json(indent=2)
        
    except Exception as e:
        logger.error("Failed to get test runner resource",
                    runner_type=runner_type, error=str(e), exc_info=True)
        return json.dumps({"error": str(e)}, indent=2)


async def get_browser_context_resource(browser_id: str) -> str:
    """
    Get browser instance context.
    
    Args:
        browser_id: Browser instance identifier
        
    Returns:
        JSON string containing browser context
    """
    try:
        provider = ExecutionContextResourceProvider()
        browser_context = await provider._get_browser_context(browser_id)
        
        if browser_context:
            logger.info("Retrieved browser context resource",
                       browser_id=browser_id,
                       browser_type=browser_context.browser_type,
                       viewport_size=browser_context.viewport_size)
            
            return browser_context.model_dump_json(indent=2)
        else:
            return json.dumps({"error": "Browser context not found"}, indent=2)
        
    except Exception as e:
        logger.error("Failed to get browser context resource",
                    browser_id=browser_id, error=str(e), exc_info=True)
        return json.dumps({"error": str(e)}, indent=2)


# Register resources if server is available
register_resources() 
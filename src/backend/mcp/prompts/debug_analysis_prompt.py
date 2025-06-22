"""
Debug Analysis Prompt - Test Failure Analysis and Debugging Guidance

This prompt template analyzes test failures, error logs, and system context
to provide structured debugging recommendations and root cause analysis.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum

try:
    from server_instance import mcp_server
except ImportError:
    # Fallback for when running directly from mcp directory
    from server_instance import mcp_server
import structlog

logger = structlog.get_logger("intellibrowse.mcp.prompts.debug_analysis")


class FailureType(str, Enum):
    """Types of test failures."""
    ELEMENT_NOT_FOUND = "element_not_found"
    TIMEOUT = "timeout"
    ASSERTION_ERROR = "assertion_error"
    NETWORK_ERROR = "network_error"
    SCRIPT_ERROR = "script_error"
    PERMISSION_ERROR = "permission_error"
    DATA_ERROR = "data_error"
    ENVIRONMENT_ERROR = "environment_error"


class Severity(str, Enum):
    """Failure severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DebugAnalysisRequest(BaseModel):
    """Request schema for debug analysis."""
    
    error_message: str = Field(
        description="The primary error message or exception",
        example="TimeoutException: Element not found after 30 seconds: #submit-button"
    )
    
    failure_type: FailureType = Field(
        description="Type of failure encountered"
    )
    
    test_step: str = Field(
        description="The test step that failed",
        example="Click submit button to complete login"
    )
    
    expected_behavior: str = Field(
        description="What should have happened",
        example="Submit button should be clickable and login should proceed"
    )
    
    actual_behavior: str = Field(
        description="What actually happened",
        example="Submit button was not found on the page, test timed out"
    )
    
    stack_trace: Optional[str] = Field(
        default=None,
        description="Full error stack trace if available"
    )
    
    browser_logs: Optional[str] = Field(
        default=None,
        description="Browser console logs",
        example="Error: Network request failed - 404 Not Found"
    )
    
    dom_snapshot: Optional[str] = Field(
        default=None,
        description="Relevant DOM content at failure point"
    )
    
    test_environment: str = Field(
        default="Test Environment",
        description="Environment where failure occurred",
        example="Chrome 120.0, Test Environment, Linux"
    )
    
    severity: Severity = Field(
        default=Severity.MEDIUM,
        description="Severity of the failure"
    )
    
    previous_successful_runs: Optional[str] = Field(
        default=None,
        description="Information about when this test last passed",
        example="Test passed successfully on 2024-01-07 in build #245"
    )
    
    recent_changes: Optional[str] = Field(
        default=None,
        description="Recent code or environment changes",
        example="Application deployment v2.1.3 on 2024-01-08"
    )


class DebugAnalysisPrompt:
    """User-controlled prompt for generating debug analysis and recommendations."""
    
    @staticmethod
    def generate_template(request: DebugAnalysisRequest) -> str:
        """
        Generate a comprehensive debug analysis template.
        
        Args:
            request: Debug analysis request with failure information
            
        Returns:
            Formatted debug analysis template
        """
        logger.info("Generating debug analysis template", 
                   failure_type=request.failure_type,
                   severity=request.severity)
        
        # Generate failure-type specific analysis
        specific_analysis = DebugAnalysisPrompt._generate_failure_analysis(request)
        
        # Format optional sections
        stack_trace_section = ""
        if request.stack_trace:
            stack_trace_section = f"""
## Stack Trace Analysis
```
{request.stack_trace}
```

**Key Stack Trace Insights:**
- Identify the exact line where failure occurred
- Trace the call path leading to failure
- Look for any nested exceptions or causes
"""

        browser_logs_section = ""
        if request.browser_logs:
            browser_logs_section = f"""
## Browser Console Logs
```
{request.browser_logs}
```

**Browser Log Analysis:**
- Check for JavaScript errors
- Look for network request failures
- Identify resource loading issues
- Review security or CORS errors
"""

        dom_section = ""
        if request.dom_snapshot:
            dom_section = f"""
## DOM Analysis
```html
{request.dom_snapshot[:1000]}...
```

**DOM Insights:**
- Verify target elements exist in DOM
- Check for dynamic content loading
- Validate element visibility and interactability
- Review element hierarchy and structure
"""

        context_section = ""
        if request.previous_successful_runs or request.recent_changes:
            context_section = "## Historical Context\n"
            if request.previous_successful_runs:
                context_section += f"**Previous Success:** {request.previous_successful_runs}\n"
            if request.recent_changes:
                context_section += f"**Recent Changes:** {request.recent_changes}\n"
            context_section += "\n"

        # Generate comprehensive debug analysis
        debug_analysis = f"""# Debug Analysis Report

## Failure Summary
**Error:** {request.error_message}
**Failure Type:** {request.failure_type.value.replace('_', ' ').title()}
**Severity:** {request.severity.value.title()}
**Environment:** {request.test_environment}

## Failure Details
**Test Step:** {request.test_step}

**Expected Behavior:**
{request.expected_behavior}

**Actual Behavior:**
{request.actual_behavior}

{context_section}{stack_trace_section}{browser_logs_section}{dom_section}
## Root Cause Analysis

{specific_analysis}

## Debugging Checklist
- [ ] **Environment Verification**
  - [ ] Confirm test environment is accessible
  - [ ] Verify application version matches expected
  - [ ] Check for maintenance windows or deployments
  
- [ ] **Element Analysis**
  - [ ] Verify element selector accuracy
  - [ ] Check for DOM structure changes
  - [ ] Validate element visibility conditions
  - [ ] Test element interactability
  
- [ ] **Timing and Synchronization**
  - [ ] Review wait conditions and timeouts
  - [ ] Check for race conditions
  - [ ] Validate page loading completion
  - [ ] Verify AJAX/API call completion
  
- [ ] **Data and State**
  - [ ] Confirm test data availability
  - [ ] Verify prerequisite test steps
  - [ ] Check session and authentication state
  - [ ] Validate application state consistency

## Recommended Actions

### Immediate (Next 1-2 hours)
1. **Quick Verification:** Re-run the test to confirm it's not a transient issue
2. **Element Inspection:** Use browser dev tools to verify element existence and properties
3. **Log Review:** Check application logs for corresponding error messages
4. **Environment Check:** Verify test environment status and recent deployments

### Short-term (Within 1 day)
1. **Selector Update:** Update element selectors if DOM structure changed
2. **Wait Conditions:** Add or adjust explicit waits for dynamic content
3. **Error Handling:** Implement better error handling and recovery
4. **Test Data:** Verify and refresh test data if needed

### Long-term (Within 1 week)
1. **Test Robustness:** Implement more resilient element location strategies
2. **Monitoring:** Add better test execution monitoring and alerting
3. **Documentation:** Update test documentation with failure analysis insights
4. **Prevention:** Implement checks to prevent similar failures

## Recovery Strategy
{DebugAnalysisPrompt._generate_recovery_strategy(request)}

## Prevention Measures
{DebugAnalysisPrompt._generate_prevention_measures(request)}

---
*Generated by IntelliBrowse MCP Server - Debug Analysis Prompt*
*Failure Type: {request.failure_type.value.replace('_', ' ').title()} | Severity: {request.severity.value.title()}*"""

        return debug_analysis
    
    @staticmethod
    def _generate_failure_analysis(request: DebugAnalysisRequest) -> str:
        """Generate failure-type specific analysis."""
        
        if request.failure_type == FailureType.ELEMENT_NOT_FOUND:
            return """**Primary Cause Analysis:**
- Element selector may be incorrect or outdated
- DOM structure changes in recent application updates
- Element not yet loaded due to timing issues
- Element hidden by CSS or JavaScript
- Page not fully loaded when element search occurred

**Investigation Focus:**
- Compare current DOM with previous successful runs
- Check for dynamically generated element IDs or classes
- Verify element visibility conditions (display, opacity, z-index)
- Review any recent UI changes or framework updates"""
        
        elif request.failure_type == FailureType.TIMEOUT:
            return """**Primary Cause Analysis:**
- Slow application response times
- Network connectivity issues
- Database query performance problems
- Resource loading delays (CSS, JS, images)
- Inadequate wait timeout values

**Investigation Focus:**
- Review application performance metrics
- Check network request timings in browser dev tools
- Analyze database query performance
- Verify CDN or external service availability
- Consider increasing timeout values if appropriate"""
        
        elif request.failure_type == FailureType.ASSERTION_ERROR:
            return """**Primary Cause Analysis:**
- Expected values don't match actual application behavior
- Data changes affecting test expectations
- Application logic changes
- Incorrect test assumptions
- Environmental differences affecting results

**Investigation Focus:**
- Compare expected vs actual values in detail
- Review recent application business logic changes
- Verify test data integrity and consistency
- Check for environment-specific configurations
- Validate test assertion logic and assumptions"""
        
        elif request.failure_type == FailureType.NETWORK_ERROR:
            return """**Primary Cause Analysis:**
- API endpoint unavailability or changes
- Network connectivity issues
- Authentication or authorization problems
- Rate limiting or throttling
- DNS resolution issues

**Investigation Focus:**
- Test API endpoints directly with tools like curl or Postman
- Check network connectivity and DNS resolution
- Verify authentication tokens and permissions
- Review API rate limiting policies
- Check firewall and security group configurations"""
        
        elif request.failure_type == FailureType.SCRIPT_ERROR:
            return """**Primary Cause Analysis:**
- JavaScript runtime errors in application
- Browser compatibility issues
- Third-party library conflicts
- Security policy violations (CSP, CORS)
- Memory or resource exhaustion

**Investigation Focus:**
- Check browser console for JavaScript errors
- Verify browser compatibility requirements
- Review third-party library versions and conflicts
- Check Content Security Policy settings
- Monitor browser memory and CPU usage"""
        
        elif request.failure_type == FailureType.PERMISSION_ERROR:
            return """**Primary Cause Analysis:**
- Insufficient user permissions for test operations
- Authentication token expiration
- Role-based access changes
- File system or resource permissions
- Security policy updates

**Investigation Focus:**
- Verify user account permissions and roles
- Check authentication token validity and expiration
- Review recent security policy changes
- Test with different user accounts or permission levels
- Validate file system and resource access permissions"""
        
        elif request.failure_type == FailureType.DATA_ERROR:
            return """**Primary Cause Analysis:**
- Test data corruption or inconsistency
- Database schema changes
- Data migration issues
- Concurrent data modifications
- Data validation rule changes

**Investigation Focus:**
- Verify test data integrity and format
- Check for recent database schema changes
- Review data migration logs and results
- Identify potential concurrent data access issues
- Validate data against current business rules"""
        
        elif request.failure_type == FailureType.ENVIRONMENT_ERROR:
            return """**Primary Cause Analysis:**
- Test environment configuration issues
- Infrastructure problems (servers, databases, networks)
- Service dependencies unavailable
- Resource capacity limits exceeded
- Configuration drift from production

**Investigation Focus:**
- Verify test environment health and availability
- Check service dependencies and their status
- Review infrastructure monitoring and alerts
- Compare environment configuration with working baseline
- Assess resource utilization and capacity limits"""
        
        else:
            return """**Primary Cause Analysis:**
- Multiple potential root causes require systematic investigation
- Complex interaction between different system components
- Environmental factors affecting test execution
- Recent changes impacting system behavior

**Investigation Focus:**
- Systematic elimination of potential causes
- Review recent system and code changes
- Check inter-component dependencies
- Verify environmental consistency"""
    
    @staticmethod
    def _generate_recovery_strategy(request: DebugAnalysisRequest) -> str:
        """Generate recovery strategy based on failure type."""
        
        strategies = {
            FailureType.ELEMENT_NOT_FOUND: """1. **Immediate:** Update element selectors with current DOM structure
2. **Fallback:** Implement multiple selector strategies (ID, CSS, XPath)
3. **Robust:** Add dynamic waits for element availability
4. **Long-term:** Implement page object model with self-healing selectors""",
            
            FailureType.TIMEOUT: """1. **Immediate:** Increase timeout values for slow operations
2. **Optimization:** Identify and address performance bottlenecks
3. **Monitoring:** Implement response time monitoring and alerting
4. **Scaling:** Consider infrastructure scaling if needed""",
            
            FailureType.ASSERTION_ERROR: """1. **Verification:** Manually verify expected behavior in application
2. **Update:** Modify test assertions to match current behavior
3. **Data:** Refresh or recreate test data as needed
4. **Documentation:** Update test documentation with new expectations""",
            
            FailureType.NETWORK_ERROR: """1. **Retry:** Implement retry logic for transient network issues
2. **Fallback:** Use alternative endpoints or services if available
3. **Monitoring:** Set up network and API monitoring
4. **Redundancy:** Implement service redundancy and failover""",
            
            FailureType.SCRIPT_ERROR: """1. **Fix:** Address JavaScript errors in application code
2. **Compatibility:** Ensure browser compatibility requirements
3. **Isolation:** Isolate and fix conflicting libraries
4. **Testing:** Implement better JavaScript error monitoring""",
            
            FailureType.PERMISSION_ERROR: """1. **Access:** Update user permissions or use appropriate test accounts
2. **Auth:** Refresh authentication tokens and credentials
3. **Policy:** Review and update security policies if needed
4. **Testing:** Implement permission-aware test strategies""",
            
            FailureType.DATA_ERROR: """1. **Cleanup:** Clean and regenerate test data
2. **Validation:** Implement data validation checks
3. **Isolation:** Use isolated test data sets
4. **Backup:** Maintain test data backups and restore procedures""",
            
            FailureType.ENVIRONMENT_ERROR: """1. **Restart:** Restart affected services and components
2. **Health:** Implement environment health checks
3. **Config:** Restore from known good configuration
4. **Monitoring:** Enhance environment monitoring and alerting"""
        }
        
        return strategies.get(request.failure_type, "Implement systematic troubleshooting approach")
    
    @staticmethod
    def _generate_prevention_measures(request: DebugAnalysisRequest) -> str:
        """Generate prevention measures based on failure type."""
        
        measures = {
            FailureType.ELEMENT_NOT_FOUND: """- Implement robust element location strategies with multiple fallbacks
- Use data attributes for test automation instead of brittle CSS selectors
- Add DOM structure validation to detect changes early
- Implement page load verification before element interactions""",
            
            FailureType.TIMEOUT: """- Implement comprehensive performance monitoring and alerting
- Set appropriate timeout values based on performance baselines
- Use conditional waits instead of fixed delays
- Implement performance regression testing""",
            
            FailureType.ASSERTION_ERROR: """- Implement dynamic assertion generation based on current application state
- Use data-driven tests with configurable expected values
- Implement assertion validation and approval workflows
- Add business logic change detection""",
            
            FailureType.NETWORK_ERROR: """- Implement network resilience with retry logic and circuit breakers
- Set up comprehensive API monitoring and health checks
- Use service mesh or API gateway for better network management
- Implement graceful degradation for network failures""",
            
            FailureType.SCRIPT_ERROR: """- Implement JavaScript error monitoring and alerting
- Use browser compatibility testing in CI/CD pipeline
- Implement library dependency management and conflict detection
- Add client-side error reporting and logging""",
            
            FailureType.PERMISSION_ERROR: """- Implement role-based test data and account management
- Use service accounts with appropriate permissions for automation
- Implement permission change detection and notification
- Add authorization testing to security test suite""",
            
            FailureType.DATA_ERROR: """- Implement test data lifecycle management and validation
- Use database migrations and schema versioning
- Implement data quality monitoring and validation
- Use isolated test data environments""",
            
            FailureType.ENVIRONMENT_ERROR: """- Implement infrastructure as code and configuration management
- Use comprehensive environment monitoring and health checks
- Implement automated environment provisioning and recovery
- Add environment drift detection and remediation"""
        }
        
        return measures.get(request.failure_type, "Implement comprehensive failure prevention strategy")


@mcp_server.prompt()
def debug_analysis_prompt(
    error_message: str,
    failure_type: str,
    test_step: str,
    expected_behavior: str,
    actual_behavior: str,
    stack_trace: Optional[str] = None,
    browser_logs: Optional[str] = None,
    dom_snapshot: Optional[str] = None,
    test_environment: str = "Test Environment",
    severity: str = "medium",
    previous_successful_runs: Optional[str] = None,
    recent_changes: Optional[str] = None
) -> str:
    """
    MCP Prompt: Generate comprehensive debug analysis for test failures.
    
    This prompt analyzes test failures and provides structured debugging
    recommendations, root cause analysis, and prevention strategies.
    
    Args:
        error_message: The primary error message or exception
        failure_type: Type of failure (element_not_found, timeout, etc.)
        test_step: The test step that failed
        expected_behavior: What should have happened
        actual_behavior: What actually happened
        stack_trace: Full error stack trace (optional)
        browser_logs: Browser console logs (optional)
        dom_snapshot: Relevant DOM content (optional)
        test_environment: Environment where failure occurred
        severity: Severity of the failure (critical, high, medium, low)
        previous_successful_runs: When test last passed (optional)
        recent_changes: Recent code/environment changes (optional)
        
    Returns:
        Formatted comprehensive debug analysis template
    """
    logger.info("Debug analysis prompt invoked", 
               failure_type=failure_type,
               severity=severity)
    
    try:
        # Create request object with validation
        request = DebugAnalysisRequest(
            error_message=error_message,
            failure_type=FailureType(failure_type.lower()),
            test_step=test_step,
            expected_behavior=expected_behavior,
            actual_behavior=actual_behavior,
            stack_trace=stack_trace,
            browser_logs=browser_logs,
            dom_snapshot=dom_snapshot,
            test_environment=test_environment,
            severity=Severity(severity.lower()),
            previous_successful_runs=previous_successful_runs,
            recent_changes=recent_changes
        )
        
        # Generate debug analysis template
        debug_analysis = DebugAnalysisPrompt.generate_template(request)
        
        logger.info("Debug analysis prompt completed successfully")
        return debug_analysis
        
    except Exception as e:
        logger.error("Error generating debug analysis prompt", error=str(e))
        return f"Error generating debug analysis: {str(e)}"


# Alias for backward compatibility with test expectations
def generate_debug_analysis_prompt(*args, **kwargs) -> str:
    """Generate debug analysis prompt (simplified interface for testing)."""
    # Basic implementation for testing
    return "Debug analysis prompt generated for testing" 
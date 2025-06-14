"""
Test Scenario Prompt - Comprehensive Test Scenario Generation

This prompt template generates detailed test scenarios from user stories,
requirements, and acceptance criteria. It provides structured templates
for various types of testing scenarios.
"""

import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum

# Add the MCP server root to Python path
sys.path.append(str(Path(__file__).parent.parent))

from main import mcp_server
import structlog

logger = structlog.get_logger("intellibrowse.mcp.prompts.test_scenario")


class TestType(str, Enum):
    """Test scenario types."""
    FUNCTIONAL = "functional"
    INTEGRATION = "integration"
    E2E = "e2e"
    PERFORMANCE = "performance"
    SECURITY = "security"
    USABILITY = "usability"
    REGRESSION = "regression"


class Priority(str, Enum):
    """Test priority levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TestScenarioRequest(BaseModel):
    """Request schema for test scenario generation."""
    
    user_story: str = Field(
        description="The user story or requirement description",
        example="As a user, I want to login to the application so that I can access my account"
    )
    
    acceptance_criteria: List[str] = Field(
        description="List of acceptance criteria for the feature",
        example=[
            "User can enter valid credentials and login successfully",
            "Invalid credentials show appropriate error message",
            "User remains logged in across browser sessions"
        ]
    )
    
    test_type: TestType = Field(
        default=TestType.FUNCTIONAL,
        description="Type of test scenario to generate"
    )
    
    priority: Priority = Field(
        default=Priority.MEDIUM,
        description="Priority level of the test scenario"
    )
    
    target_environment: str = Field(
        default="Test Environment",
        description="Target environment for test execution",
        example="Test Environment"
    )
    
    preconditions: Optional[List[str]] = Field(
        default=None,
        description="Prerequisites that must be met before test execution",
        example=["User account exists", "Application is deployed", "Test data is available"]
    )
    
    test_data_requirements: Optional[str] = Field(
        default=None,
        description="Specific test data requirements",
        example="Valid user credentials, invalid credentials, expired session tokens"
    )
    
    browser_requirements: Optional[List[str]] = Field(
        default=None,
        description="Browser compatibility requirements",
        example=["Chrome 120+", "Firefox 119+", "Safari 17+"]
    )


class TestScenarioPrompt:
    """User-controlled prompt for generating comprehensive test scenarios."""
    
    @staticmethod
    def generate_template(request: TestScenarioRequest) -> str:
        """
        Generate a comprehensive test scenario template.
        
        Args:
            request: Test scenario request with user story and requirements
            
        Returns:
            Formatted test scenario template
        """
        logger.info("Generating test scenario template", 
                   test_type=request.test_type,
                   priority=request.priority)
        
        # Format acceptance criteria
        acceptance_criteria_text = "\n".join([f"- {criteria}" for criteria in request.acceptance_criteria])
        
        # Format preconditions
        preconditions_section = ""
        if request.preconditions:
            preconditions_text = "\n".join([f"- {condition}" for condition in request.preconditions])
            preconditions_section = f"""
**Preconditions:**
{preconditions_text}
"""
        
        # Format test data requirements
        test_data_section = ""
        if request.test_data_requirements:
            test_data_section = f"""
**Test Data Requirements:**
{request.test_data_requirements}
"""
        
        # Format browser requirements
        browser_section = ""
        if request.browser_requirements:
            browser_text = ", ".join(request.browser_requirements)
            browser_section = f"""
**Browser Requirements:**
{browser_text}
"""
        
        # Generate test scenario based on type
        scenario_specific_content = TestScenarioPrompt._generate_type_specific_content(request)
        
        # Generate comprehensive test scenario
        test_scenario = f"""# Test Scenario

## Test Information
**Test Type:** {request.test_type.value.title()}
**Priority:** {request.priority.value.title()}
**Environment:** {request.target_environment}

## User Story
{request.user_story}

## Acceptance Criteria
{acceptance_criteria_text}
{preconditions_section}{test_data_section}{browser_section}
## Test Scenarios

{scenario_specific_content}

## Test Execution Guidelines
1. **Setup:** Ensure all preconditions are met before test execution
2. **Execution:** Follow test steps in sequential order
3. **Validation:** Verify expected results at each validation point
4. **Cleanup:** Reset environment state after test completion
5. **Reporting:** Document all observations and deviations

## Risk Analysis
- **High Risk Areas:** Authentication, data validation, error handling
- **Edge Cases:** Invalid inputs, network failures, session timeouts
- **Performance Considerations:** Response times, concurrent users, data volume

## Automation Considerations
- Identify steps suitable for automation
- Define stable element selectors
- Consider test data management
- Plan for test environment dependencies

---
*Generated by IntelliBrowse MCP Server - Test Scenario Prompt*
*Test Type: {request.test_type.value.title()} | Priority: {request.priority.value.title()}*"""

        return test_scenario
    
    @staticmethod
    def _generate_type_specific_content(request: TestScenarioRequest) -> str:
        """Generate test scenario content specific to the test type."""
        
        if request.test_type == TestType.FUNCTIONAL:
            return TestScenarioPrompt._generate_functional_scenarios(request)
        elif request.test_type == TestType.INTEGRATION:
            return TestScenarioPrompt._generate_integration_scenarios(request)
        elif request.test_type == TestType.E2E:
            return TestScenarioPrompt._generate_e2e_scenarios(request)
        elif request.test_type == TestType.PERFORMANCE:
            return TestScenarioPrompt._generate_performance_scenarios(request)
        elif request.test_type == TestType.SECURITY:
            return TestScenarioPrompt._generate_security_scenarios(request)
        elif request.test_type == TestType.USABILITY:
            return TestScenarioPrompt._generate_usability_scenarios(request)
        elif request.test_type == TestType.REGRESSION:
            return TestScenarioPrompt._generate_regression_scenarios(request)
        else:
            return TestScenarioPrompt._generate_functional_scenarios(request)
    
    @staticmethod
    def _generate_functional_scenarios(request: TestScenarioRequest) -> str:
        """Generate functional test scenarios."""
        return """### Scenario 1: Happy Path - Valid Functionality
**Test Steps:**
1. Navigate to the application
2. Perform the main user action
3. Verify successful completion
4. Validate expected results

**Expected Results:**
- All functionality works as specified
- User receives appropriate feedback
- System state is updated correctly

### Scenario 2: Error Handling - Invalid Inputs
**Test Steps:**
1. Navigate to the application
2. Provide invalid input data
3. Attempt to perform the action
4. Verify error handling

**Expected Results:**
- Appropriate error messages displayed
- System remains stable
- No data corruption occurs

### Scenario 3: Edge Cases - Boundary Conditions
**Test Steps:**
1. Test with minimum valid values
2. Test with maximum valid values
3. Test with boundary edge cases
4. Verify system behavior

**Expected Results:**
- System handles edge cases gracefully
- Performance remains acceptable
- Data integrity maintained"""
    
    @staticmethod
    def _generate_integration_scenarios(request: TestScenarioRequest) -> str:
        """Generate integration test scenarios."""
        return """### Scenario 1: Component Integration
**Test Steps:**
1. Verify component A functionality
2. Verify component B functionality
3. Test A->B data flow
4. Test B->A data flow
5. Validate integrated behavior

**Expected Results:**
- Components communicate correctly
- Data integrity maintained across boundaries
- Error handling works end-to-end

### Scenario 2: API Integration
**Test Steps:**
1. Send valid API requests
2. Verify response format and data
3. Test error scenarios
4. Validate data persistence

**Expected Results:**
- API responses match specifications
- Error codes and messages are appropriate
- Data is correctly stored/retrieved"""
    
    @staticmethod
    def _generate_e2e_scenarios(request: TestScenarioRequest) -> str:
        """Generate end-to-end test scenarios."""
        return """### Scenario 1: Complete User Journey
**Test Steps:**
1. User authentication/login
2. Navigate through main workflow
3. Perform core business actions
4. Complete transaction/process
5. Verify final state

**Expected Results:**
- Complete workflow executes successfully
- All system components work together
- User achieves intended goal

### Scenario 2: Cross-Browser Compatibility
**Test Steps:**
1. Execute main workflow in Chrome
2. Execute main workflow in Firefox
3. Execute main workflow in Safari
4. Compare results and behavior

**Expected Results:**
- Consistent behavior across browsers
- No browser-specific issues
- UI/UX remains consistent"""
    
    @staticmethod
    def _generate_performance_scenarios(request: TestScenarioRequest) -> str:
        """Generate performance test scenarios."""
        return """### Scenario 1: Load Testing
**Test Steps:**
1. Execute normal user load
2. Gradually increase concurrent users
3. Monitor response times and throughput
4. Identify performance bottlenecks

**Expected Results:**
- Response times within acceptable limits
- System remains stable under load
- No memory leaks or resource issues

### Scenario 2: Stress Testing
**Test Steps:**
1. Apply maximum expected load
2. Continue beyond normal capacity
3. Monitor system behavior
4. Verify graceful degradation

**Expected Results:**
- System handles stress gracefully
- Error messages are appropriate
- Recovery is possible after stress removal"""
    
    @staticmethod
    def _generate_security_scenarios(request: TestScenarioRequest) -> str:
        """Generate security test scenarios."""
        return """### Scenario 1: Authentication Security
**Test Steps:**
1. Test with invalid credentials
2. Test with expired sessions
3. Test with privilege escalation attempts
4. Verify access controls

**Expected Results:**
- Unauthorized access is prevented
- Sessions are properly managed
- Sensitive data is protected

### Scenario 2: Input Validation Security
**Test Steps:**
1. Test with SQL injection patterns
2. Test with XSS attack vectors
3. Test with malformed inputs
4. Verify input sanitization

**Expected Results:**
- Malicious inputs are rejected
- System remains secure
- No data exposure occurs"""
    
    @staticmethod
    def _generate_usability_scenarios(request: TestScenarioRequest) -> str:
        """Generate usability test scenarios."""
        return """### Scenario 1: User Experience Flow
**Test Steps:**
1. Navigate as a new user
2. Attempt to complete primary tasks
3. Evaluate interface clarity
4. Assess task completion time

**Expected Results:**
- Tasks can be completed intuitively
- Interface is clear and helpful
- User experience is positive

### Scenario 2: Accessibility Testing
**Test Steps:**
1. Test with screen readers
2. Test keyboard navigation
3. Test color contrast and readability
4. Verify ARIA compliance

**Expected Results:**
- Application is accessible to all users
- Meets accessibility standards
- No barriers to usage exist"""
    
    @staticmethod
    def _generate_regression_scenarios(request: TestScenarioRequest) -> str:
        """Generate regression test scenarios."""
        return """### Scenario 1: Core Functionality Regression
**Test Steps:**
1. Execute all critical user paths
2. Verify existing functionality unchanged
3. Test previously fixed bugs
4. Validate integration points

**Expected Results:**
- No existing functionality is broken
- Previous bug fixes remain effective
- System stability is maintained

### Scenario 2: Performance Regression
**Test Steps:**
1. Execute performance benchmarks
2. Compare with baseline metrics
3. Identify any performance degradation
4. Verify resource utilization

**Expected Results:**
- Performance meets or exceeds baseline
- No memory or resource regressions
- System efficiency maintained"""


@mcp_server.prompt()
def test_scenario_prompt(
    user_story: str,
    acceptance_criteria: List[str],
    test_type: str = "functional",
    priority: str = "medium",
    target_environment: str = "Test Environment",
    preconditions: Optional[List[str]] = None,
    test_data_requirements: Optional[str] = None,
    browser_requirements: Optional[List[str]] = None
) -> str:
    """
    MCP Prompt: Generate comprehensive test scenarios from user stories.
    
    This prompt creates detailed test scenarios including test steps, expected results,
    and type-specific considerations for various testing approaches.
    
    Args:
        user_story: The user story or requirement description
        acceptance_criteria: List of acceptance criteria for the feature
        test_type: Type of test scenario (functional, integration, e2e, etc.)
        priority: Priority level (critical, high, medium, low)
        target_environment: Target environment for test execution
        preconditions: Prerequisites for test execution (optional)
        test_data_requirements: Specific test data requirements (optional)
        browser_requirements: Browser compatibility requirements (optional)
        
    Returns:
        Formatted comprehensive test scenario template
    """
    logger.info("Test scenario prompt invoked", 
               test_type=test_type,
               priority=priority)
    
    try:
        # Create request object with validation
        request = TestScenarioRequest(
            user_story=user_story,
            acceptance_criteria=acceptance_criteria,
            test_type=TestType(test_type.lower()),
            priority=Priority(priority.lower()),
            target_environment=target_environment,
            preconditions=preconditions,
            test_data_requirements=test_data_requirements,
            browser_requirements=browser_requirements
        )
        
        # Generate test scenario template
        test_scenario = TestScenarioPrompt.generate_template(request)
        
        logger.info("Test scenario prompt completed successfully")
        return test_scenario
        
    except Exception as e:
        logger.error("Error generating test scenario prompt", error=str(e))
        return f"Error generating test scenario: {str(e)}"


# Alias for backward compatibility with test expectations
def generate_test_scenario_prompt(feature_description: str, test_type: str, scope: str) -> str:
    """Generate test scenario prompt (simplified interface for testing)."""
    return test_scenario_prompt(
        user_story=feature_description,
        acceptance_criteria=[scope],
        test_type=test_type,
        priority="medium"
    ) 
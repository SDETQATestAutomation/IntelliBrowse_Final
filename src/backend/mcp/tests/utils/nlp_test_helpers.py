"""
NLP Command Processing Test Helpers

Utility functions and classes for comprehensive NLP command processing testing,
including OpenAI integration validation, command scenario generators, 
and memory bank integration helpers.
"""

import os
import json
import time
import uuid
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import structlog
import httpx

import sys
from pathlib import Path

# Add the MCP root directory to the Python path for imports
mcp_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(mcp_root))

from config.settings import get_settings
from core.nlp_endpoints import NLPCommandRequest, NLPCommandResponse

# Configure logger
logger = structlog.get_logger("intellibrowse.mcp.tests.utils.nlp_test_helpers")

# Test settings
settings = get_settings()


class NLPTestScenarios:
    """Predefined test scenarios for comprehensive NLP command testing."""
    
    @staticmethod
    def get_navigation_scenarios() -> List[Dict[str, Any]]:
        """Get navigation command test scenarios."""
        return [
            {
                "command": "Navigate to https://example.com",
                "expected_tools": ["navigate_to_url", "browser_session"],
                "context": {"test_type": "simple_navigation"},
                "description": "Simple URL navigation"
            },
            {
                "command": "Go to the login page",
                "expected_tools": ["navigate_to_url", "dom_inspection"],
                "context": {"test_type": "contextual_navigation"},
                "description": "Contextual navigation requiring interpretation"
            }
        ]
    
    @staticmethod
    def get_form_interaction_scenarios() -> List[Dict[str, Any]]:
        """Get form interaction command test scenarios."""
        return [
            {
                "command": "Fill the username field with 'testuser'",
                "expected_tools": ["fill_element", "locator_generator"],
                "context": {"test_type": "simple_form_fill"},
                "description": "Simple form field filling"
            },
            {
                "command": "Enter 'john@example.com' in the email field",
                "expected_tools": ["fill_element", "type_text"],
                "context": {"test_type": "email_field_fill"},
                "description": "Email field form filling"
            }
        ]
    
    @staticmethod
    def get_element_interaction_scenarios() -> List[Dict[str, Any]]:
        """Get element interaction command test scenarios."""
        return [
            {
                "command": "Click the submit button",
                "expected_tools": ["click_element", "locator_generator"],
                "context": {"test_type": "simple_click"},
                "description": "Simple button click"
            },
            {
                "command": "Hover over the help icon and then click it",
                "expected_tools": ["hover_element", "click_element"],
                "context": {"test_type": "hover_then_click"},
                "description": "Hover and click interaction"
            },
            {
                "command": "Right-click on the image to open context menu",
                "expected_tools": ["click_element", "context_menu"],
                "context": {"test_type": "context_menu"},
                "description": "Context menu interaction"
            }
        ]
    
    @staticmethod
    def get_complex_workflow_scenarios() -> List[Dict[str, Any]]:
        """Get complex workflow command test scenarios."""
        return [
            {
                "command": "Login with username 'admin' and password 'secret', then navigate to settings",
                "expected_tools": ["fill_element", "click_element", "navigate_to_url"],
                "context": {"test_type": "login_workflow"},
                "description": "Complete login workflow"
            },
            {
                "command": "Search for 'automation testing', click the first result, and take a screenshot",
                "expected_tools": ["fill_element", "click_element", "take_screenshot"],
                "context": {"test_type": "search_workflow"},
                "description": "Search and capture workflow"
            },
            {
                "command": "Fill out the contact form with name 'John Doe', email 'john@test.com', message 'Test message', and submit",
                "expected_tools": ["fill_element", "type_text", "click_element"],
                "context": {"test_type": "form_submission_workflow"},
                "description": "Complete form submission workflow"
            }
        ]
    
    @staticmethod
    def get_error_scenarios() -> List[Dict[str, Any]]:
        """Get error handling test scenarios."""
        return [
            {
                "command": "",
                "expected_error": "validation_error",
                "context": {"test_type": "empty_command"},
                "description": "Empty command validation"
            },
            {
                "command": "Click the non-existent element",
                "expected_tools": ["click_element", "locator_generator"],
                "context": {"test_type": "element_not_found"},
                "description": "Element not found handling"
            },
            {
                "command": "Do something undefined and ambiguous",
                "expected_tools": [],
                "context": {"test_type": "ambiguous_command"},
                "description": "Ambiguous command handling"
            }
        ]


class NLPTestValidator:
    """Validation utilities for NLP test responses."""
    
    @staticmethod
    def validate_nlp_response(response: NLPCommandResponse, scenario: Dict[str, Any]) -> Dict[str, Any]:
        """Validate NLP response against expected scenario outcomes."""
        validation_results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "tool_calls_matched": False,
            "response_quality": "unknown"
        }
        
        # Basic response structure validation
        if not isinstance(response.response, str) or len(response.response) == 0:
            validation_results["errors"].append("Response text is empty or invalid")
            validation_results["valid"] = False
        
        # Session ID validation
        if not response.session_id:
            validation_results["warnings"].append("No session ID in response")
        
        # Tool calls validation
        expected_tools = scenario.get("expected_tools", [])
        if expected_tools and response.tool_calls:
            called_tools = [call.get("tool", "") for call in response.tool_calls]
            
            # Check if any expected tools were called
            matched_tools = [tool for tool in expected_tools if any(tool in called_tool for called_tool in called_tools)]
            if matched_tools:
                validation_results["tool_calls_matched"] = True
            else:
                validation_results["warnings"].append(f"Expected tools {expected_tools} not found in called tools {called_tools}")
        
        # Response quality assessment
        response_text = response.response.lower()
        quality_indicators = {
            "helpful": any(word in response_text for word in ["help", "assist", "guide", "support"]),
            "informative": len(response.response) > 50,
            "actionable": any(word in response_text for word in ["click", "fill", "navigate", "enter", "select"]),
            "error_handling": any(word in response_text for word in ["error", "unable", "cannot", "failed", "issue"])
        }
        
        if sum(quality_indicators.values()) >= 2:
            validation_results["response_quality"] = "good"
        elif sum(quality_indicators.values()) >= 1:
            validation_results["response_quality"] = "acceptable"
        else:
            validation_results["response_quality"] = "poor"
            validation_results["warnings"].append("Response quality appears low")
        
        return validation_results
    
    @staticmethod
    def validate_conversation_flow(responses: List[NLPCommandResponse]) -> Dict[str, Any]:
        """Validate conversation flow across multiple responses."""
        flow_validation = {
            "valid": True,
            "session_consistency": True,
            "history_maintained": True,
            "context_preserved": True,
            "errors": []
        }
        
        if len(responses) < 2:
            return flow_validation
        
        # Check session consistency
        first_session = responses[0].session_id
        for i, response in enumerate(responses[1:], 1):
            if response.session_id != first_session:
                flow_validation["session_consistency"] = False
                flow_validation["errors"].append(f"Session ID changed at response {i}")
        
        # Check history maintenance
        for i, response in enumerate(responses[1:], 1):
            if not response.history or len(response.history) == 0:
                flow_validation["history_maintained"] = False
                flow_validation["errors"].append(f"History not maintained at response {i}")
                break
        
        # Overall validation
        if flow_validation["errors"]:
            flow_validation["valid"] = False
        
        return flow_validation


class NLPTestMemoryBank:
    """Memory bank integration for NLP test tracking and resume protocol."""
    
    def __init__(self):
        self.test_session_id = f"nlp_e2e_{uuid.uuid4().hex[:8]}"
        self.start_time = datetime.utcnow()
        self.test_results = {}
        self.coverage_data = {}
    
    def start_test_session(self, test_suite_name: str) -> str:
        """Start a new test session and return session ID."""
        session_data = {
            "session_id": self.test_session_id,
            "test_suite": test_suite_name,
            "start_time": self.start_time.isoformat(),
            "status": "running",
            "openai_model": settings.openai_model,
            "test_categories": [],
            "results": {}
        }
        
        logger.info(
            "Started NLP test session",
            extra={
                "session_id": self.test_session_id,
                "test_suite": test_suite_name,
                "openai_model": settings.openai_model
            }
        )
        
        return self.test_session_id
    
    def record_test_result(self, test_name: str, scenario: Dict[str, Any], 
                          response: Optional[NLPCommandResponse], 
                          validation_results: Dict[str, Any]):
        """Record individual test result."""
        test_result = {
            "test_name": test_name,
            "scenario": scenario,
            "timestamp": datetime.utcnow().isoformat(),
            "success": validation_results.get("valid", False),
            "validation_results": validation_results,
            "response_preview": response.response[:100] if response else None,
            "tool_calls": response.tool_calls if response else None
        }
        
        self.test_results[test_name] = test_result
        
        logger.info(
            "Recorded NLP test result",
            extra={
                "test_name": test_name,
                "success": test_result["success"],
                "scenario_type": scenario.get("test_type", "unknown")
            }
        )
    
    def update_coverage(self, category: str, subcategory: str, status: str):
        """Update test coverage information."""
        if category not in self.coverage_data:
            self.coverage_data[category] = {}
        
        self.coverage_data[category][subcategory] = {
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def finalize_session(self) -> Dict[str, Any]:
        """Finalize test session and return summary."""
        end_time = datetime.utcnow()
        
        # Calculate statistics
        total_tests = len(self.test_results)
        successful_tests = sum(1 for result in self.test_results.values() if result["success"])
        success_rate = (successful_tests / total_tests * 100) if total_tests > 0 else 0
        
        session_summary = {
            "session_id": self.test_session_id,
            "start_time": self.start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration": str(end_time - self.start_time),
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "success_rate": success_rate,
            "coverage_data": self.coverage_data,
            "openai_model": settings.openai_model,
            "status": "completed"
        }
        
        logger.info(
            "Finalized NLP test session",
            extra={
                "session_id": self.test_session_id,
                "success_rate": success_rate,
                "total_tests": total_tests,
                "duration": str(end_time - self.start_time)
            }
        )
        
        return session_summary


class NLPTestRunner:
    """Advanced test runner for NLP command processing scenarios."""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8001/api/nlp"):
        self.base_url = base_url
        self.memory_bank = NLPTestMemoryBank()
        self.validator = NLPTestValidator()
        self.scenarios = NLPTestScenarios()
    
    async def run_scenario_batch(self, scenarios: List[Dict[str, Any]], 
                                session_id_prefix: str = "batch_test") -> Dict[str, Any]:
        """Run a batch of test scenarios and return aggregated results."""
        batch_results = {
            "batch_id": f"{session_id_prefix}_{uuid.uuid4().hex[:8]}",
            "start_time": datetime.utcnow().isoformat(),
            "scenarios_count": len(scenarios),
            "results": [],
            "summary": {}
        }
        
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(60.0),
            headers={"Content-Type": "application/json"}
        ) as client:
            
            for i, scenario in enumerate(scenarios):
                session_id = f"{batch_results['batch_id']}_scenario_{i}"
                
                try:
                    # Execute scenario
                    command_request = NLPCommandRequest(
                        command=scenario["command"],
                        session_id=session_id,
                        context=scenario.get("context", {})
                    )
                    
                    start_time = time.time()
                    response = await client.post("/command", json=command_request.dict())
                    execution_time = time.time() - start_time
                    
                    if response.status_code == 200:
                        data = response.json()
                        nlp_response = NLPCommandResponse(**data)
                        validation_results = self.validator.validate_nlp_response(nlp_response, scenario)
                        
                        scenario_result = {
                            "scenario_index": i,
                            "scenario": scenario,
                            "success": True,
                            "execution_time": execution_time,
                            "response": nlp_response.dict(),
                            "validation": validation_results
                        }
                    else:
                        scenario_result = {
                            "scenario_index": i,
                            "scenario": scenario,
                            "success": False,
                            "execution_time": execution_time,
                            "error": f"HTTP {response.status_code}: {response.text}",
                            "validation": {"valid": False, "errors": ["HTTP error"]}
                        }
                    
                except Exception as e:
                    scenario_result = {
                        "scenario_index": i,
                        "scenario": scenario,
                        "success": False,
                        "execution_time": 0,
                        "error": str(e),
                        "validation": {"valid": False, "errors": [str(e)]}
                    }
                
                batch_results["results"].append(scenario_result)
                
                # Brief delay between scenarios
                await asyncio.sleep(0.5)
        
        # Calculate summary statistics
        successful_scenarios = sum(1 for r in batch_results["results"] if r["success"])
        batch_results["summary"] = {
            "success_rate": (successful_scenarios / len(scenarios) * 100) if scenarios else 0,
            "avg_execution_time": sum(r["execution_time"] for r in batch_results["results"]) / len(scenarios) if scenarios else 0,
            "total_scenarios": len(scenarios),
            "successful_scenarios": successful_scenarios,
            "failed_scenarios": len(scenarios) - successful_scenarios
        }
        
        batch_results["end_time"] = datetime.utcnow().isoformat()
        
        return batch_results
    
    async def run_performance_test(self, command: str, iterations: int = 5, 
                                 concurrent_sessions: int = 3) -> Dict[str, Any]:
        """Run performance test with multiple iterations and concurrent sessions."""
        performance_results = {
            "test_id": f"perf_test_{uuid.uuid4().hex[:8]}",
            "start_time": datetime.utcnow().isoformat(),
            "command": command,
            "iterations": iterations,
            "concurrent_sessions": concurrent_sessions,
            "results": [],
            "statistics": {}
        }
        
        async def run_single_iteration(iteration: int, session_suffix: str):
            """Run a single performance test iteration."""
            session_id = f"perf_{performance_results['test_id']}_{session_suffix}_{iteration}"
            
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(60.0),
                headers={"Content-Type": "application/json"}
            ) as client:
                
                command_request = NLPCommandRequest(
                    command=command,
                    session_id=session_id,
                    context={"test_type": "performance_test"}
                )
                
                start_time = time.time()
                try:
                    response = await client.post("/command", json=command_request.dict())
                    execution_time = time.time() - start_time
                    
                    return {
                        "iteration": iteration,
                        "session_suffix": session_suffix,
                        "execution_time": execution_time,
                        "status_code": response.status_code,
                        "success": response.status_code == 200,
                        "response_size": len(response.content) if response.content else 0
                    }
                    
                except Exception as e:
                    execution_time = time.time() - start_time
                    return {
                        "iteration": iteration,
                        "session_suffix": session_suffix,
                        "execution_time": execution_time,
                        "status_code": 0,
                        "success": False,
                        "error": str(e),
                        "response_size": 0
                    }
        
        # Run concurrent performance tests
        tasks = []
        for session in range(concurrent_sessions):
            for iteration in range(iterations):
                task = run_single_iteration(iteration, f"session_{session}")
                tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        successful_results = []
        for result in results:
            if isinstance(result, dict):
                performance_results["results"].append(result)
                if result["success"]:
                    successful_results.append(result)
        
        # Calculate statistics
        if successful_results:
            execution_times = [r["execution_time"] for r in successful_results]
            performance_results["statistics"] = {
                "avg_execution_time": sum(execution_times) / len(execution_times),
                "min_execution_time": min(execution_times),
                "max_execution_time": max(execution_times),
                "success_rate": (len(successful_results) / len(results) * 100),
                "total_requests": len(results),
                "successful_requests": len(successful_results)
            }
        else:
            performance_results["statistics"] = {
                "avg_execution_time": 0,
                "min_execution_time": 0,
                "max_execution_time": 0,
                "success_rate": 0,
                "total_requests": len(results),
                "successful_requests": 0
            }
        
        performance_results["end_time"] = datetime.utcnow().isoformat()
        
        return performance_results


def validate_openai_integration() -> Dict[str, Any]:
    """Validate OpenAI integration configuration and connectivity."""
    validation_result = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "config": {}
    }
    
    # Check API key configuration
    if not settings.openai_api_key or settings.openai_api_key == "":
        validation_result["errors"].append("OpenAI API key not configured")
        validation_result["valid"] = False
    else:
        validation_result["config"]["api_key_configured"] = True
        validation_result["config"]["api_key_length"] = len(settings.openai_api_key)
    
    # Check model configuration
    if not settings.openai_model:
        validation_result["errors"].append("OpenAI model not configured")
        validation_result["valid"] = False
    else:
        validation_result["config"]["model"] = settings.openai_model
    
    # Check other OpenAI settings
    validation_result["config"].update({
        "max_tokens": settings.openai_max_tokens,
        "temperature": settings.openai_temperature
    })
    
    # Validate temperature range
    if not (0.0 <= settings.openai_temperature <= 2.0):
        validation_result["warnings"].append(f"Temperature {settings.openai_temperature} outside recommended range [0.0, 2.0]")
    
    # Validate max_tokens
    if settings.openai_max_tokens <= 0:
        validation_result["errors"].append(f"Invalid max_tokens value: {settings.openai_max_tokens}")
        validation_result["valid"] = False
    
    return validation_result


def generate_test_report(test_results: Dict[str, Any], output_file: Optional[str] = None) -> str:
    """Generate comprehensive test report from test results."""
    report_lines = [
        "# NLP Command Processing Integration E2E Test Report",
        f"Generated: {datetime.utcnow().isoformat()}",
        "",
        "## Executive Summary",
        f"- Test Session ID: {test_results.get('session_id', 'N/A')}",
        f"- Total Tests: {test_results.get('total_tests', 0)}",
        f"- Success Rate: {test_results.get('success_rate', 0):.1f}%",
        f"- Duration: {test_results.get('duration', 'N/A')}",
        f"- OpenAI Model: {test_results.get('openai_model', 'N/A')}",
        "",
        "## Test Coverage"
    ]
    
    # Add coverage information
    coverage_data = test_results.get("coverage_data", {})
    for category, subcategories in coverage_data.items():
        report_lines.append(f"### {category.title()}")
        for subcategory, info in subcategories.items():
            status = info.get("status", "unknown")
            timestamp = info.get("timestamp", "N/A")
            report_lines.append(f"- {subcategory}: {status} ({timestamp})")
        report_lines.append("")
    
    # Add detailed results if available
    if "detailed_results" in test_results:
        report_lines.extend([
            "## Detailed Test Results",
            ""
        ])
        
        for test_name, result in test_results["detailed_results"].items():
            success_icon = "✅" if result.get("success", False) else "❌"
            report_lines.extend([
                f"### {success_icon} {test_name}",
                f"- Status: {'PASSED' if result.get('success', False) else 'FAILED'}",
                f"- Scenario: {result.get('scenario', {}).get('description', 'N/A')}",
                f"- Response Preview: {result.get('response_preview', 'N/A')}",
                ""
            ])
    
    report_content = "\n".join(report_lines)
    
    # Save to file if requested
    if output_file:
        try:
            with open(output_file, "w") as f:
                f.write(report_content)
            logger.info(f"Test report saved to {output_file}")
        except Exception as e:
            logger.error(f"Failed to save test report: {e}")
    
    return report_content 
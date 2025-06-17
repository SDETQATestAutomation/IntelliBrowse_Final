"""
Debug Analyzer Tool for IntelliBrowse MCP Server

This tool analyzes test failures, exceptions, and debugging information to provide
intelligent insights, root cause analysis, and actionable recommendations.

Features:
- Test failure analysis with root cause identification
- Error pattern recognition and classification
- Log analysis and anomaly detection
- Performance bottleneck identification
- AI-powered debugging recommendations
"""

import asyncio
import logging
import re
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from enum import Enum

from openai import AsyncOpenAI
from pydantic import ValidationError

# Import the main MCP server instance
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from main import mcp_server

from ..schemas.tool_schemas import DebugAnalyzerRequest, DebugAnalyzerResponse
from ..config.settings import get_settings

# Configure logging
logger = logging.getLogger(__name__)

@mcp_server.tool()
async def analyze_debug_information(
    error_message: str,
    error_type: str = None,
    stack_trace: str = None,
    logs: str = None,
    context: str = None
) -> Dict[str, Any]:
    """
    Analyze debugging information to provide intelligent insights and recommendations.
    
    This tool combines pattern recognition, log analysis, and AI-powered debugging
    to help identify root causes and provide actionable solutions.
    
    Args:
        error_message: Error message or exception
        error_type: Type of error (e.g., TimeoutError, ElementNotFound)
        stack_trace: Stack trace if available
        logs: Relevant logs
        context: Additional context (JSON string or text)
    
    Returns:
        Dict containing debug analysis and recommendations
    """
    logger.info("Analyzing debug information", error_type=error_type)
    
    try:
        # Create request object
        request = DebugAnalyzerRequest(
            error_message=error_message,
            error_type=error_type,
            stack_trace=stack_trace,
            logs=logs,
            context=context
        )
        
        # Use the tool instance to analyze debug info
        tool_instance = DebugAnalyzerTool()
        response = await tool_instance.analyze_debug_info(request)
        
        logger.info(
            "Debug analysis completed",
            error_category=response.analysis.get("category"),
            confidence=response.confidence
        )
        
        return response.dict()
        
    except Exception as e:
        logger.error("Error analyzing debug information", error=str(e))
        return {
            "error": {
                "code": "DEBUG_ANALYSIS_ERROR",
                "message": f"Failed to analyze debug information: {str(e)}"
            }
        }

class ErrorSeverity(Enum):
    """Error severity levels for debug analysis."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

class ErrorCategory(Enum):
    """Error categories for classification."""
    SELECTOR = "selector"
    TIMING = "timing"
    NETWORK = "network"
    AUTHENTICATION = "authentication"
    ASSERTION = "assertion"
    ENVIRONMENT = "environment"
    LOGIC = "logic"
    UNKNOWN = "unknown"

class DebugAnalyzerTool:
    """
    Analyzes debugging information to provide intelligent insights and recommendations.
    
    This tool combines pattern recognition, log analysis, and AI-powered debugging
    to help identify root causes and provide actionable solutions.
    """
    
    def __init__(self):
        """Initialize the debug analyzer with patterns and AI client."""
        self.settings = get_settings()
        self.client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        self.max_recommendations = 5  # Maximum number of recommendations
        
        # Error pattern definitions for rule-based analysis
        self.error_patterns = {
            ErrorCategory.SELECTOR: [
                r"ElementNotFound|NoSuchElement|element not found",
                r"StaleElementReference|stale element",
                r"ElementNotInteractable|element not interactable",
                r"InvalidSelector|invalid selector"
            ],
            ErrorCategory.TIMING: [
                r"TimeoutException|timeout|timed out",
                r"ElementNotVisible|element not visible",
                r"WaitTimeoutError|wait.*timeout",
                r"page.*load.*timeout"
            ],
            ErrorCategory.NETWORK: [
                r"ConnectionError|connection.*failed",
                r"HTTPError|http.*error|status.*[45]\d\d",
                r"NetworkError|network.*error",
                r"DNSError|dns.*error"
            ],
            ErrorCategory.AUTHENTICATION: [
                r"Unauthorized|401|authentication.*failed",
                r"Forbidden|403|access.*denied",
                r"InvalidCredentials|invalid.*credentials",
                r"LoginError|login.*failed"
            ],
            ErrorCategory.ASSERTION: [
                r"AssertionError|assertion.*failed",
                r"ExpectedCondition|expected.*condition",
                r"ValidationError|validation.*failed",
                r"ComparisonError|comparison.*failed"
            ],
            ErrorCategory.ENVIRONMENT: [
                r"EnvironmentError|environment.*error",
                r"ConfigurationError|configuration.*error",
                r"PermissionError|permission.*denied",
                r"FileNotFound|file.*not.*found"
            ]
        }
        
        # Performance issue patterns
        self.performance_patterns = [
            r"slow|performance|memory|cpu|resource",
            r"leak|high.*usage|bottleneck",
            r"response.*time|latency|delay"
        ]
        
    async def analyze_debug_info(self, request: DebugAnalyzerRequest) -> DebugAnalyzerResponse:
        """
        Analyze debugging information and provide insights and recommendations.
        
        Args:
            request: Debug analysis request with error information and context
            
        Returns:
            DebugAnalyzerResponse with analysis results and recommendations
        """
        start_time = datetime.now()
        
        try:
            logger.info(
                "Starting debug analysis",
                extra={
                    "error_type": request.error_type,
                    "has_stack_trace": bool(request.stack_trace),
                    "has_logs": bool(request.logs),
                    "has_context": bool(request.context)
                }
            )
            
            # Validate input
            if not request.error_message.strip():
                raise ValueError("Error message cannot be empty")
            
            # Perform rule-based analysis
            rule_analysis = self._perform_rule_based_analysis(request)
            
            # Perform AI-powered analysis
            ai_analysis = await self._perform_ai_analysis(request, rule_analysis)
            
            # Combine analyses and generate recommendations
            combined_analysis = self._combine_analyses(rule_analysis, ai_analysis)
            
            # Generate actionable recommendations
            recommendations = self._generate_recommendations(combined_analysis, request)
            
            # Calculate confidence score
            confidence = self._calculate_confidence(combined_analysis, recommendations)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            logger.info(
                "Debug analysis completed",
                extra={
                    "error_category": combined_analysis.get("category"),
                    "severity": combined_analysis.get("severity"),
                    "recommendations_count": len(recommendations),
                    "confidence": confidence,
                    "processing_time": processing_time
                }
            )
            
            return DebugAnalyzerResponse(
                analysis=combined_analysis,
                recommendations=recommendations,
                confidence=confidence,
                metadata={
                    "processing_time": processing_time,
                    "analysis_approach": "hybrid",  # Rule-based + AI
                    "error_patterns_matched": rule_analysis.get("patterns_matched", 0),
                    "ai_analysis_used": bool(ai_analysis),
                    "timestamp": datetime.now().isoformat()
                }
            )
            
        except ValidationError as e:
            logger.error("Validation error in debug analysis", extra={"error": str(e)})
            raise ValueError(f"Invalid request: {e}")
        except Exception as e:
            logger.error("Error in debug analysis", extra={"error": str(e)})
            # Return fallback response
            return self._create_fallback_response(request, str(e))
    
    def _perform_rule_based_analysis(self, request: DebugAnalyzerRequest) -> Dict[str, Any]:
        """Perform rule-based analysis using error patterns."""
        
        analysis = {
            "category": ErrorCategory.UNKNOWN,
            "severity": ErrorSeverity.MEDIUM,
            "patterns_matched": 0,
            "identified_issues": [],
            "performance_issues": [],
            "root_causes": [],
            "context_clues": []
        }
        
        error_text = f"{request.error_message} {request.stack_trace or ''} {request.logs or ''}"
        error_text_lower = error_text.lower()
        
        # Pattern matching for error categorization
        for category, patterns in self.error_patterns.items():
            for pattern in patterns:
                if re.search(pattern, error_text, re.IGNORECASE):
                    analysis["category"] = category
                    analysis["patterns_matched"] += 1
                    analysis["identified_issues"].append({
                        "pattern": pattern,
                        "category": category.value,
                        "description": self._get_issue_description(category, pattern)
                    })
        
        # Performance issue detection
        for pattern in self.performance_patterns:
            if re.search(pattern, error_text_lower):
                analysis["performance_issues"].append({
                    "pattern": pattern,
                    "description": "Performance-related issue detected"
                })
        
        # Severity assessment
        analysis["severity"] = self._assess_severity(request, analysis)
        
        # Extract context clues
        analysis["context_clues"] = self._extract_context_clues(request)
        
        # Generate rule-based root causes
        analysis["root_causes"] = self._generate_rule_based_root_causes(analysis, request)
        
        return analysis
    
    def _get_issue_description(self, category: ErrorCategory, pattern: str) -> str:
        """Get human-readable description for error patterns."""
        
        descriptions = {
            ErrorCategory.SELECTOR: "Element selector issue - element not found or selector outdated",
            ErrorCategory.TIMING: "Timing issue - element not ready or page load timeout",
            ErrorCategory.NETWORK: "Network connectivity or HTTP response issue",
            ErrorCategory.AUTHENTICATION: "Authentication or authorization failure",
            ErrorCategory.ASSERTION: "Test assertion failed - expected vs actual mismatch",
            ErrorCategory.ENVIRONMENT: "Environment configuration or resource issue"
        }
        
        return descriptions.get(category, "Unspecified error pattern")
    
    def _assess_severity(self, request: DebugAnalyzerRequest, analysis: Dict[str, Any]) -> ErrorSeverity:
        """Assess error severity based on patterns and context."""
        
        error_text = request.error_message.lower()
        
        # Critical severity indicators
        if any(keyword in error_text for keyword in ["crash", "fatal", "critical", "abort"]):
            return ErrorSeverity.CRITICAL
        
        # High severity indicators
        if (analysis["category"] in [ErrorCategory.AUTHENTICATION, ErrorCategory.NETWORK] or
            any(keyword in error_text for keyword in ["exception", "error", "failed"])):
            return ErrorSeverity.HIGH
        
        # Medium severity (default)
        if analysis["patterns_matched"] > 0:
            return ErrorSeverity.MEDIUM
        
        # Low severity indicators
        if any(keyword in error_text for keyword in ["warning", "notice", "info"]):
            return ErrorSeverity.LOW
        
        return ErrorSeverity.MEDIUM
    
    def _extract_context_clues(self, request: DebugAnalyzerRequest) -> List[Dict[str, Any]]:
        """Extract contextual clues from the debug information."""
        
        clues = []
        
        # Extract from context if provided
        if request.context:
            try:
                context_data = json.loads(request.context) if isinstance(request.context, str) else request.context
                for key, value in context_data.items():
                    clues.append({
                        "type": "context",
                        "key": key,
                        "value": str(value),
                        "relevance": "high" if key in ["url", "step", "selector", "action"] else "medium"
                    })
            except (json.JSONDecodeError, AttributeError):
                clues.append({
                    "type": "context",
                    "key": "raw_context",
                    "value": str(request.context),
                    "relevance": "medium"
                })
        
        # Extract URLs from logs or stack trace
        all_text = f"{request.error_message} {request.stack_trace or ''} {request.logs or ''}"
        urls = re.findall(r'https?://[^\s]+', all_text)
        for url in urls[:3]:  # Limit to first 3 URLs
            clues.append({
                "type": "url",
                "key": "referenced_url",
                "value": url,
                "relevance": "high"
            })
        
        # Extract file paths
        file_paths = re.findall(r'[/\\][\w/\\.-]+\.(py|js|ts|html|css)', all_text)
        for path in file_paths[:3]:  # Limit to first 3 paths
            clues.append({
                "type": "file",
                "key": "file_path",
                "value": path,
                "relevance": "medium"
            })
        
        return clues
    
    def _generate_rule_based_root_causes(self, analysis: Dict[str, Any], request: DebugAnalyzerRequest) -> List[Dict[str, Any]]:
        """Generate root cause hypotheses based on rule-based analysis."""
        
        root_causes = []
        category = analysis["category"]
        
        # Category-specific root cause generation
        if category == ErrorCategory.SELECTOR:
            root_causes.extend([
                {
                    "cause": "Element selector is outdated or incorrect",
                    "probability": 0.8,
                    "evidence": "Selector-related error patterns detected"
                },
                {
                    "cause": "Page structure has changed",
                    "probability": 0.6,
                    "evidence": "Element not found errors suggest DOM changes"
                }
            ])
        
        elif category == ErrorCategory.TIMING:
            root_causes.extend([
                {
                    "cause": "Insufficient wait time for element",
                    "probability": 0.7,
                    "evidence": "Timeout patterns in error messages"
                },
                {
                    "cause": "Page performance issues causing slow loading",
                    "probability": 0.5,
                    "evidence": "Timing-related error patterns"
                }
            ])
        
        elif category == ErrorCategory.NETWORK:
            root_causes.extend([
                {
                    "cause": "Network connectivity issues",
                    "probability": 0.8,
                    "evidence": "Network error patterns detected"
                },
                {
                    "cause": "Server-side issues or maintenance",
                    "probability": 0.6,
                    "evidence": "HTTP error status codes"
                }
            ])
        
        elif category == ErrorCategory.AUTHENTICATION:
            root_causes.extend([
                {
                    "cause": "Invalid or expired credentials",
                    "probability": 0.9,
                    "evidence": "Authentication error patterns"
                },
                {
                    "cause": "Session timeout or cookie issues",
                    "probability": 0.7,
                    "evidence": "Authorization failure patterns"
                }
            ])
        
        # Performance-related root causes
        if analysis["performance_issues"]:
            root_causes.append({
                "cause": "Performance bottleneck affecting test execution",
                "probability": 0.6,
                "evidence": "Performance-related keywords detected"
            })
        
        return root_causes
    
    async def _perform_ai_analysis(self, request: DebugAnalyzerRequest, rule_analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Perform AI-powered analysis for complex debugging scenarios."""
        
        try:
            # Build AI prompt for debug analysis
            prompt = self._build_ai_debug_prompt(request, rule_analysis)
            
            response = await self.client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert debugging assistant specializing in test automation and web application debugging. Provide precise root cause analysis and actionable solutions."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=1200,
                temperature=0.1  # Very low temperature for precise analysis
            )
            
            ai_content = response.choices[0].message.content
            return self._parse_ai_analysis(ai_content)
            
        except Exception as e:
            logger.error("Error in AI analysis", extra={"error": str(e)})
            return None
    
    def _build_ai_debug_prompt(self, request: DebugAnalyzerRequest, rule_analysis: Dict[str, Any]) -> str:
        """Build comprehensive prompt for AI debug analysis."""
        
        prompt_parts = [
            "Analyze this debugging information and provide root cause analysis:",
            "",
            f"Error Message: {request.error_message}",
            f"Error Type: {request.error_type or 'Unknown'}",
            ""
        ]
        
        if request.stack_trace:
            stack_sample = request.stack_trace[:1000] + "..." if len(request.stack_trace) > 1000 else request.stack_trace
            prompt_parts.extend([
                "Stack Trace:",
                stack_sample,
                ""
            ])
        
        if request.logs:
            logs_sample = request.logs[:800] + "..." if len(request.logs) > 800 else request.logs
            prompt_parts.extend([
                "Logs:",
                logs_sample,
                ""
            ])
        
        if request.context:
            prompt_parts.extend([
                f"Context: {request.context}",
                ""
            ])
        
        # Add rule-based analysis context
        prompt_parts.extend([
            f"Rule-based Analysis:",
            f"- Category: {rule_analysis['category'].value}",
            f"- Severity: {rule_analysis['severity'].value}",
            f"- Patterns Matched: {rule_analysis['patterns_matched']}",
            ""
        ])
        
        prompt_parts.extend([
            "Please provide:",
            "1. Root cause analysis with confidence levels",
            "2. Specific debugging steps",
            "3. Prevention strategies",
            "4. Related issues to check",
            "",
            "Format your response as structured analysis with clear sections."
        ])
        
        return "\n".join(prompt_parts)
    
    def _parse_ai_analysis(self, ai_content: str) -> Dict[str, Any]:
        """Parse AI analysis response into structured format."""
        
        analysis = {
            "ai_root_causes": [],
            "debugging_steps": [],
            "prevention_strategies": [],
            "related_issues": [],
            "insights": []
        }
        
        lines = ai_content.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Detect sections
            if "root cause" in line.lower():
                current_section = "ai_root_causes"
            elif "debug" in line.lower() or "step" in line.lower():
                current_section = "debugging_steps"
            elif "prevention" in line.lower():
                current_section = "prevention_strategies"
            elif "related" in line.lower():
                current_section = "related_issues"
            elif line.startswith('-') or line.startswith('*') or line.startswith('•'):
                # Bullet point content
                content = line[1:].strip()
                if current_section and content:
                    analysis[current_section].append(content)
            else:
                # General insights
                if len(line) > 20:  # Filter out section headers
                    analysis["insights"].append(line)
        
        return analysis
    
    def _combine_analyses(self, rule_analysis: Dict[str, Any], ai_analysis: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Combine rule-based and AI analyses into unified result."""
        
        combined = rule_analysis.copy()
        
        if ai_analysis:
            # Merge AI insights
            combined["ai_insights"] = ai_analysis.get("insights", [])
            
            # Combine root causes
            ai_root_causes = [
                {
                    "cause": cause,
                    "probability": 0.7,  # Default confidence for AI causes
                    "evidence": "AI analysis",
                    "source": "ai"
                }
                for cause in ai_analysis.get("ai_root_causes", [])
            ]
            combined["root_causes"].extend(ai_root_causes)
            
            # Add AI-specific sections
            combined["debugging_steps"] = ai_analysis.get("debugging_steps", [])
            combined["prevention_strategies"] = ai_analysis.get("prevention_strategies", [])
            combined["related_issues"] = ai_analysis.get("related_issues", [])
        
        return combined
    
    def _generate_recommendations(self, analysis: Dict[str, Any], request: DebugAnalyzerRequest) -> List[Dict[str, Any]]:
        """Generate actionable recommendations based on analysis."""
        
        recommendations = []
        category = analysis["category"]
        severity = analysis["severity"]
        
        # Priority-based recommendation generation
        if severity in [ErrorSeverity.CRITICAL, ErrorSeverity.HIGH]:
            recommendations.append({
                "priority": "immediate",
                "action": "Address critical error immediately",
                "description": f"This {severity.value} severity {category.value} error requires immediate attention",
                "estimated_effort": "high"
            })
        
        # Category-specific recommendations
        category_recommendations = self._get_category_recommendations(category, analysis)
        recommendations.extend(category_recommendations)
        
        # AI-based recommendations
        if analysis.get("debugging_steps"):
            for step in analysis["debugging_steps"][:3]:  # Limit to 3 steps
                recommendations.append({
                    "priority": "medium",
                    "action": "Follow AI debugging step",
                    "description": step,
                    "estimated_effort": "medium",
                    "source": "ai"
                })
        
        # Prevention recommendations
        if analysis.get("prevention_strategies"):
            for strategy in analysis["prevention_strategies"][:2]:  # Limit to 2 strategies
                recommendations.append({
                    "priority": "low",
                    "action": "Implement prevention strategy",
                    "description": strategy,
                    "estimated_effort": "low",
                    "type": "prevention"
                })
        
        # Limit total recommendations
        return recommendations[:self.max_recommendations]
    
    def _get_category_recommendations(self, category: ErrorCategory, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get category-specific recommendations."""
        
        recommendations = []
        
        if category == ErrorCategory.SELECTOR:
            recommendations.extend([
                {
                    "priority": "high",
                    "action": "Update element selector",
                    "description": "Review and update the failing element selector using stable attributes",
                    "estimated_effort": "medium"
                },
                {
                    "priority": "medium",
                    "action": "Implement selector healing",
                    "description": "Use selector healing tool to automatically fix broken selectors",
                    "estimated_effort": "low"
                }
            ])
        
        elif category == ErrorCategory.TIMING:
            recommendations.extend([
                {
                    "priority": "high",
                    "action": "Increase wait times",
                    "description": "Add explicit waits for element visibility or page loading",
                    "estimated_effort": "low"
                },
                {
                    "priority": "medium",
                    "action": "Optimize page performance",
                    "description": "Investigate and optimize page loading performance",
                    "estimated_effort": "high"
                }
            ])
        
        elif category == ErrorCategory.NETWORK:
            recommendations.extend([
                {
                    "priority": "high",
                    "action": "Check network connectivity",
                    "description": "Verify network connectivity and server availability",
                    "estimated_effort": "low"
                },
                {
                    "priority": "medium",
                    "action": "Implement retry logic",
                    "description": "Add retry mechanisms for network-related failures",
                    "estimated_effort": "medium"
                }
            ])
        
        elif category == ErrorCategory.AUTHENTICATION:
            recommendations.extend([
                {
                    "priority": "high",
                    "action": "Verify credentials",
                    "description": "Check and update authentication credentials",
                    "estimated_effort": "low"
                },
                {
                    "priority": "medium",
                    "action": "Refresh session",
                    "description": "Implement session refresh or re-authentication logic",
                    "estimated_effort": "medium"
                }
            ])
        
        return recommendations
    
    def _calculate_confidence(self, analysis: Dict[str, Any], recommendations: List[Dict[str, Any]]) -> float:
        """Calculate confidence in the debug analysis and recommendations."""
        
        confidence = 0.5  # Base confidence
        
        # Boost confidence based on pattern matches
        confidence += min(0.3, analysis["patterns_matched"] * 0.1)
        
        # Boost confidence if AI analysis was used
        if analysis.get("ai_insights"):
            confidence += 0.2
        
        # Boost confidence based on number of quality recommendations
        quality_recommendations = len([r for r in recommendations if r.get("priority") in ["high", "immediate"]])
        confidence += min(0.2, quality_recommendations * 0.05)
        
        # Reduce confidence for unknown categories
        if analysis["category"] == ErrorCategory.UNKNOWN:
            confidence -= 0.3
        
        return max(0.0, min(1.0, round(confidence, 2)))
    
    def _create_fallback_response(self, request: DebugAnalyzerRequest, error_message: str) -> DebugAnalyzerResponse:
        """Create fallback response when analysis fails."""
        
        fallback_analysis = {
            "category": ErrorCategory.UNKNOWN,
            "severity": ErrorSeverity.MEDIUM,
            "patterns_matched": 0,
            "identified_issues": [{"description": "Analysis failed", "category": "system"}],
            "root_causes": [{"cause": "Unable to analyze error", "probability": 0.5, "evidence": "Analysis failure"}],
            "context_clues": []
        }
        
        fallback_recommendations = [
            {
                "priority": "high",
                "action": "Manual investigation required",
                "description": "Automated analysis failed, manual debugging needed",
                "estimated_effort": "high"
            }
        ]
        
        return DebugAnalyzerResponse(
            analysis=fallback_analysis,
            recommendations=fallback_recommendations,
            confidence=0.2,
            metadata={
                "error": error_message,
                "fallback_used": True,
                "processing_time": 0.0,
                "analysis_approach": "fallback"
            }
        )

# Global instance for tool registration
debug_analyzer_tool = DebugAnalyzerTool() 
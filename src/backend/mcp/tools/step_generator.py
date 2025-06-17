"""
Test Step Generator Tool for IntelliBrowse MCP Server

This tool generates test steps (Gherkin steps or automated test actions) based on 
natural language descriptions, DOM context, or existing test scenarios.

Features:
- Natural language to test step conversion
- Context-aware step generation using DOM information
- Support for BDD Gherkin steps and automation commands
- Confidence scoring and alternative suggestions
- Integration with OpenAI for intelligent step creation
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from openai import AsyncOpenAI
from pydantic import ValidationError

# Import the main MCP server instance
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from main import mcp_server

from ..schemas.tool_schemas import StepGeneratorRequest, StepGeneratorResponse
from ..config.settings import get_settings

# Configure logging
logger = logging.getLogger(__name__)

@mcp_server.tool()
async def generate_test_steps(
    description: str,
    step_type: str = "gherkin",
    dom_context: str = None,
    existing_steps: list[str] = None
) -> Dict[str, Any]:
    """
    Generate test steps from natural language descriptions.
    
    This tool uses AI to convert user requirements into executable test steps,
    supporting both BDD Gherkin format and direct automation commands.
    
    Args:
        description: Natural language description of the test requirement
        step_type: Type of steps to generate (gherkin, automation)
        dom_context: DOM context for better step generation
        existing_steps: Existing steps for reference
    
    Returns:
        Dict containing generated steps and metadata
    """
    logger.info("Generating test steps", description=description[:100])
    
    try:
        # Create request object
        request = StepGeneratorRequest(
            description=description,
            step_type=step_type,
            dom_context=dom_context,
            existing_steps=existing_steps or []
        )
        
        # Use the tool instance to generate steps
        tool_instance = StepGeneratorTool()
        response = await tool_instance.generate_steps(request)
        
        logger.info(
            "Test steps generated successfully",
            steps_count=len(response.steps),
            confidence=response.confidence
        )
        
        return response.dict()
        
    except Exception as e:
        logger.error("Error generating test steps", error=str(e))
        return {
            "error": {
                "code": "STEP_GENERATION_ERROR",
                "message": f"Failed to generate test steps: {str(e)}"
            }
        }

class StepGeneratorTool:
    """
    Generates test steps from natural language descriptions or existing context.
    
    This tool uses AI to convert user requirements into executable test steps,
    supporting both BDD Gherkin format and direct automation commands.
    """
    
    def __init__(self):
        """Initialize the step generator with OpenAI client and configuration."""
        self.settings = get_settings()
        self.client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        self.max_steps = 10  # Maximum number of steps to generate
        self.confidence_threshold = 0.6  # Minimum confidence for suggestions
        
    async def generate_steps(self, request: StepGeneratorRequest) -> StepGeneratorResponse:
        """
        Generate test steps based on the provided request.
        
        Args:
            request: Step generation request with description and context
            
        Returns:
            StepGeneratorResponse with generated steps and metadata
        """
        start_time = datetime.now()
        
        try:
            logger.info(
                "Starting step generation",
                extra={
                    "step_type": request.step_type,
                    "has_dom_context": bool(request.dom_context),
                    "description_length": len(request.description)
                }
            )
            
            # Validate input
            if not request.description.strip():
                raise ValueError("Description cannot be empty")
            
            # Generate AI-powered steps
            ai_steps = await self._generate_ai_steps(request)
            
            # Apply rule-based enhancement
            enhanced_steps = self._enhance_steps_with_rules(ai_steps, request)
            
            # Calculate confidence scores
            steps_with_confidence = self._calculate_confidence_scores(enhanced_steps, request)
            
            # Generate alternatives if confidence is low
            alternatives = []
            if any(step.get("confidence", 0) < self.confidence_threshold for step in steps_with_confidence):
                alternatives = await self._generate_alternative_steps(request)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            logger.info(
                "Step generation completed",
                extra={
                    "steps_generated": len(steps_with_confidence),
                    "alternatives_count": len(alternatives),
                    "processing_time": processing_time
                }
            )
            
            return StepGeneratorResponse(
                steps=steps_with_confidence,
                alternatives=alternatives,
                confidence=sum(step.get("confidence", 0) for step in steps_with_confidence) / len(steps_with_confidence) if steps_with_confidence else 0.0,
                metadata={
                    "processing_time": processing_time,
                    "model_used": self.settings.openai_model,
                    "token_usage": getattr(self, '_last_token_usage', {}),
                    "step_type": request.step_type,
                    "enhancement_applied": True
                }
            )
            
        except ValidationError as e:
            logger.error("Validation error in step generation", extra={"error": str(e)})
            raise ValueError(f"Invalid request: {e}")
        except Exception as e:
            logger.error("Error in step generation", extra={"error": str(e)})
            # Return fallback response
            return self._create_fallback_response(request, str(e))
    
    async def _generate_ai_steps(self, request: StepGeneratorRequest) -> List[Dict[str, Any]]:
        """Generate steps using OpenAI API."""
        
        # Build context-aware prompt
        prompt = self._build_step_generation_prompt(request)
        
        try:
            response = await self.client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert test automation engineer specializing in creating precise, executable test steps. Generate clear, actionable steps that can be automated."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=1000,
                temperature=0.3  # Lower temperature for more consistent results
            )
            
            # Store token usage for metadata
            if hasattr(response, 'usage'):
                self._last_token_usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            
            # Parse AI response into steps
            ai_content = response.choices[0].message.content
            return self._parse_ai_response_to_steps(ai_content, request.step_type)
            
        except Exception as e:
            logger.error("OpenAI API error in step generation", extra={"error": str(e)})
            return self._generate_fallback_steps(request)
    
    def _build_step_generation_prompt(self, request: StepGeneratorRequest) -> str:
        """Build a comprehensive prompt for step generation."""
        
        prompt_parts = [
            f"Generate {request.step_type} test steps for the following requirement:",
            f"Description: {request.description}",
            ""
        ]
        
        # Add DOM context if available
        if request.dom_context:
            # Limit DOM context size for token efficiency
            dom_sample = request.dom_context[:2000] + "..." if len(request.dom_context) > 2000 else request.dom_context
            prompt_parts.extend([
                "DOM Context:",
                dom_sample,
                ""
            ])
        
        # Add existing context if provided
        if request.existing_steps:
            prompt_parts.extend([
                "Existing Steps for Reference:",
                "\n".join(request.existing_steps),
                ""
            ])
        
        # Add format requirements
        if request.step_type == "gherkin":
            prompt_parts.extend([
                "Requirements:",
                "- Generate Gherkin steps (Given/When/Then format)",
                "- Use clear, specific language",
                "- Include element selectors when interacting with UI",
                "- Make steps independent and reusable",
                f"- Generate maximum {self.max_steps} steps",
                "",
                "Format each step on a new line with proper Gherkin keywords."
            ])
        else:
            prompt_parts.extend([
                "Requirements:",
                "- Generate automation code or commands",
                "- Use clear, executable actions",
                "- Include specific selectors and values",
                "- Make steps atomic and verifiable",
                f"- Generate maximum {self.max_steps} steps",
                "",
                "Format each step as a clear action or assertion."
            ])
        
        return "\n".join(prompt_parts)
    
    def _parse_ai_response_to_steps(self, ai_content: str, step_type: str) -> List[Dict[str, Any]]:
        """Parse AI response into structured step objects."""
        
        steps = []
        lines = ai_content.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Parse based on step type
            if step_type == "gherkin":
                step = self._parse_gherkin_step(line)
            else:
                step = self._parse_automation_step(line)
            
            if step:
                steps.append(step)
        
        return steps[:self.max_steps]  # Limit number of steps
    
    def _parse_gherkin_step(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse a Gherkin step from text."""
        
        gherkin_keywords = ["Given", "When", "Then", "And", "But"]
        
        for keyword in gherkin_keywords:
            if line.startswith(keyword):
                return {
                    "type": "gherkin",
                    "keyword": keyword,
                    "text": line[len(keyword):].strip(),
                    "full_step": line,
                    "actionable": True
                }
        
        # Non-keyword line - might be continuation or description
        if line and not line.startswith("#"):
            return {
                "type": "gherkin",
                "keyword": "Given",  # Default to Given for parsing
                "text": line,
                "full_step": f"Given {line}",
                "actionable": True
            }
        
        return None
    
    def _parse_automation_step(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse an automation step from text."""
        
        if not line or line.startswith("#"):
            return None
        
        # Determine step action type
        action_type = "action"
        if any(keyword in line.lower() for keyword in ["assert", "verify", "check", "should"]):
            action_type = "assertion"
        elif any(keyword in line.lower() for keyword in ["wait", "pause", "sleep"]):
            action_type = "wait"
        
        return {
            "type": "automation",
            "action_type": action_type,
            "text": line,
            "actionable": True
        }
    
    def _enhance_steps_with_rules(self, steps: List[Dict[str, Any]], request: StepGeneratorRequest) -> List[Dict[str, Any]]:
        """Apply rule-based enhancements to generated steps."""
        
        enhanced_steps = []
        
        for step in steps:
            enhanced_step = step.copy()
            
            # Add element selectors if DOM context is available
            if request.dom_context and not self._has_selector(step.get("text", "")):
                enhanced_step["suggested_selector"] = self._suggest_selector_from_dom(
                    step.get("text", ""), request.dom_context
                )
            
            # Add step metadata
            enhanced_step["step_id"] = f"step_{len(enhanced_steps) + 1}"
            enhanced_step["generated_at"] = datetime.now().isoformat()
            
            enhanced_steps.append(enhanced_step)
        
        return enhanced_steps
    
    def _has_selector(self, text: str) -> bool:
        """Check if text already contains element selectors."""
        selector_patterns = ["#", ".", "[", "css:", "xpath:", "id=", "class="]
        return any(pattern in text for pattern in selector_patterns)
    
    def _suggest_selector_from_dom(self, step_text: str, dom_context: str) -> Optional[str]:
        """Suggest element selector based on step text and DOM context."""
        
        # Simple heuristic: look for common UI elements
        step_lower = step_text.lower()
        
        if "button" in step_lower or "click" in step_lower:
            if "button" in dom_context.lower():
                return "button[type='submit'], .btn, .button"
        elif "input" in step_lower or "type" in step_lower or "enter" in step_lower:
            if "input" in dom_context.lower():
                return "input[type='text'], input[type='email'], textarea"
        elif "link" in step_lower or "navigate" in step_lower:
            if "<a" in dom_context.lower():
                return "a[href], .nav-link"
        
        return None
    
    def _calculate_confidence_scores(self, steps: List[Dict[str, Any]], request: StepGeneratorRequest) -> List[Dict[str, Any]]:
        """Calculate confidence scores for generated steps."""
        
        for step in steps:
            confidence = 0.5  # Base confidence
            
            # Increase confidence for well-formed steps
            if step.get("actionable", False):
                confidence += 0.2
            
            if step.get("suggested_selector"):
                confidence += 0.1
            
            # Decrease confidence for vague steps
            text = step.get("text", "").lower()
            if any(vague in text for vague in ["something", "anything", "maybe", "probably"]):
                confidence -= 0.2
            
            # Increase confidence for specific actions
            if any(specific in text for specific in ["click", "type", "select", "verify", "assert"]):
                confidence += 0.1
            
            step["confidence"] = max(0.0, min(1.0, confidence))
        
        return steps
    
    async def _generate_alternative_steps(self, request: StepGeneratorRequest) -> List[Dict[str, Any]]:
        """Generate alternative step suggestions."""
        
        try:
            # Create alternative request with different approach
            alt_prompt = f"""
            Provide 3 alternative approaches for this test requirement:
            {request.description}
            
            Focus on different testing strategies or step granularities.
            Keep each alternative concise (1-2 steps).
            """
            
            response = await self.client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a test strategy expert. Provide alternative testing approaches."
                    },
                    {
                        "role": "user",
                        "content": alt_prompt
                    }
                ],
                max_tokens=500,
                temperature=0.7  # Higher temperature for creativity
            )
            
            alternatives_text = response.choices[0].message.content
            return self._parse_alternatives(alternatives_text)
            
        except Exception as e:
            logger.error("Error generating alternatives", extra={"error": str(e)})
            return []
    
    def _parse_alternatives(self, alternatives_text: str) -> List[Dict[str, Any]]:
        """Parse alternative suggestions from AI response."""
        
        alternatives = []
        lines = alternatives_text.strip().split('\n')
        
        current_alt = []
        for line in lines:
            line = line.strip()
            if not line:
                if current_alt:
                    alternatives.append({
                        "approach": " ".join(current_alt),
                        "confidence": 0.7,
                        "alternative_id": f"alt_{len(alternatives) + 1}"
                    })
                    current_alt = []
            else:
                current_alt.append(line)
        
        # Add last alternative if exists
        if current_alt:
            alternatives.append({
                "approach": " ".join(current_alt),
                "confidence": 0.7,
                "alternative_id": f"alt_{len(alternatives) + 1}"
            })
        
        return alternatives[:3]  # Limit to 3 alternatives
    
    def _generate_fallback_steps(self, request: StepGeneratorRequest) -> List[Dict[str, Any]]:
        """Generate fallback steps using rule-based approach."""
        
        description = request.description.lower()
        steps = []
        
        # Basic pattern matching for common test scenarios
        if "login" in description:
            steps = [
                {"type": "action", "text": "Navigate to login page", "confidence": 0.6},
                {"type": "action", "text": "Enter username", "confidence": 0.6},
                {"type": "action", "text": "Enter password", "confidence": 0.6},
                {"type": "action", "text": "Click login button", "confidence": 0.6},
                {"type": "assertion", "text": "Verify successful login", "confidence": 0.6}
            ]
        elif "form" in description or "submit" in description:
            steps = [
                {"type": "action", "text": "Fill required form fields", "confidence": 0.5},
                {"type": "action", "text": "Submit form", "confidence": 0.5},
                {"type": "assertion", "text": "Verify form submission", "confidence": 0.5}
            ]
        elif "navigation" in description or "page" in description:
            steps = [
                {"type": "action", "text": "Navigate to target page", "confidence": 0.5},
                {"type": "assertion", "text": "Verify page loads correctly", "confidence": 0.5}
            ]
        else:
            # Generic fallback
            steps = [
                {"type": "action", "text": f"Perform action for: {request.description}", "confidence": 0.4},
                {"type": "assertion", "text": "Verify expected result", "confidence": 0.4}
            ]
        
        # Add metadata to fallback steps
        for i, step in enumerate(steps):
            step.update({
                "step_id": f"fallback_step_{i + 1}",
                "generated_at": datetime.now().isoformat(),
                "fallback": True
            })
        
        return steps
    
    def _create_fallback_response(self, request: StepGeneratorRequest, error_message: str) -> StepGeneratorResponse:
        """Create fallback response when generation fails."""
        
        fallback_steps = self._generate_fallback_steps(request)
        
        return StepGeneratorResponse(
            steps=fallback_steps,
            alternatives=[],
            confidence=0.3,  # Low confidence for fallback
            metadata={
                "error": error_message,
                "fallback_used": True,
                "step_type": request.step_type,
                "processing_time": 0.0
            }
        )

# Global instance for tool registration
step_generator_tool = StepGeneratorTool()


# Alias for backward compatibility with test expectations
async def generate_step(*args, **kwargs):
    """Generate step (alias for generate_test_steps)."""
    return await generate_test_steps(*args, **kwargs) 
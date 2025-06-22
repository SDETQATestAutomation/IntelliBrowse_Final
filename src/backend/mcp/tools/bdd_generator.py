"""
BDD Generator Tool for IntelliBrowse MCP Server.

This tool generates BDD scenarios from user stories and acceptance criteria
using OpenAI's language models.
"""

import asyncio
from typing import Dict, Any
import structlog
from openai import AsyncOpenAI

# Import the main MCP server instance
try:
    from server_instance import mcp_server
except ImportError:
    # Fallback for when running directly from mcp directory
    from server_instance import mcp_server
except ImportError:
    # Fallback for when running directly from mcp directory
    from server_instance import mcp_server

# Import schemas
try:
    from schemas.tools.bdd_generator_schemas import BDDGeneratorRequest as BDDRequest, BDDGeneratorResponse as BDDResponse
except ImportError:
    # Fallback for when running directly from mcp directory
    from schemas.tools.bdd_generator_schemas import BDDGeneratorRequest as BDDRequest, BDDGeneratorResponse as BDDResponse
try:
    from config.settings import settings
except ImportError:
    # Fallback for when running directly from mcp directory
    from config.settings import settings
except ImportError:
    # Fallback for when running directly from mcp directory
    from schemas.tools.bdd_generator_schemas import BDDGeneratorRequest as BDDRequest, BDDGeneratorResponse as BDDResponse
    from config.settings import settings

logger = structlog.get_logger("intellibrowse.mcp.tools.bdd_generator")

# Initialize OpenAI client
openai_client = AsyncOpenAI(api_key=settings.openai_api_key)


@mcp_server.tool()
async def generate_bdd_scenario(
    user_story: str,
    context: str = None,
    additional_requirements: list[str] = None
) -> Dict[str, Any]:
    """
    Generate BDD scenario from user story and acceptance criteria.
    
    This tool uses AI to create well-structured Gherkin scenarios
    based on user requirements and context.
    
    Args:
        user_story: User story description
        acceptance_criteria: List of acceptance criteria
        feature_context: Additional feature context
        existing_scenarios: Existing scenarios for reference
        scenario_type: Type of scenario (scenario, scenario_outline)
    
    Returns:
        Dict containing generated BDD scenario and metadata
    """
    logger.info("Generating BDD scenario", user_story=user_story[:100])
    
    try:
        # Validate request
        request = BDDRequest(
            user_story=user_story,
            context=context,
            additional_requirements=additional_requirements or []
        )
        
        # Build the prompt for OpenAI
        prompt = _build_bdd_prompt(request)
        
        # Call OpenAI API
        response = await openai_client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert BDD (Behavior-Driven Development) scenario writer. Generate clear, concise, and testable Gherkin scenarios."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            max_tokens=settings.openai_max_tokens,
            temperature=settings.openai_temperature
        )
        
        # Extract the generated scenario
        gherkin_scenario = response.choices[0].message.content.strip()
        
        # Analyze the generated scenario for confidence and suggestions
        analysis = await _analyze_generated_scenario(gherkin_scenario, request)
        
        # Create response
        bdd_response = BDDResponse(
            gherkin_scenario=gherkin_scenario,
            confidence_score=analysis["confidence_score"],
            suggestions=analysis["suggestions"],
            tags=analysis["tags"],
            metadata={
                "model_used": settings.openai_model,
                "tokens_used": response.usage.total_tokens,
                "generated_at": "2024-01-08T10:00:00Z"
            }
        )
        
        logger.info(
            "BDD scenario generated successfully",
            confidence=bdd_response.confidence_score,
            tokens_used=response.usage.total_tokens
        )
        
        return bdd_response.dict()
        
    except Exception as e:
        logger.error("Error generating BDD scenario", error=str(e))
        # Return error wrapped in MCP protocol format
        return {
            "error": {
                "code": "BDD_GENERATION_ERROR",
                "message": f"Failed to generate BDD scenario: {str(e)}"
            }
        }


def _build_bdd_prompt(request: BDDRequest) -> str:
    """Build the prompt for BDD scenario generation."""
    
    prompt_parts = [
        f"Generate a BDD scenario for the following user story:",
        f"User Story: {request.user_story}",
        ""
    ]
    
    if request.context:
        prompt_parts.extend([
            f"Context: {request.context}",
            ""
        ])
    
    if request.additional_requirements:
        prompt_parts.extend([
            "Additional Requirements:"
        ])
        for i, req in enumerate(request.additional_requirements, 1):
            prompt_parts.append(f"{i}. {req}")
        prompt_parts.append("")
    
    prompt_parts.extend([
        "Please generate a scenario in Gherkin format.",
        "Include appropriate Given-When-Then steps.",
        "Make the scenario clear, testable, and focused.",
        "Include relevant tags if appropriate.",
        "",
        "Format the response as a complete Gherkin feature with the scenario."
    ])
    
    return "\n".join(prompt_parts)


async def _analyze_generated_scenario(gherkin_scenario: str, request: BDDRequest) -> Dict[str, Any]:
    """Analyze the generated scenario for quality and provide suggestions."""
    
    # Simple analysis - in production this could be more sophisticated
    analysis = {
        "confidence_score": 0.85,  # Default confidence
        "suggestions": [],
        "tags": []
    }
    
    # Check for basic Gherkin structure
    if "Given" in gherkin_scenario and "When" in gherkin_scenario and "Then" in gherkin_scenario:
        analysis["confidence_score"] += 0.1
    
    # Check for feature declaration
    if "Feature:" in gherkin_scenario:
        analysis["confidence_score"] += 0.05
    
    # Generate suggestions based on content
    if "error" not in gherkin_scenario.lower() and "invalid" not in gherkin_scenario.lower():
        analysis["suggestions"].append("Consider adding negative test scenarios")
    
    if len(request.additional_requirements) > 3:
        analysis["suggestions"].append("Consider breaking down into multiple scenarios")
    
    # Generate tags based on user story content
    story_lower = request.user_story.lower()
    if "login" in story_lower or "authentication" in story_lower:
        analysis["tags"].extend(["@authentication", "@login"])
    if "register" in story_lower or "signup" in story_lower:
        analysis["tags"].extend(["@registration", "@signup"])
    if "dashboard" in story_lower:
        analysis["tags"].append("@dashboard")
    
    # Add default tags
    analysis["tags"].append("@automated")
    
    return analysis


# Alias for backward compatibility with test expectations
async def generate_bdd_scenarios(*args, **kwargs):
    """Generate BDD scenarios (alias for generate_bdd_scenario)."""
    return await generate_bdd_scenario(*args, **kwargs) 
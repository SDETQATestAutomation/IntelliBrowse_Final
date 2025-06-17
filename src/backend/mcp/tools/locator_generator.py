"""
Locator Generator Tool for IntelliBrowse MCP Server.

This tool generates robust element locators from DOM snapshots and element descriptions
using AI-powered analysis.
"""

import re
from typing import Dict, Any, List
import structlog
from openai import AsyncOpenAI

# Import the main MCP server instance
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from main import mcp_server

# Import schemas
from ..schemas.tool_schemas import LocatorRequest, LocatorResponse
from ..config.settings import settings

logger = structlog.get_logger("intellibrowse.mcp.tools.locator_generator")

# Initialize OpenAI client
openai_client = AsyncOpenAI(api_key=settings.openai_api_key)


@mcp_server.tool()
async def generate_element_locator(
    dom_snapshot: str,
    element_description: str,
    locator_strategy: str = "auto",
    context_hints: list[str] = None
) -> Dict[str, Any]:
    """
    Generate robust element locator from DOM and description.
    
    This tool analyzes DOM structure and generates the most reliable
    locator for the described element.
    
    Args:
        dom_snapshot: DOM tree snapshot
        element_description: Natural language element description
        locator_strategy: Preferred locator strategy (auto, id, css, xpath)
        context_hints: Context hints for better locating
    
    Returns:
        Dict containing generated locator and alternatives
    """
    logger.info("Generating element locator", description=element_description[:100])
    
    try:
        # Validate request
        request = LocatorRequest(
            dom_snapshot=dom_snapshot,
            element_description=element_description,
            locator_strategy=locator_strategy,
            context_hints=context_hints or []
        )
        
        # First try rule-based locator generation
        rule_based_result = _generate_rule_based_locator(request)
        
        if rule_based_result["confidence_score"] >= 0.8:
            logger.info("High confidence rule-based locator found")
            return rule_based_result
        
        # If rule-based approach has low confidence, use AI
        ai_result = await _generate_ai_locator(request)
        
        # Combine results, preferring higher confidence
        if ai_result["confidence_score"] > rule_based_result["confidence_score"]:
            final_result = ai_result
            # Add rule-based locator as fallback
            if rule_based_result["primary_locator"] not in ai_result["fallback_locators"]:
                final_result["fallback_locators"].append(rule_based_result["primary_locator"])
        else:
            final_result = rule_based_result
            # Add AI locator as fallback
            if ai_result["primary_locator"] not in rule_based_result["fallback_locators"]:
                final_result["fallback_locators"].append(ai_result["primary_locator"])
        
        logger.info(
            "Element locator generated successfully",
            strategy=final_result["strategy_used"],
            confidence=final_result["confidence_score"]
        )
        
        return final_result
        
    except Exception as e:
        logger.error("Error generating element locator", error=str(e))
        return {
            "error": {
                "code": "LOCATOR_GENERATION_ERROR",
                "message": f"Failed to generate element locator: {str(e)}"
            }
        }


def _generate_rule_based_locator(request: LocatorRequest) -> Dict[str, Any]:
    """Generate locator using rule-based DOM analysis."""
    
    dom = request.dom_snapshot
    description = request.element_description.lower()
    
    # Extract potential elements based on description keywords
    potential_locators = []
    confidence_score = 0.5
    strategy_used = "rule_based"
    
    # Look for ID attributes (highest priority)
    id_matches = re.findall(r'id=["\']([^"\']+)["\']', dom)
    for id_val in id_matches:
        if any(keyword in id_val.lower() for keyword in description.split()):
            potential_locators.append(f"id={id_val}")
            confidence_score = 0.95
            strategy_used = "id"
            break
    
    # Look for class attributes
    if not potential_locators:
        class_matches = re.findall(r'class=["\']([^"\']+)["\']', dom)
        for class_val in class_matches:
            if any(keyword in class_val.lower() for keyword in description.split()):
                potential_locators.append(f"css=.{class_val.replace(' ', '.')}")
                confidence_score = 0.8
                strategy_used = "class"
                break
    
    # Look for name attributes
    if not potential_locators:
        name_matches = re.findall(r'name=["\']([^"\']+)["\']', dom)
        for name_val in name_matches:
            if any(keyword in name_val.lower() for keyword in description.split()):
                potential_locators.append(f"name={name_val}")
                confidence_score = 0.85
                strategy_used = "name"
                break
    
    # Look for data attributes
    if not potential_locators:
        data_matches = re.findall(r'data-[^=]+=["\']([^"\']+)["\']', dom)
        for data_val in data_matches:
            if any(keyword in data_val.lower() for keyword in description.split()):
                potential_locators.append(f"css=[data-*='{data_val}']")
                confidence_score = 0.9
                strategy_used = "data_attribute"
                break
    
    # Fallback to text content matching
    if not potential_locators:
        text_matches = re.findall(r'>([^<]+)<', dom)
        for text in text_matches:
            if any(keyword in text.lower() for keyword in description.split()):
                potential_locators.append(f"xpath=//*[contains(text(), '{text.strip()}')]")
                confidence_score = 0.6
                strategy_used = "text_content"
                break
    
    # Default fallback
    if not potential_locators:
        potential_locators.append("css=*")
        confidence_score = 0.1
        strategy_used = "fallback"
    
    return {
        "primary_locator": potential_locators[0],
        "fallback_locators": potential_locators[1:] if len(potential_locators) > 1 else [],
        "strategy_used": strategy_used,
        "confidence_score": confidence_score,
        "element_analysis": {
            "analysis_method": "rule_based",
            "dom_size": len(request.dom_snapshot),
            "keywords_found": [kw for kw in description.split() if kw in dom.lower()]
        }
    }


async def _generate_ai_locator(request: LocatorRequest) -> Dict[str, Any]:
    """Generate locator using AI analysis."""
    
    # Build prompt for AI locator generation
    prompt = _build_locator_prompt(request)
    
    try:
        response = await openai_client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert in web automation and DOM analysis. Generate the most robust and reliable CSS selectors or XPath expressions for web elements."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=1000,
            temperature=0.1  # Low temperature for consistent results
        )
        
        ai_response = response.choices[0].message.content.strip()
        
        # Parse AI response to extract locator
        locator_info = _parse_ai_locator_response(ai_response)
        
        return {
            "primary_locator": locator_info["primary"],
            "fallback_locators": locator_info["fallbacks"],
            "strategy_used": "ai_generated",
            "confidence_score": locator_info["confidence"],
            "element_analysis": {
                "analysis_method": "ai_powered",
                "ai_reasoning": ai_response,
                "tokens_used": response.usage.total_tokens
            }
        }
        
    except Exception as e:
        logger.error("AI locator generation failed", error=str(e))
        # Fallback to basic CSS selector
        return {
            "primary_locator": "css=*",
            "fallback_locators": [],
            "strategy_used": "ai_fallback",
            "confidence_score": 0.2,
            "element_analysis": {
                "analysis_method": "ai_failed",
                "error": str(e)
            }
        }


def _build_locator_prompt(request: LocatorRequest) -> str:
    """Build prompt for AI locator generation."""
    
    prompt_parts = [
        "Analyze the following DOM snippet and generate the best locator for the described element:",
        "",
        f"Element Description: {request.element_description}",
        "",
        "DOM Snippet:",
        request.dom_snapshot[:2000],  # Limit DOM size for token efficiency
        ""
    ]
    
    if request.context_hints:
        prompt_parts.extend([
            "Context Hints:",
            ", ".join(request.context_hints),
            ""
        ])
    
    prompt_parts.extend([
        f"Preferred Strategy: {request.locator_strategy}",
        "",
        "Please provide:",
        "1. The best primary locator (CSS selector or XPath)",
        "2. 2-3 fallback locators",
        "3. Brief explanation of your choice",
        "",
        "Prioritize:",
        "- Uniqueness and reliability",
        "- Resistance to minor DOM changes", 
        "- Performance (CSS over XPath when possible)",
        "",
        "Format your response as:",
        "PRIMARY: [locator]",
        "FALLBACK1: [locator]",
        "FALLBACK2: [locator]",
        "REASONING: [explanation]"
    ])
    
    return "\n".join(prompt_parts)


def _parse_ai_locator_response(ai_response: str) -> Dict[str, Any]:
    """Parse AI response to extract locator information."""
    
    lines = ai_response.split('\n')
    result = {
        "primary": "css=*",
        "fallbacks": [],
        "confidence": 0.7
    }
    
    for line in lines:
        line = line.strip()
        if line.startswith("PRIMARY:"):
            result["primary"] = line.replace("PRIMARY:", "").strip()
            result["confidence"] = 0.8
        elif line.startswith("FALLBACK"):
            fallback = line.split(":", 1)[1].strip() if ":" in line else ""
            if fallback:
                result["fallbacks"].append(fallback)
    
    # Adjust confidence based on locator quality
    if "id=" in result["primary"] or "data-" in result["primary"]:
        result["confidence"] = min(0.95, result["confidence"] + 0.1)
    elif "css=" in result["primary"] and "." in result["primary"]:
        result["confidence"] = min(0.9, result["confidence"] + 0.05)
    
    return result


# Alias for backward compatibility with test expectations
async def generate_locator(*args, **kwargs):
    """Generate locator (alias for generate_element_locator)."""
    return await generate_element_locator(*args, **kwargs) 
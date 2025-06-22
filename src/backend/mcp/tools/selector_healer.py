"""
Selector Healer Tool for IntelliBrowse MCP Server

This tool analyzes broken or failing selectors and suggests healed alternatives
based on DOM context, historical patterns, and AI-powered analysis.

Features:
- Broken selector analysis and diagnosis
- Alternative selector generation with confidence scoring
- DOM-based healing using structural analysis
- AI-powered selector suggestions for complex cases
- Healing strategy recommendations
"""

import asyncio
import logging
import re
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from openai import AsyncOpenAI
from pydantic import ValidationError

# Import the main MCP server instance
try:
    from server_instance import mcp_server
except ImportError:
    # Fallback for when running directly from mcp directory
    from server_instance import mcp_server

try:
    from schemas.tools.selector_healer_schemas import SelectorHealerRequest, SelectorHealerResponse
except ImportError:
    # Fallback for when running directly from mcp directory
    from schemas.tools.selector_healer_schemas import SelectorHealerRequest, SelectorHealerResponse
try:
    from config.settings import get_settings
except ImportError:
    # Fallback for when running directly from mcp directory
    from config.settings import get_settings

# Configure logging
logger = logging.getLogger(__name__)

@mcp_server.tool()
async def heal_broken_selector(
    broken_selector: str,
    selector_type: str = "css",
    current_dom: str = None,
    original_dom: str = None,
    error_message: str = None
) -> Dict[str, Any]:
    """
    Heal broken selectors by analyzing DOM context and suggesting alternatives.
    
    This tool combines rule-based analysis with AI-powered suggestions to provide
    robust selector healing for dynamic web applications.
    
    Args:
        broken_selector: The broken/failing selector
        selector_type: Type of selector (css, xpath, id)
        current_dom: Current DOM snapshot
        original_dom: Original DOM when selector worked
        error_message: Error message from selector failure
    
    Returns:
        Dict containing healed selector suggestions and analysis
    """
    logger.info("Healing broken selector", selector=broken_selector[:100])
    
    try:
        # Create request object
        request = SelectorHealerRequest(
            broken_selector=broken_selector,
            selector_type=selector_type,
            current_dom=current_dom,
            original_dom=original_dom,
            error_message=error_message
        )
        
        # Use the tool instance to heal selector
        tool_instance = SelectorHealerTool()
        response = await tool_instance.heal_selector(request)
        
        logger.info(
            "Selector healing completed",
            suggestions_count=len(response.healed_selectors),
            confidence=response.confidence
        )
        
        return response.dict()
        
    except Exception as e:
        logger.error("Error healing selector", error=str(e))
        return {
            "error": {
                "code": "SELECTOR_HEALING_ERROR",
                "message": f"Failed to heal selector: {str(e)}"
            }
        }

class SelectorHealerTool:
    """
    Heals broken selectors by analyzing DOM context and suggesting alternatives.
    
    This tool combines rule-based analysis with AI-powered suggestions to provide
    robust selector healing for dynamic web applications.
    """
    
    def __init__(self):
        """Initialize the selector healer with OpenAI client and healing rules."""
        self.settings = get_settings()
        self.client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        self.max_suggestions = 5  # Maximum number of healing suggestions
        self.confidence_threshold = 0.7  # Minimum confidence for auto-application
        
        # Common selector patterns for rule-based healing
        self.stable_attributes = [
            'data-testid', 'data-test', 'data-cy', 'data-automation',
            'aria-label', 'aria-labelledby', 'role', 'title'
        ]
        
        self.fragile_patterns = [
            r'nth-child\(\d+\)',  # Position-based selectors
            r'nth-of-type\(\d+\)',
            r'>\s*\w+:nth',
            r'\[\d+\]',  # XPath position indices
        ]
        
    async def heal_selector(self, request: SelectorHealerRequest) -> SelectorHealerResponse:
        """
        Heal a broken selector by analyzing failure context and suggesting alternatives.
        
        Args:
            request: Selector healing request with broken selector and context
            
        Returns:
            SelectorHealerResponse with healed suggestions and analysis
        """
        start_time = datetime.now()
        
        try:
            logger.info(
                "Starting selector healing",
                extra={
                    "original_selector": request.broken_selector,
                    "selector_type": request.selector_type,
                    "has_current_dom": bool(request.current_dom),
                    "has_original_dom": bool(request.original_dom)
                }
            )
            
            # Validate input
            if not request.broken_selector.strip():
                raise ValueError("Broken selector cannot be empty")
            
            # Analyze the broken selector
            analysis = self._analyze_broken_selector(request.broken_selector)
            
            # Generate rule-based healing suggestions
            rule_based_suggestions = self._generate_rule_based_suggestions(request, analysis)
            
            # Generate AI-powered suggestions if needed
            ai_suggestions = []
            if len(rule_based_suggestions) < 3 or request.current_dom:
                ai_suggestions = await self._generate_ai_suggestions(request, analysis)
            
            # Combine and rank all suggestions
            all_suggestions = self._combine_and_rank_suggestions(
                rule_based_suggestions, ai_suggestions, request
            )
            
            # Calculate overall confidence
            overall_confidence = self._calculate_overall_confidence(all_suggestions, analysis)
            
            # Generate healing strategy
            strategy = self._generate_healing_strategy(analysis, all_suggestions)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            logger.info(
                "Selector healing completed",
                extra={
                    "suggestions_count": len(all_suggestions),
                    "overall_confidence": overall_confidence,
                    "processing_time": processing_time
                }
            )
            
            return SelectorHealerResponse(
                healed_selectors=all_suggestions,
                confidence=overall_confidence,
                analysis=analysis,
                healing_strategy=strategy,
                metadata={
                    "processing_time": processing_time,
                    "original_selector": request.broken_selector,
                    "healing_approach": "hybrid",  # Rule-based + AI
                    "suggestions_generated": len(all_suggestions),
                    "ai_suggestions_count": len(ai_suggestions),
                    "rule_suggestions_count": len(rule_based_suggestions)
                }
            )
            
        except ValidationError as e:
            logger.error("Validation error in selector healing", extra={"error": str(e)})
            raise ValueError(f"Invalid request: {e}")
        except Exception as e:
            logger.error("Error in selector healing", extra={"error": str(e)})
            # Return fallback response
            return self._create_fallback_response(request, str(e))
    
    def _analyze_broken_selector(self, selector: str) -> Dict[str, Any]:
        """Analyze the broken selector to understand failure patterns."""
        
        analysis = {
            "selector": selector,
            "type": self._detect_selector_type(selector),
            "fragility_score": 0.0,
            "issues": [],
            "components": self._parse_selector_components(selector),
            "complexity": "simple"
        }
        
        # Check for fragile patterns
        for pattern in self.fragile_patterns:
            if re.search(pattern, selector):
                analysis["issues"].append(f"Contains fragile pattern: {pattern}")
                analysis["fragility_score"] += 0.3
        
        # Check for position-based selectors
        if 'nth-child' in selector or 'nth-of-type' in selector:
            analysis["issues"].append("Position-based selector (fragile)")
            analysis["fragility_score"] += 0.4
        
        # Check for deep nesting
        if selector.count('>') > 3 or selector.count(' ') > 5:
            analysis["issues"].append("Deep nesting (brittle)")
            analysis["fragility_score"] += 0.2
            analysis["complexity"] = "complex"
        
        # Check for dynamic class names
        if re.search(r'class.*[\d\-_]{8,}', selector):
            analysis["issues"].append("Dynamic class names detected")
            analysis["fragility_score"] += 0.3
        
        # Check for lack of stable attributes
        if not any(attr in selector for attr in self.stable_attributes):
            analysis["issues"].append("No stable test attributes")
            analysis["fragility_score"] += 0.2
        
        analysis["fragility_score"] = min(1.0, analysis["fragility_score"])
        
        return analysis
    
    def _detect_selector_type(self, selector: str) -> str:
        """Detect the type of selector (CSS, XPath, etc.)."""
        
        if selector.startswith('//') or selector.startswith('/'):
            return "xpath"
        elif selector.startswith('#'):
            return "id"
        elif selector.startswith('.'):
            return "class"
        elif '[' in selector and ']' in selector:
            return "attribute"
        elif '>' in selector or '+' in selector or '~' in selector:
            return "css_combinator"
        else:
            return "css_simple"
    
    def _parse_selector_components(self, selector: str) -> Dict[str, List[str]]:
        """Parse selector into components for analysis."""
        
        components = {
            "ids": re.findall(r'#([\w\-_]+)', selector),
            "classes": re.findall(r'\.([\w\-_]+)', selector),
            "elements": re.findall(r'^(\w+)|>\s*(\w+)|\s+(\w+)', selector),
            "attributes": re.findall(r'\[([^\]]+)\]', selector),
            "pseudo_selectors": re.findall(r':([\w\-]+)', selector)
        }
        
        # Flatten element matches
        components["elements"] = [elem for group in components["elements"] for elem in group if elem]
        
        return components
    
    def _generate_rule_based_suggestions(self, request: SelectorHealerRequest, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate healing suggestions using rule-based approach."""
        
        suggestions = []
        original_selector = request.broken_selector
        components = analysis["components"]
        
        # Strategy 1: Use stable attributes if available in DOM
        if request.current_dom:
            stable_suggestions = self._find_stable_attribute_selectors(request.current_dom, components)
            suggestions.extend(stable_suggestions)
        
        # Strategy 2: Simplify overly complex selectors
        if analysis["complexity"] == "complex":
            simplified = self._simplify_selector(original_selector, components)
            if simplified and simplified != original_selector:
                suggestions.append({
                    "selector": simplified,
                    "confidence": 0.7,
                    "strategy": "simplification",
                    "reason": "Simplified complex selector to reduce brittleness"
                })
        
        # Strategy 3: Remove position-based selectors
        if any("position" in issue for issue in analysis["issues"]):
            position_free = self._remove_position_selectors(original_selector)
            if position_free and position_free != original_selector:
                suggestions.append({
                    "selector": position_free,
                    "confidence": 0.8,
                    "strategy": "position_removal",
                    "reason": "Removed fragile position-based selectors"
                })
        
        # Strategy 4: Fallback to element + attribute combinations
        if components["elements"] and components["attributes"]:
            element_attr_suggestions = self._generate_element_attribute_combinations(components)
            suggestions.extend(element_attr_suggestions)
        
        # Strategy 5: Use class/ID combinations
        if components["classes"] or components["ids"]:
            class_id_suggestions = self._generate_class_id_alternatives(components)
            suggestions.extend(class_id_suggestions)
        
        return suggestions[:self.max_suggestions]
    
    def _find_stable_attribute_selectors(self, dom: str, components: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find selectors using stable attributes from DOM."""
        
        suggestions = []
        
        # Look for stable attributes in DOM
        for attr in self.stable_attributes:
            # Simple regex to find elements with stable attributes
            pattern = rf'{attr}=["\']([^"\']+)["\']'
            matches = re.findall(pattern, dom)
            
            for match in matches:
                suggestion = {
                    "selector": f'[{attr}="{match}"]',
                    "confidence": 0.9,
                    "strategy": "stable_attribute",
                    "reason": f"Uses stable {attr} attribute"
                }
                suggestions.append(suggestion)
                
                if len(suggestions) >= 2:  # Limit stable attribute suggestions
                    break
        
        return suggestions
    
    def _simplify_selector(self, selector: str, components: Dict[str, Any]) -> Optional[str]:
        """Simplify a complex selector by removing unnecessary parts."""
        
        # Remove deep nesting - keep only last 2-3 levels
        parts = selector.split('>')
        if len(parts) > 3:
            simplified = ' > '.join(parts[-2:]).strip()
            return simplified
        
        # Remove excessive descendant selectors
        parts = selector.split()
        if len(parts) > 4:
            # Keep first and last parts, add middle if it has stable attributes
            stable_parts = []
            for part in parts:
                if any(attr in part for attr in self.stable_attributes):
                    stable_parts.append(part)
            
            if stable_parts:
                return ' '.join(stable_parts[:2])  # Take first 2 stable parts
            else:
                return ' '.join([parts[0], parts[-1]])  # First and last
        
        return None
    
    def _remove_position_selectors(self, selector: str) -> Optional[str]:
        """Remove position-based selectors from the selector."""
        
        # Remove nth-child and nth-of-type
        cleaned = re.sub(r':nth-child\(\d+\)', '', selector)
        cleaned = re.sub(r':nth-of-type\(\d+\)', '', cleaned)
        cleaned = re.sub(r':first-child|:last-child', '', cleaned)
        
        # Clean up any double spaces or trailing separators
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        cleaned = re.sub(r'>\s*>', '>', cleaned)
        
        return cleaned if cleaned != selector else None
    
    def _generate_element_attribute_combinations(self, components: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate suggestions combining elements with attributes."""
        
        suggestions = []
        elements = components["elements"]
        attributes = components["attributes"]
        
        for element in elements[:2]:  # Limit to first 2 elements
            for attr in attributes[:2]:  # Limit to first 2 attributes
                suggestion = {
                    "selector": f'{element}[{attr}]',
                    "confidence": 0.6,
                    "strategy": "element_attribute",
                    "reason": f"Combines element {element} with attribute {attr}"
                }
                suggestions.append(suggestion)
        
        return suggestions
    
    def _generate_class_id_alternatives(self, components: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate alternative selectors using classes and IDs."""
        
        suggestions = []
        
        # Single class selectors
        for cls in components["classes"][:2]:
            suggestions.append({
                "selector": f'.{cls}',
                "confidence": 0.5,
                "strategy": "single_class",
                "reason": f"Uses single class {cls}"
            })
        
        # Single ID selectors
        for id_val in components["ids"][:1]:  # IDs should be unique
            suggestions.append({
                "selector": f'#{id_val}',
                "confidence": 0.8,
                "strategy": "single_id",
                "reason": f"Uses ID {id_val}"
            })
        
        # Class combinations
        if len(components["classes"]) > 1:
            class_combo = '.'.join(components["classes"][:2])
            suggestions.append({
                "selector": f'.{class_combo}',
                "confidence": 0.6,
                "strategy": "class_combination",
                "reason": "Combines multiple classes"
            })
        
        return suggestions
    
    async def _generate_ai_suggestions(self, request: SelectorHealerRequest, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate healing suggestions using AI."""
        
        try:
            # Build AI prompt for selector healing
            prompt = self._build_ai_healing_prompt(request, analysis)
            
            response = await self.client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert web automation engineer specializing in CSS/XPath selector healing. Provide robust, maintainable selector alternatives."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=800,
                temperature=0.2  # Low temperature for consistent suggestions
            )
            
            ai_content = response.choices[0].message.content
            return self._parse_ai_suggestions(ai_content)
            
        except Exception as e:
            logger.error("Error generating AI suggestions", extra={"error": str(e)})
            return []
    
    def _build_ai_healing_prompt(self, request: SelectorHealerRequest, analysis: Dict[str, Any]) -> str:
        """Build prompt for AI-powered selector healing."""
        
        prompt_parts = [
            f"Heal this broken selector: {request.broken_selector}",
            f"Selector type: {analysis['type']}",
            f"Issues identified: {', '.join(analysis['issues'])}",
            ""
        ]
        
        if request.error_message:
            prompt_parts.extend([
                f"Error message: {request.error_message}",
                ""
            ])
        
        if request.current_dom:
            # Limit DOM size for token efficiency
            dom_sample = request.current_dom[:1500] + "..." if len(request.current_dom) > 1500 else request.current_dom
            prompt_parts.extend([
                "Current DOM context:",
                dom_sample,
                ""
            ])
        
        prompt_parts.extend([
            "Requirements:",
            "- Provide 2-3 alternative selectors",
            "- Prioritize stable attributes (data-testid, aria-label, etc.)",
            "- Avoid position-based selectors (nth-child, etc.)",
            "- Keep selectors as simple as possible",
            "- Explain healing strategy for each suggestion",
            "",
            "Format: selector | confidence (0-1) | strategy | reason"
        ])
        
        return "\n".join(prompt_parts)
    
    def _parse_ai_suggestions(self, ai_content: str) -> List[Dict[str, Any]]:
        """Parse AI response into structured suggestions."""
        
        suggestions = []
        lines = ai_content.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if '|' in line and len(line.split('|')) >= 4:
                parts = [part.strip() for part in line.split('|')]
                try:
                    suggestion = {
                        "selector": parts[0],
                        "confidence": float(parts[1]),
                        "strategy": parts[2],
                        "reason": parts[3]
                    }
                    suggestions.append(suggestion)
                except (ValueError, IndexError):
                    continue
        
        return suggestions[:3]  # Limit AI suggestions
    
    def _combine_and_rank_suggestions(self, rule_suggestions: List[Dict[str, Any]], 
                                    ai_suggestions: List[Dict[str, Any]], 
                                    request: SelectorHealerRequest) -> List[Dict[str, Any]]:
        """Combine and rank all suggestions by confidence and reliability."""
        
        all_suggestions = []
        
        # Add rule-based suggestions with source
        for suggestion in rule_suggestions:
            suggestion["source"] = "rule_based"
            all_suggestions.append(suggestion)
        
        # Add AI suggestions with source
        for suggestion in ai_suggestions:
            suggestion["source"] = "ai_powered"
            # Boost confidence for AI suggestions that use stable attributes
            if any(attr in suggestion["selector"] for attr in self.stable_attributes):
                suggestion["confidence"] = min(1.0, suggestion["confidence"] + 0.1)
            all_suggestions.append(suggestion)
        
        # Remove duplicates
        unique_suggestions = []
        seen_selectors = set()
        
        for suggestion in all_suggestions:
            if suggestion["selector"] not in seen_selectors:
                seen_selectors.add(suggestion["selector"])
                unique_suggestions.append(suggestion)
        
        # Sort by confidence (descending)
        unique_suggestions.sort(key=lambda x: x["confidence"], reverse=True)
        
        # Add suggestion IDs
        for i, suggestion in enumerate(unique_suggestions):
            suggestion["suggestion_id"] = f"heal_{i + 1}"
        
        return unique_suggestions[:self.max_suggestions]
    
    def _calculate_overall_confidence(self, suggestions: List[Dict[str, Any]], analysis: Dict[str, Any]) -> float:
        """Calculate overall confidence in healing suggestions."""
        
        if not suggestions:
            return 0.0
        
        # Base confidence on best suggestion
        max_confidence = max(suggestion["confidence"] for suggestion in suggestions)
        
        # Adjust based on analysis
        if analysis["fragility_score"] > 0.7:
            max_confidence *= 0.8  # Reduce confidence for highly fragile selectors
        
        # Boost confidence if we have multiple good suggestions
        if len([s for s in suggestions if s["confidence"] > 0.7]) >= 2:
            max_confidence = min(1.0, max_confidence + 0.1)
        
        return round(max_confidence, 2)
    
    def _generate_healing_strategy(self, analysis: Dict[str, Any], suggestions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate comprehensive healing strategy."""
        
        strategy = {
            "recommended_approach": "progressive",
            "steps": [],
            "risk_level": "low",
            "maintenance_tips": []
        }
        
        # Determine risk level
        if analysis["fragility_score"] > 0.7:
            strategy["risk_level"] = "high"
        elif analysis["fragility_score"] > 0.4:
            strategy["risk_level"] = "medium"
        
        # Generate healing steps
        if suggestions:
            best_suggestion = suggestions[0]
            strategy["steps"] = [
                f"Try primary suggestion: {best_suggestion['selector']}",
                f"Fallback to: {suggestions[1]['selector']}" if len(suggestions) > 1 else "Monitor for further failures",
                "Validate with test execution",
                "Update test documentation"
            ]
        
        # Add maintenance tips
        strategy["maintenance_tips"] = [
            "Use data-testid attributes for stable targeting",
            "Avoid position-based selectors",
            "Keep selectors as simple as possible",
            "Regular selector health checks"
        ]
        
        return strategy
    
    def _create_fallback_response(self, request: SelectorHealerRequest, error_message: str) -> SelectorHealerResponse:
        """Create fallback response when healing fails."""
        
        # Generate basic fallback suggestions
        fallback_suggestions = [
            {
                "selector": "*[data-testid]",  # Generic stable attribute selector
                "confidence": 0.3,
                "strategy": "fallback",
                "reason": "Generic stable attribute fallback",
                "source": "fallback"
            }
        ]
        
        fallback_analysis = {
            "selector": request.broken_selector,
            "type": "unknown",
            "fragility_score": 1.0,
            "issues": ["Healing analysis failed"],
            "components": {},
            "complexity": "unknown"
        }
        
        return SelectorHealerResponse(
            healed_selectors=fallback_suggestions,
            confidence=0.2,
            analysis=fallback_analysis,
            healing_strategy={
                "recommended_approach": "manual",
                "steps": ["Manual inspection required"],
                "risk_level": "high",
                "maintenance_tips": ["Consider redesigning selector strategy"]
            },
            metadata={
                "error": error_message,
                "fallback_used": True,
                "processing_time": 0.0
            }
        )

# Global instance for tool registration
selector_healer_tool = SelectorHealerTool() 
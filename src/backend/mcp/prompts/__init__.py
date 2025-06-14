"""
IntelliBrowse MCP Server - Prompts Module

This module contains user-controlled prompt templates that provide reusable templates
for common AI operations. Prompts are invoked by user/host actions and provide
structured templates with context injection capabilities.
"""

from .bug_report_prompt import BugReportPrompt
from .test_scenario_prompt import TestScenarioPrompt
from .debug_analysis_prompt import DebugAnalysisPrompt
from .locator_explanation_prompt import LocatorExplanationPrompt
from .step_documentation_prompt import StepDocumentationPrompt
from . import clear_input_prompt
from . import press_key_prompt
from . import release_key_prompt
from . import scroll_page_prompt
from . import hover_element_prompt

__all__ = [
    "BugReportPrompt",
    "TestScenarioPrompt", 
    "DebugAnalysisPrompt",
    "LocatorExplanationPrompt",
    "StepDocumentationPrompt",
    "clear_input_prompt",
    "press_key_prompt",
    "release_key_prompt",
    "scroll_page_prompt",
    "hover_element_prompt",
] 
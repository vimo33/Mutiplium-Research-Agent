"""
Shared prompt templates for Multiplium research providers.

This module provides unified, best-practice prompt templates that can be used
across all providers (OpenAI, Anthropic, Google) to ensure consistent output
quality and format.

Includes model-specific configuration and prompt mapping for optimal results
across different LLMs (Gemini 2.5 Pro, Gemini 3, GPT-5.1, Claude 4.5).
"""

from multiplium.prompts.discovery import (
    build_discovery_system_prompt,
    build_discovery_user_prompt,
    get_segment_search_strategies,
    get_segment_search_queries,
    DISCOVERY_FEW_SHOT_EXAMPLES,
)

from multiplium.prompts.deep_research import (
    build_deep_research_prompt,
    build_verification_prompt,
    WINE_INDUSTRY_CONTEXT,
)

from multiplium.prompts.model_config import (
    ModelFamily,
    ModelConfig,
    MODEL_CONFIGS,
    get_model_config,
    get_model_family,
    adapt_prompt_for_model,
    build_gemini_config,
    is_gemini_3,
    is_gemini_2_5,
    requires_high_temperature,
    get_recommended_timeout,
    list_available_models,
    list_gemini_models,
)

__all__ = [
    # Discovery prompts
    "build_discovery_system_prompt",
    "build_discovery_user_prompt",
    "get_segment_search_strategies",
    "get_segment_search_queries",
    "DISCOVERY_FEW_SHOT_EXAMPLES",
    # Deep research prompts
    "build_deep_research_prompt",
    "build_verification_prompt",
    "WINE_INDUSTRY_CONTEXT",
    # Model configuration
    "ModelFamily",
    "ModelConfig",
    "MODEL_CONFIGS",
    "get_model_config",
    "get_model_family",
    "adapt_prompt_for_model",
    "build_gemini_config",
    "is_gemini_3",
    "is_gemini_2_5",
    "requires_high_temperature",
    "get_recommended_timeout",
    "list_available_models",
    "list_gemini_models",
]


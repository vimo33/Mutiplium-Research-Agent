"""
Model-specific configuration and prompt mapping.

This module provides model-aware configurations for different LLM providers and versions,
enabling seamless switching between models while optimizing prompts for each model's
unique capabilities and requirements.

Supported Models:
- Gemini 2.5 Pro (gemini-2.5-pro): Best for complex reasoning, coding, STEM
- Gemini 3 Pro (gemini-3-pro-preview): Advanced multimodal, extended thinking
- GPT-5.1 / GPT-4o: Agentic tasks, web search
- Claude 4.5 Sonnet: Extended reasoning, tool use
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ModelFamily(Enum):
    """Model family classification."""
    GEMINI_2_5 = "gemini-2.5"
    GEMINI_3 = "gemini-3"
    GPT = "gpt"
    CLAUDE = "claude"
    UNKNOWN = "unknown"


@dataclass
class ModelConfig:
    """Configuration for a specific model."""
    
    # Model identification
    model_id: str
    family: ModelFamily
    display_name: str
    
    # Temperature settings
    default_temperature: float = 0.15
    min_temperature: float = 0.0
    max_temperature: float = 2.0
    
    # Token limits
    max_input_tokens: int = 128_000
    max_output_tokens: int = 8_192
    
    # Thinking/reasoning configuration
    supports_thinking: bool = False
    thinking_budget: int | None = None  # None = disabled, -1 = auto, N = token limit
    include_thoughts_in_response: bool = False
    
    # Search/grounding capabilities
    supports_google_search: bool = False
    supports_web_search: bool = False
    
    # Prompt optimization settings
    prefers_structured_output: bool = True
    prefers_json_mode: bool = False
    prefers_explicit_json_schema: bool = False
    needs_json_instruction_in_prompt: bool = True
    
    # System instruction handling
    system_instruction_position: str = "config"  # "config", "first_message", "both"
    
    # Special requirements
    notes: list[str] = field(default_factory=list)


# =============================================================================
# MODEL REGISTRY
# =============================================================================

MODEL_CONFIGS: dict[str, ModelConfig] = {
    # Gemini 2.5 Pro - Excellent for reasoning, coding, STEM
    "gemini-2.5-pro": ModelConfig(
        model_id="gemini-2.5-pro",
        family=ModelFamily.GEMINI_2_5,
        display_name="Gemini 2.5 Pro",
        default_temperature=0.15,
        max_input_tokens=1_048_576,  # 1M context
        max_output_tokens=65_536,
        supports_thinking=False,
        supports_google_search=True,
        prefers_structured_output=True,
        needs_json_instruction_in_prompt=True,
        notes=[
            "Best for complex multi-step reasoning",
            "Excellent at code generation and analysis",
            "Long context window (1M tokens)",
            "Lower temperature works well (0.1-0.3)",
        ],
    ),
    
    # Gemini 2.5 Pro Preview (alias)
    "gemini-2.5-pro-preview": ModelConfig(
        model_id="gemini-2.5-pro-preview",
        family=ModelFamily.GEMINI_2_5,
        display_name="Gemini 2.5 Pro Preview",
        default_temperature=0.15,
        max_input_tokens=1_048_576,
        max_output_tokens=65_536,
        supports_thinking=False,
        supports_google_search=True,
        prefers_structured_output=True,
        needs_json_instruction_in_prompt=True,
        notes=["Preview version of Gemini 2.5 Pro"],
    ),
    
    # Gemini 3 Pro Preview - Advanced multimodal, extended thinking
    "gemini-3-pro-preview": ModelConfig(
        model_id="gemini-3-pro-preview",
        family=ModelFamily.GEMINI_3,
        display_name="Gemini 3 Pro Preview",
        default_temperature=1.0,  # IMPORTANT: Gemini 3 requires 1.0
        min_temperature=1.0,
        max_temperature=1.0,
        max_input_tokens=1_048_576,
        max_output_tokens=65_536,
        supports_thinking=True,
        thinking_budget=512,  # Moderate reasoning depth
        include_thoughts_in_response=False,
        supports_google_search=True,
        prefers_structured_output=True,
        needs_json_instruction_in_prompt=True,
        notes=[
            "REQUIRES temperature=1.0 (lower values cause looping)",
            "Supports ThinkingConfig for extended reasoning",
            "Best for complex multi-step analysis",
            "May need longer timeouts due to thinking",
        ],
    ),
    
    # GPT-5.1 - Latest OpenAI flagship
    "gpt-5.1": ModelConfig(
        model_id="gpt-5.1",
        family=ModelFamily.GPT,
        display_name="GPT-5.1",
        default_temperature=0.15,
        max_input_tokens=400_000,
        max_output_tokens=32_768,
        supports_thinking=False,
        supports_web_search=True,
        prefers_structured_output=True,
        prefers_json_mode=True,
        needs_json_instruction_in_prompt=True,
        system_instruction_position="config",
        notes=[
            "400K context window",
            "Optimized for agentic tasks",
            "Native web search via Responses API",
        ],
    ),
    
    # GPT-4o - Strong multimodal
    "gpt-4o": ModelConfig(
        model_id="gpt-4o",
        family=ModelFamily.GPT,
        display_name="GPT-4o",
        default_temperature=0.15,
        max_input_tokens=128_000,
        max_output_tokens=16_384,
        supports_thinking=False,
        supports_web_search=True,
        prefers_structured_output=True,
        prefers_json_mode=True,
        needs_json_instruction_in_prompt=False,  # JSON mode handles it
        notes=["Good balance of speed and capability"],
    ),
    
    # Claude 4.5 Sonnet
    "claude-sonnet-4-5-20250929": ModelConfig(
        model_id="claude-sonnet-4-5-20250929",
        family=ModelFamily.CLAUDE,
        display_name="Claude 4.5 Sonnet",
        default_temperature=0.15,
        max_input_tokens=200_000,
        max_output_tokens=8_192,
        supports_thinking=True,
        thinking_budget=1024,
        supports_web_search=True,
        prefers_structured_output=True,
        needs_json_instruction_in_prompt=True,
        notes=[
            "Extended thinking for complex reasoning",
            "Excellent tool use capabilities",
        ],
    ),
}


def get_model_config(model_id: str) -> ModelConfig:
    """
    Get configuration for a specific model.
    
    Args:
        model_id: The model identifier (e.g., "gemini-2.5-pro")
    
    Returns:
        ModelConfig for the specified model, or a default config if unknown
    """
    if model_id in MODEL_CONFIGS:
        return MODEL_CONFIGS[model_id]
    
    # Try prefix matching for versioned models
    for key, config in MODEL_CONFIGS.items():
        if model_id.startswith(key.split("-")[0]):
            return config
    
    # Return a sensible default for unknown models
    family = ModelFamily.UNKNOWN
    if "gemini" in model_id.lower():
        if "3" in model_id:
            family = ModelFamily.GEMINI_3
        else:
            family = ModelFamily.GEMINI_2_5
    elif "gpt" in model_id.lower():
        family = ModelFamily.GPT
    elif "claude" in model_id.lower():
        family = ModelFamily.CLAUDE
    
    return ModelConfig(
        model_id=model_id,
        family=family,
        display_name=model_id,
        notes=["Unknown model - using default settings"],
    )


def get_model_family(model_id: str) -> ModelFamily:
    """Get the model family for a given model ID."""
    return get_model_config(model_id).family


# =============================================================================
# PROMPT ADAPTERS - Model-specific prompt transformations
# =============================================================================

@dataclass
class PromptAdaptation:
    """Adapted prompts for a specific model."""
    system_prompt: str
    user_prompt: str
    config_overrides: dict[str, Any] = field(default_factory=dict)


def adapt_prompt_for_model(
    model_id: str,
    system_prompt: str,
    user_prompt: str,
    **kwargs: Any,
) -> PromptAdaptation:
    """
    Adapt prompts for a specific model's requirements.
    
    Args:
        model_id: The target model ID
        system_prompt: The base system prompt
        user_prompt: The base user prompt
        **kwargs: Additional context (segment_name, etc.)
    
    Returns:
        PromptAdaptation with model-optimized prompts
    """
    config = get_model_config(model_id)
    config_overrides: dict[str, Any] = {}
    
    # Apply model-specific adaptations
    if config.family == ModelFamily.GEMINI_3:
        return _adapt_for_gemini_3(config, system_prompt, user_prompt, **kwargs)
    elif config.family == ModelFamily.GEMINI_2_5:
        return _adapt_for_gemini_2_5(config, system_prompt, user_prompt, **kwargs)
    elif config.family == ModelFamily.GPT:
        return _adapt_for_gpt(config, system_prompt, user_prompt, **kwargs)
    elif config.family == ModelFamily.CLAUDE:
        return _adapt_for_claude(config, system_prompt, user_prompt, **kwargs)
    
    # Default: return prompts as-is
    return PromptAdaptation(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        config_overrides=config_overrides,
    )


def _adapt_for_gemini_2_5(
    config: ModelConfig,
    system_prompt: str,
    user_prompt: str,
    **kwargs: Any,
) -> PromptAdaptation:
    """
    Adapt prompts for Gemini 2.5 Pro.
    
    Gemini 2.5 Pro characteristics:
    - Excellent at step-by-step reasoning without explicit thinking mode
    - Works well with lower temperatures (0.1-0.3)
    - Prefers clear, structured instructions
    - No ThinkingConfig needed
    """
    # Enhance system prompt with reasoning guidance
    enhanced_system = f"""{system_prompt}

**REASONING APPROACH:**
Think through each company systematically before adding to your output:
1. Verify vineyard/winery evidence exists
2. Assess source quality (Tier 1/2/3)
3. Calculate confidence score based on evidence strength
4. Only include companies meeting quality threshold

**OUTPUT DISCIPLINE:**
- Output ONLY valid JSON
- Start response with {{ and end with }}
- No preamble, explanations, or markdown"""

    # Simplify user prompt - Gemini 2.5 follows instructions well
    enhanced_user = f"""{user_prompt}

**REMINDER:** Begin research immediately. Output JSON when complete."""

    return PromptAdaptation(
        system_prompt=enhanced_system,
        user_prompt=enhanced_user,
        config_overrides={
            "temperature": config.default_temperature,
            "thinking_config": None,  # No thinking for 2.5
        },
    )


def _adapt_for_gemini_3(
    config: ModelConfig,
    system_prompt: str,
    user_prompt: str,
    **kwargs: Any,
) -> PromptAdaptation:
    """
    Adapt prompts for Gemini 3 Pro.
    
    Gemini 3 Pro characteristics:
    - REQUIRES temperature=1.0 (lower values cause looping issues)
    - Supports ThinkingConfig for extended reasoning
    - May need more explicit turn management
    - Longer response times due to thinking
    """
    # Add thinking-aware instructions
    enhanced_system = f"""{system_prompt}

**THINKING MODE ENABLED:**
You have extended reasoning capabilities. Use them to:
- Deeply analyze each company's vineyard evidence
- Evaluate source quality systematically
- Make careful confidence assessments

However, OUTPUT only the final JSON - your internal reasoning will be handled separately.

**CRITICAL CONSTRAINTS:**
- Temperature is fixed at 1.0 for this model
- Respect turn budget strictly
- Output by the specified turn even if incomplete"""

    # More directive user prompt for Gemini 3
    segment_name = kwargs.get("segment_name", "the current segment")
    enhanced_user = f"""{user_prompt}

**EXECUTION PLAN:**
1. Use Google Search to find companies in {segment_name}
2. Verify each candidate with additional searches
3. Apply quality filters (vineyard evidence, source tiers)
4. Output JSON when ready

Begin now with your first search."""

    return PromptAdaptation(
        system_prompt=enhanced_system,
        user_prompt=enhanced_user,
        config_overrides={
            "temperature": 1.0,  # REQUIRED for Gemini 3
            "thinking_config": {
                "thinking_budget": config.thinking_budget or 512,
                "include_thoughts": config.include_thoughts_in_response,
            },
        },
    )


def _adapt_for_gpt(
    config: ModelConfig,
    system_prompt: str,
    user_prompt: str,
    **kwargs: Any,
) -> PromptAdaptation:
    """
    Adapt prompts for GPT models (GPT-4o, GPT-5.1).
    
    GPT characteristics:
    - Strong instruction following
    - Native JSON mode available
    - Good at structured outputs
    - Web search via Responses API
    """
    # GPT works well with concise, clear instructions
    enhanced_system = system_prompt
    
    # If JSON mode is available, we can simplify JSON instructions
    if config.prefers_json_mode:
        enhanced_system = enhanced_system.replace(
            "**CRITICAL:** Output ONLY valid JSON. Start with { and end with }. No markdown, no explanations, no preamble.",
            "Output your response as valid JSON."
        )
    
    return PromptAdaptation(
        system_prompt=enhanced_system,
        user_prompt=user_prompt,
        config_overrides={
            "temperature": config.default_temperature,
            "response_format": {"type": "json_object"} if config.prefers_json_mode else None,
        },
    )


def _adapt_for_claude(
    config: ModelConfig,
    system_prompt: str,
    user_prompt: str,
    **kwargs: Any,
) -> PromptAdaptation:
    """
    Adapt prompts for Claude models.
    
    Claude characteristics:
    - Extended thinking for complex reasoning
    - Excellent at tool use
    - Follows complex instructions well
    - Prefers conversational but precise language
    """
    # Claude benefits from clear structure
    enhanced_system = f"""{system_prompt}

<important>
You have extended thinking capabilities. Use them to reason through each company carefully, but only output the final JSON result.
</important>"""

    return PromptAdaptation(
        system_prompt=enhanced_system,
        user_prompt=user_prompt,
        config_overrides={
            "temperature": config.default_temperature,
        },
    )


# =============================================================================
# GEMINI-SPECIFIC CONFIGURATION BUILDER
# =============================================================================

def build_gemini_config(
    model_id: str,
    system_instruction: str,
    tools: list[Any] | None = None,
    temperature: float | None = None,
) -> dict[str, Any]:
    """
    Build Gemini-specific GenerateContentConfig parameters.
    
    Args:
        model_id: The Gemini model ID
        system_instruction: System instruction text
        tools: List of tools (Google Search, etc.)
        temperature: Override temperature (uses model default if None)
    
    Returns:
        Dict of parameters for types.GenerateContentConfig
    """
    config = get_model_config(model_id)
    
    params: dict[str, Any] = {
        "system_instruction": system_instruction,
        "temperature": temperature if temperature is not None else config.default_temperature,
    }
    
    if tools:
        params["tools"] = tools
    
    # Add ThinkingConfig for Gemini 3
    if config.supports_thinking and config.family == ModelFamily.GEMINI_3:
        # ThinkingConfig will be constructed by the caller using types
        params["_thinking_enabled"] = True
        params["_thinking_budget"] = config.thinking_budget
        params["_include_thoughts"] = config.include_thoughts_in_response
    
    return params


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def is_gemini_3(model_id: str) -> bool:
    """Check if model is a Gemini 3 variant."""
    return get_model_family(model_id) == ModelFamily.GEMINI_3


def is_gemini_2_5(model_id: str) -> bool:
    """Check if model is a Gemini 2.5 variant."""
    return get_model_family(model_id) == ModelFamily.GEMINI_2_5


def requires_high_temperature(model_id: str) -> bool:
    """Check if model requires temperature=1.0 (like Gemini 3)."""
    config = get_model_config(model_id)
    return config.min_temperature >= 1.0


def get_recommended_timeout(model_id: str, base_timeout: float = 60.0) -> float:
    """Get recommended timeout for a model (thinking models need more time)."""
    config = get_model_config(model_id)
    if config.supports_thinking:
        return base_timeout * 1.5  # 50% more time for thinking models
    return base_timeout


def list_available_models() -> list[str]:
    """List all configured model IDs."""
    return list(MODEL_CONFIGS.keys())


def list_gemini_models() -> list[str]:
    """List all Gemini model IDs."""
    return [
        model_id for model_id, config in MODEL_CONFIGS.items()
        if config.family in (ModelFamily.GEMINI_2_5, ModelFamily.GEMINI_3)
    ]


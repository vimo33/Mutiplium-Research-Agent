"""Provider cost tracking and calculation utilities."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# Pricing per 1M tokens (as of December 2025)
# Input/Output pricing
MODEL_PRICING: dict[str, dict[str, float]] = {
    # OpenAI pricing (December 2025)
    "gpt-5.1": {"input": 5.00, "output": 15.00},  # Latest flagship model
    "gpt-5": {"input": 5.00, "output": 15.00},
    "o4-mini": {"input": 1.10, "output": 4.40},   # Fast reasoning model
    "o3": {"input": 10.00, "output": 40.00},      # Advanced reasoning model
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-4": {"input": 30.00, "output": 60.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    # Anthropic pricing
    "claude-sonnet-4-5-20250929": {"input": 3.00, "output": 15.00},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    # Google pricing (December 2025)
    "gemini-3-pro-preview": {"input": 1.25, "output": 5.00},  # Gemini 3 Pro
    "gemini-3-pro-image-preview": {"input": 1.25, "output": 5.00},
    "gemini-2.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-2.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    # Perplexity pricing (per request, not tokens)
    "perplexity-pro": {"per_request": 0.005},
    "perplexity-online": {"per_request": 0.005},
    # xAI/Grok pricing (estimated)
    "grok-2": {"input": 2.00, "output": 10.00},
    "grok-2-vision": {"input": 2.00, "output": 10.00},
}

# Default pricing for unknown models
DEFAULT_PRICING = {"input": 5.00, "output": 15.00}


@dataclass
class ProviderCost:
    """Cost breakdown for a single provider."""
    
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 0
    api_requests: int = 0
    input_cost: float = 0.0
    output_cost: float = 0.0
    tool_cost: float = 0.0  # For external API tools
    total_cost: float = 0.0
    currency: str = "USD"
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "tool_calls": self.tool_calls,
            "api_requests": self.api_requests,
            "input_cost": round(self.input_cost, 6),
            "output_cost": round(self.output_cost, 6),
            "tool_cost": round(self.tool_cost, 6),
            "total_cost": round(self.total_cost, 6),
            "currency": self.currency,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProviderCost":
        return cls(
            provider=data.get("provider", "unknown"),
            model=data.get("model", "unknown"),
            input_tokens=data.get("input_tokens", 0),
            output_tokens=data.get("output_tokens", 0),
            tool_calls=data.get("tool_calls", 0),
            api_requests=data.get("api_requests", 0),
            input_cost=data.get("input_cost", 0.0),
            output_cost=data.get("output_cost", 0.0),
            tool_cost=data.get("tool_cost", 0.0),
            total_cost=data.get("total_cost", 0.0),
            currency=data.get("currency", "USD"),
        )


@dataclass
class RunCostSummary:
    """Aggregate cost summary for an entire run."""
    
    run_id: str
    providers: dict[str, ProviderCost] = field(default_factory=dict)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tool_calls: int = 0
    total_cost: float = 0.0
    currency: str = "USD"
    calculated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "providers": {k: v.to_dict() for k, v in self.providers.items()},
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tool_calls": self.total_tool_calls,
            "total_cost": round(self.total_cost, 4),
            "currency": self.currency,
            "calculated_at": self.calculated_at,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunCostSummary":
        providers = {
            k: ProviderCost.from_dict(v) 
            for k, v in data.get("providers", {}).items()
        }
        return cls(
            run_id=data.get("run_id", ""),
            providers=providers,
            total_input_tokens=data.get("total_input_tokens", 0),
            total_output_tokens=data.get("total_output_tokens", 0),
            total_tool_calls=data.get("total_tool_calls", 0),
            total_cost=data.get("total_cost", 0.0),
            currency=data.get("currency", "USD"),
            calculated_at=data.get("calculated_at", datetime.now(timezone.utc).isoformat()),
        )


def calculate_cost(
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    api_requests: int = 0,
) -> tuple[float, float, float]:
    """
    Calculate cost for a model based on token usage.
    
    Returns:
        Tuple of (input_cost, output_cost, total_cost) in USD
    """
    # Find pricing for model (try exact match, then prefix match)
    pricing = MODEL_PRICING.get(model)
    if not pricing:
        # Try prefix matching for versioned models
        for model_key, price in MODEL_PRICING.items():
            if model.startswith(model_key) or model_key in model:
                pricing = price
                break
    
    if not pricing:
        pricing = DEFAULT_PRICING
    
    # For per-request pricing (like Perplexity)
    if "per_request" in pricing:
        total = pricing["per_request"] * api_requests
        return (0.0, 0.0, total)
    
    # Standard token-based pricing (per 1M tokens)
    input_cost = (input_tokens / 1_000_000) * pricing.get("input", DEFAULT_PRICING["input"])
    output_cost = (output_tokens / 1_000_000) * pricing.get("output", DEFAULT_PRICING["output"])
    total_cost = input_cost + output_cost
    
    return (input_cost, output_cost, total_cost)


def calculate_provider_cost(
    provider: str,
    model: str,
    telemetry: dict[str, Any],
) -> ProviderCost:
    """
    Calculate cost for a provider from telemetry data.
    
    Extracts token counts from various telemetry formats.
    """
    # Extract tokens from different telemetry formats
    input_tokens = (
        telemetry.get("input_tokens") or
        telemetry.get("prompt_tokens") or
        telemetry.get("tokens_used", {}).get("input") or
        0
    )
    output_tokens = (
        telemetry.get("output_tokens") or
        telemetry.get("completion_tokens") or
        telemetry.get("tokens_used", {}).get("output") or
        0
    )
    tool_calls = telemetry.get("tool_calls") or telemetry.get("tool_uses") or 0
    api_requests = telemetry.get("api_requests") or 1
    
    input_cost, output_cost, total_cost = calculate_cost(
        model, input_tokens, output_tokens, api_requests
    )
    
    # Add tool costs (external API calls like Perplexity, Tavily)
    tool_cost = 0.0
    tool_usage = telemetry.get("tool_usage", {})
    for tool_name, count in tool_usage.items():
        if "perplexity" in tool_name.lower():
            tool_cost += count * 0.005  # Perplexity per-request cost
        elif "tavily" in tool_name.lower():
            tool_cost += count * 0.001  # Tavily per-request cost (estimated)
    
    return ProviderCost(
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        tool_calls=tool_calls,
        api_requests=api_requests,
        input_cost=input_cost,
        output_cost=output_cost,
        tool_cost=tool_cost,
        total_cost=total_cost + tool_cost,
    )


def calculate_run_cost(
    run_id: str,
    provider_results: list[dict[str, Any]],
) -> RunCostSummary:
    """
    Calculate total cost for a run from provider results.
    
    Args:
        run_id: The run identifier
        provider_results: List of provider result dictionaries with telemetry
    
    Returns:
        RunCostSummary with per-provider and total costs
    """
    summary = RunCostSummary(run_id=run_id)
    
    for result in provider_results:
        provider = result.get("provider", "unknown")
        model = result.get("model", "unknown")
        telemetry = result.get("telemetry", {})
        
        cost = calculate_provider_cost(provider, model, telemetry)
        summary.providers[provider] = cost
        summary.total_input_tokens += cost.input_tokens
        summary.total_output_tokens += cost.output_tokens
        summary.total_tool_calls += cost.tool_calls
        summary.total_cost += cost.total_cost
    
    return summary

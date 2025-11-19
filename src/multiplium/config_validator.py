"""Environment and configuration validation utilities."""
from __future__ import annotations

import os
import sys
from typing import Any

import structlog

log = structlog.get_logger()


class ConfigValidationError(Exception):
    """Raised when critical configuration is missing or invalid."""


def validate_provider_keys(settings: Any) -> dict[str, list[str]]:
    """
    Validate that required API keys are present for enabled providers.
    
    Returns a dict mapping provider names to lists of missing keys.
    """
    missing: dict[str, list[str]] = {}
    
    # Check Anthropic
    anthropic_config = settings.providers.get("anthropic")
    if anthropic_config and anthropic_config.enabled:
        if not os.getenv("ANTHROPIC_API_KEY"):
            missing["anthropic"] = ["ANTHROPIC_API_KEY"]
            log.warning(
                "provider.key_missing",
                provider="anthropic",
                keys=missing["anthropic"],
                impact="Provider will be skipped",
            )
    
    # Check OpenAI
    openai_config = settings.providers.get("openai")
    if openai_config and openai_config.enabled:
        if not os.getenv("OPENAI_API_KEY"):
            missing["openai"] = ["OPENAI_API_KEY"]
            log.warning(
                "provider.key_missing",
                provider="openai",
                keys=missing["openai"],
                impact="Provider will be skipped",
            )
    
    # Check Google/Gemini (multiple possible env vars)
    google_config = settings.providers.get("google")
    if google_config and google_config.enabled:
        google_key = (
            os.getenv("GOOGLE_GENAI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
            or os.getenv("GEMINI_API_KEY")
        )
        if not google_key:
            missing["google"] = [
                "GOOGLE_GENAI_API_KEY or GOOGLE_API_KEY or GEMINI_API_KEY"
            ]
            log.warning(
                "provider.key_missing",
                provider="google",
                keys=missing["google"],
                impact="Provider will be skipped",
            )
    
    # Check xAI (optional 4th provider)
    xai_config = settings.providers.get("xai")
    if xai_config and xai_config.enabled:
        if not os.getenv("XAI_API_KEY"):
            missing["xai"] = ["XAI_API_KEY"]
            log.warning(
                "provider.key_missing",
                provider="xai",
                keys=missing["xai"],
                impact="Provider will be skipped",
            )
    
    return missing


def validate_search_apis() -> dict[str, bool]:
    """
    Check availability of search API keys.
    
    Returns dict mapping API names to availability status.
    """
    availability = {
        "tavily": bool(os.getenv("TAVILY_API_KEY")),
        "perplexity": bool(os.getenv("PERPLEXITY_API_KEY")),
    }
    
    if not any(availability.values()):
        log.warning(
            "search.no_premium_apis",
            message="No premium search APIs configured. Falling back to DuckDuckGo only.",
            recommendation="Set TAVILY_API_KEY or PERPLEXITY_API_KEY for better research quality",
        )
    else:
        enabled = [name for name, avail in availability.items() if avail]
        log.info("search.apis_configured", apis=enabled)
    
    return availability


def validate_optional_tools() -> dict[str, bool]:
    """Check availability of optional tool API keys."""
    availability = {
        "financial_modeling_prep": bool(os.getenv("FMP_API_KEY")),
        "crunchbase": bool(os.getenv("CRUNCHBASE_API_KEY")),
    }
    
    if not availability["financial_modeling_prep"]:
        log.info(
            "tools.using_demo_key",
            tool="financial_modeling_prep",
            message="Using demo key with rate limits. Set FMP_API_KEY for higher limits.",
        )
    
    return availability


def validate_all_on_startup(settings: Any) -> None:
    """
    Run all validation checks on orchestrator startup.
    
    Logs warnings for missing optional keys and raises ConfigValidationError
    if no providers are configured.
    """
    log.info("config.validation_start", message="Validating environment configuration")
    
    # Validate provider keys
    missing_provider_keys = validate_provider_keys(settings)
    
    # Count enabled providers with valid keys
    enabled_count = 0
    for provider_name in ["anthropic", "openai", "google", "xai"]:
        provider_config = settings.providers.get(provider_name)
        if provider_config and provider_config.enabled:
            if provider_name not in missing_provider_keys:
                enabled_count += 1
    
    if enabled_count == 0:
        error_msg = (
            "No providers are properly configured. At least one provider "
            "(Anthropic, OpenAI, Google, or xAI) must have both enabled=true and valid API key."
        )
        log.error("config.no_providers", message=error_msg)
        raise ConfigValidationError(error_msg)
    
    log.info(
        "config.providers_ready",
        enabled_count=enabled_count,
        total_configured=4,
    )
    
    # Validate search APIs (optional but recommended)
    validate_search_apis()
    
    # Validate optional tools
    validate_optional_tools()
    
    log.info("config.validation_complete", message="Configuration validation passed")


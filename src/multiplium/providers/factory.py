from __future__ import annotations

from collections.abc import Iterator

from multiplium.config import Settings
from multiplium.providers.base import BaseAgentProvider
from multiplium.tools.manager import ToolManager

from .anthropic_provider import ClaudeAgentProvider
from .google_provider import GeminiAgentProvider
from .openai_provider import OpenAIAgentProvider


class ProviderFactory:
    """Registers and instantiates provider-specific agent wrappers."""

    PROVIDER_MAPPING = {
        "anthropic": ClaudeAgentProvider,
        "openai": OpenAIAgentProvider,
        "google": GeminiAgentProvider,
    }

    def __init__(self, tool_manager: ToolManager, settings: Settings) -> None:
        self.tool_manager = tool_manager
        self.settings = settings

    def iter_active_agents(self) -> Iterator[tuple[str, BaseAgentProvider]]:
        for name, config in self.settings.providers.items():
            if not config.enabled:
                continue

            provider_cls = self.PROVIDER_MAPPING.get(name)
            if provider_cls is None:
                continue

            yield name, provider_cls(
                name=name,
                config=config,
                tool_manager=self.tool_manager,
                dry_run=self.settings.orchestrator.dry_run,
            )

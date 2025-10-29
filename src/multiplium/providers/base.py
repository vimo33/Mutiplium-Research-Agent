from __future__ import annotations

import abc
from dataclasses import dataclass
import os
from typing import Any, Optional
from multiplium.config import ProviderConfig
from multiplium.tools.manager import ToolManager


@dataclass
class ProviderRunResult:
    """Minimal result container for agent outputs."""

    provider: str
    model: str
    status: str
    findings: list[dict[str, Any]]
    telemetry: dict[str, Any]

    def summary(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "status": self.status,
            "finding_count": len(self.findings),
        }


class BaseAgentProvider(abc.ABC):
    """Base class for provider-specific wrappers."""

    def __init__(
        self,
        name: str,
        config: ProviderConfig,
        tool_manager: ToolManager,
        *,
        dry_run: bool = False,
    ) -> None:
        self.name = name
        self.config = config
        self.tool_manager = tool_manager
        self.dry_run = dry_run

    @abc.abstractmethod
    async def run(self, context: Any) -> ProviderRunResult:
        """Execute the agent autonomously and return aggregated findings."""

    def resolve_api_key(self, env_var: str) -> Optional[str]:
        if self.config.api_key:
            return self.config.api_key.get_secret_value()
        return os.environ.get(env_var)

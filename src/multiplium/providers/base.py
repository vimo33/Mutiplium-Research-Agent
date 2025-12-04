from __future__ import annotations

import abc
import asyncio
from dataclasses import dataclass, field
import os
from typing import Any, Optional

import httpx
import structlog
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from multiplium.config import ProviderConfig
from multiplium.tools.manager import ToolManager

logger = structlog.get_logger()


@dataclass
class ProviderRunResult:
    """Minimal result container for agent outputs."""

    provider: str
    model: str
    status: str
    findings: list[dict[str, Any]]
    telemetry: dict[str, Any]
    errors: list[dict[str, Any]] = field(default_factory=list)
    retry_count: int = 0

    def summary(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "status": self.status,
            "finding_count": len(self.findings),
            "error_count": len(self.errors),
            "retry_count": self.retry_count,
        }


class BaseAgentProvider(abc.ABC):
    """Base class for provider-specific wrappers with built-in retry logic."""

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
        self._retry_count = 0

    @abc.abstractmethod
    async def run(self, context: Any) -> ProviderRunResult:
        """Execute the agent autonomously and return aggregated findings."""

    @retry(
        retry=retry_if_exception_type((
            httpx.HTTPError,
            httpx.TimeoutException,
            asyncio.TimeoutError,
            ConnectionError,
        )),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def run_with_retry(self, context: Any) -> ProviderRunResult:
        """
        Execute the agent with automatic retry logic for transient failures.
        
        Retries up to 3 times with exponential backoff for:
        - HTTP errors (5xx, network issues)
        - Timeout errors
        - Connection errors
        
        Returns the result with retry_count populated.
        """
        try:
            result = await self.run(context)
            result.retry_count = self._retry_count
            return result
        except Exception as e:
            self._retry_count += 1
            logger.warning(
                "provider.retry_attempt",
                provider=self.name,
                attempt=self._retry_count,
                error=str(e),
            )
            raise
        finally:
            # Reset counter after completion (success or final failure)
            if self._retry_count > 0:
                logger.info(
                    "provider.retry_summary",
                    provider=self.name,
                    total_retries=self._retry_count,
                )

    def resolve_api_key(self, env_var: str) -> Optional[str]:
        if self.config.api_key:
            return self.config.api_key.get_secret_value()
        return os.environ.get(env_var)

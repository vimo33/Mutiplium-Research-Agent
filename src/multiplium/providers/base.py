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


# Transient errors that should be retried
RETRYABLE_EXCEPTIONS: tuple = (
    httpx.HTTPError,
    httpx.TimeoutException,
    asyncio.TimeoutError,
    ConnectionError,
)

# Import Google GenAI exceptions if available
try:
    from google.genai import errors as genai_errors
    RETRYABLE_EXCEPTIONS = RETRYABLE_EXCEPTIONS + (
        genai_errors.ServerError,  # 503, 500 errors
    )
    logger.debug("google_genai_retry_enabled", exceptions=["ServerError"])
except ImportError:
    pass  # google-genai not installed

# Import Google API Core exceptions if available (for other Google SDKs)
try:
    from google.api_core import exceptions as google_exceptions
    RETRYABLE_EXCEPTIONS = RETRYABLE_EXCEPTIONS + (
        google_exceptions.ServiceUnavailable,
        google_exceptions.ResourceExhausted,
        google_exceptions.DeadlineExceeded,
        google_exceptions.Aborted,
    )
except ImportError:
    pass  # google-cloud not installed


@dataclass
class ProviderCostData:
    """Cost tracking for a provider run."""
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 0
    input_cost: float = 0.0
    output_cost: float = 0.0
    tool_cost: float = 0.0
    total_cost: float = 0.0
    currency: str = "USD"
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "tool_calls": self.tool_calls,
            "input_cost": round(self.input_cost, 6),
            "output_cost": round(self.output_cost, 6),
            "tool_cost": round(self.tool_cost, 6),
            "total_cost": round(self.total_cost, 6),
            "currency": self.currency,
        }


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
    cost: ProviderCostData | None = None

    def summary(self) -> dict[str, Any]:
        result = {
            "provider": self.provider,
            "model": self.model,
            "status": self.status,
            "finding_count": len(self.findings),
            "error_count": len(self.errors),
            "retry_count": self.retry_count,
        }
        if self.cost:
            result["cost"] = self.cost.to_dict()
        return result
    
    def calculate_cost(self) -> None:
        """Calculate and populate cost data from telemetry."""
        from multiplium.providers.cost_tracker import calculate_provider_cost
        
        cost_data = calculate_provider_cost(
            self.provider,
            self.model,
            self.telemetry,
        )
        self.cost = ProviderCostData(
            input_tokens=cost_data.input_tokens,
            output_tokens=cost_data.output_tokens,
            tool_calls=cost_data.tool_calls,
            input_cost=cost_data.input_cost,
            output_cost=cost_data.output_cost,
            tool_cost=cost_data.tool_cost,
            total_cost=cost_data.total_cost,
        )


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

    async def run_with_retry(self, context: Any) -> ProviderRunResult:
        """
        Execute the agent with automatic retry logic for transient failures.
        
        Retries up to 3 times with exponential backoff for:
        - HTTP errors (5xx, network issues)
        - Timeout errors
        - Connection errors
        - Google API errors (503 overloaded, rate limits)
        
        Returns the result with retry_count populated and cost calculated.
        If all retries are exhausted, returns a failed ProviderRunResult
        instead of raising an exception (to allow other providers to continue).
        """
        from tenacity import RetryError
        
        @retry(
            retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
            stop=stop_after_attempt(5),  # More retries for transient 503 errors
            wait=wait_exponential(multiplier=2, min=10, max=120),  # Longer waits: 10s, 20s, 40s, 80s, 120s
        )
        async def _inner_run() -> ProviderRunResult:
            try:
                result = await self.run(context)
                result.retry_count = self._retry_count
                # Calculate cost after successful run
                try:
                    result.calculate_cost()
                except Exception as cost_err:
                    logger.warning(
                        "provider.cost_calculation_failed",
                        provider=self.name,
                        error=str(cost_err),
                    )
                return result
            except RETRYABLE_EXCEPTIONS as e:
                self._retry_count += 1
                logger.warning(
                    "provider.retry_attempt",
                    provider=self.name,
                    attempt=self._retry_count,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise
            except Exception as e:
                # Non-retryable error - log but don't increment retry counter
                logger.error(
                    "provider.non_retryable_error",
                    provider=self.name,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise
        
        try:
            result = await _inner_run()
            return result
        except RetryError as e:
            # All retries exhausted - return a failed result instead of raising
            # This allows other providers to continue running
            error_msg = str(e)
            # Try to extract the underlying error message
            try:
                underlying = e.last_attempt.exception()
                if underlying:
                    error_msg = f"{type(underlying).__name__}: {underlying}"
            except Exception:
                pass
            
            logger.error(
                "provider.all_retries_exhausted",
                provider=self.name,
                total_retries=self._retry_count,
                error=error_msg,
            )
            return ProviderRunResult(
                provider=self.name,
                model=self.config.model,
                status="failed",
                findings=[],
                telemetry={
                    "error": error_msg,
                    "retries_exhausted": True,
                    "total_retries": self._retry_count,
                },
                errors=[{
                    "type": "RetryError",
                    "message": error_msg,
                    "retries": self._retry_count,
                }],
                retry_count=self._retry_count,
            )
        except Exception as e:
            # Unexpected non-retryable error
            error_msg = str(e)
            logger.error(
                "provider.unexpected_failure",
                provider=self.name,
                error=error_msg,
                error_type=type(e).__name__,
            )
            return ProviderRunResult(
                provider=self.name,
                model=self.config.model,
                status="failed",
                findings=[],
                telemetry={"error": error_msg},
                errors=[{"type": type(e).__name__, "message": error_msg}],
                retry_count=self._retry_count,
            )
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

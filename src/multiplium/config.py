from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field, SecretStr, field_validator


class ProviderConfig(BaseModel):
    """General configuration for an LLM provider agent."""

    enabled: bool = True
    model: str
    temperature: float = 0.2
    max_steps: int = Field(
        default=16,
        description="Maximum autonomous tool iterations before forcing a response.",
    )
    retry_limit: int = Field(default=3, description="Max retries on transient SDK errors.")
    api_key: Optional[SecretStr] = None


class ToolConfig(BaseModel):
    """Configuration for a shared tool endpoint."""

    name: str
    endpoint: str
    enabled: bool = True
    timeout_seconds: int = 30
    rate_limit_per_minute: int = 30
    allow_domains: Optional[List[str]] = None
    cache_ttl_seconds: int = 900


class OrchestratorConfig(BaseModel):
    """Application-level configuration and thresholds."""

    sector: str
    thesis_path: Path
    value_chain_path: Path
    kpi_path: Path
    concurrency: int = 3
    output_path: Path = Path("reports/latest_report.json")
    dry_run: bool = False

    @field_validator("thesis_path", "value_chain_path", "kpi_path", "output_path", mode="before")
    def _expand_path(cls, value: str | Path) -> Path:
        return Path(value).expanduser().resolve()


class Settings(BaseModel):
    """Aggregate configuration root."""

    orchestrator: OrchestratorConfig
    providers: dict[str, ProviderConfig]
    tools: List[ToolConfig]


def load_settings(path: Path) -> Settings:
    """Load configuration from YAML into strongly-typed settings."""

    with path.expanduser().open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream)

    return Settings.model_validate(data)

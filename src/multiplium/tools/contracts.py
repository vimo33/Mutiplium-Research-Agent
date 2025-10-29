from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Mapping


@dataclass
class ToolSpec:
    """Describes a tool surface exposed to agents."""

    name: str
    description: str
    input_schema: Mapping[str, Any]
    output_schema: Mapping[str, Any]
    mcp_endpoint: str
    sync: bool = True
    cache_ttl_seconds: int = 900
    allowed_domains: tuple[str, ...] = field(default_factory=tuple)


ToolHandler = Callable[..., Awaitable[Any]]

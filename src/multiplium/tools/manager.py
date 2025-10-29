from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Awaitable
from urllib.parse import urlparse

import httpx

from multiplium.config import ToolConfig
from multiplium.tools.catalog import DEFAULT_TOOL_LIBRARY
from multiplium.tools.contracts import ToolHandler, ToolSpec
from multiplium.tools.stubs import STUB_HANDLERS


CacheValue = tuple[float, Any]


def _serialize_args_kwargs(*args: Any, **kwargs: Any) -> str:
    """Produce a deterministic cache key for tool calls."""

    def _default(obj: Any) -> Any:
        if isinstance(obj, (str, int, float, bool)) or obj is None:
            return obj
        if isinstance(obj, (list, tuple)):
            return [_default(o) for o in obj]
        if isinstance(obj, dict):
            return {str(k): _default(v) for k, v in sorted(obj.items(), key=lambda item: str(item[0]))}
        return repr(obj)

    payload = {"args": [_default(a) for a in args], "kwargs": _default(kwargs)}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


class ToolManager:
    """Registers shared tool callables and exposes MCP-compatible adapters."""

    def __init__(self, *, dry_run: bool = False, default_timeout: float = 30.0) -> None:
        self._tools: dict[str, ToolHandler] = {}
        self._specs: dict[str, ToolSpec] = {}
        self._cache: dict[tuple[str, str], CacheValue] = {}
        self._dry_run = dry_run
        self._client = httpx.AsyncClient(timeout=default_timeout)
        self._lock = asyncio.Lock()

    def register(self, spec: ToolSpec, handler: ToolHandler) -> None:
        self._tools[spec.name] = handler
        self._specs[spec.name] = spec

    def get(self, name: str) -> ToolHandler:
        return self._tools[name]

    def iter_specs(self) -> list[ToolSpec]:
        return list(self._specs.values())

    async def invoke(self, name: str, *args: Any, **kwargs: Any) -> Any:
        handler = self.get(name)
        spec = self._specs[name]
        cache_key = _serialize_args_kwargs(*args, **kwargs)
        now = time.time()

        if spec.cache_ttl_seconds > 0:
            cached = self._cache.get((name, cache_key))
            if cached:
                expires_at, value = cached
                if expires_at > now:
                    return value

        self._validate_allowed_domains(spec, kwargs)

        result = await handler(*args, **kwargs)

        if spec.cache_ttl_seconds > 0:
            self._cache[(name, cache_key)] = (now + spec.cache_ttl_seconds, result)

        return result

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "ToolManager":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    @classmethod
    def from_settings(cls, configs: list[ToolConfig], *, dry_run: bool = False) -> "ToolManager":
        manager = cls(dry_run=dry_run)
        for config in configs:
            if not config.enabled:
                continue

            defaults = DEFAULT_TOOL_LIBRARY.get(config.name, {})
            spec = ToolSpec(
                name=config.name,
                description=defaults.get("description", f"Tool {config.name}"),
                input_schema=defaults.get("input_schema", {"type": "object"}),
                output_schema=defaults.get("output_schema", {"type": "object"}),
                mcp_endpoint=config.endpoint,
                cache_ttl_seconds=config.cache_ttl_seconds,
                allowed_domains=tuple(config.allow_domains or []),
            )
            if dry_run:
                handler = STUB_HANDLERS.get(config.name, _stub_tool)
            else:
                handler = manager._build_http_handler(spec)
            manager.register(spec=spec, handler=handler)
        return manager

    def _build_http_handler(self, spec: ToolSpec) -> ToolHandler:
        async def _handler(*args: Any, **kwargs: Any) -> Any:
            payload = {"name": spec.name, "args": args, "kwargs": kwargs}
            async with self._lock:
                try:
                    response = await self._client.post(spec.mcp_endpoint, json=payload)
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    content = _safe_response_json(response)
                    return {
                        "error": f"HTTP {response.status_code} from tool endpoint: {exc}",
                        "status_code": response.status_code,
                        "endpoint": spec.mcp_endpoint,
                        "response": content,
                    }
                except httpx.HTTPError as exc:
                    return {
                        "error": f"Tool endpoint request failed: {exc}",
                        "endpoint": spec.mcp_endpoint,
                    }
            data = _safe_response_json(response)
            return data

        return _handler

    def _validate_allowed_domains(self, spec: ToolSpec, kwargs: dict[str, Any]) -> None:
        if not spec.allowed_domains:
            return

        url = kwargs.get("url")
        if not url:
            return

        hostname = urlparse(url).hostname or ""
        if hostname not in spec.allowed_domains:
            raise ValueError(f"URL hostname '{hostname}' not allowed for tool '{spec.name}'")


async def _stub_tool(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return {
        "status": "stub",
        "args": args,
        "kwargs": kwargs,
    }


def _safe_response_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return {"raw": response.text}

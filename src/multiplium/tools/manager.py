from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Mapping
from urllib.parse import urlparse

import httpx
import structlog
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from multiplium.config import ToolConfig
from multiplium.tools.catalog import DEFAULT_TOOL_LIBRARY
from multiplium.tools.contracts import ToolHandler, ToolSpec
from multiplium.tools.stubs import STUB_HANDLERS

logger = structlog.get_logger()

# Import MCP clients (only when not in dry run)
try:
    from multiplium.tools.tavily_mcp import TavilyMCPClient
except ImportError:
    TavilyMCPClient = None  # type: ignore[assignment,misc]

try:
    from multiplium.tools.perplexity_mcp import PerplexityMCPClient
except ImportError:
    PerplexityMCPClient = None  # type: ignore[assignment,misc]


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
        self._tavily_client: Any = None  # Lazy-initialized Tavily MCP client
        self._perplexity_client: Any = None  # Lazy-initialized Perplexity MCP client

    def register(self, spec: ToolSpec, handler: ToolHandler) -> None:
        self._tools[spec.name] = handler
        self._specs[spec.name] = spec

    def get(self, name: str) -> ToolHandler:
        return self._tools[name]

    def iter_specs(self) -> list[ToolSpec]:
        return list(self._specs.values())

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
    async def invoke(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """
        Invoke a tool with automatic retry logic for transient failures.
        
        Retries up to 3 times with exponential backoff for:
        - HTTP errors (5xx, network issues)
        - Timeout errors
        - Connection errors
        
        Caching is checked before retries to avoid redundant calls.
        """
        handler = self.get(name)
        spec = self._specs[name]
        cache_key = _serialize_args_kwargs(*args, **kwargs)
        now = time.time()

        # Check cache first (before any network call)
        if spec.cache_ttl_seconds > 0:
            cached = self._cache.get((name, cache_key))
            if cached:
                expires_at, value = cached
                if expires_at > now:
                    logger.debug("tool.cache_hit", tool=name)
                    return value

        self._validate_allowed_domains(spec, kwargs)

        # Execute handler (with automatic retry via decorator)
        try:
            result = await handler(*args, **kwargs)
        except Exception as e:
            logger.error(
                "tool.invoke_failed",
                tool=name,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

        # Cache successful result
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

            entry = DEFAULT_TOOL_LIBRARY.get(config.name)
            if entry is not None:
                description: str = entry["description"]
                input_schema: Mapping[str, Any] = entry["input_schema"]
                output_schema: Mapping[str, Any] = entry["output_schema"]
            else:
                description = f"Tool {config.name}"
                input_schema = {"type": "object"}
                output_schema = {"type": "object"}

            spec = ToolSpec(
                name=config.name,
                description=description,
                input_schema=input_schema,
                output_schema=output_schema,
                mcp_endpoint=config.endpoint,
                cache_ttl_seconds=config.cache_ttl_seconds,
                allowed_domains=tuple(config.allow_domains or []),
            )
            if dry_run:
                handler = STUB_HANDLERS.get(config.name, _stub_tool)
            elif config.endpoint == "tavily_mcp":
                # Use Tavily MCP client for these tools
                handler = manager._build_tavily_mcp_handler(spec)
            elif config.endpoint == "perplexity_mcp":
                # Use Perplexity MCP client for these tools
                handler = manager._build_perplexity_mcp_handler(spec)
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
    
    def _build_tavily_mcp_handler(self, spec: ToolSpec) -> ToolHandler:
        """Build a handler that uses the Tavily MCP client."""
        async def _handler(*args: Any, **kwargs: Any) -> Any:
            if TavilyMCPClient is None:
                return {
                    "error": "Tavily MCP client not available. Install required dependencies.",
                }
            
            # Lazy-initialize Tavily client
            if self._tavily_client is None:
                try:
                    self._tavily_client = TavilyMCPClient()
                except Exception as exc:
                    return {
                        "error": f"Failed to initialize Tavily MCP client: {exc}",
                    }
            
            # Route to appropriate Tavily MCP method
            try:
                if spec.name == "search_web":
                    return await self._tavily_client.search(**kwargs)
                elif spec.name == "fetch_content":
                    return await self._tavily_client.fetch_content(**kwargs)
                elif spec.name == "extract_content":
                    return await self._tavily_client.extract(**kwargs)
                elif spec.name == "map_website":
                    return await self._tavily_client.map_website(**kwargs)
                elif spec.name == "crawl_website":
                    return await self._tavily_client.crawl_website(**kwargs)
                else:
                    return {
                        "error": f"Unknown Tavily MCP tool: {spec.name}",
                    }
            except Exception as exc:
                return {
                    "error": f"Tavily MCP call failed: {exc}",
                    "tool": spec.name,
                }
        
        return _handler
    
    def _build_perplexity_mcp_handler(self, spec: ToolSpec) -> ToolHandler:
        """Build a handler that uses the Perplexity MCP client."""
        async def _handler(*args: Any, **kwargs: Any) -> Any:
            if PerplexityMCPClient is None:
                return {
                    "error": "Perplexity MCP client not available. Install required dependencies.",
                }
            
            # Lazy-initialize Perplexity client
            if self._perplexity_client is None:
                try:
                    self._perplexity_client = PerplexityMCPClient()
                except Exception as exc:
                    return {
                        "error": f"Failed to initialize Perplexity MCP client: {exc}",
                    }
            
            # Route to appropriate Perplexity MCP method
            try:
                if spec.name == "perplexity_search":
                    return await self._perplexity_client.search(**kwargs)
                elif spec.name == "perplexity_ask":
                    return await self._perplexity_client.ask(**kwargs)
                elif spec.name == "perplexity_research":
                    return await self._perplexity_client.research(**kwargs)
                elif spec.name == "perplexity_reason":
                    return await self._perplexity_client.reason(**kwargs)
                elif spec.name == "perplexity_enrich_company":
                    return await self._perplexity_client.enrich_company(**kwargs)
                else:
                    return {
                        "error": f"Unknown Perplexity MCP tool: {spec.name}",
                    }
            except Exception as exc:
                return {
                    "error": f"Perplexity MCP call failed: {exc}",
                    "tool": spec.name,
                }
        
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

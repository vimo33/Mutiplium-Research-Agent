from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import asyncio

from multiplium.config import ToolConfig
from multiplium.tools.manager import ToolManager
from multiplium.tools.contracts import ToolSpec


@pytest.mark.asyncio
async def test_tool_manager_dry_run_invokes_stub() -> None:
    """Test that dry_run mode uses stub handlers."""
    config = ToolConfig(
        name="search_web",
        endpoint="http://localhost/mock/search",
        cache_ttl_seconds=0,
    )
    manager = ToolManager.from_settings([config], dry_run=True)
    try:
        result = await manager.invoke("search_web", "regenerative viticulture", max_results=3)
    finally:
        await manager.aclose()

    assert result["tool"] == "search_web"
    assert result["query"] == "regenerative viticulture"
    assert result["max_results"] == 3


@pytest.mark.asyncio
async def test_tool_manager_caching() -> None:
    """Test that tool manager caches results correctly."""
    config = ToolConfig(
        name="search_web",
        endpoint="http://localhost/mock/search",
        cache_ttl_seconds=60,  # Cache for 60 seconds
    )
    manager = ToolManager.from_settings([config], dry_run=True)
    
    try:
        # First call - should execute
        result1 = await manager.invoke("search_web", "test query", max_results=5)
        
        # Second call with same arguments - should hit cache
        result2 = await manager.invoke("search_web", "test query", max_results=5)
        
        # Results should be identical (from cache)
        assert result1 == result2
        
        # Different arguments - should execute again
        result3 = await manager.invoke("search_web", "different query", max_results=5)
        assert result3["query"] == "different query"
    finally:
        await manager.aclose()


@pytest.mark.asyncio
async def test_tool_manager_no_caching_when_disabled() -> None:
    """Test that caching is disabled when cache_ttl_seconds is 0."""
    config = ToolConfig(
        name="search_web",
        endpoint="http://localhost/mock/search",
        cache_ttl_seconds=0,  # No caching
    )
    manager = ToolManager.from_settings([config], dry_run=True)
    
    try:
        result1 = await manager.invoke("search_web", "test query", max_results=5)
        result2 = await manager.invoke("search_web", "test query", max_results=5)
        
        # Both calls should execute (not cached)
        # In dry_run mode, we can't easily verify this, but ensure no errors
        assert result1 is not None
        assert result2 is not None
    finally:
        await manager.aclose()


@pytest.mark.asyncio
async def test_tool_manager_retry_on_http_error() -> None:
    """Test that tool manager retries on HTTP errors."""
    mock_handler = AsyncMock()
    # First two calls fail, third succeeds
    mock_handler.side_effect = [
        httpx.HTTPError("Connection failed"),
        httpx.HTTPError("Connection failed"),
        {"result": "success"},
    ]
    
    manager = ToolManager(dry_run=False)
    spec = ToolSpec(
        name="test_tool",
        description="Test tool",
        input_schema={},
        output_schema={},
        cache_ttl_seconds=0,
        allowed_domains=[],
    )
    manager.register(spec, mock_handler)
    
    try:
        # Should retry and eventually succeed
        result = await manager.invoke("test_tool")
        assert result == {"result": "success"}
        assert mock_handler.call_count == 3
    finally:
        await manager.aclose()


@pytest.mark.asyncio
async def test_tool_manager_retry_exhaustion() -> None:
    """Test that tool manager fails after max retries."""
    mock_handler = AsyncMock()
    # All calls fail
    mock_handler.side_effect = httpx.HTTPError("Permanent failure")
    
    manager = ToolManager(dry_run=False)
    spec = ToolSpec(
        name="test_tool",
        description="Test tool",
        input_schema={},
        output_schema={},
        cache_ttl_seconds=0,
        allowed_domains=[],
    )
    manager.register(spec, mock_handler)
    
    try:
        # Should fail after 3 attempts
        with pytest.raises(httpx.HTTPError):
            await manager.invoke("test_tool")
        
        # Should have tried 3 times (stop_after_attempt(3))
        assert mock_handler.call_count == 3
    finally:
        await manager.aclose()


@pytest.mark.asyncio
async def test_tool_manager_no_retry_on_non_retryable_error() -> None:
    """Test that tool manager doesn't retry on non-retryable errors."""
    mock_handler = AsyncMock()
    # Raise a non-retryable error (ValueError)
    mock_handler.side_effect = ValueError("Invalid input")
    
    manager = ToolManager(dry_run=False)
    spec = ToolSpec(
        name="test_tool",
        description="Test tool",
        input_schema={},
        output_schema={},
        cache_ttl_seconds=0,
        allowed_domains=[],
    )
    manager.register(spec, mock_handler)
    
    try:
        # Should fail immediately without retry
        with pytest.raises(ValueError):
            await manager.invoke("test_tool")
        
        # Should have tried only once (no retry for ValueError)
        assert mock_handler.call_count == 1
    finally:
        await manager.aclose()


@pytest.mark.asyncio
async def test_tool_manager_domain_validation() -> None:
    """Test that tool manager validates allowed domains."""
    manager = ToolManager(dry_run=False)
    
    spec = ToolSpec(
        name="test_tool",
        description="Test tool",
        input_schema={},
        output_schema={},
        cache_ttl_seconds=0,
        allowed_domains=["example.com"],
    )
    
    mock_handler = AsyncMock(return_value={"status": "ok"})
    manager.register(spec, mock_handler)
    
    try:
        # This should pass validation (or raise if validation fails)
        result = await manager.invoke("test_tool", url="https://example.com/page")
        assert result is not None
    finally:
        await manager.aclose()


@pytest.mark.asyncio
async def test_tool_manager_concurrent_invocations() -> None:
    """Test that tool manager handles concurrent invocations correctly."""
    config = ToolConfig(
        name="search_web",
        endpoint="http://localhost/mock/search",
        cache_ttl_seconds=0,
    )
    manager = ToolManager.from_settings([config], dry_run=True)
    
    try:
        # Execute multiple tool calls concurrently
        results = await asyncio.gather(
            manager.invoke("search_web", "query1", max_results=3),
            manager.invoke("search_web", "query2", max_results=3),
            manager.invoke("search_web", "query3", max_results=3),
        )
        
        assert len(results) == 3
        assert results[0]["query"] == "query1"
        assert results[1]["query"] == "query2"
        assert results[2]["query"] == "query3"
    finally:
        await manager.aclose()


class TestToolManagerRegistration:
    """Test tool registration functionality."""

    def test_register_tool(self):
        """Test registering a tool with the manager."""
        manager = ToolManager(dry_run=False)
        
        spec = ToolSpec(
            name="custom_tool",
            description="Custom tool",
            input_schema={},
            output_schema={},
            cache_ttl_seconds=0,
            allowed_domains=[],
        )
        
        mock_handler = AsyncMock()
        manager.register(spec, mock_handler)
        
        # Should be able to retrieve the handler
        retrieved_handler = manager.get("custom_tool")
        assert retrieved_handler is mock_handler

    def test_iter_specs(self):
        """Test iterating over registered tool specs."""
        manager = ToolManager(dry_run=False)
        
        spec1 = ToolSpec(
            name="tool1",
            description="Tool 1",
            input_schema={},
            output_schema={},
            cache_ttl_seconds=0,
            allowed_domains=[],
        )
        spec2 = ToolSpec(
            name="tool2",
            description="Tool 2",
            input_schema={},
            output_schema={},
            cache_ttl_seconds=0,
            allowed_domains=[],
        )
        
        manager.register(spec1, AsyncMock())
        manager.register(spec2, AsyncMock())
        
        specs = manager.iter_specs()
        assert len(specs) == 2
        spec_names = [s.name for s in specs]
        assert "tool1" in spec_names
        assert "tool2" in spec_names

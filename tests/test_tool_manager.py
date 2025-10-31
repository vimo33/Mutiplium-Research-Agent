from __future__ import annotations

import pytest

from multiplium.config import ToolConfig
from multiplium.tools.manager import ToolManager


@pytest.mark.asyncio
async def test_tool_manager_dry_run_invokes_stub() -> None:
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

from __future__ import annotations

import pytest

from multiplium.config import ProviderConfig
from multiplium.providers.openai_provider import OpenAIAgentProvider
from multiplium.tools.manager import ToolManager


@pytest.mark.asyncio
async def test_sanitize_json_output_strips_comment_lines() -> None:
    config = ProviderConfig(enabled=True, model="gpt-4.1")
    tool_manager = ToolManager.from_settings([], dry_run=True)
    provider = OpenAIAgentProvider(
        name="openai",
        config=config,
        tool_manager=tool_manager,
        dry_run=True,
    )
    try:
        payload = '{\n  "url": "https://example.com/path"\n  // comment that should be removed\n}'
        cleaned = provider._sanitize_json_output(payload)
    finally:
        await tool_manager.aclose()

    assert "// comment" not in cleaned
    assert "https://example.com/path" in cleaned

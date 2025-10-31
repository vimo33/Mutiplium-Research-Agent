from __future__ import annotations

from typing import Any

import pytest

from servers.clients import search


@pytest.mark.asyncio
async def test_search_perplexity_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(search, "PERPLEXITY_API_KEY", None)

    result = await search._search_perplexity("regenerative viticulture", max_results=3)

    assert result["results"] == []
    assert "Perplexity" in result["note"]


@pytest.mark.asyncio
async def test_search_web_deduplicates_results(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_tavily(**_: Any) -> dict[str, Any]:
        return {
            "results": [
                {"title": "A", "url": "https://example.com/a", "summary": "A summary", "source": "example.com", "published_at": None},
                {"title": "B", "url": "https://example.com/b", "summary": "B summary", "source": "example.com", "published_at": None},
            ]
        }

    async def fake_perplexity(**_: Any) -> dict[str, Any]:
        return {
            "results": [
                {"title": "A duplicate", "url": "https://example.com/a", "summary": "Duplicate", "source": "example.com", "published_at": None},
                {"title": "C", "url": "https://example.com/c", "summary": "C summary", "source": "example.com", "published_at": None},
            ]
        }

    monkeypatch.setattr(search, "_search_tavily", fake_tavily)
    monkeypatch.setattr(search, "_search_perplexity", fake_perplexity)
    monkeypatch.setattr(search, "_search_duckduckgo", fake_perplexity)
    monkeypatch.setattr(search, "TAVILY_API_KEY", "fake-key")
    monkeypatch.setattr(search, "PERPLEXITY_API_KEY", "fake-key")

    result = await search.search_web("regenerative viticulture", max_results=3)

    assert len(result["results"]) == 3
    urls = [item["url"] for item in result["results"]]
    assert urls == ["https://example.com/a", "https://example.com/b", "https://example.com/c"]

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

DUCKDUCKGO_API = "https://api.duckduckgo.com/"


async def search_web(query: str, *, max_results: int = 5, freshness_days: int | None = None) -> dict[str, Any]:
    """Perform a lightweight web search using DuckDuckGo's instant answer API."""

    max_results = max(1, min(max_results, 10))
    params = {
        "q": query,
        "format": "json",
        "no_html": "1",
        "no_redirect": "1",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(DUCKDUCKGO_API, params=params)
    response.raise_for_status()
    payload = response.json()

    results: list[dict[str, Any]] = []

    def _add_result(url: str, text: str) -> None:
        if not url or not text:
            return
        parsed = urlparse(url)
        title = text.split(" - ", 1)[0]
        summary = text
        results.append(
            {
                "title": title,
                "url": url,
                "summary": summary,
                "source": parsed.hostname or "",
                "published_at": None,
            }
        )

    for item in payload.get("Results", []):
        _add_result(item.get("FirstURL", ""), item.get("Text", ""))
        if len(results) >= max_results:
            break

    if len(results) < max_results:
        for topic in payload.get("RelatedTopics", []):
            if "FirstURL" in topic and "Text" in topic:
                _add_result(topic["FirstURL"], topic["Text"])
            elif "Topics" in topic:
                for nested in topic["Topics"]:
                    _add_result(nested.get("FirstURL", ""), nested.get("Text", ""))
            if len(results) >= max_results:
                break

    return {
        "query": query,
        "max_results": max_results,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "results": results[:max_results],
        "note": "DuckDuckGo instant answer API; results may emphasize encyclopedic sources.",
    }


async def fetch_page_content(url: str) -> dict[str, Any]:
    """Fetch page content via HTTP GET, returning text payload and metadata."""

    headers = {"User-Agent": "MultipliumFetcher/0.1"}
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=headers) as client:
        response = await client.get(url)

    content_type = response.headers.get("content-type", "")
    text = response.text

    # Basic sanitization: collapse consecutive whitespace.
    clean_text = re.sub(r"\s+", " ", text).strip()

    return {
        "url": str(url),
        "status_code": response.status_code,
        "content_type": content_type,
        "content": clean_text,
        "charset": response.encoding,
    }

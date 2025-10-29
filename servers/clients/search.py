from __future__ import annotations

import re
import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

DUCKDUCKGO_API = "https://api.duckduckgo.com/"
TAVILY_API = "https://api.tavily.com/search"
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")


async def search_web(query: str, *, max_results: int = 5, freshness_days: int | None = None) -> dict[str, Any]:
    """Perform a lightweight web search using DuckDuckGo's instant answer API."""

    max_results = max(1, min(max_results, 10))
    if TAVILY_API_KEY:
        tavily_payload = await _search_tavily(query=query, max_results=max_results)
        if tavily_payload["results"]:
            return tavily_payload

    params = {
        "q": query,
        "format": "json",
        "no_html": "1",
        "no_redirect": "1",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(DUCKDUCKGO_API, params=params)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        return {
            "query": query,
            "max_results": max_results,
            "results": [],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "note": f"DuckDuckGo request failed: {exc}",
        }
    except Exception as exc:  # pragma: no cover - unexpected transport errors
        return {
            "query": query,
            "max_results": max_results,
            "results": [],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "note": f"DuckDuckGo request encountered unexpected error: {exc}",
        }

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
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=headers) as client:
            response = await client.get(url)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        return {
            "url": str(url),
            "status_code": getattr(exc.response, "status_code", None),
            "content_type": None,
            "content": "",
            "charset": None,
            "error": f"fetch failed: {exc}",
        }
    except Exception as exc:  # pragma: no cover - unexpected transport errors
        return {
            "url": str(url),
            "status_code": None,
            "content_type": None,
            "content": "",
            "charset": None,
            "error": f"fetch encountered unexpected error: {exc}",
        }

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


async def _search_tavily(query: str, *, max_results: int) -> dict[str, Any]:
    payload = {
        "query": query,
        "max_results": max_results,
        "search_depth": "advanced",
    }
    headers = {
        "Authorization": f"Bearer {TAVILY_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(TAVILY_API, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError as exc:
        return {
            "query": query,
            "max_results": max_results,
            "results": [],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "note": f"Tavily request failed: {exc}",
        }

    results: list[dict[str, Any]] = []
    for item in data.get("results", []):
        url = item.get("url")
        if not url:
            continue
        parsed = urlparse(url)
        results.append(
            {
                "title": item.get("title") or parsed.hostname or url,
                "url": url,
                "summary": item.get("content") or item.get("snippet") or "",
                "source": parsed.hostname or "",
                "published_at": item.get("published_at"),
            }
        )

    return {
        "query": query,
        "max_results": max_results,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "results": results[:max_results],
        "note": "Tavily API advanced search results.",
    }

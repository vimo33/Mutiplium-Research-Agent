from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

DUCKDUCKGO_API = "https://api.duckduckgo.com/"
TAVILY_API = "https://api.tavily.com/search"
PERPLEXITY_API = "https://api.perplexity.ai/chat/completions"

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")


async def search_web(query: str, *, max_results: int = 5, freshness_days: int | None = None) -> dict[str, Any]:
    """Aggregate search results across available providers (Tavily, Perplexity, DuckDuckGo)."""

    max_results = max(1, min(max_results, 10))
    aggregated: list[dict[str, Any]] = []
    sources_used: list[str] = []
    provider_hits: dict[str, int] = {"tavily": 0, "perplexity": 0, "duckduckgo": 0}

    if TAVILY_API_KEY:
        tavily_payload = await _search_tavily(query=query, max_results=max_results)
        aggregated.extend(tavily_payload["results"])
        if tavily_payload["results"]:
            sources_used.append("Tavily")
            provider_hits["tavily"] += len(tavily_payload["results"])

    if PERPLEXITY_API_KEY:
        perplexity_payload = await _search_perplexity(query=query, max_results=max_results)
        aggregated.extend(perplexity_payload["results"])
        if perplexity_payload["results"]:
            sources_used.append("Perplexity")
            provider_hits["perplexity"] += len(perplexity_payload["results"])

    if not aggregated:
        duck_payload = await _search_duckduckgo(query=query, max_results=max_results)
        aggregated.extend(duck_payload["results"])
        if duck_payload["results"]:
            sources_used.append("DuckDuckGo")
            provider_hits["duckduckgo"] += len(duck_payload["results"])

    seen_urls: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in aggregated:
        url = item.get("url")
        if not isinstance(url, str):
            continue
        normalized = url.strip()
        if normalized in seen_urls:
            continue
        seen_urls.add(normalized)
        deduped.append(item)
        if len(deduped) >= max_results:
            break

    note = (
        f"Sources used: {', '.join(sources_used)}."
        if sources_used
        else "No search providers returned results; manual follow-up required."
    )

    return {
        "query": query,
        "max_results": max_results,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "results": deduped,
        "note": note,
        "sources": provider_hits,
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
    except Exception as exc:  # pragma: no cover
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
        return {"results": [], "note": f"Tavily request failed: {exc}"}
    except Exception as exc:  # pragma: no cover
        return {"results": [], "note": f"Tavily request encountered unexpected error: {exc}"}

    results: list[dict[str, Any]] = []
    for item in data.get("results", []):
        url = item.get("url")
        if not url:
            continue
        parsed = urlparse(url)
        summary = item.get("content") or item.get("snippet") or ""
        results.append(
            {
                "title": item.get("title") or parsed.hostname or url,
                "url": url,
                "summary": summary[:2000],
                "source": parsed.hostname or "",
                "published_at": item.get("published_at"),
            }
        )

    return {"results": results[:max_results], "note": "Tavily API advanced search results."}


async def _search_perplexity(query: str, *, max_results: int) -> dict[str, Any]:
    if not PERPLEXITY_API_KEY:
        return {"results": [], "note": ""}

    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "sonar-medium-online",
        "messages": [
            {
                "role": "system",
                "content": "Provide concise, well-sourced search results for investment research queries. Include reputable citations.",
            },
            {"role": "user", "content": query},
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(PERPLEXITY_API, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError as exc:
        return {"results": [], "note": f"Perplexity request failed: {exc}"}
    except Exception as exc:  # pragma: no cover
        return {"results": [], "note": f"Perplexity request encountered unexpected error: {exc}"}

    results: list[dict[str, Any]] = []
    citations = data.get("citations") or []
    for item in citations[:max_results]:
        url = item.get("url")
        if not url:
            continue
        parsed = urlparse(url)
        summary = item.get("snippet") or ""
        results.append(
            {
                "title": item.get("title") or parsed.hostname or url,
                "url": url,
                "summary": summary[:2000],
                "source": parsed.hostname or "",
                "published_at": item.get("published_at"),
            }
        )

    if not results:
        choices = data.get("choices") or []
        if choices:
            message = choices[0].get("message", {})
            summary = message.get("content", "")
            results.append(
                {
                    "title": "Perplexity summary",
                    "url": "",
                    "summary": summary[:2000],
                    "source": "perplexity.ai",
                    "published_at": None,
                }
            )

    return {"results": results[:max_results], "note": "Perplexity API search results."}


async def _search_duckduckgo(query: str, *, max_results: int) -> dict[str, Any]:
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
        return {"results": [], "note": f"DuckDuckGo request failed: {exc}"}
    except Exception as exc:  # pragma: no cover
        return {"results": [], "note": f"DuckDuckGo request encountered unexpected error: {exc}"}

    results: list[dict[str, Any]] = []

    def _add_result(url: str, text: str) -> None:
        if not url or not text:
            return
        parsed = urlparse(url)
        title = text.split(" - ", 1)[0]
        summary = text[:2000]
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
        "results": results[:max_results],
        "note": "DuckDuckGo instant answer API; results may emphasize encyclopedic sources.",
    }

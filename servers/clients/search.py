from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

try:  # pragma: no cover - optional import for local dev environments
    from perplexity import Perplexity, PerplexityError  # type: ignore
except ImportError:  # pragma: no cover
    Perplexity = None  # type: ignore[assignment]

    class PerplexityError(Exception):  # type: ignore[override]
        """Fallback exception when perplexity SDK is unavailable."""


DUCKDUCKGO_API = "https://api.duckduckgo.com/"
TAVILY_API = "https://api.tavily.com/search"

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")


async def search_web(
    query: str,
    *,
    max_results: int = 5,
    search_depth: str = "basic",
    include_domains: list[str] | None = None,
    topic: str = "general",
) -> dict[str, Any]:
    """Aggregate search results across Tavily, Perplexity, and DuckDuckGo."""

    max_results = max(1, min(max_results, 10))
    aggregated: list[dict[str, Any]] = []
    sources_used: list[str] = []
    provider_hits: dict[str, int] = {"tavily": 0, "perplexity": 0, "duckduckgo": 0}

    if TAVILY_API_KEY:
        tavily_payload = await _search_tavily(
            query=query,
            max_results=max_results,
            search_depth=search_depth,
            include_domains=include_domains,
            topic=topic,
        )
        aggregated.extend(tavily_payload["results"])
        if tavily_payload["results"]:
            sources_used.append("Tavily")
            provider_hits["tavily"] = len(tavily_payload["results"])

    if PERPLEXITY_API_KEY:
        perplexity_payload = await _search_perplexity(query=query, max_results=max_results)
        aggregated.extend(perplexity_payload["results"])
        if perplexity_payload["results"]:
            sources_used.append("Perplexity")
            provider_hits["perplexity"] = len(perplexity_payload["results"])

    if not aggregated:
        duck_payload = await _search_duckduckgo(query=query, max_results=max_results)
        aggregated.extend(duck_payload["results"])
        if duck_payload["results"]:
            sources_used.append("DuckDuckGo")
            provider_hits["duckduckgo"] = len(duck_payload["results"])

    seen_urls: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in aggregated:
        url = item.get("url")
        if not isinstance(url, str) or not url:
            continue
        normalized = url.strip()
        if normalized in seen_urls:
            continue
        seen_urls.add(normalized)
        deduped.append(item)
        if len(deduped) >= max_results:
            break

    note = f"Sources used: {', '.join(sources_used)}." if sources_used else "No search providers returned results."
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
        return {"url": str(url), "content": "", "error": f"fetch failed: {exc}"}
    except Exception as exc:  # pragma: no cover
        return {"url": str(url), "content": "", "error": f"fetch encountered unexpected error: {exc}"}

    clean_text = re.sub(r"\s+", " ", response.text).strip()
    return {"url": str(url), "content": clean_text}


async def _search_tavily(
    query: str,
    *,
    max_results: int,
    search_depth: str,
    include_domains: list[str] | None,
    topic: str,
) -> dict[str, Any]:
    """Perform a Tavily search with advanced parameters."""

    if not TAVILY_API_KEY:
        return {"results": [], "note": "Tavily API key not configured."}

    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "max_results": max_results,
        "search_depth": "advanced" if search_depth == "advanced" else "basic",
        "include_domains": include_domains or None,
        "topic": topic,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(TAVILY_API, json=payload)
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError as exc:
        return {"results": [], "note": f"Tavily request failed: {exc}"}
    except Exception as exc:  # pragma: no cover
        return {"results": [], "note": f"Tavily request encountered unexpected error: {exc}"}

    results: list[dict[str, Any]] = []
    for item in data.get("results", []) or []:
        url = item.get("url")
        if not url:
            continue
        parsed = urlparse(url)
        results.append(
            {
                "title": item.get("title", "") or parsed.hostname or url,
                "url": url,
                "summary": (item.get("content") or "")[:2000],
                "source": parsed.hostname or "",
                "published_at": item.get("published_at"),
            }
        )
        if len(results) >= max_results:
            break

    return {"results": results, "note": "Tavily API search results."}


async def _search_perplexity(query: str, *, max_results: int) -> dict[str, Any]:
    """Perform a search using the Perplexity Search API."""

    if not PERPLEXITY_API_KEY:
        return {"results": [], "note": "Perplexity API key not configured."}
    if Perplexity is None:
        return {"results": [], "note": "Perplexity client not installed."}

    client: Any | None = None
    try:
        client = Perplexity(api_key=PERPLEXITY_API_KEY)
        search = await client.search.acreate(query=query, max_results=max_results)

        results: list[dict[str, Any]] = []
        for result in getattr(search, "results", []) or []:
            if not result.url:
                continue
            parsed = urlparse(result.url)
            summary = getattr(result, "content", "") or ""
            results.append(
                {
                    "title": result.title or parsed.hostname or result.url,
                    "url": result.url,
                    "summary": summary[:2000],
                    "source": parsed.hostname or "",
                    "published_at": None,
                }
            )
        return {"results": results[:max_results], "note": "Perplexity API search results."}
    except PerplexityError as exc:
        return {"results": [], "note": f"Perplexity request failed: {exc}"}
    except Exception as exc:  # pragma: no cover
        return {"results": [], "note": f"Perplexity request encountered unexpected error: {exc}"}
    finally:
        if client is not None:
            try:
                await client.aclose()  # type: ignore[attr-defined]
            except Exception:
                pass


async def _search_duckduckgo(query: str, *, max_results: int) -> dict[str, Any]:
    """Perform a fallback search using the DuckDuckGo Instant Answer API."""

    params = {"q": query, "format": "json", "no_html": "1", "no_redirect": "1"}
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
        results.append(
            {
                "title": text.split(" - ")[0],
                "url": url,
                "summary": text[:2000],
                "source": parsed.hostname or "",
                "published_at": None,
            }
        )

    for item in payload.get("Results", []) or []:
        _add_result(item.get("FirstURL", ""), item.get("Text", ""))
        if len(results) >= max_results:
            break

    if len(results) < max_results:
        for item in payload.get("RelatedTopics", []) or []:
            if isinstance(item, dict) and "FirstURL" in item:
                _add_result(item.get("FirstURL", ""), item.get("Text", ""))
                if len(results) >= max_results:
                    break

    return {"results": results[:max_results], "note": "DuckDuckGo instant answer API results."}

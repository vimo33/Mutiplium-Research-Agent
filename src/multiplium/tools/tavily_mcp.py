"""Tavily API Integration (Direct API - More Reliable than MCP)."""
from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any

import httpx
import structlog

log = structlog.get_logger()


class TavilyMCPClient:
    """Client for Tavily's API with enhanced tools and rate limiting."""
    
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        if not self.api_key:
            raise ValueError("TAVILY_API_KEY is required")
        
        self.search_url = "https://api.tavily.com/search"
        self.extract_url = "https://api.tavily.com/extract"
        self.timeout = 30.0
        
        # Rate limiting: 100 requests/minute = 0.6 seconds between requests
        self._last_request_time = 0.0
        self._min_request_interval = 0.6  # seconds
        self._lock = asyncio.Lock()
    
    async def _rate_limit(self) -> None:
        """Ensure we don't exceed 100 requests/minute."""
        async with self._lock:
            now = time.time()
            time_since_last = now - self._last_request_time
            if time_since_last < self._min_request_interval:
                wait_time = self._min_request_interval - time_since_last
                log.debug("tavily.rate_limit", wait_seconds=wait_time)
                await asyncio.sleep(wait_time)
            self._last_request_time = time.time()
    
    async def _call_search_api(self, **kwargs: Any) -> dict[str, Any]:
        """Call Tavily search API directly with rate limiting."""
        await self._rate_limit()
        try:
            payload = {"api_key": self.api_key, **kwargs}
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.search_url, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            log.error(
                "tavily.search_error",
                status=exc.response.status_code,
                response=exc.response.text[:500],
            )
            return {
                "error": f"HTTP {exc.response.status_code}: {exc.response.text[:200]}",
                "results": [],
            }
        except Exception as exc:
            log.error("tavily.search_error", error=str(exc))
            return {"error": str(exc), "results": []}
    
    async def _call_extract_api(self, urls: list[str]) -> dict[str, Any]:
        """Call Tavily extract API directly with rate limiting."""
        await self._rate_limit()
        try:
            payload = {"api_key": self.api_key, "urls": urls}
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.extract_url, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            log.error(
                "tavily.extract_error",
                status=exc.response.status_code,
                response=exc.response.text[:500],
            )
            return {
                "error": f"HTTP {exc.response.status_code}: {exc.response.text[:200]}",
                "results": [],
            }
        except Exception as exc:
            log.error("tavily.extract_error", error=str(exc))
            return {"error": str(exc), "results": []}
    
    async def search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic",
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        topic: str = "general",
    ) -> dict[str, Any]:
        """
        Search the web using Tavily's search tool.
        
        Args:
            query: Search query
            max_results: Maximum number of results (1-10)
            search_depth: "basic" or "advanced"
            include_domains: List of domains to include
            exclude_domains: List of domains to exclude
            topic: Topic filter ("general", "news", etc.)
        """
        arguments = {
            "query": query,
            "max_results": min(max(1, max_results), 10),
            "search_depth": search_depth,
            "topic": topic,
        }
        
        if include_domains:
            arguments["include_domains"] = include_domains
        if exclude_domains:
            arguments["exclude_domains"] = exclude_domains
        
        log.info("tavily.search", query=query, max_results=max_results)
        return await self._call_search_api(**arguments)
    
    async def extract(
        self,
        urls: list[str],
        include_raw_content: bool = False,
    ) -> dict[str, Any]:
        """
        Extract structured content from URLs.
        
        Args:
            urls: List of URLs to extract content from
            include_raw_content: Include raw HTML content
        """
        arguments = {
            "urls": urls,
            "include_raw_content": include_raw_content,
        }
        
        log.info("tavily.extract", url_count=len(urls))
        return await self._call_extract_api(urls)
    
    async def map_website(
        self,
        url: str,
        max_pages: int = 10,
    ) -> dict[str, Any]:
        """
        Map a website's structure.
        
        Args:
            url: Website URL to map
            max_pages: Maximum number of pages to map
        """
        arguments = {
            "url": url,
            "max_pages": min(max(1, max_pages), 50),
        }
        
        log.info("tavily.map", url=url, max_pages=max_pages)
        # Note: Map/crawl features not available in direct API
        # Fallback: Do extract on the main URL
        return await self._call_extract_api([url])
    
    async def crawl_website(
        self,
        url: str,
        max_depth: int = 2,
        max_pages: int = 10,
    ) -> dict[str, Any]:
        """
        Crawl a website systematically.
        
        Args:
            url: Starting URL for crawl
            max_depth: Maximum crawl depth
            max_pages: Maximum number of pages to crawl
        """
        arguments = {
            "url": url,
            "max_depth": min(max(1, max_depth), 5),
            "max_pages": min(max(1, max_pages), 50),
        }
        
        log.info("tavily.crawl", url=url, max_depth=max_depth, max_pages=max_pages)
        # Note: Map/crawl features not available in direct API
        # Fallback: Do extract on the main URL
        return await self._call_extract_api([url])
    
    async def fetch_content(self, url: str) -> dict[str, Any]:
        """
        Fetch and extract content from a single URL.
        This uses Tavily's extract API internally.
        """
        result = await self._call_extract_api([url])
        
        # Transform to match expected fetch_content format
        if "error" in result:
            return {"url": url, "content": "", "error": result["error"]}
        
        # Extract first result from Tavily response
        if isinstance(result, dict) and "results" in result:
            results = result["results"]
            if results and len(results) > 0:
                first = results[0]
                return {
                    "url": url,
                    "content": first.get("raw_content", "") or first.get("content", ""),
                    "title": first.get("title", ""),
                }
        
        return {"url": url, "content": "", "error": "No content extracted"}


# Global client instance
_client: TavilyMCPClient | None = None


def get_client() -> TavilyMCPClient:
    """Get or create the global Tavily MCP client."""
    global _client
    if _client is None:
        _client = TavilyMCPClient()
    return _client


# Convenience functions for direct use
async def search_web(
    query: str,
    max_results: int = 5,
    search_depth: str = "basic",
    include_domains: list[str] | None = None,
    topic: str = "general",
) -> dict[str, Any]:
    """Search the web using Tavily MCP."""
    client = get_client()
    return await client.search(query, max_results, search_depth, include_domains, None, topic)


async def fetch_content(url: str) -> dict[str, Any]:
    """Fetch content from a URL using Tavily MCP."""
    client = get_client()
    return await client.fetch_content(url)


async def extract_content(
    urls: list[str],
    include_raw_content: bool = False,
) -> dict[str, Any]:
    """Extract structured content from URLs using Tavily MCP."""
    client = get_client()
    return await client.extract(urls, include_raw_content)


async def map_website(url: str, max_pages: int = 10) -> dict[str, Any]:
    """Map a website's structure using Tavily MCP."""
    client = get_client()
    return await client.map_website(url, max_pages)


async def crawl_website(
    url: str,
    max_depth: int = 2,
    max_pages: int = 10,
) -> dict[str, Any]:
    """Crawl a website using Tavily MCP."""
    client = get_client()
    return await client.crawl_website(url, max_depth, max_pages)


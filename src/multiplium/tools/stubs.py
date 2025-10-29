from __future__ import annotations

from typing import Any

from multiplium.tools.contracts import ToolHandler


async def search_web_stub(query: str, *, max_results: int = 5) -> dict[str, Any]:
    return {
        "tool": "search_web",
        "query": query,
        "max_results": max_results,
        "results": [],
        "note": "Stub search implementation; integrate real web search API.",
    }


async def fetch_content_stub(url: str) -> dict[str, Any]:
    return {
        "tool": "fetch_content",
        "url": url,
        "content": "",
        "note": "Stub content fetch; replace with HTTP client and sanitize output.",
    }


async def crunchbase_stub(company: str) -> dict[str, Any]:
    return {
        "tool": "lookup_crunchbase",
        "company": company,
        "profile": {},
        "note": "Stub Crunchbase lookup; wire to MCP service.",
    }


async def patents_stub(query: str) -> dict[str, Any]:
    return {
        "tool": "lookup_patents",
        "query": query,
        "patents": [],
        "note": "Stub patent search; integrate USPTO or Lens.org API.",
    }


async def financials_stub(company: str) -> dict[str, Any]:
    return {
        "tool": "financial_metrics",
        "company": company,
        "metrics": {},
        "note": "Stub financial metrics lookup; connect to financial data provider.",
    }


STUB_HANDLERS: dict[str, ToolHandler] = {
    "search_web": search_web_stub,
    "fetch_content": fetch_content_stub,
    "lookup_crunchbase": crunchbase_stub,
    "lookup_patents": patents_stub,
    "financial_metrics": financials_stub,
}

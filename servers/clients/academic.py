from __future__ import annotations

from typing import Any

import httpx

OPENALEX_BASE = "https://api.openalex.org/works"
MAILTO = "hello@multiplium.com"


async def search_academic_papers(query: str, *, max_results: int = 5) -> dict[str, Any]:
    """Search for peer-reviewed scientific papers and academic journals."""

    max_results = max(1, min(max_results, 25))
    params = {"search": query, "per-page": max_results, "mailto": MAILTO}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(OPENALEX_BASE, params=params)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        return {
            "query": query,
            "papers": [],
            "note": f"OpenAlex API request failed: {exc}",
        }

    results = payload.get("results", []) if isinstance(payload, dict) else []
    if not results:
        return {"query": query, "papers": [], "note": "No academic papers found."}

    papers: list[dict[str, Any]] = []
    for work in results:
        if not isinstance(work, dict):
            continue
        authors: list[str] = []
        for authorship in work.get("authorships", []) or []:
            if not isinstance(authorship, dict):
                continue
            author = authorship.get("author", {})
            name = author.get("display_name") if isinstance(author, dict) else None
            if name:
                authors.append(name)

        open_access = work.get("open_access", {})
        if not isinstance(open_access, dict):
            open_access = {}

        papers.append(
            {
                "title": work.get("title"),
                "authors": authors,
                "publication_year": work.get("publication_year"),
                "journal": (work.get("host_venue") or {}).get("display_name")
                if isinstance(work.get("host_venue"), dict)
                else None,
                "type": work.get("type"),
                "doi_url": work.get("doi"),
                "open_access_url": open_access.get("oa_url"),
            }
        )

    return {
        "query": query,
        "papers": papers,
        "note": f"Found {len(papers)} papers via OpenAlex API.",
    }

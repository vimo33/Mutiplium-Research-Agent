from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

import httpx

PATENTSVIEW_ENDPOINT = "https://api.patentsview.org/patents/query"


async def search_patents(query: str, *, max_results: int = 10) -> dict[str, Any]:
    """Search USPTO PatentsView for filings matching the query."""

    max_results = max(1, min(max_results, 25))
    q_param = json.dumps({"_text_any": {"patent_title": query}})
    f_param = json.dumps(
        [
            "patent_number",
            "patent_title",
            "patent_date",
            "patent_abstract",
            "assignees",
            "patent_application_number",
        ]
    )
    o_param = json.dumps({"per_page": max_results})

    params = {
        "q": q_param,
        "f": f_param,
        "o": o_param,
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(PATENTSVIEW_ENDPOINT, params=params)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return {
                "query": query,
                "patents": [],
                "note": f"PatentsView request failed: {exc}",
            }
    payload = response.json()

    patents: list[dict[str, Any]] = []
    for patent in payload.get("patents", []):
        assignees = patent.get("assignees") or []
        assignee_names = [a.get("assignee_organization") for a in assignees if a.get("assignee_organization")]
        patents.append(
            {
                "title": patent.get("patent_title"),
                "publication_number": patent.get("patent_number"),
                "assignee": assignee_names[0] if assignee_names else None,
                "url": f"https://patents.google.com/patent/{quote(str(patent.get('patent_number', '') or ''))}",
                "abstract": patent.get("patent_abstract"),
                "publication_date": patent.get("patent_date"),
            }
        )

    return {
        "query": query,
        "patents": patents,
        "note": "Results provided by USPTO PatentsView API.",
    }

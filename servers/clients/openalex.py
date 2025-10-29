from __future__ import annotations

from typing import Any

import httpx

OPENALEX_BASE = "https://api.openalex.org/organizations"


async def lookup_company_profile(company: str) -> dict[str, Any]:
    """Use OpenAlex organizations API to approximate company metadata."""

    params = {"search": company, "per-page": 1}
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(OPENALEX_BASE, params=params)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return {
                "company": company,
                "profile": {},
                "funding_rounds": [],
                "investors": [],
                "note": f"OpenAlex request failed: {exc}",
            }
    data = response.json()

    results = data.get("results") or []
    if not results:
        return {
            "company": company,
            "profile": {},
            "funding_rounds": [],
            "investors": [],
            "note": "No organization match found in OpenAlex.",
        }

    org = results[0]
    profile = {
        "id": org.get("id"),
        "display_name": org.get("display_name"),
        "alternate_names": org.get("display_name_alternatives") or [],
        "homepage_url": org.get("homepage_url"),
        "country_code": org.get("country_code"),
        "type": org.get("type"),
        "summary": org.get("summary"),
        "works_count": org.get("works_count"),
        "cited_by_count": org.get("cited_by_count"),
        "image_url": org.get("image_url"),
    }

    return {
        "company": company,
        "profile": profile,
        "funding_rounds": [],
        "investors": [],
        "note": "Data sourced from OpenAlex organizations API (no funding data available).",
    }

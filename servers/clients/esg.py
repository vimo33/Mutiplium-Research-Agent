from __future__ import annotations

import os
from typing import Any

import httpx

FMP_BASE = "https://financialmodelingprep.com/api/v4"
FMP_SEARCH_BASE = "https://financialmodelingprep.com/api/v3"
FMP_API_KEY = os.getenv("FMP_API_KEY", "demo")


async def lookup_esg_ratings(company: str) -> dict[str, Any]:
    """Retrieve ESG (Environmental, Social, Governance) ratings for a public company."""

    symbol = await _resolve_symbol(company)
    if not symbol:
        return {
            "company": company,
            "symbol": None,
            "esg_data": {},
            "note": f"Could not resolve a stock symbol for '{company}'.",
        }

    params = {"apikey": FMP_API_KEY}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(f"{FMP_BASE}/esg-score/{symbol}", params=params)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        return {
            "company": company,
            "symbol": symbol,
            "esg_data": {},
            "note": f"FMP API request for ESG data failed: {exc}",
        }

    esg_record: dict[str, Any] | None
    if isinstance(payload, list) and payload:
        esg_record = payload[0]
    elif isinstance(payload, dict):
        esg_record = payload
    else:
        esg_record = None

    if not esg_record:
        return {
            "company": company,
            "symbol": symbol,
            "esg_data": {},
            "note": f"No ESG data found for symbol '{symbol}'.",
        }

    return {
        "company": company,
        "symbol": esg_record.get("symbol", symbol),
        "esg_data": {
            "cik": esg_record.get("cik"),
            "company_name": esg_record.get("companyName"),
            "esg_score": esg_record.get("esgScore"),
            "environmental_score": esg_record.get("environmentalScore"),
            "social_score": esg_record.get("socialScore"),
            "governance_score": esg_record.get("governanceScore"),
            "reporting_year": esg_record.get("year"),
            "source": "Financial Modeling Prep API",
        },
        "note": f"Successfully retrieved ESG data for {symbol}.",
    }


async def _resolve_symbol(company: str) -> str | None:
    """Resolve a company name to a ticker symbol using FMP's search."""

    candidate = company.strip().upper()
    if candidate and candidate.isalpha() and len(candidate) <= 5:
        return candidate

    params = {"query": company, "limit": 1, "apikey": FMP_API_KEY}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{FMP_SEARCH_BASE}/search", params=params)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        return None

    if isinstance(payload, list) and payload:
        first = payload[0] or {}
        return first.get("symbol")

    if isinstance(payload, dict):
        return payload.get("symbol")

    return None

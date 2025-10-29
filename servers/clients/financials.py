from __future__ import annotations

import os
from typing import Any

import httpx

FMP_BASE = "https://financialmodelingprep.com/api/v3"
FMP_API_KEY = os.getenv("FMP_API_KEY", "demo")

DEFAULT_METRIC_FIELDS = {
    "price": ("price", "USD"),
    "market_cap": ("marketCap", "USD"),
    "beta": ("beta", None),
    "pe_ratio": ("pe", None),
    "eps": ("eps", "USD"),
    "revenue": ("revenue", "USD"),
    "gross_profit": ("grossProfit", "USD"),
    "52_week_high": ("52WeekHigh", "USD"),
    "52_week_low": ("52WeekLow", "USD"),
}


async def fetch_financial_metrics(
    company: str,
    *,
    metrics: list[str] | None = None,
    period: str | None = None,
) -> dict[str, Any]:
    """Retrieve basic financial metrics using the Financial Modeling Prep API."""

    symbol = await _resolve_symbol(company)
    if symbol is None:
        return {
            "company": company,
            "metrics": {},
            "note": "Unable to resolve company symbol via Financial Modeling Prep search endpoint.",
        }

    profile = await _fetch_profile(symbol)
    if not profile:
        return {
            "company": company,
            "symbol": symbol,
            "metrics": {},
            "note": "No profile data returned from Financial Modeling Prep.",
        }

    metric_keys = _normalize_metrics(metrics) if metrics else list(DEFAULT_METRIC_FIELDS.keys())
    metrics_payload: dict[str, Any] = {}

    for metric_key in metric_keys:
        field, unit = DEFAULT_METRIC_FIELDS.get(metric_key, (metric_key, None))
        value = profile.get(field)
        if value is None:
            continue
        metrics_payload[metric_key] = {
            "value": value,
            "unit": unit,
            "as_of": profile.get("lastDivDate"),
            "source": "Financial Modeling Prep API (demo key)" if FMP_API_KEY == "demo" else "Financial Modeling Prep API",
        }

    return {
        "company": company,
        "symbol": symbol,
        "metrics": metrics_payload,
        "note": f"Values fetched from Financial Modeling Prep profile endpoint using symbol {symbol}.",
    }


async def _resolve_symbol(company: str) -> str | None:
    # Treat obvious ticker symbols directly.
    candidate = company.strip().upper()
    if candidate and candidate.isalpha() and len(candidate) <= 5:
        return candidate

    params = {"query": company, "limit": 1, "apikey": FMP_API_KEY}
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{FMP_BASE}/search", params=params)
    response.raise_for_status()
    data = response.json()
    if not data:
        return None
    return data[0].get("symbol")


async def _fetch_profile(symbol: str) -> dict[str, Any]:
    params = {"apikey": FMP_API_KEY}
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{FMP_BASE}/profile/{symbol}", params=params)
    response.raise_for_status()
    data = response.json()
    if not data:
        return {}
    return data[0]


def _normalize_metrics(metrics: list[str]) -> list[str]:
    normalized: list[str] = []
    for metric in metrics:
        key = metric.lower().replace("-", "_").strip()
        if key in DEFAULT_METRIC_FIELDS:
            normalized.append(key)
    return normalized

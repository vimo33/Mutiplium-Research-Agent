from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from multiplium.providers.base import ProviderRunResult


def write_report(
    output_path: Path,
    *,
    context: Any,
    sector: str,
    provider_results: Iterable[ProviderRunResult],
    deep_research: dict[str, Any] | None = None,
) -> None:
    """Persist agent outputs to disk for analyst review."""

    generated_at = datetime.now(timezone.utc)
    payload = {
        "generated_at": generated_at.isoformat(),
        "sector": sector,
        "thesis": getattr(context, "thesis", ""),
        "value_chain": getattr(context, "value_chain", []),
        "kpis": getattr(context, "kpis", {}),
        "providers": [
            {
                "provider": result.provider,
                "model": result.model,
                "status": result.status,
                "findings": result.findings,
                "telemetry": result.telemetry,
                "tool_summary": result.telemetry.get("tool_summary"),
            }
            for result in provider_results
        ],
    }
    
    # Add deep research data if available
    if deep_research:
        # Enhance stats with 3-layer financial enrichment metrics
        deep_research = _enhance_deep_research_stats(deep_research)
        payload["deep_research"] = deep_research

    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_json = json.dumps(payload, indent=2, ensure_ascii=True)
    output_path.write_text(report_json, encoding="utf-8")

    # Persist timestamped snapshot to reports/new/ folder
    timestamp_suffix = generated_at.strftime("%Y%m%dT%H%M%SZ")
    new_reports_dir = output_path.parent / "new"
    new_reports_dir.mkdir(parents=True, exist_ok=True)
    timestamped_path = new_reports_dir / f"report_{timestamp_suffix}{output_path.suffix}"
    timestamped_path.write_text(report_json, encoding="utf-8")


def _enhance_deep_research_stats(deep_research: dict[str, Any]) -> dict[str, Any]:
    """
    Enhance deep research stats with 3-layer financial enrichment metrics.
    
    Calculates:
    - has_exact_financials: Count of companies with auditable financial data
    - has_estimated_financials: Count of companies with revenue estimates
    - has_funding_data: Count of companies with funding round info
    - has_financial_signals: Count of companies with meaningful financial signals
    - financial_data_coverage_pct: Overall financial data coverage
    """
    companies = deep_research.get("companies", [])
    
    if not companies:
        return deep_research
    
    # Calculate enhanced financial stats
    total = len(companies)
    completed = sum(1 for c in companies if c.get("deep_research_status") == "completed")
    has_team = sum(1 for c in companies if c.get("team"))
    has_competitors = sum(1 for c in companies if c.get("competitors"))
    has_swot = sum(1 for c in companies if c.get("swot"))
    
    # New 3-layer financial stats
    has_exact_financials = 0
    has_estimated_financials = 0
    has_funding_data = 0
    has_financial_signals = 0
    has_any_financial_data = 0
    
    for company in companies:
        enrichment = company.get("financial_enrichment", {})
        
        if not enrichment:
            # Legacy check - old style financial data
            if company.get("financials") and company.get("financials") != "Not Disclosed":
                has_any_financial_data += 1
            continue
        
        # Check exact financials
        exact = enrichment.get("financials_exact")
        if exact and exact.get("years"):
            has_revenue = any(y.get("revenue", 0) > 0 for y in exact["years"])
            if has_revenue:
                has_exact_financials += 1
                has_any_financial_data += 1
                continue  # Already counted
        
        # Check estimated financials
        estimated = enrichment.get("financials_estimated")
        if estimated and estimated.get("revenue_estimate"):
            has_estimated_financials += 1
            has_any_financial_data += 1
            continue  # Already counted
        
        # Check funding rounds
        funding_rounds = enrichment.get("funding_rounds", [])
        if funding_rounds:
            has_funding_data += 1
            has_any_financial_data += 1
            continue  # Already counted
        
        # Check for meaningful signals
        signals = enrichment.get("financial_signals_raw", [])
        meaningful = [
            s for s in signals
            if s.get("type") in ("funding", "revenue", "contract")
            and s.get("confidence_0to1", 0) >= 0.5
        ]
        if len(meaningful) >= 2:
            has_financial_signals += 1
            has_any_financial_data += 1
    
    # Calculate overall data completeness
    # Weight: team=20%, competitors=20%, SWOT=10%, financials=50%
    team_pct = (has_team / total * 100) if total > 0 else 0
    competitors_pct = (has_competitors / total * 100) if total > 0 else 0
    swot_pct = (has_swot / total * 100) if total > 0 else 0
    financial_pct = (has_any_financial_data / total * 100) if total > 0 else 0
    
    data_completeness = (team_pct * 0.2 + competitors_pct * 0.2 + swot_pct * 0.1 + financial_pct * 0.5)
    
    # Update stats
    deep_research["stats"] = {
        "total": total,
        "completed": completed,
        "has_team": has_team,
        "has_competitors": has_competitors,
        "has_swot": has_swot,
        # Legacy field (for backward compatibility)
        "has_financials": has_any_financial_data,
        # New 3-layer financial stats
        "has_exact_financials": has_exact_financials,
        "has_estimated_financials": has_estimated_financials,
        "has_funding_data": has_funding_data,
        "has_financial_signals": has_financial_signals,
        "has_any_financial_data": has_any_financial_data,
        # Percentages
        "financial_data_coverage_pct": round(financial_pct, 1),
        "data_completeness_pct": round(data_completeness, 1),
    }
    
    return deep_research

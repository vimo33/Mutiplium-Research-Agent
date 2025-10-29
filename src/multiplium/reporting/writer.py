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

    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_json = json.dumps(payload, indent=2, ensure_ascii=True)
    output_path.write_text(report_json, encoding="utf-8")

    # Also persist a timestamped snapshot for historical runs.
    timestamp_suffix = generated_at.strftime("%Y%m%dT%H%M%SZ")
    timestamped_path = output_path.parent / f"report_{timestamp_suffix}{output_path.suffix}"
    if timestamped_path != output_path:
        timestamped_path.write_text(report_json, encoding="utf-8")

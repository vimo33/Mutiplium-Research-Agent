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

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
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
            }
            for result in provider_results
        ],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")

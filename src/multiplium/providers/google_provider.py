from __future__ import annotations

import json
import re
from typing import Any

from multiplium.providers.base import BaseAgentProvider, ProviderRunResult


def _default_json(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {k: _default_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_default_json(v) for v in value]
    return str(value)


class GeminiAgentProvider(BaseAgentProvider):
    """Google Gemini integration using the python-genai SDK with automatic function calling."""

    _MIN_COMPANIES = 10

    async def run(self, context: Any) -> ProviderRunResult:
        if self.dry_run:
            findings: list[dict[str, Any]] = [{"note": "Dry run placeholder"}]
            telemetry = {"steps": 0, "notes": "Dry run mode"}
            return ProviderRunResult(
                provider=self.name,
                model=self.config.model,
                status="dry_run",
                findings=findings,
                telemetry=telemetry,
            )

        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:  # pragma: no cover
            return ProviderRunResult(
                provider=self.name,
                model=self.config.model,
                status="dependency_missing",
                findings=[],
                telemetry={"error": str(exc)},
            )

        api_key = self.resolve_api_key("GOOGLE_GENAI_API_KEY")
        if not api_key:
            return ProviderRunResult(
                provider=self.name,
                model=self.config.model,
                status="configuration_error",
                findings=[],
                telemetry={"error": "GOOGLE_GENAI_API_KEY not configured"},
            )

        segment_names = self._extract_segment_names(context)
        if not segment_names:
            return ProviderRunResult(
                provider=self.name,
                model=self.config.model,
                status="configuration_error",
                findings=[],
                telemetry={"error": "No value-chain segments defined for Gemini provider."},
            )

        client = genai.Client(api_key=api_key)
        findings: list[dict[str, Any]] = []
        coverage_details = {
            "segments_total": len(segment_names),
            "segments_with_minimum": 0,
            "minimum_companies": self._MIN_COMPANIES,
            "segments_missing": [],
        }
        total_input_tokens = 0
        total_output_tokens = 0

        google_search_tool = types.Tool(google_search=types.GoogleSearch())

        try:
            for segment_name in segment_names:
                tools = [google_search_tool]

                config = types.GenerateContentConfig(
                    system_instruction=self._build_system_prompt(context, segment_name),
                    temperature=self.config.temperature,
                    tools=tools,
                    response_mime_type="application/json",
                    tool_config=types.ToolConfig(
                        function_calling_config=types.FunctionCallingConfig(
                            mode=types.FunctionCallingConfigMode.AUTO
                        )
                    ),
                )

                contents = [
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_text(
                                text=self._build_segment_user_prompt(segment_name, context)
                            )
                        ],
                    )
                ]

                try:
                    response = await client.aio.models.generate_content(
                        model=self.config.model,
                        contents=contents,
                        config=config,
                    )
                except Exception as exc:  # pragma: no cover
                    findings.append(
                        {
                            "name": segment_name,
                            "companies": [],
                            "notes": [f"Segment run failed: {exc}"],
                        }
                    )
                    coverage_details["segments_missing"].append(
                        {"segment": segment_name, "companies": 0}
                    )
                    continue

                text_output = response.text or ""
                segment_data = self._extract_segment_output(text_output, segment_name)
                companies = segment_data.get("companies", [])

                if len(companies) >= self._MIN_COMPANIES:
                    coverage_details["segments_with_minimum"] += 1
                else:
                    coverage_details["segments_missing"].append(
                        {"segment": segment_name, "companies": len(companies)}
                    )
                    segment_data.setdefault("notes", []).append(
                        f"Segment returned {len(companies)} companies; minimum target is {self._MIN_COMPANIES}."
                    )

                findings.append(segment_data)
                usage_meta = response.usage_metadata or types.GenerateContentResponseUsageMetadata()
                total_input_tokens += getattr(usage_meta, "prompt_token_count", 0)
                total_output_tokens += getattr(usage_meta, "candidates_token_count", 0)

        finally:
            await client.aio.aclose()
            client.close()

        coverage_ok = (
            coverage_details["segments_with_minimum"] == coverage_details["segments_total"]
            and coverage_details["segments_total"] > 0
        )

        telemetry = {
            "tool_calls": 0,
            "tool_usage": {},
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "coverage": coverage_details,
        }
        telemetry["tool_summary"] = self._format_tool_summary(telemetry)

        return ProviderRunResult(
            provider=self.name,
            model=self.config.model,
            status="completed" if coverage_ok else "partial",
            findings=findings,
            telemetry=telemetry,
        )

    def _build_tool_functions(self) -> tuple[list[Callable[..., Awaitable[Any]]], dict[str, int]]:
        counter = {"count": 0}
        functions: list[Callable[..., Awaitable[Any]]] = []

        for spec in self.tool_manager.iter_specs():

            async def _tool_wrapper(*, spec_name=spec.name, **kwargs: Any) -> Any:
                counter["count"] += 1
                return await self.tool_manager.invoke(spec_name, **kwargs)

            _tool_wrapper.__name__ = spec.name  # type: ignore[attr-defined]
            _tool_wrapper.__doc__ = spec.description
            functions.append(_tool_wrapper)

        return functions, counter

    def _build_system_prompt(self, context: Any, segment_name: str) -> str:
        thesis = getattr(context, "thesis", "").strip()
        kpis = _default_json(getattr(context, "kpis", {}))
        return (
            "You are a Gemini-based research analyst collaborating with other LLM agents. "
            "Use the provided tools, including Google Search, to gather verifiable, up-to-date evidence. "
            f"Focus exclusively on the value-chain segment '{segment_name}'. Produce at least ten unique company profiles with supporting citations. "
            "Do not fabricate sources; only cite URLs you have verified."
            f"\n\nInvestment thesis:\n{thesis}"
            f"\n\nKPIs:\n{json.dumps(kpis, indent=2)}"
            "\n\nReturn JSON formatted as:"
            '\n{"segment": {"name": str, "companies": [{"company": str, "summary": str, "kpi_alignment": [str], "sources": [str]}]}}'
        )

    def _build_segment_user_prompt(self, segment_name: str, context: Any) -> str:
        return (
            f"Research the value-chain segment '{segment_name}'. "
            "Use search, document fetch, Crunchbase, patent, and financial tools as needed. "
            f"Produce at least {self._MIN_COMPANIES} unique companies with concise summaries, explicit KPI alignment, and cited sources. "
            "Ensure company names are unique; omit duplicates or generic vendors. Only include companies with clear regenerative viticulture relevance."
        )

    def _extract_segment_output(self, final_text: str, segment_name: str) -> dict[str, Any]:
        if not final_text.strip():
            return {"name": segment_name, "companies": [], "notes": ["Empty response from Gemini."]}

        try:
            data = json.loads(final_text)
        except json.JSONDecodeError:
            return {
                "name": segment_name,
                "companies": [],
                "notes": [f"Unable to parse Gemini output: {final_text}"],
            }

        segment = data.get("segment") if isinstance(data, dict) else None
        if isinstance(segment, dict):
            companies = self._dedupe_companies(segment.get("companies") or [])
            return {
                "name": segment.get("name") or segment_name,
                "companies": companies,
                "notes": segment.get("notes", []),
            }

        return {
            "name": segment_name,
            "companies": [],
            "notes": [f"Unexpected Gemini output structure: {data}"],
        }

    def _extract_segment_names(self, context: Any) -> list[str]:
        value_chain_entries = getattr(context, "value_chain", [])
        full_text_parts: list[str] = []
        for entry in value_chain_entries:
            if isinstance(entry, dict):
                raw = entry.get("raw")
                if isinstance(raw, str):
                    full_text_parts.append(raw)
            elif isinstance(entry, str):
                full_text_parts.append(entry)
        full_text = "\n".join(full_text_parts)

        names: list[str] = []
        for match in re.finditer(r"^##\s*(.+)$", full_text, flags=re.MULTILINE):
            name = match.group(1).strip()
            if name:
                names.append(name)
        return names

    def _dedupe_companies(self, raw_companies: list[dict[str, Any]]) -> list[dict[str, Any]]:
        unique: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in raw_companies:
            if not isinstance(item, dict):
                continue
            name = item.get("company")
            if not isinstance(name, str):
                continue
            normalized = name.strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique.append(item)
        return unique

    def _format_tool_summary(self, telemetry: dict[str, Any]) -> str:
        tool_usage: dict[str, int] = telemetry.get("tool_usage") or {}
        total_tool_calls = telemetry.get("tool_calls", 0)
        coverage_details = telemetry.get("coverage", {})

        parts: list[str] = []
        if tool_usage:
            ordered = sorted(tool_usage.items(), key=lambda item: (-item[1], item[0]))
            parts.append(
                "tool calls: " + ", ".join(f"{name}×{count}" for name, count in ordered)
            )
        else:
            parts.append(f"{total_tool_calls} tool calls")

        deficits = coverage_details.get("segments_missing", [])
        minimum = coverage_details.get("minimum_companies")
        if deficits:
            deficit_text = ", ".join(
                f"{d.get('segment') or 'unknown'} ({d.get('companies', 0)})" for d in deficits
            )
            parts.append(f"segments below target: {deficit_text}")
        elif coverage_details.get("segments_total"):
            parts.append(f"all segments meet ≥{minimum} companies")

        return "; ".join(parts)

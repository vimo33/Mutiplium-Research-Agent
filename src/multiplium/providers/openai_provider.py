from __future__ import annotations

import json
from collections import Counter
import re
from typing import Any, Iterable

from multiplium.providers.base import BaseAgentProvider, ProviderRunResult


def _default_json(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {k: _default_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_default_json(v) for v in value]
    return str(value)


class OpenAIAgentProvider(BaseAgentProvider):
    """OpenAI Agents SDK integration."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._tools_cached: list[Any] | None = None

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
            from agents import Agent, Runner, set_default_openai_key
            from agents.tool import FunctionTool
        except ImportError as exc:  # pragma: no cover
            return ProviderRunResult(
                provider=self.name,
                model=self.config.model,
                status="dependency_missing",
                findings=[],
                telemetry={"error": str(exc)},
            )

        api_key = self.resolve_api_key("OPENAI_API_KEY")
        if not api_key:
            return ProviderRunResult(
                provider=self.name,
                model=self.config.model,
                status="configuration_error",
                findings=[],
                telemetry={"error": "OPENAI_API_KEY not configured"},
            )

        set_default_openai_key(api_key)

        agent = Agent(
            name="OpenAI Investment Researcher",
            instructions=self._build_system_prompt(context),
            model=self.config.model,
            tools=self._build_function_tools(FunctionTool),
        )

        user_prompt = self._build_user_prompt(context)
        run_context = {
            "sector": getattr(context, "sector", None),
            "value_chain": getattr(context, "value_chain", None),
            "kpis": getattr(context, "kpis", None),
        }

        try:
            result = await Runner.run(
                agent,
                user_prompt,
                context=run_context,
                max_turns=self.config.max_steps,
            )
        except Exception as exc:  # pragma: no cover
            return ProviderRunResult(
                provider=self.name,
                model=self.config.model,
                status="runtime_error",
                findings=[],
                telemetry={"error": str(exc)},
            )

        findings = self._extract_findings(result.final_output)
        findings = self._ensure_segment_scaffold(findings, context)
        fallback_stats = await self._ensure_company_coverage(findings, context)
        coverage_ok, coverage_details = self._assess_coverage(findings, minimum=5)

        tool_usage_counts = self._aggregate_tool_usage(result.new_items)
        tool_call_count = (
            sum(tool_usage_counts.values())
            if tool_usage_counts
            else self._count_tool_calls(result.new_items)
        )

        telemetry = {
            "raw_responses": len(result.raw_responses),
            "tool_calls": tool_call_count,
            "tool_usage": tool_usage_counts,
            "output_guardrails": len(result.output_guardrail_results),
            "fallback_companies_added": fallback_stats["added_companies"],
            "coverage": coverage_details,
        }
        telemetry["tool_summary"] = self._format_tool_summary(
            tool_usage_counts,
            fallback_stats["added_companies"],
            tool_call_count,
            coverage_details,
        )

        return ProviderRunResult(
            provider=self.name,
            model=self.config.model,
            status="completed" if coverage_ok else "partial",
            findings=findings,
            telemetry=telemetry,
        )

    def _build_function_tools(self, function_tool_cls: Any) -> list[Any]:
        if self._tools_cached is not None:
            return self._tools_cached

        tools: list[Any] = []
        for spec in self.tool_manager.iter_specs():

            async def _on_invoke(ctx: Any, input_json: str, *, spec_name=spec.name) -> Any:
                data = json.loads(input_json) if input_json else {}
                return await self.tool_manager.invoke(spec_name, **data)

            tool = function_tool_cls(
                name=spec.name,
                description=spec.description,
                params_json_schema=spec.input_schema,
                on_invoke_tool=_on_invoke,
            )
            tools.append(tool)

        self._tools_cached = tools
        return tools

    def _build_system_prompt(self, context: Any) -> str:
        thesis = getattr(context, "thesis", "").strip()
        value_chain = _default_json(getattr(context, "value_chain", []))
        kpis = _default_json(getattr(context, "kpis", {}))
        return (
            "You are a senior investment research analyst working on a deep-dive project. "
            "Use the available tools to gather validated, up-to-date information from trusted sources. "
            "For each value-chain segment, produce at least five company profiles that include KPI alignment and cited sources. "
            "Do not produce a final response until every segment from the provided value-chain list is populated with the minimum number of companies. "
            "If you lack sufficient evidence for a segment, continue researching with tools until you can confidently report."
            f"\n\nInvestment thesis:\n{thesis}"
            f"\n\nValue chain context:\n{json.dumps(value_chain, indent=2)}"
            f"\n\nKPI definitions:\n{json.dumps(kpis, indent=2)}"
            "\n\nOutput JSON strictly matching:"
            '\n{"segments": [{"name": str, "companies": [{"company": str, "summary": str, "kpi_alignment": [str], "sources": [str]}]}]}'
        )

    def _build_user_prompt(self, context: Any) -> str:
        segment_names = self._extract_segment_names(context)
        segment_list = "\n".join(f"- {name}" for name in segment_names) if segment_names else ""
        return (
            "Research each value-chain segment sequentially. "
            "Use tools for search, content retrieval, and quantitative lookups. "
            "Do not stop after covering the first segment—explicitly iterate through every segment in the order provided, verifying each has at least five well-sourced companies before presenting the final JSON. "
            "\n\nSegments to cover:\n"
            f"{segment_list}\n"
            "Return structured JSON with company list, KPI rationale, and source URLs."
        )

    def _extract_findings(self, final_output: Any) -> list[dict[str, Any]]:
        if isinstance(final_output, str):
            try:
                data = json.loads(final_output)
            except json.JSONDecodeError:
                return [{"raw": final_output}]
        elif isinstance(final_output, dict):
            data = final_output
        else:
            return [{"raw": _default_json(final_output)}]

        segments = data.get("segments")
        if isinstance(segments, list):
            return [segment for segment in segments if isinstance(segment, dict)]

        return [{"raw": data}]

    def _count_tool_calls(self, items: Iterable[Any]) -> int:
        try:
            from agents.items import ToolCallItem, ToolCallOutputItem
        except ImportError:  # pragma: no cover
            return 0

        count = 0
        for item in items:
            if isinstance(item, (ToolCallItem, ToolCallOutputItem)):
                count += 1
        return count

    def _aggregate_tool_usage(self, items: Iterable[Any]) -> dict[str, int]:
        try:
            from agents.items import ToolCallItem, ToolCallOutputItem
        except ImportError:  # pragma: no cover
            return {}

        counter: Counter[str] = Counter()
        seen_call_ids: set[object] = set()
        for item in items:
            tool_call = None
            if isinstance(item, ToolCallItem):
                tool_call = getattr(item, "tool_call", None)
            elif isinstance(item, ToolCallOutputItem):
                tool_call = getattr(item, "tool_call", None)

            tool_name = getattr(tool_call, "name", None)
            call_id = getattr(tool_call, "id", None)
            if isinstance(tool_name, str):
                cache_key = call_id if isinstance(call_id, str) else (tool_name, id(tool_call))
                if cache_key in seen_call_ids:
                    continue
                seen_call_ids.add(cache_key)
                counter[tool_name] += 1

        return dict(counter)

    async def _ensure_company_coverage(
        self,
        findings: list[dict[str, Any]],
        context: Any,
        *,
        required: int = 5,
    ) -> dict[str, int]:
        stats = {
            "segments_considered": 0,
            "segments_augmented": 0,
            "added_companies": 0,
            "failures": 0,
        }
        if self.dry_run:
            return stats

        for segment in findings:
            companies = segment.setdefault("companies", [])
            if not isinstance(companies, list):
                segment["companies"] = companies = []

            notes = segment.setdefault("notes", [])
            if not isinstance(notes, list):
                notes = [notes] if notes else []
                segment["notes"] = notes

            current_count = len([c for c in companies if isinstance(c, dict)])
            if current_count >= required:
                continue

            stats["segments_considered"] += 1
            notes.append(
                "Segment is below the 5-company target. Collect additional primary sources before finalizing."
            )
            stats["failures"] += 1

        return stats

    def _ensure_segment_scaffold(
        self,
        findings: list[dict[str, Any]],
        context: Any,
    ) -> list[dict[str, Any]]:
        existing_names = {
            segment.get("name").strip()
            for segment in findings
            if isinstance(segment, dict) and isinstance(segment.get("name"), str)
        }
        segment_names = self._extract_segment_names(context)
        for name in segment_names:
            if name not in existing_names:
                findings.append(
                    {
                        "name": name,
                        "companies": [],
                        "notes": [
                            "Segment scaffolded from value-chain context; awaiting research findings."
                        ],
                    }
                )
                existing_names.add(name)
        return findings

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

        names = []
        for match in re.finditer(r"^##\s*(.+)$", full_text, flags=re.MULTILINE):
            name = match.group(1).strip()
            if name:
                names.append(name)
        return names

    def _normalize_company_name(self, value: Any) -> str:
        if not isinstance(value, str):
            return ""
        return value.strip().lower()

    def _assess_coverage(
        self,
        findings: list[dict[str, Any]],
        *,
        minimum: int,
    ) -> tuple[bool, dict[str, Any]]:
        segments_total = len(findings)
        segments_meeting = 0
        deficits: list[dict[str, Any]] = []

        for segment in findings:
            name = segment.get("name") if isinstance(segment, dict) else ""
            companies = segment.get("companies") if isinstance(segment, dict) else []
            company_count = len(companies) if isinstance(companies, list) else 0

            if company_count >= minimum:
                segments_meeting += 1
            else:
                deficits.append({"segment": name, "companies": company_count})

        coverage_details = {
            "segments_total": segments_total,
            "segments_with_minimum": segments_meeting,
            "minimum_companies": minimum,
            "segments_missing": deficits,
        }
        return segments_meeting == segments_total and segments_total > 0, coverage_details

    def _format_tool_summary(
        self,
        tool_usage: dict[str, int],
        fallback_added: int,
        total_tool_calls: int,
        coverage_details: dict[str, Any],
    ) -> str:
        parts: list[str] = []

        if tool_usage:
            ordered = sorted(tool_usage.items(), key=lambda item: (-item[1], item[0]))
            parts.append(
                "tool calls: " + ", ".join(f"{name}×{count}" for name, count in ordered)
            )
        else:
            parts.append(f"{total_tool_calls} tool calls")

        if fallback_added:
            parts.append(f"fallback added {fallback_added} companies via search_web")

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

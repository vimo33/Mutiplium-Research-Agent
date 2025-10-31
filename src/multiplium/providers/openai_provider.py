from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, TypedDict, cast

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

    _MIN_COMPANIES = 10

    class SegmentDeficit(TypedDict):
        segment: str
        companies: int

    class CoverageDetails(TypedDict):
        segments_total: int
        segments_with_minimum: int
        minimum_companies: int
        segments_missing: list["OpenAIAgentProvider.SegmentDeficit"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._tools_cached: list[Any] | None = None
        self._seed_companies_cache: dict[str, list[dict[str, Any]]] | None = None

    async def run(self, context: Any) -> ProviderRunResult:
        if self.dry_run:
            placeholder_findings = [{"note": "Dry run placeholder"}]
            telemetry = {"steps": 0, "notes": "Dry run mode"}
            return ProviderRunResult(
                provider=self.name,
                model=self.config.model,
                status="dry_run",
                findings=placeholder_findings,
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

        segment_names = self._extract_segment_names(context)
        if not segment_names:
            return ProviderRunResult(
                provider=self.name,
                model=self.config.model,
                status="configuration_error",
                findings=[],
                telemetry={"error": "No segments defined in value-chain context."},
            )

        seed_map = self._load_seed_companies()
        findings: list[dict[str, Any]] = []
        total_raw_responses = 0
        total_tool_calls = 0
        total_guardrails = 0
        usage_counter: Counter[str] = Counter()
        segments_missing: list[OpenAIAgentProvider.SegmentDeficit] = []
        coverage_details: OpenAIAgentProvider.CoverageDetails = {
            "segments_total": len(segment_names),
            "segments_with_minimum": 0,
            "minimum_companies": self._MIN_COMPANIES,
            "segments_missing": segments_missing,
        }

        for segment_name in segment_names:
            seed_entries = seed_map.get(segment_name, [])
            agent = Agent(
                name="OpenAI Investment Researcher",
                instructions=self._build_system_prompt(context, segment_name, seed_entries),
                model=self.config.model,
                tools=self._build_function_tools(FunctionTool),
            )

            user_prompt = self._build_segment_user_prompt(segment_name, context, seed_entries)
            run_context = {
                "segment": segment_name,
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

            segment_data = self._extract_segment_output(result.final_output, segment_name, seed_entries)
            if not segment_data.get("companies"):
                notes = cast(list[str], segment_data.setdefault("notes", []))
                notes.append(
                    "Segment is below the 5-company target. Collect additional primary sources before finalizing."
                )
                coverage_details["segments_missing"].append(
                    {"segment": segment_name, "companies": 0}
                )
            else:
                coverage_details["segments_with_minimum"] += int(
                    len(segment_data["companies"]) >= self._MIN_COMPANIES
                )
                if len(segment_data["companies"]) < self._MIN_COMPANIES:
                    coverage_details["segments_missing"].append(
                        {
                            "segment": segment_name,
                            "companies": len(segment_data["companies"]),
                        }
                    )
                    notes = cast(list[str], segment_data.setdefault("notes", []))
                    notes.append(
                        f"Segment returned {len(segment_data['companies'])} companies; minimum target is {self._MIN_COMPANIES}."
                    )

            findings.append(segment_data)
            total_raw_responses += len(result.raw_responses)
            run_usage = self._aggregate_tool_usage(result.new_items)
            if run_usage:
                usage_counter.update(run_usage)
                total_tool_calls += sum(run_usage.values())
            else:
                total_tool_calls += self._count_tool_calls(result.new_items)
            total_guardrails += len(result.output_guardrail_results)

        coverage_ok = (
            coverage_details["segments_with_minimum"] == coverage_details["segments_total"]
            and coverage_details["segments_total"] > 0
        )

        telemetry = {
            "raw_responses": total_raw_responses,
            "tool_calls": total_tool_calls,
            "tool_usage": dict(usage_counter),
            "output_guardrails": total_guardrails,
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

    def _build_system_prompt(
        self,
        context: Any,
        segment_name: str,
        seed_companies: list[dict[str, Any]],
    ) -> str:
        thesis = getattr(context, "thesis", "").strip()
        value_chain = _default_json(getattr(context, "value_chain", []))
        kpis = _default_json(getattr(context, "kpis", {}))
        seed_section = ""
        if seed_companies:
            seed_section = (
                "\n\nValidated vineyard companies to treat as high-confidence seeds:\n"
                + json.dumps(seed_companies, indent=2)
            )
        return (
            "You are a senior investment research analyst working on a deep-dive project. "
            "Use the available tools to gather validated, up-to-date information from trusted sources. "
            f"Focus exclusively on the value-chain segment '{segment_name}'. Produce at least ten unique company profiles that include KPI alignment and cited sources. "
            "Do not finish until you have assembled a well-supported list for this segment. "
            "If you lack sufficient evidence, continue researching with tools until you can confidently report."
            f"\n\nInvestment thesis:\n{thesis}"
            f"\n\nValue chain context:\n{json.dumps(value_chain, indent=2)}"
            f"\n\nKPI definitions:\n{json.dumps(kpis, indent=2)}"
            f"{seed_section}"
            "\n\nOutput JSON strictly matching:"
            '\n{"segment": {"name": str, "companies": [{"company": str, "summary": str, "kpi_alignment": [str], "sources": [str]}]}}'
        )

    def _build_segment_user_prompt(
        self,
        segment_name: str,
        context: Any,
        seed_companies: list[dict[str, Any]],
    ) -> str:
        seed_note = ""
        if seed_companies:
            names = ", ".join(company.get("company", "") for company in seed_companies)
            seed_note = (
                " You already have high-confidence vineyard deployments for the following companies: "
                f"{names}. Verify their evidence and build upon them with new, non-duplicate findings."
            )
        return (
            f"Research the value-chain segment '{segment_name}'. "
            "Use registered tools (`search_web`, `fetch_content`, `lookup_crunchbase`, `lookup_patents`, `financial_metrics`) to gather trustworthy evidence for at least ten distinct companies. "
            "Ensure company names are unique and remove duplicates before responding. "
            "For each company, capture a concise summary, explicit KPI alignment, and cite primary + independent sources." + seed_note +
            "\nReturn JSON exactly in the form:\n"
            '{"segment": {"name": "<segment_name>", "companies": [{"company": str, "summary": str, "kpi_alignment": [str], "sources": [str]}]}}'
        )

    def _extract_segment_output(
        self,
        final_output: Any,
        segment_name: str,
        seed_companies: list[dict[str, Any]],
    ) -> dict[str, Any]:
        data: Any
        if isinstance(final_output, str):
            try:
                cleaned = self._sanitize_json_output(final_output)
                data = json.loads(cleaned)
            except json.JSONDecodeError:
                return {
                    "name": segment_name,
                    "companies": [],
                    "notes": [f"Unable to parse segment output: {final_output}"],
                }
        elif isinstance(final_output, dict):
            data = final_output
        else:
            return {
                "name": segment_name,
                "companies": [],
                "notes": [f"Unexpected segment output type: {type(final_output).__name__}"],
            }

        segment = data.get("segment") if isinstance(data, dict) else None
        if isinstance(segment, dict):
            name = segment.get("name") or segment_name
            companies = self._dedupe_companies(segment.get("companies") or [])
            companies = self._merge_seed_companies(companies, seed_companies)
            return {
                "name": name,
                "companies": companies,
                "notes": segment.get("notes", []),
            }

        return {
            "name": segment_name,
            "companies": [],
            "notes": [f"Agent returned unexpected payload: {data}"],
        }

    def _sanitize_json_output(self, payload: str) -> str:
        """Strip inline comments or trailing guidance the agent sometimes appends."""
        lines = []
        for line in payload.splitlines():
            if re.match(r"^\s*//", line):
                continue
            lines.append(line)
        return "\n".join(lines)

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
        """Return a canonical form suitable for equality comparisons."""
        if not isinstance(value, str):
            return ""
        normalized = value.strip().lower()
        normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
        return re.sub(r"\s+", " ", normalized).strip()

    def _dedupe_company_name(self, value: Any) -> str:
        return self._normalize_company_name(value)

    def _dedupe_companies(self, raw_companies: list[dict[str, Any]]) -> list[dict[str, Any]]:
        unique: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in raw_companies:
            if not isinstance(item, dict):
                continue
            normalized = self._dedupe_company_name(item.get("company"))
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique.append(item)
        return unique

    def _load_seed_companies(self) -> dict[str, list[dict[str, Any]]]:
        if self._seed_companies_cache is not None:
            return self._seed_companies_cache

        path = Path(__file__).resolve().parents[3] / "seed_companies.json"
        if not path.exists():
            self._seed_companies_cache = {}
            return self._seed_companies_cache

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {}

        if not isinstance(data, dict):
            data = {}

        normalised: dict[str, list[dict[str, Any]]] = {}
        for key, value in data.items():
            if isinstance(key, str) and isinstance(value, list):
                normalised[key] = [entry for entry in value if isinstance(entry, dict)]

        self._seed_companies_cache = normalised
        return self._seed_companies_cache

    def _merge_seed_companies(
        self,
        companies: list[dict[str, Any]],
        seeds: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not seeds:
            return companies

        seen = {self._normalize_company_name(item.get("company")) for item in companies if isinstance(item, dict)}
        for seed in seeds:
            if not isinstance(seed, dict):
                continue
            normalized = self._normalize_company_name(seed.get("company"))
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            companies.append(seed)
        return companies

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

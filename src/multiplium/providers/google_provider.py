from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any, TypedDict, cast

from multiplium.providers.base import BaseAgentProvider, ProviderRunResult


def _default_json(value: Any) -> Any:
    """Helper to serialize non-standard JSON types to strings."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {k: _default_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_default_json(v) for v in value]
    return str(value)


class GeminiAgentProvider(BaseAgentProvider):
    """Google Gemini integration using the google-genai SDK with full tool support."""

    _MIN_COMPANIES = 10

    class SegmentDeficit(TypedDict):
        segment: str
        companies: int

    class CoverageDetails(TypedDict):
        segments_total: int
        segments_with_minimum: int
        minimum_companies: int
        segments_missing: list["GeminiAgentProvider.SegmentDeficit"]

    async def run(self, context: Any) -> ProviderRunResult:
        if self.dry_run:
            return ProviderRunResult(
                provider=self.name,
                model=self.config.model,
                status="dry_run",
                findings=[{"note": "Dry run placeholder"}],
                telemetry={"steps": 0, "notes": "Dry run mode", "tool_summary": "Dry run"},
            )

        try:
            from google import genai
            from google.genai import types
            from google.generative_ai.types import FunctionDeclaration  # type: ignore[import-untyped]
        except ImportError as exc:  # pragma: no cover
            return ProviderRunResult(
                provider=self.name,
                model=self.config.model,
                status="dependency_missing",
                findings=[],
                telemetry={"error": str(exc), "tool_summary": "Dependency missing"},
            )

        api_key = (
            self.resolve_api_key("GOOGLE_GENAI_API_KEY")
            or self.resolve_api_key("GOOGLE_API_KEY")
            or self.resolve_api_key("GEMINI_API_KEY")
        )
        if not api_key:
            return ProviderRunResult(
                provider=self.name,
                model=self.config.model,
                status="configuration_error",
                findings=[],
                telemetry={"error": "API key not configured", "tool_summary": "API key missing"},
            )

        segment_names = self._extract_segment_names(context)
        if not segment_names:
            return ProviderRunResult(
                provider=self.name,
                model=self.config.model,
                status="configuration_error",
                findings=[],
                telemetry={"error": "No value-chain segments defined.", "tool_summary": "No segments"},
            )

        http_options = types.HttpOptions(api_version="v1beta1")
        client = cast(Any, genai.Client(api_key=api_key, http_options=http_options))

        findings: list[dict[str, Any]] = []
        tool_usage: Counter[str] = Counter()
        total_input_tokens = 0
        total_output_tokens = 0

        segments_missing: list[GeminiAgentProvider.SegmentDeficit] = []
        coverage_details: GeminiAgentProvider.CoverageDetails = {
            "segments_total": len(segment_names),
            "segments_with_minimum": 0,
            "minimum_companies": self._MIN_COMPANIES,
            "segments_missing": segments_missing,
        }

        try:
            for segment_name in segment_names:
                system_prompt = self._build_system_prompt(context, segment_name)
                user_prompt = self._build_segment_user_prompt(segment_name, context)

                mcp_tools = self._build_mcp_tools(FunctionDeclaration)
                google_search_tool = types.Tool(google_search=types.GoogleSearch())
                tools = mcp_tools + [google_search_tool]

                conversation: list[types.Content] = [
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=user_prompt)],
                    )
                ]

                final_response_text: str | None = None

                for _ in range(self.config.max_steps):
                    response = await client.aio.responses.generate_content(
                        model=self.config.model,
                        contents=conversation,
                        system_instruction=system_prompt,
                        tools=tools,
                        generation_config=types.GenerationConfig(
                            temperature=self.config.temperature,
                            response_mime_type="application/json",
                        ),
                    )

                    usage_meta = getattr(response, "usage_metadata", None)
                    if usage_meta is not None:
                        total_input_tokens += getattr(usage_meta, "prompt_token_count", 0)
                        total_output_tokens += getattr(usage_meta, "candidates_token_count", 0)

                    candidate = response.candidates[0] if getattr(response, "candidates", None) else None
                    if candidate is not None and candidate.content is not None:
                        conversation.append(candidate.content)

                    function_calls = response.function_calls or []
                    if not function_calls:
                        final_response_text = response.text or ""
                        break

                    tool_responses: list[types.Content] = []
                    for function_call in function_calls:
                        tool_usage[function_call.name] += 1
                        args = dict(function_call.args or {})
                        tool_result = await self.tool_manager.invoke(function_call.name, **args)
                        tool_responses.append(
                            types.Content(
                                role="tool",
                                parts=[
                                    types.Part.from_function_response(
                                        name=function_call.name,
                                        response={"result": json.dumps(tool_result, default=_default_json)},
                                    )
                                ],
                            )
                        )

                    conversation.extend(tool_responses)

                segment_text = final_response_text or ""
                segment_data = self._extract_segment_output(segment_text, segment_name)
                companies = segment_data.get("companies", [])

                if len(companies) >= self._MIN_COMPANIES:
                    coverage_details["segments_with_minimum"] += 1
                else:
                    segments_missing.append({"segment": segment_name, "companies": len(companies)})
                    notes = segment_data.setdefault("notes", [])
                    if isinstance(notes, list):
                        notes.append(
                            f"Segment returned {len(companies)} companies; minimum target is {self._MIN_COMPANIES}."
                        )

                findings.append(segment_data)

        finally:
            try:
                client.close()
            except Exception:  # pragma: no cover
                pass

        coverage_ok = (
            coverage_details["segments_total"] > 0
            and coverage_details["segments_with_minimum"] == coverage_details["segments_total"]
        )
        telemetry = {
            "tool_calls": sum(tool_usage.values()),
            "tool_usage": dict(tool_usage),
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

    def _build_mcp_tools(self, function_declaration_cls: Any) -> list[Any]:
        """Builds a list of Gemini-compatible FunctionDeclaration tools from the tool manager."""
        tool_declarations: list[Any] = []
        for spec in self.tool_manager.iter_specs():
            tool_declarations.append(
                function_declaration_cls(
                    name=spec.name,
                    description=spec.description,
                    parameters=spec.input_schema,
                )
            )
        return tool_declarations

    def _build_system_prompt(self, context: Any, segment_name: str) -> str:
        """Builds the main system prompt with impact investment focus."""
        thesis = getattr(context, "thesis", "").strip()
        kpis = _default_json(getattr(context, "kpis", {}))
        return (
            "You are an analyst for an **impact investment** fund. Your primary objective is to identify companies "
            "that not only have strong business potential but also generate positive, measurable environmental and social impact. "
            "Strictly adhere to the KPI framework, giving higher weight to impact-related KPIs like 'Soil Carbon Sequestration' "
            "and 'Pesticide Reduction' over purely operational metrics. "
            "If a company has strong financial indicators but lacks verifiable impact evidence (Tier 1 or Tier 2 sources), "
            "you must flag it as 'Low Confidence' or exclude it. "
            f"Your current task is to research the value-chain segment '{segment_name}'. "
            "Use the integrated Google Search tool for broad, real-time information and the other provided tools for specific data lookups. "
            "Do not fabricate sources; only cite URLs you have verified."
            f"\n\nInvestment thesis:\n{thesis}"
            f"\n\nKPIs:\n{json.dumps(kpis, indent=2)}"
            "\n\nAfter completing your research, return a final JSON object formatted as:"
            '\n```json\n{"segment": {"name": str, "companies": [{"company": str, "summary": str, "kpi_alignment": [str], "sources": [str]}]}}\n```'
        )

    def _build_segment_user_prompt(self, segment_name: str, context: Any) -> str:
        """Builds the initial user prompt to kick off research for a segment."""
        return (
            f"Execute a full research workflow for the value-chain segment '{segment_name}'. "
            "Use the available tools to gather trustworthy evidence for at least ten distinct companies. "
            "Ensure company names are unique and remove duplicates. For each company, provide a concise summary, explicit KPI alignment, and cite all sources."
        )

    def _extract_segment_output(self, final_text: str, segment_name: str) -> dict[str, Any]:
        """Parses the final JSON output from the model's text response."""
        if not final_text.strip():
            return {"name": segment_name, "companies": [], "notes": ["Empty response from Gemini."]}

        match = re.search(r"```json\s*(\{.*\})\s*```", final_text, re.DOTALL)
        json_str = match.group(1) if match else final_text

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return {
                "name": segment_name,
                "companies": [],
                "notes": [f"Unable to parse Gemini output: {final_text}"],
            }

        segment = data.get("segment") if isinstance(data, dict) else None
        if isinstance(segment, dict):
            companies = self._dedupe_companies(segment.get("companies") or [])
            notes = segment.get("notes", [])
            return {
                "name": segment.get("name") or segment_name,
                "companies": companies,
                "notes": notes if isinstance(notes, list) else [str(notes)],
            }

        return {
            "name": segment_name,
            "companies": [],
            "notes": [f"Unexpected Gemini output structure: {data}"],
        }

    def _extract_segment_names(self, context: Any) -> list[str]:
        """Extracts segment names from the value_chain context."""
        value_chain_entries = getattr(context, "value_chain", [])
        full_text_parts: list[str] = []
        for entry in value_chain_entries:
            raw = entry.get("raw") if isinstance(entry, dict) else entry
            if isinstance(raw, str):
                full_text_parts.append(raw)
        full_text = "\n".join(full_text_parts)

        names: list[str] = re.findall(r"^##\s*(.+)$", full_text, flags=re.MULTILINE)
        return [name.strip() for name in names if name.strip()]

    def _dedupe_companies(self, raw_companies: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Deduplicates a list of company dictionaries based on a normalized name."""
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
        """Creates a human-readable summary of tool usage and coverage."""
        tool_usage: dict[str, int] = telemetry.get("tool_usage") or {}
        coverage_details = telemetry.get("coverage", {})
        parts: list[str] = []

        if tool_usage:
            ordered = sorted(tool_usage.items(), key=lambda item: (-item[1], item[0]))
            parts.append("tool calls: " + ", ".join(f"{name}×{count}" for name, count in ordered))
        else:
            parts.append(f"{telemetry.get('tool_calls', 0)} tool calls")

        deficits = coverage_details.get("segments_missing", [])
        if deficits:
            deficit_text = ", ".join(
                f"{d.get('segment', 'unknown')} ({d.get('companies', 0)})" for d in deficits
            )
            parts.append(f"segments below target: {deficit_text}")
        elif coverage_details.get("segments_total"):
            parts.append(f"all segments meet ≥{coverage_details.get('minimum_companies')} companies")

        return "; ".join(parts)

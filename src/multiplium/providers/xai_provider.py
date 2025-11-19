"""xAI Grok provider integration."""
from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any, TypedDict, cast

from multiplium.providers.base import BaseAgentProvider, ProviderRunResult


def _default_json(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {k: _default_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_default_json(v) for v in value]
    return str(value)


class XAIAgentProvider(BaseAgentProvider):
    """xAI Grok integration using OpenAI-compatible API."""

    _MIN_COMPANIES = 10

    class SegmentDeficit(TypedDict):
        segment: str
        companies: int

    class CoverageDetails(TypedDict):
        segments_total: int
        segments_with_minimum: int
        minimum_companies: int
        segments_missing: list["XAIAgentProvider.SegmentDeficit"]

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
            from openai import AsyncOpenAI
        except ImportError as exc:  # pragma: no cover
            return ProviderRunResult(
                provider=self.name,
                model=self.config.model,
                status="dependency_missing",
                findings=[],
                telemetry={"error": str(exc), "tool_summary": "Dependency missing"},
            )

        api_key = self.resolve_api_key("XAI_API_KEY")
        if not api_key:
            return ProviderRunResult(
                provider=self.name,
                model=self.config.model,
                status="configuration_error",
                findings=[],
                telemetry={"error": "XAI_API_KEY not configured", "tool_summary": "API key missing"},
            )

        # xAI uses OpenAI-compatible API
        client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.x.ai/v1",
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

        findings: list[dict[str, Any]] = []
        tool_usage: Counter[str] = Counter()
        total_input_tokens = 0
        total_output_tokens = 0

        segments_missing: list[XAIAgentProvider.SegmentDeficit] = []
        coverage_details: XAIAgentProvider.CoverageDetails = {
            "segments_total": len(segment_names),
            "segments_with_minimum": 0,
            "minimum_companies": self._MIN_COMPANIES,
            "segments_missing": segments_missing,
        }

        # Build tools for Grok
        tools = self._build_function_tools()

        try:
            for segment_name in segment_names:
                system_prompt = self._build_system_prompt(context, segment_name)
                user_prompt = self._build_segment_user_prompt(segment_name)

                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]

                final_response_text: str | None = None
                conversation_turns = 0

                for _ in range(self.config.max_steps):
                    conversation_turns += 1
                    
                    response = await client.chat.completions.create(
                        model=self.config.model,
                        messages=messages,
                        tools=tools if tools else None,  # type: ignore[arg-type]
                        temperature=self.config.temperature,
                    )

                    if response.usage:
                        total_input_tokens += response.usage.prompt_tokens or 0
                        total_output_tokens += response.usage.completion_tokens or 0

                    choice = response.choices[0] if response.choices else None
                    if not choice or not choice.message:
                        break

                    message = choice.message
                    messages.append(cast(Any, message))

                    # Check for tool calls
                    if message.tool_calls:
                        tool_results = []
                        for tool_call in message.tool_calls:
                            tool_usage[tool_call.function.name] += 1
                            try:
                                args = json.loads(tool_call.function.arguments)
                            except json.JSONDecodeError:
                                args = {}
                            
                            result = await self.tool_manager.invoke(tool_call.function.name, **args)
                            tool_results.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": json.dumps(result, default=_default_json),
                            })
                        
                        messages.extend(tool_results)
                        continue

                    # No tool calls, agent is done
                    final_response_text = message.content or ""
                    break

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
            await client.close()

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

    def _build_function_tools(self) -> list[dict[str, Any]]:
        """Build OpenAI-compatible tool definitions from MCP specs."""
        tools: list[dict[str, Any]] = []
        for spec in self.tool_manager.iter_specs():
            tools.append({
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.input_schema,
                },
            })
        return tools

    def _build_system_prompt(self, context: Any, segment_name: str) -> str:
        thesis = getattr(context, "thesis", "").strip()
        kpis = _default_json(getattr(context, "kpis", {}))
        return (
            "You are Grok, an AI analyst for an **impact investment** fund with access to real-time X/Twitter data. "
            "Your primary objective is to identify companies that generate positive environmental and social impact "
            "while maintaining strong business fundamentals. "
            "Use your unique access to real-time social sentiment and news to uncover emerging companies and controversies. "
            "Prioritize impact-related KPIs like 'Soil Carbon Sequestration' and 'Pesticide Reduction'. "
            "Flag companies lacking verifiable impact evidence (Tier 1 or Tier 2 sources) as 'Low Confidence'. "
            f"Focus on the value-chain segment '{segment_name}'. "
            "Use available tools to gather trustworthy evidence for at least ten distinct companies. "
            f"\n\nInvestment thesis:\n{thesis}"
            f"\n\nKPIs:\n{json.dumps(kpis, indent=2)}"
            "\n\nReturn JSON formatted as:"
            '\n{"segment": {"name": str, "companies": [{"company": str, "summary": str, "kpi_alignment": [str], "sources": [str]}]}}'
        )

    def _build_segment_user_prompt(self, segment_name: str) -> str:
        return (
            f"Research the value-chain segment '{segment_name}'. "
            "Use registered tools to gather evidence for at least ten distinct companies. "
            "Leverage your real-time knowledge to identify recent ESG news, social sentiment, and emerging startups. "
            "Ensure company names are unique. For each company, provide a summary, KPI alignment, and cited sources."
        )

    def _extract_segment_output(self, final_text: str, segment_name: str) -> dict[str, Any]:
        if not final_text.strip():
            return {"name": segment_name, "companies": [], "notes": ["Empty response from Grok."]}

        # Try to extract JSON from markdown code blocks
        match = re.search(r"```json\s*(\{.*\})\s*```", final_text, re.DOTALL)
        json_str = match.group(1) if match else final_text

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return {
                "name": segment_name,
                "companies": [],
                "notes": [f"Unable to parse Grok output: {final_text[:200]}..."],
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
            "notes": [f"Unexpected Grok output structure: {str(data)[:200]}..."],
        }

    def _extract_segment_names(self, context: Any) -> list[str]:
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


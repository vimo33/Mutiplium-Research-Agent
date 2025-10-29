from __future__ import annotations

import json
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
        telemetry = {
            "raw_responses": len(result.raw_responses),
            "tool_calls": self._count_tool_calls(result.new_items),
            "output_guardrails": len(result.output_guardrail_results),
        }
        return ProviderRunResult(
            provider=self.name,
            model=self.config.model,
            status="completed",
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
            "For each value-chain segment, produce 3-5 company profiles that include KPI alignment and cited sources. "
            "Do not produce a final response until every segment from the provided value-chain list is populated with the minimum number of companies. "
            "If you lack sufficient evidence for a segment, continue researching with tools until you can confidently report."
            f"\n\nInvestment thesis:\n{thesis}"
            f"\n\nValue chain context:\n{json.dumps(value_chain, indent=2)}"
            f"\n\nKPI definitions:\n{json.dumps(kpis, indent=2)}"
            "\n\nOutput JSON strictly matching:"
            '\n{"segments": [{"name": str, "companies": [{"company": str, "summary": str, "kpi_alignment": [str], "sources": [str]}]}]}'
        )

    def _build_user_prompt(self, context: Any) -> str:
        return (
            "Research each value-chain segment sequentially. "
            "Use tools for search, content retrieval, and quantitative lookups. "
            "Do not stop after covering the first segment—explicitly iterate through every segment in the order provided, verifying each has at least three well-sourced companies before presenting the final JSON. "
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

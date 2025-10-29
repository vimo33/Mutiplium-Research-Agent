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


class ClaudeAgentProvider(BaseAgentProvider):
    """Anthropic Claude integration using the Messages API with tool support."""

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
            import anthropic
        except ImportError as exc:  # pragma: no cover
            return ProviderRunResult(
                provider=self.name,
                model=self.config.model,
                status="dependency_missing",
                findings=[],
                telemetry={"error": str(exc)},
            )

        api_key = self.resolve_api_key("ANTHROPIC_API_KEY")
        if not api_key:
            return ProviderRunResult(
                provider=self.name,
                model=self.config.model,
                status="configuration_error",
                findings=[],
                telemetry={"error": "ANTHROPIC_API_KEY not configured"},
            )

        client = anthropic.AsyncAnthropic(api_key=api_key)
        specs = list(self.tool_manager.iter_specs())
        tool_names = {spec.name for spec in specs}
        tools = [
            {
                "name": spec.name,
                "description": spec.description,
                "input_schema": spec.input_schema,
            }
            for spec in specs
        ]

        system_prompt = self._build_system_prompt(context)
        user_prompt = self._build_user_prompt(context)

        messages: list[dict[str, Any]] = [{"role": "user", "content": user_prompt}]
        tool_calls = 0
        final_text: str | None = None
        usage = {"input_tokens": 0, "output_tokens": 0}

        try:
            for _ in range(self.config.max_steps):
                response = await client.messages.create(
                    model=self.config.model,
                    system=system_prompt,
                    messages=messages,
                    tools=tools or anthropic.NOT_GIVEN,
                    temperature=self.config.temperature,
                    max_tokens=4096,
                )

                usage["input_tokens"] += getattr(response.usage, "input_tokens", 0)
                usage["output_tokens"] += getattr(response.usage, "output_tokens", 0)

                assistant_blocks = [block.model_dump() for block in response.content]
                messages.append({"role": "assistant", "content": assistant_blocks})

                pending_tools = []
                for block in response.content:
                    block_name = getattr(block, "name", None)
                    if (
                        getattr(block, "type", None) in {"tool_use", "server_tool_use"}
                        and block_name in tool_names
                    ):
                        pending_tools.append(block)

                if not pending_tools:
                    final_text = self._collect_text_blocks(response.content)
                    break

                tool_results = []
                for block in pending_tools:
                    tool_calls += 1
                    args = block.input if isinstance(block.input, dict) else {}
                    result = await self.tool_manager.invoke(block.name, **args)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result, default=_default_json),
                        }
                    )

                messages.append({"role": "user", "content": tool_results})

            if final_text is None and messages:
                final_text = self._collect_text_from_conversation(messages)
        finally:
            await client.aclose()

        findings = self._extract_findings(final_text)
        telemetry = {
            "tool_calls": tool_calls,
            "input_tokens": usage["input_tokens"],
            "output_tokens": usage["output_tokens"],
        }

        return ProviderRunResult(
            provider=self.name,
            model=self.config.model,
            status="completed",
            findings=findings,
            telemetry=telemetry,
        )

    def _build_system_prompt(self, context: Any) -> str:
        thesis = getattr(context, "thesis", "").strip()
        value_chain = _default_json(getattr(context, "value_chain", []))
        kpis = _default_json(getattr(context, "kpis", {}))
        return (
            "You are Claude, an autonomous investment research analyst. "
            "Carefully use the provided tools to collect verifiable information from trusted sources. "
            "Prioritize accuracy, cite URLs, and align findings with the defined KPIs."
            f"\n\nInvestment thesis:\n{thesis}"
            f"\n\nValue chain context:\n{json.dumps(value_chain, indent=2)}"
            f"\n\nKPI definitions:\n{json.dumps(kpis, indent=2)}"
            "\n\nReturn JSON strictly formatted as:"
            '\n{"segments": [{"name": str, "companies": [{"company": str, "summary": str, "kpi_alignment": [str], "sources": [str]}]}]}'
        )

    def _build_user_prompt(self, context: Any) -> str:
        return (
            "Execute the full research workflow for every value-chain segment. "
            "Iteratively search, fetch source documents, and retrieve quantitative data as needed. "
            "Summarize each company relative to KPIs and include citations."
        )

    def _collect_text_blocks(self, blocks: Iterable[Any]) -> str:
        parts: list[str] = []
        for block in blocks:
            if getattr(block, "type", None) == "text":
                parts.append(block.text)
        return "\n".join(parts).strip()

    def _collect_text_from_conversation(self, messages: list[dict[str, Any]]) -> str:
        outputs: list[str] = []
        for message in messages:
            if message.get("role") != "assistant":
                continue
            for block in message.get("content", []):
                if block.get("type") == "text":
                    outputs.append(block.get("text", ""))
        return "\n".join(outputs).strip()

    def _extract_findings(self, final_text: str | None) -> list[dict[str, Any]]:
        if not final_text:
            return []
        try:
            data = json.loads(final_text)
        except json.JSONDecodeError:
            return [{"raw": final_text}]

        segments = data.get("segments")
        if isinstance(segments, list):
            return [segment for segment in segments if isinstance(segment, dict)]
        return [{"raw": data}]

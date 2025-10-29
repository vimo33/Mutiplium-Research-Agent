from __future__ import annotations

import json
from typing import Any, Awaitable, Callable, Iterable

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

        tool_functions, call_counter = self._build_tool_functions()

        client = genai.Client(api_key=api_key)
        response = None
        usage = None
        try:
            config = types.GenerateContentConfig(
                system_instruction=self._build_system_prompt(context),
                temperature=self.config.temperature,
                tools=tool_functions,
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
                    parts=[types.Part.from_text(text=self._build_user_prompt(context))],
                )
            ]

            response = await client.aio.models.generate_content(
                model=self.config.model,
                contents=contents,
                config=config,
            )
            text_output = response.text or ""
            usage = response.usage_metadata
        except Exception as exc:  # pragma: no cover
            return ProviderRunResult(
                provider=self.name,
                model=self.config.model,
                status="runtime_error",
                findings=[],
                telemetry={"error": str(exc)},
            )

        finally:
            await client.aio.aclose()
            client.close()

        usage_meta = usage or types.GenerateContentResponseUsageMetadata()
        findings = self._extract_findings(text_output)
        telemetry = {
            "tool_calls": call_counter["count"],
            "candidates": len(response.candidates or []) if response else 0,
            "input_tokens": getattr(usage_meta, "prompt_token_count", 0),
            "output_tokens": getattr(usage_meta, "candidates_token_count", 0),
        }

        return ProviderRunResult(
            provider=self.name,
            model=self.config.model,
            status="completed",
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

    def _build_system_prompt(self, context: Any) -> str:
        thesis = getattr(context, "thesis", "").strip()
        value_chain = _default_json(getattr(context, "value_chain", []))
        kpis = _default_json(getattr(context, "kpis", {}))
        return (
            "You are a Gemini-based research analyst collaborating with other LLM agents. "
            "Use registered tools to gather verifiable data, reason carefully, and output structured insights."
            f"\n\nInvestment thesis:\n{thesis}"
            f"\n\nValue chain context:\n{json.dumps(value_chain, indent=2)}"
            f"\n\nKPIs:\n{json.dumps(kpis, indent=2)}"
            "\n\nReturn JSON formatted as:"
            '\n{"segments": [{"name": str, "companies": [{"company": str, "summary": str, "kpi_alignment": [str], "sources": [str]}]}]}'
        )

    def _build_user_prompt(self, context: Any) -> str:
        return (
            "Perform comprehensive research for each value-chain segment. "
            "Leverage search, document fetch, Crunchbase, patent, and financial tools as needed. "
            "Summarize 3-5 companies per segment with KPI rationale and provide citations."
        )

    def _extract_findings(self, final_text: str) -> list[dict[str, Any]]:
        if not final_text.strip():
            return []

        try:
            data = json.loads(final_text)
        except json.JSONDecodeError:
            return [{"raw": final_text}]

        segments = data.get("segments")
        if isinstance(segments, list):
            return [segment for segment in segments if isinstance(segment, dict)]
        return [{"raw": data}]

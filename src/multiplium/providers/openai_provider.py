from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, TypedDict, cast

from pydantic import BaseModel, Field

from multiplium.providers.base import BaseAgentProvider, ProviderRunResult


def _default_json(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {k: _default_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_default_json(v) for v in value]
    return str(value)


# Structured output schema for OpenAI
class CompanyOutput(BaseModel):
    """Structured company data for research output."""
    company: str = Field(description="Company name")
    summary: str = Field(description="Brief summary of company's impact and technology (2-3 sentences)")
    kpi_alignment: list[str] = Field(description="List of KPI alignments with specific metrics")
    sources: list[str] = Field(description="List of source URLs (3-5 URLs)")
    website: str = Field(description="Company official website URL")
    country: str = Field(description="Company headquarters country (e.g., 'Spain', 'Israel', 'Australia')")
    confidence_0to1: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0-1.0) based on evidence quality: 0.8+ strong, 0.6-0.79 good, <0.6 weak"
    )
    source_tier: str = Field(
        default="Tier 3",
        description="Best source quality tier: 'Tier 1' (academic), 'Tier 2' (industry), 'Tier 3' (vendor)"
    )


class SegmentOutput(BaseModel):
    """Structured segment output with companies."""
    name: str = Field(description="Segment name")
    companies: list[CompanyOutput] = Field(description="List of companies in this segment")


class OpenAIAgentProvider(BaseAgentProvider):
    """OpenAI Agents SDK integration."""

    _MIN_COMPANIES = 10  # FULL RUN: 10 companies per segment target

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
            from agents import Agent, Runner, RunConfig, ModelSettings, WebSearchTool, set_default_openai_key
            from openai.types.shared import Reasoning
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

        # Configure ModelSettings for GPT-5.1 with optimized reasoning
        # Using "low" reasoning effort for faster responses while maintaining quality
        # Note: GPT-5.1 with reasoning mode doesn't support temperature or max_tokens
        # Must use max_completion_tokens instead of max_tokens for reasoning models
        model_settings = ModelSettings(
            reasoning=Reasoning(effort="low"),  # Optimized for speed
            extra_body={"max_completion_tokens": self.config.max_tokens},  # Use max_completion_tokens for reasoning models
        )
        
        # Configure RunConfig for better tracing and workflow management
        run_config = RunConfig(
            model=self.config.model,
            model_settings=model_settings,
            workflow_name="multiplium-discovery",
            tracing_disabled=False,
        )

        for segment_name in segment_names:
            seed_entries = seed_map.get(segment_name, [])
            # Use built-in WebSearchTool for native web search capability
            agent = Agent(
                name="OpenAI Investment Researcher",
                instructions=self._build_system_prompt(context, segment_name, seed_entries),
                model=self.config.model,
                model_settings=model_settings,
                tools=[WebSearchTool()],  # Built-in web search from SDK
            )

            user_prompt = self._build_segment_user_prompt(segment_name, context, seed_entries)

            try:
                # Add timeout to prevent hanging (5 minutes per segment max)
                import asyncio
                result = await asyncio.wait_for(
                    Runner.run(
                        agent,
                        user_prompt,
                        run_config=run_config,
                        max_turns=min(self.config.max_steps, 20),
                    ),
                    timeout=300.0,  # 5 minute timeout per segment
                )
            except asyncio.TimeoutError:
                error_msg = f"Segment '{segment_name}' timed out after 5 minutes. OpenAI API may be slow or unresponsive."
                findings.append(
                    {
                        "name": segment_name,
                        "companies": [],
                        "notes": [error_msg],
                    }
                )
                continue  # Try next segment
            except Exception as exc:  # pragma: no cover
                error_msg = str(exc)
                # Check if this was a max turns timeout
                if "Max turns" in error_msg or "exceeded" in error_msg:
                    error_msg = f"Max turns ({self.config.max_steps}) exceeded - segment incomplete. Consider breaking into smaller subsegments."
                
                findings.append(
                    {
                        "name": segment_name,
                        "companies": [],
                        "notes": [f"Segment run failed: {error_msg}"],
                    }
                )
                coverage_details["segments_missing"].append(
                    {"segment": segment_name, "companies": 0}
                )
                continue

            segment_data = self._extract_segment_output(result.final_output, segment_name, seed_entries)
            
            # Check if agent stopped due to max turns
            if len(result.raw_responses) >= self.config.max_steps - 1:
                notes = cast(list[str], segment_data.setdefault("notes", []))
                notes.append(
                    f"Agent reached max turns ({self.config.max_steps}). Results may be incomplete."
                )
            
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
            
            # Aggregate tool usage with fallback
            run_usage = self._aggregate_tool_usage(result.new_items)
            if run_usage:
                usage_counter.update(run_usage)
                total_tool_calls += sum(run_usage.values())
            else:
                # Fallback: count tool calls even if we can't get names
                fallback_count = self._count_tool_calls(result.new_items)
                if fallback_count > 0:
                    total_tool_calls += fallback_count
                    # Try to extract tool names from result data as backup
                    tool_names = self._extract_tool_names_from_result(result)
                    if tool_names:
                        for name in tool_names:
                            usage_counter[name] += 1
            
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
            "input_tokens": 0,  # OpenAI Agents SDK doesn't expose token counts yet
            "output_tokens": 0,  # Will be estimated post-run or from usage API
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

        # Note: OpenAI does not have native web search capabilities
        # All search is handled through MCP tools (Tavily, Perplexity) for consistency across providers
        
        self._tools_cached = tools
        return tools

    def _build_system_prompt(
        self,
        context: Any,
        segment_name: str,
        seed_companies: list[dict[str, Any]],
    ) -> str:
        """Builds the system prompt with reasoning guidance and full context."""
        thesis = getattr(context, "thesis", "").strip()
        value_chain = _default_json(getattr(context, "value_chain", []))
        kpis = _default_json(getattr(context, "kpis", {}))
        
        # Format seed companies as a structured table if present
        seed_section = ""
        if seed_companies:
            seed_section = (
                "\n\n**PRE-VALIDATED COMPANIES (High Confidence - use as quality benchmarks):**\n"
                "| Company | Evidence | KPI Alignment |\n"
                "|---------|----------|---------------|\n"
            )
            for company in seed_companies[:5]:  # Limit to 5 seeds
                name = company.get("company", "Unknown")
                summary = company.get("summary", "")[:60] + "..."
                kpis_list = ", ".join(company.get("kpi_alignment", [])[:2])
                seed_section += f"| {name} | {summary} | {kpis_list} |\n"
            seed_section += "\nUse these as reference standards. Find additional companies meeting similar quality bar."
        
        # Create segment-specific search strategies
        search_strategies = self._get_search_strategies(segment_name)
        
        return (
            f"You are a senior analyst for an **impact investment** fund specializing in wine industry technology.\n\n"
            f"**YOUR MISSION:** Identify 10 unique companies in the '{segment_name}' segment that generate measurable environmental/social impact.\n\n"
            "**REASONING FRAMEWORK (apply step-by-step to each company):**\n"
            "When evaluating each candidate company, reason through these criteria:\n"
            "1. **Vineyard Evidence Check:** Does this company have a named winery/vineyard deployment?\n"
            "   → If NO: Exclude immediately\n"
            "   → If YES: Proceed to step 2\n"
            "2. **KPI Impact Assessment:** Are the claimed impacts DIRECT (not indirect/implied)?\n"
            "   → Score 1-5 (5 = quantified, direct impact; 1 = vague, indirect claims)\n"
            "   → Exclude if score < 3\n"
            "3. **Source Quality Evaluation:** What tier are the best sources?\n"
            "   → Tier 1: Academic papers, government studies, university research\n"
            "   → Tier 2: Industry publications (Wines & Vines, Wine Business Monthly), ESG reports\n"
            "   → Tier 3: Vendor websites, blogs, press releases\n"
            "4. **Confidence Scoring:** Based on steps 1-3, assign confidence_0to1:\n"
            "   → 0.8-1.0: Strong vineyard evidence + Tier 1/2 sources + quantified metrics\n"
            "   → 0.6-0.79: Good evidence but limited to Tier 2/3 sources\n"
            "   → 0.4-0.59: Some vineyard connection but vague metrics\n"
            "   → Below 0.4: Exclude - insufficient evidence\n\n"
            "**MANDATORY REQUIREMENTS:**\n"
            "1. VINEYARD EVIDENCE: Every company MUST cite at least ONE vineyard-specific deployment.\n"
            "2. NO INDIRECT IMPACTS: Reject claims marked '(indirectly)', 'implied', 'potentially'.\n"
            "3. SOURCE QUALITY: Flag companies with only Tier 3 sources as confidence_0to1 < 0.6.\n"
            "4. QUANTIFIED METRICS: Prefer specific percentages, hectares, tCO2e values.\n"
            "5. INVESTABLE ENTITIES ONLY: Include ONLY private companies that can accept investment.\n"
            "   → EXCLUDE: NGOs, foundations, certification bodies (Demeter, EcoCert), government programs,\n"
            "     industry associations/councils, EU/LIFE funded projects, cooperatives, research initiatives.\n"
            "   → INCLUDE: Startups, scale-ups, established tech companies with products/services.\n\n"
            f"**SEARCH STRATEGY FOR '{segment_name}':**\n{search_strategies}\n"
            + seed_section +
            f"\n\n**INVESTMENT THESIS:**\n{thesis}"
            f"\n\n**VALUE CHAIN CONTEXT:**\n{json.dumps(value_chain, indent=2)}"
            f"\n\n**KPI FRAMEWORK:**\n{json.dumps(kpis, indent=2)}"
            "\n\n**OUTPUT FORMAT (JSON only, no markdown):**\n"
            "Return your findings as a JSON object with ALL required fields.\n\n"
            "**EXAMPLE OUTPUT (follow this exact structure):**\n"
            '{"segment": {"name": "' + segment_name + '", "companies": [\n'
            '  {\n'
            '    "company": "SupPlant",\n'
            '    "summary": "Israeli AI-driven precision irrigation company. Documented 30% water reduction at Golan Heights Winery (2023). Deployed across 50+ vineyards in Mediterranean climates.",\n'
            '    "kpi_alignment": ["Water Intensity: 30% reduction (4.2→2.9 m³/tonne)", "Labor Productivity: 40% fewer manual irrigation adjustments"],\n'
            '    "sources": ["https://supplant.me/case-studies/wine", "https://doi.org/10.1016/j.agwat.2023.107892", "https://winesandvines.com/supplant-review-2023"],\n'
            '    "website": "https://supplant.me",\n'
            '    "country": "Israel",\n'
            '    "confidence_0to1": 0.85,\n'
            '    "source_tier": "Tier 1"\n'
            '  }\n'
            ']}}\n\n'
            "**CRITICAL:** Output ONLY valid JSON. Start with { and end with }. No markdown, no explanations."
        )

    def _build_segment_user_prompt(
        self,
        segment_name: str,
        context: Any,
        seed_companies: list[dict[str, Any]],
    ) -> str:
        """Builds the user prompt with pacing guidance and research workflow."""
        seed_note = ""
        if seed_companies:
            names = ", ".join(company.get("company", "") for company in seed_companies)
            seed_note = (
                f"\n**PRE-VALIDATED SEEDS:** {names}\n"
                "Verify their evidence and find additional companies meeting the same quality bar.\n"
            )
        
        # Get optimized search queries for this segment
        search_queries = self._get_search_queries_for_segment(segment_name)
        queries_text = "\n".join([f"  - \"{q}\"" for q in search_queries])
        
        return (
            f"🎯 **MISSION:** Find EXACTLY 10 unique companies in the '{segment_name}' segment.\n\n"
            "**TURN BUDGET (20 turns maximum):**\n"
            "- Turns 1-10: Discover companies using web searches with the queries below\n"
            "- Turns 11-15: Verify top candidates have vineyard-specific evidence\n"
            "- Turns 16-18: Finalize your list and prepare JSON output\n"
            "- **Output by turn 18** even if you haven't reached 10 companies\n\n"
            "**RESEARCH QUERIES (use these as starting points):**\n" + queries_text + "\n\n"
            "**SYSTEMATIC RESEARCH WORKFLOW:**\n"
            "1. Search the web for companies matching each query\n"
            "2. For each promising company, verify vineyard/winery deployment evidence\n"
            "3. Look for case studies, named customers, and quantified impact metrics\n"
            "4. Assess source quality (Tier 1/2/3) and assign confidence score\n"
            "5. Find company website and headquarters country\n"
            "6. Continue until you have 10 VERIFIED companies\n"
            + seed_note +
            "\n**REQUIRED OUTPUT FIELDS (for EVERY company):**\n"
            "- `company`: Unique company name\n"
            "- `summary`: 2-3 sentences with specific metrics/impact data\n"
            "- `kpi_alignment`: 2-3 explicit KPI alignments with quantitative evidence\n"
            "- `sources`: 3-5 verified source URLs\n"
            "- `website`: Official company website URL\n"
            "- `country`: Headquarters country (e.g., 'Israel', 'Spain', 'Australia')\n"
            "- `confidence_0to1`: Your confidence score (0.0-1.0) based on evidence quality\n"
            "- `source_tier`: Best source tier ('Tier 1', 'Tier 2', or 'Tier 3')\n\n"
            "**IF YOU FIND FEWER THAN 10:**\n"
            "- Add geographic modifiers (Spain, France, Italy, Chile, Australia, California)\n"
            "- Try alternative technology terms and synonyms\n"
            "- Search wine trade publications (Wines & Vines, Wine Business Monthly)\n"
            "- Search startup accelerators (AgFunder, WineTech Network)\n\n"
            "Begin your research now. Output JSON when you have 10 verified companies or by turn 18."
        )

    def _extract_segment_output(
        self,
        final_output: Any,
        segment_name: str,
        seed_companies: list[dict[str, Any]],
    ) -> dict[str, Any]:
        data: Any = None
        if isinstance(final_output, str):
            try:
                cleaned = self._sanitize_json_output(final_output)
                data = json.loads(cleaned)
            except json.JSONDecodeError:
                # Try to extract JSON from markdown code blocks or surrounding text
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', final_output, re.DOTALL)
                if json_match:
                    try:
                        data = json.loads(json_match.group(1))
                    except json.JSONDecodeError:
                        pass
                else:
                    # Try to find any JSON object in the text
                    json_match = re.search(r'\{.*?"segment".*?\{.*?"companies".*?\[.*?\].*?\}.*?\}', final_output, re.DOTALL)
                    if json_match:
                        try:
                            data = json.loads(json_match.group(0))
                        except json.JSONDecodeError:
                            pass
                
                if not isinstance(data, dict):
                    # Try markdown fallback parser
                    markdown_data = self._parse_markdown_to_json(final_output, segment_name)
                    if markdown_data and markdown_data.get("companies"):
                        data = {"segment": markdown_data}
                    else:
                        return {
                            "name": segment_name,
                            "companies": [],
                            "notes": [f"Unable to parse segment output: {final_output[:500]}..."],
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
    
    def _parse_markdown_to_json(self, markdown: str, segment_name: str) -> dict[str, Any] | None:
        """Fallback parser: convert markdown company list to JSON structure."""
        companies = []
        
        # Find company blocks in markdown (numbered or bulleted)
        company_pattern = r'(?:^|\n)(?:\d+\.|[-\*])\s+\*\*([^*]+)\*\*\s*\n\s*[-\*]\s+\*\*Summary[:\]]?\*\*[:\s]+([^\n]+(?:\n(?!\s*[-\*]\s+\*\*)[^\n]+)*)\s*\n\s*[-\*]\s+\*\*KPI Alignment[:\]]?\*\*[:\s]+([^\n]+(?:\n(?!\s*[-\*]\s+\*\*)[^\n]+)*)\s*\n\s*[-\*]\s+\*\*Sources[:\]]?\*\*[:\s]+([\s\S]+?)(?=\n(?:\d+\.|[-\*])\s+\*\*[A-Z]|\Z)'
        
        for match in re.finditer(company_pattern, markdown, re.IGNORECASE | re.MULTILINE):
            company_name = match.group(1).strip()
            summary = re.sub(r'\s+', ' ', match.group(2).strip())
            kpi_text = match.group(3).strip()
            sources_text = match.group(4).strip()
            
            # Parse KPIs
            kpis = [kpi.strip('- \t\n') for kpi in re.findall(r'[-\*•]\s*([^\n]+)', kpi_text)]
            if not kpis:
                kpis = [k.strip() for k in kpi_text.split(',') if k.strip()]
            
            # Parse sources
            sources = re.findall(r'https?://[^\s\)\]]+', sources_text)
            if not sources:
                sources = [s.strip('- \t\n[]()') for s in re.findall(r'[-\*•]\s*([^\n]+)', sources_text)]
            
            if company_name and summary:
                companies.append({
                    "company": company_name,
                    "summary": summary,
                    "kpi_alignment": kpis[:5],  # Max 5 KPIs
                    "sources": sources[:5],  # Max 5 sources
                })
        
        if companies:
            return {
                "name": segment_name,
                "companies": companies
            }
        return None

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
            tool_name = None
            
            # Try multiple ways to extract tool information
            if isinstance(item, ToolCallItem):
                tool_call = getattr(item, "tool_call", None)
                if hasattr(item, "name"):
                    tool_name = item.name
            elif isinstance(item, ToolCallOutputItem):
                tool_call = getattr(item, "tool_call", None)
                if hasattr(item, "name"):
                    tool_name = item.name
            
            # Try to get name from tool_call if not found yet
            if tool_call is not None and tool_name is None:
                tool_name = getattr(tool_call, "name", None)
                if hasattr(tool_call, "function"):
                    func = tool_call.function
                    if hasattr(func, "name"):
                        tool_name = func.name
            
            # Record if we found a valid tool name
            if isinstance(tool_name, str) and tool_name:
                call_id = getattr(tool_call, "id", None) if tool_call else None
                cache_key = call_id if isinstance(call_id, str) else (tool_name, id(tool_call or item))
                if cache_key not in seen_call_ids:
                    seen_call_ids.add(cache_key)
                    counter[tool_name] += 1

        return dict(counter)
    
    def _extract_tool_names_from_result(self, result: Any) -> list[str]:
        """Fallback: Extract tool names from result object by inspecting raw_responses."""
        tool_names = []
        try:
            raw_responses = getattr(result, "raw_responses", [])
            for response in raw_responses:
                if hasattr(response, "tool_calls") and response.tool_calls:
                    for tool_call in response.tool_calls:
                        if hasattr(tool_call, "function") and hasattr(tool_call.function, "name"):
                            tool_names.append(tool_call.function.name)
        except Exception:
            pass
        return tool_names

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

    def _get_search_strategies(self, segment_name: str) -> str:
        """Provides segment-specific search strategies to guide the agent."""
        strategies = {
            "Soil Health Technologies": (
                "• Search for: soil microbiome, soil carbon sequestration, regenerative agriculture tech\n"
                "• Target companies: soil testing labs, microbial inoculants, biochar producers\n"
                "• Geographic focus: France, Spain, California, Australia (Adelaide)\n"
                "• Look for: vineyard case studies, ROC certifications, university partnerships"
            ),
            "Precision Irrigation Systems": (
                "• Search for: smart irrigation, precision water management, soil moisture sensors\n"
                "• Target companies: IoT irrigation platforms, drip irrigation tech, water optimization software\n"
                "• Geographic focus: Israel, Spain, California, Chile, Australia\n"
                "• Look for: water savings metrics (%), drought resilience data, named winery clients"
            ),
            "Integrated Pest Management (IPM)": (
                "• Search for: biological pest control, pheromone monitoring, pesticide alternatives\n"
                "• Target companies: biocontrol producers, pest monitoring platforms, disease prediction\n"
                "• Geographic focus: France, Italy, Spain, New Zealand\n"
                "• Look for: pesticide reduction %, biodiversity impact, organic certifications"
            ),
            "Canopy Management Solutions": (
                "• Search for: precision viticulture, robotic pruning, canopy sensing, vineyard drones\n"
                "• Target companies: ag robotics, drone/satellite imaging, pruning automation\n"
                "• Geographic focus: France, Germany, USA, Australia\n"
                "• Look for: yield optimization %, labor savings, disease prevention metrics"
            ),
            "Carbon MRV & Traceability Platforms": (
                "• Search for: carbon accounting, MRV platforms, blockchain traceability\n"
                "• Target companies: carbon credit platforms, supply chain software, sustainability reporting\n"
                "• Geographic focus: EU, California, Australia, South Africa\n"
                "• Look for: tons CO2 sequestered, verified carbon credits, traceability deployments"
            ),
            "Grape Production": (
                "• Search for: precision viticulture platforms, vineyard management systems\n"
                "• Target companies: farm management software, yield prediction, quality monitoring\n"
                "• Geographic focus: France, Spain, Italy, California, Australia, Chile\n"
                "• Look for: yield improvements, quality metrics, named winery clients"
            ),
            "Wine Production": (
                "• Search for: fermentation control, cellar automation, winemaking analytics\n"
                "• Target companies: tank sensors, SCADA systems, wine QC platforms\n"
                "• Geographic focus: France, Italy, USA, Australia, New Zealand\n"
                "• Look for: fermentation success rates, OEE improvements, quality consistency"
            ),
            "Packaging": (
                "• Search for: wine packaging sustainability, bottle filling technology\n"
                "• Target companies: lightweight glass, sustainable closures, packaging automation\n"
                "• Geographic focus: EU (glass manufacturers), USA, Australia\n"
                "• Look for: weight reduction %, recycled content, OEE improvements"
            ),
            "Distribution": (
                "• Search for: wine logistics cold chain, temperature monitoring, DTC platforms\n"
                "• Target companies: 3PL with wine focus, cold chain telemetry, wine e-commerce\n"
                "• Geographic focus: USA, EU, Australia\n"
                "• Look for: OTIF rates, temperature excursion reduction, delivery success metrics"
            ),
        }
        # Try exact match first, then partial match
        if segment_name in strategies:
            return strategies[segment_name]
        for key, value in strategies.items():
            if key.lower() in segment_name.lower() or segment_name.lower() in key.lower():
                return value
        return "• Use general search strategies for wine/viticulture technology and sustainability"

    def _get_search_queries_for_segment(self, segment_name: str) -> list[str]:
        """Returns optimized search queries for each segment."""
        queries = {
            "Soil Health Technologies": [
                "soil microbiome testing vineyard",
                "soil carbon sequestration technology wine",
                "regenerative agriculture viticulture startups",
                "soil health monitoring platform vineyard",
                "microbial inoculant wine grape",
            ],
            "Precision Irrigation Systems": [
                "smart irrigation technology vineyard",
                "precision water management wine startup",
                "soil moisture sensor vineyard irrigation",
                "AI irrigation optimization viticulture",
                "water stress monitoring wine grape",
            ],
            "Integrated Pest Management (IPM)": [
                "biological pest control vineyard",
                "IPM monitoring platform viticulture",
                "pheromone trap system wine grape",
                "disease prediction vineyard AI",
                "biocontrol solutions vineyard",
            ],
            "Canopy Management Solutions": [
                "vineyard robotics pruning automation",
                "precision viticulture canopy sensing",
                "drone vineyard mapping NDVI",
                "robotic vineyard equipment",
                "canopy management technology wine",
            ],
            "Carbon MRV & Traceability Platforms": [
                "carbon accounting wine supply chain",
                "MRV platform vineyard agriculture",
                "blockchain traceability wine",
                "carbon credits vineyard regenerative",
                "sustainability reporting winery",
            ],
            "Grape Production": [
                "precision viticulture technology platform",
                "vineyard management software",
                "grape quality monitoring AI",
                "harvest optimization wine technology",
                "yield prediction vineyard",
            ],
            "Wine Production": [
                "fermentation monitoring winery technology",
                "wine tank sensor IoT",
                "cellar automation software winery",
                "winemaking analytics platform",
                "quality control wine production technology",
            ],
            "Packaging": [
                "wine packaging sustainability technology",
                "bottle filling technology winery",
                "wine closure technology innovation",
                "lightweight glass wine bottle",
                "sustainable wine packaging solutions",
            ],
            "Distribution": [
                "wine logistics cold chain technology",
                "temperature monitoring wine transport",
                "wine inventory management software",
                "DTC wine platform technology",
                "wine shipping logistics technology",
            ],
        }
        # Try exact match first, then partial match
        if segment_name in queries:
            return queries[segment_name]
        for key, value in queries.items():
            if key.lower() in segment_name.lower() or segment_name.lower() in key.lower():
                return value
        return [
            f"{segment_name} vineyard technology",
            f"{segment_name} wine industry",
            f"{segment_name} viticulture innovation",
            f"{segment_name} winery solution",
        ]

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

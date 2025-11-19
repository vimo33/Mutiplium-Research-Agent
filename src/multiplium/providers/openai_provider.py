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
    website: str = Field(description="Company official website URL (extract from sources)")
    country: str = Field(description="Company headquarters country (e.g., 'Spain', 'United States', 'Chile')")


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
            # Note: No MCP tools - OpenAI will use native web search capabilities
            # MCP tools reserved for validation phase only
            agent = Agent(
                name="OpenAI Investment Researcher",
                instructions=self._build_system_prompt(context, segment_name, seed_entries),
                model=self.config.model,
                tools=[],  # Empty tools list - use native capabilities
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
                    max_turns=min(self.config.max_steps, 20),  # FULL RUN: Cap at 20
                )
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
        thesis = getattr(context, "thesis", "").strip()
        value_chain = _default_json(getattr(context, "value_chain", []))
        kpis = _default_json(getattr(context, "kpis", {}))
        seed_section = ""
        if seed_companies:
            seed_section = (
                "\n\nValidated vineyard companies to treat as high-confidence seeds:\n"
                + json.dumps(seed_companies, indent=2)
            )
        # Create segment-specific search strategies
        search_strategies = self._get_search_strategies(segment_name)
        
        return (
            "You are a senior analyst for an **impact investment** fund. Your primary objective is to identify companies that not only have strong business potential but also generate positive, measurable environmental and social impact. "
            "Strictly adhere to the KPI framework, giving higher weight to impact-related KPIs like 'Soil Carbon Sequestration' and 'Pesticide Reduction' over purely operational metrics. "
            "\n\n**MANDATORY VITICULTURE REQUIREMENTS:**\n"
            "1. VINEYARD EVIDENCE REQUIRED: Every company MUST cite at least ONE vineyard-specific deployment, named winery customer, or viticulture case study. Generic agriculture platforms are EXCLUDED unless they demonstrate specific vineyard projects with named clients.\n"
            "2. NO INDIRECT IMPACTS: Core segment KPIs must show DIRECT impacts. Reject companies where primary KPIs are marked '(indirectly)' or 'implied' or 'general precision agriculture benefits' or 'potentially' or 'could lead to'.\n"
            "3. TIER 1/2 SOURCES PREFERRED: Each company should have at least ONE Tier 1 (peer-reviewed, government study, university research) or Tier 2 (industry publication, cooperative whitepaper, ESG report) source. Companies with only Tier 3 sources (vendor websites, blogs, press releases) should be flagged 'Low Confidence'.\n"
            "4. QUANTIFIED METRICS: Prefer companies with specific percentages, hectares, tCO2e values, liters saved over vague claims like 'improves soil health' or 'optimizes irrigation'.\n"
            "\n\n**CRITICAL TARGET:** Find 10 unique companies for this segment. Use your native web search capabilities to discover companies quickly. "
            "**IMPORTANT:** You have 20 turns maximum. Pace yourself:\n"
            "- Turns 1-10: Discover companies using broad web searches\n"
            "- Turns 11-15: Verify top candidates have vineyard evidence\n"
            "- Turns 16-20: Finalize your list and output JSON\n"
            "\n\n**SEARCH STRATEGY FOR THIS SEGMENT:**\n" + search_strategies +
            f"\n\nFocus exclusively on the value-chain segment '{segment_name}'. Your goal is to produce {self._MIN_COMPANIES} unique company profiles with comprehensive KPI alignment and cited sources. "
            "If initial searches yield fewer companies, expand your search with alternative keywords, geographic variations (EU, US, Australia, South America), and related terms. "
            "**IMPORTANT: Output what you have found by turn 18, even if you haven't reached 10 companies yet.**"
            f"\n\nInvestment thesis:\n{thesis}"
            f"\n\nValue chain context:\n{json.dumps(value_chain, indent=2)}"
            f"\n\nKPI definitions:\n{json.dumps(kpis, indent=2)}"
            f"{seed_section}"
            "\n\nOutput JSON strictly matching (INCLUDE website and country for EVERY company):"
            '\n{"segment": {"name": str, "companies": [{"company": str, "summary": str, "kpi_alignment": [str], "sources": [str], "website": str, "country": str}]}}'
            "\n\n**CRITICAL:** For each company, extract:"
            "\n- website: Company's official URL (look in sources or search results)"
            "\n- country: Headquarters country (e.g., 'Spain', 'Chile', 'United States')"
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
        
        # Get optimized search queries for this segment
        search_queries = self._get_search_queries_for_segment(segment_name)
        queries_text = "\n".join([f"  - \"{q}\"" for q in search_queries])
        
        return (
            f"🎯 MISSION: Find EXACTLY 10 unique companies in the '{segment_name}' segment.\n\n"
            "**SYSTEMATIC APPROACH:**\n"
            "1. Start with these optimized search queries:\n" + queries_text + "\n"
            "2. For EACH query, use `search_web` with max_results=10 to cast a wide net\n"
            "3. Use `fetch_content` on promising company websites to verify impact claims\n"
            "4. Use `lookup_crunchbase` to confirm company profiles and funding\n"
            "5. Use `search_academic_papers` to find scientific validation\n"
            "6. Use `lookup_patents` to verify innovation claims\n"
            "7. Continue until you have 10 VERIFIED companies with evidence\n\n"
            "**REQUIREMENTS FOR EACH COMPANY:**\n"
            "- Unique name (no duplicates)\n"
            "- 2-3 sentence summary with specific metrics/impact data\n"
            "- 2-3 explicit KPI alignments with quantitative evidence\n"
            "- 3-5 verified sources (prioritize: company websites, case studies, academic papers, certifications)\n\n"
            "**IF YOU FIND FEWER THAN 10:** Expand your search with:\n"
            "- Alternative keywords and synonyms\n"
            "- Geographic variations (add 'Europe', 'US', 'Australia', 'South America')\n"
            "- Related technology terms\n"
            "- Emerging startups vs established players\n\n"
            + seed_note +
            "\n\n**OUTPUT FORMAT (CRITICAL):**\n"
            "Return ONLY valid JSON in this EXACT structure (no markdown, no extra text):\n\n"
            '{"segment": {"name": "' + segment_name + '", "companies": [{"company": "CompanyName", "summary": "2-3 sentence summary with metrics", "kpi_alignment": ["KPI 1: specific metric/evidence", "KPI 2: specific metric/evidence"], "sources": ["https://url1.com", "https://url2.com", "https://url3.com"]}]}}\n\n'
            "Do NOT stop until you have 10 companies! Quality + Quantity = Success! 🎯"
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
                "• Keywords: 'soil health technology', 'carbon farming platforms', 'soil microbiome analysis'\n"
                "• Look for: case studies from vineyards, ROC (regenerative organic) certifications"
            ),
            "Precision Irrigation Systems": (
                "• Search for: smart irrigation, precision water management, soil moisture sensors\n"
                "• Target companies: IoT irrigation platforms, drip irrigation tech, water optimization software\n"
                "• Keywords: 'precision irrigation vineyard', 'smart water management agriculture', 'soil moisture monitoring'\n"
                "• Look for: water savings metrics (%), drought resilience data, case studies"
            ),
            "Integrated Pest Management (IPM)": (
                "• Search for: biological pest control, pheromone monitoring, pesticide alternatives\n"
                "• Target companies: biocontrol producers, pest monitoring platforms, organic pesticide alternatives\n"
                "• Keywords: 'IPM vineyard', 'biological pest control', 'organic pest management', 'pheromone traps'\n"
                "• Look for: pesticide reduction %, biodiversity impact, organic certifications"
            ),
            "Canopy Management Solutions": (
                "• Search for: precision viticulture, robotic pruning, canopy sensing, vineyard robotics\n"
                "• Target companies: ag robotics, drone/satellite imaging, canopy sensors, pruning automation\n"
                "• Keywords: 'vineyard robotics', 'precision viticulture', 'canopy management technology', 'vineyard drones'\n"
                "• Look for: yield optimization %, labor savings, disease prevention metrics"
            ),
            "Carbon MRV & Traceability Platforms": (
                "• Search for: carbon accounting, MRV platforms, blockchain traceability, supply chain transparency\n"
                "• Target companies: carbon credit platforms, blockchain ag-tech, supply chain software, sustainability reporting\n"
                "• Keywords: 'agricultural carbon credits', 'MRV platform agriculture', 'blockchain traceability wine', 'carbon accounting farm'\n"
                "• Look for: tons CO2 sequestered, verified carbon credits, traceability case studies"
            ),
        }
        return strategies.get(segment_name, "• Use general search strategies for agtech and sustainability")

    def _get_search_queries_for_segment(self, segment_name: str) -> list[str]:
        """Returns optimized search queries for each segment."""
        queries = {
            "Soil Health Technologies": [
                "soil microbiome testing vineyard",
                "soil carbon sequestration technology agriculture",
                "regenerative agriculture soil health startups",
                "soil health monitoring platform wine",
                "microbial inoculant vineyard",
            ],
            "Precision Irrigation Systems": [
                "smart irrigation technology vineyard",
                "precision water management agriculture startup",
                "soil moisture sensor irrigation wine",
                "IoT drip irrigation system",
                "water optimization platform agriculture",
            ],
            "Integrated Pest Management (IPM)": [
                "biological pest control vineyard",
                "IPM monitoring platform agriculture",
                "pheromone trap system vineyard",
                "organic pest management technology",
                "biocontrol solutions agriculture",
            ],
            "Canopy Management Solutions": [
                "vineyard robotics pruning",
                "precision viticulture canopy sensing",
                "agricultural drone vineyard management",
                "canopy imaging technology wine",
                "robotic vineyard equipment",
            ],
            "Carbon MRV & Traceability Platforms": [
                "agricultural carbon credit platform",
                "MRV monitoring reporting verification agriculture",
                "blockchain traceability wine supply chain",
                "carbon accounting software farm",
                "sustainability traceability platform food",
            ],
        }
        return queries.get(segment_name, [f"{segment_name} technology companies"])

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

from __future__ import annotations

import json
from typing import Any, Iterable, cast

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
            findings = [{"note": "Dry run placeholder"}]
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

        client = cast(Any, anthropic.AsyncAnthropic(api_key=api_key))
        
        # Use native web search tool - no MCP tools
        # Web search is built-in and automatically cites sources
        # Pricing: $10/1000 searches + standard token costs
        # Ref: https://docs.claude.com/en/docs/agents-and-tools/tool-use/web-search-tool
        tools = [
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 30,  # FULL RUN: 30 searches for all segments (6 per segment avg)
            }
        ]
        tool_names = {"web_search"}

        # Build system prompt with cache control for large context
        system_blocks = self._build_cached_system_prompt(context)
        user_prompt = self._build_user_prompt(context)

        messages: list[dict[str, Any]] = [{"role": "user", "content": user_prompt}]
        tool_calls = 0
        final_text: str | None = None
        usage = {"input_tokens": 0, "output_tokens": 0}

        try:
            # FULL RUN: Cap at 20 turns to force convergence
            max_turns = min(self.config.max_steps, 20)
            for _ in range(max_turns):
                messages_payload: Any = messages
                tools_payload: Any = tools  # Native web search tool
                response = await client.messages.create(
                    model=self.config.model,
                    system=system_blocks,
                    messages=messages_payload,
                    tools=tools_payload,
                    temperature=self.config.temperature,
                    max_tokens=8192,  # Increased for longer responses
                    # Note: token-efficient-tools is DEFAULT in Claude 4 models
                )

                usage["input_tokens"] += getattr(response.usage, "input_tokens", 0)
                usage["output_tokens"] += getattr(response.usage, "output_tokens", 0)
                # Track prompt caching metrics for cost optimization
                usage["cache_creation_input_tokens"] = usage.get("cache_creation_input_tokens", 0) + getattr(response.usage, "cache_creation_input_tokens", 0)
                usage["cache_read_input_tokens"] = usage.get("cache_read_input_tokens", 0) + getattr(response.usage, "cache_read_input_tokens", 0)

                response_blocks = list(cast(Iterable[Any], response.content))
                assistant_blocks = [block.model_dump() for block in response_blocks]
                messages.append({"role": "assistant", "content": assistant_blocks})

                # Check for web search tool use (server-side execution)
                has_web_search = False
                for block in response_blocks:
                    block_type = getattr(block, "type", None)
                    if block_type == "server_tool_use":
                        tool_calls += 1
                        has_web_search = True
                    elif block_type == "web_search_tool_result":
                        # Web search results are automatically added by API
                        has_web_search = True

                # If no server tools, check if we have final text
                has_text = any(getattr(b, "type", None) == "text" for b in response_blocks)
                if has_text and not has_web_search:
                    final_text = self._collect_text_blocks(response_blocks)
                    break

                # Web search executes server-side, results automatically included
                # Continue to next turn to get Claude's response with search results

            if final_text is None and messages:
                final_text = self._collect_text_from_conversation(messages)
        finally:
            await client.close()

        findings = self._extract_findings(final_text)
        
        # Enhanced telemetry with ACTUAL cache metrics and web search usage
        cache_creation = usage.get("cache_creation_input_tokens", 0)
        cache_read = usage.get("cache_read_input_tokens", 0)
        total_input = usage["input_tokens"]
        
        telemetry: dict[str, Any] = {
            "tool_calls": tool_calls,
            "input_tokens": total_input,
            "output_tokens": usage["output_tokens"],
            "tool_usage": {"web_search": tool_calls},
            # REAL cache metrics from Anthropic API
            "cache_creation_input_tokens": cache_creation,
            "cache_read_input_tokens": cache_read,
            "cache_hit_rate": round(cache_read / max(total_input, 1), 3) if total_input > 0 else 0,
        }
        
        # Note: Prompt caching reduces input token cost by 10x ($0.30/1M vs $3/1M)
        # Web search pricing: $10/1000 searches + token costs
        # token-efficient-tools feature saves average 14% output tokens (default in Claude 4)

        return ProviderRunResult(
            provider=self.name,
            model=self.config.model,
            status="completed",
            findings=findings,
            telemetry=telemetry,
        )

    def _build_cached_system_prompt(self, context: Any) -> list[dict[str, Any]]:
        """
        Build system prompt with prompt caching for expensive context.
        
        Uses Anthropic's prompt caching to cache thesis, value chain, and KPI context,
        which can be reused across multiple API calls for significant cost savings.
        """
        thesis = getattr(context, "thesis", "").strip()
        value_chain = _default_json(getattr(context, "value_chain", []))
        kpis = _default_json(getattr(context, "kpis", {}))
        
        # Base instructions (not cached - changes frequently)
        base_instruction = {
            "type": "text",
            "text": (
                "You are Claude, an autonomous analyst for an **impact investment** fund. "
                "Your primary objective is to identify companies that not only have strong business potential "
                "but also generate positive, measurable environmental and social impact. "
                "\n\n**MANDATORY VITICULTURE REQUIREMENTS:**\n"
                "1. VINEYARD EVIDENCE REQUIRED: Every company MUST cite at least ONE vineyard-specific deployment, named winery customer, or viticulture case study.\n"
                "2. NO INDIRECT IMPACTS: Core segment KPIs must show DIRECT impacts. Reject companies where primary KPIs are marked '(indirectly)' or 'implied'.\n"
                "3. TIER 1/2 SOURCES PREFERRED: Each company should have at least ONE Tier 1 or Tier 2 source.\n"
                "4. QUANTIFIED METRICS: Prefer companies with specific percentages, hectares, tCO2e values, liters saved.\n"
                "\n\n**RESEARCH APPROACH & WEB SEARCH STRATEGY:**\n"
                "- You have 30 web searches to research ALL 5 segments (~6 searches per segment)\n"
                "- You have 20 conversational turns to complete the research\n"
                "- Use web_search to find real-time information about vineyard technology companies\n"
                "- SEARCH STRATEGY PER SEGMENT:\n"
                "  * Search 1-2: Broad discovery (e.g., 'soil microbiome vineyard technology companies Europe')\n"
                "  * Search 3-4: Targeted verification (e.g., 'Biome Makers vineyard case study quantified results')\n"
                "  * Search 5-6: Gap filling for underrepresented regions (e.g., 'precision irrigation vineyard Chile Argentina')\n"
                "- Search queries should combine: technology keywords + 'vineyard'/'wine'/'viticulture' + geography\n"
                "- Examples: 'carbon MRV wine traceability platform Italy', 'IPM biocontrol vineyard Australia'\n"
                "- For each company, provide: name, summary (2-3 sentences), KPI alignments with metrics, and 3-5 source URLs\n"
                "- Target 10 companies per segment across 5 segments (50 total)\n"
                "- Web search automatically cites sources - extract and include those URLs in your output\n"
                "- PACE YOURSELF: Don't exhaust searches early - allocate them strategically across all segments"
            ),
        }
        
        # Thesis context (cached - large and stable)
        thesis_block = {
            "type": "text",
            "text": f"\n\nInvestment thesis:\n{thesis}",
            "cache_control": {"type": "ephemeral"},
        }
        
        # Value chain context (cached - large and stable)
        value_chain_block = {
            "type": "text",
            "text": f"\n\nValue chain context:\n{json.dumps(value_chain, indent=2)}",
            "cache_control": {"type": "ephemeral"},
        }
        
        # KPI definitions (cached - large and stable)
        kpi_block = {
            "type": "text",
            "text": (
                f"\n\nKPI definitions:\n{json.dumps(kpis, indent=2)}"
                "\n\n**REQUIRED OUTPUT FORMAT:**"
                '\n{"segments": [{"name": str, "companies": [{'
                '\n  "company": str,'
                '\n  "executive_summary": str (Solution, Impact, Maturity),'
                '\n  "technology_solution": str (Tech & Value Chain mapping),'
                '\n  "evidence_of_impact": str (Specific metrics),'
                '\n  "key_clients": [str] (List of named clients),'
                '\n  "team": str (Key founders/execs),'
                '\n  "competitors": str (Differentiation),'
                '\n  "financials": str (Turnover, EBITDA, Cost Structure - last 3 years if available, else "Not Disclosed"),'
                '\n  "cap_table": str (Structure of capital if available, else "Not Disclosed"),'
                '\n  "swot": {"strengths": [str], "weaknesses": [str], "opportunities": [str], "threats": [str]},'
                '\n  "sources": [str] (3-5 URLs),'
                '\n  "website": str (company official website URL),'
                '\n  "country": str (headquarters country)'
                '\n}]}]}'
                '\n\n**CRITICAL:** Always include "website" (company\'s official URL) and "country" (HQ location) for every company.'
            ),
            "cache_control": {"type": "ephemeral"},
        }
        
        return [base_instruction, thesis_block, value_chain_block, kpi_block]

    def _build_user_prompt(self, context: Any) -> str:
        return (
            "Execute systematic research across ALL value-chain segments defined in the wine industry value chain context. "
            "For EACH segment, identify HIGH-QUALITY companies with:\n"
            "- Strong vineyard/winery-specific evidence (named clients, documented case studies, specific deployments)\n"
            "- Direct impact on core KPIs with quantified metrics (not indirect/implied/potentially)\n"
            "- At least 1 Tier 1/2 source per company (peer-reviewed, government, reputable industry publication)\n"
            "- Geographic diversity (aim for 50%+ non-US coverage across all segments)\n\n"
            "**WEB SEARCH BUDGET: 30 searches total (~6 per segment for Viticulture segments, ~3 for other value chain stages)**\n"
            "**TURN BUDGET: 20 turns maximum**\n\n"
            "**SYSTEMATIC SEARCH WORKFLOW PER SEGMENT:**\n"
            "1. **Discovery (2-3 searches):** Broad queries combining segment tech + wine/vineyard + region\n"
            "   - Example: 'precision irrigation vineyard technology companies Mediterranean'\n"
            "   - Example: 'fermentation control winery automation analytics'\n"
            "   - **NEW KEYWORDS:** Include 'UV-C', 'robotics', 'CO2 capture', 'biomaterials' to capture niche technologies.\n"
            "2. **Verification (2-3 searches):** Targeted searches for top candidates to find evidence AND financial/SWOT data\n"
            "   - Example: 'SupPlant vineyard water savings case study quantified'\n"
            "   - Example: 'Biome Makers revenue funding competitors'\n"
            "3. **Gap Filling (1-2 searches):** If coverage gaps exist, search underrepresented regions or value chain stages\n"
            "   - Example: 'WiseConn Chile vineyard deployment'\n"
            "   - Use anchor companies from value chain as leads\n\n"
            "**PACING STRATEGY:**\n"
            "- Turns 1-8: Research viticulture segments (Soil Health, Irrigation, IPM, Canopy) - 24 searches\n"
            "- Turns 9-12: Research other value chain stages (Vinification, Packaging, Logistics, etc.) - 6 searches\n"
            "- Turns 13-20: Synthesize, fill gaps, format JSON output\n\n"
            "**OUTPUT FORMAT:**\n"
            "Return complete JSON with all 5 segments and 50 companies (10 per segment).\n"
            "For EACH company, include ALL the required fields defined in the system prompt (Executive Summary, Financials, SWOT, etc.).\n"
            "If financial data is not public, explicitly state 'Not Disclosed' but try to find funding rounds or revenue estimates.\n"
            "**CRITICAL:** website and country are REQUIRED fields. Extract them from your web search results or the first source URL."
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
        """
        Robust 4-tier parser to extract structured findings from Claude's output.
        
        This ensures Claude's output is always structured as individual segment findings,
        preventing truncation issues and enabling seamless CSV export.
        """
        if not final_text:
            return []
        
        import re
        
        # TIER 1: Try parsing as direct JSON
        try:
            data = json.loads(final_text)
            segments = data.get("segments")
            if isinstance(segments, list):
                # Validate each segment has required structure
                structured_findings = []
                for segment in segments:
                    if isinstance(segment, dict) and "name" in segment and "companies" in segment:
                        structured_findings.append(segment)
                if structured_findings:
                    return structured_findings
        except json.JSONDecodeError:
            pass
        
        # TIER 2: Extract JSON from markdown code blocks
        if "```json" in final_text or "```" in final_text:
            json_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', final_text, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group(1))
                    segments = data.get("segments")
                    if isinstance(segments, list):
                        structured_findings = []
                        for segment in segments:
                            if isinstance(segment, dict) and "name" in segment and "companies" in segment:
                                structured_findings.append(segment)
                        if structured_findings:
                            return structured_findings
                except json.JSONDecodeError:
                    pass
        
        # TIER 3: Parse individual segment blocks with regex
        # Pattern: {"name": "Segment Name", "companies": [...]}
        segment_pattern = r'\{\s*"name"\s*:\s*"([^"]+)"\s*,\s*"companies"\s*:\s*\[(.*?)\]\s*\}'
        segment_matches = list(re.finditer(segment_pattern, final_text, re.DOTALL))
        
        if segment_matches:
            structured_findings = []
            for match in segment_matches:
                segment_name = match.group(1)
                companies_json = match.group(2)
                
                # Parse individual company objects
                companies = self._parse_company_objects(companies_json)
                
                if companies:
                    structured_findings.append({
                        "name": segment_name,
                        "companies": companies
                    })
            
            if structured_findings:
                return structured_findings
        
        # TIER 4: Look for any company objects and group them generically
        # Pattern: {"company": "...", "summary": "...", ...}
        company_pattern = r'\{\s*"company"\s*:\s*"([^"]+)"[^}]*\}'
        company_matches = re.findall(company_pattern, final_text)
        
        if company_matches:
            # Try to parse each company object
            companies = self._parse_company_objects(final_text)
            if companies:
                return [{
                    "name": "Claude Research Results",
                    "companies": companies
                }]
        
        # FALLBACK: Return as raw only if all parsing attempts failed
        # This should rarely happen with the robust parsing above
        return [{"raw": final_text}]
    
    def _parse_company_objects(self, text: str) -> list[dict[str, Any]]:
        """
        Extract individual company objects from a text containing JSON.
        Uses brace-depth tracking to handle nested structures correctly.
        """
        companies = []
        brace_depth = 0
        current_obj = ""
        in_company = False
        
        for char in text:
            if char == '{':
                if brace_depth == 0:
                    current_obj = "{"
                    in_company = True
                else:
                    current_obj += char
                brace_depth += 1
            elif char == '}':
                brace_depth -= 1
                current_obj += char
                if brace_depth == 0 and in_company:
                    # Try to parse this company object
                    try:
                        company_obj = json.loads(current_obj)
                        # Validate it looks like a company (has "company" field)
                        if "company" in company_obj or "name" in company_obj:
                            # Normalize field name if needed
                            if "name" in company_obj and "company" not in company_obj:
                                company_obj["company"] = company_obj.pop("name")
                            companies.append(company_obj)
                    except json.JSONDecodeError:
                        pass
                    current_obj = ""
                    in_company = False
            elif in_company:
                current_obj += char
        
        return companies

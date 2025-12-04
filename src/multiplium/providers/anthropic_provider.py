from __future__ import annotations

import json
from typing import Any, Iterable, cast

import structlog

from multiplium.providers.base import BaseAgentProvider, ProviderRunResult

log = structlog.get_logger()


def _default_json(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {k: _default_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_default_json(v) for v in value]
    return str(value)


def _decode_first_json_object(text: str) -> Any | None:
    """Attempt to decode the first JSON object embedded in `text`."""
    decoder = json.JSONDecoder()
    idx = 0
    while idx < len(text):
        start = text.find("{", idx)
        if start == -1:
            break
        try:
            obj, offset = decoder.raw_decode(text[start:])
            return obj
        except json.JSONDecodeError:
            idx = start + 1
    return None


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

        # Use standard Anthropic client
        # Note: Structured outputs beta may not be available on all accounts
        # Relying on strong prompts + robust parsing instead
        client = cast(Any, anthropic.AsyncAnthropic(
            api_key=api_key,
            timeout=300.0  # 5 minutes - simple timeout value
        ))
        
        # Use native web search tool - no MCP tools
        # Web search is built-in and automatically cites sources
        # Pricing: $10/1000 searches + standard token costs
        # Ref: https://docs.claude.com/en/docs/agents-and-tools/tool-use/web-search-tool
        tools = [
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": self.config.max_tool_uses,
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
            # Cap turns to force convergence
            max_turns = min(self.config.max_steps, self.config.max_conversation_turns)
            for turn_num in range(max_turns):
                messages_payload: Any = messages
                tools_payload: Any = tools  # Native web search tool
                
                # On final turns, add explicit JSON reminder
                if turn_num >= max_turns - 3:
                    # Inject reminder into last user message to force JSON output
                    if messages and messages[-1]["role"] == "user":
                        last_user_msg = messages[-1]["content"]
                        if isinstance(last_user_msg, str):
                            messages[-1]["content"] = (
                                last_user_msg + 
                                "\n\n**CRITICAL REMINDER:** You MUST output ONLY valid JSON in this exact format with NO additional text, explanation, or markdown:\n"
                                '{"segments": [{"name": "segment name", "companies": [{"company": "...", "summary": "...", ...}]}]}\n'
                                "Start your response with { and end with }. No preamble, no explanation, ONLY JSON."
                            )
                
                # No extra params - rely on strong prompts for JSON output
                # Note: Anthropic's structured outputs beta is not universally available
                # The robust parsing in _extract_findings handles various output formats
                extra_params = {}
                
                # Calculate payload sizes
                import json
                system_size = len(json.dumps(system_blocks))
                messages_size = len(json.dumps(messages_payload))
                total_size = system_size + messages_size
                
                log.info(
                    "anthropic.calling_api_now",
                    turn=turn_num,
                    model=self.config.model,
                    system_blocks_count=len(system_blocks),
                    message_count=len(messages_payload),
                    total_size_kb=round(total_size / 1024, 1),
                )
                
                import time
                start_time = time.time()
                log.info("anthropic.awaiting_response", message="About to await API call...")
                
                response = await client.messages.create(
                    model=self.config.model,
                    system=system_blocks,
                    messages=messages_payload,
                    tools=tools_payload,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                    **extra_params,
                    # Note: token-efficient-tools is DEFAULT in Claude 4 models
                )
                
                elapsed = time.time() - start_time
                log.info(
                    "anthropic.response_received",
                    elapsed_seconds=round(elapsed, 2),
                    message="API call completed successfully"
                )
                
                log.debug(
                    "anthropic.api_call_complete",
                    turn=turn_num,
                    stop_reason=response.stop_reason,
                    content_blocks=len(response.content),
                )

                usage["input_tokens"] += getattr(response.usage, "input_tokens", 0)
                usage["output_tokens"] += getattr(response.usage, "output_tokens", 0)
                # Track prompt caching metrics for cost optimization
                usage["cache_creation_input_tokens"] = usage.get("cache_creation_input_tokens", 0) + getattr(response.usage, "cache_creation_input_tokens", 0)
                usage["cache_read_input_tokens"] = usage.get("cache_read_input_tokens", 0) + getattr(response.usage, "cache_read_input_tokens", 0)

                response_blocks = list(cast(Iterable[Any], response.content))
                assistant_blocks = [block.model_dump() for block in response_blocks]
                
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

                # CRITICAL: Append assistant response to messages BEFORE collecting text
                # This ensures we capture the full conversation including the latest turn
                messages.append({"role": "assistant", "content": assistant_blocks})

                # If no server tools, check if we have final text
                has_text = any(getattr(b, "type", None) == "text" for b in response_blocks)
                if has_text and not has_web_search:
                    # Final turn - collect from ENTIRE conversation including this turn
                    # This ensures we don't truncate multi-turn responses
                    final_text = self._collect_text_from_conversation(messages)
                    break

                # Web search executes server-side, results automatically included
                # Continue to next turn to get Claude's response with search results

            if final_text is None and messages:
                final_text = self._collect_text_from_conversation(messages)
        finally:
            await client.close()

        # DEBUG: Log the raw output to diagnose parsing issues
        if final_text:
            import hashlib
            text_hash = hashlib.md5(final_text.encode()).hexdigest()[:8]
            log.info(
                "anthropic.raw_output_captured",
                length=len(final_text),
                hash=text_hash,
                first_200=final_text[:200],
                last_200=final_text[-200:],
            )

        findings = self._extract_findings(final_text)
        
        # DEBUG: Log extraction results
        log.info(
            "anthropic.extraction_complete",
            findings_count=len(findings),
            findings_structure=[
                {
                    "type": "segment" if isinstance(f, dict) and "companies" in f else "raw",
                    "companies": len(f.get("companies", [])) if isinstance(f, dict) and "companies" in f else 0,
                    "keys": list(f.keys()) if isinstance(f, dict) else None
                }
                for f in findings
            ]
        )
        
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
                "- You have 30 web searches to research ALL 8 value chain segments\n"
                "- You have 20 conversational turns to complete the research\n"
                "- Use web_search to find real-time information about wine industry technology companies\n"
                "\n**SEARCH TERM VARIATIONS (use multiple per segment):**\n"
                "- Primary: [technology] + vineyard OR wine OR viticulture\n"
                "- Secondary: [technology] + agriculture wine OR winegrowing\n"
                "- Company-specific: [specific product name] + wine deployment\n"
                "- Early-stage: [technology] + wine pilot OR wine trial OR wine innovation\n"
                "\n**GEOGRAPHIC DIVERSITY TARGET (70%+ non-US):**\n"
                "Prioritize searches in major wine tech regions:\n"
                "- 🇫🇷 France: Montpellier, Bordeaux, Champagne (search in French: 'technologie viticole', 'robot vigne')\n"
                "- 🇮🇹 Italy: Verona, Sicily, Piedmont (search in Italian: 'tecnologia vinicola', 'robotica vigna')\n"
                "- 🇪🇸 Spain: La Rioja, Catalonia, Ribera (search in Spanish: 'tecnología viñedo', 'robótica viticultura')\n"
                "- 🇦🇺 Australia: Adelaide, Margaret River, Barossa\n"
                "- 🇨🇱 Chile: Maipo, Colchagua, Casablanca\n"
                "- 🇦🇷 Argentina: Mendoza, Salta\n"
                "- 🇿🇦 South Africa: Stellenbosch, Paarl\n"
                "- 🇳🇿 New Zealand: Marlborough, Central Otago\n"
                "\n**WINE TRADE PUBLICATION SOURCES (prioritize):**\n"
                "- Wines & Vines (US)\n"
                "- Wine Business Monthly (US)\n"
                "- The Drinks Business (UK)\n"
                "- VitiBiz / Vitisphere (France)\n"
                "- Meininger's International (Germany)\n"
                "- Decanter / Harpers Wine & Spirit (UK)\n"
                "- Wine Industry Advisor (US)\n"
                "- Australian & New Zealand Grapegrower & Winemaker\n"
                "\n**SEARCH STRATEGY PER SEGMENT:**\n"
                "  * Search 1-2: Geographic discovery (e.g., 'robotique vigne France 2024', 'vineyard robotics Australia')\n"
                "  * Search 3-4: Trade publication search (e.g., 'Wines Vines irrigation technology 2024')\n"
                "  * Search 5-6: Technology-specific (e.g., 'UV-C wine sanitation', 'CO2 capture winery')\n"
                "\n**INCLUDE EARLY-STAGE COMPANIES:**\n"
                "Accept companies with ANY of:\n"
                "- Pilot/trial with named winery (even if ongoing)\n"
                "- Presentation at wine tech events (VitEff, VinExpo, Wine Vision)\n"
                "- Wine industry partnership announcement\n"
                "- Agriculture technology with clear wine application\n"
                "\n- Target 10 companies per segment across 8 segments (80 total)\n"
                "- Web search automatically cites sources - extract and include those URLs\n"
                "- PACE YOURSELF: Allocate searches strategically across all segments"
            ),
        }
        
        # Thesis context (cached - large and stable)
        thesis_block = {
            "type": "text",
            "text": f"\n\nInvestment thesis:\n{thesis}",
            # TEMP: Disabled cache control for debugging
            # "cache_control": {"type": "ephemeral"},
        }
        
        # Value chain context (cached - large and stable)
        value_chain_block = {
            "type": "text",
            "text": f"\n\nValue chain context:\n{json.dumps(value_chain, indent=2)}",
            # TEMP: Disabled cache control for debugging
            # "cache_control": {"type": "ephemeral"},
        }
        
        # KPI definitions (cached - large and stable)
        kpi_block = {
            "type": "text",
            "text": (
                f"\n\nKPI definitions:\n{json.dumps(kpis, indent=2)}"
                "\n\n**ABSOLUTELY REQUIRED OUTPUT FORMAT - JSON ONLY:**"
                "\n\n⚠️ YOUR FINAL RESPONSE MUST BE VALID JSON WITH NO ADDITIONAL TEXT ⚠️"
                "\nDo NOT include explanations, markdown, or commentary."
                "\nDo NOT say 'Here is the JSON' or 'I found these companies'."
                "\nDo NOT include ## headers or narrative text."
                "\nSTART your final response with { and END with }"
                "\n\nExact JSON structure required:"
                '\n{"segments": [{"name": str, "companies": [{'
                '\n  "company": str,'
                '\n  "summary": str (brief description),'
                '\n  "kpi_alignment": [str] (list of KPI impacts),'
                '\n  "sources": [str] (3-5 URLs),'
                '\n  "website": str (company official website URL),'
                '\n  "country": str (headquarters country)'
                '\n}]}]}'
                '\n\n**CRITICAL:** '
                '\n1. Output ONLY valid JSON - no preamble, no explanation'
                '\n2. Always include "website" and "country" for every company'
                '\n3. On your FINAL turn, output the complete JSON object'
            ),
            # TEMP: Disabled cache control for debugging
            # "cache_control": {"type": "ephemeral"},
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
            "   - Example: 'Biome Makers revenue funding competitors team'\n"
            "   - **Deep research:** Search for company details (team, clients, financials, competitors)\n"
            "3. **Gap Filling (1-2 searches):** If coverage gaps exist, search underrepresented regions or value chain stages\n"
            "   - Example: 'WiseConn Chile vineyard deployment'\n"
            "   - Use anchor companies from value chain as leads\n\n"
            "**PACING STRATEGY:**\n"
            "- Turns 1-8: Research viticulture segments (Soil Health, Irrigation, IPM, Canopy) - 24 searches\n"
            "- Turns 9-12: Research other value chain stages (Vinification, Packaging, Logistics, etc.) - 6 searches\n"
            "- Turns 13-20: Synthesize, fill gaps, format JSON output\n\n"
            "**CRITICAL FINAL OUTPUT:**\n"
            "After completing your research (typically turns 15-18), you MUST output ONLY a valid JSON object.\n"
            "NO markdown, NO explanations, NO narrative text - ONLY JSON.\n"
            "\n"
            "Your final message should start with { and end with }\n"
            "Include ALL segments with 8-10 companies each.\n"
            "For EACH company: name, summary, kpi_alignment, sources (3-5 URLs), website, country.\n"
            "\n"
            "Example of what your FINAL response should look like:\n"
            '{"segments": [{"name": "1. Grape Production", "companies": [{"company": "Biome Makers", "summary": "...", "kpi_alignment": [...], "sources": [...], "website": "...", "country": "..."}]}]}'
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
        
        # TIER 0: attempt to decode the first JSON object embedded in the text
        candidate = _decode_first_json_object(final_text)
        if isinstance(candidate, dict):
            segments = candidate.get("segments")
            if isinstance(segments, list) and segments:
                structured_findings = []
                for segment in segments:
                    if isinstance(segment, dict) and "name" in segment and "companies" in segment:
                        structured_findings.append(segment)
                if structured_findings:
                    return structured_findings
        
        # TIER 1: Try parsing as direct JSON without searching
        try:
            data = json.loads(final_text)
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

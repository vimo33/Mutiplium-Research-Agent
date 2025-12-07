from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any, TypedDict, cast

from multiplium.prompts.model_config import (
    get_model_config,
    is_gemini_3,
    is_gemini_2_5,
    get_recommended_timeout,
    adapt_prompt_for_model,
    ModelFamily,
)
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

        # Use default API version (no HttpOptions needed for latest SDK)
        client = cast(Any, genai.Client(api_key=api_key))

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
            import asyncio
            import structlog
            segment_log = structlog.get_logger()
            
            # Log model configuration being used
            model_cfg = get_model_config(self.config.model)
            segment_log.info(
                "google.model_config",
                model=self.config.model,
                family=model_cfg.family.value,
                temperature=model_cfg.default_temperature,
                supports_thinking=model_cfg.supports_thinking,
                thinking_budget=model_cfg.thinking_budget,
            )
            
            for segment_idx, segment_name in enumerate(segment_names, 1):
                segment_log.info(
                    "google.segment_start",
                    segment=segment_name,
                    segment_num=segment_idx,
                    total_segments=len(segment_names),
                    model_family=model_cfg.family.value,
                )
                system_prompt = self._build_system_prompt(context, segment_name)
                user_prompt = self._build_segment_user_prompt(segment_name, context)

                # Enable Google Search grounding with dynamic retrieval
                # This allows Gemini to decide when to search based on query complexity
                google_search_tool = types.Tool(
                    google_search=types.GoogleSearch()
                )
                tools = [google_search_tool]

                conversation: list[types.Content] = [
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=user_prompt)],
                    )
                ]

                final_response_text: str | None = None

                # FULL RUN: Cap at 20 turns to force convergence
                max_turns = min(self.config.max_steps, 20)
                segment_start_time = asyncio.get_event_loop().time()
                
                # Use model-specific timeout (thinking models need more time)
                model_config = get_model_config(self.config.model)
                base_segment_timeout = 600.0  # 10 minutes base
                segment_timeout = get_recommended_timeout(self.config.model, base_segment_timeout)
                
                # Track consecutive errors for backoff
                consecutive_errors = 0
                max_consecutive_errors = 5
                
                for turn_num in range(max_turns):
                    # Check segment timeout
                    elapsed = asyncio.get_event_loop().time() - segment_start_time
                    if elapsed > segment_timeout:
                        if not final_response_text:
                            final_response_text = ""
                        break
                    
                    try:
                        # Configure thinking based on model capabilities
                        # Uses model_config to determine if thinking is supported
                        thinking_config = None
                        if model_config.supports_thinking and is_gemini_3(self.config.model):
                            thinking_config = types.ThinkingConfig(
                                thinking_budget=model_config.thinking_budget or 512,
                                include_thoughts=model_config.include_thoughts_in_response,
                            )
                        
                        # Use model-appropriate temperature
                        # Gemini 3 REQUIRES 1.0, Gemini 2.5 works better with lower values
                        effective_temperature = model_config.default_temperature
                        if self.config.temperature is not None:
                            # Only override if within model's valid range
                            if model_config.min_temperature <= self.config.temperature <= model_config.max_temperature:
                                effective_temperature = self.config.temperature
                        
                        # Add per-turn timeout (longer for thinking models)
                        turn_timeout = 90.0 if is_gemini_3(self.config.model) else 60.0
                        response = await asyncio.wait_for(
                            client.aio.models.generate_content(
                                model=self.config.model,
                                contents=conversation,
                                config=types.GenerateContentConfig(
                                    system_instruction=system_prompt,
                                    tools=tools,
                                    temperature=effective_temperature,
                                    thinking_config=thinking_config,
                                ),
                            ),
                            timeout=turn_timeout,
                        )
                        # Reset error counter on success
                        consecutive_errors = 0
                    except asyncio.TimeoutError:
                        # Log timeout but continue to next turn
                        consecutive_errors += 1
                        continue
                    except Exception as e:
                        # Handle transient errors (503 overloaded, etc.)
                        error_str = str(e).lower()
                        is_transient = (
                            "503" in error_str or 
                            "overloaded" in error_str or 
                            "unavailable" in error_str or
                            "server" in error_str
                        )
                        
                        if is_transient and consecutive_errors < max_consecutive_errors:
                            consecutive_errors += 1
                            # Exponential backoff: 10s, 20s, 40s, 80s, 120s
                            wait_time = min(10 * (2 ** (consecutive_errors - 1)), 120)
                            import structlog
                            structlog.get_logger().warning(
                                "google.transient_error_retry",
                                segment=segment_name,
                                error=str(e)[:200],
                                consecutive_errors=consecutive_errors,
                                wait_seconds=wait_time,
                            )
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            # Non-transient or too many consecutive errors - re-raise
                            raise

                    usage_meta = getattr(response, "usage_metadata", None)
                    if usage_meta is not None:
                        total_input_tokens += getattr(usage_meta, "prompt_token_count", 0) or 0
                        total_output_tokens += getattr(usage_meta, "candidates_token_count", 0) or 0

                    candidate = response.candidates[0] if getattr(response, "candidates", None) else None
                    if candidate is not None and candidate.content is not None:
                        conversation.append(candidate.content)

                    # Google Search grounding is automatic - no function calls to handle
                    # Just check if we have a response
                    if not response.text:
                        # No more content, continue to next turn
                        continue
                    else:
                        final_response_text = response.text
                        # If response includes grounding metadata, log it
                        if hasattr(response, 'grounding_metadata') and response.grounding_metadata:
                            tool_usage['google_search'] += 1
                        # Check if model wants to output JSON (contains "segment" and "companies")
                        if '"segment"' in final_response_text and '"companies"' in final_response_text:
                            break

                segment_text = final_response_text or ""
                # Debug: Log raw response for troubleshooting
                segment_log.debug(
                    "google.segment_raw_response",
                    segment=segment_name,
                    response_length=len(segment_text) if segment_text else 0,
                    response_preview=segment_text[:500] if segment_text else "EMPTY",
                )
                
                segment_data = self._extract_segment_output(segment_text, segment_name)
                companies = segment_data.get("companies", [])
                
                # Log if no companies found
                if not companies:
                    segment_log.warning(
                        "google.no_companies_extracted",
                        segment=segment_name,
                        notes=segment_data.get("notes", []),
                    )

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
                segment_log.info(
                    "google.segment_complete",
                    segment=segment_name,
                    segment_num=segment_idx,
                    companies_found=len(companies),
                )

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
        from google.genai import types
        
        tool_declarations: list[Any] = []
        for spec in self.tool_manager.iter_specs():
            # Clean schema for Google GenAI - remove additionalProperties
            cleaned_schema = self._clean_schema_for_google(spec.input_schema)
            tool_declarations.append(
                function_declaration_cls(
                    name=spec.name,
                    description=spec.description,
                    parameters=cleaned_schema,
                )
            )
        # Wrap function declarations in Tool objects
        return [types.Tool(function_declarations=tool_declarations)] if tool_declarations else []
    
    def _clean_schema_for_google(self, schema: dict[str, Any]) -> dict[str, Any]:
        """Remove fields that Google GenAI doesn't accept (like additionalProperties)."""
        import copy
        cleaned = copy.deepcopy(schema)
        
        # Remove additionalProperties at root level
        cleaned.pop("additionalProperties", None)
        
        # Recursively clean nested schemas
        if "properties" in cleaned:
            for prop_name, prop_schema in cleaned["properties"].items():
                if isinstance(prop_schema, dict):
                    cleaned["properties"][prop_name] = self._clean_nested_schema(prop_schema)
        
        return cleaned
    
    def _clean_nested_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
        """Recursively remove Google-incompatible fields from nested schemas."""
        import copy
        cleaned = copy.deepcopy(schema)
        cleaned.pop("additionalProperties", None)
        
        # Clean nested properties
        if "properties" in cleaned:
            for prop_name, prop_schema in cleaned["properties"].items():
                if isinstance(prop_schema, dict):
                    cleaned["properties"][prop_name] = self._clean_nested_schema(prop_schema)
        
        # Clean array items
        if "items" in cleaned and isinstance(cleaned["items"], dict):
            cleaned["items"] = self._clean_nested_schema(cleaned["items"])
        
        return cleaned

    def _build_system_prompt(self, context: Any, segment_name: str) -> str:
        """Builds the main system prompt with impact investment focus and full context.
        
        Uses model-specific prompt adaptation for optimal results across Gemini versions.
        """
        thesis = getattr(context, "thesis", "").strip()
        value_chain = _default_json(getattr(context, "value_chain", []))
        kpis = _default_json(getattr(context, "kpis", {}))
        
        # Extract anchor companies for this segment from value chain
        anchor_companies = self._extract_anchor_companies(context, segment_name)
        anchor_text = ""
        if anchor_companies:
            anchor_text = (
                "\n\n**ANCHOR COMPANIES TO RESEARCH (Start with these as references):**\n"
                + "\n".join(f"- {company}" for company in anchor_companies)
                + "\n\nUse these as starting points, verify their vineyard evidence, then find similar companies."
            )
        
        # Get segment-specific search strategies
        search_strategies = self._get_search_strategies(segment_name)
        
        # Build base system prompt
        base_prompt = (
            "You are a senior analyst for an **impact investment** fund specializing in wine industry technology. "
            "Your primary objective is to identify companies that generate positive, measurable environmental and social impact "
            "while maintaining strong business potential.\n\n"
            f"**YOUR MISSION:** Identify 10 unique companies in the '{segment_name}' segment.\n\n"
            "**EVALUATION FRAMEWORK:**\n"
            "For each candidate company, systematically evaluate:\n"
            "1. ✓ **Vineyard Evidence:** Does the company have a named winery/vineyard deployment? (Required)\n"
            "2. ✓ **Direct KPI Impact:** Are the claimed impacts direct, not indirect/implied? (Score 1-5)\n"
            "3. ✓ **Source Quality:** What tier are the sources? Tier 1 (academic), Tier 2 (industry), Tier 3 (vendor)\n"
            "4. ✓ **Quantified Metrics:** Are there specific numbers (%, hectares, tCO2e, liters)?\n\n"
            "**CONFIDENCE SCORING:**\n"
            "- 0.8-1.0: Strong vineyard evidence + Tier 1/2 sources + quantified metrics\n"
            "- 0.6-0.79: Good evidence but limited to Tier 2/3 sources\n"
            "- 0.4-0.59: Some vineyard connection but vague metrics or only Tier 3 sources\n"
            "- Below 0.4: Exclude - insufficient evidence\n\n"
            "**MANDATORY REQUIREMENTS:**\n"
            "1. VINEYARD EVIDENCE: Every company MUST cite at least ONE vineyard-specific deployment, named winery customer, or viticulture case study.\n"
            "2. NO INDIRECT IMPACTS: Reject claims marked '(indirectly)', 'implied', 'potentially', or 'could lead to'.\n"
            "3. SOURCE QUALITY: Flag companies with only Tier 3 sources as 'Low Confidence' (confidence_0to1 < 0.6).\n"
            "4. QUANTIFIED METRICS: Prefer specific percentages, hectares, tCO2e values over vague claims.\n"
            "5. INVESTABLE ENTITIES ONLY: Include ONLY private companies that can accept investment.\n"
            "   - EXCLUDE: NGOs, foundations, certification bodies (Demeter, EcoCert), government programs,\n"
            "     industry associations/councils, EU/LIFE funded projects, cooperatives, research initiatives.\n"
            "   - INCLUDE: Startups, scale-ups, established tech companies with products/services.\n\n"
            f"**SEARCH STRATEGY FOR '{segment_name}':**\n{search_strategies}\n"
            + anchor_text +
            f"\n\n**INVESTMENT THESIS:**\n{thesis}"
            f"\n\n**VALUE CHAIN CONTEXT:**\n{json.dumps(value_chain, indent=2)}"
            f"\n\n**KPI FRAMEWORK:**\n{json.dumps(kpis, indent=2)}"
            "\n\n**OUTPUT FORMAT (JSON only, no markdown):**\n"
            "Return your findings as a JSON object. Include ALL required fields for each company.\n\n"
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
            "**CRITICAL:** Output ONLY valid JSON. Start with { and end with }. No markdown code blocks, no explanations."
        )
        
        # Apply model-specific prompt adaptation
        adaptation = adapt_prompt_for_model(
            self.config.model,
            base_prompt,
            "",  # User prompt handled separately
            segment_name=segment_name,
        )
        
        return adaptation.system_prompt

    def _build_segment_user_prompt(self, segment_name: str, context: Any) -> str:
        """Builds the initial user prompt to kick off research for a segment."""
        search_keywords = self._get_search_keywords(segment_name)
        keywords_text = "\n".join([f"  - \"{kw}\"" for kw in search_keywords])
        
        return (
            f"🎯 **MISSION:** Find EXACTLY 10 unique companies in the '{segment_name}' segment.\n\n"
            "**TURN BUDGET:** You have 20 turns maximum. Pace yourself:\n"
            "- Turns 1-10: Discover companies using Google Search with targeted queries\n"
            "- Turns 11-15: Verify top candidates have vineyard-specific evidence\n"
            "- Turns 16-20: Finalize your list and output JSON\n"
            "- **Output by turn 18** even if you haven't reached 10 companies.\n\n"
            "**SYSTEMATIC RESEARCH APPROACH:**\n"
            f"Use Google Search grounding with these optimized queries:\n{keywords_text}\n\n"
            "**RESEARCH WORKFLOW:**\n"
            "1. Search for companies using the keywords above\n"
            "2. For each promising company, verify vineyard/winery deployment evidence\n"
            "3. Look for case studies, customer testimonials, and impact metrics\n"
            "4. Find funding information and company backgrounds\n"
            "5. Assess source quality (Tier 1/2/3) and assign confidence score\n"
            "6. If under 10 companies, expand with geographic variations\n\n"
            "**REQUIRED OUTPUT FIELDS (for EVERY company):**\n"
            "- `company`: Unique company name\n"
            "- `summary`: 2-3 sentences with specific metrics/impact data\n"
            "- `kpi_alignment`: 2-3 explicit KPI alignments with quantitative evidence\n"
            "- `sources`: 3-5 verified source URLs\n"
            "- `website`: Official company website URL\n"
            "- `country`: Headquarters country (e.g., 'Spain', 'Israel', 'Australia')\n"
            "- `confidence_0to1`: Your confidence score (0.0-1.0) based on evidence quality\n"
            "- `source_tier`: Best source tier ('Tier 1', 'Tier 2', or 'Tier 3')\n\n"
            "**IF YOU FIND FEWER THAN 10:**\n"
            "- Add geographic modifiers (Spain, France, Italy, Chile, Australia, California)\n"
            "- Try alternative technology terms\n"
            "- Search wine trade publications (Wines & Vines, Wine Business Monthly)\n"
            "- Search startup accelerators and VC portfolios\n\n"
            "Begin your research now. Output JSON when you have 10 verified companies or by turn 18."
        )

    def _extract_segment_output(self, final_text: str, segment_name: str) -> dict[str, Any]:
        """Parses the final JSON output from the model's text response."""
        if not final_text.strip():
            return {"name": segment_name, "companies": [], "notes": ["Empty response from Gemini."]}

        # Try multiple parsing strategies
        data = None
        
        # Strategy 1: JSON code block
        match = re.search(r"```json\s*(\{.*?\})\s*```", final_text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Strategy 2: Any code block
        if data is None:
            match = re.search(r"```\s*(\{.*?\})\s*```", final_text, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass
        
        # Strategy 3: Direct JSON object
        if data is None:
            try:
                data = json.loads(final_text)
            except json.JSONDecodeError:
                pass
        
        # Strategy 4: Extract JSON from mixed text
        if data is None:
            json_match = re.search(r'\{[^{}]*"segment"[^{}]*\{[^{}]*"companies"[^{}]*\[.*?\][^{}]*\}[^{}]*\}', final_text, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass
        
        # If all parsing fails, return error
        if data is None:
            return {
                "name": segment_name,
                "companies": [],
                "notes": [f"Unable to parse Gemini output after trying multiple strategies. First 200 chars: {final_text[:200]}..."],
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
            "notes": [f"Unexpected Gemini output structure: {str(data)[:200]}..."],
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

    def _extract_anchor_companies(self, context: Any, segment_name: str) -> list[str]:
        """Extract anchor companies from value chain definition for this segment."""
        value_chain = getattr(context, "value_chain", [])
        anchor_pattern = r"\*\*Anchors?:\*\*\s+([^\n]+)"
        
        for entry in value_chain:
            raw = entry.get("raw") if isinstance(entry, dict) else entry
            if not isinstance(raw, str):
                continue
            
            # Find the section for this segment
            if segment_name.split(".")[0] not in raw:
                continue
            
            # Extract anchor companies
            match = re.search(anchor_pattern, raw)
            if match:
                anchors_text = match.group(1)
                # Split by commas and clean up
                companies = [c.strip() for c in re.split(r",|;", anchors_text)]
                # Remove country codes in parentheses
                companies = [re.sub(r"\s*\([A-Z]{2}[/A-Z]*\)", "", c) for c in companies]
                return [c for c in companies if c and not c.lower().startswith("http")]
        
        return []
    
    def _get_search_keywords(self, segment_name: str) -> list[str]:
        """Get optimized search keywords for each segment."""
        keywords_map = {
            "Soil Health": [
                "soil microbiome testing vineyard",
                "soil carbon sequestration wine",
                "regenerative agriculture viticulture",
                "soil health monitoring platform vineyard",
                "microbial inoculant wine grape",
            ],
            "Precision Irrigation": [
                "smart irrigation technology vineyard",
                "precision water management wine",
                "soil moisture sensor vineyard",
                "AI irrigation optimization viticulture",
                "water stress monitoring wine grape",
            ],
            "Integrated Pest Management": [
                "IPM vineyard biological control",
                "pheromone trap monitoring wine",
                "organic pest management viticulture",
                "biocontrol solutions vineyard",
                "disease prediction vineyard AI",
            ],
            "Canopy Management": [
                "vineyard robotics pruning",
                "canopy sensing precision viticulture",
                "drone vineyard mapping",
                "robotic vineyard equipment",
                "NDVI vineyard monitoring",
            ],
            "Carbon MRV": [
                "carbon accounting wine supply chain",
                "MRV agriculture vineyard",
                "blockchain traceability wine",
                "carbon credits vineyard regenerative",
                "sustainability reporting winery",
            ],
            "Grape Production": [
                "precision viticulture technology",
                "vineyard management software",
                "grape quality monitoring",
                "harvest optimization wine",
                "yield prediction vineyard AI",
            ],
            "Wine Production": [
                "fermentation monitoring winery",
                "wine tank sensor IoT",
                "cellar automation software",
                "winemaking analytics platform",
                "quality control wine technology",
            ],
            "Packaging": [
                "wine packaging sustainability",
                "bottle filling technology wine",
                "closure technology wine",
                "lightweight glass wine bottle",
                "sustainable wine packaging",
            ],
            "Distribution": [
                "wine logistics cold chain",
                "temperature monitoring wine transport",
                "wine inventory management",
                "DTC wine platform",
                "wine shipping technology",
            ],
        }
        
        for key, keywords in keywords_map.items():
            if key.lower() in segment_name.lower():
                return keywords
        
        return [
            f"{segment_name} vineyard technology",
            f"{segment_name} wine industry",
            f"{segment_name} viticulture innovation",
            f"{segment_name} winery solution",
        ]

    def _get_search_strategies(self, segment_name: str) -> str:
        """Provides segment-specific search strategies to guide the agent."""
        strategies = {
            "Soil Health": (
                "• Search for: soil microbiome, soil carbon sequestration, regenerative agriculture tech\n"
                "• Target companies: soil testing labs, microbial inoculants, biochar producers\n"
                "• Geographic focus: France (Bordeaux), Spain, California, Australia (Adelaide)\n"
                "• Look for: vineyard case studies, ROC certifications, university partnerships"
            ),
            "Precision Irrigation": (
                "• Search for: smart irrigation, precision water management, soil moisture sensors\n"
                "• Target companies: IoT irrigation platforms, drip irrigation tech, water optimization software\n"
                "• Geographic focus: Israel, Spain, California, Chile, Australia\n"
                "• Look for: water savings metrics (%), drought resilience data, vineyard deployments"
            ),
            "Integrated Pest Management": (
                "• Search for: biological pest control, pheromone monitoring, pesticide alternatives\n"
                "• Target companies: biocontrol producers, pest monitoring platforms, organic alternatives\n"
                "• Geographic focus: France, Italy, Spain, New Zealand\n"
                "• Look for: pesticide reduction %, biodiversity impact, organic certifications"
            ),
            "Canopy Management": (
                "• Search for: precision viticulture, robotic pruning, canopy sensing, vineyard drones\n"
                "• Target companies: ag robotics, drone/satellite imaging, pruning automation\n"
                "• Geographic focus: France, Germany, USA, Australia\n"
                "• Look for: yield optimization %, labor savings, disease prevention metrics"
            ),
            "Carbon MRV": (
                "• Search for: carbon accounting, MRV platforms, blockchain traceability\n"
                "• Target companies: carbon credit platforms, supply chain software, sustainability reporting\n"
                "• Geographic focus: EU, California, Australia, South Africa\n"
                "• Look for: tons CO2 sequestered, verified carbon credits, traceability case studies"
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
        }
        return strategies.get(segment_name, "• Use general search strategies for wine/viticulture technology")

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

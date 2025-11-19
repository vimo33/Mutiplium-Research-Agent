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
            for segment_name in segment_names:
                system_prompt = self._build_system_prompt(context, segment_name)
                user_prompt = self._build_segment_user_prompt(segment_name, context)

                # Enable Google Search grounding - native capability, no MCP tools
                # MCP tools reserved for validation phase only
                tools = [types.Tool(google_search=types.GoogleSearch())]

                conversation: list[types.Content] = [
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=user_prompt)],
                    )
                ]

                final_response_text: str | None = None

                # FULL RUN: Cap at 20 turns to force convergence
                max_turns = min(self.config.max_steps, 20)
                for turn_num in range(max_turns):
                    response = await client.aio.models.generate_content(
                        model=self.config.model,
                        contents=conversation,
                        config=types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            tools=tools,
                            temperature=self.config.temperature,
                            # Note: response_mime_type not supported with function calling
                        ),
                    )

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
        """Builds the main system prompt with impact investment focus."""
        thesis = getattr(context, "thesis", "").strip()
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
        
        return (
            "You are an analyst for an **impact investment** fund. Your primary objective is to identify companies "
            "that not only have strong business potential but also generate positive, measurable environmental and social impact. "
            "Strictly adhere to the KPI framework, giving higher weight to impact-related KPIs like 'Soil Carbon Sequestration' "
            "and 'Pesticide Reduction' over purely operational metrics. "
            "If a company has strong financial indicators but lacks verifiable impact evidence (Tier 1 or Tier 2 sources), "
            "you must flag it as 'Low Confidence' or exclude it. "
            "\n\n**MANDATORY VITICULTURE REQUIREMENTS:**\n"
            "1. VINEYARD EVIDENCE REQUIRED: Every company MUST cite at least ONE vineyard-specific deployment, named winery customer, or viticulture case study. Generic agriculture platforms are EXCLUDED unless they demonstrate specific vineyard projects with named clients.\n"
            "2. NO INDIRECT IMPACTS: Core segment KPIs must show DIRECT impacts. Reject companies where primary KPIs are marked '(indirectly)' or 'implied' or 'general precision agriculture benefits' or 'potentially' or 'could lead to'.\n"
            "3. TIER 1/2 SOURCES PREFERRED: Each company should have at least ONE Tier 1 (peer-reviewed, government study, university research) or Tier 2 (industry publication, cooperative whitepaper, ESG report) source. Companies with only Tier 3 sources (vendor websites, blogs, press releases) should be flagged 'Low Confidence'.\n"
            "4. QUANTIFIED METRICS: Prefer companies with specific percentages, hectares, tCO2e values, liters saved over vague claims like 'improves soil health' or 'optimizes irrigation'.\n"
            f"\n\nYour current task is to research the value-chain segment '{segment_name}'. "
            "**CRITICAL TARGET: Find MINIMUM 10 unique companies for this segment. Use Google Search grounding for real-time web discovery.**\n"
            "**IMPORTANT:** You have 20 turns maximum. Pace yourself:\n"
            "- Turns 1-10: Discover companies using Google Search with targeted queries\n"
            "- Turns 11-15: Verify top candidates have vineyard-specific evidence\n"
            "- Turns 16-20: Finalize your list and output JSON\n"
            + anchor_text +
            "\n\n**SEARCH APPROACH:** Use Google Search with specific queries combining technology terms + 'vineyard' + geography. "
            "Example: 'soil microbiome testing vineyard Spain', 'smart irrigation sensors wine Australia'. "
            "**Do not stop early - continue searching with variations until you have at least 10 companies.**"
            f"\n\nInvestment thesis:\n{thesis}"
            f"\n\nKPIs:\n{json.dumps(kpis, indent=2)}"
            "\n\nAfter completing your research, return a final JSON object formatted as:"
            '\n```json\n{"segment": {"name": str, "companies": [{"company": str, "summary": str, "kpi_alignment": [str], "sources": [str]}]}}\n```'
            "\n\n**REMEMBER: 10 companies minimum. Use multiple search strategies and geographic variations if needed.**"
        )

    def _build_segment_user_prompt(self, segment_name: str, context: Any) -> str:
        """Builds the initial user prompt to kick off research for a segment."""
        search_keywords = self._get_search_keywords(segment_name)
        keywords_text = ", ".join(f'"{kw}"' for kw in search_keywords[:5])
        
        return (
            f"🎯 MISSION: Find EXACTLY 10 unique companies in '{segment_name}' segment.\n\n"
            "**SYSTEMATIC APPROACH:**\n"
            "1. Start with anchor companies if provided - verify their vineyard evidence\n"
            f"2. Use broad search queries with keywords: {keywords_text}\n"
            "3. For EACH promising result, use extract_content or fetch_content to verify impact claims\n"
            "4. Use perplexity_search or perplexity_ask for company verification and enrichment\n"
            "5. Use search_academic_papers to find scientific validation for technologies\n"
            "6. Continue searching with geographic variations (Europe, US, Australia, South America, etc.)\n"
            "7. DO NOT STOP until you have researched 10 verified companies\n\n"
            "**FOR EACH COMPANY:**\n"
            "- Unique name (no duplicates)\n"
            "- 2-3 sentence summary with specific metrics/impact data\n"
            "- 2-3 explicit KPI alignments with quantitative evidence\n"
            "- 3-5 verified sources (mix of company site, case studies, academic papers, certifications)\n\n"
            "**SEARCH STRATEGY IF YOU FIND FEWER THAN 10:**\n"
            "- Add geographic modifiers (Spain, France, Italy, Chile, Australia, California, etc.)\n"
            "- Try alternative technology terms (e.g., 'precision viticulture' vs 'smart vineyard')\n"
            "- Search for university research partnerships\n"
            "- Look for startup accelerators and VC portfolios\n"
            "- Check industry awards and certifications\n\n"
            "Execute a comprehensive research workflow. Use all available tools. Do NOT finish until you have 10 companies!"
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
            "Soil Health": ["soil microbiome", "soil carbon", "regenerative agriculture", "soil testing vineyard"],
            "Precision Irrigation": ["smart irrigation vineyard", "precision water", "soil moisture sensor", "irrigation automation wine"],
            "Integrated Pest Management": ["IPM vineyard", "biological pest control", "pheromone trap", "organic pest management wine"],
            "Canopy Management": ["vineyard robotics", "canopy sensing", "precision viticulture", "drone vineyard"],
            "Carbon MRV": ["carbon accounting wine", "MRV agriculture", "blockchain traceability wine", "carbon credits vineyard"],
        }
        
        for key, keywords in keywords_map.items():
            if key.lower() in segment_name.lower():
                return keywords
        
        return [segment_name, f"{segment_name} vineyard", f"{segment_name} wine technology"]

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

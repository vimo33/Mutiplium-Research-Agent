"""MCP-based quality validator for research findings.

NEW ARCHITECTURE:
- Providers use native search (OpenAI web, Google Grounding, Claude reasoning)
- Validation uses MCP tools (Tavily + Perplexity) for deep verification
- This prevents Tavily exhaustion during discovery phase
- More strategic use of MCP tools in validation

PERPLEXITY BEST PRACTICES:
- Uses structured prompts with explicit format requirements
- Multi-strategy response parsing with fallbacks
- Comprehensive country and URL validation
- Rate-limited to prevent API exhaustion
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import structlog

logger = structlog.get_logger()

# Comprehensive list of countries for validation
VALID_COUNTRIES = {
    # Major countries (common in agtech)
    "United States", "USA", "US", "Canada", "Mexico",
    "United Kingdom", "UK", "France", "Germany", "Italy", "Spain", "Portugal",
    "Netherlands", "Belgium", "Switzerland", "Austria", "Denmark", "Sweden",
    "Norway", "Finland", "Ireland", "Poland", "Czech Republic", "Hungary",
    "Australia", "New Zealand", "Japan", "China", "India", "South Korea",
    "Israel", "South Africa", "Brazil", "Argentina", "Chile", "Colombia",
    "Singapore", "Taiwan", "Thailand", "Vietnam", "Indonesia", "Malaysia",
    "Greece", "Turkey", "Romania", "Bulgaria", "Croatia", "Slovenia",
    "Estonia", "Latvia", "Lithuania", "Ukraine", "Russia",
    # Wine regions specifically
    "Georgia", "Moldova", "Morocco", "Tunisia", "Lebanon",
}

# Country name normalization (map variations to canonical names)
COUNTRY_ALIASES = {
    "usa": "United States",
    "us": "United States",
    "u.s.": "United States",
    "u.s.a.": "United States",
    "america": "United States",
    "uk": "United Kingdom",
    "u.k.": "United Kingdom",
    "britain": "United Kingdom",
    "great britain": "United Kingdom",
    "england": "United Kingdom",
    "deutschland": "Germany",
    "italia": "Italy",
    "espana": "Spain",
    "españa": "Spain",
    "brasil": "Brazil",
    "schweiz": "Switzerland",
    "suisse": "Switzerland",
    "the netherlands": "Netherlands",
    "holland": "Netherlands",
}

# Entity types that indicate non-investable organizations
# These patterns match against company names to filter out NGOs, studies, and initiatives
NON_INVESTABLE_PATTERNS = [
    # Explicit non-profit/government indicators in name
    r"\binitiative\b",
    r"\bprogram(?:me)?\b",
    r"\bproject\b",
    r"\bstudy\b",
    r"\bfoundation\b",
    r"\binstitute\b",
    r"\buniversity\b",
    r"\bconsortium\b",
    r"\balliance\b",
    r"\bassociation\b",
    r"\bcouncil\b",
    r"\bnetwork\b",  # e.g., "WineTech Network" - industry body not a company
    r"\bsociety\b",
    r"\bfederation\b",
    r"\bcoalition\b",
    r"\bprotocol\b",  # e.g., "Porto Protocol"
    r"\bcertification\s+body\b",
    r"\bcertification\s+scheme\b",
    r"\bcertification\s+program\b",
    r"\bngo\b",
    r"\bnon[\s-]?profit\b",
    r"\bgovernment\b",
    r"\bagency\b",
    r"\bauthority\b",
    r"\bcommission\b",
    r"\bboard\b",
    r"\bministry\b",
    r"\bdepartment\b",
    r"\bcooperative\b",  # Co-ops are not traditional investment targets
    r"\bco-op\b",
    # EU/UN/Government funded projects
    r"\blife\s+(?:program|project)\b",
    r"\beu\s+funded\b",
    r"\bhorizon\s+\d+\b",
    # Certification bodies (not companies)
    r"^demeter\b",  # Demeter International - certification body
    r"^ecocert\b",
    r"^usda\s+organic\b",
    # Industry bodies/exchanges (borderline but typically not VC-investable)
    r"\bexchange\b",  # e.g., Liv-ex (London International Vintners Exchange)
]

# Patterns in summaries that indicate non-investable entities
NON_INVESTABLE_SUMMARY_PATTERNS = [
    r"certification\s+body",
    r"industry\s+(?:body|association|group|initiative)",
    r"government[\s-]funded",
    r"publicly[\s-]funded",
    r"eu[\s-]funded",
    r"non[\s-]?profit\s+(?:organization|organisation)",
    r"research\s+(?:project|study|programme|program|initiative)",
    r"pilot\s+(?:project|programme|program|test)",
    r"funded\s+by\s+(?:the\s+)?(?:eu|government|public)",
    r"life\s+program",  # EU LIFE program funded projects
    # Industry exchanges/marketplaces (not typical investment targets)
    r"(?:international|global)\s+(?:vintners?\s+)?exchange",
    r"(?:global|international)\s+marketplace\s+for\s+(?:the\s+)?(?:professional\s+)?(?:wine|fine\s+wine)\s+trade",
    # Cork recycling programs (NGO-like)
    r"cork\s+recycling\s+program",
    r"cork\s+take[\s-]?back\s+program",
]


class CompanyValidator:
    """Post-research validator using MCP tools for verification and enrichment."""

    def __init__(self, tool_manager: Any, use_dedicated_enrichment: bool = True) -> None:
        self.tool_manager = tool_manager
        self.use_dedicated_enrichment = use_dedicated_enrichment
        self._enrichment_stats = {
            "attempted": 0,
            "successful": 0,
            "failed": 0,
        }

    async def validate_and_enrich_companies(
        self,
        companies: list[dict[str, Any]],
        segment: str,
    ) -> list[dict[str, Any]]:
        """
        Uses MCP tools to validate and enrich company data.

        Steps:
        1. Verify vineyard deployments (Tavily)
        2. Check company legitimacy (Perplexity)
        3. Validate KPI claims (Tavily extract)
        4. Fill missing data (website, country, confidence)
        5. Deduplicate companies (track duplicates in metadata)
        6. Reject low-quality entries
        """
        if not companies:
            return []

        validated: list[dict[str, Any]] = []
        rejected_count = 0
        seen_companies: dict[str, dict[str, Any]] = {}  # Track by normalized name
        duplicate_count = 0

        for idx, company in enumerate(companies, 1):
            company_name = company.get("company", f"Unknown-{idx}")
            logger.info(
                "validation.company_start",
                company=company_name,
                segment=segment,
                index=f"{idx}/{len(companies)}",
            )

            # Step 0: Check if entity is investable (not NGO/study/initiative)
            try:
                is_investable, rejection_reason = self._is_investable_entity(company)
                if not is_investable:
                    logger.warning(
                        "validation.rejected",
                        company=company_name,
                        reason=f"Non-investable entity: {rejection_reason}",
                    )
                    rejected_count += 1
                    continue
            except Exception as e:
                logger.error(
                    "validation.investability_check_failed",
                    company=company_name,
                    error=str(e),
                )
                # Don't reject on check failure, continue to other validations

            # Step 1: Quick vineyard verification (lightweight - just check sources)
            try:
                # Quick check: Do sources mention vineyard keywords OR early-stage wine indicators?
                sources_text = " ".join(company.get("sources", [])).lower()
                summary_text = company.get("summary", "").lower()
                combined_text = sources_text + " " + summary_text
                
                # Primary: Direct vineyard evidence
                vineyard_keywords = ["vineyard", "winery", "wine", "viticulture", "grape"]
                has_vineyard_mention = any(kw in combined_text for kw in vineyard_keywords)
                
                # Secondary: Early-stage wine industry indicators
                early_stage_indicators = [
                    "wine pilot", "wine trial", "wine partnership", 
                    "wine innovation", "wine tech", "viteff", "vinexpo",
                    "wine vision", "wine industry", "winegrowing"
                ]
                has_early_stage_indicator = any(ind in combined_text for ind in early_stage_indicators)
                
                if not has_vineyard_mention and not has_early_stage_indicator:
                    logger.warning(
                        "validation.rejected",
                        company=company_name,
                        reason="No vineyard keywords or wine industry indicators in sources",
                    )
                    rejected_count += 1
                    continue
                    
                verification = {"is_valid": True, "evidence": None}
            except Exception as e:
                logger.error(
                    "validation.verification_failed",
                    company=company_name,
                    error=str(e),
                )
                verification = {"is_valid": True, "evidence": None}

            # Step 2: Smart enrichment (lightweight + strategic MCP)
            try:
                enriched = company.copy()
                enriched.setdefault("segment", segment)
                enriched.setdefault("region_state", "N/A")
                
                # First: Try lightweight extraction from sources URLs
                if not enriched.get("website") or enriched.get("website") == "N/A":
                    enriched["website"] = self._extract_website_from_sources(enriched.get("sources", []))
                
                # Second: Use Perplexity only if still missing critical data (rate limiting)
                missing_critical = (
                    not enriched.get("website") or enriched.get("website") == "N/A" or
                    not enriched.get("country") or enriched.get("country") == "N/A"
                )
                if missing_critical:
                    enriched = await self._enrich_company_data(enriched, segment)
                
                # Final fallback to N/A
                enriched.setdefault("website", "N/A")
                enriched.setdefault("country", "N/A")
                
            except Exception as e:
                logger.error(
                    "validation.enrichment_failed",
                    company=company_name,
                    error=str(e),
                )
                enriched = company.copy()
                enriched.setdefault("website", "N/A")
                enriched.setdefault("country", "N/A")
                enriched.setdefault("region_state", "N/A")
                enriched.setdefault("segment", segment)

            # Step 3: Lightweight KPI validation (no MCP calls - just pattern matching)
            try:
                kpi_valid = self._validate_kpi_claims_lightweight(enriched)
                if not kpi_valid:
                    logger.warning(
                        "validation.rejected",
                        company=company_name,
                        reason="KPI claims contain indirect/implied markers",
                    )
                    rejected_count += 1
                    continue
            except Exception as e:
                logger.error(
                    "validation.kpi_validation_failed",
                    company=company_name,
                    error=str(e),
                )
                # Don't reject on validation error
                kpi_valid = True

            # Step 4: Calculate confidence score
            enriched["vineyard_verified"] = verification["is_valid"]
            enriched["confidence_0to1"] = self._calculate_confidence(enriched)

            # Adjusted threshold: 0.45 to balance quality and coverage
            if enriched["confidence_0to1"] < 0.45:
                logger.warning(
                    "validation.rejected",
                    company=company_name,
                    reason=f"Low confidence: {enriched['confidence_0to1']:.2f}",
                )
                rejected_count += 1
                continue

            # Step 5: Deduplication check
            normalized_name = self._normalize_company_name(company_name)
            
            if normalized_name in seen_companies:
                # Duplicate found - keep the one with higher confidence
                existing = seen_companies[normalized_name]
                duplicate_count += 1
                
                if enriched["confidence_0to1"] > existing["confidence_0to1"]:
                    # Replace with higher confidence version
                    logger.info(
                        "validation.duplicate_replaced",
                        company=company_name,
                        existing_confidence=existing["confidence_0to1"],
                        new_confidence=enriched["confidence_0to1"],
                    )
                    # Mark the existing one as duplicate
                    existing["is_duplicate"] = True
                    existing["duplicate_of"] = company_name
                    # Add duplicate metadata to new one
                    enriched["had_duplicate"] = True
                    enriched["duplicate_sources"] = existing.get("sources", [])
                    seen_companies[normalized_name] = enriched
                else:
                    # Keep existing, mark current as duplicate
                    logger.info(
                        "validation.duplicate_skipped",
                        company=company_name,
                        kept_company=existing.get("company"),
                        existing_confidence=existing["confidence_0to1"],
                    )
                    enriched["is_duplicate"] = True
                    enriched["duplicate_of"] = existing.get("company")
                    # Add duplicate info to existing
                    if "duplicates_found" not in existing:
                        existing["duplicates_found"] = []
                    existing["duplicates_found"].append({
                        "name": company_name,
                        "confidence": enriched["confidence_0to1"],
                        "sources": enriched.get("sources", [])
                    })
                continue
            else:
                # New company - add to seen and validated
                seen_companies[normalized_name] = enriched
                validated.append(enriched)
                logger.info(
                    "validation.accepted",
                    company=company_name,
                    confidence=enriched["confidence_0to1"],
                )

        logger.info(
            "validation.segment_complete",
            segment=segment,
            validated=len(validated),
            rejected=rejected_count,
            duplicates=duplicate_count,
            total=len(companies),
        )

        return validated
    
    def _normalize_company_name(self, name: str) -> str:
        """Normalize company name for deduplication."""
        import re
        
        # Convert to lowercase
        normalized = name.lower()
        
        # Remove common suffixes and legal entities
        suffixes = [
            r'\s+inc\.?$', r'\s+llc\.?$', r'\s+ltd\.?$', r'\s+gmbh\.?$',
            r'\s+ag\.?$', r'\s+sa\.?$', r'\s+spa\.?$', r'\s+corp\.?$',
            r'\s+corporation$', r'\s+limited$', r'\s+co\.?$',
            r'\s+plc\.?$', r'\s+pty\.?$', r'\s+b\.?v\.?$'
        ]
        for suffix in suffixes:
            normalized = re.sub(suffix, '', normalized)
        
        # Remove special characters and extra spaces
        normalized = re.sub(r'[^a-z0-9\s]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized

    def _extract_website_from_sources(self, sources: list[str]) -> str:
        """Extract company website from sources URLs (lightweight, no API calls)."""
        import re
        from urllib.parse import urlparse
        
        if not sources:
            return "N/A"
        
        # Look for company website patterns (not generic domains)
        excluded_domains = {
            "github.com", "linkedin.com", "twitter.com", "facebook.com",
            "youtube.com", "medium.com", "crunchbase.com", "wikipedia.org",
            "pmc.ncbi.nlm.nih.gov", "pubmed.ncbi.nlm.nih.gov", "doi.org",
            "springer.com", "wiley.com", "mdpi.com", "frontiersin.org",
            "winebusiness.com", "wines-vines.com", "wineenthusiast.com",
            "google.com", "bing.com", "reddit.com", "quora.com"
        }
        
        for url in sources:
            try:
                parsed = urlparse(url)
                domain = parsed.netloc.lower().replace("www.", "")
                
                # Skip excluded domains
                if any(excluded in domain for excluded in excluded_domains):
                    continue
                
                # If domain looks like a company site, return it
                if domain and "." in domain:
                    return f"https://{domain}"
            except:
                continue
        
        return "N/A"

    async def _verify_vineyard_deployment(
        self,
        company: dict[str, Any],
    ) -> dict[str, Any]:
        """Use Tavily to verify vineyard-specific evidence."""
        company_name = company.get("company", "")
        if not company_name:
            return {"is_valid": False, "evidence": None}

        # Use Tavily advanced search for verification
        query = f"{company_name} vineyard viticulture winery deployment case study"

        try:
            results = await self.tool_manager.invoke(
                "search_web",
                query=query,
                search_depth="advanced",
                max_results=5,
                topic="general",
            )

            # Check if results mention vineyard/wine/viticulture
            vineyard_keywords = [
                "vineyard",
                "winery",
                "wine",
                "viticulture",
                "grape",
                "vitis vinifera",
                "oenology",
                "enology",
            ]

            results_text = str(results).lower()
            keyword_matches = sum(1 for keyword in vineyard_keywords if keyword in results_text)

            # Need at least 1 vineyard keyword in results (relaxed from 2)
            has_vineyard_evidence = keyword_matches >= 1

            return {"is_valid": has_vineyard_evidence, "evidence": results}

        except Exception as e:
            logger.error("validation.verification_error", company=company_name, error=str(e))
            # Assume valid if verification fails (don't penalize)
            return {"is_valid": True, "evidence": None}

    async def _enrich_company_data(
        self,
        company: dict[str, Any],
        segment: str,
    ) -> dict[str, Any]:
        """
        Use Perplexity to fill missing data fields with structured prompts.
        
        Strategy:
        1. First try dedicated perplexity_enrich_company tool (optimized for this task)
        2. Fall back to perplexity_ask with structured prompt if dedicated tool fails
        
        Best practices applied:
        - Highly structured prompts with explicit format requirements
        - Multi-strategy response parsing with fallbacks
        - Comprehensive validation of extracted data
        """
        enriched = company.copy()
        company_name = company.get("company", "")

        # Only enrich if critical fields are missing
        needs_website = not company.get("website") or company.get("website") == "N/A"
        needs_country = not company.get("country") or company.get("country") == "N/A"

        if not (needs_website or needs_country) or not company_name:
            return enriched

        self._enrichment_stats["attempted"] += 1
        
        # Determine which fields to request
        fields_to_request = []
        if needs_website:
            fields_to_request.append("website")
        if needs_country:
            fields_to_request.append("country")

        # Strategy 1: Try dedicated enrichment tool (preferred)
        if self.use_dedicated_enrichment:
            try:
                response = await self.tool_manager.invoke(
                    "perplexity_enrich_company",
                    company_name=company_name,
                    segment=segment if segment != "Unknown Segment" else None,
                    fields=fields_to_request,
                )
                
                if isinstance(response, dict) and response.get("success"):
                    fields = response.get("fields", {})
                    
                    if needs_website and fields.get("website"):
                        validated_url = self._validate_and_clean_url(fields["website"])
                        if validated_url and not self._is_excluded_domain(validated_url):
                            enriched["website"] = validated_url
                            logger.info(
                                "validation.website_extracted",
                                company=company_name,
                                website=validated_url,
                                method="dedicated_tool",
                            )
                    
                    if needs_country and fields.get("country"):
                        validated_country = self._validate_country(fields["country"])
                        if validated_country:
                            enriched["country"] = validated_country
                            logger.info(
                                "validation.country_extracted",
                                company=company_name,
                                country=validated_country,
                                method="dedicated_tool",
                            )
                    
                    # Check if we got what we needed
                    still_needs_website = needs_website and (not enriched.get("website") or enriched.get("website") == "N/A")
                    still_needs_country = needs_country and (not enriched.get("country") or enriched.get("country") == "N/A")
                    
                    if not still_needs_website and not still_needs_country:
                        self._enrichment_stats["successful"] += 1
                        enriched.setdefault("website", "N/A")
                        enriched.setdefault("country", "N/A")
                        enriched.setdefault("region_state", "N/A")
                        enriched.setdefault("segment", segment)
                        return enriched
                    
                    # Continue to fallback for remaining fields
                    needs_website = still_needs_website
                    needs_country = still_needs_country
                    
            except Exception as e:
                logger.warning(
                    "validation.dedicated_enrichment_failed",
                    company=company_name,
                    error=str(e),
                    fallback="perplexity_ask",
                )

        # Strategy 2: Fallback to perplexity_ask with structured prompt
        question = self._build_enrichment_prompt(company_name, segment, needs_website, needs_country)

        try:
            response = await self.tool_manager.invoke(
                "perplexity_ask",
                question=question,
                return_related_questions=False,
            )

            # Handle both dict response and string response
            if isinstance(response, dict):
                response_text = response.get("answer", "") or str(response)
            else:
                response_text = str(response)
            
            logger.debug(
                "validation.perplexity_response",
                company=company_name,
                response_length=len(response_text),
                response_preview=response_text[:200] if response_text else "empty",
            )

            # Multi-strategy parsing
            if needs_website:
                extracted_url = self._extract_website_robust(response_text, company_name)
                if extracted_url:
                    enriched["website"] = extracted_url
                    logger.info(
                        "validation.website_extracted",
                        company=company_name,
                        website=extracted_url,
                        method="fallback",
                    )

            if needs_country:
                extracted_country = self._extract_country_robust(response_text)
                if extracted_country:
                    enriched["country"] = extracted_country
                    logger.info(
                        "validation.country_extracted",
                        company=company_name,
                        country=extracted_country,
                        method="fallback",
                    )

            # Track success
            if (enriched.get("website") and enriched["website"] != "N/A") or \
               (enriched.get("country") and enriched["country"] != "N/A"):
                self._enrichment_stats["successful"] += 1
            else:
                self._enrichment_stats["failed"] += 1

            # Set defaults if still missing
            enriched.setdefault("website", "N/A")
            enriched.setdefault("country", "N/A")
            enriched.setdefault("region_state", "N/A")
            enriched.setdefault("segment", segment)

        except Exception as e:
            self._enrichment_stats["failed"] += 1
            logger.error(
                "validation.enrichment_error",
                company=company_name,
                error=str(e),
                error_type=type(e).__name__,
            )
            # Set defaults on error
            enriched.setdefault("website", "N/A")
            enriched.setdefault("country", "N/A")
            enriched.setdefault("region_state", "N/A")
            enriched.setdefault("segment", segment)

        return enriched
    
    def get_enrichment_stats(self) -> dict[str, int]:
        """Get statistics about enrichment operations."""
        return self._enrichment_stats.copy()

    def _build_enrichment_prompt(
        self,
        company_name: str,
        segment: str,
        needs_website: bool,
        needs_country: bool,
    ) -> str:
        """
        Build a highly structured prompt for Perplexity.
        
        Best practices applied:
        - Clear, explicit instructions
        - Specific format requirements
        - Context about the domain
        - Request for concise, factual response
        """
        parts = [f'Find the following information for "{company_name}"']
        
        if segment and segment != "Unknown Segment":
            parts.append(f"(an agricultural technology company in the {segment} sector)")
        
        parts.append(":\n")
        
        request_items = []
        if needs_website:
            request_items.append("1. WEBSITE: The official company website URL (format: https://example.com)")
        if needs_country:
            request_items.append(f"{'2' if needs_website else '1'}. COUNTRY: The country where the company is headquartered (just the country name)")
        
        parts.append("\n".join(request_items))
        
        parts.append("\n\nRespond with ONLY the requested facts in this exact format:")
        if needs_website:
            parts.append("\nWEBSITE: [url]")
        if needs_country:
            parts.append("\nCOUNTRY: [country name]")
        
        parts.append("\n\nIf information is not found, respond with 'NOT FOUND' for that field.")
        
        return "".join(parts)

    def _extract_website_robust(self, text: str, company_name: str) -> str | None:
        """
        Extract website URL using multiple strategies with validation.
        
        Strategies (in order of preference):
        1. Explicit "WEBSITE:" pattern from structured response
        2. Company-specific domain matching
        3. Generic URL extraction with validation
        """
        if not text:
            return None
        
        # Strategy 1: Look for explicit WEBSITE: pattern
        website_patterns = [
            r"WEBSITE:\s*(https?://[^\s\]\)\"',]+)",
            r"website[:\s]+is\s+(https?://[^\s\]\)\"',]+)",
            r"official\s+website[:\s]+(https?://[^\s\]\)\"',]+)",
            r"website[:\s]+(https?://[^\s\]\)\"',]+)",
        ]
        
        for pattern in website_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                url = self._validate_and_clean_url(match.group(1))
                if url:
                    return url
        
        # Strategy 2: Look for company-name-derived domains
        company_slug = self._company_name_to_slug(company_name)
        if company_slug:
            slug_pattern = rf"https?://(?:www\.)?{re.escape(company_slug)}[a-z0-9-]*\.[a-z]{{2,}}"
            match = re.search(slug_pattern, text, re.IGNORECASE)
            if match:
                url = self._validate_and_clean_url(match.group(0))
                if url:
                    return url
        
        # Strategy 3: Generic URL extraction with validation
        # More comprehensive URL regex
        url_pattern = r"https?://(?:www\.)?([a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}(?:/[^\s\]\)\"',]*)?"
        
        all_urls = re.findall(url_pattern, text)
        
        # Filter and validate URLs - prefer .com, .io, .ai, .tech, .ag domains
        for url_match in re.finditer(url_pattern, text):
            url = url_match.group(0)
            validated = self._validate_and_clean_url(url)
            if validated and not self._is_excluded_domain(validated):
                return validated
        
        return None

    def _validate_and_clean_url(self, url: str) -> str | None:
        """Validate and clean a URL, returning None if invalid."""
        if not url:
            return None
        
        # Clean up common issues
        url = url.rstrip(".,;:!?)]}")
        
        # Skip "NOT FOUND" or similar
        if "not found" in url.lower() or "unknown" in url.lower():
            return None
        
        try:
            parsed = urlparse(url)
            
            # Must have scheme and netloc
            if not parsed.scheme or not parsed.netloc:
                return None
            
            # Must be http or https
            if parsed.scheme not in ("http", "https"):
                return None
            
            # Domain must have at least one dot
            if "." not in parsed.netloc:
                return None
            
            # Clean domain
            domain = parsed.netloc.lower().replace("www.", "")
            
            # Return cleaned URL (just the domain, no path)
            return f"https://{domain}"
            
        except Exception:
            return None

    def _company_name_to_slug(self, company_name: str) -> str | None:
        """Convert company name to likely domain slug."""
        if not company_name:
            return None
        
        # Remove common suffixes
        name = company_name.lower()
        for suffix in [" inc", " llc", " ltd", " gmbh", " ag", " corp", " co"]:
            name = name.replace(suffix, "")
        
        # Remove special characters, keep alphanumeric
        slug = re.sub(r"[^a-z0-9]", "", name)
        
        return slug if len(slug) >= 3 else None

    def _is_excluded_domain(self, url: str) -> bool:
        """Check if URL is from an excluded domain (not a company website)."""
        excluded_domains = {
            # Social media
            "github.com", "linkedin.com", "twitter.com", "facebook.com",
            "youtube.com", "instagram.com", "tiktok.com", "x.com",
            # Content platforms
            "medium.com", "substack.com", "wordpress.com", "blogspot.com",
            # Business databases
            "crunchbase.com", "pitchbook.com", "zoominfo.com", "apollo.io",
            # Reference sites
            "wikipedia.org", "wikidata.org",
            # Academic
            "pmc.ncbi.nlm.nih.gov", "pubmed.ncbi.nlm.nih.gov", "doi.org",
            "springer.com", "wiley.com", "mdpi.com", "frontiersin.org",
            "sciencedirect.com", "researchgate.net", "academia.edu",
            # Wine industry news (not company sites)
            "winebusiness.com", "wines-vines.com", "wineenthusiast.com",
            "decanter.com", "winefolly.com", "wine-searcher.com",
            # Search engines
            "google.com", "bing.com", "duckduckgo.com",
            # Forums/Q&A
            "reddit.com", "quora.com", "stackexchange.com",
            # News
            "techcrunch.com", "forbes.com", "bloomberg.com", "reuters.com",
            # Perplexity's own domain
            "perplexity.ai",
        }
        
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower().replace("www.", "")
            return any(excluded in domain for excluded in excluded_domains)
        except Exception:
            return False

    def _extract_country_robust(self, text: str) -> str | None:
        """
        Extract country using multiple strategies with validation.
        
        Strategies (in order of preference):
        1. Explicit "COUNTRY:" pattern from structured response
        2. Common phrasing patterns (headquartered in, based in, etc.)
        3. Direct country name matching
        """
        if not text:
            return None
        
        # Strategy 1: Look for explicit COUNTRY: pattern
        country_patterns = [
            r"COUNTRY:\s*([A-Za-z][A-Za-z\s]{1,30}?)(?:\.|,|\n|$)",
            r"country[:\s]+is\s+([A-Za-z][A-Za-z\s]{1,30}?)(?:\.|,|\n|$)",
            r"headquartered\s+in\s+([A-Za-z][A-Za-z\s]{1,30}?)(?:\.|,|\n|$)",
        ]
        
        for pattern in country_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                country = self._validate_country(match.group(1).strip())
                if country:
                    return country
        
        # Strategy 2: Common phrasing patterns
        location_patterns = [
            r"based\s+in\s+([A-Z][a-zA-Z\s]{1,30}?)(?:\.|,|\n|;|$)",
            r"located\s+in\s+([A-Z][a-zA-Z\s]{1,30}?)(?:\.|,|\n|;|$)",
            r"from\s+([A-Z][a-zA-Z\s]{1,30}?)(?:\.|,|\n|;|$)",
            r"operates\s+(?:out\s+of|from)\s+([A-Z][a-zA-Z\s]{1,30}?)(?:\.|,|\n|;|$)",
            r"(?:is\s+)?(?:a|an)\s+[A-Za-z-]+\s+company\s+(?:based\s+)?in\s+([A-Z][a-zA-Z\s]{1,30}?)(?:\.|,|\n|;|$)",
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, text)
            if match:
                country = self._validate_country(match.group(1).strip())
                if country:
                    return country
        
        # Strategy 3: Direct country name matching in text
        text_upper = text.upper()
        for country in sorted(VALID_COUNTRIES, key=len, reverse=True):
            if country.upper() in text_upper:
                return self._normalize_country(country)
        
        return None

    def _validate_country(self, candidate: str) -> str | None:
        """Validate and normalize a country candidate."""
        if not candidate:
            return None
        
        # Clean up
        candidate = candidate.strip().rstrip(".,;:")
        
        # Skip obvious non-countries
        skip_words = {"not found", "unknown", "n/a", "none", "the", "a", "an"}
        if candidate.lower() in skip_words:
            return None
        
        # Check against known countries (case-insensitive)
        return self._normalize_country(candidate)

    def _normalize_country(self, country: str) -> str | None:
        """Normalize country name to canonical form."""
        if not country:
            return None
        
        country_lower = country.lower().strip()
        
        # Reject known city names that are incorrectly passed as countries
        # These are common cities that appear in wine/agtech company locations
        invalid_locations = {
            # Cities incorrectly identified as countries
            "stepney", "pertuis", "melbourne", "sydney", "london", "paris",
            "berlin", "madrid", "barcelona", "milan", "rome", "munich",
            "san francisco", "new york", "los angeles", "seattle", "boston",
            "napa", "sonoma", "bordeaux", "burgundy", "champagne", "rioja",
            "mendoza", "stellenbosch", "cape town", "auckland", "wellington",
            # Regions that shouldn't be country values
            "catalonia", "california", "oregon", "washington", "texas",
            "victoria", "south australia", "western australia", "queensland",
            "provence", "languedoc", "alsace", "loire", "tuscany", "piedmont",
            "veneto", "sicily", "sardinia", "galicia", "andalusia",
            "marlborough", "hawke's bay", "central otago",
            "barossa", "mclaren vale", "hunter valley", "yarra valley",
        }
        
        if country_lower in invalid_locations:
            return None
        
        # Check aliases first
        if country_lower in COUNTRY_ALIASES:
            return COUNTRY_ALIASES[country_lower]
        
        # Check valid countries (case-insensitive match)
        for valid_country in VALID_COUNTRIES:
            if valid_country.lower() == country_lower:
                return valid_country
        
        # Partial match for multi-word countries
        for valid_country in VALID_COUNTRIES:
            if country_lower in valid_country.lower() or valid_country.lower() in country_lower:
                return valid_country
        
        # DON'T blindly accept unknown strings - only accept if it's in valid countries
        # This prevents cities/regions from being accepted as countries
        return None

    def _is_investable_entity(self, company: dict[str, Any]) -> tuple[bool, str | None]:
        """
        Check if the entity is an investable company vs NGO/study/initiative.
        
        Returns:
            tuple: (is_investable, rejection_reason)
        """
        company_name = company.get("company", "").lower()
        summary = company.get("summary", "").lower()
        
        # Check company name against non-investable patterns
        for pattern in NON_INVESTABLE_PATTERNS:
            if re.search(pattern, company_name, re.IGNORECASE):
                return False, f"Name matches non-investable pattern: {pattern}"
        
        # Check summary for non-investable indicators
        for pattern in NON_INVESTABLE_SUMMARY_PATTERNS:
            if re.search(pattern, summary, re.IGNORECASE):
                return False, f"Summary indicates non-investable entity: {pattern}"
        
        # Additional heuristics for common non-investable types
        # Check for certification body indicators
        if "certification" in summary and any(
            indicator in summary 
            for indicator in ["certifies", "certifying", "certification body", "accredits"]
        ):
            return False, "Entity appears to be a certification body"
        
        # Check for government program indicators
        if any(
            indicator in summary 
            for indicator in [
                "funded by", "life program", "eu program", "government program",
                "publicly funded", "state-funded"
            ]
        ):
            return False, "Entity appears to be a government/EU funded program"
        
        # Check for research/academic project indicators
        if "university" in summary or "academic" in summary:
            # Only reject if it's clearly a research project, not a spin-off
            if any(
                indicator in summary 
                for indicator in ["research project", "study conducted", "pilot project", "research initiative"]
            ):
                return False, "Entity appears to be an academic research project"
        
        return True, None

    def _validate_kpi_claims_lightweight(self, company: dict[str, Any]) -> bool:
        """Lightweight KPI validation without MCP calls - just pattern matching."""
        sources = company.get("sources", [])
        kpi_claims = company.get("kpi_alignment", [])

        if not sources or not kpi_claims:
            return False

        # Check for "Low Confidence" flag
        summary = company.get("summary", "").lower()
        kpis_text = " ".join(kpi_claims).lower()
        if "low confidence" in (summary + kpis_text):
            return False

        # Check for indirect impact markers in core KPIs
        indirect_markers = [
            "(indirectly)",
            "(implied)",
            "indirect",
            "implied",
            "potentially",
            "likely",
            "could lead to",
            "may support",
            "aims to",
            "contributes to",
        ]
        for kpi in kpi_claims:
            kpi_lower = kpi.lower()
            if any(marker in kpi_lower for marker in indirect_markers):
                # Check if it's a core KPI (first 2 KPIs are usually core)
                if kpi_claims.index(kpi) < 2:
                    return False

        # Check if sources mention vineyard keywords
        sources_text = " ".join(sources).lower()
        vineyard_keywords = ["vineyard", "wine", "viticulture", "grape", "winery"]
        return any(keyword in sources_text for keyword in vineyard_keywords)

    def _calculate_confidence(self, company: dict[str, Any]) -> float:
        """Calculate confidence score based on evidence quality."""
        score = 0.5  # Base score

        # +0.1 for each quality source (max 3)
        sources = company.get("sources", [])
        quality_domains = [".edu", ".gov", "doi.org", "research", "journal", "university"]
        quality_source_count = sum(
            1 for source in sources if any(domain in source.lower() for domain in quality_domains)
        )
        score += min(quality_source_count * 0.1, 0.3)

        # +0.1 for quantified metrics in KPIs
        kpis = " ".join(company.get("kpi_alignment", []))
        metric_patterns = ["%", "tco2", "hectare", "litre", "kg", "ton"]
        has_metrics = any(pattern in kpis.lower() for pattern in metric_patterns)
        if has_metrics:
            score += 0.1

        # +0.1 for vineyard verification
        if company.get("vineyard_verified"):
            score += 0.1

        # -0.1 if only Tier 3 sources
        tier_3_indicators = ["blog", "press release", company.get("company", "").lower()]
        all_tier_3 = all(
            any(indicator in source.lower() for indicator in tier_3_indicators)
            for source in sources
        )
        if all_tier_3:
            score -= 0.1

        return max(0.0, min(score, 1.0))


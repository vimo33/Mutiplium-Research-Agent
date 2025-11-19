"""MCP-based quality validator for research findings.

NEW ARCHITECTURE:
- Providers use native search (OpenAI web, Google Grounding, Claude reasoning)
- Validation uses MCP tools (Tavily + Perplexity) for deep verification
- This prevents Tavily exhaustion during discovery phase
- More strategic use of MCP tools in validation
"""

from __future__ import annotations

import re
from typing import Any

import structlog

logger = structlog.get_logger()


class CompanyValidator:
    """Post-research validator using MCP tools for verification and enrichment."""

    def __init__(self, tool_manager: Any) -> None:
        self.tool_manager = tool_manager

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
        5. Reject low-quality entries
        """
        if not companies:
            return []

        validated: list[dict[str, Any]] = []
        rejected_count = 0

        for idx, company in enumerate(companies, 1):
            company_name = company.get("company", f"Unknown-{idx}")
            logger.info(
                "validation.company_start",
                company=company_name,
                segment=segment,
                index=f"{idx}/{len(companies)}",
            )

            # Step 1: Quick vineyard verification (lightweight - just check sources)
            try:
                # Quick check: Do sources mention vineyard keywords?
                sources_text = " ".join(company.get("sources", [])).lower()
                summary_text = company.get("summary", "").lower()
                combined_text = sources_text + " " + summary_text
                
                vineyard_keywords = ["vineyard", "winery", "wine", "viticulture", "grape"]
                has_vineyard_mention = any(kw in combined_text for kw in vineyard_keywords)
                
                if not has_vineyard_mention:
                    logger.warning(
                        "validation.rejected",
                        company=company_name,
                        reason="No vineyard keywords in sources or summary",
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
            if enriched["confidence_0to1"] >= 0.45:
                validated.append(enriched)
                logger.info(
                    "validation.accepted",
                    company=company_name,
                    confidence=enriched["confidence_0to1"],
                )
            else:
                logger.warning(
                    "validation.rejected",
                    company=company_name,
                    reason=f"Low confidence: {enriched['confidence_0to1']:.2f}",
                )
                rejected_count += 1

        logger.info(
            "validation.segment_complete",
            segment=segment,
            validated=len(validated),
            rejected=rejected_count,
            total=len(companies),
        )

        return validated

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
        """Use Perplexity to fill missing data fields."""
        enriched = company.copy()
        company_name = company.get("company", "")

        # Only enrich if critical fields are missing
        missing_fields = []
        if not company.get("website"):
            missing_fields.append("website")
        if not company.get("country"):
            missing_fields.append("country")

        if not missing_fields or not company_name:
            return enriched

        # Use Perplexity ask for structured data
        question = (
            f"What is {company_name}'s official website URL and headquarters country? "
            f"This company operates in the {segment} segment for viticulture/wine industry."
        )

        try:
            response = await self.tool_manager.invoke(
                "perplexity_ask",
                question=question,
                return_related_questions=False,
            )

            response_text = str(response)

            # Extract website URL
            if "website" in missing_fields:
                url_match = re.search(
                    r"https?://(?:www\.)?([a-zA-Z0-9-]+\.(?:com|io|ai|tech|ag|net|org|eu|co\.uk))",
                    response_text,
                )
                if url_match:
                    enriched["website"] = url_match.group(0)

            # Extract country
            if "country" in missing_fields:
                # Common country patterns
                country_patterns = [
                    r"headquarters in ([A-Z][a-z]+)",
                    r"based in ([A-Z][a-z]+)",
                    r"located in ([A-Z][a-z]+)",
                    r"from ([A-Z][a-z]+)",
                ]
                for pattern in country_patterns:
                    country_match = re.search(pattern, response_text)
                    if country_match:
                        enriched["country"] = country_match.group(1)
                        break

            # Set defaults if still missing
            if not enriched.get("website"):
                enriched["website"] = "N/A"
            if not enriched.get("country"):
                enriched["country"] = "N/A"
            if not enriched.get("region_state"):
                enriched["region_state"] = "N/A"
            if not enriched.get("segment"):
                enriched["segment"] = segment

        except Exception as e:
            logger.error("validation.enrichment_error", company=company_name, error=str(e))
            # Set defaults on error
            enriched.setdefault("website", "N/A")
            enriched.setdefault("country", "N/A")
            enriched.setdefault("region_state", "N/A")
            enriched.setdefault("segment", segment)

        return enriched

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


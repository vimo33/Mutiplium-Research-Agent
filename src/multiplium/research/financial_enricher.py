"""
Financial Enrichment System for Deep Research.

Multi-path enrichment based on entity classification:
1. Listed companies → Finance APIs (FMP, Alpha Vantage) + SEC EDGAR
2. Private with filed accounts → Company registries (Companies House, OpenCorporates)
3. Private startups → Web/PR mining with GPT-4o + Agents SDK tool calling

Outputs a 3-layer schema:
- financials_exact: Auditable data from official sources
- financials_estimated: Revenue ranges using sector heuristics
- financial_signals_raw: Raw evidence snippets for analyst review
- awards: Industry recognition and grants with source links
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import structlog
from typing import Any, Callable

logger = structlog.get_logger()

# Try to import OpenAI Agents SDK
try:
    from agents import Agent, Runner, set_default_openai_key
    from agents.tool import FunctionTool
    AGENTS_SDK_AVAILABLE = True
except ImportError:
    AGENTS_SDK_AVAILABLE = False
    logger.warning("agents SDK not available, falling back to basic GPT-4o")


# Wine/Agtech sector heuristics for revenue estimation
SECTOR_HEURISTICS = {
    "agtech_hardware": {
        "description": "Agricultural hardware/sensors/equipment",
        "revenue_per_employee_min": 250000,
        "revenue_per_employee_max": 400000,
        "examples": ["Sentek", "Smart Apply", "precision sprayers"],
    },
    "agtech_saas": {
        "description": "Agricultural SaaS/monitoring/analytics",
        "revenue_per_employee_min": 150000,
        "revenue_per_employee_max": 250000,
        "examples": ["vineyard management software", "crop analytics"],
    },
    "iot_hybrid": {
        "description": "IoT + Hardware hybrid solutions",
        "revenue_per_employee_min": 200000,
        "revenue_per_employee_max": 350000,
        "examples": ["sensor + software platforms", "eProvenance"],
    },
    "biotech": {
        "description": "Agricultural biotech/biologicals",
        "revenue_per_employee_min": 200000,
        "revenue_per_employee_max": 500000,
        "examples": ["pheromone solutions", "Suterra", "biological controls"],
    },
    "services": {
        "description": "Agricultural consulting/services",
        "revenue_per_employee_min": 80000,
        "revenue_per_employee_max": 150000,
        "examples": ["viticulture consulting", "sustainability services"],
    },
    "logistics": {
        "description": "Wine logistics/distribution tech",
        "revenue_per_employee_min": 150000,
        "revenue_per_employee_max": 300000,
        "examples": ["cold chain monitoring", "shipping optimization"],
    },
    "circular_economy": {
        "description": "Recycling/reuse/circular economy",
        "revenue_per_employee_min": 100000,
        "revenue_per_employee_max": 200000,
        "examples": ["bottle reuse", "Conscious Container"],
    },
}

# Employee band mapping
EMPLOYEE_BANDS = {
    "1-10": (1, 10),
    "1-10 employees": (1, 10),
    "11-50": (11, 50),
    "11-50 employees": (11, 50),
    "51-200": (51, 200),
    "51-200 employees": (51, 200),
    "201-500": (201, 500),
    "201-500 employees": (201, 500),
    "501-1000": (501, 1000),
    "501-1000 employees": (501, 1000),
    "1000+": (1000, 2000),
    "1001-5000": (1001, 5000),
}


class FinancialEnricher:
    """
    Orchestrates financial data enrichment using multiple sources.
    
    Flow:
    1. Classify entity (listed/private/startup)
    2. Route to appropriate data sources
    3. Mine financial signals using OpenAI Responses API with web_search tool
    4. Extract awards and recognition
    5. Estimate revenue if no exact data
    6. Return 3-layer output schema with source links
    """
    
    def __init__(self):
        """Initialize enricher with all required clients."""
        from multiplium.tools.finance_apis import FinanceAPIClient
        from multiplium.tools.company_registries import UnifiedRegistryClient
        
        self.finance_api = FinanceAPIClient()
        self.registry = UnifiedRegistryClient()
        
        # Initialize OpenAI API key for Responses API
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        
        # Initialize OpenAI client
        from openai import AsyncOpenAI
        self.openai = AsyncOpenAI(api_key=self.openai_api_key)
    
    async def enrich(self, company: dict[str, Any]) -> dict[str, Any]:
        """
        Main enrichment pipeline for a single company.
        
        Args:
            company: Company dict from discovery phase with:
                - company: name
                - website: URL
                - country: headquarters country
                - summary: brief description
                - team: {size: "X employees"} (if available)
        
        Returns:
            Dict with 3-layer financial enrichment:
            {
                "entity_classification": {...},
                "financials_exact": {...} or null,
                "financials_estimated": {...} or null,
                "funding_rounds": [...],
                "awards": [...],
                "financial_signals_raw": [...]
            }
        """
        company_name = company.get("company", "Unknown")
        
        logger.info(
            "financial_enricher.start",
            company=company_name,
        )
        
        # Step 1: Classify entity
        classification = await self._classify_entity(company)
        
        # Step 2: Route to appropriate enrichment path
        financials_exact = None
        
        if classification.get("is_listed"):
            financials_exact = await self._enrich_listed(company, classification)
        elif classification.get("has_filed_accounts"):
            financials_exact = await self._enrich_from_registry(company, classification)
        
        # Step 3: Mine web/PR for financial signals using Agents SDK with tools
        signals = await self._mine_financial_signals(company, classification)
        
        # Step 4: Extract funding rounds from signals
        funding_rounds = self._extract_funding_rounds(signals)
        
        # Step 5: Extract awards from signals
        awards = self._extract_awards(signals)
        
        # Step 6: Estimate revenue if no exact data
        financials_estimated = None
        if not financials_exact or not financials_exact.get("years"):
            financials_estimated = await self._estimate_revenue(company, classification, signals)
        
        result = {
            "entity_classification": classification,
            "financials_exact": financials_exact,
            "financials_estimated": financials_estimated,
            "funding_rounds": funding_rounds,
            "awards": awards,
            "financial_signals_raw": signals,
        }
        
        logger.info(
            "financial_enricher.complete",
            company=company_name,
            has_exact=bool(financials_exact),
            has_estimated=bool(financials_estimated),
            signals_count=len(signals),
            funding_rounds_count=len(funding_rounds),
            awards_count=len(awards),
        )
        
        return result
    
    async def _classify_entity(self, company: dict[str, Any]) -> dict[str, Any]:
        """
        Classify company to determine enrichment path.
        
        Returns:
            {
                "is_listed": bool,
                "has_filed_accounts": bool,
                "country": str,
                "likely_size_bucket": str,
                "likely_sector": str,
                "ticker": str or null,
                "company_number": str or null
            }
        """
        company_name = company.get("company", "")
        country = company.get("country", "").upper()
        summary = company.get("summary", "")
        team_size = company.get("team", {}).get("size", "") if isinstance(company.get("team"), dict) else ""
        
        # Normalize country codes
        if country in ("N/A", "UNITED STATES", "USA"):
            country = "US"
        elif country in ("UNITED KINGDOM", "ENGLAND"):
            country = "GB"
        elif country in ("AUSTRALIA",):
            country = "AU"
        
        classification = {
            "is_listed": False,
            "has_filed_accounts": False,
            "country": country,
            "likely_size_bucket": self._parse_employee_band(team_size),
            "likely_sector": self._infer_sector(summary),
            "ticker": None,
            "company_number": None,
            "cik": None,
        }
        
        # Check if listed (search for ticker)
        if self.finance_api.fmp_api_key:
            ticker_results = await self.finance_api.search_ticker(company_name)
            if ticker_results.get("results"):
                # Check if any result matches closely
                for result in ticker_results["results"]:
                    if self._name_matches(company_name, result.get("name", "")):
                        classification["is_listed"] = True
                        classification["ticker"] = result.get("symbol")
                        break
        
        # Check registries for company number
        if not classification["is_listed"]:
            if country in ("GB", "UK"):
                ch_results = await self.registry.companies_house.search_company(company_name)
                if ch_results.get("results"):
                    for result in ch_results["results"]:
                        if self._name_matches(company_name, result.get("name", "")):
                            classification["has_filed_accounts"] = True
                            classification["company_number"] = result.get("company_number")
                            break
            
            elif country == "US":
                sec_results = await self.registry.sec_edgar.search_company(company_name)
                if sec_results.get("results"):
                    for result in sec_results["results"]:
                        if self._name_matches(company_name, result.get("name", "")):
                            classification["is_listed"] = True
                            classification["cik"] = result.get("cik")
                            classification["ticker"] = result.get("ticker")
                            break
            
            # Try OpenCorporates for other countries
            if not classification["has_filed_accounts"] and country:
                oc_results = await self.registry.opencorporates.search_company(
                    company_name, country=country.lower()
                )
                if oc_results.get("results"):
                    for result in oc_results["results"]:
                        if self._name_matches(company_name, result.get("name", "")):
                            classification["has_filed_accounts"] = True
                            classification["company_number"] = result.get("company_number")
                            classification["jurisdiction_code"] = result.get("jurisdiction_code")
                            break
        
        logger.info(
            "financial_enricher.classification.complete",
            company=company_name,
            is_listed=classification["is_listed"],
            has_filed_accounts=classification["has_filed_accounts"],
            sector=classification["likely_sector"],
        )
        
        return classification
    
    async def _enrich_listed(
        self,
        company: dict[str, Any],
        classification: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Enrich listed company using finance APIs.
        
        Uses FMP for comprehensive financials, falls back to Alpha Vantage.
        """
        ticker = classification.get("ticker")
        cik = classification.get("cik")
        
        if not ticker and not cik:
            return None
        
        company_name = company.get("company", "")
        
        try:
            if ticker:
                # Use FMP for full financials
                financials = await self.finance_api.get_full_financials(ticker, years=3)
                
                if financials.get("years"):
                    logger.info(
                        "financial_enricher.listed.success",
                        company=company_name,
                        ticker=ticker,
                        years_count=len(financials["years"]),
                    )
                    return financials
                
                # Fallback to Alpha Vantage
                av_data = await self.finance_api.get_alpha_vantage_overview(ticker)
                if av_data.get("revenue_ttm"):
                    return {
                        "source_type": "public_api",
                        "source": "Alpha Vantage",
                        "currency": av_data.get("currency", "USD"),
                        "years": [{
                            "year": 2024,  # TTM
                            "revenue": av_data.get("revenue_ttm", 0),
                            "ebitda": av_data.get("ebitda", 0),
                            "gross_profit": av_data.get("gross_profit_ttm", 0),
                        }],
                        "profile": {
                            "employees": av_data.get("employees", 0),
                            "market_cap": av_data.get("market_cap", 0),
                        },
                        "confidence_0to1": 0.9,
                    }
            
            if cik:
                # Use SEC EDGAR for XBRL facts
                facts = await self.registry.sec_edgar.get_company_facts(cik)
                
                if facts.get("metrics"):
                    # Convert SEC facts to our format
                    years_data = self._convert_sec_facts(facts)
                    if years_data:
                        return {
                            "source_type": "official_registry",
                            "source": "SEC EDGAR",
                            "currency": "USD",
                            "years": years_data,
                            "confidence_0to1": 0.95,
                        }
        
        except Exception as e:
            logger.error(
                "financial_enricher.listed.failed",
                company=company_name,
                error=str(e),
            )
        
        return None
    
    async def _enrich_from_registry(
        self,
        company: dict[str, Any],
        classification: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Enrich from company registries for private companies with filed accounts.
        """
        company_name = company.get("company", "")
        country = classification.get("country", "")
        company_number = classification.get("company_number")
        
        if not company_number:
            return None
        
        try:
            if country in ("GB", "UK"):
                accounts = await self.registry.companies_house.get_accounts_summary(company_number)
                
                if not accounts.get("error"):
                    # Companies House doesn't provide actual numbers via API
                    # But we can get filing metadata
                    return {
                        "source_type": "official_registry",
                        "source": "Companies House",
                        "company_number": company_number,
                        "last_accounts": accounts.get("last_accounts", {}),
                        "next_accounts_due": accounts.get("next_accounts_due"),
                        "recent_filings": accounts.get("recent_filings", []),
                        "note": "Full accounts available via Companies House PDF download",
                        "confidence_0to1": 0.95,
                    }
            
            # For other countries, use OpenCorporates
            jurisdiction = classification.get("jurisdiction_code")
            if jurisdiction:
                oc_company = await self.registry.opencorporates.get_company(
                    jurisdiction, company_number
                )
                
                if not oc_company.get("error"):
                    return {
                        "source_type": "official_registry",
                        "source": "OpenCorporates",
                        "company_number": company_number,
                        "jurisdiction": jurisdiction,
                        "incorporation_date": oc_company.get("incorporation_date"),
                        "current_status": oc_company.get("current_status"),
                        "officers": oc_company.get("officers", []),
                        "opencorporates_url": oc_company.get("opencorporates_url"),
                        "confidence_0to1": 0.8,
                    }
        
        except Exception as e:
            logger.error(
                "financial_enricher.registry.failed",
                company=company_name,
                error=str(e),
            )
        
        return None
    
    async def _mine_financial_signals(
        self,
        company: dict[str, Any],
        classification: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Mine web for financial signals using OpenAI Responses API with web_search tool.
        
        Uses GPT's built-in web search to find:
        - Funding announcements with source URLs
        - Awards and grants
        - Revenue hints
        - Contract values
        - Scale signals
        """
        company_name = company.get("company", "")
        website = company.get("website", "")
        summary = company.get("summary", "")
        country = classification.get("country", "Unknown")
        
        prompt = f"""Research the company "{company_name}" and find ALL financial and recognition information.

**Company Info:**
- Website: {website}
- Country: {country}
- Description: {summary[:500]}

**Search for and report:**
1. **Funding rounds** - Search for "{company_name} funding raised investment" and "{company_name} series A B C"
2. **Awards & Grants** - Search for "{company_name} award winner grant"  
3. **Revenue/Financial signals** - Any public revenue figures, customer counts, growth metrics
4. **Key partnerships** - Major contracts or strategic partners

For EACH piece of information found, you MUST include:
- The exact fact/figure
- The source URL where you found it
- The date/year if mentioned

Return a JSON object with this structure:
{{
  "funding_rounds": [
    {{
      "round_type": "Series A/Seed/Grant/etc",
      "amount": 10000000,
      "currency": "USD",
      "date": "2023",
      "investors": ["Investor Name"],
      "source_url": "https://...",
      "evidence": "Quote or description"
    }}
  ],
  "awards": [
    {{
      "name": "Award Name",
      "year": "2023",
      "organization": "Granting org",
      "amount": null,
      "source_url": "https://...",
      "evidence": "Description"
    }}
  ],
  "financial_signals": [
    {{
      "type": "revenue/customers/growth_rate/valuation",
      "value": 5000000,
      "description": "$5M ARR",
      "date": "2023",
      "source_url": "https://...",
      "evidence": "Quote"
    }}
  ]
}}

IMPORTANT: Only include information you can verify with a source URL. Do not invent data."""

        try:
            # Use OpenAI Responses API with web_search tool
            # Format: just {"type": "web_search"} - no nested config
            response = await self.openai.responses.create(
                model="gpt-4o",
                tools=[{"type": "web_search"}],
                input=prompt,
            )
            
            # Extract the response text and citations
            signals = []
            source_urls = []
            
            # Process the response
            for output in response.output:
                if output.type == "message":
                    # Use model_dump() to get dict representation
                    output_dict = output.model_dump()
                    
                    for content in output_dict.get("content", []):
                        # Content type is "output_text" not "text"
                        if content.get("type") == "output_text":
                            text = content.get("text", "")
                            
                            # Collect source URLs from annotations
                            for ann in content.get("annotations", []):
                                url = ann.get("url")
                                if url:
                                    source_urls.append(url)
                            
                            # Try to parse JSON from the response
                            try:
                                json_start = text.find('{')
                                json_end = text.rfind('}') + 1
                                if json_start >= 0 and json_end > json_start:
                                    json_str = text[json_start:json_end]
                                    data = json.loads(json_str)
                                    
                                    # Extract funding rounds
                                    for fr in data.get("funding_rounds", []):
                                        signals.append({
                                            "type": "funding",
                                            "text": fr.get("evidence", ""),
                                            "value": fr.get("amount"),
                                            "value_unit": fr.get("currency", "USD"),
                                            "date": fr.get("date"),
                                            "source_url": fr.get("source_url"),
                                            "source_type": "web_search",
                                            "confidence_0to1": 0.85 if fr.get("source_url") else 0.6,
                                            "investors": fr.get("investors", []),
                                            "round_type": fr.get("round_type"),
                                        })
                                    
                                    # Extract awards
                                    for award in data.get("awards", []):
                                        signals.append({
                                            "type": "award",
                                            "text": award.get("evidence", award.get("name", "")),
                                            "value": award.get("amount"),
                                            "value_unit": "USD" if award.get("amount") else None,
                                            "date": award.get("year"),
                                            "source_url": award.get("source_url"),
                                            "source_type": "web_search",
                                            "confidence_0to1": 0.85 if award.get("source_url") else 0.6,
                                            "award_name": award.get("name"),
                                            "organization": award.get("organization"),
                                        })
                                    
                                    # Extract financial signals
                                    for sig in data.get("financial_signals", []):
                                        signals.append({
                                            "type": sig.get("type", "revenue"),
                                            "text": sig.get("evidence", sig.get("description", "")),
                                            "value": sig.get("value"),
                                            "value_unit": "USD",
                                            "date": sig.get("date"),
                                            "source_url": sig.get("source_url"),
                                            "source_type": "web_search",
                                            "confidence_0to1": 0.75 if sig.get("source_url") else 0.5,
                                        })
                            except json.JSONDecodeError:
                                # If JSON parsing fails, try to extract info from plain text
                                logger.info(
                                    "financial_enricher.parsing_text_response",
                                    company=company_name,
                                    text_length=len(text),
                                )
                                # Add raw text as a signal with source URLs
                                if text and source_urls:
                                    signals.append({
                                        "type": "raw_research",
                                        "text": text[:2000],
                                        "source_urls": source_urls[:5],
                                        "source_type": "web_search",
                                        "confidence_0to1": 0.7,
                                    })
            
            # Filter out any None signals before logging
            signals = [s for s in signals if s is not None]
            
            logger.info(
                "financial_enricher.web_search.complete",
                company=company_name,
                signals_count=len(signals),
                has_funding=any(s.get("type") == "funding" for s in signals),
                has_awards=any(s.get("type") == "award" for s in signals),
            )
            
            return signals
        
        except Exception as e:
            logger.warning(
                "financial_enricher.web_search.failed",
                company=company_name,
                error=str(e),
            )
            # Fallback to basic extraction without web search
            return await self._mine_signals_fallback(company, classification)
    
    async def _mine_signals_fallback(
        self,
        company: dict[str, Any],
        classification: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Fallback signal extraction using GPT-4o without web search."""
        company_name = company.get("company", "")
        website = company.get("website", "")
        summary = company.get("summary", "")
        
        prompt = f"""Extract financial signals from your knowledge about "{company_name}".

Company: {company_name}
Website: {website}
Description: {summary[:500]}

Return JSON with funding_rounds, awards, and financial_signals arrays.
Only include information you're confident about. Include source URLs if known."""

        try:
            response = await self.openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Extract financial signals. Return valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            
            result_text = response.choices[0].message.content
            data = json.loads(result_text)
            
            signals = []
            for fr in data.get("funding_rounds", []):
                signals.append({
                    "type": "funding",
                    "text": fr.get("evidence", ""),
                    "value": fr.get("amount"),
                    "value_unit": fr.get("currency", "USD"),
                    "date": fr.get("date"),
                    "source_url": fr.get("source_url"),
                    "source_type": "prior_knowledge",
                    "confidence_0to1": 0.5,
                })
            
            for award in data.get("awards", []):
                signals.append({
                    "type": "award",
                    "text": award.get("evidence", award.get("name", "")),
                    "value": award.get("amount"),
                    "date": award.get("year"),
                    "source_url": award.get("source_url"),
                    "source_type": "prior_knowledge",
                    "confidence_0to1": 0.5,
                    "award_name": award.get("name"),
                })
            
            return signals
        except Exception as e:
            logger.error("financial_enricher.fallback.failed", error=str(e))
            return []
    
    async def _estimate_revenue(
        self,
        company: dict[str, Any],
        classification: dict[str, Any],
        signals: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """
        Estimate revenue using sector heuristics when no exact data available.
        
        Uses:
        - Employee count × revenue/employee benchmark
        - Sector-specific heuristics
        - Scale signals from mining
        """
        company_name = company.get("company", "")
        sector = classification.get("likely_sector", "")
        size_bucket = classification.get("likely_size_bucket", "")
        
        # Get sector heuristics
        heuristics = SECTOR_HEURISTICS.get(sector, SECTOR_HEURISTICS["agtech_saas"])
        
        # Parse employee count
        employee_range = self._parse_employee_band(size_bucket)
        if not employee_range or employee_range == "Unknown":
            # Try to extract from team data
            team = company.get("team", {})
            if isinstance(team, dict):
                team_size = team.get("size", "")
                employee_range = self._parse_employee_band(team_size)
        
        # Get employee numbers
        if employee_range and employee_range != "Unknown":
            band = EMPLOYEE_BANDS.get(employee_range, EMPLOYEE_BANDS.get(f"{employee_range} employees"))
            if band:
                emp_min, emp_max = band
            else:
                # Try to parse directly
                emp_match = re.search(r"(\d+)", str(employee_range))
                if emp_match:
                    emp_mid = int(emp_match.group(1))
                    emp_min = int(emp_mid * 0.8)
                    emp_max = int(emp_mid * 1.2)
                else:
                    return None
        else:
            return None
        
        # Calculate revenue range
        rev_per_emp_min = heuristics["revenue_per_employee_min"]
        rev_per_emp_max = heuristics["revenue_per_employee_max"]
        
        # Use midpoint of employee range
        emp_mid = (emp_min + emp_max) / 2
        
        revenue_min = int(emp_min * rev_per_emp_min)
        revenue_max = int(emp_max * rev_per_emp_max)
        revenue_mid = int(emp_mid * (rev_per_emp_min + rev_per_emp_max) / 2)
        
        # Adjust confidence based on available signals
        base_confidence = 0.3
        
        # Boost confidence if we have supporting signals
        growth_signals = [s for s in signals if s.get("type") == "growth_rate"]
        scale_signals = [s for s in signals if s.get("type") == "scale"]
        
        if growth_signals:
            base_confidence += 0.1
        if scale_signals:
            base_confidence += 0.1
        if len(signals) > 3:
            base_confidence += 0.1
        
        estimate = {
            "revenue_estimate": {
                "currency": "USD",
                "min": revenue_min,
                "max": revenue_max,
                "mid": revenue_mid,
                "method": "employees_x_sector_heuristics",
                "inputs": {
                    "employee_range": employee_range,
                    "employee_min": emp_min,
                    "employee_max": emp_max,
                    "sector": sector,
                    "sector_description": heuristics["description"],
                    "revenue_per_employee_min": rev_per_emp_min,
                    "revenue_per_employee_max": rev_per_emp_max,
                },
                "confidence_0to1": min(base_confidence, 0.6),
            }
        }
        
        logger.info(
            "financial_enricher.estimate.generated",
            company=company_name,
            revenue_min=revenue_min,
            revenue_max=revenue_max,
            confidence=estimate["revenue_estimate"]["confidence_0to1"],
        )
        
        return estimate
    
    def _extract_funding_rounds(self, signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Extract and structure funding rounds from signals."""
        funding_signals = [s for s in signals if s.get("type") == "funding"]
        
        rounds = []
        for signal in funding_signals:
            round_data = {
                "round_type": signal.get("round_type", "undisclosed"),
                "amount": signal.get("value"),
                "amount_min": signal.get("value_range_min"),
                "amount_max": signal.get("value_range_max"),
                "currency": signal.get("value_unit", "USD"),
                "date": signal.get("date"),
                "evidence": signal.get("text", ""),
                "source_url": signal.get("source_url"),
                "investors": signal.get("investors", []),
                "confidence_0to1": signal.get("confidence_0to1", 0.5),
            }
            
            # Try to extract round type from evidence if not already set
            if round_data["round_type"] == "undisclosed":
                evidence = signal.get("text", "").lower()
                if "series a" in evidence:
                    round_data["round_type"] = "Series A"
                elif "series b" in evidence:
                    round_data["round_type"] = "Series B"
                elif "series c" in evidence:
                    round_data["round_type"] = "Series C"
                elif "seed" in evidence:
                    round_data["round_type"] = "Seed"
                elif "growth" in evidence:
                    round_data["round_type"] = "Growth"
                elif "grant" in evidence:
                    round_data["round_type"] = "Grant"
            
            rounds.append(round_data)
        
        return rounds
    
    def _extract_awards(self, signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Extract and structure awards from signals."""
        award_signals = [s for s in signals if s.get("type") == "award"]
        
        awards = []
        for signal in award_signals:
            award_data = {
                "name": signal.get("award_name", signal.get("text", "")[:100]),
                "year": signal.get("date"),
                "organization": signal.get("organization"),
                "amount": signal.get("value"),  # For grants
                "currency": signal.get("value_unit", "USD") if signal.get("value") else None,
                "evidence": signal.get("text", ""),
                "source_url": signal.get("source_url"),
                "confidence_0to1": signal.get("confidence_0to1", 0.5),
            }
            awards.append(award_data)
        
        return awards
    
    def _infer_sector(self, summary: str) -> str:
        """Infer sector from company summary."""
        summary_lower = summary.lower()
        
        if any(w in summary_lower for w in ["sensor", "probe", "hardware", "equipment", "sprayer", "lidar"]):
            return "agtech_hardware"
        elif any(w in summary_lower for w in ["software", "saas", "platform", "analytics", "monitoring software"]):
            return "agtech_saas"
        elif any(w in summary_lower for w in ["iot", "connected", "smart"]) and any(w in summary_lower for w in ["sensor", "device"]):
            return "iot_hybrid"
        elif any(w in summary_lower for w in ["pheromone", "biological", "biotech", "bio-", "microb"]):
            return "biotech"
        elif any(w in summary_lower for w in ["consulting", "advisory", "service"]):
            return "services"
        elif any(w in summary_lower for w in ["logistics", "shipping", "distribution", "supply chain", "temperature"]):
            return "logistics"
        elif any(w in summary_lower for w in ["recycl", "reuse", "circular", "bottle"]):
            return "circular_economy"
        else:
            return "agtech_saas"  # Default
    
    def _parse_employee_band(self, size_str: str) -> str:
        """Parse employee band from various formats."""
        if not size_str:
            return "Unknown"
        
        size_str = str(size_str).strip()
        
        # Direct match
        if size_str in EMPLOYEE_BANDS:
            return size_str
        
        # Try common patterns
        for band in EMPLOYEE_BANDS:
            if band.lower() in size_str.lower():
                return band
        
        # Try to extract number
        match = re.search(r"(\d+)\s*(?:-\s*(\d+))?\s*employees?", size_str, re.IGNORECASE)
        if match:
            num1 = int(match.group(1))
            num2 = int(match.group(2)) if match.group(2) else num1
            
            # Find closest band
            if num1 <= 10:
                return "1-10"
            elif num1 <= 50:
                return "11-50"
            elif num1 <= 200:
                return "51-200"
            elif num1 <= 500:
                return "201-500"
            else:
                return "501-1000"
        
        # Just a number
        match = re.search(r"(\d+)", size_str)
        if match:
            num = int(match.group(1))
            if num <= 10:
                return "1-10"
            elif num <= 50:
                return "11-50"
            elif num <= 200:
                return "51-200"
            elif num <= 500:
                return "201-500"
            else:
                return "501-1000"
        
        return "Unknown"
    
    def _name_matches(self, name1: str, name2: str) -> bool:
        """Check if two company names match (fuzzy)."""
        # Normalize names
        def normalize(name: str) -> str:
            name = name.lower()
            # Remove common suffixes
            for suffix in [", inc.", ", inc", " inc.", " inc", ", llc", " llc", ", ltd", " ltd", 
                          " limited", " corporation", " corp", " corp.", " plc"]:
                name = name.replace(suffix, "")
            # Remove punctuation
            name = re.sub(r"[^\w\s]", "", name)
            return name.strip()
        
        n1 = normalize(name1)
        n2 = normalize(name2)
        
        # Exact match after normalization
        if n1 == n2:
            return True
        
        # One contains the other
        if n1 in n2 or n2 in n1:
            return True
        
        # Word overlap
        words1 = set(n1.split())
        words2 = set(n2.split())
        
        if len(words1) > 0 and len(words2) > 0:
            overlap = words1 & words2
            # At least 50% word overlap
            if len(overlap) >= min(len(words1), len(words2)) * 0.5:
                return True
        
        return False
    
    def _convert_sec_facts(self, facts: dict[str, Any]) -> list[dict[str, Any]]:
        """Convert SEC EDGAR facts to our financial year format."""
        metrics = facts.get("metrics", {})
        
        # Get revenue data
        revenue_data = metrics.get("revenue", [])
        
        years_data = []
        for item in revenue_data[:3]:  # Last 3 years
            year_match = re.search(r"(\d{4})", item.get("end_date", ""))
            if year_match:
                years_data.append({
                    "year": int(year_match.group(1)),
                    "revenue": item.get("value", 0),
                    "date": item.get("end_date"),
                })
        
        return years_data
    
    async def close(self):
        """Close all clients."""
        await self.finance_api.close()
        await self.registry.close()



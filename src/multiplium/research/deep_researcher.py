"""
Deep Research Orchestrator for Investment Due Diligence.

Gathers comprehensive company profiles with 9 required data points:
1. Executive Summary
2. Technology & Value Chain
3. Evidence of Impact
4. Key Clients
5. Team
6. Competitors
7. Financials (3 years) - Now with multi-path enrichment
8. Cap Table
9. SWOT

Financial Enrichment System:
- Listed companies → Finance APIs (FMP, Alpha Vantage) + SEC EDGAR
- Private with filed accounts → Company registries (Companies House, OpenCorporates)
- Private startups → Web/PR mining with GPT-4o + revenue estimation
- Output: 3-layer schema (exact, estimated, signals_raw)
"""

from __future__ import annotations

import asyncio
import json
import re
import structlog
from typing import Any, Callable

from multiplium.tools.perplexity_mcp import PerplexityMCPClient
from multiplium.research.financial_enricher import FinancialEnricher

# Import new prompt templates
try:
    from multiplium.prompts.deep_research import (
        build_deep_research_prompt,
        build_verification_prompt,
        WINE_INDUSTRY_CONTEXT,
    )
    PROMPTS_AVAILABLE = True
except ImportError:
    PROMPTS_AVAILABLE = False

logger = structlog.get_logger()


class DeepResearcher:
    """
    Comprehensive company research using multi-path enrichment.
    
    Cost Optimization:
    - FinancialEnricher (~$0.01): Multi-path financial enrichment
    - GPT-4o (~$0.01): Team, competitors, evidence (cost-effective, good quality)
    Total: ~$0.02 per company
    
    Financial Enrichment:
    - Listed: Finance APIs (FMP, Alpha Vantage) + SEC EDGAR
    - Private w/ filings: Registries (Companies House, OpenCorporates)
    - Startups: GPT-4o signal mining + sector heuristics estimation
    
    Time: ~3-5 minutes per company with optimized research.
    """
    
    def __init__(self):
        """Initialize deep researcher with financial enricher and OpenAI clients."""
        self.perplexity = PerplexityMCPClient()
        self.financial_enricher = FinancialEnricher()
        # Initialize OpenAI for team, competitors, and evidence research
        import os
        from openai import AsyncOpenAI
        self.openai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    async def research_company(
        self,
        company: dict[str, Any],
        depth: str = "full",
    ) -> dict[str, Any]:
        """
        Single-pass comprehensive research for a company.
        
        Args:
            company: Basic company data from discovery phase
                - company: name
                - summary: brief description
                - website: company URL (may be inaccurate)
                - country: headquarters country
                - sources: list of initial sources
            depth: "quick" (3-4 searches, ~$0.01) or "full" (8-10 searches, ~$0.02)
        
        Returns:
            Enhanced company profile with all 9 investment data points
        """
        company_name = company.get("company", "Unknown")
        website = company.get("website", "")
        initial_summary = company.get("summary", "")
        
        logger.info(
            "deep_research.start",
            company=company_name,
            website=website,
            depth=depth,
        )
        
        # Initialize enhanced profile
        enhanced = company.copy()
        enhanced["deep_research_status"] = "in_progress"
        
        # STEP 0: Verify and correct website URL (CRITICAL for accurate data)
        if not website or website in ("N/A", "Not Available", "Unknown"):
            verified_website = await self._find_official_website(company_name, initial_summary)
            if verified_website:
                enhanced["website"] = verified_website
                website = verified_website
                logger.info(
                    "deep_research.website_found",
                    company=company_name,
                    website=website,
                )
        
        try:
            if depth == "full":
                # Multi-path enrichment strategy:
                # Task 1: Financial enrichment (multi-path: APIs, registries, GPT-4o mining)
                financial_task = self.financial_enricher.enrich(company)
                
                # Task 2: Team, competitors, evidence via GPT-4o (cost-effective)
                # Pass segment for competitive landscape context
                segment = company.get("_source_segment")
                gpt4o_task = self._research_with_gpt4o(company_name, website, initial_summary, segment)
                
                # Execute in parallel
                results = await asyncio.gather(
                    financial_task,
                    gpt4o_task,
                    return_exceptions=True
                )
                
                # Merge results
                for result in results:
                    if isinstance(result, Exception):
                        logger.warning(
                            "deep_research.task_failed",
                            company=company_name,
                            error=str(result),
                        )
                        continue
                    
                    # Handle financial enrichment result specially
                    if isinstance(result, dict) and "entity_classification" in result:
                        # This is the new 3-layer financial enrichment result
                        enhanced["financial_enrichment"] = result
                        
                        # Also populate legacy fields for backward compatibility
                        enhanced = self._populate_legacy_financial_fields(enhanced, result)
                    else:
                        enhanced.update(result)
            
            else:
                # Quick mode: Single comprehensive query
                quick_result = await self._quick_research(
                    company_name, website, initial_summary
                )
                enhanced.update(quick_result)
            
            # Generate SWOT from gathered data (using enriched financial signals)
            enhanced = await self._generate_swot(enhanced)
            
            # Optional: Run verification step (improves quality but adds ~10s per company)
            if PROMPTS_AVAILABLE and depth == "full":
                verification_result = await self._verify_research(enhanced, initial_summary)
                enhanced["verification"] = verification_result
                
                # Adjust confidence based on verification
                if verification_result.get("confidence_adjustment"):
                    original_confidence = enhanced.get("confidence_0to1", 0.5)
                    adjusted = original_confidence + verification_result["confidence_adjustment"]
                    enhanced["confidence_0to1"] = max(0.0, min(1.0, adjusted))
            
            # Mark as complete
            enhanced["deep_research_status"] = "completed"
            
            # Calculate has_financials based on new enrichment
            has_financials = self._check_has_financials(enhanced)
            
            logger.info(
                "deep_research.complete",
                company=company_name,
                has_financials=has_financials,
                has_team=bool(enhanced.get("team")),
                has_competitors=bool(enhanced.get("competitors")),
                has_swot=bool(enhanced.get("swot")),
                has_exact_financials=bool(enhanced.get("financial_enrichment", {}).get("financials_exact")),
                has_estimated_financials=bool(enhanced.get("financial_enrichment", {}).get("financials_estimated")),
                signals_count=len(enhanced.get("financial_enrichment", {}).get("financial_signals_raw", [])),
            )
        
        except Exception as e:
            logger.error(
                "deep_research.failed",
                company=company_name,
                error=str(e),
            )
            enhanced["deep_research_status"] = "failed"
            enhanced["deep_research_error"] = str(e)
        
        return enhanced
    
    async def research_batch(
        self,
        companies: list[dict[str, Any]],
        max_concurrent: int = 5,
        depth: str = "full",
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Process multiple companies in parallel batches.
        
        Args:
            companies: List of company dicts from discovery
            max_concurrent: Number of companies to research in parallel
            depth: Research depth ("quick" or "full")
            progress_callback: Optional callback(completed, total) for real-time progress updates
        
        Returns:
            List of enhanced company profiles
        
        Cost: ~$0.02/company × N companies
        Time: ~(N / max_concurrent) × 5-8 minutes
        """
        logger.info(
            "deep_research.batch_start",
            total_companies=len(companies),
            max_concurrent=max_concurrent,
            depth=depth,
        )
        
        results = []
        total_companies = len(companies)
        
        for i in range(0, len(companies), max_concurrent):
            batch = companies[i:i+max_concurrent]
            batch_num = (i // max_concurrent) + 1
            
            logger.info(
                "deep_research.batch_processing",
                batch=batch_num,
                batch_size=len(batch),
            )
            
            batch_results = await asyncio.gather(*[
                self.research_company(c, depth=depth) for c in batch
            ])
            results.extend(batch_results)
            
            # Report progress after each batch
            if progress_callback:
                progress_callback(len(results), total_companies)
        
        # Summary statistics
        completed = sum(1 for r in results if r.get("deep_research_status") == "completed")
        failed = sum(1 for r in results if r.get("deep_research_status") == "failed")
        
        logger.info(
            "deep_research.batch_complete",
            total=len(results),
            completed=completed,
            failed=failed,
        )
        
        return results
    
    async def _research_financials(
        self,
        company_name: str,
        website: str,
    ) -> dict[str, Any]:
        """
        Use Perplexity Pro to gather financial data.
        
        Perplexity is trained on Crunchbase data and excels at finding:
        - Funding rounds and amounts
        - Investors and lead investors
        - Revenue estimates and growth
        - Valuation data
        - Cap table information (if public)
        """
        financial_query = f"""
Find detailed financial data for {company_name} ({website}):

1. **Funding History:**
   - Total funding raised (all rounds)
   - Most recent funding round (date, amount, type, lead investor)
   - Complete funding history (Series A, B, seed, etc.)

2. **Investors & Cap Table:**
   - Key investors and venture capital firms
   - Lead investors for each round
   - Cap table structure (if disclosed)
   - Notable strategic investors

3. **Financial Performance:**
   - Revenue (last 3 years if available)
   - Revenue growth rate
   - EBITDA or profitability status
   - Burn rate or runway (if disclosed)

4. **Valuation:**
   - Last disclosed valuation
   - Valuation history across rounds

5. **Cost Structure:**
   - R&D spending
   - Sales & marketing spend
   - Operational costs
   - Employee count trends

Focus on wine/agriculture technology company metrics.
Prioritize Crunchbase, PitchBook, company announcements, and financial news.
Cite all sources with URLs.
"""
        
        try:
            # Use Perplexity Pro's research mode for comprehensive search
            result = await self.perplexity.research(financial_query)
            
            # Parse response
            financial_data = self._parse_financial_response(result)
            
            logger.info(
                "deep_research.financials.success",
                company=company_name,
                funding_found=bool(financial_data.get("funding_rounds")),
                revenue_found=bool(financial_data.get("revenue_3yr")),
            )
            
            return financial_data
        
        except Exception as e:
            logger.warning(
                "deep_research.financials.failed",
                company=company_name,
                error=str(e),
            )
            return {
                "financials": "Not Disclosed",
                "cap_table": "Not Disclosed",
                "funding_rounds": [],
                "investors": [],
                "revenue_3yr": "Not Disclosed",
            }
    
    async def _research_with_gpt4o(
        self,
        company_name: str,
        website: str,
        initial_summary: str,
        segment: str | None = None,
    ) -> dict[str, Any]:
        """
        Use GPT-4o to gather team, competitors, and evidence data in one efficient call.
        
        Cost: ~$0.005 per company (vs $0.015 with 3 separate Perplexity calls)
        Speed: ~2-3 minutes (vs 6-9 minutes with separate calls)
        Quality: Excellent for structured data extraction
        
        Now uses wine-industry specific prompts with competitive landscape context.
        """
        # Use new unified prompts if available
        if PROMPTS_AVAILABLE:
            comprehensive_prompt = build_deep_research_prompt(
                company_name=company_name,
                website=website,
                initial_summary=initial_summary,
                segment=segment,
            )
        else:
            # Fallback to legacy prompt
            comprehensive_prompt = f"""
Research the following company comprehensively. Use web search to find current, accurate information.

**Company:** {company_name}
**Website:** {website}
**Context:** {initial_summary}

Gather the following data and return as structured JSON:

**1. TEAM DATA:**
- Founders (names, backgrounds, LinkedIn if available)
- Key executives (CEO, CTO, COO with names and backgrounds)
- Team size (number of employees)
- Notable advisors or board members
- Company culture and values

**2. COMPETITIVE LANDSCAPE:**
- 3-5 direct competitors (wine/agriculture technology companies)
- For each competitor: name and brief description
- How {company_name} differentiates from competitors
- Unique technology or approach
- Competitive advantages
- Market positioning (target customers, geography, pricing)

**3. EVIDENCE OF IMPACT:**
- Additional case studies with quantified metrics
- Named vineyard/winery deployments
- Academic papers or research validations
- Industry awards or certifications
- Customer testimonials with specific results

**4. KEY CLIENTS:**
- List of named clients (wineries, vineyards)
- Geographic markets served
- Notable customer references

Search wine industry sources, LinkedIn, company website, Crunchbase, and industry publications.

Return JSON with this structure:
{{
  "team": {{
    "founders": ["name1", "name2"],
    "executives": ["CEO: name", "CTO: name"],
    "size": "X employees",
    "advisors": ["advisor1"]
  }},
  "competitors": {{
    "direct": ["competitor1", "competitor2", "competitor3"],
    "differentiation": "How company stands out..."
  }},
  "evidence_of_impact": {{
    "case_studies": ["metric1", "metric2"],
    "academic_papers": [],
    "awards": []
  }},
  "key_clients": ["client1", "client2"]
}}
"""
        
        try:
            # Use GPT-4o with web search
            response = await self.openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a research analyst gathering company intelligence. Use web search to find accurate, current information. Return structured JSON only."},
                    {"role": "user", "content": comprehensive_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            
            # Parse response
            result_text = response.choices[0].message.content
            result_data = json.loads(result_text)
            
            logger.info(
                "deep_research.gpt4o.success",
                company=company_name,
                has_team=bool(result_data.get("team")),
                has_competitors=bool(result_data.get("competitors")),
                has_evidence=bool(result_data.get("evidence_of_impact")),
            )
            
            return result_data
        
        except Exception as e:
            logger.warning(
                "deep_research.gpt4o.failed",
                company=company_name,
                error=str(e),
            )
            return {
                "team": {
                    "founders": [],
                    "executives": [],
                    "size": "Unknown",
                    "advisors": [],
                },
                "competitors": {
                    "direct": [],
                    "differentiation": "Unknown",
                },
                "evidence_of_impact": {
                    "case_studies": [],
                    "academic_papers": [],
                    "awards": [],
                },
                "key_clients": [],
            }
    
    async def _research_team(
        self,
        company_name: str,
        website: str,
    ) -> dict[str, Any]:
        """
        Use Perplexity Pro to find team data from LinkedIn and company sources.
        
        Gathers:
        - Founders (names, backgrounds, LinkedIn profiles)
        - Key executives (CEO, CTO, COO, CMO)
        - Team size
        - Notable advisors or board members
        """
        team_query = f"""
Find comprehensive team information for {company_name} ({website}):

1. **Founders:**
   - Names and titles
   - Professional backgrounds (previous companies, education)
   - LinkedIn profiles
   - Relevant wine/agriculture experience

2. **Key Executives:**
   - CEO (name, background)
   - CTO/Chief Product Officer (name, background)
   - COO/VP Operations (name, background)
   - CMO/Head of Sales (name, background)

3. **Team Size:**
   - Total number of employees
   - Growth trajectory
   - Department breakdown (engineering, sales, operations)

4. **Advisory Board & Investors:**
   - Notable advisors
   - Board members
   - Strategic investors with active roles

5. **Company Culture:**
   - Values and mission alignment with sustainability
   - Remote vs. in-office
   - Key hiring announcements

Search LinkedIn, company website, Crunchbase, press releases, and team pages.
Cite all sources with URLs.
"""
        
        try:
            result = await self.perplexity.research(team_query)
            
            team_data = self._parse_team_response(result)
            
            logger.info(
                "deep_research.team.success",
                company=company_name,
                founders_found=bool(team_data.get("team", {}).get("founders")),
                team_size_found=bool(team_data.get("team", {}).get("size")),
            )
            
            return team_data
        
        except Exception as e:
            logger.warning(
                "deep_research.team.failed",
                company=company_name,
                error=str(e),
            )
            return {
                "team": {
                    "founders": [],
                    "executives": [],
                    "size": "Unknown",
                    "advisors": [],
                }
            }
    
    async def _research_competitors(
        self,
        company_name: str,
        website: str,
        initial_summary: str,
    ) -> dict[str, Any]:
        """
        Use Perplexity Pro to map competitive landscape.
        
        Identifies:
        - Direct competitors (2-3 main ones)
        - How company differentiates
        - Competitive advantages
        - Market positioning
        """
        competitors_query = f"""
Analyze the competitive landscape for {company_name} ({website}):

Context: {initial_summary}

1. **Direct Competitors:**
   - Identify 3-5 main direct competitors
   - For each competitor, provide:
     * Company name
     * Brief description
     * Key differentiators vs. {company_name}
     * Market presence (regions, customer base)

2. **Differentiation:**
   - How does {company_name} differentiate from competitors?
   - Unique technology or approach
   - Patents or proprietary IP
   - Key competitive advantages

3. **Market Positioning:**
   - Target customer segment (SME wineries vs. large producers)
   - Geographic focus vs. competitors
   - Pricing strategy (premium vs. value)
   - Go-to-market strategy

4. **Competitive Threats:**
   - New entrants in the space
   - Technology shifts
   - Consolidation risks

Search wine industry reports, competitor websites, market analyses, and industry news.
Cite all sources with URLs.
"""
        
        try:
            result = await self.perplexity.research(competitors_query)
            
            competitors_data = self._parse_competitors_response(result)
            
            logger.info(
                "deep_research.competitors.success",
                company=company_name,
                competitors_found=len(competitors_data.get("competitors", {}).get("direct", [])),
            )
            
            return competitors_data
        
        except Exception as e:
            logger.warning(
                "deep_research.competitors.failed",
                company=company_name,
                error=str(e),
            )
            return {
                "competitors": {
                    "direct": [],
                    "differentiation": "Unknown",
                }
            }
    
    async def _research_evidence_deep(
        self,
        company_name: str,
        website: str,
        initial_summary: str,
    ) -> dict[str, Any]:
        """
        Deep dive into evidence of impact with quantified metrics.
        
        Expands initial evidence with:
        - Additional case studies
        - Peer-reviewed papers
        - Industry validation
        - Customer testimonials
        """
        evidence_query = f"""
Find comprehensive evidence of impact for {company_name} ({website}):

Context: {initial_summary}

1. **Quantified Case Studies:**
   - Named vineyard/winery deployments
   - Specific quantified results (%, hectares, tCO2e, liters saved)
   - Before/after metrics
   - Duration of deployment

2. **Academic Validation:**
   - Peer-reviewed papers citing the technology
   - University research partnerships
   - Government studies or grants

3. **Industry Recognition:**
   - Awards and certifications
   - Industry publication features
   - Conference presentations
   - Pilot programs with major wine companies

4. **Customer Testimonials:**
   - Quotes from winery owners/winemakers
   - Customer success stories
   - Named references

Search academic databases, wine industry publications, company case studies, and press releases.
Cite all sources with URLs (prioritize Tier 1/2 sources).
"""
        
        try:
            result = await self.perplexity.research(evidence_query)
            
            evidence_data = self._parse_evidence_response(result)
            
            logger.info(
                "deep_research.evidence.success",
                company=company_name,
                case_studies_found=len(evidence_data.get("evidence_of_impact", {}).get("case_studies", [])),
            )
            
            return evidence_data
        
        except Exception as e:
            logger.warning(
                "deep_research.evidence.failed",
                company=company_name,
                error=str(e),
            )
            return {
                "evidence_of_impact": {
                    "case_studies": [],
                    "academic_papers": [],
                    "awards": [],
                }
            }
    
    async def _quick_research(
        self,
        company_name: str,
        website: str,
        initial_summary: str,
    ) -> dict[str, Any]:
        """
        Quick single-query research for cost-conscious deep dive.
        
        Uses 1 Perplexity Pro research call (~$0.01) to gather all data points.
        """
        comprehensive_query = f"""
Comprehensive investment research for {company_name} ({website}):

Context: {initial_summary}

Gather ALL of the following data points:

**1. FINANCIALS:**
- Total funding raised and recent rounds
- Key investors
- Revenue estimates (last 3 years if available)
- Cap table structure (if disclosed)

**2. TEAM:**
- Founders (names, backgrounds)
- Key executives (CEO, CTO, etc.)
- Team size

**3. COMPETITORS:**
- 2-3 main direct competitors
- How {company_name} differentiates

**4. EVIDENCE:**
- Key case studies with quantified metrics
- Named clients/references
- Academic or industry validation

**5. SWOT INPUTS:**
- Key strengths
- Potential weaknesses or risks
- Market opportunities
- Competitive threats

Focus on wine/agriculture technology context.
Cite all sources with URLs.
Prioritize Crunchbase, LinkedIn, company website, and wine industry publications.
"""
        
        try:
            result = await self.perplexity.research(comprehensive_query)
            
            # Parse comprehensive response
            data = self._parse_comprehensive_response(result)
            
            logger.info(
                "deep_research.quick.success",
                company=company_name,
            )
            
            return data
        
        except Exception as e:
            logger.warning(
                "deep_research.quick.failed",
                company=company_name,
                error=str(e),
            )
            return {}
    
    async def _generate_swot(self, company: dict[str, Any]) -> dict[str, Any]:
        """
        Generate SWOT analysis from gathered data.
        
        Uses structured data to create a comprehensive SWOT:
        - Strengths: From evidence, team, technology, financial growth
        - Weaknesses: From financials, competitive analysis
        - Opportunities: From market trends, value chain gaps
        - Threats: From competitors, market risks
        """
        company_name = company.get("company", "Unknown")
        
        # Extract relevant data for SWOT
        # Use `or {}` pattern because keys may exist with None values
        financials = company.get("financials", "Not Disclosed")
        team = company.get("team") or {}
        competitors = company.get("competitors") or {}
        evidence = company.get("evidence_of_impact") or {}
        
        # Get new financial enrichment data
        # Use `or {}` pattern because keys may exist with None values
        enrichment = company.get("financial_enrichment") or {}
        funding_rounds = enrichment.get("funding_rounds") or []
        signals = enrichment.get("financial_signals_raw") or []
        estimated = enrichment.get("financials_estimated") or {}
        exact = enrichment.get("financials_exact")
        
        # Build SWOT from data
        swot = {
            "strengths": [],
            "weaknesses": [],
            "opportunities": [],
            "threats": [],
        }
        
        # Strengths from evidence
        if evidence and isinstance(evidence, dict):
            case_studies = evidence.get("case_studies", [])
            if case_studies:
                swot["strengths"].append(f"Proven impact with {len(case_studies)} documented case studies")
            
            awards = evidence.get("awards", [])
            if awards:
                swot["strengths"].append(f"Industry recognition: {', '.join(str(a) for a in awards[:2])}")
        
        # Strengths from team
        if team and isinstance(team, dict):
            founders = team.get("founders", [])
            if founders:
                swot["strengths"].append("Experienced founding team with wine/agriculture expertise")
        
        # Strengths from financial signals (filter out None signals)
        growth_signals = [s for s in signals if s and s.get("type") == "growth_rate"]
        if growth_signals:
            swot["strengths"].append("Demonstrated growth trajectory")
        
        if funding_rounds:
            total_rounds = len(funding_rounds)
            swot["strengths"].append(f"Secured {total_rounds} funding round(s)")
        
        scale_signals = [s for s in signals if s and s.get("type") == "scale"]
        if scale_signals:
            swot["strengths"].append("Established market presence with measurable scale")
        
        # Weaknesses from financials
        has_financial_data = (
            (exact and exact.get("years")) or
            estimated.get("revenue_estimate") or
            len(funding_rounds) > 0
        )
        
        if not has_financial_data:
            swot["weaknesses"].append("Limited publicly available financial data")
        elif estimated and not exact:
            swot["weaknesses"].append("Financial data based on estimates, not audited figures")
        
        # Weaknesses from signals (filter out None signals)
        profitability_signals = [s for s in signals if s and s.get("type") == "profitability"]
        for sig in profitability_signals:
            text = sig.get("text", "").lower()
            if "burn" in text or "loss" in text or "not profitable" in text:
                swot["weaknesses"].append("Pre-profitability stage company")
                break
        
        # Opportunities from value chain
        swot["opportunities"].append("Growing wine industry demand for sustainability solutions")
        swot["opportunities"].append("Regulatory drivers for carbon reduction and traceability")
        
        # Opportunities from classification
        classification = enrichment.get("entity_classification") or {}
        sector = classification.get("likely_sector", "")
        if sector in ("agtech_saas", "iot_hybrid"):
            swot["opportunities"].append("SaaS model enables recurring revenue growth")
        
        # Threats from competitors
        if competitors and isinstance(competitors, dict):
            direct_competitors = competitors.get("direct", [])
            if len(direct_competitors) >= 3:
                swot["threats"].append(f"Competitive market with {len(direct_competitors)}+ direct competitors")
        
        swot["threats"].append("Technology adoption barriers in traditional wine industry")
        
        company["swot"] = swot
        
        logger.info(
            "deep_research.swot.generated",
            company=company_name,
            strengths=len(swot["strengths"]),
            weaknesses=len(swot["weaknesses"]),
            opportunities=len(swot["opportunities"]),
            threats=len(swot["threats"]),
        )
        
        return company
    
    async def _verify_research(
        self,
        company_data: dict[str, Any],
        original_summary: str,
    ) -> dict[str, Any]:
        """
        Verify research findings for accuracy and completeness.
        
        This adds a quality control step to ensure:
        - Vineyard evidence is real and verifiable
        - Team/executive data is accurate
        - Financial claims are plausible
        - Competitive positioning makes sense
        
        Returns verification result with potential confidence adjustment.
        """
        company_name = company_data.get("company", "Unknown")
        
        logger.info(
            "deep_research.verification.start",
            company=company_name,
        )
        
        try:
            verification_prompt = build_verification_prompt(
                company_data=company_data,
                original_summary=original_summary,
            )
            
            response = await self.openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a research quality analyst. Verify the accuracy and completeness of "
                            "company research findings. Be critical but fair. Return structured JSON."
                        )
                    },
                    {"role": "user", "content": verification_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            
            result_text = response.choices[0].message.content
            verification_result = json.loads(result_text)
            
            logger.info(
                "deep_research.verification.complete",
                company=company_name,
                status=verification_result.get("verification_status", "unknown"),
                recommendation=verification_result.get("recommendation", "unknown"),
            )
            
            return verification_result
        
        except Exception as e:
            logger.warning(
                "deep_research.verification.failed",
                company=company_name,
                error=str(e),
            )
            return {
                "verification_status": "skipped",
                "confidence_adjustment": 0.0,
                "error": str(e),
            }
    
    def _parse_financial_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """Extract structured financial data from Perplexity response."""
        # Perplexity returns: {"answer": "...", "sources": [...]}
        answer = response.get("answer", "")
        sources = response.get("sources", [])
        
        # Extract funding info (simple regex-based extraction)
        funding_patterns = [
            r'raised\s+\$?([\d.]+)\s*(million|M|billion|B)',
            r'funding.*?\$?([\d.]+)\s*(million|M|billion|B)',
            r'Series\s+([A-Z])\s*:\s*\$?([\d.]+)\s*(million|M)',
        ]
        
        funding_rounds = []
        for pattern in funding_patterns:
            matches = re.findall(pattern, answer, re.IGNORECASE)
            for match in matches:
                if len(match) >= 2:
                    amount = match[0]
                    unit = match[1]
                    funding_rounds.append(f"${amount}{unit}")
        
        # Extract investors
        investor_patterns = [
            r'(?:led by|investor[s]?:?)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'([A-Z][a-z]+\s+(?:Capital|Ventures|Partners|Fund))',
        ]
        
        investors = []
        for pattern in investor_patterns:
            matches = re.findall(pattern, answer)
            investors.extend(matches[:5])  # Limit to top 5
        
        return {
            "financials": answer if answer else "Not Disclosed",
            "cap_table": "See financials" if funding_rounds else "Not Disclosed",
            "funding_rounds": funding_rounds[:5],  # Top 5 rounds
            "investors": list(set(investors))[:5],  # Top 5 unique investors
            "revenue_3yr": "Not Disclosed",  # Usually not public for startups
            "sources": [s.get("url", "") for s in sources if s.get("url")],
        }
    
    def _parse_team_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """Extract structured team data from Perplexity response."""
        answer = response.get("answer", "")
        sources = response.get("sources", [])
        
        # Extract founder names (simple pattern matching)
        founder_patterns = [
            r'(?:founded by|founder[s]?:?)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'([A-Z][a-z]+\s+[A-Z][a-z]+),?\s+(?:CEO|CTO|Co-founder)',
        ]
        
        founders = []
        for pattern in founder_patterns:
            matches = re.findall(pattern, answer)
            founders.extend(matches[:5])
        
        # Extract team size
        size_patterns = [
            r'(\d+)\s+employees',
            r'team of\s+(\d+)',
            r'staff of\s+(\d+)',
        ]
        
        team_size = "Unknown"
        for pattern in size_patterns:
            match = re.search(pattern, answer, re.IGNORECASE)
            if match:
                team_size = f"{match.group(1)} employees"
                break
        
        return {
            "team": {
                "founders": list(set(founders)),
                "executives": [],  # Could enhance with more parsing
                "size": team_size,
                "advisors": [],
                "summary": answer if answer else "Team data not available",
            },
            "sources": [s.get("url", "") for s in sources if s.get("url")],
        }
    
    def _parse_competitors_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """Extract structured competitor data from Perplexity response."""
        answer = response.get("answer", "")
        sources = response.get("sources", [])
        
        # Extract competitor names
        competitor_patterns = [
            r'(?:competitors?:?|competing with)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:is a|offers|provides)',
        ]
        
        competitors = []
        for pattern in competitor_patterns:
            matches = re.findall(pattern, answer)
            competitors.extend(matches[:5])
        
        return {
            "competitors": {
                "direct": list(set(competitors))[:5],
                "differentiation": answer if answer else "Competitive analysis not available",
            },
            "sources": [s.get("url", "") for s in sources if s.get("url")],
        }
    
    def _parse_evidence_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """Extract structured evidence data from Perplexity response."""
        answer = response.get("answer", "")
        sources = response.get("sources", [])
        
        # Extract case study metrics (simple pattern matching)
        metric_patterns = [
            r'(\d+%)\s+(?:reduction|increase|improvement)',
            r'(\d+)\s+(?:hectares|ha|vineyards?|wineries)',
            r'(\d+)\s+(?:tCO2e|tonnes?|kg)',
        ]
        
        case_studies = []
        for pattern in metric_patterns:
            matches = re.findall(pattern, answer, re.IGNORECASE)
            case_studies.extend([m if isinstance(m, str) else m[0] for m in matches[:5]])
        
        return {
            "evidence_of_impact": {
                "case_studies": list(set(case_studies)),
                "academic_papers": [],  # Could enhance with more parsing
                "awards": [],
                "summary": answer if answer else "Evidence data not available",
            },
            "sources": [s.get("url", "") for s in sources if s.get("url")],
        }
    
    async def _find_official_website(
        self,
        company_name: str,
        summary: str = "",
    ) -> str:
        """
        Use Perplexity to find the official company website.
        
        This is a targeted, efficient search specifically for the website URL.
        Cost: ~$0.005 per search (much cheaper than full research).
        """
        website_query = f"""
Find the official website URL for {company_name}.

Context: {summary}

Return ONLY the official company website URL (e.g., https://example.com).
Do NOT return social media links, news articles, or other sites.

If it's a wine/agriculture technology company, verify it's the correct company.
"""
        
        try:
            # Use Perplexity's "ask" mode for quick factual lookup
            result = await self.perplexity.ask(website_query)
            answer = result.get("answer", "")
            
            # Extract URL from answer using regex
            import re
            url_pattern = r'https?://(?:www\.)?([a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?)'
            matches = re.findall(url_pattern, answer)
            
            if matches:
                # Return first match, ensure it has http/https
                url = matches[0]
                if not url.startswith("http"):
                    url = f"https://{url}"
                
                logger.info(
                    "deep_research.website_found",
                    company=company_name,
                    website=url,
                )
                return url
            
            # Fallback: Try to extract from sources
            sources = result.get("sources", [])
            for source in sources:
                source_url = source.get("url", "")
                # Look for company domain (not news/blog sites)
                if company_name.lower().replace(" ", "") in source_url.lower().replace("-", ""):
                    return source_url
            
            logger.warning(
                "deep_research.website_not_found",
                company=company_name,
            )
            return ""
        
        except Exception as e:
            logger.error(
                "deep_research.website_search_failed",
                company=company_name,
                error=str(e),
            )
            return ""
    
    def _parse_comprehensive_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """Parse comprehensive single-query response."""
        # Combine all parsing methods
        financial = self._parse_financial_response(response)
        team = self._parse_team_response(response)
        competitors = self._parse_competitors_response(response)
        evidence = self._parse_evidence_response(response)
        
        # Merge all data
        result = {}
        result.update(financial)
        result.update(team)
        result.update(competitors)
        result.update(evidence)
        
        return result
    
    def _populate_legacy_financial_fields(
        self,
        enhanced: dict[str, Any],
        enrichment: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Populate legacy financial fields for backward compatibility.
        
        Maps the new 3-layer enrichment schema to the old flat fields:
        - financials
        - cap_table
        - funding_rounds
        - investors
        - revenue_3yr
        """
        exact = enrichment.get("financials_exact")
        estimated = enrichment.get("financials_estimated")
        signals = enrichment.get("financial_signals_raw", [])
        funding_rounds = enrichment.get("funding_rounds", [])
        
        # Populate financials summary
        if exact and exact.get("years"):
            # We have exact financial data
            years = exact["years"]
            if years:
                latest = years[0]
                revenue = latest.get("revenue", 0)
                if revenue:
                    enhanced["financials"] = f"Revenue: ${revenue:,.0f} ({latest.get('year', 'N/A')})"
                    enhanced["revenue_3yr"] = [
                        {"year": y.get("year"), "revenue": y.get("revenue")}
                        for y in years[:3]
                    ]
                else:
                    enhanced["financials"] = "See financial_enrichment for details"
            
            # Extract cap table info if available
            enhanced["cap_table"] = exact.get("source", "See financial_enrichment")
        
        elif estimated:
            # We have estimated data
            rev_est = estimated.get("revenue_estimate", {})
            if rev_est:
                min_rev = rev_est.get("min", 0)
                max_rev = rev_est.get("max", 0)
                confidence = rev_est.get("confidence_0to1", 0)
                enhanced["financials"] = (
                    f"Estimated Revenue: ${min_rev:,.0f} - ${max_rev:,.0f} "
                    f"(confidence: {confidence:.0%})"
                )
                enhanced["revenue_3yr"] = "Estimated - see financial_enrichment"
            else:
                enhanced["financials"] = "Not Disclosed"
                enhanced["revenue_3yr"] = "Not Disclosed"
            
            enhanced["cap_table"] = "Not Disclosed"
        
        else:
            enhanced["financials"] = "Not Disclosed"
            enhanced["cap_table"] = "Not Disclosed"
            enhanced["revenue_3yr"] = "Not Disclosed"
        
        # Populate funding rounds
        if funding_rounds:
            enhanced["funding_rounds"] = funding_rounds
            
            # Extract investors from funding rounds
            investors = set()
            for rnd in funding_rounds:
                evidence = rnd.get("evidence", "")
                # Simple extraction of investor names
                if "led by" in evidence.lower():
                    # Try to extract investor name after "led by"
                    import re
                    match = re.search(r"led by\s+([A-Z][a-zA-Z\s]+?)(?:[,\.]|$)", evidence, re.IGNORECASE)
                    if match:
                        investors.add(match.group(1).strip())
            
            enhanced["investors"] = list(investors)
        else:
            enhanced["funding_rounds"] = []
            enhanced["investors"] = []
        
        return enhanced
    
    def _check_has_financials(self, enhanced: dict[str, Any]) -> bool:
        """
        Check if the company has meaningful financial data.
        
        Returns True if:
        - Has exact financials with revenue data, OR
        - Has estimated financials, OR
        - Has funding rounds, OR
        - Has 3+ financial signals
        """
        enrichment = enhanced.get("financial_enrichment") or {}
        
        # Check for exact financials
        exact = enrichment.get("financials_exact")
        if exact:
            if exact.get("years"):
                for year in exact["years"]:
                    if year.get("revenue", 0) > 0:
                        return True
        
        # Check for estimated financials
        estimated = enrichment.get("financials_estimated")
        if estimated and estimated.get("revenue_estimate"):
            return True
        
        # Check for funding rounds
        funding_rounds = enrichment.get("funding_rounds") or []
        if len(funding_rounds) > 0:
            return True
        
        # Check for meaningful signals
        signals = enrichment.get("financial_signals_raw") or []
        meaningful_signals = [
            s for s in signals if s  # Filter out None signals
            and s.get("type") in ("funding", "revenue", "contract")
            and s.get("confidence_0to1", 0) >= 0.5
        ]
        if len(meaningful_signals) >= 2:
            return True
        
        return False


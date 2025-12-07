"""
Deep research prompt templates.

Provides specialized prompts for the deep research phase that gathers:
- Team & leadership data
- Competitive landscape
- Financial signals
- Evidence of impact
- SWOT analysis

Includes wine industry-specific context and verification steps.
"""

from __future__ import annotations

from typing import Any


# =============================================================================
# WINE INDUSTRY CONTEXT
# =============================================================================

WINE_INDUSTRY_CONTEXT = """
**WINE INDUSTRY CONTEXT (use for relevant framing):**

🍷 **Market Structure:**
- Global wine market: ~$400B annually, 7.5B cases produced
- Premium segment ($15+/bottle) growing faster than value
- Top producing countries: France, Italy, Spain, USA, Argentina, Australia, Chile
- ~500,000 wineries worldwide, majority are SMEs (<500,000 cases/year)

📈 **Technology Adoption Trends:**
- Precision viticulture adoption: ~15% of global vineyard area
- IoT/sensor deployment accelerating post-2020
- Sustainability driving tech investment (EU Green Deal, SBTi adoption)
- Labor shortages increasing robotics interest

🏆 **Relevant Investors & Accelerators:**
- AgFunder (wine-tech portfolio includes: Biome Makers, Trace Genomics)
- Astanor Ventures (EU agtech focus)
- WineTech Network (industry-specific)
- SVG Partners (agricultural innovation)
- BASF Venture Capital (crop protection)
- Syngenta Ventures (biological solutions)

🎯 **Wine Industry Grant Programs:**
- EU CAP (Common Agricultural Policy) - vineyard modernization
- USDA SBIR/STTR - agricultural technology
- CalRecycle (California) - circular economy
- Wine Australia R&D grants
- Innovate UK - agricultural technology

📊 **Typical Wine-Tech Company Metrics:**
- Seed/Series A: $1-5M funding
- Series B+: $10-30M funding
- Revenue per employee: $150K-400K (varies by segment)
- Vineyard deployments: 10-50 for early stage, 200+ for growth stage
"""


# =============================================================================
# WINE INDUSTRY COMPETITORS BY SEGMENT
# =============================================================================

WINE_TECH_COMPETITIVE_LANDSCAPE = {
    "soil_health": {
        "leaders": ["Biome Makers (Spain)", "Trace Genomics (USA)", "Sound Agriculture (USA)"],
        "challengers": ["Pattern Ag", "AgBiome", "Indigo Agriculture"],
        "categories": "Soil microbiome testing, biologicals, carbon sequestration",
    },
    "irrigation": {
        "leaders": ["SupPlant (Israel)", "Fruition Sciences (USA)", "Tule Technologies (USA)"],
        "challengers": ["CropX", "Ceres Imaging", "Hortau", "WiseConn"],
        "categories": "Precision irrigation, water stress monitoring, ET-based scheduling",
    },
    "ipm_pest": {
        "leaders": ["Suterra (USA)", "Biobest (Belgium)", "Koppert (Netherlands)"],
        "challengers": ["Trapview", "Semios", "Spensa Technologies", "ISCA Technologies"],
        "categories": "Pheromone mating disruption, biocontrol, pest monitoring",
    },
    "canopy_robotics": {
        "leaders": ["Naïo Technologies (France)", "VineView (USA)", "Ceres Imaging (USA)"],
        "challengers": ["Abundant Robotics", "Iron Ox", "TerraClear", "Burro"],
        "categories": "Robotic pruning, drone mapping, NDVI analytics",
    },
    "carbon_traceability": {
        "leaders": ["eProvenance (France)", "Regrow Ag (USA)", "Evigence (Israel)"],
        "challengers": ["Nori", "Indigo Ag (carbon)", "Boomitra", "Watershed"],
        "categories": "Carbon MRV, blockchain provenance, sustainability reporting",
    },
    "vineyard_management": {
        "leaders": ["Vintrace (Australia)", "eVineyard (Spain)", "Croptracker (Canada)"],
        "challengers": ["Granular", "Conservis", "FarmLogs", "Agrivi"],
        "categories": "Farm management software, yield prediction, compliance tracking",
    },
    "winery_production": {
        "leaders": ["Pulsarbox (France)", "Wine Spectroscopy (Australia)", "Parsec (Italy)"],
        "challengers": ["TankIQ", "EnWine", "Sigfox wine solutions"],
        "categories": "Fermentation monitoring, tank sensors, winemaking analytics",
    },
    "packaging": {
        "leaders": ["O-I Glass (USA)", "Amorim Cork (Portugal)", "Verallia (France)"],
        "challengers": ["Vinventions (Nomacorc)", "Estal Packaging", "Vetropack"],
        "categories": "Lightweight glass, sustainable closures, packaging automation",
    },
    "distribution": {
        "leaders": ["ShipCompliant (USA)", "eProvenance (France)", "VinoShipper (USA)"],
        "challengers": ["SevenFifty", "LibDib", "Provi"],
        "categories": "Compliance, DTC fulfillment, cold chain monitoring",
    },
}


# =============================================================================
# DEEP RESEARCH PROMPT BUILDER
# =============================================================================

def build_deep_research_prompt(
    company_name: str,
    website: str,
    initial_summary: str,
    segment: str | None = None,
) -> str:
    """
    Build comprehensive deep research prompt for a company.
    
    Uses wine industry context for relevant framing and competitor identification.
    
    Args:
        company_name: Name of the company
        website: Company website URL
        initial_summary: Brief description from discovery phase
        segment: Optional segment classification for competitor context
    
    Returns:
        Formatted prompt for GPT-4o research
    """
    # Get relevant competitor context
    competitor_context = ""
    if segment:
        segment_key = _normalize_segment_key(segment)
        if segment_key in WINE_TECH_COMPETITIVE_LANDSCAPE:
            landscape = WINE_TECH_COMPETITIVE_LANDSCAPE[segment_key]
            competitor_context = f"""
**COMPETITIVE LANDSCAPE CONTEXT:**
- Market leaders: {', '.join(landscape['leaders'])}
- Challengers: {', '.join(landscape['challengers'])}
- Categories: {landscape['categories']}

Position {company_name} relative to these players.
"""

    return f"""Research the following wine/agriculture technology company comprehensively.

**COMPANY:** {company_name}
**WEBSITE:** {website}
**INITIAL CONTEXT:** {initial_summary}

{WINE_INDUSTRY_CONTEXT}

{competitor_context}

**GATHER THE FOLLOWING DATA (return as structured JSON):**

**1. TEAM DATA:**
- Founders (names, backgrounds, LinkedIn profiles if available)
- Key executives (CEO, CTO, COO with names and brief backgrounds)
- Team size (number of employees, growth trajectory)
- Notable advisors or board members
- Wine/agriculture industry experience (specific, named previous roles)

**2. COMPETITIVE LANDSCAPE:**
- 3-5 direct competitors in wine/agriculture technology
- For each competitor: name, brief description, key differentiator vs. {company_name}
- How {company_name} differentiates (unique technology, approach, target market)
- Competitive advantages (patents, proprietary data, partnerships)
- Market positioning (premium vs. value, target customer size)

**3. EVIDENCE OF IMPACT:**
- Additional case studies with quantified metrics (%, hectares, tCO2e, liters)
- Named vineyard/winery deployments (specific customer names)
- Academic papers or research validations (DOIs, university partnerships)
- Industry awards or certifications (SWNZ, HVE, organic certifications)
- Customer testimonials with specific results

**4. KEY CLIENTS:**
- Named clients (wineries, vineyards, cooperatives)
- Geographic markets served
- Notable customer references (premium brands, large producers)
- Customer concentration risk (% of revenue from top clients if disclosed)

**5. FINANCIAL SIGNALS (search web for):**
- Funding rounds (amounts, dates, lead investors)
- Revenue estimates or disclosed figures
- Growth indicators (customer count growth, ARR if SaaS)
- Key partnerships that indicate scale

**WINE INDUSTRY SPECIFIC SEARCHES:**
Search for "{company_name}" in combination with:
- "vineyard deployment" OR "winery customer" OR "viticulture"
- "funding raised" OR "series A B C" OR "investment round"
- "award winner" OR "innovation award" OR "wine industry"
- Major wine industry publications: Wines & Vines, Wine Business Monthly, Decanter

**RETURN JSON STRUCTURE:**
{{
  "team": {{
    "founders": ["name1 - background", "name2 - background"],
    "executives": ["CEO: name - background", "CTO: name - background"],
    "size": "X employees",
    "advisors": ["advisor1 - relevance"],
    "wine_experience": "Summary of team's wine/ag background"
  }},
  "competitors": {{
    "direct": [
      {{"name": "Competitor1", "description": "...", "vs_target": "How {company_name} differentiates"}}
    ],
    "differentiation": "Key competitive advantages of {company_name}",
    "market_position": "Target segment and positioning"
  }},
  "evidence_of_impact": {{
    "case_studies": [{{"client": "name", "metric": "30% water reduction", "source": "URL"}}],
    "academic_papers": ["DOI or title"],
    "awards": ["Award name (Year)"],
    "certifications": ["Certification name"]
  }},
  "key_clients": {{
    "named_clients": ["Client1", "Client2"],
    "geographies": ["Country1", "Country2"],
    "segments": ["Premium wineries", "Cooperatives", etc]
  }},
  "financial_signals": {{
    "funding_rounds": [{{"round": "Series A", "amount": 5000000, "date": "2023", "lead": "Investor"}}],
    "revenue_signals": "Any disclosed or estimated revenue",
    "growth_indicators": ["100 vineyard deployments", "50% YoY customer growth"]
  }}
}}

**IMPORTANT:**
- Only include information you can verify with sources
- Include source URLs for key facts
- Mark uncertain information as "estimated" or "unconfirmed"
- If information cannot be found, use null or empty arrays
"""


def build_verification_prompt(
    company_data: dict[str, Any],
    original_summary: str,
) -> str:
    """
    Build a verification prompt to validate research findings.
    
    This adds a quality control step to ensure accuracy.
    
    Args:
        company_data: Enriched company data from deep research
        original_summary: Original discovery summary for comparison
    
    Returns:
        Formatted verification prompt
    """
    company_name = company_data.get("company", "Unknown")
    
    # Extract key claims to verify
    claims_to_verify = []
    
    # Team claims
    team = company_data.get("team", {})
    if team.get("founders"):
        claims_to_verify.append(f"Founders: {team['founders']}")
    if team.get("size"):
        claims_to_verify.append(f"Team size: {team['size']}")
    
    # Evidence claims
    evidence = company_data.get("evidence_of_impact", {})
    for case_study in evidence.get("case_studies", [])[:3]:
        if isinstance(case_study, dict):
            claims_to_verify.append(f"Case study: {case_study.get('client', '')} - {case_study.get('metric', '')}")
        elif isinstance(case_study, str):
            claims_to_verify.append(f"Case study: {case_study}")
    
    # Financial claims
    financials = company_data.get("financial_signals", {}) or company_data.get("financial_enrichment", {})
    funding_rounds = financials.get("funding_rounds", [])
    for round_data in funding_rounds[:2]:
        if isinstance(round_data, dict):
            claims_to_verify.append(
                f"Funding: {round_data.get('round', 'Unknown')} - ${round_data.get('amount', 'N/A')}"
            )
    
    claims_text = "\n".join([f"- {claim}" for claim in claims_to_verify]) if claims_to_verify else "- No specific claims to verify"
    
    return f"""**VERIFICATION TASK for {company_name}**

Review the following research findings for accuracy and completeness.

**ORIGINAL DISCOVERY SUMMARY:**
{original_summary}

**KEY CLAIMS TO VERIFY:**
{claims_text}

**VERIFICATION CHECKLIST:**

1. ✓ **VINEYARD EVIDENCE:**
   - Is there at least ONE named vineyard/winery deployment?
   - Are the deployment claims specific (not generic "agricultural" claims)?
   - Can deployment be verified via web search?

2. ✓ **TEAM ACCURACY:**
   - Do the named founders/executives appear on LinkedIn or company website?
   - Is the team size plausible for the company stage?

3. ✓ **FINANCIAL PLAUSIBILITY:**
   - Are funding amounts and dates consistent with Crunchbase/press releases?
   - Do funding rounds match typical wine-tech company progression?

4. ✓ **COMPETITIVE POSITIONING:**
   - Are the named competitors actually in the same market segment?
   - Does the differentiation claim make sense?

5. ✓ **SOURCE QUALITY:**
   - Are sources from reputable publications?
   - Are there any red flags (dead links, outdated info, vendor-only sources)?

**OUTPUT VERIFICATION RESULT:**
{{
  "company": "{company_name}",
  "verification_status": "verified" | "partially_verified" | "needs_review",
  "confidence_adjustment": 0.0,  // Adjust confidence: -0.2 to +0.1
  "issues_found": ["List any issues"],
  "corrections": {{}},  // Any corrections to the data
  "missing_data": ["List critical missing info"],
  "recommendation": "accept" | "accept_with_caveats" | "reject" | "needs_more_research"
}}

Provide a brief explanation for your verification decision."""


def _normalize_segment_key(segment: str) -> str:
    """Normalize segment name to match landscape keys."""
    segment_lower = segment.lower()
    
    mappings = {
        "soil": "soil_health",
        "irrigation": "irrigation",
        "water": "irrigation",
        "pest": "ipm_pest",
        "ipm": "ipm_pest",
        "canopy": "canopy_robotics",
        "robot": "canopy_robotics",
        "carbon": "carbon_traceability",
        "trace": "carbon_traceability",
        "mrv": "carbon_traceability",
        "vineyard": "vineyard_management",
        "grape": "vineyard_management",
        "production": "winery_production",
        "vinification": "winery_production",
        "winery": "winery_production",
        "ferment": "winery_production",
        "packag": "packaging",
        "bottle": "packaging",
        "distribut": "distribution",
        "logistic": "distribution",
    }
    
    for key, value in mappings.items():
        if key in segment_lower:
            return value
    
    return "vineyard_management"  # Default fallback


# =============================================================================
# SWOT GENERATION PROMPT
# =============================================================================

def build_swot_prompt(company_data: dict[str, Any]) -> str:
    """
    Build a prompt to generate SWOT analysis from gathered data.
    
    Args:
        company_data: Enriched company data from deep research
    
    Returns:
        SWOT generation prompt (or None if data is insufficient)
    """
    company_name = company_data.get("company", "Unknown")
    
    # Gather relevant data points
    team = company_data.get("team", {})
    competitors = company_data.get("competitors", {})
    evidence = company_data.get("evidence_of_impact", {})
    financials = company_data.get("financial_enrichment", {}) or company_data.get("financial_signals", {})
    
    return f"""Generate a SWOT analysis for {company_name} based on the following research data.

**COMPANY:** {company_name}
**SUMMARY:** {company_data.get('summary', 'N/A')}

**TEAM DATA:**
{_format_dict(team)}

**COMPETITIVE DATA:**
{_format_dict(competitors)}

**EVIDENCE OF IMPACT:**
{_format_dict(evidence)}

**FINANCIAL DATA:**
{_format_dict(financials)}

**WINE INDUSTRY CONTEXT:**
- Technology adoption in vineyards is accelerating globally
- Sustainability/ESG requirements driving investment
- Labor shortages increasing automation demand
- Premium wine segment growing faster than value

**GENERATE SWOT (2-4 bullets per quadrant, wine-industry specific):**

{{
  "strengths": [
    // Based on: team expertise, proven deployments, unique technology, funding
  ],
  "weaknesses": [
    // Based on: financial transparency, geographic concentration, team gaps
  ],
  "opportunities": [
    // Based on: market trends, regulatory drivers, expansion potential
  ],
  "threats": [
    // Based on: competition, technology shifts, adoption barriers
  ]
}}

Make each bullet specific and actionable for an investment decision."""


def _format_dict(d: dict | None) -> str:
    """Format a dictionary for prompt inclusion."""
    if not d:
        return "No data available"
    
    import json
    try:
        return json.dumps(d, indent=2, default=str)[:2000]  # Limit size
    except Exception:
        return str(d)[:2000]


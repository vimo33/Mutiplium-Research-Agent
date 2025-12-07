"""
Discovery phase prompt templates.

Provides unified prompts for the initial company discovery phase across all providers.
Includes:
- System prompts with reasoning framework
- User prompts with turn budgets
- Few-shot examples for output quality
- Segment-specific search strategies
"""

from __future__ import annotations

import json
from typing import Any


# =============================================================================
# FEW-SHOT EXAMPLES (3-5 diverse examples improve output quality significantly)
# =============================================================================

DISCOVERY_FEW_SHOT_EXAMPLES = [
    {
        "company": "SupPlant",
        "summary": "Israeli AI-driven precision irrigation platform. Documented 30% water reduction at Golan Heights Winery (2023). "
                   "Deployed across 50+ Mediterranean vineyards using autonomous drip irrigation with plant sensors.",
        "kpi_alignment": [
            "Water Intensity: 30% reduction (4.2→2.9 m³/tonne grapes)",
            "Labor Productivity: 40% fewer manual irrigation adjustments",
            "Yield Stability: 15% reduction in yield variability across blocks"
        ],
        "sources": [
            "https://supplant.me/case-studies/wine",
            "https://doi.org/10.1016/j.agwat.2023.107892",
            "https://winesandvines.com/features/supplant-precision-irrigation-2023"
        ],
        "website": "https://supplant.me",
        "country": "Israel",
        "confidence_0to1": 0.88,
        "source_tier": "Tier 1"
    },
    {
        "company": "Biome Makers",
        "summary": "Spanish soil microbiome analytics company using DNA sequencing. Partnership with E&J Gallo for vineyard soil health. "
                   "Platform covers 12M+ acres globally with wine representing 30% of deployments.",
        "kpi_alignment": [
            "Soil Health Index: Quantified microbiome diversity scores",
            "Chemical Use Intensity: 20% reduction in synthetic inputs post-analysis",
            "Disease Incidence: Early detection of vine stress indicators"
        ],
        "sources": [
            "https://biomemakers.com/wine",
            "https://www.winebusiness.com/news/article/262847/",
            "https://agfundernews.com/biome-makers-series-b"
        ],
        "website": "https://biomemakers.com",
        "country": "Spain",
        "confidence_0to1": 0.85,
        "source_tier": "Tier 2"
    },
    {
        "company": "Suterra",
        "summary": "US-based pheromone mating disruption specialist. 500,000+ acres of vineyards protected globally. "
                   "Documented 95% reduction in grape moth damage at multiple Napa Valley wineries.",
        "kpi_alignment": [
            "Chemical Use Intensity: 60-80% reduction in insecticide applications",
            "Disease/Pest Incidence: 95% reduction in target pest populations",
            "Certification Status: Enables organic/biodynamic compliance"
        ],
        "sources": [
            "https://suterra.com/crops/grapes/",
            "https://journals.ashs.org/hortsci/view/journals/hortsci/55/8/article-p1157.xml",
            "https://www.napavalleyregister.com/suterra-organic-pest-control"
        ],
        "website": "https://suterra.com",
        "country": "United States",
        "confidence_0to1": 0.82,
        "source_tier": "Tier 1"
    },
    {
        "company": "Fruition Sciences",
        "summary": "California-based vine water stress monitoring using sap flow sensors. "
                   "Deployed at 200+ premium vineyards including Opus One, Ridge Vineyards. Real-time stress analytics.",
        "kpi_alignment": [
            "Water Intensity: 15-25% irrigation water savings",
            "Grape Maturity Index: Optimized harvest timing via stress curves",
            "Yield per Hectare: 10% yield improvement through precision watering"
        ],
        "sources": [
            "https://fruitionsciences.com/case-studies",
            "https://www.winesandvines.com/news/article/fruition-sciences-sap-flow",
            "https://wineindustryadvisor.com/2022/12/fruition-sciences"
        ],
        "website": "https://fruitionsciences.com",
        "country": "United States",
        "confidence_0to1": 0.80,
        "source_tier": "Tier 2"
    },
    {
        "company": "eProvenance",
        "summary": "French IoT temperature/humidity monitoring for wine logistics. Used by 50+ Bordeaux châteaux. "
                   "Tracking 10M+ bottles annually with blockchain-verified provenance.",
        "kpi_alignment": [
            "Temperature Excursion Rate: <0.5% excursions with real-time alerts",
            "Traceability Coverage: 100% lot-level tracking from cellar to consumer",
            "Breakage/Spoilage Rate: 40% reduction in quality claims"
        ],
        "sources": [
            "https://eprovenance.com/wine-monitoring",
            "https://www.thedrinksbusiness.com/eprovenance-blockchain-wine",
            "https://www.decanter.com/wine-news/eprovenance-temperature-monitoring"
        ],
        "website": "https://eprovenance.com",
        "country": "France",
        "confidence_0to1": 0.78,
        "source_tier": "Tier 2"
    }
]


# =============================================================================
# REASONING FRAMEWORK (Chain-of-Thought guidance)
# =============================================================================

REASONING_FRAMEWORK = """
**REASONING FRAMEWORK (apply step-by-step to EACH candidate company):**

Before adding a company to your output, reason through these criteria:

<reasoning_example>
Company: [Company Name]

Step 1 - VINEYARD EVIDENCE CHECK:
- Does this company have a named winery/vineyard deployment?
- Specific evidence found: [Named winery or "NONE FOUND"]
→ Decision: [INCLUDE / EXCLUDE]

Step 2 - KPI IMPACT ASSESSMENT (Score 1-5):
- Are the claimed impacts DIRECT (not indirect/implied)?
- Quantified metrics found: [List specific numbers]
- Score: [1-5] (5 = quantified direct impact, 1 = vague indirect claims)
→ Decision: [INCLUDE if ≥3 / EXCLUDE if <3]

Step 3 - SOURCE QUALITY EVALUATION:
- Tier 1 (academic, government): [List sources]
- Tier 2 (industry publications): [List sources]
- Tier 3 (vendor, blogs): [List sources]
- Best tier: [Tier 1/2/3]
→ Flag if only Tier 3 sources

Step 4 - CONFIDENCE SCORING:
- Vineyard evidence strength: [Strong/Medium/Weak]
- Source quality: [Tier 1/2/3]
- Metrics quantification: [Specific/Vague]
- Final confidence_0to1: [0.0-1.0]
</reasoning_example>

**CONFIDENCE SCORE GUIDE:**
- 0.85-1.0: Strong vineyard evidence + Tier 1/2 sources + quantified metrics
- 0.70-0.84: Good evidence, multiple sources, some quantification
- 0.55-0.69: Limited to Tier 2/3 sources OR vague metrics
- 0.40-0.54: Some vineyard connection but weak evidence
- Below 0.40: EXCLUDE - insufficient evidence
"""


# =============================================================================
# MANDATORY REQUIREMENTS
# =============================================================================

MANDATORY_REQUIREMENTS = """
**MANDATORY REQUIREMENTS (enforce strictly):**

1. ✓ VINEYARD EVIDENCE REQUIRED
   - Every company MUST cite at least ONE:
     • Named winery/vineyard deployment
     • Specific customer case study
     • Documented viticulture pilot/trial
   - Generic "agricultural" companies without wine evidence → EXCLUDE

2. ✗ NO INDIRECT IMPACTS
   - Reject claims marked: "(indirectly)", "implied", "potentially", "could lead to"
   - KPIs must show DIRECT, measurable impact
   - Example of BAD: "Could potentially reduce water usage" → EXCLUDE
   - Example of GOOD: "Reduced water usage 30% at Opus One (2023)" → INCLUDE

3. ⚠ SOURCE QUALITY FLAGGING
   - Companies with ONLY Tier 3 sources → confidence_0to1 < 0.60
   - Best practice: At least ONE Tier 1 or Tier 2 source per company

4. 📊 QUANTIFIED METRICS PREFERRED
   - Specific percentages (30% reduction)
   - Hectares/acres covered
   - tCO2e sequestered
   - Liters/m³ saved
   - Named customer counts
"""


# =============================================================================
# GEOGRAPHIC DIVERSITY
# =============================================================================

GEOGRAPHIC_DIVERSITY = """
**GEOGRAPHIC DIVERSITY TARGET (70%+ non-US):**

Prioritize searches in major wine tech regions with local language terms:

🇫🇷 FRANCE: Bordeaux, Champagne, Burgundy, Provence, Languedoc
   - French terms: "technologie viticole", "robot vigne", "précision irrigation"
   
🇮🇹 ITALY: Tuscany, Piedmont, Veneto, Sicily
   - Italian terms: "tecnologia vinicola", "robotica vigna", "irrigazione precisione"
   
🇪🇸 SPAIN: La Rioja, Catalonia, Ribera del Duero, Priorat
   - Spanish terms: "tecnología viñedo", "robótica viticultura", "riego inteligente"
   
🇦🇺 AUSTRALIA: Adelaide, Margaret River, Barossa Valley, Hunter Valley
🇨🇱 CHILE: Maipo Valley, Colchagua, Casablanca
🇦🇷 ARGENTINA: Mendoza, Salta, Patagonia
🇿🇦 SOUTH AFRICA: Stellenbosch, Paarl, Constantia
🇳🇿 NEW ZEALAND: Marlborough, Central Otago, Hawke's Bay
🇵🇹 PORTUGAL: Douro, Alentejo, Vinho Verde
🇩🇪 GERMANY: Mosel, Rheingau, Pfalz
"""


# =============================================================================
# WINE TRADE PUBLICATIONS
# =============================================================================

WINE_TRADE_PUBLICATIONS = """
**PRIORITY SOURCES (Wine Industry Publications):**

📰 Trade Media:
- Wines & Vines (US) - winesandvines.com
- Wine Business Monthly (US) - winebusiness.com
- The Drinks Business (UK) - thedrinksbusiness.com
- Meininger's Wine Business International (DE) - wine-business-international.com
- Decanter (UK) - decanter.com
- Wine Industry Advisor (US) - wineindustryadvisor.com
- Australian & New Zealand Grapegrower & Winemaker

📚 Academic Journals (Tier 1):
- OENO One (oeno-one.eu)
- American Journal of Enology and Viticulture (ajevonline.org)
- Australian Journal of Grape and Wine Research

🎓 Conferences & Events:
- Unified Wine & Grape Symposium
- VinExpo, Wine Vision, Prowein
- Wine Industry Technology Symposium
- VitEff (France)

🚀 VC/Accelerators:
- AgFunder wine-tech portfolio
- WineTech Network
- Astanor Ventures
- SVG Partners (agricultural tech)
"""


# =============================================================================
# SEGMENT-SPECIFIC SEARCH STRATEGIES
# =============================================================================

SEGMENT_SEARCH_STRATEGIES = {
    "Soil Health Technologies": {
        "strategy": (
            "• Search for: soil microbiome testing, soil carbon sequestration, regenerative agriculture tech\n"
            "• Target companies: soil testing labs, microbial inoculants, biochar producers, cover crop analytics\n"
            "• Geographic focus: France (Bordeaux), Spain, California, Australia (Adelaide)\n"
            "• Look for: vineyard case studies, ROC certifications, university partnerships\n"
            "• Key players: Biome Makers, Trace Genomics, Sound Agriculture"
        ),
        "queries": [
            "soil microbiome testing vineyard wine",
            "soil carbon sequestration technology viticulture",
            "regenerative agriculture vineyard startups",
            "soil health monitoring platform vineyard",
            "microbial inoculant wine grape soil",
            "cover crop analytics vineyard carbon"
        ]
    },
    "Precision Irrigation Systems": {
        "strategy": (
            "• Search for: smart irrigation, precision water management, soil moisture sensors, ET-based irrigation\n"
            "• Target companies: IoT irrigation platforms, drip system optimization, water stress monitoring\n"
            "• Geographic focus: Israel, Spain, California, Chile, Australia\n"
            "• Look for: water savings metrics (%), drought resilience data, named winery clients\n"
            "• Key players: SupPlant, Fruition Sciences, Tule Technologies, Ceres Imaging"
        ),
        "queries": [
            "smart irrigation technology vineyard",
            "precision water management wine grape",
            "soil moisture sensor vineyard irrigation",
            "AI irrigation optimization viticulture",
            "water stress monitoring wine grape sensors",
            "drip irrigation automation vineyard"
        ]
    },
    "Integrated Pest Management (IPM)": {
        "strategy": (
            "• Search for: biological pest control, pheromone monitoring, pesticide alternatives, disease prediction\n"
            "• Target companies: biocontrol producers, pest monitoring platforms, organic pest management\n"
            "• Geographic focus: France, Italy, Spain, New Zealand\n"
            "• Look for: pesticide reduction %, biodiversity impact, organic certifications\n"
            "• Key players: Suterra, Biobest, Koppert, Trapview"
        ),
        "queries": [
            "biological pest control vineyard wine",
            "IPM monitoring platform viticulture",
            "pheromone trap system wine grape moth",
            "disease prediction vineyard AI machine learning",
            "biocontrol solutions vineyard organic",
            "mating disruption grape pest"
        ]
    },
    "Canopy Management Solutions": {
        "strategy": (
            "• Search for: precision viticulture, robotic pruning, canopy sensing, vineyard drones, NDVI mapping\n"
            "• Target companies: ag robotics, drone/satellite imaging, pruning automation, leaf removal\n"
            "• Geographic focus: France, Germany, USA, Australia\n"
            "• Look for: yield optimization %, labor savings, disease prevention metrics\n"
            "• Key players: Naïo Technologies, Abundant Robotics, VineView, Ceres Imaging"
        ),
        "queries": [
            "vineyard robotics pruning automation",
            "precision viticulture canopy sensing satellite",
            "drone vineyard mapping NDVI wine",
            "robotic vineyard equipment pruning",
            "canopy management technology wine grape",
            "leaf removal automation vineyard"
        ]
    },
    "Carbon MRV & Traceability Platforms": {
        "strategy": (
            "• Search for: carbon accounting, MRV platforms, blockchain traceability, sustainability reporting\n"
            "• Target companies: carbon credit platforms, supply chain software, sustainability certification\n"
            "• Geographic focus: EU, California, Australia, South Africa\n"
            "• Look for: tons CO2 sequestered, verified carbon credits, traceability deployments\n"
            "• Key players: Regrow, Nori, eProvenance, Evigence"
        ),
        "queries": [
            "carbon accounting wine supply chain MRV",
            "MRV platform vineyard agriculture carbon",
            "blockchain traceability wine provenance",
            "carbon credits vineyard regenerative",
            "sustainability reporting winery ESG",
            "wine traceability QR NFC technology"
        ]
    },
    "Grape Production": {
        "strategy": (
            "• Search for: precision viticulture platforms, vineyard management systems, yield prediction\n"
            "• Target companies: farm management software, quality monitoring, harvest optimization\n"
            "• Geographic focus: France, Spain, Italy, California, Australia, Chile\n"
            "• Look for: yield improvements, quality metrics, named winery clients\n"
            "• Key players: Vintrace, eVineyard, Vinea, Croptracker"
        ),
        "queries": [
            "precision viticulture technology platform",
            "vineyard management software wine",
            "grape quality monitoring AI prediction",
            "harvest optimization wine technology",
            "yield prediction vineyard machine learning",
            "vineyard ERP system winery"
        ]
    },
    "Wine Production": {
        "strategy": (
            "• Search for: fermentation control, cellar automation, winemaking analytics, tank sensors\n"
            "• Target companies: in-tank monitoring, SCADA systems, wine QC platforms, LIMS\n"
            "• Geographic focus: France, Italy, USA, Australia, New Zealand\n"
            "• Look for: fermentation success rates, OEE improvements, quality consistency\n"
            "• Key players: Pulsarbox, TankIQ, Wine Spectroscopy, Parsec"
        ),
        "queries": [
            "fermentation monitoring winery IoT technology",
            "wine tank sensor real-time analytics",
            "cellar automation software winery",
            "winemaking analytics platform AI",
            "quality control wine production technology",
            "LIMS winery laboratory information"
        ]
    },
    "Packaging": {
        "strategy": (
            "• Search for: wine packaging sustainability, bottle filling technology, oxygen management\n"
            "• Target companies: lightweight glass, sustainable closures, packaging automation, QA vision\n"
            "• Geographic focus: EU (glass manufacturers), USA, Australia\n"
            "• Look for: weight reduction %, recycled content, OEE improvements, TPO control\n"
            "• Key players: O-I Glass, Amorim Cork, Nomacorc, Vetropack"
        ),
        "queries": [
            "wine packaging sustainability technology lightweight",
            "bottle filling technology winery oxygen control",
            "wine closure technology innovation cork screw cap",
            "lightweight glass wine bottle recycled",
            "sustainable wine packaging solutions circular",
            "packaging line OEE wine automation"
        ]
    },
    "Distribution": {
        "strategy": (
            "• Search for: wine logistics cold chain, temperature monitoring, DTC platforms, inventory management\n"
            "• Target companies: 3PL with wine focus, cold chain telemetry, wine e-commerce, WMS/TMS\n"
            "• Geographic focus: USA, EU, Australia\n"
            "• Look for: OTIF rates, temperature excursion reduction, delivery success metrics\n"
            "• Key players: Eurofins, eProvenance, ShipCompliant, VinoShipper"
        ),
        "queries": [
            "wine logistics cold chain technology monitoring",
            "temperature monitoring wine transport IoT",
            "wine inventory management software WMS",
            "DTC wine platform direct to consumer",
            "wine shipping logistics compliance",
            "cold chain telemetry beverage alcohol"
        ]
    },
}


# =============================================================================
# JSON OUTPUT FORMAT
# =============================================================================

JSON_OUTPUT_FORMAT = """
**OUTPUT FORMAT (JSON only, no markdown):**

Return your findings as a valid JSON object. Start with { and end with }. No markdown code blocks.

**REQUIRED FIELDS (for EVERY company):**
- "company": Unique company name (string)
- "summary": 2-3 sentences with specific metrics and named deployments (string)
- "kpi_alignment": List of 2-4 explicit KPI alignments with quantitative evidence (array of strings)
- "sources": 3-5 verified source URLs from your web searches (array of strings)
- "website": Official company website URL (string)
- "country": Headquarters country, e.g., "Israel", "Spain", "Australia" (string)
- "confidence_0to1": Your confidence score based on evidence quality (number 0.0-1.0)
- "source_tier": Best source tier found: "Tier 1", "Tier 2", or "Tier 3" (string)
"""


# =============================================================================
# PROMPT BUILDERS
# =============================================================================

def build_discovery_system_prompt(
    context: Any,
    segment_name: str,
    include_examples: bool = True,
    include_reasoning: bool = True,
) -> str:
    """
    Build a unified system prompt for company discovery.
    
    Args:
        context: AgentContext with thesis, value_chain, kpis
        segment_name: Name of the value chain segment being researched
        include_examples: Include few-shot examples (recommended)
        include_reasoning: Include chain-of-thought reasoning framework
    
    Returns:
        Formatted system prompt string
    """
    thesis = getattr(context, "thesis", "").strip()
    value_chain = getattr(context, "value_chain", [])
    kpis = getattr(context, "kpis", {})
    
    # Convert to JSON-safe format
    if isinstance(value_chain, list):
        value_chain = [v.get("raw", str(v)) if isinstance(v, dict) else str(v) for v in value_chain]
    
    # Build segment-specific search strategy
    segment_strategy = get_segment_search_strategies(segment_name)
    
    # Build examples section
    examples_section = ""
    if include_examples:
        # Select 2-3 relevant examples
        examples = DISCOVERY_FEW_SHOT_EXAMPLES[:3]
        examples_json = json.dumps({"segment": {"name": segment_name, "companies": examples}}, indent=2)
        examples_section = f"""
**EXAMPLE OUTPUT (follow this exact structure for {segment_name}):**
```
{examples_json}
```
"""
    
    # Build reasoning section
    reasoning_section = REASONING_FRAMEWORK if include_reasoning else ""
    
    return f"""You are a senior analyst for an **impact investment** fund specializing in wine industry technology.

**YOUR MISSION:** Identify 10 unique companies in the '{segment_name}' segment that generate measurable environmental/social impact in vineyards and wineries.

{reasoning_section}

{MANDATORY_REQUIREMENTS}

{GEOGRAPHIC_DIVERSITY}

{WINE_TRADE_PUBLICATIONS}

**SEARCH STRATEGY FOR '{segment_name}':**
{segment_strategy}

**INVESTMENT THESIS:**
{thesis}

**VALUE CHAIN CONTEXT:**
{json.dumps(value_chain, indent=2) if value_chain else "See segment-specific guidance above."}

**KPI FRAMEWORK:**
{json.dumps(kpis, indent=2) if isinstance(kpis, dict) else str(kpis)}

{JSON_OUTPUT_FORMAT}

{examples_section}

**CRITICAL:** Output ONLY valid JSON. Start with {{ and end with }}. No markdown, no explanations, no preamble."""


def build_discovery_user_prompt(
    segment_name: str,
    context: Any,
    max_turns: int = 20,
    target_companies: int = 10,
) -> str:
    """
    Build the user prompt to kick off discovery for a segment.
    
    Args:
        segment_name: Name of the segment to research
        context: AgentContext (used for any additional context)
        max_turns: Maximum number of turns/iterations
        target_companies: Target number of companies to find
    
    Returns:
        Formatted user prompt string
    """
    # Get optimized search queries
    queries = get_segment_search_queries(segment_name)
    queries_text = "\n".join([f'  • "{q}"' for q in queries])
    
    output_turn = max(max_turns - 2, 15)
    
    return f"""🎯 **MISSION:** Find EXACTLY {target_companies} unique companies in the '{segment_name}' segment.

**TURN BUDGET ({max_turns} turns maximum):**
- Turns 1-10: Discover companies using web searches with queries below
- Turns 11-15: Verify top candidates have vineyard-specific evidence
- Turns 16-{output_turn}: Finalize list and prepare JSON output
- **⚠️ Output by turn {output_turn}** even if you haven't reached {target_companies} companies

**OPTIMIZED SEARCH QUERIES (use these as starting points):**
{queries_text}

**SYSTEMATIC RESEARCH WORKFLOW:**

1. **DISCOVERY PHASE** (Turns 1-8)
   - Execute web searches using the queries above
   - Note company names and initial evidence
   - Cast a wide net across geographies

2. **VERIFICATION PHASE** (Turns 9-14)
   - For each promising company, verify vineyard/winery deployment evidence
   - Look for case studies, customer testimonials, impact metrics
   - Find company website and headquarters country
   - Assess source quality (Tier 1/2/3)

3. **SYNTHESIS PHASE** (Turns 15-{output_turn})
   - Apply reasoning framework to each company
   - Assign confidence scores based on evidence
   - Prepare final JSON output

**REQUIRED OUTPUT FIELDS (for EVERY company):**
- `company`: Unique company name
- `summary`: 2-3 sentences with specific metrics/impact data
- `kpi_alignment`: 2-4 explicit KPI alignments with quantitative evidence
- `sources`: 3-5 verified source URLs from your searches
- `website`: Official company website URL
- `country`: Headquarters country (e.g., 'Spain', 'Israel', 'Australia')
- `confidence_0to1`: Your confidence score (0.0-1.0) based on evidence quality
- `source_tier`: Best source tier ('Tier 1', 'Tier 2', or 'Tier 3')

**IF YOU FIND FEWER THAN {target_companies}:**
- Add geographic modifiers (Spain, France, Italy, Chile, Australia, California)
- Try alternative technology terms and synonyms
- Search wine trade publications directly
- Search startup accelerators (AgFunder, WineTech Network)

**BEGIN NOW.** Output valid JSON when you have {target_companies} verified companies or by turn {output_turn}."""


def get_segment_search_strategies(segment_name: str) -> str:
    """Get the detailed search strategy for a segment."""
    # Try exact match first
    if segment_name in SEGMENT_SEARCH_STRATEGIES:
        return SEGMENT_SEARCH_STRATEGIES[segment_name]["strategy"]
    
    # Try partial match
    segment_lower = segment_name.lower()
    for key, value in SEGMENT_SEARCH_STRATEGIES.items():
        if key.lower() in segment_lower or segment_lower in key.lower():
            return value["strategy"]
    
    # Fallback
    return (
        f"• Search for: {segment_name} technology vineyard wine\n"
        f"• Target companies: {segment_name} solutions for viticulture\n"
        "• Geographic focus: France, Spain, Italy, California, Australia, Chile\n"
        "• Look for: vineyard case studies, quantified metrics, named winery clients"
    )


def get_segment_search_queries(segment_name: str) -> list[str]:
    """Get optimized search queries for a segment."""
    # Try exact match first
    if segment_name in SEGMENT_SEARCH_STRATEGIES:
        return SEGMENT_SEARCH_STRATEGIES[segment_name]["queries"]
    
    # Try partial match
    segment_lower = segment_name.lower()
    for key, value in SEGMENT_SEARCH_STRATEGIES.items():
        if key.lower() in segment_lower or segment_lower in key.lower():
            return value["queries"]
    
    # Fallback queries
    return [
        f"{segment_name} vineyard technology",
        f"{segment_name} wine industry innovation",
        f"{segment_name} viticulture solution",
        f"{segment_name} winery technology startup",
    ]


"""Quantitative impact scoring system for investment analysis."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ImpactScore:
    """Comprehensive impact score for a company."""
    
    environmental: float  # 0-1 score
    social: float  # 0-1 score
    governance: float  # 0-1 score
    sdg_alignment: list[int]  # List of SDG numbers
    financial_viability: float  # 0-1 score
    overall_impact: float  # Weighted composite
    
    confidence: float  # 0-1, based on evidence quality
    tier_breakdown: dict[str, int]  # Count of Tier 1/2/3 sources
    
    # Detailed metrics
    carbon_reduction: float | None = None  # tCO2e/year
    water_savings: float | None = None  # liters/year
    pesticide_reduction: float | None = None  # percentage
    biodiversity_enhancement: bool | None = None
    certifications: list[str] | None = None
    
    # Financial metrics
    revenue_growth: float | None = None
    profitability: str | None = None  # "positive", "breakeven", "negative"
    funding_stage: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "environmental": round(self.environmental, 2),
            "social": round(self.social, 2),
            "governance": round(self.governance, 2),
            "sdg_alignment": self.sdg_alignment,
            "financial_viability": round(self.financial_viability, 2),
            "overall_impact": round(self.overall_impact, 2),
            "confidence": round(self.confidence, 2),
            "tier_breakdown": self.tier_breakdown,
            "carbon_reduction": self.carbon_reduction,
            "water_savings": self.water_savings,
            "pesticide_reduction": self.pesticide_reduction,
            "biodiversity_enhancement": self.biodiversity_enhancement,
            "certifications": self.certifications or [],
            "revenue_growth": self.revenue_growth,
            "profitability": self.profitability,
            "funding_stage": self.funding_stage,
        }


class ImpactScorer:
    """Calculate quantitative impact scores from company research data."""
    
    # Weights for overall impact score (total = 1.0)
    WEIGHT_ENVIRONMENTAL = 0.35
    WEIGHT_SOCIAL = 0.30
    WEIGHT_GOVERNANCE = 0.20
    WEIGHT_FINANCIAL = 0.15
    
    # Evidence tier weights
    TIER_1_WEIGHT = 1.0  # Peer-reviewed, regulatory
    TIER_2_WEIGHT = 0.7  # Reputable media, industry reports
    TIER_3_WEIGHT = 0.3  # Vendor materials, self-published
    
    def score_company(self, company_data: dict[str, Any]) -> ImpactScore:
        """
        Score a company based on research findings.
        
        Args:
            company_data: Dictionary containing:
                - kpi_alignment: List of KPI strings
                - sources: List of source URLs/citations
                - summary: Company description
                - certifications: Optional list of certifications
                - financial_data: Optional financial metrics
        """
        kpi_alignment = company_data.get("kpi_alignment", [])
        sources = company_data.get("sources", [])
        summary = company_data.get("summary", "")
        
        # Score each dimension
        env_score = self._score_environmental(kpi_alignment, summary)
        social_score = self._score_social(kpi_alignment, summary)
        gov_score = self._score_governance(kpi_alignment, summary)
        financial_score = self._score_financial(company_data)
        
        # Calculate confidence based on evidence tiers
        tier_breakdown, confidence = self._assess_evidence_quality(sources, kpi_alignment)
        
        # Extract SDG alignment
        sdg_list = self._extract_sdgs(company_data)
        
        # Calculate weighted overall score
        overall = (
            env_score * self.WEIGHT_ENVIRONMENTAL
            + social_score * self.WEIGHT_SOCIAL
            + gov_score * self.WEIGHT_GOVERNANCE
            + financial_score * self.WEIGHT_FINANCIAL
        )
        
        # Extract detailed metrics
        carbon_reduction = self._extract_metric(kpi_alignment, ["carbon", "co2", "emissions"])
        water_savings = self._extract_metric(kpi_alignment, ["water"])
        pesticide_reduction = self._extract_metric(kpi_alignment, ["pesticide", "chemical"])
        biodiversity = any(
            word in " ".join(kpi_alignment).lower() 
            for word in ["biodiversity", "beneficial insects", "native species"]
        )
        
        return ImpactScore(
            environmental=env_score,
            social=social_score,
            governance=gov_score,
            sdg_alignment=sdg_list,
            financial_viability=financial_score,
            overall_impact=overall,
            confidence=confidence,
            tier_breakdown=tier_breakdown,
            carbon_reduction=carbon_reduction,
            water_savings=water_savings,
            pesticide_reduction=pesticide_reduction,
            biodiversity_enhancement=biodiversity,
            certifications=company_data.get("certifications"),
        )
    
    def _score_environmental(self, kpi_alignment: list[str], summary: str) -> float:
        """Score environmental impact (0-1)."""
        env_keywords = {
            "soil carbon": 0.2,
            "carbon sequestration": 0.2,
            "water": 0.15,
            "emissions": 0.15,
            "pesticide reduction": 0.15,
            "biodiversity": 0.1,
            "renewable": 0.05,
        }
        
        text = " ".join(kpi_alignment).lower() + " " + summary.lower()
        score = 0.0
        
        for keyword, weight in env_keywords.items():
            if keyword in text:
                score += weight
        
        return min(score, 1.0)
    
    def _score_social(self, kpi_alignment: list[str], summary: str) -> float:
        """Score social impact (0-1)."""
        social_keywords = {
            "employment": 0.2,
            "community": 0.15,
            "health": 0.15,
            "education": 0.15,
            "gender": 0.1,
            "inclusion": 0.1,
            "fair trade": 0.15,
        }
        
        text = " ".join(kpi_alignment).lower() + " " + summary.lower()
        score = 0.0
        
        for keyword, weight in social_keywords.items():
            if keyword in text:
                score += weight
        
        return min(score, 1.0)
    
    def _score_governance(self, kpi_alignment: list[str], summary: str) -> float:
        """Score governance/transparency (0-1)."""
        gov_keywords = {
            "tier 1": 0.3,
            "peer-reviewed": 0.25,
            "certified": 0.15,
            "b corp": 0.15,
            "transparent": 0.1,
            "audit": 0.05,
        }
        
        text = " ".join(kpi_alignment).lower() + " " + summary.lower()
        score = 0.3  # Base score for having any documented evidence
        
        for keyword, weight in gov_keywords.items():
            if keyword in text:
                score += weight
        
        return min(score, 1.0)
    
    def _score_financial(self, company_data: dict[str, Any]) -> float:
        """Score financial viability (0-1)."""
        # This is a simplified heuristic
        # In production, integrate actual financial data
        
        summary = company_data.get("summary", "").lower()
        
        score = 0.5  # Base assumption
        
        # Positive indicators
        if any(word in summary for word in ["profitable", "revenue", "funded", "Series", "raised"]):
            score += 0.2
        if any(word in summary for word in ["growing", "scale", "expansion"]):
            score += 0.15
        if any(word in summary for word in ["deployed", "commercial", "customers"]):
            score += 0.15
        
        # Negative indicators
        if any(word in summary for word in ["pre-revenue", "pilot", "prototype"]):
            score -= 0.2
        
        return min(max(score, 0.0), 1.0)
    
    def _assess_evidence_quality(
        self, sources: list[str], kpi_alignment: list[str]
    ) -> tuple[dict[str, int], float]:
        """
        Assess evidence quality and calculate confidence score.
        
        Returns:
            - tier_breakdown: Count of Tier 1/2/3 sources
            - confidence: Overall confidence score (0-1)
        """
        tier_breakdown = {"tier_1": 0, "tier_2": 0, "tier_3": 0}
        
        # Check for tier markers in KPI alignment text
        text = " ".join(kpi_alignment).lower()
        
        # Tier 1 indicators
        tier1_markers = ["peer-reviewed", "university", "regulatory", "iso", "certified"]
        tier1_count = sum(1 for marker in tier1_markers if marker in text)
        
        # Tier 2 indicators
        tier2_markers = ["wine business", "industry", "cooperative", "study"]
        tier2_count = sum(1 for marker in tier2_markers if marker in text)
        
        # Assume rest are Tier 3
        total_sources = len(sources)
        tier3_count = max(0, total_sources - tier1_count - tier2_count)
        
        tier_breakdown["tier_1"] = tier1_count
        tier_breakdown["tier_2"] = tier2_count
        tier_breakdown["tier_3"] = tier3_count
        
        # Calculate confidence
        if total_sources == 0:
            confidence = 0.0
        else:
            weighted_sum = (
                tier1_count * self.TIER_1_WEIGHT
                + tier2_count * self.TIER_2_WEIGHT
                + tier3_count * self.TIER_3_WEIGHT
            )
            confidence = weighted_sum / total_sources
        
        return tier_breakdown, confidence
    
    def _extract_sdgs(self, company_data: dict[str, Any]) -> list[int]:
        """Extract SDG alignment numbers from company data."""
        # Check if SDG data is already available
        if "sdg_alignment" in company_data:
            return company_data["sdg_alignment"]
        
        # Otherwise, do keyword-based heuristic
        summary = company_data.get("summary", "").lower()
        kpi_text = " ".join(company_data.get("kpi_alignment", [])).lower()
        text = summary + " " + kpi_text
        
        sdgs = []
        if "hunger" in text or "food" in text or "agriculture" in text:
            sdgs.append(2)
        if "health" in text:
            sdgs.append(3)
        if "water" in text:
            sdgs.append(6)
        if "energy" in text:
            sdgs.append(7)
        if "employment" in text or "jobs" in text:
            sdgs.append(8)
        if "consumption" in text or "circular" in text:
            sdgs.append(12)
        if "climate" in text or "carbon" in text:
            sdgs.append(13)
        if "land" in text or "biodiversity" in text or "soil" in text:
            sdgs.append(15)
        
        return sorted(set(sdgs))
    
    def _extract_metric(self, kpi_alignment: list[str], keywords: list[str]) -> float | None:
        """Extract quantitative metric from KPI alignment text."""
        text = " ".join(kpi_alignment)
        
        for keyword in keywords:
            if keyword in text.lower():
                # Try to find percentage or number near the keyword
                import re
                # Look for patterns like "20%", "20 percent", "20-30%"
                pattern = r"(\d+(?:\.\d+)?)\s*(?:%|percent)"
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    return float(matches[0])
        
        return None


def calculate_pareto_frontier(
    companies: list[dict[str, Any]],
    impact_weight: float = 0.6,
    financial_weight: float = 0.4,
) -> list[dict[str, Any]]:
    """
    Calculate Pareto frontier for impact vs financial performance.
    
    Args:
        companies: List of company dicts with impact scores
        impact_weight: Weight for impact dimension (0-1)
        financial_weight: Weight for financial dimension (0-1)
    
    Returns:
        List of companies on the Pareto frontier (optimal trade-offs)
    """
    scorer = ImpactScorer()
    scored_companies = []
    
    for company in companies:
        score = scorer.score_company(company)
        scored_companies.append({
            **company,
            "impact_score": score.to_dict(),
            "composite_score": (
                score.overall_impact * impact_weight
                + score.financial_viability * financial_weight
            ),
        })
    
    # Sort by composite score
    scored_companies.sort(key=lambda x: x["composite_score"], reverse=True)
    
    # Find Pareto-optimal companies (not dominated on both dimensions)
    pareto_frontier = []
    for candidate in scored_companies:
        dominated = False
        for other in scored_companies:
            if (
                other["impact_score"]["overall_impact"] > candidate["impact_score"]["overall_impact"]
                and other["impact_score"]["financial_viability"] > candidate["impact_score"]["financial_viability"]
            ):
                dominated = True
                break
        
        if not dominated:
            pareto_frontier.append(candidate)
    
    return pareto_frontier


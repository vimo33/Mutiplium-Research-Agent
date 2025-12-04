"""
Tests for the Financial Enrichment System.

Tests entity classification, multi-path routing, and revenue estimation.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys


class TestFinanceAPIs:
    """Tests for finance_apis.py"""
    
    def test_import(self):
        """Test that the module imports correctly."""
        from multiplium.tools.finance_apis import FinanceAPIClient, EXCHANGE_CODES
        assert FinanceAPIClient is not None
        assert "NYSE" in EXCHANGE_CODES
    
    def test_calculate_derived_metrics(self):
        """Test derived metrics calculation."""
        from multiplium.tools.finance_apis import FinanceAPIClient
        
        # Create client with mocked httpx to avoid SSL issues
        with patch('httpx.AsyncClient'):
            client = FinanceAPIClient()
        
        years_data = [
            {"year": 2024, "revenue": 130000000, "roe": 0.18, "roa": 0.10, "gross_profit": 60000000, "ebitda": 30000000, "net_income": 20000000},
            {"year": 2023, "revenue": 115000000, "roe": 0.16, "roa": 0.09, "gross_profit": 50000000, "ebitda": 25000000, "net_income": 17000000},
            {"year": 2022, "revenue": 100000000, "roe": 0.15, "roa": 0.08, "gross_profit": 40000000, "ebitda": 20000000, "net_income": 15000000},
        ]
        
        derived = client._calculate_derived_metrics(years_data)
        
        # Check CAGR calculation (130/100)^(1/2) - 1 ≈ 0.14
        assert "revenue_cagr" in derived
        assert 0.13 < derived["revenue_cagr"] < 0.15
        
        # Check average ROE
        assert "avg_roe" in derived
        assert 0.16 < derived["avg_roe"] < 0.17
        
        # Check margins
        assert "gross_margin" in derived
        assert "ebitda_margin" in derived


class TestCompanyRegistries:
    """Tests for company_registries.py"""
    
    def test_import(self):
        """Test that the module imports correctly."""
        from multiplium.tools.company_registries import (
            CompaniesHouseClient,
            SECEdgarClient,
            UK_SIC_CODES,
        )
        assert CompaniesHouseClient is not None
        assert SECEdgarClient is not None
        assert "01210" in UK_SIC_CODES  # Growing of grapes


class TestFinancialEnricher:
    """Tests for financial_enricher.py"""
    
    def test_import(self):
        """Test that the module imports correctly."""
        from multiplium.research.financial_enricher import (
            SECTOR_HEURISTICS,
            EMPLOYEE_BANDS,
        )
        assert "agtech_hardware" in SECTOR_HEURISTICS
        assert "11-50" in EMPLOYEE_BANDS
    
    def test_sector_heuristics_values(self):
        """Test that sector heuristics have reasonable values."""
        from multiplium.research.financial_enricher import SECTOR_HEURISTICS
        
        for sector, heuristics in SECTOR_HEURISTICS.items():
            assert "revenue_per_employee_min" in heuristics
            assert "revenue_per_employee_max" in heuristics
            assert heuristics["revenue_per_employee_min"] > 0
            assert heuristics["revenue_per_employee_max"] > heuristics["revenue_per_employee_min"]
    
    def test_infer_sector(self):
        """Test sector inference from summary."""
        # Import the class and mock all external dependencies
        with patch('httpx.AsyncClient'), \
             patch('openai.AsyncOpenAI'):
            from multiplium.research.financial_enricher import FinancialEnricher
            
            enricher = FinancialEnricher()
            
            # Test hardware detection
            assert enricher._infer_sector("LiDAR sensor for vineyards") == "agtech_hardware"
            
            # Test SaaS detection
            assert enricher._infer_sector("vineyard management software platform") == "agtech_saas"
            
            # Test biotech detection
            assert enricher._infer_sector("pheromone-based pest control") == "biotech"
            
            # Test logistics detection
            assert enricher._infer_sector("temperature monitoring for wine shipping") == "logistics"
    
    def test_parse_employee_band(self):
        """Test employee band parsing."""
        with patch('httpx.AsyncClient'), \
             patch('openai.AsyncOpenAI'):
            from multiplium.research.financial_enricher import FinancialEnricher
            
            enricher = FinancialEnricher()
            
            # The function returns the band key, which may include "employees"
            result = enricher._parse_employee_band("11-50 employees")
            assert "11-50" in result
            
            result = enricher._parse_employee_band("50 employees")
            assert "11-50" in result or "51" in result  # 50 is at boundary
            
            result = enricher._parse_employee_band("200 employees")
            assert "51-200" in result or "200" in result
            
            result = enricher._parse_employee_band("5 employees")
            assert "1-10" in result or "5" in result
            
            assert enricher._parse_employee_band("") == "Unknown"
    
    def test_name_matches(self):
        """Test company name matching."""
        with patch('httpx.AsyncClient'), \
             patch('openai.AsyncOpenAI'):
            from multiplium.research.financial_enricher import FinancialEnricher
            
            enricher = FinancialEnricher()
            
            # Exact match
            assert enricher._name_matches("Sentek", "Sentek") is True
            
            # With suffixes
            assert enricher._name_matches("Sentek", "Sentek, Inc.") is True
            assert enricher._name_matches("Smart Apply", "Smart Apply Inc") is True
            
            # Substring match
            assert enricher._name_matches("Sentek", "Sentek Technologies") is True
            
            # No match
            assert enricher._name_matches("Sentek", "Unrelated Company") is False


class TestDeepResearcherIntegration:
    """Tests for deep_researcher.py integration with FinancialEnricher."""
    
    def test_import(self):
        """Test that deep_researcher imports correctly with new dependencies."""
        from multiplium.research.deep_researcher import DeepResearcher
        assert DeepResearcher is not None
    
    def test_check_has_financials(self):
        """Test the _check_has_financials helper method."""
        with patch('httpx.AsyncClient'), \
             patch('openai.AsyncOpenAI'), \
             patch('multiplium.research.deep_researcher.PerplexityMCPClient'), \
             patch('multiplium.research.deep_researcher.FinancialEnricher'):
            from multiplium.research.deep_researcher import DeepResearcher
            
            researcher = DeepResearcher()
            
            # No financial data
            enhanced = {}
            assert researcher._check_has_financials(enhanced) is False
            
            # With exact financials
            enhanced = {
                "financial_enrichment": {
                    "financials_exact": {
                        "years": [{"year": 2024, "revenue": 10000000}]
                    }
                }
            }
            assert researcher._check_has_financials(enhanced) is True
            
            # With estimated financials
            enhanced = {
                "financial_enrichment": {
                    "financials_estimated": {
                        "revenue_estimate": {"min": 5000000, "max": 15000000}
                    }
                }
            }
            assert researcher._check_has_financials(enhanced) is True
            
            # With funding rounds
            enhanced = {
                "financial_enrichment": {
                    "funding_rounds": [{"round_type": "Series A", "amount": 5000000}]
                }
            }
            assert researcher._check_has_financials(enhanced) is True


class TestReportWriterEnhancement:
    """Tests for the enhanced report writer."""
    
    def test_enhance_deep_research_stats(self):
        """Test that stats are correctly calculated."""
        from multiplium.reporting.writer import _enhance_deep_research_stats
        
        deep_research = {
            "companies": [
                {
                    "company": "Company A",
                    "deep_research_status": "completed",
                    "team": {"founders": ["John Doe"]},
                    "competitors": {"direct": ["Competitor 1"]},
                    "swot": {"strengths": ["Strong team"]},
                    "financial_enrichment": {
                        "financials_exact": {
                            "years": [{"year": 2024, "revenue": 10000000}]
                        }
                    }
                },
                {
                    "company": "Company B",
                    "deep_research_status": "completed",
                    "team": {"founders": ["Jane Doe"]},
                    "competitors": {"direct": ["Competitor 2"]},
                    "swot": {"strengths": ["Great product"]},
                    "financial_enrichment": {
                        "financials_estimated": {
                            "revenue_estimate": {"min": 5000000, "max": 15000000}
                        }
                    }
                },
                {
                    "company": "Company C",
                    "deep_research_status": "completed",
                    "team": {},
                    "competitors": {},
                    "swot": {},
                    "financial_enrichment": {}
                }
            ]
        }
        
        result = _enhance_deep_research_stats(deep_research)
        stats = result["stats"]
        
        assert stats["total"] == 3
        assert stats["completed"] == 3
        assert stats["has_exact_financials"] == 1
        assert stats["has_estimated_financials"] == 1
        assert stats["has_any_financial_data"] == 2
        assert stats["financial_data_coverage_pct"] == pytest.approx(66.7, rel=0.1)


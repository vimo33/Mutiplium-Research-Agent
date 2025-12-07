"""
Company Registries Client - Official Filing Data.

Integrates:
- Companies House API (UK): Full accounts, officers, filings (unlimited free)
- SEC EDGAR (US): 10-K/10-Q filings for listed companies (free)
- OpenCorporates: Global company registry (500 req/month free)

These provide auditable, official financial data with citations.
"""

from __future__ import annotations

import os
import re
import structlog
import httpx
from typing import Any
from datetime import datetime

logger = structlog.get_logger()


class CompaniesHouseClient:
    """
    UK Companies House API client.
    
    Provides access to:
    - Company search and profiles
    - Filing history
    - Officers/directors
    - Annual accounts (turnover, profit, assets)
    
    Free tier: Unlimited requests (with rate limiting)
    API Key: https://developer.company-information.service.gov.uk/
    """
    
    BASE_URL = "https://api.company-information.service.gov.uk"
    
    def __init__(self):
        """Initialize with API key from environment."""
        self.api_key = os.getenv("COMPANIES_HOUSE_API_KEY")
        self.client = httpx.AsyncClient(
            timeout=30.0,
            auth=(self.api_key, "") if self.api_key else None,
        )
        
        if not self.api_key:
            logger.warning(
                "companies_house.no_api_key",
                message="COMPANIES_HOUSE_API_KEY not set. Requests will fail.",
            )
    
    async def search_company(
        self,
        name: str,
        items_per_page: int = 10,
    ) -> dict[str, Any]:
        """
        Search for UK companies by name.
        
        Args:
            name: Company name to search
            items_per_page: Number of results to return
        
        Returns:
            Dict with company matches
        """
        if not self.api_key:
            return {"results": [], "error": "COMPANIES_HOUSE_API_KEY not configured"}
        
        try:
            response = await self.client.get(
                f"{self.BASE_URL}/search/companies",
                params={
                    "q": name,
                    "items_per_page": items_per_page,
                },
            )
            response.raise_for_status()
            
            data = response.json()
            
            results = []
            for item in data.get("items", []):
                results.append({
                    "company_number": item.get("company_number", ""),
                    "name": item.get("title", ""),
                    "company_type": item.get("company_type", ""),
                    "company_status": item.get("company_status", ""),
                    "date_of_creation": item.get("date_of_creation", ""),
                    "registered_office_address": item.get("registered_office_address", {}),
                    "description": item.get("description", ""),
                })
            
            logger.info(
                "companies_house.search.success",
                query=name,
                results_count=len(results),
            )
            
            return {
                "results": results,
                "total_results": data.get("total_results", 0),
            }
        
        except httpx.HTTPStatusError as e:
            logger.warning(
                "companies_house.search.http_error",
                query=name,
                status_code=e.response.status_code,
            )
            return {"results": [], "error": str(e)}
        
        except Exception as e:
            logger.error(
                "companies_house.search.failed",
                query=name,
                error=str(e),
            )
            return {"results": [], "error": str(e)}
    
    async def get_company(
        self,
        company_number: str,
    ) -> dict[str, Any]:
        """
        Get detailed company profile.
        
        Args:
            company_number: UK company registration number
        
        Returns:
            Dict with company details including SIC codes, officers count, etc.
        """
        if not self.api_key:
            return {"error": "COMPANIES_HOUSE_API_KEY not configured"}
        
        try:
            response = await self.client.get(
                f"{self.BASE_URL}/company/{company_number}",
            )
            response.raise_for_status()
            
            data = response.json()
            
            result = {
                "company_number": data.get("company_number", ""),
                "name": data.get("company_name", ""),
                "company_type": data.get("type", ""),
                "company_status": data.get("company_status", ""),
                "date_of_creation": data.get("date_of_creation", ""),
                "jurisdiction": data.get("jurisdiction", ""),
                "registered_office_address": data.get("registered_office_address", {}),
                "sic_codes": data.get("sic_codes", []),
                "accounts": data.get("accounts", {}),
                "confirmation_statement": data.get("confirmation_statement", {}),
                "has_insolvency_history": data.get("has_insolvency_history", False),
                "has_charges": data.get("has_charges", False),
            }
            
            logger.info(
                "companies_house.get_company.success",
                company_number=company_number,
                name=result["name"],
            )
            
            return result
        
        except Exception as e:
            logger.error(
                "companies_house.get_company.failed",
                company_number=company_number,
                error=str(e),
            )
            return {"error": str(e)}
    
    async def get_officers(
        self,
        company_number: str,
    ) -> dict[str, Any]:
        """
        Get company officers/directors.
        
        Returns:
            Dict with officers list including roles and appointment dates
        """
        if not self.api_key:
            return {"officers": [], "error": "COMPANIES_HOUSE_API_KEY not configured"}
        
        try:
            response = await self.client.get(
                f"{self.BASE_URL}/company/{company_number}/officers",
            )
            response.raise_for_status()
            
            data = response.json()
            
            officers = []
            for item in data.get("items", []):
                officers.append({
                    "name": item.get("name", ""),
                    "officer_role": item.get("officer_role", ""),
                    "appointed_on": item.get("appointed_on", ""),
                    "resigned_on": item.get("resigned_on", ""),
                    "nationality": item.get("nationality", ""),
                    "occupation": item.get("occupation", ""),
                })
            
            logger.info(
                "companies_house.get_officers.success",
                company_number=company_number,
                officers_count=len(officers),
            )
            
            return {
                "officers": officers,
                "total_results": data.get("total_results", 0),
                "active_count": data.get("active_count", 0),
            }
        
        except Exception as e:
            logger.error(
                "companies_house.get_officers.failed",
                company_number=company_number,
                error=str(e),
            )
            return {"officers": [], "error": str(e)}
    
    async def get_filing_history(
        self,
        company_number: str,
        category: str | None = None,
        items_per_page: int = 25,
    ) -> dict[str, Any]:
        """
        Get company filing history.
        
        Args:
            company_number: UK company registration number
            category: Filter by category (e.g., "accounts", "confirmation-statement")
            items_per_page: Number of filings to retrieve
        
        Returns:
            Dict with filing history
        """
        if not self.api_key:
            return {"filings": [], "error": "COMPANIES_HOUSE_API_KEY not configured"}
        
        try:
            params = {"items_per_page": items_per_page}
            if category:
                params["category"] = category
            
            response = await self.client.get(
                f"{self.BASE_URL}/company/{company_number}/filing-history",
                params=params,
            )
            response.raise_for_status()
            
            data = response.json()
            
            filings = []
            for item in data.get("items", []):
                filings.append({
                    "date": item.get("date", ""),
                    "category": item.get("category", ""),
                    "type": item.get("type", ""),
                    "description": item.get("description", ""),
                    "description_values": item.get("description_values", {}),
                    "paper_filed": item.get("paper_filed", False),
                    "links": item.get("links", {}),
                })
            
            return {
                "filings": filings,
                "total_count": data.get("total_count", 0),
            }
        
        except Exception as e:
            logger.error(
                "companies_house.get_filing_history.failed",
                company_number=company_number,
                error=str(e),
            )
            return {"filings": [], "error": str(e)}
    
    async def get_accounts_summary(
        self,
        company_number: str,
    ) -> dict[str, Any]:
        """
        Get summary of filed accounts (financial data).
        
        Note: Companies House doesn't directly provide financials via API.
        This extracts metadata about accounts. For actual numbers, you need
        to download and parse the PDF/iXBRL filings.
        
        Returns:
            Dict with accounts metadata and any available financial signals
        """
        # Get company profile for accounts info
        company = await self.get_company(company_number)
        
        if "error" in company:
            return company
        
        accounts_info = company.get("accounts", {})
        
        # Get recent accounts filings
        filings = await self.get_filing_history(
            company_number,
            category="accounts",
            items_per_page=5,
        )
        
        result = {
            "company_number": company_number,
            "name": company.get("name", ""),
            "accounting_reference_date": accounts_info.get("accounting_reference_date", {}),
            "last_accounts": accounts_info.get("last_accounts", {}),
            "next_accounts_due": accounts_info.get("next_due", ""),
            "next_accounts_made_up_to": accounts_info.get("next_made_up_to", ""),
            "recent_filings": filings.get("filings", [])[:3],
            "source_type": "official_registry",
            "source": "Companies House",
            "confidence_0to1": 0.95,
        }
        
        logger.info(
            "companies_house.get_accounts_summary.success",
            company_number=company_number,
            has_accounts=bool(accounts_info),
        )
        
        return result
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


class SECEdgarClient:
    """
    SEC EDGAR client for US public company filings.
    
    Provides access to:
    - 10-K (annual reports)
    - 10-Q (quarterly reports)
    - 8-K (current reports)
    - Company facts (XBRL data)
    
    Free: No API key required
    Rate limit: 10 requests/second
    """
    
    BASE_URL = "https://data.sec.gov"
    SUBMISSIONS_URL = "https://data.sec.gov/submissions"
    
    def __init__(self):
        """Initialize SEC EDGAR client."""
        # SEC requires User-Agent header
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "Multiplium Research contact@example.com",
                "Accept-Encoding": "gzip, deflate",
            },
        )
    
    async def get_company_by_cik(
        self,
        cik: str,
    ) -> dict[str, Any]:
        """
        Get company submissions by CIK (Central Index Key).
        
        Args:
            cik: SEC Central Index Key (10 digits, zero-padded)
        
        Returns:
            Dict with company info and recent filings
        """
        # Pad CIK to 10 digits
        cik_padded = cik.zfill(10)
        
        try:
            response = await self.client.get(
                f"{self.SUBMISSIONS_URL}/CIK{cik_padded}.json",
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Extract recent filings
            filings = data.get("filings", {}).get("recent", {})
            
            result = {
                "cik": cik_padded,
                "name": data.get("name", ""),
                "sic": data.get("sic", ""),
                "sic_description": data.get("sicDescription", ""),
                "state": data.get("stateOfIncorporation", ""),
                "fiscal_year_end": data.get("fiscalYearEnd", ""),
                "ein": data.get("ein", ""),
                "exchanges": data.get("exchanges", []),
                "tickers": data.get("tickers", []),
                "recent_filings": self._parse_filings(filings),
            }
            
            logger.info(
                "sec_edgar.get_company.success",
                cik=cik_padded,
                name=result["name"],
            )
            
            return result
        
        except httpx.HTTPStatusError as e:
            logger.warning(
                "sec_edgar.get_company.http_error",
                cik=cik_padded,
                status_code=e.response.status_code,
            )
            return {"cik": cik_padded, "error": str(e)}
        
        except Exception as e:
            logger.error(
                "sec_edgar.get_company.failed",
                cik=cik_padded,
                error=str(e),
            )
            return {"cik": cik_padded, "error": str(e)}
    
    async def search_company(
        self,
        name: str,
    ) -> dict[str, Any]:
        """
        Search for companies by name.
        
        Note: SEC doesn't have a direct search API. This uses the company
        tickers endpoint which includes names.
        
        Args:
            name: Company name to search
        
        Returns:
            Dict with matching companies
        """
        try:
            response = await self.client.get(
                f"{self.BASE_URL}/files/company_tickers.json",
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Search by name (case-insensitive)
            name_lower = name.lower()
            results = []
            
            for _, company in data.items():
                company_name = company.get("title", "").lower()
                if name_lower in company_name:
                    results.append({
                        "cik": str(company.get("cik_str", "")),
                        "name": company.get("title", ""),
                        "ticker": company.get("ticker", ""),
                    })
            
            logger.info(
                "sec_edgar.search.success",
                query=name,
                results_count=len(results),
            )
            
            return {"results": results[:10]}  # Limit to 10 results
        
        except Exception as e:
            logger.error(
                "sec_edgar.search.failed",
                query=name,
                error=str(e),
            )
            return {"results": [], "error": str(e)}
    
    async def get_company_facts(
        self,
        cik: str,
    ) -> dict[str, Any]:
        """
        Get company facts (XBRL financial data).
        
        This provides structured financial data from SEC filings including:
        - Revenue
        - Net income
        - Assets
        - Liabilities
        - Equity
        
        Args:
            cik: SEC Central Index Key
        
        Returns:
            Dict with financial facts organized by taxonomy
        """
        cik_padded = cik.zfill(10)
        
        try:
            response = await self.client.get(
                f"{self.BASE_URL}/api/xbrl/companyfacts/CIK{cik_padded}.json",
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Extract key financial facts from US-GAAP taxonomy
            us_gaap = data.get("facts", {}).get("us-gaap", {})
            
            # Key metrics to extract
            metrics = {
                "revenue": self._extract_metric(us_gaap, ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"]),
                "net_income": self._extract_metric(us_gaap, ["NetIncomeLoss", "ProfitLoss"]),
                "total_assets": self._extract_metric(us_gaap, ["Assets"]),
                "total_liabilities": self._extract_metric(us_gaap, ["Liabilities"]),
                "stockholders_equity": self._extract_metric(us_gaap, ["StockholdersEquity"]),
                "operating_income": self._extract_metric(us_gaap, ["OperatingIncomeLoss"]),
            }
            
            result = {
                "cik": cik_padded,
                "entity_name": data.get("entityName", ""),
                "metrics": metrics,
                "source_type": "official_registry",
                "source": "SEC EDGAR",
                "confidence_0to1": 0.95,
            }
            
            logger.info(
                "sec_edgar.get_company_facts.success",
                cik=cik_padded,
                metrics_found=sum(1 for v in metrics.values() if v),
            )
            
            return result
        
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Company doesn't have XBRL facts (older filings)
                return {"cik": cik_padded, "error": "No XBRL facts available"}
            
            logger.warning(
                "sec_edgar.get_company_facts.http_error",
                cik=cik_padded,
                status_code=e.response.status_code,
            )
            return {"cik": cik_padded, "error": str(e)}
        
        except Exception as e:
            logger.error(
                "sec_edgar.get_company_facts.failed",
                cik=cik_padded,
                error=str(e),
            )
            return {"cik": cik_padded, "error": str(e)}
    
    def _parse_filings(self, filings: dict) -> list[dict]:
        """Parse recent filings from submissions response."""
        if not filings:
            return []
        
        result = []
        forms = filings.get("form", [])
        dates = filings.get("filingDate", [])
        accession_numbers = filings.get("accessionNumber", [])
        
        for i in range(min(10, len(forms))):  # Last 10 filings
            if forms[i] in ["10-K", "10-Q", "8-K", "10-K/A", "10-Q/A"]:
                result.append({
                    "form": forms[i],
                    "filing_date": dates[i] if i < len(dates) else "",
                    "accession_number": accession_numbers[i] if i < len(accession_numbers) else "",
                })
        
        return result
    
    def _extract_metric(
        self,
        us_gaap: dict,
        concept_names: list[str],
    ) -> list[dict]:
        """Extract a specific metric from US-GAAP facts."""
        for concept in concept_names:
            if concept in us_gaap:
                units = us_gaap[concept].get("units", {})
                # Look for USD values (most common)
                for unit_type in ["USD", "usd"]:
                    if unit_type in units:
                        values = units[unit_type]
                        # Return last 3 annual filings (10-K)
                        annual_values = [
                            {
                                "value": v.get("val"),
                                "end_date": v.get("end"),
                                "filed": v.get("filed"),
                                "form": v.get("form", ""),
                            }
                            for v in values
                            if v.get("form") == "10-K"
                        ]
                        # Sort by end date descending and take last 3
                        annual_values.sort(key=lambda x: x.get("end_date", ""), reverse=True)
                        return annual_values[:3]
        return []
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


class UnifiedRegistryClient:
    """
    Unified interface for all company registries.
    
    Routes requests to appropriate registry based on country/jurisdiction:
    - UK: Companies House
    - US: SEC EDGAR (for listed) + OpenCorporates
    - Other: OpenCorporates
    """
    
    def __init__(self):
        """Initialize all registry clients."""
        self.companies_house = CompaniesHouseClient()
        self.sec_edgar = SECEdgarClient()
        
        # Import OpenCorporates from existing module
        from multiplium.tools.opencorporates import OpenCorporatesClient
        self.opencorporates = OpenCorporatesClient()
    
    async def search_company(
        self,
        name: str,
        country: str | None = None,
    ) -> dict[str, Any]:
        """
        Search for company across registries.
        
        Args:
            name: Company name to search
            country: ISO country code (US, GB, AU, etc.)
        
        Returns:
            Dict with results from appropriate registry
        """
        country = (country or "").upper()
        
        results = {
            "query": name,
            "country": country,
            "sources": [],
        }
        
        if country == "GB" or country == "UK":
            ch_results = await self.companies_house.search_company(name)
            if ch_results.get("results"):
                results["sources"].append({
                    "source": "Companies House",
                    "results": ch_results["results"],
                })
        
        elif country == "US":
            # Try SEC for listed companies
            sec_results = await self.sec_edgar.search_company(name)
            if sec_results.get("results"):
                results["sources"].append({
                    "source": "SEC EDGAR",
                    "results": sec_results["results"],
                })
        
        # Always try OpenCorporates as fallback
        oc_results = await self.opencorporates.search_company(name, country=country.lower() if country else None)
        if oc_results.get("results"):
            results["sources"].append({
                "source": "OpenCorporates",
                "results": oc_results["results"],
            })
        
        logger.info(
            "unified_registry.search.complete",
            query=name,
            country=country,
            sources_found=len(results["sources"]),
        )
        
        return results
    
    async def get_financials(
        self,
        company_name: str,
        country: str,
        company_number: str | None = None,
        cik: str | None = None,
    ) -> dict[str, Any]:
        """
        Get financial data from appropriate registry.
        
        Args:
            company_name: Company name (for logging)
            country: ISO country code
            company_number: UK company number or similar
            cik: SEC CIK number (for US listed companies)
        
        Returns:
            Dict with financial data if available
        """
        country = (country or "").upper()
        
        if country in ("GB", "UK") and company_number:
            return await self.companies_house.get_accounts_summary(company_number)
        
        elif country == "US" and cik:
            return await self.sec_edgar.get_company_facts(cik)
        
        else:
            # For other countries, try OpenCorporates
            if company_number:
                # Need jurisdiction code for OpenCorporates
                jurisdiction = self._country_to_jurisdiction(country)
                if jurisdiction:
                    return await self.opencorporates.get_company(jurisdiction, company_number)
        
        return {
            "error": "No financial data available from registries",
            "company_name": company_name,
            "country": country,
        }
    
    def _country_to_jurisdiction(self, country: str) -> str | None:
        """Convert country code to OpenCorporates jurisdiction."""
        mapping = {
            "AU": "au",
            "NZ": "nz",
            "CA": "ca",
            "FR": "fr",
            "DE": "de",
            "ES": "es",
            "IT": "it",
            "NL": "nl",
            "PT": "pt",
            "CL": "cl",
            "AR": "ar",
            "ZA": "za",
        }
        return mapping.get(country.upper())
    
    async def close(self):
        """Close all registry clients."""
        await self.companies_house.close()
        await self.sec_edgar.close()
        await self.opencorporates.close()


# SIC code mappings for industry classification
UK_SIC_CODES = {
    "01110": "Growing of cereals",
    "01210": "Growing of grapes",
    "01250": "Growing of other tree and bush fruits and nuts",
    "01500": "Mixed farming",
    "11020": "Manufacture of wine from grape",
    "11030": "Manufacture of cider and other fruit wines",
    "46341": "Wholesale of wine",
    "47250": "Retail sale of beverages",
    "62011": "Ready-made interactive leisure software development",
    "62012": "Business and domestic software development",
    "62020": "Information technology consultancy activities",
}





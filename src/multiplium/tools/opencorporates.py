"""
OpenCorporates API Client - Free Global Company Registry.

Free Tier: 500 requests/month
Coverage: 100+ jurisdictions globally
Data: Company registration, officers, addresses, status

API Docs: https://api.opencorporates.com/documentation/API-Reference
"""

from __future__ import annotations

import os
import structlog
import httpx
from typing import Any

logger = structlog.get_logger()


class OpenCorporatesClient:
    """
    Free global company registry API client.
    
    Provides access to company data from 100+ jurisdictions:
    - Company registration details
    - Officers/directors
    - Registered addresses
    - Company status (active, dissolved, etc.)
    
    Free tier: 500 requests/month
    Signup: https://opencorporates.com/api_accounts/new
    """
    
    BASE_URL = "https://api.opencorporates.com/v0.4"
    
    def __init__(self):
        """Initialize with API key from environment."""
        self.api_key = os.getenv("OPENCORPORATES_API_KEY")
        self.client = httpx.AsyncClient(timeout=30.0)
        
        if not self.api_key:
            logger.warning(
                "opencorporates.no_api_key",
                message="OPENCORPORATES_API_KEY not set. Requests will be rate-limited to 50/month.",
            )
    
    async def search_company(
        self,
        name: str,
        jurisdiction: str | None = None,
        country: str | None = None,
    ) -> dict[str, Any]:
        """
        Search for company by name.
        
        Args:
            name: Company name to search
            jurisdiction: Jurisdiction code (e.g., "us_ca" for California)
            country: Country code (e.g., "us", "gb", "fr")
        
        Returns:
            Dict with company matches:
            {
                "results": [
                    {
                        "name": "...",
                        "company_number": "...",
                        "jurisdiction_code": "...",
                        "incorporation_date": "...",
                        "company_type": "...",
                        "registered_address": "...",
                        "current_status": "Active"
                    }
                ],
                "total_count": 10
            }
        """
        params: dict[str, Any] = {
            "q": name,
        }
        
        if self.api_key:
            params["api_token"] = self.api_key
        
        if jurisdiction:
            params["jurisdiction_code"] = jurisdiction
        elif country:
            # If only country provided, search across all jurisdictions in that country
            params["country_code"] = country
        
        try:
            response = await self.client.get(
                f"{self.BASE_URL}/companies/search",
                params=params,
            )
            response.raise_for_status()
            
            data = response.json()
            companies = data.get("results", {}).get("companies", [])
            total_count = data.get("results", {}).get("total_count", 0)
            
            # Parse company data
            results = []
            for company_item in companies:
                company_data = company_item.get("company", {})
                results.append({
                    "name": company_data.get("name", ""),
                    "company_number": company_data.get("company_number", ""),
                    "jurisdiction_code": company_data.get("jurisdiction_code", ""),
                    "incorporation_date": company_data.get("incorporation_date", ""),
                    "company_type": company_data.get("company_type", ""),
                    "registered_address": company_data.get("registered_address_in_full", ""),
                    "current_status": company_data.get("current_status", ""),
                    "opencorporates_url": company_data.get("opencorporates_url", ""),
                })
            
            logger.info(
                "opencorporates.search.success",
                query=name,
                results_count=len(results),
                total_count=total_count,
            )
            
            return {
                "results": results,
                "total_count": total_count,
            }
        
        except httpx.HTTPStatusError as e:
            logger.warning(
                "opencorporates.search.http_error",
                query=name,
                status_code=e.response.status_code,
                error=str(e),
            )
            return {"results": [], "total_count": 0, "error": str(e)}
        
        except Exception as e:
            logger.error(
                "opencorporates.search.failed",
                query=name,
                error=str(e),
            )
            return {"results": [], "total_count": 0, "error": str(e)}
    
    async def get_company(
        self,
        jurisdiction_code: str,
        company_number: str,
    ) -> dict[str, Any]:
        """
        Get detailed company information.
        
        Args:
            jurisdiction_code: Jurisdiction code (e.g., "us_ca")
            company_number: Company registration number
        
        Returns:
            Dict with detailed company data including officers
        """
        params = {}
        if self.api_key:
            params["api_token"] = self.api_key
        
        try:
            response = await self.client.get(
                f"{self.BASE_URL}/companies/{jurisdiction_code}/{company_number}",
                params=params,
            )
            response.raise_for_status()
            
            data = response.json()
            company = data.get("results", {}).get("company", {})
            
            # Get officers if available
            officers_data = await self.get_company_officers(jurisdiction_code, company_number)
            
            result = {
                "name": company.get("name", ""),
                "company_number": company.get("company_number", ""),
                "jurisdiction_code": company.get("jurisdiction_code", ""),
                "incorporation_date": company.get("incorporation_date", ""),
                "company_type": company.get("company_type", ""),
                "registered_address": company.get("registered_address_in_full", ""),
                "current_status": company.get("current_status", ""),
                "industry_codes": company.get("industry_codes", []),
                "officers": officers_data.get("officers", []),
                "opencorporates_url": company.get("opencorporates_url", ""),
            }
            
            logger.info(
                "opencorporates.get_company.success",
                company=result["name"],
                officers_count=len(result["officers"]),
            )
            
            return result
        
        except httpx.HTTPStatusError as e:
            logger.warning(
                "opencorporates.get_company.http_error",
                jurisdiction=jurisdiction_code,
                company_number=company_number,
                status_code=e.response.status_code,
                error=str(e),
            )
            return {"error": str(e)}
        
        except Exception as e:
            logger.error(
                "opencorporates.get_company.failed",
                jurisdiction=jurisdiction_code,
                company_number=company_number,
                error=str(e),
            )
            return {"error": str(e)}
    
    async def get_company_officers(
        self,
        jurisdiction_code: str,
        company_number: str,
    ) -> dict[str, Any]:
        """
        Get company officers/directors.
        
        Returns:
            Dict with officers list:
            {
                "officers": [
                    {
                        "name": "...",
                        "position": "Director",
                        "start_date": "...",
                        "end_date": "...",
                    }
                ]
            }
        """
        params = {}
        if self.api_key:
            params["api_token"] = self.api_key
        
        try:
            response = await self.client.get(
                f"{self.BASE_URL}/companies/{jurisdiction_code}/{company_number}/officers",
                params=params,
            )
            response.raise_for_status()
            
            data = response.json()
            officers_list = data.get("results", {}).get("officers", [])
            
            officers = []
            for officer_item in officers_list:
                officer_data = officer_item.get("officer", {})
                officers.append({
                    "name": officer_data.get("name", ""),
                    "position": officer_data.get("position", ""),
                    "start_date": officer_data.get("start_date", ""),
                    "end_date": officer_data.get("end_date", ""),
                    "nationality": officer_data.get("nationality", ""),
                    "occupation": officer_data.get("occupation", ""),
                })
            
            return {"officers": officers}
        
        except Exception as e:
            logger.warning(
                "opencorporates.get_officers.failed",
                jurisdiction=jurisdiction_code,
                company_number=company_number,
                error=str(e),
            )
            return {"officers": []}
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# Example usage and jurisdiction codes
JURISDICTION_EXAMPLES = {
    "United States": "us",  # Then specific state: us_ca, us_ny, us_tx, etc.
    "United Kingdom": "gb",
    "France": "fr",
    "Spain": "es",
    "Italy": "it",
    "Germany": "de",
    "Netherlands": "nl",
    "Australia": "au",
    "New Zealand": "nz",
    "Chile": "cl",
    "Argentina": "ar",
    "South Africa": "za",
    "Portugal": "pt",
}


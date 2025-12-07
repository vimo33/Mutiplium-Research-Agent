"""
Finance APIs Client - Financial Data for Listed Companies.

Integrates:
- Financial Modeling Prep (FMP): Income statements, balance sheets, ratios
- Alpha Vantage: Stock quotes, fundamentals (500 req/day free)

Both have free tiers suitable for our wine/agtech company research.
"""

from __future__ import annotations

import os
import structlog
import httpx
from typing import Any
from datetime import datetime

logger = structlog.get_logger()


class FinanceAPIClient:
    """
    Unified client for financial data APIs.
    
    Provides access to:
    - Company financials (revenue, EBITDA, net income)
    - Balance sheet data (assets, equity, debt)
    - Key ratios and derived metrics
    - Ticker lookup by company name
    
    Free tiers:
    - FMP: 250 requests/day
    - Alpha Vantage: 500 requests/day
    """
    
    FMP_BASE_URL = "https://financialmodelingprep.com/api/v3"
    ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"
    
    def __init__(self):
        """Initialize with API keys from environment."""
        self.fmp_api_key = os.getenv("FMP_API_KEY")
        self.alpha_vantage_api_key = os.getenv("ALPHAVANTAGE_API_KEY", "demo")
        self.client = httpx.AsyncClient(timeout=30.0)
        
        if not self.fmp_api_key:
            logger.warning(
                "finance_apis.no_fmp_key",
                message="FMP_API_KEY not set. FMP requests will fail.",
            )
    
    async def search_ticker(
        self,
        company_name: str,
        exchange: str | None = None,
    ) -> dict[str, Any]:
        """
        Search for stock ticker by company name.
        
        Args:
            company_name: Company name to search
            exchange: Optional exchange filter (NYSE, NASDAQ, etc.)
        
        Returns:
            Dict with ticker matches:
            {
                "results": [
                    {
                        "symbol": "AAPL",
                        "name": "Apple Inc.",
                        "exchange": "NASDAQ",
                        "exchange_short": "NASDAQ"
                    }
                ]
            }
        """
        if not self.fmp_api_key:
            return {"results": [], "error": "FMP_API_KEY not configured"}
        
        try:
            response = await self.client.get(
                f"{self.FMP_BASE_URL}/search",
                params={
                    "query": company_name,
                    "apikey": self.fmp_api_key,
                    "limit": 10,
                },
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Filter by exchange if specified
            if exchange:
                data = [d for d in data if exchange.upper() in d.get("exchangeShortName", "").upper()]
            
            results = [
                {
                    "symbol": item.get("symbol", ""),
                    "name": item.get("name", ""),
                    "exchange": item.get("stockExchange", ""),
                    "exchange_short": item.get("exchangeShortName", ""),
                    "currency": item.get("currency", "USD"),
                }
                for item in data
            ]
            
            logger.info(
                "finance_apis.ticker_search.success",
                query=company_name,
                results_count=len(results),
            )
            
            return {"results": results}
        
        except httpx.HTTPStatusError as e:
            logger.warning(
                "finance_apis.ticker_search.http_error",
                query=company_name,
                status_code=e.response.status_code,
            )
            return {"results": [], "error": str(e)}
        
        except Exception as e:
            logger.error(
                "finance_apis.ticker_search.failed",
                query=company_name,
                error=str(e),
            )
            return {"results": [], "error": str(e)}
    
    async def get_income_statement(
        self,
        symbol: str,
        period: str = "annual",
        limit: int = 5,
    ) -> dict[str, Any]:
        """
        Get income statement data from FMP.
        
        Args:
            symbol: Stock ticker symbol
            period: "annual" or "quarter"
            limit: Number of periods to retrieve
        
        Returns:
            Dict with income statement data:
            {
                "symbol": "AAPL",
                "currency": "USD",
                "years": [
                    {
                        "year": 2024,
                        "date": "2024-09-28",
                        "revenue": 391035000000,
                        "gross_profit": 180683000000,
                        "operating_income": 123216000000,
                        "ebitda": 137352000000,
                        "net_income": 93736000000,
                        "eps": 6.11
                    }
                ]
            }
        """
        if not self.fmp_api_key:
            return {"error": "FMP_API_KEY not configured"}
        
        try:
            response = await self.client.get(
                f"{self.FMP_BASE_URL}/income-statement/{symbol}",
                params={
                    "period": period,
                    "limit": limit,
                    "apikey": self.fmp_api_key,
                },
            )
            response.raise_for_status()
            
            data = response.json()
            
            if not data:
                return {"symbol": symbol, "years": [], "error": "No data found"}
            
            years = []
            for item in data:
                years.append({
                    "year": int(item.get("calendarYear", 0)),
                    "date": item.get("date", ""),
                    "revenue": item.get("revenue", 0),
                    "gross_profit": item.get("grossProfit", 0),
                    "operating_income": item.get("operatingIncome", 0),
                    "ebitda": item.get("ebitda", 0),
                    "net_income": item.get("netIncome", 0),
                    "eps": item.get("eps", 0),
                })
            
            logger.info(
                "finance_apis.income_statement.success",
                symbol=symbol,
                years_count=len(years),
            )
            
            return {
                "symbol": symbol,
                "currency": data[0].get("reportedCurrency", "USD") if data else "USD",
                "years": years,
            }
        
        except httpx.HTTPStatusError as e:
            logger.warning(
                "finance_apis.income_statement.http_error",
                symbol=symbol,
                status_code=e.response.status_code,
            )
            return {"symbol": symbol, "years": [], "error": str(e)}
        
        except Exception as e:
            logger.error(
                "finance_apis.income_statement.failed",
                symbol=symbol,
                error=str(e),
            )
            return {"symbol": symbol, "years": [], "error": str(e)}
    
    async def get_balance_sheet(
        self,
        symbol: str,
        period: str = "annual",
        limit: int = 5,
    ) -> dict[str, Any]:
        """
        Get balance sheet data from FMP.
        
        Args:
            symbol: Stock ticker symbol
            period: "annual" or "quarter"
            limit: Number of periods to retrieve
        
        Returns:
            Dict with balance sheet data
        """
        if not self.fmp_api_key:
            return {"error": "FMP_API_KEY not configured"}
        
        try:
            response = await self.client.get(
                f"{self.FMP_BASE_URL}/balance-sheet-statement/{symbol}",
                params={
                    "period": period,
                    "limit": limit,
                    "apikey": self.fmp_api_key,
                },
            )
            response.raise_for_status()
            
            data = response.json()
            
            if not data:
                return {"symbol": symbol, "years": [], "error": "No data found"}
            
            years = []
            for item in data:
                years.append({
                    "year": int(item.get("calendarYear", 0)),
                    "date": item.get("date", ""),
                    "total_assets": item.get("totalAssets", 0),
                    "total_liabilities": item.get("totalLiabilities", 0),
                    "total_equity": item.get("totalStockholdersEquity", 0),
                    "total_debt": item.get("totalDebt", 0),
                    "cash": item.get("cashAndCashEquivalents", 0),
                    "net_debt": item.get("netDebt", 0),
                })
            
            logger.info(
                "finance_apis.balance_sheet.success",
                symbol=symbol,
                years_count=len(years),
            )
            
            return {
                "symbol": symbol,
                "currency": data[0].get("reportedCurrency", "USD") if data else "USD",
                "years": years,
            }
        
        except Exception as e:
            logger.error(
                "finance_apis.balance_sheet.failed",
                symbol=symbol,
                error=str(e),
            )
            return {"symbol": symbol, "years": [], "error": str(e)}
    
    async def get_key_metrics(
        self,
        symbol: str,
        period: str = "annual",
        limit: int = 5,
    ) -> dict[str, Any]:
        """
        Get key financial metrics and ratios from FMP.
        
        Returns metrics like:
        - ROE, ROA, ROIC
        - P/E, P/S, EV/EBITDA
        - Debt/Equity, Current Ratio
        - Revenue growth, earnings growth
        """
        if not self.fmp_api_key:
            return {"error": "FMP_API_KEY not configured"}
        
        try:
            response = await self.client.get(
                f"{self.FMP_BASE_URL}/key-metrics/{symbol}",
                params={
                    "period": period,
                    "limit": limit,
                    "apikey": self.fmp_api_key,
                },
            )
            response.raise_for_status()
            
            data = response.json()
            
            if not data:
                return {"symbol": symbol, "metrics": [], "error": "No data found"}
            
            metrics = []
            for item in data:
                metrics.append({
                    "year": int(item.get("calendarYear", 0)),
                    "date": item.get("date", ""),
                    "market_cap": item.get("marketCap", 0),
                    "enterprise_value": item.get("enterpriseValue", 0),
                    "pe_ratio": item.get("peRatio", 0),
                    "ev_to_ebitda": item.get("enterpriseValueOverEBITDA", 0),
                    "roe": item.get("roe", 0),
                    "roa": item.get("returnOnTangibleAssets", 0),
                    "roic": item.get("roic", 0),
                    "revenue_per_share": item.get("revenuePerShare", 0),
                    "debt_to_equity": item.get("debtToEquity", 0),
                    "current_ratio": item.get("currentRatio", 0),
                })
            
            logger.info(
                "finance_apis.key_metrics.success",
                symbol=symbol,
                metrics_count=len(metrics),
            )
            
            return {
                "symbol": symbol,
                "metrics": metrics,
            }
        
        except Exception as e:
            logger.error(
                "finance_apis.key_metrics.failed",
                symbol=symbol,
                error=str(e),
            )
            return {"symbol": symbol, "metrics": [], "error": str(e)}
    
    async def get_company_profile(
        self,
        symbol: str,
    ) -> dict[str, Any]:
        """
        Get company profile from FMP.
        
        Returns:
            Company overview including sector, industry, employees, etc.
        """
        if not self.fmp_api_key:
            return {"error": "FMP_API_KEY not configured"}
        
        try:
            response = await self.client.get(
                f"{self.FMP_BASE_URL}/profile/{symbol}",
                params={"apikey": self.fmp_api_key},
            )
            response.raise_for_status()
            
            data = response.json()
            
            if not data:
                return {"symbol": symbol, "error": "No data found"}
            
            profile = data[0]
            
            result = {
                "symbol": symbol,
                "name": profile.get("companyName", ""),
                "exchange": profile.get("exchangeShortName", ""),
                "currency": profile.get("currency", "USD"),
                "market_cap": profile.get("mktCap", 0),
                "sector": profile.get("sector", ""),
                "industry": profile.get("industry", ""),
                "employees": profile.get("fullTimeEmployees", 0),
                "country": profile.get("country", ""),
                "website": profile.get("website", ""),
                "description": profile.get("description", ""),
                "ceo": profile.get("ceo", ""),
                "ipo_date": profile.get("ipoDate", ""),
            }
            
            logger.info(
                "finance_apis.company_profile.success",
                symbol=symbol,
                name=result["name"],
            )
            
            return result
        
        except Exception as e:
            logger.error(
                "finance_apis.company_profile.failed",
                symbol=symbol,
                error=str(e),
            )
            return {"symbol": symbol, "error": str(e)}
    
    async def get_full_financials(
        self,
        symbol: str,
        years: int = 3,
    ) -> dict[str, Any]:
        """
        Get comprehensive financial data for a listed company.
        
        Combines income statement, balance sheet, and key metrics
        into a unified format suitable for investment analysis.
        
        Args:
            symbol: Stock ticker symbol
            years: Number of years of data to retrieve
        
        Returns:
            Dict with comprehensive financial data:
            {
                "symbol": "...",
                "currency": "USD",
                "profile": {...},
                "years": [
                    {
                        "year": 2024,
                        "revenue": ...,
                        "ebitda": ...,
                        "net_income": ...,
                        "total_assets": ...,
                        "roe": ...,
                        ...
                    }
                ],
                "derived": {
                    "revenue_cagr_3y": 0.12,
                    "avg_roe_3y": 0.18,
                    ...
                }
            }
        """
        # Fetch all data in parallel
        import asyncio
        
        profile_task = self.get_company_profile(symbol)
        income_task = self.get_income_statement(symbol, limit=years)
        balance_task = self.get_balance_sheet(symbol, limit=years)
        metrics_task = self.get_key_metrics(symbol, limit=years)
        
        profile, income, balance, metrics = await asyncio.gather(
            profile_task, income_task, balance_task, metrics_task
        )
        
        # Check for errors
        if "error" in profile and not profile.get("name"):
            return {"symbol": symbol, "error": profile.get("error", "Failed to fetch profile")}
        
        # Merge data by year
        years_data = {}
        
        for item in income.get("years", []):
            year = item["year"]
            years_data[year] = {
                "year": year,
                "revenue": item.get("revenue", 0),
                "gross_profit": item.get("gross_profit", 0),
                "operating_income": item.get("operating_income", 0),
                "ebitda": item.get("ebitda", 0),
                "net_income": item.get("net_income", 0),
                "eps": item.get("eps", 0),
            }
        
        for item in balance.get("years", []):
            year = item["year"]
            if year in years_data:
                years_data[year].update({
                    "total_assets": item.get("total_assets", 0),
                    "total_equity": item.get("total_equity", 0),
                    "total_debt": item.get("total_debt", 0),
                    "cash": item.get("cash", 0),
                    "net_debt": item.get("net_debt", 0),
                })
        
        for item in metrics.get("metrics", []):
            year = item["year"]
            if year in years_data:
                years_data[year].update({
                    "market_cap": item.get("market_cap", 0),
                    "enterprise_value": item.get("enterprise_value", 0),
                    "pe_ratio": item.get("pe_ratio", 0),
                    "ev_to_ebitda": item.get("ev_to_ebitda", 0),
                    "roe": item.get("roe", 0),
                    "roa": item.get("roa", 0),
                    "roic": item.get("roic", 0),
                })
        
        # Sort years descending
        sorted_years = sorted(years_data.values(), key=lambda x: x["year"], reverse=True)
        
        # Calculate derived metrics
        derived = self._calculate_derived_metrics(sorted_years)
        
        result = {
            "symbol": symbol,
            "currency": income.get("currency", "USD"),
            "profile": {
                "name": profile.get("name", ""),
                "sector": profile.get("sector", ""),
                "industry": profile.get("industry", ""),
                "employees": profile.get("employees", 0),
                "country": profile.get("country", ""),
                "market_cap": profile.get("market_cap", 0),
            },
            "years": sorted_years,
            "derived": derived,
            "source_type": "public_api",
            "source": "Financial Modeling Prep",
            "confidence_0to1": 0.95,  # High confidence for public API data
        }
        
        logger.info(
            "finance_apis.full_financials.success",
            symbol=symbol,
            years_count=len(sorted_years),
            has_derived=bool(derived),
        )
        
        return result
    
    def _calculate_derived_metrics(self, years_data: list[dict]) -> dict[str, Any]:
        """Calculate derived metrics from raw financial data."""
        if len(years_data) < 2:
            return {}
        
        derived = {}
        
        # Revenue CAGR
        if len(years_data) >= 3:
            latest_rev = years_data[0].get("revenue", 0)
            oldest_rev = years_data[-1].get("revenue", 0)
            if oldest_rev > 0 and latest_rev > 0:
                years_diff = years_data[0]["year"] - years_data[-1]["year"]
                if years_diff > 0:
                    cagr = (latest_rev / oldest_rev) ** (1 / years_diff) - 1
                    derived["revenue_cagr"] = round(cagr, 4)
                    derived["revenue_cagr_years"] = years_diff
        
        # Average ROE
        roe_values = [y.get("roe", 0) for y in years_data if y.get("roe")]
        if roe_values:
            derived["avg_roe"] = round(sum(roe_values) / len(roe_values), 4)
        
        # Average ROA
        roa_values = [y.get("roa", 0) for y in years_data if y.get("roa")]
        if roa_values:
            derived["avg_roa"] = round(sum(roa_values) / len(roa_values), 4)
        
        # Latest margins
        if years_data[0].get("revenue", 0) > 0:
            revenue = years_data[0]["revenue"]
            derived["gross_margin"] = round(years_data[0].get("gross_profit", 0) / revenue, 4)
            derived["ebitda_margin"] = round(years_data[0].get("ebitda", 0) / revenue, 4)
            derived["net_margin"] = round(years_data[0].get("net_income", 0) / revenue, 4)
        
        return derived
    
    async def get_alpha_vantage_overview(
        self,
        symbol: str,
    ) -> dict[str, Any]:
        """
        Get company overview from Alpha Vantage.
        
        Useful as fallback when FMP data is unavailable.
        Free tier: 500 requests/day.
        """
        try:
            response = await self.client.get(
                self.ALPHA_VANTAGE_BASE_URL,
                params={
                    "function": "OVERVIEW",
                    "symbol": symbol,
                    "apikey": self.alpha_vantage_api_key,
                },
            )
            response.raise_for_status()
            
            data = response.json()
            
            if "Note" in data:
                # Rate limit hit
                return {"symbol": symbol, "error": "Alpha Vantage rate limit reached"}
            
            if not data or "Symbol" not in data:
                return {"symbol": symbol, "error": "No data found"}
            
            result = {
                "symbol": data.get("Symbol", symbol),
                "name": data.get("Name", ""),
                "exchange": data.get("Exchange", ""),
                "currency": data.get("Currency", "USD"),
                "country": data.get("Country", ""),
                "sector": data.get("Sector", ""),
                "industry": data.get("Industry", ""),
                "market_cap": int(data.get("MarketCapitalization", 0) or 0),
                "pe_ratio": float(data.get("PERatio", 0) or 0),
                "eps": float(data.get("EPS", 0) or 0),
                "revenue_ttm": int(data.get("RevenueTTM", 0) or 0),
                "gross_profit_ttm": int(data.get("GrossProfitTTM", 0) or 0),
                "ebitda": int(data.get("EBITDA", 0) or 0),
                "profit_margin": float(data.get("ProfitMargin", 0) or 0),
                "roe": float(data.get("ReturnOnEquityTTM", 0) or 0),
                "employees": int(data.get("FullTimeEmployees", 0) or 0),
            }
            
            logger.info(
                "finance_apis.alpha_vantage.success",
                symbol=symbol,
                name=result["name"],
            )
            
            return result
        
        except Exception as e:
            logger.error(
                "finance_apis.alpha_vantage.failed",
                symbol=symbol,
                error=str(e),
            )
            return {"symbol": symbol, "error": str(e)}
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# Exchange codes for reference
EXCHANGE_CODES = {
    "NYSE": "New York Stock Exchange",
    "NASDAQ": "NASDAQ",
    "LSE": "London Stock Exchange",
    "ASX": "Australian Securities Exchange",
    "TSX": "Toronto Stock Exchange",
    "EURONEXT": "Euronext (Paris, Amsterdam, Brussels)",
    "XETRA": "Frankfurt Stock Exchange",
    "SIX": "Swiss Exchange",
}





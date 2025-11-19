#!/usr/bin/env python3
"""Test all API keys and report their status."""
from __future__ import annotations

import asyncio
import os
from datetime import datetime

import httpx
import structlog

log = structlog.get_logger()


async def test_tavily_api() -> dict[str, str | bool]:
    """Test Tavily API key."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return {"service": "Tavily", "status": False, "error": "API key not set"}
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": "test",
                    "max_results": 1,
                }
            )
        response.raise_for_status()
        data = response.json()
        return {
            "service": "Tavily",
            "status": True,
            "message": f"✅ Working - Found {len(data.get('results', []))} results",
        }
    except httpx.HTTPStatusError as e:
        return {
            "service": "Tavily",
            "status": False,
            "error": f"HTTP {e.response.status_code}: {e.response.text[:200]}",
        }
    except Exception as e:
        return {"service": "Tavily", "status": False, "error": str(e)}


async def test_tavily_mcp() -> dict[str, str | bool]:
    """Test Tavily remote MCP server."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return {"service": "Tavily MCP", "status": False, "error": "API key not set"}
    
    mcp_url = f"https://mcp.tavily.com/mcp/?tavilyApiKey={api_key}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(mcp_url)
        response.raise_for_status()
        return {
            "service": "Tavily MCP",
            "status": True,
            "message": f"✅ Accessible - Status {response.status_code}",
        }
    except Exception as e:
        return {"service": "Tavily MCP", "status": False, "error": str(e)}


async def test_perplexity_api() -> dict[str, str | bool]:
    """Test Perplexity API key."""
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        return {"service": "Perplexity", "status": False, "error": "API key not set"}
    
    try:
        # Try the Perplexity Search API
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.perplexity.ai/search",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"query": "test"},
            )
        response.raise_for_status()
        return {
            "service": "Perplexity",
            "status": True,
            "message": "✅ Working - API accessible",
        }
    except httpx.HTTPStatusError as e:
        return {
            "service": "Perplexity",
            "status": False,
            "error": f"HTTP {e.response.status_code}: {e.response.text[:200]}",
        }
    except Exception as e:
        return {"service": "Perplexity", "status": False, "error": str(e)}


async def test_openai_api() -> dict[str, str | bool]:
    """Test OpenAI API key."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"service": "OpenAI", "status": False, "error": "API key not set"}
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
        response.raise_for_status()
        data = response.json()
        model_count = len(data.get("data", []))
        return {
            "service": "OpenAI",
            "status": True,
            "message": f"✅ Working - {model_count} models accessible",
        }
    except httpx.HTTPStatusError as e:
        return {
            "service": "OpenAI",
            "status": False,
            "error": f"HTTP {e.response.status_code}: {e.response.text[:200]}",
        }
    except Exception as e:
        return {"service": "OpenAI", "status": False, "error": str(e)}


async def test_google_api() -> dict[str, str | bool]:
    """Test Google GenAI API key."""
    api_key = (
        os.getenv("GOOGLE_GENAI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or os.getenv("GEMINI_API_KEY")
    )
    if not api_key:
        return {"service": "Google GenAI", "status": False, "error": "API key not set"}
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            )
        response.raise_for_status()
        data = response.json()
        model_count = len(data.get("models", []))
        return {
            "service": "Google GenAI",
            "status": True,
            "message": f"✅ Working - {model_count} models accessible",
        }
    except httpx.HTTPStatusError as e:
        return {
            "service": "Google GenAI",
            "status": False,
            "error": f"HTTP {e.response.status_code}: {e.response.text[:200]}",
        }
    except Exception as e:
        return {"service": "Google GenAI", "status": False, "error": str(e)}


async def test_anthropic_api() -> dict[str, str | bool]:
    """Test Anthropic API key."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {"service": "Anthropic", "status": False, "error": "API key not set"}
    
    try:
        # Test with a minimal message
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": "Hi"}],
                },
            )
        response.raise_for_status()
        return {
            "service": "Anthropic",
            "status": True,
            "message": "✅ Working - API accessible",
        }
    except httpx.HTTPStatusError as e:
        return {
            "service": "Anthropic",
            "status": False,
            "error": f"HTTP {e.response.status_code}: {e.response.text[:200]}",
        }
    except Exception as e:
        return {"service": "Anthropic", "status": False, "error": str(e)}


async def test_fmp_api() -> dict[str, str | bool]:
    """Test Financial Modeling Prep API key."""
    api_key = os.getenv("FMP_API_KEY")
    if not api_key or api_key == "demo":
        return {"service": "FMP", "status": False, "error": "API key not set or using demo"}
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"https://financialmodelingprep.com/api/v3/profile/AAPL?apikey={api_key}"
            )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list) and len(data) > 0:
            return {
                "service": "FMP",
                "status": True,
                "message": "✅ Working - API accessible",
            }
        return {
            "service": "FMP",
            "status": False,
            "error": "API returned empty or invalid response",
        }
    except httpx.HTTPStatusError as e:
        return {
            "service": "FMP",
            "status": False,
            "error": f"HTTP {e.response.status_code}: {e.response.text[:200]}",
        }
    except Exception as e:
        return {"service": "FMP", "status": False, "error": str(e)}


async def main() -> None:
    """Run all API key tests."""
    print("=" * 80)
    print(f"🔑 API Key Test Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()
    
    tests = [
        test_tavily_api(),
        test_tavily_mcp(),
        test_perplexity_api(),
        test_openai_api(),
        test_google_api(),
        test_anthropic_api(),
        test_fmp_api(),
    ]
    
    results = await asyncio.gather(*tests)
    
    working_count = 0
    failed_count = 0
    
    for result in results:
        status = result.get("status")
        service = result.get("service", "Unknown")
        
        if status:
            working_count += 1
            print(f"✅ {service:20s} {result.get('message', 'Working')}")
        else:
            failed_count += 1
            error = result.get("error", "Unknown error")
            print(f"❌ {service:20s} ERROR: {error}")
    
    print()
    print("=" * 80)
    print(f"Summary: {working_count} working, {failed_count} failed")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())


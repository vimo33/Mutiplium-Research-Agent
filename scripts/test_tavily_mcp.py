#!/usr/bin/env python3
"""Test Tavily MCP integration and all 5 tools."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

# Load .env file
try:
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env")
except ImportError:
    # Fallback: manually load .env if python-dotenv not installed
    env_file = project_root / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip().strip('"')

from src.multiplium.tools.tavily_mcp import TavilyMCPClient


async def test_search() -> None:
    """Test Tavily search."""
    print("\n" + "=" * 80)
    print("🔍 Testing Tavily MCP Search")
    print("=" * 80)
    
    client = TavilyMCPClient()
    result = await client.search(
        query="precision irrigation vineyard technology",
        max_results=3,
        search_depth="basic"
    )
    
    print(f"\n✅ Search completed")
    print(f"Query: 'precision irrigation vineyard technology'")
    print(f"Results: {json.dumps(result, indent=2)[:500]}...")
    
    if "error" in result:
        print(f"❌ Error: {result['error']}")
        return False
    
    return True


async def test_extract() -> None:
    """Test Tavily extract."""
    print("\n" + "=" * 80)
    print("📄 Testing Tavily MCP Extract")
    print("=" * 80)
    
    client = TavilyMCPClient()
    result = await client.extract(
        urls=["https://www.crunchbase.com/organization/farmwise"],
        include_raw_content=False
    )
    
    print(f"\n✅ Extract completed")
    print(f"URL: https://www.crunchbase.com/organization/farmwise")
    print(f"Results: {json.dumps(result, indent=2)[:500]}...")
    
    if "error" in result:
        print(f"❌ Error: {result['error']}")
        return False
    
    return True


async def test_map() -> None:
    """Test Tavily map."""
    print("\n" + "=" * 80)
    print("🗺️  Testing Tavily MCP Map")
    print("=" * 80)
    
    client = TavilyMCPClient()
    result = await client.map_website(
        url="https://www.farmwise.io",
        max_pages=5
    )
    
    print(f"\n✅ Map completed")
    print(f"URL: https://www.farmwise.io")
    print(f"Results: {json.dumps(result, indent=2)[:500]}...")
    
    if "error" in result:
        print(f"❌ Error: {result['error']}")
        return False
    
    return True


async def test_crawl() -> None:
    """Test Tavily crawl."""
    print("\n" + "=" * 80)
    print("🕷️  Testing Tavily MCP Crawl")
    print("=" * 80)
    
    client = TavilyMCPClient()
    result = await client.crawl_website(
        url="https://www.farmwise.io",
        max_depth=1,
        max_pages=3
    )
    
    print(f"\n✅ Crawl completed")
    print(f"URL: https://www.farmwise.io")
    print(f"Max depth: 1, Max pages: 3")
    print(f"Results: {json.dumps(result, indent=2)[:500]}...")
    
    if "error" in result:
        print(f"❌ Error: {result['error']}")
        return False
    
    return True


async def test_fetch() -> None:
    """Test Tavily fetch (uses extract internally)."""
    print("\n" + "=" * 80)
    print("📥 Testing Tavily MCP Fetch Content")
    print("=" * 80)
    
    client = TavilyMCPClient()
    result = await client.fetch_content(
        url="https://www.farmwise.io"
    )
    
    print(f"\n✅ Fetch completed")
    print(f"URL: https://www.farmwise.io")
    print(f"Results: {json.dumps(result, indent=2)[:500]}...")
    
    if "error" in result:
        print(f"❌ Error: {result['error']}")
        return False
    
    return True


async def main() -> None:
    """Run all Tavily MCP tests."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        print("❌ TAVILY_API_KEY not set in environment")
        print("Please set your API key:")
        print("  export TAVILY_API_KEY='your-key-here'")
        return
    
    print("=" * 80)
    print("🧪 Tavily MCP Integration Test Suite")
    print("=" * 80)
    print(f"API Key: {api_key[:10]}...{api_key[-4:]}")
    
    tests = [
        ("Search", test_search),
        ("Extract", test_extract),
        ("Map", test_map),
        ("Crawl", test_crawl),
        ("Fetch", test_fetch),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = await test_func()
            results.append((name, success))
        except Exception as exc:
            print(f"\n❌ {name} test failed with exception: {exc}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 Test Summary")
    print("=" * 80)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status:10s} {name}")
    
    print("=" * 80)
    print(f"Result: {passed}/{total} tests passed")
    print("=" * 80)
    
    if passed == total:
        print("\n🎉 All Tavily MCP tools are working correctly!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Check errors above.")


if __name__ == "__main__":
    asyncio.run(main())


#!/usr/bin/env python3
"""Test Perplexity MCP integration and all 4 tools."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.multiplium.tools.perplexity_mcp import PerplexityMCPClient


async def test_search() -> None:
    """Test Perplexity search."""
    print("\n" + "=" * 80)
    print("🔍 Testing Perplexity MCP Search")
    print("=" * 80)
    
    client = PerplexityMCPClient()
    result = await client.search(
        query="precision irrigation technology vineyards 2024",
        max_results=3,
        search_recency_filter="month"
    )
    
    print(f"\n✅ Search completed")
    print(f"Query: 'precision irrigation technology vineyards 2024'")
    print(f"Content preview: {result.get('content', '')[:200]}...")
    print(f"Citations: {len(result.get('citations', []))} sources")
    
    if "error" in result:
        print(f"❌ Error: {result['error']}")
        return False
    
    return True


async def test_ask() -> None:
    """Test Perplexity ask."""
    print("\n" + "=" * 80)
    print("💬 Testing Perplexity MCP Ask")
    print("=" * 80)
    
    client = PerplexityMCPClient()
    result = await client.ask(
        question="What is FarmWise and how does it help vineyards?",
        return_related_questions=True
    )
    
    print(f"\n✅ Ask completed")
    print(f"Question: 'What is FarmWise and how does it help vineyards?'")
    print(f"Answer preview: {result.get('answer', '')[:200]}...")
    print(f"Citations: {len(result.get('citations', []))} sources")
    print(f"Related questions: {len(result.get('related_questions', []))}")
    
    if "error" in result:
        print(f"❌ Error: {result['error']}")
        return False
    
    return True


async def test_research() -> None:
    """Test Perplexity research."""
    print("\n" + "=" * 80)
    print("📊 Testing Perplexity MCP Research")
    print("=" * 80)
    
    client = PerplexityMCPClient()
    result = await client.research(
        topic="FarmWise agricultural robotics impact on vineyard sustainability",
        focus_areas=["environmental impact", "ROI data", "customer adoption"]
    )
    
    print(f"\n✅ Research completed")
    print(f"Topic: 'FarmWise agricultural robotics...'")
    print(f"Report length: {result.get('word_count', 0)} words")
    print(f"Citations: {len(result.get('citations', []))} sources")
    print(f"Report preview: {result.get('report', '')[:200]}...")
    
    if "error" in result:
        print(f"❌ Error: {result['error']}")
        return False
    
    return True


async def test_reason() -> None:
    """Test Perplexity reason."""
    print("\n" + "=" * 80)
    print("🧠 Testing Perplexity MCP Reason")
    print("=" * 80)
    
    client = PerplexityMCPClient()
    result = await client.reason(
        problem="Compare precision irrigation ROI vs traditional methods for vineyards",
        context="Focus on water savings, yield improvement, and installation costs"
    )
    
    print(f"\n✅ Reason completed")
    print(f"Problem: 'Compare precision irrigation ROI...'")
    print(f"Analysis preview: {result.get('analysis', '')[:200]}...")
    print(f"Citations: {len(result.get('citations', []))} sources")
    
    if "error" in result:
        print(f"❌ Error: {result['error']}")
        return False
    
    return True


async def main() -> None:
    """Run all Perplexity MCP tests."""
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        print("❌ PERPLEXITY_API_KEY not set in environment")
        print("Please set your API key:")
        print("  export PERPLEXITY_API_KEY='your-key-here'")
        return
    
    print("=" * 80)
    print("🧪 Perplexity MCP Integration Test Suite")
    print("=" * 80)
    print(f"API Key: {api_key[:10]}...{api_key[-4:]}")
    
    tests = [
        ("Search", test_search),
        ("Ask", test_ask),
        ("Research", test_research),
        ("Reason", test_reason),
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
        print("\n🎉 All Perplexity MCP tools are working correctly!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Check errors above.")


if __name__ == "__main__":
    asyncio.run(main())


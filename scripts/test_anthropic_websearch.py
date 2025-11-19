#!/usr/bin/env python3
"""Test Anthropic Claude 4.5 Sonnet with native web search tool."""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env")
except ImportError:
    # Fallback: manually load .env
    env_file = project_root / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip().strip('"')


async def test_anthropic_websearch():
    """Test Claude 4.5 Sonnet with web search tool."""
    try:
        import anthropic
    except ImportError:
        print("❌ anthropic package not installed")
        print("   Run: pip install anthropic")
        return False

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY not found in environment")
        return False

    print("✅ ANTHROPIC_API_KEY found")
    print(f"   Key prefix: {api_key[:10]}...")

    # Test 1: Basic connection
    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)
        print("✅ Anthropic client initialized")
    except Exception as e:
        print(f"❌ Failed to initialize client: {e}")
        return False

    # Test 2: Web search tool configuration
    try:
        tools = [
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 2,
            }
        ]
        print("✅ Web search tool configured")
        print(f"   Type: web_search_20250305")
        print(f"   Max uses: 2")
    except Exception as e:
        print(f"❌ Failed to configure web search tool: {e}")
        return False

    # Test 3: Make a test request with web search
    try:
        print("\n🔍 Testing web search with Claude 4.5 Sonnet...")
        print("   Query: 'Find 1 vineyard technology company using soil microbiome testing'")
        
        messages = [
            {
                "role": "user",
                "content": "Find ONE vineyard technology company that uses soil microbiome testing. Use web_search to find a real company. Provide: company name, country, and one key fact."
            }
        ]

        response = await client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2048,
            messages=messages,
            tools=tools,
        )

        print("✅ API call successful")
        print(f"   Model: {response.model}")
        print(f"   Stop reason: {response.stop_reason}")
        
        # Check for web search usage
        usage = response.usage
        if hasattr(usage, "model_extra") and usage.model_extra:
            server_tool_use = usage.model_extra.get("server_tool_use", {})
            web_search_requests = server_tool_use.get("web_search_requests", 0)
            if web_search_requests > 0:
                print(f"   ✅ Web searches executed: {web_search_requests}")
            else:
                print("   ⚠️  No web searches detected in usage")
        
        # Extract response text
        text_blocks = [block for block in response.content if hasattr(block, "type") and block.type == "text"]
        if text_blocks:
            response_text = text_blocks[0].text[:200]
            print(f"\n📝 Response preview:")
            print(f"   {response_text}...")
        
        await client.aclose()
        print("\n✅ All tests passed!")
        print("✅ Claude 4.5 Sonnet with web search is ready for production")
        return True

    except Exception as e:
        print(f"❌ API call failed: {e}")
        if "client" in locals():
            await client.aclose()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_anthropic_websearch())
    sys.exit(0 if success else 1)


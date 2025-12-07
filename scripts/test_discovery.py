#!/usr/bin/env python3
"""Quick test script to verify SDK integrations for discovery."""
import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Load .env file
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


async def test_openai_sdk():
    """Test OpenAI Agents SDK with WebSearchTool."""
    print("\n" + "=" * 60)
    print("🔵 Testing OpenAI Agents SDK (GPT-5.1 + WebSearchTool)")
    print("=" * 60)
    
    try:
        from agents import Agent, Runner, WebSearchTool, ModelSettings, set_default_openai_key
        from openai.types.shared import Reasoning
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("❌ OPENAI_API_KEY not set")
            return False
        
        set_default_openai_key(api_key)
        
        # Configure model settings
        # Note: GPT-5.1 with reasoning doesn't support temperature parameter
        model_settings = ModelSettings(
            reasoning=Reasoning(effort="low"),
        )
        
        agent = Agent(
            name="Company Researcher",
            instructions=(
                "You are a research analyst. Find ONE company that uses AI/ML for vineyard soil health monitoring. "
                "Return a JSON with: company name, website, country, and a brief summary."
            ),
            model="gpt-5.1",
            model_settings=model_settings,
            tools=[WebSearchTool()],
        )
        
        print("🔍 Searching for a soil health vineyard company...")
        result = await asyncio.wait_for(
            Runner.run(agent, "Find one company that uses AI for vineyard soil health monitoring."),
            timeout=60.0
        )
        
        print(f"✅ OpenAI Result:\n{result.final_output[:500]}...")
        return True
        
    except asyncio.TimeoutError:
        print("❌ OpenAI test timed out after 60 seconds")
        return False
    except Exception as e:
        print(f"❌ OpenAI test failed: {e}")
        return False


async def test_google_sdk():
    """Test Google GenAI SDK with Google Search grounding."""
    print("\n" + "=" * 60)
    print("🟢 Testing Google GenAI SDK (Gemini 3 Pro + Search Grounding)")
    print("=" * 60)
    
    try:
        from google import genai
        from google.genai import types
        
        api_key = (
            os.getenv("GOOGLE_GENAI_API_KEY") or
            os.getenv("GOOGLE_API_KEY") or
            os.getenv("GEMINI_API_KEY")
        )
        if not api_key:
            print("❌ GOOGLE_API_KEY not set")
            return False
        
        client = genai.Client(api_key=api_key)
        
        # Enable Google Search grounding
        google_search_tool = types.Tool(google_search=types.GoogleSearch())
        
        # Configure thinking for Gemini 3
        thinking_config = types.ThinkingConfig(
            thinking_budget=512,
            include_thoughts=False,
        )
        
        prompt = (
            "Find ONE company that uses precision irrigation technology for vineyards. "
            "Return a JSON with: company name, website, country, and a brief summary."
        )
        
        print("🔍 Searching for a precision irrigation vineyard company...")
        response = await asyncio.wait_for(
            client.aio.models.generate_content(
                model="gemini-3-pro-preview",
                contents=[types.Content(role="user", parts=[types.Part.from_text(text=prompt)])],
                config=types.GenerateContentConfig(
                    system_instruction="You are a research analyst. Find real companies using web search.",
                    tools=[google_search_tool],
                    temperature=1.0,
                    thinking_config=thinking_config,
                ),
            ),
            timeout=60.0
        )
        
        print(f"✅ Google Result:\n{response.text[:500]}...")
        
        # Check for grounding metadata
        if hasattr(response, 'grounding_metadata') and response.grounding_metadata:
            print("✅ Google Search grounding was used!")
        
        client.close()
        return True
        
    except asyncio.TimeoutError:
        print("❌ Google test timed out after 60 seconds")
        return False
    except Exception as e:
        print(f"❌ Google test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("\n🧪 Multiplium SDK Integration Test")
    print("Testing discovery with latest models and native search tools\n")
    
    results = {}
    
    # Test OpenAI
    results["openai"] = await test_openai_sdk()
    
    # Test Google
    results["google"] = await test_google_sdk()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)
    
    for provider, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {provider.upper()}: {status}")
    
    all_passed = all(results.values())
    print(f"\nOverall: {'✅ All tests passed!' if all_passed else '❌ Some tests failed'}")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(asyncio.run(main()))

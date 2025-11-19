"""Test Tavily and Google GenAI API keys."""
import asyncio
import os
import sys
from datetime import datetime, timezone

import httpx


async def test_tavily_api(api_key: str) -> tuple[bool, str]:
    """Test Tavily API with search endpoint."""
    if not api_key:
        return False, "API key not set"
    
    print(f"🔑 Testing Tavily API key: {api_key[:15]}...{api_key[-5:]}")
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": "test precision agriculture",
                    "max_results": 2,
                },
            )
        
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            return True, f"✅ SUCCESS - Found {len(results)} results"
        elif response.status_code == 401:
            return False, f"❌ UNAUTHORIZED - Invalid API key"
        else:
            return False, f"❌ HTTP {response.status_code}: {response.text[:200]}"
    except Exception as e:
        return False, f"❌ ERROR: {str(e)}"


async def test_google_genai_api(api_key: str) -> tuple[bool, str]:
    """Test Google GenAI API with the correct SDK."""
    if not api_key:
        return False, "API key not set"
    
    print(f"🔑 Testing Google GenAI API key: {api_key[:15]}...{api_key[-5:]}")
    
    try:
        from google import genai
        
        # Initialize client with explicit API key
        client = genai.Client(api_key=api_key)
        
        # Test with gemini-2.5-flash (latest stable model from docs)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Say 'API test successful' in exactly 3 words"
        )
        
        text = response.text
        return True, f"✅ SUCCESS - Response: {text[:100]}"
    
    except ImportError as e:
        return False, f"❌ SDK NOT INSTALLED: {e}"
    except Exception as e:
        error_msg = str(e)
        if "404" in error_msg or "Not Found" in error_msg:
            return False, f"❌ MODEL NOT FOUND - Try: gemini-1.5-flash, gemini-1.5-pro, or gemini-2.0-flash-exp"
        elif "401" in error_msg or "403" in error_msg or "Unauthorized" in error_msg:
            return False, f"❌ INVALID API KEY"
        else:
            return False, f"❌ ERROR: {error_msg[:200]}"


async def test_google_available_models(api_key: str) -> tuple[bool, str]:
    """List available Google GenAI models."""
    if not api_key:
        return False, "API key not set"
    
    print("🔍 Checking available Google GenAI models...")
    
    try:
        from google import genai
        
        client = genai.Client(api_key=api_key)
        
        # Try to list models
        models = client.models.list()
        model_names = []
        for model in models:
            if hasattr(model, 'name'):
                model_names.append(model.name)
        
        if model_names:
            return True, f"✅ Found {len(model_names)} models: {', '.join(model_names[:5])}"
        else:
            return False, "❌ No models returned from API"
    
    except Exception as e:
        return False, f"⚠️  Could not list models: {str(e)[:200]}"


async def main():
    print("=" * 80)
    print(f"🧪 Tavily + Google GenAI API Key Test - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 80)
    print()
    
    # Get API keys
    tavily_key = os.getenv("TAVILY_API_KEY")
    google_key = (
        os.getenv("GOOGLE_GENAI_API_KEY") 
        or os.getenv("GOOGLE_API_KEY") 
        or os.getenv("GEMINI_API_KEY")
    )
    
    results = {}
    
    # Test 1: Tavily API
    print("=" * 80)
    print("📍 TEST 1: Tavily Search API")
    print("=" * 80)
    status, message = await test_tavily_api(tavily_key)
    results["Tavily API"] = status
    print(f"{message}\n")
    
    # Test 2: Google GenAI available models
    print("=" * 80)
    print("📍 TEST 2: Google GenAI - Available Models")
    print("=" * 80)
    status, message = await test_google_available_models(google_key)
    results["Google Models List"] = status
    print(f"{message}\n")
    
    # Test 3: Google GenAI API with gemini-2.5-flash
    print("=" * 80)
    print("📍 TEST 3: Google GenAI - Generate Content (gemini-2.5-flash)")
    print("=" * 80)
    status, message = await test_google_genai_api(google_key)
    results["Google GenAI API"] = status
    print(f"{message}\n")
    
    # Summary
    print("=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    
    working_count = sum(1 for status in results.values() if status)
    
    for test_name, status in results.items():
        icon = "✅" if status else "❌"
        print(f"{icon} {test_name}")
    
    print("=" * 80)
    print(f"Result: {working_count}/{len(results)} tests passed")
    print("=" * 80)
    
    if working_count == len(results):
        print("\n🎉 ALL TESTS PASSED! Ready to run full research.")
        sys.exit(0)
    else:
        print("\n⚠️  SOME TESTS FAILED. Please check API keys and model availability.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())


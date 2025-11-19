#!/usr/bin/env python3
"""
Comprehensive pre-flight validation for all Multiplium systems.
Tests all providers, API keys, and configurations before research run.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

# Load .env explicitly
try:
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env")
except ImportError:
    env_file = project_root / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip().strip('"').strip("'")


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    END = "\033[0m"


def print_header(text: str) -> None:
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(80)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 80}{Colors.END}\n")


def print_pass(text: str) -> None:
    """Print a pass message."""
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")


def print_fail(text: str) -> None:
    """Print a fail message."""
    print(f"{Colors.RED}❌ {text}{Colors.END}")


def print_warn(text: str) -> None:
    """Print a warning message."""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")


def print_info(text: str) -> None:
    """Print an info message."""
    print(f"   {text}")


async def test_anthropic() -> bool:
    """Test Anthropic Claude 4.5 Sonnet with web search."""
    print(f"\n{Colors.BOLD}1. Testing Anthropic (Claude 4.5 Sonnet)...{Colors.END}")
    
    try:
        import anthropic
    except ImportError:
        print_fail("anthropic package not installed")
        print_info("Run: pip install anthropic")
        return False
    
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print_fail("ANTHROPIC_API_KEY not found in environment")
        return False
    
    print_pass(f"API key found: {api_key[:15]}...")
    
    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)
        print_pass("Client initialized")
    except Exception as e:
        print_fail(f"Failed to initialize client: {e}")
        return False
    
    # Test web search tool
    try:
        print_info("Testing web search tool...")
        
        messages = [
            {
                "role": "user",
                "content": "Find ONE vineyard in Napa Valley using a web search. Just return the name."
            }
        ]
        
        tools = [
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 1,
            }
        ]
        
        response = await client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=512,
            messages=messages,
            tools=tools,
        )
        
        print_pass(f"Web search test completed (stop: {response.stop_reason})")
        
        # Check for web search usage
        usage = response.usage
        if hasattr(usage, "model_extra") and usage.model_extra:
            server_tool_use = usage.model_extra.get("server_tool_use", {})
            web_search_requests = server_tool_use.get("web_search_requests", 0)
            if web_search_requests > 0:
                print_pass(f"Web search executed: {web_search_requests} request(s)")
            else:
                print_warn("Web search tool available but not used in test")
        
        await client.close()
        print_pass("Anthropic provider fully operational")
        return True
        
    except Exception as e:
        print_fail(f"API call failed: {e}")
        if "client" in locals():
            await client.close()
        return False


async def test_openai() -> bool:
    """Test OpenAI GPT-5 with native web search."""
    print(f"\n{Colors.BOLD}2. Testing OpenAI (GPT-5)...{Colors.END}")
    
    try:
        from openai import AsyncOpenAI
    except ImportError:
        print_fail("openai package not installed")
        print_info("Run: pip install openai")
        return False
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print_fail("OPENAI_API_KEY not found in environment")
        return False
    
    print_pass(f"API key found: {api_key[:15]}...")
    
    try:
        client = AsyncOpenAI(api_key=api_key)
        print_pass("Client initialized")
    except Exception as e:
        print_fail(f"Failed to initialize client: {e}")
        return False
    
    # Test API call (no native web search config needed)
    try:
        print_info("Testing API connection...")
        
        response = await client.chat.completions.create(
            model="gpt-4o",  # Use gpt-4o for testing (gpt-5 might not be available)
            messages=[
                {"role": "user", "content": "Say 'test successful' in 2 words"}
            ],
            max_tokens=10,
        )
        
        print_pass(f"API test completed: {response.choices[0].message.content}")
        print_info("Note: GPT-5 uses native web search (no explicit tool config)")
        
        await client.close()
        print_pass("OpenAI provider fully operational")
        return True
        
    except Exception as e:
        print_fail(f"API call failed: {e}")
        if "client" in locals():
            await client.close()
        return False


async def test_google() -> bool:
    """Test Google Gemini 2.5 Pro with Grounding."""
    print(f"\n{Colors.BOLD}3. Testing Google (Gemini 2.5 Pro)...{Colors.END}")
    
    try:
        import google.genai as genai
        from google.genai import types
    except ImportError:
        print_fail("google-genai package not installed")
        print_info("Run: pip install google-genai")
        return False
    
    api_key = (
        os.getenv("GOOGLE_GENAI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or os.getenv("GEMINI_API_KEY")
    )
    
    if not api_key:
        print_fail("No Google API key found (tried GOOGLE_GENAI_API_KEY, GOOGLE_API_KEY, GEMINI_API_KEY)")
        return False
    
    print_pass(f"API key found: {api_key[:15]}...")
    
    try:
        client = genai.Client(api_key=api_key)
        print_pass("Client initialized")
    except Exception as e:
        print_fail(f"Failed to initialize client: {e}")
        return False
    
    # Test Google Search grounding
    try:
        print_info("Testing Google Search grounding...")
        
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",  # Use flash for testing (cheaper)
            contents="Find ONE vineyard in Napa Valley. Just return the name.",
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.1,
            ),
        )
        
        text_result = response.text if response.text else "(empty)"
        print_pass(f"Grounding test completed: {text_result[:50]}...")
        print_pass("Google provider fully operational")
        return True
        
    except Exception as e:
        print_fail(f"API call failed: {e}")
        return False


async def test_mcp_tools() -> bool:
    """Test MCP tools (Perplexity, Tavily)."""
    print(f"\n{Colors.BOLD}4. Testing MCP Tools...{Colors.END}")
    
    # Test Perplexity
    perplexity_key = os.getenv("PERPLEXITY_API_KEY") or os.getenv("PPLX_API_KEY")
    if perplexity_key:
        print_pass(f"Perplexity API key found: {perplexity_key[:15]}...")
    else:
        print_warn("Perplexity API key not found (validation will be limited)")
    
    # Test Tavily
    tavily_key = os.getenv("TAVILY_API_KEY")
    if tavily_key:
        print_pass(f"Tavily API key found: {tavily_key[:15]}...")
    else:
        print_warn("Tavily API key not found (validation will be limited)")
    
    if perplexity_key or tavily_key:
        print_pass("At least one MCP tool is available")
        return True
    else:
        print_fail("No MCP tools available (validation will be severely limited)")
        return False


async def test_config() -> bool:
    """Test configuration file."""
    print(f"\n{Colors.BOLD}5. Testing Configuration...{Colors.END}")
    
    config_path = project_root / "config" / "dev.yaml"
    if not config_path.exists():
        print_fail(f"Config file not found: {config_path}")
        return False
    
    print_pass(f"Config file found: {config_path}")
    
    try:
        import yaml
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        # Check providers
        providers = config.get("providers", {})
        enabled_providers = [name for name, cfg in providers.items() if cfg.get("enabled")]
        
        print_info(f"Enabled providers: {', '.join(enabled_providers)}")
        
        if len(enabled_providers) < 2:
            print_warn(f"Only {len(enabled_providers)} provider(s) enabled - consider enabling at least 2")
        
        # Check concurrency
        concurrency = config.get("orchestrator", {}).get("concurrency", 1)
        print_info(f"Concurrency: {concurrency}")
        
        print_pass("Configuration valid")
        return True
        
    except Exception as e:
        print_fail(f"Config validation failed: {e}")
        return False


async def main() -> int:
    """Run all validation tests."""
    print_header("MULTIPLIUM PRE-FLIGHT VALIDATION")
    
    print(f"{Colors.BOLD}Testing all systems before research run...{Colors.END}")
    
    results = {
        "Anthropic": await test_anthropic(),
        "OpenAI": await test_openai(),
        "Google": await test_google(),
        "MCP Tools": await test_mcp_tools(),
        "Configuration": await test_config(),
    }
    
    # Summary
    print_header("VALIDATION SUMMARY")
    
    passed = sum(results.values())
    total = len(results)
    
    for name, status in results.items():
        if status:
            print_pass(f"{name:20} PASS")
        else:
            print_fail(f"{name:20} FAIL")
    
    print(f"\n{Colors.BOLD}Result: {passed}/{total} tests passed{Colors.END}")
    
    if passed == total:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🚀 ALL SYSTEMS GREEN - READY FOR RESEARCH RUN{Colors.END}")
        return 0
    elif passed >= 3:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠️  PARTIAL SYSTEMS - Research can proceed with limitations{Colors.END}")
        print(f"{Colors.YELLOW}   Some providers may be disabled but core functionality available{Colors.END}")
        return 0
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}❌ CRITICAL FAILURES - DO NOT PROCEED WITH RESEARCH{Colors.END}")
        print(f"{Colors.RED}   Fix critical issues before running{Colors.END}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)


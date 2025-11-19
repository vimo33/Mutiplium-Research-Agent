#!/usr/bin/env python3
"""Check environment variables for API keys."""
import os

print("=" * 80)
print("🔍 Environment Variable Check")
print("=" * 80)
print()

keys_to_check = [
    "TAVILY_API_KEY",
    "PERPLEXITY_API_KEY",
    "OPENAI_API_KEY",
    "GOOGLE_GENAI_API_KEY",
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY",
    "ANTHROPIC_API_KEY",
    "XAI_API_KEY",
    "FMP_API_KEY",
]

for key in keys_to_check:
    value = os.getenv(key)
    if value:
        # Mask the middle part for security
        if len(value) > 20:
            masked = f"{value[:10]}...{value[-6:]}"
        else:
            masked = value[:4] + "..." + value[-2:] if len(value) > 6 else "***"
        
        print(f"✅ {key:25s} = {masked} (length: {len(value)})")
        
        # Check for common issues
        if value != value.strip():
            print(f"   ⚠️  WARNING: Key has leading/trailing whitespace!")
        if "\n" in value or "\r" in value:
            print(f"   ⚠️  WARNING: Key contains newline characters!")
        if " " in value:
            print(f"   ⚠️  WARNING: Key contains spaces!")
    else:
        print(f"❌ {key:25s} = NOT SET")

print()
print("=" * 80)


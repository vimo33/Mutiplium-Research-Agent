#!/bin/bash
# Quick test runner for Multiplium
# This script runs a full test of the research platform

set -e

cd "$(dirname "$0")"

echo "🚀 Multiplium Research Tool - Test Runner"
echo "=========================================="
echo ""

# Check Python version
PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $PYTHON_VERSION"

# Activate venv
if [ -d ".venv" ]; then
    echo "✓ Activating virtual environment..."
    source .venv/bin/activate
else
    echo "❌ No .venv found! Run: python3.11 -m venv .venv"
    exit 1
fi

# Load environment
if [ -f ".env" ]; then
    echo "✓ Loading environment variables..."
    export $(grep -v '^#' .env | xargs)
else
    echo "❌ No .env file found!"
    exit 1
fi

# Check API keys
echo ""
echo "Checking API keys..."
if [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠️  OPENAI_API_KEY not set"
else
    echo "✓ OpenAI key found"
fi

if [ -z "$GOOGLE_GENAI_API_KEY" ]; then
    echo "⚠️  GOOGLE_GENAI_API_KEY not set"
else
    echo "✓ Google GenAI key found"
fi

if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "⚠️  ANTHROPIC_API_KEY not set (optional)"
fi

echo ""
echo "=========================================="
echo "Running DRY RUN test..."
echo "=========================================="
echo ""

python -m multiplium.orchestrator --config config/dev.yaml --dry-run

echo ""
echo "=========================================="
echo "✅ Dry run complete!"
echo "=========================================="
echo ""
echo "To run a FULL test with real API calls:"
echo ""
echo "  Terminal 1 (start tool servers):"
echo "  $ ./scripts/start_tool_servers.sh"
echo ""
echo "  Terminal 2 (run research):"
echo "  $ source .venv/bin/activate"
echo "  $ export \$(grep -v '^#' .env | xargs)"
echo "  $ python -m multiplium.orchestrator --config config/dev.yaml"
echo ""
echo "Report will be saved to: reports/latest_report.json"
echo ""


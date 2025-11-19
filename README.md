# Multiplium Deep Research Platform

Internal MVP for running multi-LLM investment research across Anthropic Claude, OpenAI GPT, and Google Gemini agents with integrated Tavily remote MCP server for production-ready web search, content extraction, and website crawling.

## Repo Layout
- `pyproject.toml` – Python project metadata and dependencies
- `src/multiplium/` – application source code
  - `config.py` – settings model and loader
  - `orchestrator.py` – async CLI orchestration and report persistence
  - `providers/` – SDK-specific agent wrappers (Claude, OpenAI, Gemini)
  - `tools/` – shared MCP-compatible tool interfaces
  - `reporting/` – report serialization and persistence helpers
- `servers/` – MCP reference implementations (search, Crunchbase, patents, financials, ESG, academic)
- `config/` – default configuration files
- `tests/` – unit and integration test suites (to be populated)

## Getting Started
1. Install **Python 3.11+** and Poetry or pip.
2. Copy `.env.example` to `.env` and populate required API keys:
   - **Required Provider Keys:** At least one of `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or `GOOGLE_GENAI_API_KEY` (or `GEMINI_API_KEY`)
   - **Required Search API:** `TAVILY_API_KEY` for Tavily remote MCP server (search, extract, map, crawl)
     - Get yours at: https://tavily.com
     - Your MCP endpoint: `https://mcp.tavily.com/mcp/?tavilyApiKey=YOUR_KEY`
   - **Optional Search APIs:** `PERPLEXITY_API_KEY` for additional search coverage
   - **Optional Tool APIs:** `FMP_API_KEY` for financial data (defaults to demo), `CRUNCHBASE_API_KEY`
   
   The orchestrator will validate your configuration on startup and warn you about missing optional keys.
   
   **Test your API keys:**
   ```bash
   python scripts/test_api_keys.py
   ```
3. Install dependencies:
   ```bash
   pip install -e .
   # or
   poetry install
   ```
4. **Tavily Remote MCP** (Production-Ready Search): The platform now uses Tavily's official remote MCP server for web search and content extraction. This provides 5 powerful tools:
   - `search_web` - Real-time web search
   - `fetch_content` - Fetch and extract page content
   - `extract_content` - Advanced content extraction from multiple URLs
   - `map_website` - Discover and map website structure
   - `crawl_website` - Systematically crawl websites for comprehensive research
   
   **Test Tavily MCP integration:**
   ```bash
   python scripts/test_tavily_mcp.py
   ```

5. **Local MCP Tool Servers** (Optional): For additional research capabilities, you can run local MCP servers for ESG ratings, academic papers, and sustainability data:
   ```bash
   # Quick start all servers:
   ./scripts/start_tool_servers.sh
   
   # Or start individually:
   pip install -r servers/requirements.txt
   PYTHONPATH=src uvicorn servers.esg_service:app --reload --port 7005
   PYTHONPATH=src uvicorn servers.academic_search_service:app --reload --port 7006
   PYTHONPATH=src uvicorn servers.sustainability_service:app --reload --port 7007
   ```
   
   **External data sources** (deployed on Render):
   - OpenAlex Organizations API for company metadata (`lookup_crunchbase`)
   - USPTO PatentsView API for patent search (`lookup_patents`)
   - Financial Modeling Prep API for financial metrics (`financial_metrics`)

   Optional environment variables:
   ```bash
   export FMP_API_KEY="demo"        # Replace with your own key for higher limits
   export TAVILY_API_KEY="..."      # Optional: richer search coverage
   export PERPLEXITY_API_KEY="..."  # Optional: augment search_web with Perplexity
   export GOOGLE_GENAI_API_KEY="..." # Required for Gemini provider
   export GEMINI_API_KEY="..."       # Alternate env var recognised by google-genai SDK
   # Optional: edit seed_companies.json to inject high-confidence vineyard deployments
   ```
   Run the uvicorn processes in separate terminals and keep them running while the orchestrator is executing. To launch all six servers in one shot, use the helper script (after `chmod +x scripts/start_tool_servers.sh`):
   ```bash
   scripts/start_tool_servers.sh
   ```
5. Run a dry-run smoke test (no live tool calls, returns placeholders):
   ```bash
   python -m multiplium.orchestrator --config config/dev.yaml --dry-run
   ```
6. Execute a full run (requires tool servers + provider credentials):
   ```bash
   python -m multiplium.orchestrator --config config/dev.yaml
   ```
   A consolidated JSON report is written to `reports/latest_report.json` by default. Override via `orchestrator.output_path` in the config file.

## Deploying MCP Tool Servers to Render

To avoid running the six tool services locally, deploy them as a single FastAPI app on [Render](https://render.com):

1. The repository includes `servers/app.py`, `requirements.txt`, and `render.yaml`. Push these files to your Git remote.
2. In Render, create a **Web Service** pointing at the repository. Render will install `requirements.txt` and start `uvicorn servers.app:app`.
3. Configure environment variables (e.g., `FMP_API_KEY`, `TAVILY_API_KEY`, `PERPLEXITY_API_KEY`, `GOOGLE_GENAI_API_KEY`) in the Render dashboard under the service's **Environment** tab.
4. After the service deploys, note the base URL (e.g., `https://multiplium-mcp-tools.onrender.com`) and update `config/dev.yaml` tool endpoints to point at:
   - `https://<host>/search/mcp/search`
   - `https://<host>/search/mcp/fetch`
   - `https://<host>/crunchbase/mcp/crunchbase`
   - `https://<host>/patents/mcp/patents`
   - `https://<host>/financials/mcp/financials`
   - `https://<host>/esg/mcp/esg`
   - `https://<host>/academic/mcp/academic`

> **Note**: SDKs evolve quickly—pin versions that are validated in your environment:
> - Anthropic Python SDK (`anthropic`)
> - OpenAI Agents SDK (`openai-agents`)
> - Google GenAI SDK (`google-genai`)

## Runtime Overview
- The orchestrator loads the thesis, value-chain, and KPI context from paths defined in `config/*.yaml`.
- `ToolManager` registers MCP endpoints and calls them over HTTP with caching, domain allowlists, and deterministic serialization.
- Provider wrappers:
  - **Claude** uses the Messages API with tool loops, streaming MCP results back into the conversation.
  - **OpenAI** uses the Agents SDK (`Runner`) with runtime-generated `FunctionTool` adapters.
  - **Gemini** uses the GenAI SDK with automatic function calling against async Python callables.
- Results from each provider (findings + telemetry) are persisted to JSON for downstream synthesis.

## Project Goals
1. Build a shared tool layer (search, fetch, Crunchbase, patents, metrics, ESG, academic research) exposed via Model Context Protocol (MCP).
2. Integrate Claude, OpenAI, and Gemini agents that consume the same tool contracts and KPI context.
3. Orchestrate agents in parallel, capture provenance for each fact, and synthesize consensus vs. unique findings.
4. Deliver an auditable investment brief with source metadata, KPI alignment, and analyst hand-off notes.

## Next Milestones
- [ ] Harden MCP tool servers (rate limiting, retries, provenance tagging)
- [ ] Implement aggregation logic for consensus scoring across providers
- [ ] Add regression/evaluation harness with fixture theses
- [ ] Enforce response schemas and guardrails per provider (e.g., OpenAI Guards, Gemini JSON schema)
- [ ] Expand telemetry (cost tracking, per-tool latencies) and observability hooks

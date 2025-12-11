# Project Context – Multiplium Multi-Agent Investment Research Platform

**Last Updated:** December 10, 2025  
**Version:** 1.0  
**Status:** Authoritative Source of Truth

---

## 1. Executive Summary

Multiplium is a multi-agent investment research platform designed for venture capital and family office analysts to discover, validate, and evaluate emerging companies within specific industry sectors. The platform orchestrates three LLM providers (OpenAI GPT, Google Gemini, and Anthropic Claude) to run parallel research discovery sessions, each using native web search capabilities to identify companies matching an investment thesis. Results are deduplicated, validated against configurable KPI frameworks, and persisted to JSON reports. A React dashboard provides partners with a visual interface to review discovered companies, approve/reject candidates, and export findings. The system uses Supabase for persistent data storage across browser sessions and Render.com for cloud deployment.

---

## 2. Core Design Philosophy (Do Not Violate)

These principles are observable in the current implementation and must be preserved:

1. **Provider-Agnostic Tool Layer**: MCP (Model Context Protocol) endpoints expose tools (search, Crunchbase, patents, financials) in a provider-neutral format. All three LLM providers consume the same tool contracts.

2. **Native Search First, MCP Second**: Discovery uses each provider's native web search capability (no API exhaustion). MCP tools (Tavily, Perplexity) are reserved for validation and enrichment only.

3. **Parallel Execution with Convergence Caps**: Providers run in parallel (concurrency=3) with hard limits (max_steps=20) to prevent runaway sessions and force output by turn 18.

4. **Immutable Reports**: Once a research report is written to disk (`reports/`), it is treated as immutable. Updates create new timestamped copies.

5. **Server as Source of Truth**: Project state, reviews, and archived status are stored in Supabase. Browser localStorage is a cache only—never the primary data source.

6. **Configuration-Driven Behavior**: All research parameters (thesis, value chain, KPIs, provider settings) are defined in YAML files under `config/`. No hardcoded research logic.

7. **Structured Logging with Telemetry**: All operations emit structured logs via `structlog`. Telemetry (token usage, tool counts, errors) is captured per provider for cost tracking and debugging.

8. **Separation of Discovery vs. Dashboard**: The Python orchestrator discovers companies and writes reports. The TypeScript/React dashboard reads reports and manages review workflows. They share data via JSON files and REST APIs.

---

## 3. High-Level Architecture

### Major System Components

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Orchestrator** | Python/Typer CLI | Loads config, runs agents, writes reports |
| **Providers** | anthropic, openai-agents, google-genai SDKs | LLM wrappers with native search |
| **Tool Layer** | FastAPI MCP servers | Search, Crunchbase, patents, financials, ESG |
| **Dashboard API** | FastAPI (research_dashboard.py) | Projects, reviews, chat, reports CRUD |
| **Dashboard UI** | React/TypeScript/Vite | Partner-facing review interface |
| **Persistence** | Supabase (Postgres + Storage) | Projects, reviews, frameworks, reports |
| **Deployment** | Render.com | Static site + web services |

### ASCII Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PARTNER BROWSER                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  React Dashboard (multiplium-dashboard)                              │    │
│  │  - Project list, company cards, review workflow                      │    │
│  │  - localStorage cache (secondary)                                    │    │
│  └─────────────────────────┬───────────────────────────────────────────┘    │
└────────────────────────────┼────────────────────────────────────────────────┘
                             │ REST API (X-API-Key auth)
                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DASHBOARD API (research_dashboard.py)                     │
│  - /projects, /projects/{id}/reviews, /projects/{id}/framework              │
│  - /reports, /chat, /runs                                                    │
│  - Supabase sync for persistence                                             │
└─────────────────────────────┬───────────────────────────────────────────────┘
                             │
          ┌──────────────────┴──────────────────┐
          ▼                                      ▼
┌─────────────────────┐              ┌─────────────────────────────────────┐
│  Supabase           │              │  MCP Tool Servers (multiplium-mcp)  │
│  - projects table   │              │  - search (Tavily, Perplexity)      │
│  - reviews table    │              │  - crunchbase, patents, financials  │
│  - frameworks table │              │  - esg, academic, sustainability    │
│  - reports storage  │              └─────────────────────────────────────┘
└─────────────────────┘
                                                 ▲
                                                 │ MCP calls (validation only)
                                                 │
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ORCHESTRATOR (CLI)                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  python -m multiplium.orchestrator --config config/dev.yaml          │    │
│  └─────────────────────────┬───────────────────────────────────────────┘    │
│                            │                                                 │
│         ┌──────────────────┼──────────────────┐                             │
│         ▼                  ▼                  ▼                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                      │
│  │   OpenAI    │    │   Google    │    │  Anthropic  │   (parallel)         │
│  │   GPT-5.1   │    │ Gemini 2.5  │    │ Claude 4.5  │                      │
│  │ native web  │    │  grounding  │    │ web_search  │                      │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                      │
│         │                  │                  │                             │
│         └──────────────────┴──────────────────┘                             │
│                            │                                                 │
│                            ▼                                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Reporting: JSON export to reports/latest_report.json                │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Agent-by-Agent Overview

### 4.1 Orchestrator (`src/multiplium/orchestrator.py`)

- **Role**: CLI entry point that loads configuration, initializes providers, runs parallel discovery, and persists reports.
- **Inputs**: YAML config file (thesis, value chain, KPIs, provider settings)
- **Outputs**: JSON report to `reports/latest_report.json` and timestamped copy
- **Key Files**: `orchestrator.py`, `config.py`, `runs.py`
- **Limitations**: No real-time progress streaming to dashboard (polling-based)

### 4.2 OpenAI Provider (`src/multiplium/providers/openai_provider.py`)

- **Role**: Wraps OpenAI Agents SDK (`Runner`) for discovery with native web browsing
- **Inputs**: AgentContext (thesis, value chain, KPIs), tool schemas
- **Outputs**: `ProviderRunResult` with discovered companies and telemetry
- **Key Files**: `openai_provider.py`, `prompts/discovery.py`
- **Limitations**: Model availability depends on OpenAI account tier

### 4.3 Google Provider (`src/multiplium/providers/google_provider.py`)

- **Role**: Wraps Google GenAI SDK with Google Search grounding for discovery
- **Inputs**: AgentContext, automatic function calling config
- **Outputs**: `ProviderRunResult` with discovered companies
- **Key Files**: `google_provider.py`, `prompts/model_config.py`
- **Limitations**: Gemini 3 thinking mode requires temperature=1.0

### 4.4 Anthropic Provider (`src/multiplium/providers/anthropic_provider.py`)

- **Role**: Wraps Anthropic Messages API with native `web_search` tool
- **Inputs**: AgentContext, web_search tool configuration
- **Outputs**: `ProviderRunResult` with auto-cited companies
- **Key Files**: `anthropic_provider.py`
- **Limitations**: Web search costs $10/1000 searches on top of tokens

### 4.5 Tool Manager (`src/multiplium/tools/manager.py`)

- **Role**: Registers MCP endpoints, provides caching, handles HTTP calls to tool servers
- **Inputs**: Tool specs from config YAML
- **Outputs**: Tool call results (JSON)
- **Key Files**: `manager.py`, `catalog.py`, `contracts.py`, `tavily_mcp.py`, `perplexity_mcp.py`
- **Limitations**: No retry logic for failed tool calls (planned)

### 4.6 Dashboard API (`servers/research_dashboard.py`)

- **Role**: FastAPI backend serving projects, reviews, frameworks, chat, and reports
- **Inputs**: HTTP requests with X-API-Key authentication
- **Outputs**: JSON responses, Supabase sync
- **Key Files**: `research_dashboard.py`
- **Limitations**: Some endpoints fall back to file storage if Supabase unavailable

### 4.7 Dashboard UI (`dashboard/src/`)

- **Role**: React SPA for partners to view projects, review companies, manage workflows
- **Inputs**: REST API responses, localStorage cache
- **Outputs**: User interactions synced to backend
- **Key Files**: `App.tsx`, `hooks/useProjects.ts`, `hooks/useReviews.ts`, `components/ProjectDetailView.tsx`
- **Limitations**: Initial load requires server data; localStorage is cache only

---

## 5. Data Flow & State Management

### Raw Data Origins

1. **Thesis/Value Chain/KPIs**: Markdown files in `data/new/` or `data/discoveries/{id}/`
2. **Web Search Results**: Native LLM search (GPT, Gemini, Claude) during discovery
3. **Enrichment Data**: MCP tools (Crunchbase, patents, financials) during validation

### Data Movement Between Agents

```
Config YAML → Orchestrator → Providers (parallel) → Raw Findings
                                                          │
                                                          ▼
                                              Deduplication + Validation
                                                          │
                                                          ▼
                                              JSON Report (reports/)
                                                          │
                                                          ▼
                                              Dashboard API reads report
                                                          │
                                                          ▼
                                              Supabase (reviews, frameworks)
                                                          │
                                                          ▼
                                              React UI displays to partner
```

### Temporary vs. Persistent State

| Type | Location | Persistence |
|------|----------|-------------|
| Run progress | In-memory (orchestrator) | Lost on restart |
| Provider telemetry | In-memory, logged | Logged only |
| Discovery results | `reports/*.json` | Persistent (immutable) |
| Project metadata | Supabase `projects` table | Persistent |
| Company reviews | Supabase `reviews` table | Persistent |
| Frameworks | Supabase `frameworks` table | Persistent |
| Chat history | `data/chats/*.json` | Persistent |
| Browser cache | localStorage | Cache only, cleared on logout |

### Context Sharing

- Providers do NOT share context during execution (fully parallel)
- Orchestrator collates results after all providers complete
- Dashboard receives merged data via API

---

## 6. Configuration & Environment

### Important Config Files

| File | Purpose |
|------|---------|
| `config/dev.yaml` | Local development configuration |
| `config/prod.yaml` | Production with remote tool endpoints |
| `.env` | API keys (never committed) |
| `.env.example` | Template for required environment variables |
| `render.yaml` | Render.com deployment specification |
| `pyproject.toml` | Python dependencies and project metadata |
| `dashboard/package.json` | React frontend dependencies |

### Environment Variables (Names Only)

**Required:**
- `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` or `GOOGLE_GENAI_API_KEY`
- `TAVILY_API_KEY`
- `DASHBOARD_API_KEY` (for partner authentication)

**Optional:**
- `PERPLEXITY_API_KEY`
- `FMP_API_KEY`
- `CRUNCHBASE_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`

### Runtime Assumptions

1. Python 3.11+ with dependencies from `pyproject.toml`
2. Node.js 18+ for dashboard development
3. `reports/` directory exists and is writable
4. `data/` directory for project metadata and chat history
5. MCP tool servers running (local or Render-deployed)

---

## 7. Known Issues & Current Stabilisation Focus

### Active Issues

1. **Loading Race Condition (Fixed)**: Projects now load from server first; localStorage is cache only. If loading appears stuck, clear localStorage.

2. **Review Status Harmonization (Fixed)**: Removed `needs_review` status that caused counter confusion. Now only: `pending`, `approved`, `rejected`, `maybe`.

3. **Archive Sync**: Archive state syncs to Supabase `archived_projects` table. Table must be created manually if not present.

4. **Report File Access on Render**: Reports in `reports/` are gitignored. For Render to serve them, they must be uploaded to Supabase Storage or committed with `-f` flag.

### Fragile Areas

- Supabase connection errors cause fallback to file storage (silent degradation)
- Provider timeouts set to 90 minutes; long runs may hit this limit
- Dashboard assumes server is source of truth but has stale localStorage handling

### Modules Under Stabilisation

- `hooks/useProjects.ts` - Project loading and sync
- `hooks/useReviews.ts` - Review persistence
- `servers/research_dashboard.py` - Supabase upsert reliability

---

## 8. Safe Change Guidelines

### Safe Changes

- Adding new MCP tool endpoints (follow existing pattern in `tools/`)
- Updating prompts in `prompts/discovery.py` or `prompts/deep_research.py`
- Adding dashboard UI components (follow existing component patterns)
- Modifying CSS styling
- Adding new fields to reports (additive changes)

### Risky Changes (Proceed with Caution)

- Changing `useProjects.ts` or `useReviews.ts` hooks (sync logic is delicate)
- Modifying Supabase table schemas (requires migration)
- Changing provider SDK usage patterns (API changes frequently)
- Altering `orchestrator.py` parallel execution logic

### NEVER Change Without Explicit Approval

1. **Authentication flow** (`ApiKeyPrompt.tsx`, `api.ts` auth functions)
2. **Supabase connection logic** in `research_dashboard.py`
3. **Provider factory initialization** in `providers/factory.py`
4. **Report schema structure** (breaks backward compatibility)
5. **Config YAML schema** (breaks existing configs)

---

## 9. Non-Goals (Prevents Scope Creep)

The following are intentionally NOT part of this system:

1. **Real-time collaboration** - Partners do not see each other's cursors or live edits
2. **User accounts/multi-tenancy** - Single shared API key per deployment
3. **Automated trading/investment execution** - Research only, no financial actions
4. **Provider fine-tuning** - Uses off-the-shelf LLM APIs
5. **Self-hosted LLMs** - Cloud APIs only (OpenAI, Anthropic, Google)
6. **Mobile-native apps** - Web dashboard only
7. **Offline operation** - Requires internet for LLM and tool APIs

---

## 10. Future Ideas (Non-Binding)

The following appear as TODOs or partial implementations:

1. **Consensus Scoring**: Aggregate findings across providers with weighted voting (mentioned in README)
2. **Regression Harness**: Fixture theses with baseline outputs for evaluation (planned in docs)
3. **Cost Governance**: Per-run cost tracking and budgets (telemetry exists, UI not built)
4. **Provider Guardrails**: Output schema validation per provider (partial in prompts)
5. **Deep Research Phase**: Extended research for approved companies (`research/deep_researcher.py` exists)
6. **Financial Enrichment**: Automated financial data pull (`research/financial_enricher.py` exists)
7. **Impact Scoring**: ESG/SDG alignment scoring (`impact_scoring.py` exists)

*These are exploratory and should not be prioritized without explicit direction.*

---

## Appendix: Outdated Documentation to Archive

The following `.md` files were generated by previous agent sessions and are now superseded by this `PROJECT_CONTEXT.md`. They should be moved to `/docs/old/` to prevent confusion:

| File | Reason |
|------|--------|
| `QUICK_REFERENCE.md` | Superseded by PROJECT_CONTEXT.md sections 3-6 |
| `IMPLEMENTATION_SUMMARY.md` | Partial, outdated implementation notes |
| `BUGFIX_SUBPROCESS_HANDLE.md` | Session-specific debugging notes |
| `OPTIMIZATION_SUMMARY.md` | Superseded by ARCHITECTURE_V2.md |
| `DEPLOYMENT.md` | Keep - still accurate for Render deployment |
| `QUICK_START.md` | Superseded by README.md |
| `LAUNCH_READY.md` | Session-specific status report |
| `DEEP_RESEARCH_GUIDE.md` | Keep - useful for deep research phase |
| `COST_OPTIMIZATION.md` | Superseded by ARCHITECTURE_V2.md cost analysis |
| `TEST_REVIEW_GUIDE.md` | Session-specific test notes |
| `TEST_REVIEW_README.md` | Session-specific test notes |
| `NEXT_STEPS.md` | Outdated roadmap |
| `DEEP_RESEARCH_IMPLEMENTATION.md` | Partial implementation notes |
| `EXECUTIVE_SUMMARY.md` | Superseded by PROJECT_CONTEXT.md section 1 |
| `IMPLEMENTATION_COMPLETE.md` | Session-specific status report |
| `DISCOVERY_ENHANCEMENTS_COMPLETE.md` | Session-specific status report |
| `PLATFORM_HARDENING_COMPLETE.md` | Session-specific status report |
| `CLAUDE_OUTPUT_FIX.md` | Session-specific debugging notes |
| `BEFORE_AFTER_COMPARISON.md` | Session-specific comparison |
| `FIX_SUMMARY.md` | Session-specific debugging notes |
| `CLAUDE_DATA_FIX_SUMMARY.md` | Session-specific debugging notes |
| `FULL_RUN_SUMMARY.md` | Session-specific run report |
| `CLAUDE_CACHE_TEST_RESULTS.md` | Session-specific test results |
| `WEBSITE_COUNTRY_FIX.md` | Session-specific debugging notes |
| `CLAUDE_OPTIMIZATION.md` | Session-specific optimization notes |
| `SYSTEMS_VALIDATED.md` | Session-specific validation report |
| `FULL_RUN_ANALYSIS_20251101.md` | Session-specific analysis |
| `FULL_RUN_CONFIG.md` | Superseded by config/dev.yaml |
| `TEST_RUN_CONFIG.md` | Superseded by config/dev.yaml |
| `ARCHITECTURE_V2.md` | Keep - detailed V2 architecture reference |
| `FINAL_ARCHITECTURE_SUMMARY.md` | Keep - detailed V2 summary |
| `IMPROVEMENTS_SUMMARY.md` | Session-specific improvement notes |
| `QUALITY_IMPROVEMENTS.md` | Session-specific notes |
| `PERPLEXITY_MCP_INTEGRATION.md` | Superseded by README.md tools section |
| `FREE_API_ALTERNATIVES.md` | Reference only, not actionable |
| `TAVILY_MCP_INTEGRATION.md` | Superseded by README.md tools section |
| `OPTIMIZATION_SESSION_REPORT.md` | Session-specific report |
| `SUCCESS_REPORT.md` | Session-specific status report |
| `FINAL_STATUS_AND_SUMMARY.md` | Session-specific status report |
| `STATUS_PAUSE_HERE.md` | Session-specific checkpoint |
| `DIAGNOSIS_AND_FIX.md` | Session-specific debugging notes |
| `SYSTEM_STATUS_FINAL.md` | Session-specific status report |
| `TEST_RESULTS.md` | Session-specific test results |
| `FINAL_TEST_STATUS.md` | Session-specific test status |
| `TEST_STATUS.md` | Session-specific test status |
| `FINAL_SUMMARY.md` | Session-specific summary |
| `YOUR_TODO_LIST.md` | Outdated task list |
| `RENDER_DEPLOYMENT.md` | Superseded by DEPLOYMENT.md |
| `TEST_PLAN.md` | Session-specific test plan |
| `SETUP_INSTRUCTIONS.md` | Superseded by README.md |
| `session_context.md` | Session-specific context |

### Recommended Archive Structure

```
/docs/
  /old/
    QUICK_REFERENCE.md
    IMPLEMENTATION_SUMMARY.md
    BUGFIX_SUBPROCESS_HANDLE.md
    OPTIMIZATION_SUMMARY.md
    QUICK_START.md
    LAUNCH_READY.md
    COST_OPTIMIZATION.md
    TEST_REVIEW_GUIDE.md
    TEST_REVIEW_README.md
    NEXT_STEPS.md
    DEEP_RESEARCH_IMPLEMENTATION.md
    EXECUTIVE_SUMMARY.md
    IMPLEMENTATION_COMPLETE.md
    DISCOVERY_ENHANCEMENTS_COMPLETE.md
    PLATFORM_HARDENING_COMPLETE.md
    CLAUDE_OUTPUT_FIX.md
    BEFORE_AFTER_COMPARISON.md
    FIX_SUMMARY.md
    CLAUDE_DATA_FIX_SUMMARY.md
    FULL_RUN_SUMMARY.md
    CLAUDE_CACHE_TEST_RESULTS.md
    WEBSITE_COUNTRY_FIX.md
    CLAUDE_OPTIMIZATION.md
    SYSTEMS_VALIDATED.md
    FULL_RUN_ANALYSIS_20251101.md
    FULL_RUN_CONFIG.md
    TEST_RUN_CONFIG.md
    IMPROVEMENTS_SUMMARY.md
    QUALITY_IMPROVEMENTS.md
    PERPLEXITY_MCP_INTEGRATION.md
    FREE_API_ALTERNATIVES.md
    TAVILY_MCP_INTEGRATION.md
    OPTIMIZATION_SESSION_REPORT.md
    SUCCESS_REPORT.md
    FINAL_STATUS_AND_SUMMARY.md
    STATUS_PAUSE_HERE.md
    DIAGNOSIS_AND_FIX.md
    SYSTEM_STATUS_FINAL.md
    TEST_RESULTS.md
    FINAL_TEST_STATUS.md
    TEST_STATUS.md
    FINAL_SUMMARY.md
    YOUR_TODO_LIST.md
    RENDER_DEPLOYMENT.md
    TEST_PLAN.md
    SETUP_INSTRUCTIONS.md
    session_context.md
```

### Files to KEEP in Root

| File | Reason |
|------|--------|
| `README.md` | Primary project documentation |
| `AGENTS.md` | Repository guidelines for AI agents |
| `DEPLOYMENT.md` | Accurate Render deployment guide |
| `DEEP_RESEARCH_GUIDE.md` | Useful deep research documentation |
| `ARCHITECTURE_V2.md` | Detailed V2 architecture reference |
| `FINAL_ARCHITECTURE_SUMMARY.md` | V2 summary with cost analysis |
| `PROJECT_CONTEXT.md` | **This file - authoritative source of truth** |
| `docs/architecture.md` | Core architecture reference |

### Data Files (Not Documentation)

Files in `data/` directories (thesis.md, kpis.md, value_chain.md) are **content files**, not documentation. They should remain in place as they are consumed by the orchestrator.

---

*This document is the single source of truth for the Multiplium platform architecture. All other documentation should be treated as supplementary or archived.*

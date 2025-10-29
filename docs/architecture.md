# Multiplium Deep Research Architecture

## System Overview
```
Analyst CLI/Web
        │
        ▼
  Orchestrator (Typer CLI)
        │
        ├── Context Loader (thesis, value chain, KPIs)
        ├── Tool Manager (MCP adapters, caching, rate limits)
        ├── Parallel Agent Runners
        │       ├── Claude Messages API + tools
        │       ├── OpenAI Agents SDK (`Runner`)
        │       └── Google GenAI automatic function calling
        └── Reporting (JSON export, telemetry)
```

## Execution Flow
1. Load configuration (`config/*.yaml`) and environment secrets.
2. Build shared tool registry from MCP endpoints (search, fetch, Crunchbase, patents, financials).
3. Hydrate agent context from thesis/value-chain/KPI documents.
4. Launch provider-specific agent wrappers concurrently.
5. Each agent:
   - Registers shared tools with consistent JSON schemas.
   - Iteratively plans, calls tools, and accumulates findings.
   - Emits telemetry (tool count, token usage, errors).
6. Orchestrator collates agent results and persists a consolidated JSON report to disk.

## Tool Layer Strategy
- **MCP Services**: host REST/WebSocket servers per domain, enforcing domain allowlists, credential isolation, and caching.
- **Shared Contracts**: tool schemas captured in `multiplium.tools.contracts.ToolSpec`, enabling reuse across SDKs.
- **Stubs**: `multiplium.tools.stubs` demonstrates placeholders; replace with real adapters.

## Agent Integration Notes
- **Anthropic Claude**: uses the `messages.create` API with tool-use blocks; tool responses are streamed back via `tool_result` blocks before requesting additional turns.
- **OpenAI Agents**: runtime-generated `FunctionTool` instances bridge ToolSpecs into the `Runner` loop; JSON outputs are enforced via system prompts.
- **Google Gemini**: async Python callables are registered directly via `GenerateContentConfig.tools`, enabling automatic function calling and response JSON enforcement.

## Observability & Guardrails
- Structured logging via `structlog` (extend with sinks: stdout, JSON, APM).
- Telemetry captured per provider (token usage, tool counts, status).
- Guardrails per provider:
  - Output schema validation (OpenAI guardrails / Gemini JSON schema).
  - Context window compaction and safety filters (Claude).
  - Domain filtering enforced at tool layer.

## Roadmap Highlights
- Persist tool response ledger and structured findings (e.g., S3/Postgres) for audit.
- Build aggregation layer for consensus scoring and deduplicated company lists.
- Add automated evaluation harness with fixture theses and regression baselines.
- Harden security: secret vault integration, IAM roles, audit logging, cost governance.

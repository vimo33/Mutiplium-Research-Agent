# Multiplium Session Context

## Current State
- CLI orchestrator (`src/multiplium/orchestrator.py`) wraps Typer entrypoint, loads research context from `data/`, fans out across enabled providers, and persists consolidated JSON via `reporting.write_report`.
- Configuration modeled with Pydantic (`src/multiplium/config.py`) and hydrated from YAML (`config/dev.yaml`), including per-provider settings, tool endpoint metadata, and file-system path expansion.
- Provider adapters in `src/multiplium/providers/` implement Anthropic Claude, OpenAI Agents SDK, and Google Gemini integrations with shared dry-run fallbacks, API key resolution, and provider-specific tool bridging.
- Tooling layer centers on `ToolManager` with deterministic caching, domain allowlists, and HTTP client reuse, backed by schemas in `tools/catalog.py` and dry-run stubs in `tools/stubs.py`.
- Reference MCP tool servers live under `servers/`, exposing FastAPI apps for search/fetch (`DuckDuckGo` + direct fetch), organization lookup (OpenAlex), patent search (USPTO PatentsView), and financial metrics (Financial Modeling Prep), with a helper launcher `scripts/start_tool_servers.sh`.
- Sample thesis, value-chain, and KPI inputs live in `data/`; `reports/latest_report.json` captures the most recent run output (currently generated from sample data).
- Project metadata (`pyproject.toml`) targets Python 3.11+, pins core SDK dependencies, and defines optional dev tooling (pytest, ruff, mypy).
- README documents end-to-end setup, including environment variables, server launch commands, and dry-run vs. live execution paths.

## Outstanding Work
- Populate `.env` with Anthropic, OpenAI, Google GenAI, and tool-layer credentials; surface validation errors early during orchestrator launch.
- Stand up long-running MCP services (or containerize) with retries, rate-limit guards, and richer error responses; evaluate caching strategy for API quotas.
- Implement aggregation/consensus module to reconcile provider findings, apply scoring, and flag conflicts prior to analyst review.
- Add structured tests (unit + async integration) covering `ToolManager`, provider adapters (with SDK mocks), config parsing, and server contract behaviors.
- Layer in observability: structured logging enrichment, per-provider/tool cost tracking, and trace IDs across orchestrator + servers.
- Harden report schema (versioning, output validation) and support historical report retention or datastore persistence.

## Operational Notes
- Run `pip install -e .` (or `poetry install`) with Python 3.11+; ensure `PYTHONPATH=src` when invoking scripts.
- Launch tool servers individually with `uvicorn` or via `scripts/start_tool_servers.sh`; requires outbound network access to public APIs.
- Orchestrator accepts `--dry-run` for stubbed tool responses; live mode expects servers online and credentials set.
- Additions pending git history; repository initialization forthcoming so changes can be tracked via commits.

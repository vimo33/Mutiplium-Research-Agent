# Multiplium Session Context

## Current State
- Orchestrator (`src/multiplium/orchestrator.py`) drives Typer CLI execution, loads thesis/value-chain context from `data/`, and now writes both `reports/latest_report.json` and timestamped snapshots via `multiplium.reporting.writer.write_report`.
- Configuration stays centralized in `config/dev.yaml` with per-provider toggles, tool endpoints, and Render-friendly overrides surfaced through environment variables.
- Provider adapters under `src/multiplium/providers/` include OpenAI Agents (primary), Anthropic, and Gemini. OpenAI flow enforces a ≥10 companies per segment target, merges high-confidence seeds from `seed_companies.json`, tracks tool usage, deduplicates results, and now sanitizes agent JSON before parsing to tolerate inline guidance. Gemini now runs on `gemini-2.5-flash` via the `google-genai` client (API version `v1beta1`) with full function-calling support, allowing it to mix native Google Search and all MCP tools; keys are resolved from `GOOGLE_GENAI_API_KEY`, `GOOGLE_API_KEY`, or `GEMINI_API_KEY`.
- MCP tooling stack (`multiplium.tools.manager` + FastAPI servers in `servers/`) underpins search, content fetch, Crunchbase, patents, financial metrics, ESG lookups, and academic research. The combined app (deployed to Render) exposes `/search`, `/crunchbase`, `/patents`, `/financials`, `/esg`, and `/academic` prefixes; `scripts/start_tool_servers.sh` now launches all six services locally (ports 7001–7006). The web-search client integrates Tavily advanced parameters and the Perplexity Search API.
- Seed scaffolding for thin segments lives at repo root (`seed_companies.json`) and is referenced in prompts so seeded vineyard companies carry through outputs.
- README and `AGENTS.md` call out environment preparation, Render deployment steps, and the need to export keys (`OPENAI_API_KEY`, `GOOGLE_GENAI_API_KEY`, `TAVILY_API_KEY`, `PERPLEXITY_API_KEY`, `FMP_API_KEY`) before running live research.
- Test suite now includes pytest-asyncio coverage for the tool manager (`tests/test_tool_manager.py`) plus a unit test for OpenAI JSON sanitization (`tests/test_openai_provider.py`); `tests/conftest.py` wires `src/` onto `sys.path`.
- Additional tool aggregation tests live in `tests/test_search_providers.py`, covering deduplication and optional provider fallbacks.

## Outstanding Work
- Confirm live runs export required API keys locally and on Render—Gemini, Perplexity, Tavily, and FMP are all needed for full coverage.
- Exercise Gemini provider end-to-end using a valid Google AI Studio key (config now targets `gemini-2.5-flash`) and verify function-calling with Google Search + MCP tools.
- Expand seed coverage and source quality for value-chain segments 1 (Soil Health) and 3 (IPM); audit `seed_companies.json` summaries/URLs for accuracy.
- Build regression tests for provider output parsing/tool invocation counting so name normalization and telemetry stay stable.
- Harden Render deployments (retry/backoff, better error messaging) across the expanded tool suite.
- Revisit analyst fusion layer (consensus/scoring) after provider coverage stabilizes.

## Operational Notes
- Preferred workflow: `pip install -e .` (Python 3.11) or reuse `.venv`, then `set -a; source .env; set +a` to export provider keys before running orchestration or servers.
- Local MCP servers start via `PYTHONPATH=src scripts/start_tool_servers.sh`; the Render deployment auto-starts with `pip install -r requirements.txt` and serves FastAPI apps behind `/search`, `/crunchbase`, `/patents`, `/financials`.
- Run `python -m multiplium.orchestrator --config config/dev.yaml --dry-run` for safe smoke tests; omit `--dry-run` for live research (requires remote or local MCP endpoints reachable).
- Reports persist under `reports/`; every live run creates `latest_report.json` plus a timestamped `report_YYYYMMDDTHHMMSSZ.json` for audit trails.
- Before pushing updates, run `ruff check src tests`, `mypy src`, and `pytest`; staging branch is `main` (GitHub remote `https://github.com/vimo33/Multiplium`).

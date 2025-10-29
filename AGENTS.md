# Repository Guidelines

## Project Structure & Module Organization
`src/multiplium/` contains the core Python packages: `agents/` for orchestration flows, `providers/` for Claude/OpenAI/Gemini adapters, `tools/` for shared MCP helpers, and `reporting/` for persistence. Configuration defaults live in `config/`, while `servers/` hosts FastAPI reference implementations for the external tool layer. Use `scripts/` for operational helpers (for example `scripts/start_tool_servers.sh`), keep generated artifacts in `reports/`, and mirror the module layout when adding tests under `tests/`.

## Build, Test, and Development Commands
- `pip install -e .` (or `poetry install`) provisions the runtime dependencies for Python 3.11+.
- `scripts/start_tool_servers.sh` launches the four MCP tool servers with sensible defaults.
- `python -m multiplium.orchestrator --config config/dev.yaml --dry-run` exercises the CLI without hitting live tools.
- `python -m multiplium.orchestrator --config config/dev.yaml` runs a full research pass and writes `reports/latest_report.json`.
- `pytest` executes the unit and async integration suites.
- `ruff check src tests` and `mypy src` enforce formatting and static typing before submitting changes.

## Coding Style & Naming Conventions
Follow the Ruff defaults pinned in `pyproject.toml` (line length 100, Python 3.11 target). Prefer type-annotated `snake_case` functions, `PascalCase` classes, and reserve `ALL_CAPS` for module constants. Keep async boundaries explicit by suffixing internal coroutines with `_async`, and prefer `structlog` for new telemetry. Route new CLI entry points through Typer commands in `src/multiplium/agents/`.

## Testing Guidelines
Use `pytest` with `pytest-asyncio` for async flows and mock outbound HTTP where feasible. Name test modules `test_<module>.py`; keep fixtures in module-scoped factories or under `tests/` as needed. High-leverage scenarios (multi-provider fan-out, report serialization) should assert deterministic JSON output. When adding tool servers, back them with contract tests that stub HTTP responses. Run `pytest`, `ruff`, and `mypy` before requesting review.

## Commit & Pull Request Guidelines
Repository metadata is distributed without a `.git` directory, so write commits in imperative mood with concise scope prefixes (e.g., `agents: add consensus scaffold`). Keep refactors separate from feature work and call out config or secret updates in the body. Pull requests should outline intent, testing evidence, and any orchestration output; link tracking issues and note configuration steps so reviewers can reproduce results.

## Tool Servers & Configuration Tips
Copy `.env.example` to `.env` and populate provider credentials plus optional `FMP_API_KEY`. Keep environment-specific YAML in `config/` and never commit secrets—document overrides in PRs instead. The helper servers tap public APIs; if you add endpoints, document rate limits, error handling, and port assignments alongside the code.

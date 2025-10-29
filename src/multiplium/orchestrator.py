from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog
import typer

from multiplium.config import Settings, load_settings
from multiplium.providers import ProviderFactory, ProviderRunResult
from multiplium.reporting import write_report
from multiplium.tools.manager import ToolManager

cli = typer.Typer(context_settings={"help_option_names": ["-h", "--help"]})
log = structlog.get_logger()


@dataclass
class AgentContext:
    """Shared research context passed into each agent."""

    thesis: str
    value_chain: list[dict[str, Any]]
    kpis: dict[str, list[str]]


async def _load_context(settings: Settings) -> AgentContext:
    thesis_text = settings.orchestrator.thesis_path.read_text(encoding="utf-8")
    value_chain_data = settings.orchestrator.value_chain_path.read_text(encoding="utf-8")
    kpi_data = settings.orchestrator.kpi_path.read_text(encoding="utf-8")

    # TODO: replace with structured loaders (likely YAML/JSON)
    return AgentContext(
        thesis=thesis_text,
        value_chain=[{"raw": value_chain_data}],
        kpis={"raw": [kpi_data]},
    )


async def _run_agents(context: AgentContext, settings: Settings) -> list[ProviderRunResult]:
    tool_manager = ToolManager.from_settings(
        settings.tools,
        dry_run=settings.orchestrator.dry_run,
    )
    provider_factory = ProviderFactory(tool_manager=tool_manager, settings=settings)

    tasks = []
    try:
        for name, provider in provider_factory.iter_active_agents():
            log.info("agent.scheduled", provider=name, model=provider.config.model)
            tasks.append(asyncio.create_task(provider.run(context)))

        if not tasks:
            log.warning("orchestrator.no_providers_enabled")
            return []

        return await asyncio.gather(*tasks, return_exceptions=False)
    finally:
        await tool_manager.aclose()


@cli.command()
def main(
    config: str = typer.Option("config/dev.yaml", "--config", "-c", help="Path to YAML config."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Skip live tool calls for smoke tests."),
) -> None:
    """Run multiplium orchestrator."""

    settings = load_settings(Path(config))
    settings.orchestrator.dry_run = dry_run or settings.orchestrator.dry_run

    log.info("orchestrator.start", config=config, dry_run=settings.orchestrator.dry_run)

    asyncio.run(_main_async(settings))


async def _main_async(settings: Settings) -> None:
    context = await _load_context(settings)
    results = await _run_agents(context, settings)

    try:
        write_report(
            settings.orchestrator.output_path,
            context=context,
            sector=settings.orchestrator.sector,
            provider_results=results,
        )
    except Exception as exc:  # pragma: no cover - persistence shouldn't block run
        log.error("report.write_failed", error=str(exc))

    log.info("orchestrator.completed", results=[r.summary() for r in results])


if __name__ == "__main__":
    cli()

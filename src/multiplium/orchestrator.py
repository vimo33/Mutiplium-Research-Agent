from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog
import typer

from multiplium.config import Settings, load_settings
from multiplium.config_validator import ConfigValidationError, validate_all_on_startup
from multiplium.providers import ProviderFactory, ProviderRunResult
from multiplium.reporting import write_report
from multiplium.tools.manager import ToolManager

# Load .env file explicitly to ensure API keys are available
# This must happen before any provider initialization
try:
    from dotenv import load_dotenv
    # Load from project root (two levels up from this file)
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        structlog.get_logger().debug("orchestrator.env_loaded", path=str(env_path))
except ImportError:
    # Fallback: manually load .env if python-dotenv not installed
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        import os
        for line in env_path.read_text().splitlines():
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip().strip('"').strip("'")
        structlog.get_logger().debug("orchestrator.env_loaded_manual", path=str(env_path))

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


async def _validate_and_enrich_results(
    results: list[ProviderRunResult],
    settings: Settings,
) -> list[ProviderRunResult]:
    """Validate and enrich company findings using MCP tools."""
    from multiplium.validation import CompanyValidator

    log.info("validation.phase_start", provider_count=len(results))

    # Create a new tool manager for validation
    tool_manager = ToolManager.from_settings(settings.tools, dry_run=False)
    validator = CompanyValidator(tool_manager)

    validated_results = []

    try:
        for result in results:
            if not result.findings:
                validated_results.append(result)
                continue

            validated_findings = []
            for finding in result.findings:
                if not isinstance(finding, dict) or "companies" not in finding:
                    validated_findings.append(finding)
                    continue

                segment_name = finding.get("name", "Unknown Segment")
                original_count = len(finding["companies"])

                log.info(
                    "validation.segment_start",
                    provider=result.provider,
                    segment=segment_name,
                    company_count=original_count,
                )

                # Validate and enrich companies
                validated_companies = await validator.validate_and_enrich_companies(
                    finding["companies"],
                    segment_name,
                )

                # Update finding with validated companies
                validated_finding = finding.copy()
                validated_finding["companies"] = validated_companies

                # Update notes with validation summary
                notes = validated_finding.get("notes", [])
                if not isinstance(notes, list):
                    notes = [notes] if notes else []

                validation_summary = (
                    f"Validation: {len(validated_companies)}/{original_count} companies passed quality checks "
                    f"(rejected: {original_count - len(validated_companies)})"
                )
                notes.append(validation_summary)
                validated_finding["notes"] = notes

                validated_findings.append(validated_finding)

                log.info(
                    "validation.segment_complete",
                    provider=result.provider,
                    segment=segment_name,
                    validated=len(validated_companies),
                    rejected=original_count - len(validated_companies),
                )

            # Create new result with validated findings
            validated_result = ProviderRunResult(
                provider=result.provider,
                model=result.model,
                status=result.status,
                findings=validated_findings,
                telemetry=result.telemetry,
            )
            validated_results.append(validated_result)

    finally:
        await tool_manager.aclose()

    log.info("validation.phase_complete", provider_count=len(validated_results))
    return validated_results


@cli.command()
def main(
    config: str = typer.Option("config/dev.yaml", "--config", "-c", help="Path to YAML config."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Skip live tool calls for smoke tests."),
) -> None:
    """Run multiplium orchestrator."""

    settings = load_settings(Path(config))
    settings.orchestrator.dry_run = dry_run or settings.orchestrator.dry_run

    log.info("orchestrator.start", config=config, dry_run=settings.orchestrator.dry_run)
    
    # Validate environment configuration
    try:
        validate_all_on_startup(settings)
    except ConfigValidationError as exc:
        log.error("orchestrator.config_error", error=str(exc))
        raise typer.Exit(code=1) from exc

    asyncio.run(_main_async(settings))


async def _main_async(settings: Settings) -> None:
    context = await _load_context(settings)
    results = await _run_agents(context, settings)

    # Validation phase: Enrich and validate companies using MCP tools
    if not settings.orchestrator.dry_run:
        results = await _validate_and_enrich_results(results, settings)

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

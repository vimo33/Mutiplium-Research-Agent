from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import structlog
import typer

from multiplium.config import Settings, load_settings
from multiplium.config_validator import ConfigValidationError, validate_all_on_startup
from multiplium.providers import ProviderFactory, ProviderRunResult
from multiplium.reporting import write_report
from multiplium.runs import RunRegistry
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


async def _run_agents(
    context: AgentContext,
    settings: Settings,
    *,
    registry: RunRegistry | None = None,
    run_id: str | None = None,
) -> list[ProviderRunResult]:
    tool_manager = ToolManager.from_settings(
        settings.tools,
        dry_run=settings.orchestrator.dry_run,
    )
    provider_factory = ProviderFactory(tool_manager=tool_manager, settings=settings)

    try:
        agents = list(provider_factory.iter_active_agents())
        if registry and run_id:
            registry.register_providers(run_id, [name for name, _ in agents])

        tasks: list[asyncio.Task[ProviderRunResult]] = []

        async def _run_single_provider(name: str, provider) -> ProviderRunResult:
            if registry and run_id:
                registry.set_provider_status(
                    run_id,
                    name,
                    status="running",
                    progress=5.0,
                    message="Discovery started",
                )
            log.info("agent.scheduled", provider=name, model=provider.config.model)
            
            # Add top-level timeout for each provider (90 minutes max)
            # Gemini 3 with thinking mode can take 8-10 minutes per segment × 8 segments = ~80 minutes
            try:
                result = await asyncio.wait_for(
                    provider.run_with_retry(context),
                    timeout=5400.0,  # 90 minutes max per provider
                )
            except asyncio.TimeoutError:
                log.error("provider.timeout", provider=name, timeout_seconds=5400)
                if registry and run_id:
                    registry.set_provider_status(
                        run_id,
                        name,
                        status="timeout",
                        progress=0.0,
                        message="Provider timed out after 90 minutes",
                        error="Provider execution timed out",
                    )
                return ProviderRunResult(
                    provider=name,
                    model=provider.config.model,
                    status="timeout",
                    findings=[],
                    telemetry={"error": "Provider timed out after 90 minutes"},
                )
            company_count = _count_companies(result.findings)
            telemetry = result.telemetry or {}
            tool_calls = telemetry.get("tool_calls") or telemetry.get("tool_uses")
            
            # Extract cost data if available
            cost_data = None
            if result.cost:
                cost_data = result.cost.to_dict()
            
            if registry and run_id:
                registry.set_provider_status(
                    run_id,
                    name,
                    status=result.status or "completed",
                    progress=100.0,
                    message="Discovery complete",
                    tool_calls=tool_calls if isinstance(tool_calls, int) else 0,
                    companies_found=company_count,
                    error="; ".join(result.errors) if result.errors else None,
                    cost_data=cost_data,
                )
                registry.append_event(
                    run_id,
                    "provider.completed",
                    provider=name,
                    status=result.status,
                    companies_found=company_count,
                    tool_calls=tool_calls,
                    cost=cost_data,
                )
            return result

        for name, provider in agents:
            tasks.append(asyncio.create_task(_run_single_provider(name, provider)))

        if not tasks:
            log.warning("orchestrator.no_providers_enabled")
            return []

        # Use return_exceptions=True to ensure individual provider failures
        # don't crash the entire orchestrator - we want partial results
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and convert them to failed ProviderRunResults
        results: list[ProviderRunResult] = []
        for i, result in enumerate(raw_results):
            if isinstance(result, Exception):
                provider_name = agents[i][0]
                provider = agents[i][1]
                error_msg = str(result)
                log.error(
                    "provider.failed_with_exception",
                    provider=provider_name,
                    error=error_msg,
                    error_type=type(result).__name__,
                )
                if registry and run_id:
                    registry.set_provider_status(
                        run_id,
                        provider_name,
                        status="failed",
                        progress=0.0,
                        message=f"Provider failed: {type(result).__name__}",
                        error=error_msg,
                    )
                # Create a failed result so we can continue with other providers
                results.append(
                    ProviderRunResult(
                        provider=provider_name,
                        model=provider.config.model,
                        status="failed",
                        findings=[],
                        telemetry={"error": error_msg},
                        errors=[{"type": type(result).__name__, "message": error_msg}],
                    )
                )
            else:
                results.append(result)
        
        return results
    finally:
        await tool_manager.aclose()


def _count_companies(findings: list[Any]) -> int:
    total = 0
    for finding in findings or []:
        if isinstance(finding, dict) and "companies" in finding and isinstance(
            finding["companies"], list
        ):
            total += len(finding["companies"])
    return total


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
                errors=result.errors,
                retry_count=result.retry_count,
            )
            validated_results.append(validated_result)

    finally:
        await tool_manager.aclose()

    log.info("validation.phase_complete", provider_count=len(validated_results))
    return validated_results


async def _run_deep_research(
    results: list[ProviderRunResult],
    top_n: int = 25,
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """
    Deep research phase for comprehensive investment profiles.
    
    Gathers 9 required data points using Perplexity Pro:
    1. Executive Summary (already have from discovery)
    2. Technology & Value Chain (already have from discovery)
    3. Evidence of Impact (enhanced with deep dive)
    4. Key Clients (enhanced with more references)
    5. Team (NEW - founders, executives, size)
    6. Competitors (NEW - landscape analysis)
    7. Financials (NEW - funding, revenue, 3yr metrics)
    8. Cap Table (NEW - investors, structure)
    9. SWOT (NEW - generated from gathered data)
    
    Cost: ~$0.02 per company (Perplexity Pro research mode)
    Time: ~5-8 minutes per company with 8-10 searches
    
    Args:
        results: Validated provider results from discovery phase
        top_n: Number of top companies to research deeply (default: 25)
    
    Returns:
        Dict with enriched companies and research metadata
    """
    from multiplium.research.deep_researcher import DeepResearcher
    
    log.info(
        "deep_research.start",
        total_providers=len(results),
        target_companies=top_n,
    )
    
    # Collect all companies from all providers
    all_companies = []
    for result in results:
        for finding in result.findings:
            if not isinstance(finding, dict):
                continue
            
            companies = finding.get("companies", [])
            for company in companies:
                if not isinstance(company, dict):
                    continue
                
                # Tag with provider and segment for tracking
                company["_source_provider"] = result.provider
                company["_source_segment"] = finding.get("name", "Unknown")
                all_companies.append(company)
    
    log.info(
        "deep_research.companies_collected",
        total_companies=len(all_companies),
    )
    
    if not all_companies:
        log.warning("deep_research.no_companies", message="No companies found for deep research")
        return {
            "companies": [],
            "stats": {"total": 0, "completed": 0},
            "error": "No companies available for deep research",
        }
    
    # Sort by confidence score (descending)
    sorted_companies = sorted(
        all_companies,
        key=lambda c: c.get("confidence_0to1", 0) if isinstance(c, dict) else 0,
        reverse=True,
    )
    
    # Take top N
    top_companies = sorted_companies[:top_n]
    
    log.info(
        "deep_research.selection",
        selected=len(top_companies),
        min_confidence=top_companies[-1].get("confidence_0to1", 0) if top_companies else 0,
        max_confidence=top_companies[0].get("confidence_0to1", 0) if top_companies else 0,
    )
    
    # Run deep research in parallel batches
    researcher = DeepResearcher()
    enriched_companies = await researcher.research_batch(
        top_companies,
        max_concurrent=5,  # Process 5 companies at a time
        depth="full",  # Full depth: 8-10 searches per company
        progress_callback=progress_callback,
    )
    
    # Calculate summary statistics
    completed = sum(
        1 for c in enriched_companies 
        if isinstance(c, dict) and c.get("deep_research_status") == "completed"
    )
    has_financials = sum(
        1 for c in enriched_companies 
        if isinstance(c, dict) and c.get("financials") and c.get("financials") != "Not Disclosed"
    )
    has_team = sum(
        1 for c in enriched_companies 
        if isinstance(c, dict) and c.get("team")
    )
    has_competitors = sum(
        1 for c in enriched_companies 
        if isinstance(c, dict) and c.get("competitors")
    )
    has_swot = sum(
        1 for c in enriched_companies 
        if isinstance(c, dict) and c.get("swot")
    )
    
    return _finalize_deep_research(enriched_companies, completed, has_financials, has_team, has_competitors, has_swot)


async def _run_deep_research_on_companies(
    companies: list[dict[str, Any]],
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """Run deep research directly on a list of companies (for report-based deep research)."""
    from multiplium.research.deep_researcher import DeepResearcher
    
    log.info("deep_research.start_from_list", total_companies=len(companies))
    
    if not companies:
        return {
            "companies": [],
            "stats": {"total": 0, "completed": 0},
            "error": "No companies provided",
        }
    
    # Run deep research in parallel batches
    researcher = DeepResearcher()
    enriched_companies = await researcher.research_batch(
        companies,
        max_concurrent=5,
        depth="full",
        progress_callback=progress_callback,
    )
    
    # Calculate statistics
    completed = sum(
        1 for c in enriched_companies 
        if isinstance(c, dict) and c.get("deep_research_status") == "completed"
    )
    has_financials = sum(
        1 for c in enriched_companies 
        if isinstance(c, dict) and c.get("financials") and c.get("financials") != "Not Disclosed"
    )
    has_team = sum(
        1 for c in enriched_companies 
        if isinstance(c, dict) and c.get("team")
    )
    has_competitors = sum(
        1 for c in enriched_companies 
        if isinstance(c, dict) and c.get("competitors")
    )
    has_swot = sum(
        1 for c in enriched_companies 
        if isinstance(c, dict) and c.get("swot")
    )
    
    return _finalize_deep_research(enriched_companies, completed, has_financials, has_team, has_competitors, has_swot)


def _finalize_deep_research(
    enriched_companies: list[dict[str, Any]],
    completed: int,
    has_financials: int,
    has_team: int,
    has_competitors: int,
    has_swot: int,
) -> dict[str, Any]:
    """Finalize deep research results with statistics."""
    log.info(
        "deep_research.complete",
        total=len(enriched_companies),
        completed=completed,
        has_financials=has_financials,
        has_team=has_team,
        has_competitors=has_competitors,
        has_swot=has_swot,
    )
    
    return {
        "companies": enriched_companies,
        "methodology": "Perplexity Pro research (8-10 searches per company) + free APIs (OpenCorporates)",
        "cost_per_company": 0.02,
        "total_cost": len(enriched_companies) * 0.02,
        "stats": {
            "total": len(enriched_companies),
            "completed": completed,
            "has_financials": has_financials,
            "has_team": has_team,
            "has_competitors": has_competitors,
            "has_swot": has_swot,
            "data_completeness_pct": round((has_financials + has_team + has_competitors + has_swot) / (len(enriched_companies) * 4) * 100, 1) if enriched_companies else 0,
        },
    }


async def _deep_research_from_report(
    settings: Settings,
    report_path: Path,
    top_n: int,
    selected_companies: list[str] | None = None,
    run_id_override: str | None = None,
    project_id_override: str | None = None,
) -> None:
    """Run deep research on companies from an existing discovery report."""
    import json
    from multiplium.reporting.writer import write_report
    
    # Load existing report
    if not report_path.exists():
        log.error("report.not_found", path=str(report_path))
        raise FileNotFoundError(f"Report not found: {report_path}")
    
    with report_path.open("r") as f:
        report_data = json.load(f)
    
    log.info("orchestrator.loading_report", path=str(report_path))
    
    # Extract companies from the report
    all_companies = []
    for provider_result in report_data.get("providers", []):
        for finding in provider_result.get("findings", []):
            companies = finding.get("companies", [])
            all_companies.extend(companies)
    
    if not all_companies:
        log.warning("orchestrator.no_companies_in_report")
        return
    
    # Filter by selected company names if provided
    if selected_companies:
        selected_set = set(c.lower() for c in selected_companies)
        top_companies = [
            c for c in all_companies
            if c.get("company", "").lower() in selected_set
        ][:top_n]
        log.info(
            "orchestrator.filtered_by_selection",
            requested=len(selected_companies),
            matched=len(top_companies),
        )
    else:
        # Sort by confidence and take top N
        top_companies = sorted(
            all_companies,
            key=lambda c: c.get("confidence_0to1", 0),
            reverse=True,
        )[:top_n]
    
    log.info(
        "orchestrator.deep_research_from_report",
        total_companies=len(all_companies),
        selected=len(top_companies),
    )
    
    # Initialize registry
    registry = RunRegistry()
    run_id = run_id_override or uuid.uuid4().hex
    project_id = project_id_override or f"deep-research-{report_path.stem}"
    
    registry.create_run(
        project_id=project_id,
        config_path=str(report_path),
        params={
            "source_report": str(report_path),
            "deep_research": True,
            "top_n": top_n,
        },
        run_id=run_id,
    )
    
    try:
        registry.mark_phase(run_id, "deep_research", 10.0)
        registry.update_snapshot(run_id, status="running")
        
        # Create progress callback for real-time UI updates
        def on_progress(completed: int, total: int) -> None:
            # Scale progress from 10% to 95%
            percent = 10.0 + (completed / total) * 85.0
            registry.mark_phase(run_id, "deep_research", percent)
        
        # Run deep research with progress callback
        deep_research_data = await _run_deep_research_on_companies(
            top_companies,
            progress_callback=on_progress,
        )
        
        registry.mark_phase(run_id, "deep_research_complete", 95.0)
        
        # Write enhanced report to deep_research folder
        output_path = settings.orchestrator.output_path
        # Create deep_research folder path
        deep_research_folder = output_path.parent / "deep_research"
        deep_research_folder.mkdir(parents=True, exist_ok=True)
        
        # Generate output filename from source report
        output_filename = f"deep_research_{report_path.stem}_{run_id[:8]}.json"
        output_path = deep_research_folder / output_filename
        
        # Reconstruct minimal report structure
        write_report(
            output_path,
            context=report_data.get("context", {}),
            sector=report_data.get("sector", "unknown"),
            provider_results=[],  # Skip discovery data, only include deep research
            deep_research=deep_research_data,
        )
        
        registry.complete_run(run_id, report_path=str(output_path))
        log.info("orchestrator.deep_research_complete", report_path=str(output_path))
        
    except Exception as exc:
        registry.fail_run(run_id, error=str(exc))
        raise


async def _main_async(
    settings: Settings,
    *,
    config_path: Path,
    deep_research: bool = False,
    top_n: int = 25,
    run_id_override: str | None = None,
    project_id_override: str | None = None,
) -> None:
    registry = RunRegistry()
    project_id = project_id_override or (
        (settings.orchestrator.sector or config_path.stem)
        .lower()
        .replace(" ", "-")
        .replace("/", "-")
    )
    if run_id_override and registry.snapshot_exists(run_id_override):
        run_snapshot = registry.update_snapshot(
            run_id_override,
            project_id=project_id,
            config_path=str(config_path),
            params={"deep_research": deep_research, "top_n": top_n},
            status="running",
            phase="init",
            percent_complete=0.0,
            report_path=None,
            finished_at=None,
        )
        run_id = run_snapshot.run_id
    else:
        run_snapshot = registry.create_run(
            project_id=project_id,
            config_path=str(config_path),
            params={"deep_research": deep_research, "top_n": top_n},
            run_id=run_id_override,
        )
        run_id = run_snapshot.run_id
    registry.append_event(
        run_id,
        "run.started",
        config=str(config_path),
        deep_research=deep_research,
        top_n=top_n,
    )
    registry.mark_phase(run_id, "context_loading", 5.0)

    try:
        context = await _load_context(settings)
        registry.mark_phase(run_id, "discovery", 15.0)
        results = await _run_agents(
            context,
            settings,
            registry=registry,
            run_id=run_id,
        )
        registry.mark_phase(run_id, "discovery_complete", 55.0)

        # Validation phase: Enrich and validate companies using MCP tools
        if not settings.orchestrator.dry_run:
            registry.mark_phase(run_id, "validation", 60.0)
            results = await _validate_and_enrich_results(results, settings)
            registry.mark_phase(run_id, "validation_complete", 75.0)

        # Deep research phase: Comprehensive profiles for top N companies
        deep_research_data = None
        if deep_research and not settings.orchestrator.dry_run:
            registry.mark_phase(run_id, "deep_research", 80.0)
            registry.update_snapshot(run_id, status="running")
            
            # Create progress callback for real-time UI updates
            def on_deep_research_progress(completed: int, total: int) -> None:
                # Scale progress from 80% to 95%
                percent = 80.0 + (completed / total) * 15.0
                registry.mark_phase(run_id, "deep_research", percent)
            
            deep_research_data = await _run_deep_research(
                results, top_n, progress_callback=on_deep_research_progress
            )
            registry.mark_phase(run_id, "deep_research_complete", 95.0)
        else:
            deep_research_data = None

        # Determine output path based on whether deep research was performed
        if deep_research and deep_research_data:
            # Save to deep_research folder with descriptive name
            deep_research_folder = settings.orchestrator.output_path.parent / "deep_research"
            deep_research_folder.mkdir(parents=True, exist_ok=True)
            output_path = deep_research_folder / f"deep_research_{run_id[:8]}.json"
        else:
            # Regular discovery report goes to default location
            output_path = settings.orchestrator.output_path

        try:
            write_report(
                output_path,
                context=context,
                sector=settings.orchestrator.sector,
                provider_results=results,
                deep_research=deep_research_data,
            )
        except Exception as exc:  # pragma: no cover - persistence shouldn't block run
            log.error("report.write_failed", error=str(exc))

        registry.complete_run(
            run_id,
            report_path=str(output_path),
        )
        log.info("orchestrator.completed", results=[r.summary() for r in results])
    except Exception as exc:
        registry.complete_run(run_id, error=str(exc))
        raise


@cli.command()
def main(
    config: str = typer.Option("config/dev.yaml", "--config", "-c", help="Path to YAML config."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Skip live tool calls for smoke tests."),
    deep_research: bool = typer.Option(False, "--deep-research", help="Enable deep research phase for top N companies."),
    top_n: int = typer.Option(25, "--top-n", help="Number of companies to research deeply (default: 25)."),
    from_report: str | None = typer.Option(None, "--from-report", help="Load companies from existing report and run deep research only."),
    companies: str | None = typer.Option(None, "--companies", help="JSON list of company names to research (used with --from-report)."),
    run_id: str | None = typer.Option(None, "--run-id", help="Use a pre-allocated run identifier (for dashboard launches)."),
    project_id: str | None = typer.Option(None, "--project-id", help="Override project identifier used in registry."),
) -> None:
    """Run multiplium orchestrator with optional deep research."""

    config_path = Path(config)
    settings = load_settings(config_path)
    settings.orchestrator.dry_run = dry_run or settings.orchestrator.dry_run

    log.info("orchestrator.start", config=config, dry_run=settings.orchestrator.dry_run, deep_research=deep_research, from_report=from_report)
    
    # Parse companies list if provided
    selected_companies: list[str] | None = None
    if companies:
        try:
            import json
            selected_companies = json.loads(companies)
            if not isinstance(selected_companies, list):
                raise ValueError("Companies must be a JSON list of strings")
        except (json.JSONDecodeError, ValueError) as e:
            log.error("orchestrator.invalid_companies", error=str(e))
            raise typer.Exit(code=1) from e
    
    # Validate environment configuration
    try:
        validate_all_on_startup(settings)
    except ConfigValidationError as exc:
        log.error("orchestrator.config_error", error=str(exc))
        raise typer.Exit(code=1) from exc

    try:
        if from_report:
            # Run deep research only on existing report
            asyncio.run(
                _deep_research_from_report(
                    settings,
                    report_path=Path(from_report),
                    top_n=top_n,
                    selected_companies=selected_companies,
                    run_id_override=run_id,
                    project_id_override=project_id,
                )
            )
        else:
            # Run full discovery + optional deep research
            asyncio.run(
                _main_async(
                    settings,
                    config_path=config_path,
                    deep_research=deep_research,
                    top_n=top_n,
                    run_id_override=run_id,
                    project_id_override=project_id,
                )
            )
    except Exception as exc:  # pragma: no cover - top-level logging for dashboard
        log.error("orchestrator.unhandled_exception", error=str(exc))
        raise


if __name__ == "__main__":
    cli()

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from multiplium.runs import RunRegistry

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]

app = FastAPI(title="Multiplium Research Dashboard API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

registry = RunRegistry(workspace_root=WORKSPACE_ROOT)


class RunCreateRequest(BaseModel):
    project_id: str | None = Field(default=None, description="Logical project grouping")
    config_path: str = Field(default="config/dev.yaml", description="Path to orchestrator config")
    deep_research: bool = Field(default=False)
    top_n: int = Field(default=25, ge=1)
    dry_run: bool = Field(default=False)


class DeepResearchRequest(BaseModel):
    report_path: str = Field(description="Path to the discovery report JSON file")
    top_n: int = Field(default=25, ge=1, description="Number of top companies to research")
    config_path: str = Field(default="config/dev.yaml", description="Path to orchestrator config")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/runs")
def list_runs(limit: int = 50) -> dict[str, list[dict[str, object]]]:
    snapshots = registry.list_snapshots(limit=limit)
    return {"runs": [snapshot.to_dict() for snapshot in snapshots]}


@app.get("/runs/{run_id}")
def get_run(run_id: str) -> dict[str, object]:
    if not registry.snapshot_exists(run_id):
        raise HTTPException(status_code=404, detail="Run not found")
    snapshot = registry.load_snapshot(run_id)
    return snapshot.to_dict()


@app.get("/runs/{run_id}/events")
def get_run_events(run_id: str, limit: int = 200) -> dict[str, list[dict[str, object]]]:
    if not registry.snapshot_exists(run_id):
        raise HTTPException(status_code=404, detail="Run not found")
    return {"events": registry.load_events(run_id, limit=limit)}


@app.get("/reports")
def list_reports() -> dict[str, list[dict[str, object]]]:
    """List all available research reports (both discovery and deep research)."""
    reports = []
    
    # List discovery reports from reports/new/
    reports_dir = WORKSPACE_ROOT / "reports" / "new"
    if reports_dir.exists():
        for report_file in sorted(reports_dir.glob("report_*.json"), reverse=True):
            try:
                with report_file.open("r") as f:
                    data = json.load(f)
                
                # Extract summary info
                total_companies = 0
                for provider in data.get("providers", []):
                    for finding in provider.get("findings", []):
                        total_companies += len(finding.get("companies", []))
                
                reports.append({
                    "path": str(report_file.relative_to(WORKSPACE_ROOT)),
                    "filename": report_file.name,
                    "timestamp": data.get("timestamp", ""),
                    "total_companies": total_companies,
                    "has_deep_research": bool(data.get("deep_research")),
                    "providers": [p.get("provider", "") for p in data.get("providers", [])],
                    "report_type": "discovery",
                })
            except Exception:
                # Skip invalid reports
                continue
    
    # List deep research reports from reports/deep_research/
    deep_research_dir = WORKSPACE_ROOT / "reports" / "deep_research"
    if deep_research_dir.exists():
        for report_file in sorted(deep_research_dir.glob("deep_research_*.json"), reverse=True):
            try:
                with report_file.open("r") as f:
                    data = json.load(f)
                
                # Extract summary info from deep research section
                total_companies = 0
                if "deep_research" in data:
                    companies = data["deep_research"].get("companies", [])
                    total_companies = len(companies)
                
                reports.append({
                    "path": str(report_file.relative_to(WORKSPACE_ROOT)),
                    "filename": report_file.name,
                    "timestamp": data.get("generated_at", data.get("timestamp", "")),
                    "total_companies": total_companies,
                    "has_deep_research": True,
                    "providers": ["deep_research"],
                    "report_type": "deep_research",
                })
            except Exception:
                # Skip invalid reports
                continue
    
    # Also check deep_research/new/ for newer reports
    deep_research_new_dir = WORKSPACE_ROOT / "reports" / "deep_research" / "new"
    if deep_research_new_dir.exists():
        for report_file in sorted(deep_research_new_dir.glob("report_*.json"), reverse=True):
            try:
                with report_file.open("r") as f:
                    data = json.load(f)
                
                # Extract summary info from deep research section
                total_companies = 0
                if "deep_research" in data:
                    companies = data["deep_research"].get("companies", [])
                    total_companies = len(companies)
                
                reports.append({
                    "path": str(report_file.relative_to(WORKSPACE_ROOT)),
                    "filename": report_file.name,
                    "timestamp": data.get("generated_at", data.get("timestamp", "")),
                    "total_companies": total_companies,
                    "has_deep_research": True,
                    "providers": ["deep_research"],
                    "report_type": "deep_research",
                })
            except Exception:
                # Skip invalid reports
                continue
    
    return {"reports": reports}


@app.get("/reports/{report_path:path}/raw")
def get_report_raw(report_path: str) -> dict[str, object]:
    """Fetch raw JSON data from a report file."""
    report_file = WORKSPACE_ROOT / report_path
    
    if not report_file.exists():
        raise HTTPException(status_code=404, detail=f"Report not found: {report_path}")
    
    if not report_file.suffix == ".json":
        raise HTTPException(status_code=400, detail="Only JSON reports are supported")
    
    # Security check: ensure path is within reports directory
    try:
        report_file.resolve().relative_to((WORKSPACE_ROOT / "reports").resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        with report_file.open("r") as f:
            data = json.load(f)
        return data
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid JSON in report file")


@app.post("/runs", status_code=201)
def create_run(request: RunCreateRequest) -> dict[str, object]:
    run_id = uuid.uuid4().hex
    config_path = WORKSPACE_ROOT / request.config_path
    if not config_path.exists():
        raise HTTPException(status_code=400, detail=f"Config not found: {config_path}")

    # Pre-create snapshot so UI can display queued run immediately
    registry.create_run(
        project_id=request.project_id or config_path.stem,
        config_path=str(config_path),
        params={
            "deep_research": request.deep_research,
            "top_n": request.top_n,
            "dry_run": request.dry_run,
        },
        run_id=run_id,
    )

    cmd = [
        sys.executable,
        "-m",
        "multiplium.orchestrator",
        "--config",
        str(config_path),
        "--top-n",
        str(request.top_n),
        "--run-id",
        run_id,
        "--project-id",
        request.project_id or config_path.stem,
    ]

    if request.deep_research:
        cmd.append("--deep-research")
    if request.dry_run:
        cmd.append("--dry-run")

    stdout_path = registry.stdout_path(run_id)
    env = os.environ.copy()
    
    # Open file handle for subprocess (will be inherited and remain open)
    stdout_handle = stdout_path.open("w", encoding="utf-8", buffering=1)  # Line buffered

    subprocess.Popen(
        cmd,
        cwd=str(WORKSPACE_ROOT),
        stdout=stdout_handle,
        stderr=stdout_handle,
        env=env,
        start_new_session=True,  # Detach from parent process
        close_fds=False,  # Keep file descriptors open
    )
    
    # Don't close handle - subprocess needs it
    # Handle will be closed when subprocess finishes

    snapshot = registry.load_snapshot(run_id)
    return {"run": snapshot.to_dict()}


@app.post("/deep-research", status_code=201)
def create_deep_research(request: DeepResearchRequest) -> dict[str, object]:
    """Launch deep research from an existing discovery report."""
    run_id = uuid.uuid4().hex
    report_path = WORKSPACE_ROOT / request.report_path
    
    if not report_path.exists():
        raise HTTPException(status_code=400, detail=f"Report not found: {report_path}")
    
    config_path = WORKSPACE_ROOT / request.config_path
    if not config_path.exists():
        raise HTTPException(status_code=400, detail=f"Config not found: {config_path}")
    
    # Pre-create snapshot
    registry.create_run(
        project_id=f"deep-research-{report_path.stem}",
        config_path=str(config_path),
        params={
            "deep_research": True,
            "top_n": request.top_n,
            "source_report": str(report_path),
        },
        run_id=run_id,
    )
    
    # Launch orchestrator with deep research on existing report
    cmd = [
        sys.executable,
        "-m",
        "multiplium.orchestrator",
        "--config",
        str(config_path),
        "--deep-research",
        "--top-n",
        str(request.top_n),
        "--from-report",
        str(report_path),
        "--run-id",
        run_id,
        "--project-id",
        f"deep-research-{report_path.stem}",
    ]
    
    stdout_path = registry.stdout_path(run_id)
    env = os.environ.copy()
    
    # Open file handle for subprocess (will be inherited and remain open)
    stdout_handle = stdout_path.open("w", encoding="utf-8", buffering=1)  # Line buffered
    
    subprocess.Popen(
        cmd,
        cwd=str(WORKSPACE_ROOT),
        stdout=stdout_handle,
        stderr=stdout_handle,
        env=env,
        start_new_session=True,  # Detach from parent process
        close_fds=False,  # Keep file descriptors open
    )
    
    # Don't close handle - subprocess needs it
    # Handle will be closed when subprocess finishes
    
    snapshot = registry.load_snapshot(run_id)
    return {"run": snapshot.to_dict()}


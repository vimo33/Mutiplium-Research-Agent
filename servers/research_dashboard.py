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


class EnrichRequest(BaseModel):
    company_name: str = Field(description="Name of the company to enrich")
    existing_data: dict = Field(default={}, description="Existing company data")
    fields_to_enrich: list[str] = Field(default=[], description="Fields to fetch: website, team, financials, swot")


# ============================================================================
# Project System Models
# ============================================================================

class ResearchBrief(BaseModel):
    objective: str = Field(description="Research objective description")
    target_stages: list[str] = Field(default=[], description="Target company stages")
    investment_size: str = Field(default="", description="Target investment size")
    geography: list[str] = Field(default=[], description="Geographic focus")
    technologies: list[str] = Field(default=[], description="Target technologies")
    additional_notes: str = Field(default="", description="Additional notes")


class KPI(BaseModel):
    name: str
    target: str = ""
    rationale: str = ""


class ValueChainSegment(BaseModel):
    segment: str
    description: str = ""


class ResearchFramework(BaseModel):
    thesis: str = ""
    kpis: list[KPI] = Field(default=[])
    value_chain: list[ValueChainSegment] = Field(default=[])


class ProjectStats(BaseModel):
    total_companies: int = 0
    enriched_companies: int = 0
    approved: int = 0
    rejected: int = 0
    maybe: int = 0
    pending: int = 0
    flagged: int = 0


class ProjectCreateRequest(BaseModel):
    client_name: str = Field(description="Client/organization name")
    project_name: str = Field(description="Project name")
    brief: ResearchBrief = Field(description="Research brief")


class ProjectUpdateRequest(BaseModel):
    client_name: str | None = None
    project_name: str | None = None
    brief: ResearchBrief | None = None
    framework: ResearchFramework | None = None
    status: str | None = None
    report_path: str | None = None
    stats: ProjectStats | None = None


class EnrichBriefRequest(BaseModel):
    objective: str = Field(description="Research objective to enrich")


class GenerateFrameworkRequest(BaseModel):
    brief: ResearchBrief = Field(description="Research brief to generate framework from")
    answers: dict = Field(default={}, description="Answers to clarifying questions")


# Project storage (in-memory for now, would be DB in production)
PROJECTS_FILE = WORKSPACE_ROOT / "data" / "projects.json"


def load_projects() -> dict[str, dict]:
    """Load projects from JSON file."""
    if PROJECTS_FILE.exists():
        try:
            with PROJECTS_FILE.open("r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_projects(projects: dict[str, dict]) -> None:
    """Save projects to JSON file."""
    PROJECTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with PROJECTS_FILE.open("w") as f:
        json.dump(projects, f, indent=2)


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


# ============================================================================
# Project Endpoints
# ============================================================================

@app.get("/projects")
def list_projects() -> dict[str, list[dict]]:
    """List all research projects."""
    projects = load_projects()
    return {"projects": list(projects.values())}


@app.post("/projects", status_code=201)
def create_project(request: ProjectCreateRequest) -> dict[str, dict]:
    """Create a new research project."""
    from datetime import datetime
    
    project_id = uuid.uuid4().hex[:12]
    now = datetime.utcnow().isoformat() + "Z"
    
    project = {
        "id": project_id,
        "client_name": request.client_name,
        "project_name": request.project_name,
        "brief": request.brief.model_dump(),
        "framework": {"thesis": "", "kpis": [], "value_chain": []},
        "status": "draft",
        "report_path": None,
        "test_run_report_path": None,
        "stats": {
            "total_companies": 0,
            "enriched_companies": 0,
            "approved": 0,
            "rejected": 0,
            "maybe": 0,
            "pending": 0,
            "flagged": 0,
        },
        "created_at": now,
        "updated_at": now,
    }
    
    projects = load_projects()
    projects[project_id] = project
    save_projects(projects)
    
    return {"project": project}


@app.get("/projects/{project_id}")
def get_project(project_id: str) -> dict[str, dict]:
    """Get a single project by ID."""
    projects = load_projects()
    if project_id not in projects:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"project": projects[project_id]}


@app.put("/projects/{project_id}")
def update_project(project_id: str, request: ProjectUpdateRequest) -> dict[str, dict]:
    """Update a project."""
    from datetime import datetime
    
    projects = load_projects()
    if project_id not in projects:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project = projects[project_id]
    
    if request.client_name is not None:
        project["client_name"] = request.client_name
    if request.project_name is not None:
        project["project_name"] = request.project_name
    if request.brief is not None:
        project["brief"] = request.brief.model_dump()
    if request.framework is not None:
        project["framework"] = request.framework.model_dump()
    if request.status is not None:
        project["status"] = request.status
    if request.report_path is not None:
        project["report_path"] = request.report_path
    if request.stats is not None:
        project["stats"] = request.stats.model_dump()
    
    project["updated_at"] = datetime.utcnow().isoformat() + "Z"
    
    projects[project_id] = project
    save_projects(projects)
    
    return {"project": project}


@app.delete("/projects/{project_id}")
def delete_project(project_id: str) -> dict[str, str]:
    """Delete a project."""
    projects = load_projects()
    if project_id not in projects:
        raise HTTPException(status_code=404, detail="Project not found")
    
    del projects[project_id]
    save_projects(projects)
    
    return {"status": "deleted"}


@app.post("/projects/{project_id}/enrich-brief")
async def enrich_project_brief(project_id: str, request: EnrichBriefRequest) -> dict[str, object]:
    """Use GPT to generate clarifying questions based on the research brief."""
    from openai import AsyncOpenAI
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")
    
    client = AsyncOpenAI(api_key=api_key)
    
    prompt = f"""Based on this investment research objective, generate 4-5 clarifying questions to better understand the research scope:

Research Objective: {request.objective}

Generate questions about:
1. Target company stages (seed, series A, etc.)
2. Investment size preferences
3. Geographic focus
4. Business model preferences
5. Any specific technologies or trends to focus on

Return as JSON array with this structure:
[
  {{
    "id": "unique_id",
    "question": "The question text",
    "type": "single_choice" | "multiple_choice" | "text",
    "options": ["option1", "option2"] // only for choice types
  }}
]
"""

    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an investment research assistant helping to scope research projects."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            max_tokens=800,
        )
        
        result = json.loads(response.choices[0].message.content or '{"questions": []}')
        return {"questions": result.get("questions", result if isinstance(result, list) else [])}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Brief enrichment failed: {str(e)}")


@app.post("/projects/{project_id}/generate-framework")
async def generate_project_framework(project_id: str, request: GenerateFrameworkRequest) -> dict[str, object]:
    """Use GPT to generate investment thesis, KPIs, and value chain segments."""
    from openai import AsyncOpenAI
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")
    
    client = AsyncOpenAI(api_key=api_key)
    
    brief = request.brief
    answers = request.answers
    
    prompt = f"""Generate an investment research framework based on this brief:

Research Objective: {brief.objective}
Target Stages: {', '.join(brief.target_stages) if brief.target_stages else 'Not specified'}
Investment Size: {brief.investment_size or 'Not specified'}
Geography: {', '.join(brief.geography) if brief.geography else 'Not specified'}
Technologies: {', '.join(brief.technologies) if brief.technologies else 'Not specified'}

Additional Context from Questions:
{json.dumps(answers, indent=2)}

Generate:
1. Investment Thesis (2-3 paragraphs explaining the opportunity)
2. Key Performance Indicators (4-6 KPIs with targets)
3. Value Chain Segments (6-8 segments to search for companies)

Return as JSON:
{{
  "thesis": "The investment thesis text...",
  "kpis": [
    {{"name": "KPI Name", "target": ">50%", "rationale": "Why this matters"}}
  ],
  "value_chain": [
    {{"segment": "Segment Name", "description": "What this segment covers"}}
  ]
}}
"""

    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert investment analyst helping to structure research projects for venture capital and private equity firms."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            max_tokens=1500,
        )
        
        result = json.loads(response.choices[0].message.content or "{}")
        
        # Update project with generated framework
        projects = load_projects()
        if project_id in projects:
            from datetime import datetime
            projects[project_id]["framework"] = result
            projects[project_id]["updated_at"] = datetime.utcnow().isoformat() + "Z"
            save_projects(projects)
        
        return {"framework": result}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Framework generation failed: {str(e)}")


@app.post("/projects/{project_id}/start-test-run")
def start_project_test_run(project_id: str) -> dict[str, object]:
    """Start a test run (3 companies per segment) for a project."""
    from datetime import datetime
    
    projects = load_projects()
    if project_id not in projects:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project = projects[project_id]
    
    # Update project status
    project["status"] = "test_run"
    project["updated_at"] = datetime.utcnow().isoformat() + "Z"
    save_projects(projects)
    
    # In production, this would launch the actual research
    # For now, return success and the frontend will poll for updates
    return {
        "status": "started",
        "message": "Test run started (3 companies per segment)",
        "project_id": project_id,
    }


@app.post("/projects/{project_id}/approve-test-run")
def approve_project_test_run(project_id: str) -> dict[str, object]:
    """Approve test run and start full research."""
    from datetime import datetime
    
    projects = load_projects()
    if project_id not in projects:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project = projects[project_id]
    
    if project["status"] != "pending_approval":
        raise HTTPException(status_code=400, detail="Project is not pending approval")
    
    # Update project status
    project["status"] = "researching"
    project["updated_at"] = datetime.utcnow().isoformat() + "Z"
    save_projects(projects)
    
    # In production, this would launch the full research run
    return {
        "status": "started",
        "message": "Full research run started",
        "project_id": project_id,
    }


# ============================================================================
# Company Enrichment Endpoint
# ============================================================================

@app.post("/enrich")
async def enrich_company(request: EnrichRequest) -> dict[str, object]:
    """
    Enrich company data using GPT-4o with native tool calling.
    
    This endpoint uses the OpenAI API to fetch missing company information
    like website, team details, financials, etc.
    """
    from openai import AsyncOpenAI
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")
    
    client = AsyncOpenAI(api_key=api_key)
    
    # Build the enrichment prompt
    fields_needed = request.fields_to_enrich or ["website", "team", "financials"]
    fields_str = ", ".join(fields_needed)
    
    prompt = f"""You are a company research assistant. Find the following information about {request.company_name}:

Fields needed: {fields_str}

Existing information:
- Summary: {request.existing_data.get('summary', 'N/A')}
- Website: {request.existing_data.get('website', 'N/A')}
- Country: {request.existing_data.get('country', 'N/A')}

Please provide accurate, verified information. For website, provide the official company URL.
For team, provide team size estimate if available.
For financials, provide any publicly known funding information.

Return the information in JSON format with these keys (only include fields you have data for):
- website: official company website URL
- team_size: estimated team size (e.g., "50-100 employees")
- funding: funding information if known (e.g., "$10M Series A")
- summary: enhanced company summary if available
"""
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful research assistant that provides accurate company information. Always provide real, verifiable data. If you're not sure about something, don't include it."
                },
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            max_tokens=500,
        )
        
        result = json.loads(response.choices[0].message.content or "{}")
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Enrichment failed: {str(e)}")


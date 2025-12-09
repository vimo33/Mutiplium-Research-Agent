from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator

import yaml
from fastapi import Depends, FastAPI, HTTPException, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

from multiplium.runs import RunRegistry

# =============================================================================
# Supabase Client (optional - for persistent storage)
# =============================================================================

supabase_client = None
SUPABASE_INIT_ERROR = None
try:
    from supabase import create_client, Client
    
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
    
    if SUPABASE_URL and SUPABASE_KEY:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print(f"✅ Supabase connected: {SUPABASE_URL}")
    else:
        SUPABASE_INIT_ERROR = "URL or KEY not set"
        print("⚠️ Supabase not configured - using file storage")
except ImportError as e:
    SUPABASE_INIT_ERROR = f"ImportError: {e}"
    print(f"⚠️ Supabase package not installed - using file storage: {e}")
except Exception as e:
    SUPABASE_INIT_ERROR = f"Exception: {e}"
    print(f"⚠️ Supabase init failed: {e}")

# =============================================================================
# Configuration
# =============================================================================

# Use /data mount on Render (persistent disk) or local workspace
DATA_ROOT = Path(os.getenv("DATA_ROOT", Path(__file__).resolve().parents[1]))
WORKSPACE_ROOT = Path(__file__).resolve().parents[1]

# =============================================================================
# API Key Authentication
# =============================================================================

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str | None = Security(API_KEY_HEADER)) -> None:
    """
    Verify the API key from request header.
    
    If DASHBOARD_API_KEY env var is not set, authentication is disabled (dev mode).
    If set, the X-API-Key header must match.
    """
    expected_key = os.getenv("DASHBOARD_API_KEY")
    
    # If no key configured, allow all requests (dev mode)
    if not expected_key:
        return
    
    # Key is configured, so require it
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required. Include X-API-Key header.",
        )
    
    if api_key != expected_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
        )


# =============================================================================
# App Setup
# =============================================================================

app = FastAPI(
    title="Multiplium Research Dashboard API",
    description="Research orchestration platform for investment analysis",
    version="1.0.0",
)

# CORS configuration - restrict in production
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

registry = RunRegistry(workspace_root=WORKSPACE_ROOT, data_root=DATA_ROOT)


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
    companies: list[str] | None = Field(default=None, description="Specific company names to research (optional)")


class EnrichRequest(BaseModel):
    company_name: str = Field(description="Name of the company to enrich")
    existing_data: dict = Field(default={}, description="Existing company data")
    fields_to_enrich: list[str] = Field(default=[], description="Fields to fetch: website, team, financials, swot")


class EnrichCompanyDataRequest(BaseModel):
    company_name: str = Field(description="Name of the company to enrich")
    current_data: dict = Field(default={}, description="Current company data")
    missing_fields: list[str] = Field(default=[], description="List of missing field keys to enrich")


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


class ProjectCost(BaseModel):
    """Cost tracking for a project."""
    total_cost: float = 0.0
    discovery_cost: float = 0.0
    deep_research_cost: float = 0.0
    enrichment_cost: float = 0.0
    currency: str = "USD"
    last_updated: str | None = None


class ProjectStats(BaseModel):
    total_companies: int = 0
    enriched_companies: int = 0
    approved: int = 0
    rejected: int = 0
    maybe: int = 0
    pending: int = 0
    flagged: int = 0
    cost: ProjectCost = Field(default_factory=ProjectCost)


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


# ============================================================================
# Chat System Models
# ============================================================================

class ChatMessage(BaseModel):
    role: str = Field(description="Message role: 'user' or 'assistant'")
    content: str = Field(description="Message content")


class ChatRequest(BaseModel):
    session_id: str = Field(description="Unique session identifier")
    message: str = Field(description="User message to send")
    client_name: str = Field(default="", description="Optional client name context")
    project_name: str = Field(default="", description="Optional project name context")


class ChatFinalizeRequest(BaseModel):
    session_id: str = Field(description="Session ID to finalize")


# In-memory conversation storage (would be Redis/DB in production)
CHAT_SESSIONS: dict[str, list[dict]] = {}

# System prompt for the Research Context Guide
CONTEXT_GUIDE_SYSTEM_PROMPT = """You are a Research Context Guide, an expert AI assistant helping investment professionals set up research projects. Your goal is to gather comprehensive context through natural, engaging conversation.

## Your Personality
- Warm and professional, like a knowledgeable colleague
- Ask one or two questions at a time, not overwhelming lists
- Acknowledge and build upon the user's responses
- Be proactive in suggesting insights based on what you learn

## Your Goals
Through conversation, you need to understand:
1. **Research Objective**: What type of companies or investments are they looking for?
2. **Target Sectors**: Which industries or verticals?
3. **Geographic Focus**: Which regions or countries?
4. **Company Stages**: Pre-seed, Seed, Series A, B, C, Growth, etc.
5. **Investment Size**: What check sizes are they targeting?
6. **Key Criteria**: Technology focus, business models, specific characteristics
7. **Deal Breakers**: What would disqualify a company?

## Generating Artifacts
As you gather enough context, progressively generate research artifacts using these EXACT markers:

### Investment Thesis (generate when you understand the core opportunity)
[THESIS_START]
Your 2-3 paragraph investment thesis explaining the opportunity, market dynamics, and why this is compelling.
[THESIS_END]

### KPIs (generate when you understand their evaluation criteria)
[KPI_START]{"name": "KPI Name", "target": "Target Value (e.g., >50%)", "rationale": "Why this matters"}[KPI_END]
Generate 4-6 KPIs, each with its own markers.

### Value Chain Segments (generate when you understand the target space)
[SEGMENT_START]{"segment": "Segment Name", "description": "What companies in this segment do"}[SEGMENT_END]
Generate 6-8 segments, each with its own markers.

## Conversation Flow
1. Start by warmly greeting and asking about their research goals
2. Dig deeper with follow-up questions based on their responses
3. After 3-4 exchanges, start proposing artifacts
4. Ask for feedback on generated artifacts and refine if needed
5. When you've generated thesis, KPIs, and value chain, ask if they're ready to proceed

## Important Rules
- NEVER generate artifacts in your first response - gather context first
- Generate artifacts progressively, not all at once
- If the user asks to modify an artifact, regenerate it with their feedback
- Keep conversational text OUTSIDE the artifact markers
- Be concise but thorough in your questions"""


# Project storage (uses DATA_ROOT for persistent storage in production)
PROJECTS_FILE = DATA_ROOT / "data" / "projects.json"


def load_projects() -> dict[str, dict]:
    """Load projects from Supabase (or file fallback)."""
    # Try Supabase first
    if supabase_client:
        try:
            response = supabase_client.table("projects").select("*").execute()
            if response.data:
                return {row["id"]: row["data"] for row in response.data}
        except Exception as e:
            print(f"Supabase projects load error, falling back to file: {e}")
    
    # File fallback
    if PROJECTS_FILE.exists():
        try:
            with PROJECTS_FILE.open("r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_projects(projects: dict[str, dict]) -> None:
    """Save projects to Supabase (and file fallback)."""
    # Try Supabase first
    if supabase_client:
        try:
            for project_id, project_data in projects.items():
                supabase_client.table("projects").upsert({
                    "id": project_id,
                    "data": project_data,
                    "updated_at": datetime.utcnow().isoformat() + "Z",
                }).execute()
            print(f"✅ Saved {len(projects)} projects to Supabase")
        except Exception as e:
            print(f"Supabase projects save error, falling back to file: {e}")
    
    # Always save to file as backup
    PROJECTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with PROJECTS_FILE.open("w") as f:
        json.dump(projects, f, indent=2)


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint (no auth required for monitoring)."""
    return {"status": "ok"}


@app.get("/auth-check", dependencies=[Depends(verify_api_key)])
def auth_check() -> dict[str, str]:
    """Check if API key is valid (use for frontend validation)."""
    return {"status": "authenticated"}


@app.get("/runs", dependencies=[Depends(verify_api_key)])
def list_runs(limit: int = 50) -> dict[str, list[dict[str, object]]]:
    snapshots = registry.list_snapshots(limit=limit)
    return {"runs": [snapshot.to_dict() for snapshot in snapshots]}


@app.get("/runs/{run_id}", dependencies=[Depends(verify_api_key)])
def get_run(run_id: str) -> dict[str, object]:
    if not registry.snapshot_exists(run_id):
        raise HTTPException(status_code=404, detail="Run not found")
    snapshot = registry.load_snapshot(run_id)
    return snapshot.to_dict()


@app.get("/runs/{run_id}/events", dependencies=[Depends(verify_api_key)])
def get_run_events(run_id: str, limit: int = 200) -> dict[str, list[dict[str, object]]]:
    if not registry.snapshot_exists(run_id):
        raise HTTPException(status_code=404, detail="Run not found")
    return {"events": registry.load_events(run_id, limit=limit)}


@app.get("/reports", dependencies=[Depends(verify_api_key)])
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


def upload_report_to_supabase(report_path: str, data: dict) -> bool:
    """Upload a report to Supabase Storage."""
    if not supabase_client:
        return False
    
    try:
        # Convert path to storage path (e.g., reports/discoveries/xxx/report.json)
        storage_path = report_path.replace("\\", "/")
        
        # Upload as JSON
        content = json.dumps(data).encode("utf-8")
        supabase_client.storage.from_("reports").upload(
            storage_path,
            content,
            {"content-type": "application/json", "upsert": "true"}
        )
        print(f"✅ Uploaded report to Supabase: {storage_path}")
        return True
    except Exception as e:
        print(f"Failed to upload report to Supabase: {e}")
        return False


def download_report_from_supabase(report_path: str) -> dict | None:
    """Download a report from Supabase Storage."""
    if not supabase_client:
        return None
    
    try:
        storage_path = report_path.replace("\\", "/")
        response = supabase_client.storage.from_("reports").download(storage_path)
        if response:
            return json.loads(response.decode("utf-8"))
    except Exception as e:
        print(f"Report not in Supabase: {storage_path} - {e}")
    return None


@app.get("/reports/{report_path:path}/raw", dependencies=[Depends(verify_api_key)])
def get_report_raw(report_path: str) -> dict[str, object]:
    """Fetch raw JSON data from a report file (Supabase or local)."""
    
    if not report_path.endswith(".json"):
        raise HTTPException(status_code=400, detail="Only JSON reports are supported")
    
    # Try local file first
    report_file = WORKSPACE_ROOT / report_path
    if report_file.exists():
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
    
    # Try Supabase Storage
    data = download_report_from_supabase(report_path)
    if data:
        return data
    
    raise HTTPException(status_code=404, detail=f"Report not found: {report_path}")


@app.post("/runs", status_code=201, dependencies=[Depends(verify_api_key)])
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
        "-u",  # Unbuffered stdout for real-time logs
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


@app.post("/deep-research", status_code=201, dependencies=[Depends(verify_api_key)])
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
    
    # Add companies filter if specified
    if request.companies:
        import json
        cmd.extend(["--companies", json.dumps(request.companies)])
    
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

@app.get("/projects", dependencies=[Depends(verify_api_key)])
def list_projects() -> dict[str, list[dict]]:
    """List all research projects."""
    projects = load_projects()
    return {"projects": list(projects.values())}


@app.post("/projects", status_code=201, dependencies=[Depends(verify_api_key)])
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


@app.get("/projects/{project_id}", dependencies=[Depends(verify_api_key)])
def get_project(project_id: str) -> dict[str, dict]:
    """Get a single project by ID."""
    projects = load_projects()
    if project_id not in projects:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"project": projects[project_id]}


@app.put("/projects/{project_id}", dependencies=[Depends(verify_api_key)])
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


@app.delete("/projects/{project_id}", dependencies=[Depends(verify_api_key)])
def delete_project(project_id: str) -> dict[str, str]:
    """Delete a project."""
    projects = load_projects()
    if project_id not in projects:
        raise HTTPException(status_code=404, detail="Project not found")
    
    del projects[project_id]
    save_projects(projects)
    
    return {"status": "deleted"}


@app.post("/projects/{project_id}/enrich-brief", dependencies=[Depends(verify_api_key)])
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


@app.post("/projects/{project_id}/generate-framework", dependencies=[Depends(verify_api_key)])
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


class TestRunRequest(BaseModel):
    framework: ResearchFramework = Field(description="Research framework to test")
    companies_per_segment: int = Field(default=3, ge=1, le=10, description="Companies per segment")


@app.post("/projects/{project_id}/start-test-run", dependencies=[Depends(verify_api_key)])
def start_project_test_run(project_id: str, request: TestRunRequest) -> dict[str, object]:
    """Start a live test run using the orchestrator with a small sample size."""
    
    projects = load_projects()
    if project_id not in projects:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project = projects[project_id]
    framework = request.framework
    
    # Create temporary context files for the orchestrator
    test_run_dir = WORKSPACE_ROOT / "data" / "test_runs" / project_id
    test_run_dir.mkdir(parents=True, exist_ok=True)
    
    # Write thesis file
    thesis_path = test_run_dir / "thesis.md"
    thesis_path.write_text(framework.thesis or "Investment research thesis", encoding="utf-8")
    
    # Write value chain file (markdown format)
    value_chain_md = "# Value Chain Segments\n\n"
    for i, segment in enumerate(framework.value_chain, 1):
        value_chain_md += f"## {i}. {segment.segment}\n{segment.description}\n\n"
    value_chain_path = test_run_dir / "value_chain.md"
    value_chain_path.write_text(value_chain_md, encoding="utf-8")
    
    # Write KPIs file (markdown format)  
    kpis_md = "# Key Performance Indicators\n\n"
    for kpi in framework.kpis:
        kpis_md += f"**{kpi.name}**: {kpi.target}\n- {kpi.rationale}\n\n"
    kpis_path = test_run_dir / "kpis.md"
    kpis_path.write_text(kpis_md, encoding="utf-8")
    
    # Create test run config (use existing dev.yaml as base, override paths)
    base_config_path = WORKSPACE_ROOT / "config" / "dev.yaml"
    if not base_config_path.exists():
        raise HTTPException(status_code=500, detail="Base config not found")
    
    import yaml
    with base_config_path.open("r") as f:
        config = yaml.safe_load(f)
    
    # Override context paths for test run
    config["orchestrator"]["sector"] = project.get("project_name", "Research Project")
    config["orchestrator"]["thesis_path"] = str(thesis_path.relative_to(WORKSPACE_ROOT))
    config["orchestrator"]["value_chain_path"] = str(value_chain_path.relative_to(WORKSPACE_ROOT))
    config["orchestrator"]["kpi_path"] = str(kpis_path.relative_to(WORKSPACE_ROOT))
    config["orchestrator"]["output_path"] = f"reports/test_runs/{project_id}/report.json"
    
    # Use only one provider for test run (faster)
    config["providers"]["anthropic"]["enabled"] = False
    config["providers"]["google"]["enabled"] = False
    config["providers"]["openai"]["enabled"] = True
    config["providers"]["openai"]["max_steps"] = 10  # Limit iterations for test
    
    # Write test run config
    test_config_path = test_run_dir / "config.yaml"
    with test_config_path.open("w") as f:
        yaml.dump(config, f, default_flow_style=False)
    
    # Create run via orchestrator
    run_id = uuid.uuid4().hex
    
    # Pre-create snapshot
    registry.create_run(
        project_id=project_id,
        config_path=str(test_config_path),
        params={
            "test_run": True,
            "companies_per_segment": request.companies_per_segment,
        },
        run_id=run_id,
    )
    
    # Launch orchestrator with small sample size
    # top_n = companies_per_segment * number_of_segments
    total_companies = request.companies_per_segment * len(framework.value_chain)
    
    cmd = [
        sys.executable,
        "-m",
        "multiplium.orchestrator",
        "--config",
        str(test_config_path),
        "--top-n",
        str(max(total_companies, 10)),  # At least 10 companies
        "--run-id",
        run_id,
        "--project-id",
        project_id,
    ]
    
    stdout_path = registry.stdout_path(run_id)
    env = os.environ.copy()
    
    # Ensure reports directory exists
    (WORKSPACE_ROOT / "reports" / "test_runs" / project_id).mkdir(parents=True, exist_ok=True)
    
    stdout_handle = stdout_path.open("w", encoding="utf-8", buffering=1)
    
    subprocess.Popen(
        cmd,
        cwd=str(WORKSPACE_ROOT),
        stdout=stdout_handle,
        stderr=stdout_handle,
        env=env,
        start_new_session=True,
        close_fds=False,
    )
    
    # Update project status
    project["status"] = "test_run"
    project["updated_at"] = datetime.utcnow().isoformat() + "Z"
    save_projects(projects)
    
    return {
        "status": "started",
        "run_id": run_id,
        "message": f"Test run started: searching for ~{total_companies} companies across {len(framework.value_chain)} segments",
        "project_id": project_id,
    }


class StartDiscoveryRequest(BaseModel):
    framework: ResearchFramework = Field(description="Research framework for discovery")
    top_n: int = Field(default=50, ge=10, le=200, description="Total companies to find")


class StartDeepResearchRequest(BaseModel):
    companies: list[str] = Field(description="List of company names to research deeply")
    config_path: str = Field(default="config/dev.yaml", description="Path to orchestrator config")


@app.post("/projects/{project_id}/start-discovery", dependencies=[Depends(verify_api_key)])
def start_project_discovery(project_id: str, request: StartDiscoveryRequest) -> dict[str, object]:
    """Start full discovery research for a project."""
    
    projects = load_projects()
    if project_id not in projects:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project = projects[project_id]
    framework = request.framework
    
    # Create context files for the orchestrator
    discovery_dir = WORKSPACE_ROOT / "data" / "discoveries" / project_id
    discovery_dir.mkdir(parents=True, exist_ok=True)
    
    # Write thesis file
    thesis_path = discovery_dir / "thesis.md"
    thesis_path.write_text(framework.thesis or "Investment research thesis", encoding="utf-8")
    
    # Write value chain file
    value_chain_md = "# Value Chain Segments\n\n"
    for i, segment in enumerate(framework.value_chain, 1):
        value_chain_md += f"## {i}. {segment.segment}\n{segment.description}\n\n"
    value_chain_path = discovery_dir / "value_chain.md"
    value_chain_path.write_text(value_chain_md, encoding="utf-8")
    
    # Write KPIs file
    kpis_md = "# Key Performance Indicators\n\n"
    for kpi in framework.kpis:
        kpis_md += f"**{kpi.name}**: {kpi.target}\n- {kpi.rationale}\n\n"
    kpis_path = discovery_dir / "kpis.md"
    kpis_path.write_text(kpis_md, encoding="utf-8")
    
    # Create discovery config
    base_config_path = WORKSPACE_ROOT / "config" / "dev.yaml"
    if not base_config_path.exists():
        raise HTTPException(status_code=500, detail="Base config not found")
    
    with base_config_path.open("r") as f:
        config = yaml.safe_load(f)
    
    # Override context paths
    config["orchestrator"]["sector"] = project.get("project_name", "Research Project")
    config["orchestrator"]["thesis_path"] = str(thesis_path.relative_to(WORKSPACE_ROOT))
    config["orchestrator"]["value_chain_path"] = str(value_chain_path.relative_to(WORKSPACE_ROOT))
    config["orchestrator"]["kpi_path"] = str(kpis_path.relative_to(WORKSPACE_ROOT))
    config["orchestrator"]["output_path"] = f"reports/discoveries/{project_id}/report.json"
    
    # Keep providers as configured in dev.yaml (anthropic disabled, openai+google enabled)
    
    # Write discovery config
    config_path = discovery_dir / "config.yaml"
    with config_path.open("w") as f:
        yaml.dump(config, f, default_flow_style=False)
    
    # Create run
    run_id = uuid.uuid4().hex
    
    registry.create_run(
        project_id=project_id,
        config_path=str(config_path),
        params={
            "discovery": True,
            "top_n": request.top_n,
        },
        run_id=run_id,
    )
    
    # Launch orchestrator
    cmd = [
        sys.executable,
        "-u",  # Unbuffered stdout for real-time logs
        "-m",
        "multiplium.orchestrator",
        "--config",
        str(config_path),
        "--top-n",
        str(request.top_n),
        "--run-id",
        run_id,
        "--project-id",
        project_id,
    ]
    
    stdout_path = registry.stdout_path(run_id)
    env = os.environ.copy()
    
    # Ensure reports directory exists
    (WORKSPACE_ROOT / "reports" / "discoveries" / project_id).mkdir(parents=True, exist_ok=True)
    
    stdout_handle = stdout_path.open("w", encoding="utf-8", buffering=1)
    
    subprocess.Popen(
        cmd,
        cwd=str(WORKSPACE_ROOT),
        stdout=stdout_handle,
        stderr=stdout_handle,
        env=env,
        start_new_session=True,
        close_fds=False,
    )
    
    # Update project with run_id and status
    project["status"] = "researching"
    project["current_run_id"] = run_id
    project["updated_at"] = datetime.utcnow().isoformat() + "Z"
    save_projects(projects)
    
    return {
        "status": "started",
        "run_id": run_id,
        "message": f"Discovery started: searching for ~{request.top_n} companies across {len(framework.value_chain)} segments",
        "project_id": project_id,
    }


@app.post("/projects/{project_id}/retry-discovery", dependencies=[Depends(verify_api_key)])
def retry_project_discovery(project_id: str) -> dict[str, object]:
    """Retry a failed discovery run for a project."""
    
    projects = load_projects()
    if project_id not in projects:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project = projects[project_id]
    
    # Check if retry is allowed
    # Allow retry for failed, researching, or completed-with-no-results
    allowed_statuses = ("discovery_failed", "researching", "discovery_complete")
    if project.get("status") not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot retry discovery in status: {project.get('status')}"
        )
    
    # Check if discovery config exists
    discovery_dir = WORKSPACE_ROOT / "data" / "discoveries" / project_id
    config_path = discovery_dir / "config.yaml"
    
    if not config_path.exists():
        raise HTTPException(status_code=400, detail="Discovery config not found. Please restart the project.")
    
    # Regenerate config from dev.yaml to get current model names/settings
    # while preserving project-specific paths
    base_config_path = WORKSPACE_ROOT / "config" / "dev.yaml"
    if base_config_path.exists():
        with base_config_path.open("r") as f:
            config = yaml.safe_load(f)
        
        # Load existing discovery paths
        with config_path.open("r") as f:
            old_config = yaml.safe_load(f)
        
        # Preserve project-specific paths from old config
        config["orchestrator"]["sector"] = old_config["orchestrator"].get("sector", "Research Project")
        config["orchestrator"]["thesis_path"] = old_config["orchestrator"]["thesis_path"]
        config["orchestrator"]["value_chain_path"] = old_config["orchestrator"]["value_chain_path"]
        config["orchestrator"]["kpi_path"] = old_config["orchestrator"]["kpi_path"]
        config["orchestrator"]["output_path"] = old_config["orchestrator"]["output_path"]
        
        # Write updated config with fresh provider settings
        with config_path.open("w") as f:
            yaml.dump(config, f, default_flow_style=False)
    
    # Create new run
    run_id = uuid.uuid4().hex
    
    registry.create_run(
        project_id=project_id,
        config_path=str(config_path),
        params={
            "discovery": True,
            "retry": True,
        },
        run_id=run_id,
    )
    
    # Launch orchestrator
    cmd = [
        sys.executable,
        "-u",  # Unbuffered stdout for real-time logs
        "-m",
        "multiplium.orchestrator",
        "--config",
        str(config_path),
        "--run-id",
        run_id,
        "--project-id",
        project_id,
    ]
    
    stdout_path = registry.stdout_path(run_id)
    env = os.environ.copy()
    
    # Ensure reports directory exists
    (WORKSPACE_ROOT / "reports" / "discoveries" / project_id).mkdir(parents=True, exist_ok=True)
    
    stdout_handle = stdout_path.open("w", encoding="utf-8", buffering=1)
    
    subprocess.Popen(
        cmd,
        cwd=str(WORKSPACE_ROOT),
        stdout=stdout_handle,
        stderr=stdout_handle,
        env=env,
        start_new_session=True,
        close_fds=False,
    )
    
    # Update project with new run_id and status
    project["status"] = "researching"
    project["current_run_id"] = run_id
    project["updated_at"] = datetime.utcnow().isoformat() + "Z"
    save_projects(projects)
    
    return {
        "status": "started",
        "run_id": run_id,
        "message": "Discovery retry started",
        "project_id": project_id,
    }


@app.post("/projects/{project_id}/start-deep-research", dependencies=[Depends(verify_api_key)])
def start_project_deep_research(project_id: str, request: StartDeepResearchRequest) -> dict[str, object]:
    """Start deep research on selected companies from discovery."""
    
    projects = load_projects()
    if project_id not in projects:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project = projects[project_id]
    
    # Get discovery report path
    discovery_dir = WORKSPACE_ROOT / "data" / "discoveries" / project_id
    discovery_report = discovery_dir / "report.json"
    
    if not discovery_report.exists():
        raise HTTPException(status_code=400, detail="Discovery report not found")
    
    # Use existing config from discovery
    config_path = discovery_dir / "config.yaml"
    if not config_path.exists():
        config_path = WORKSPACE_ROOT / request.config_path
    
    # Create run
    run_id = uuid.uuid4().hex
    
    registry.create_run(
        project_id=project_id,
        config_path=str(config_path),
        params={
            "deep_research": True,
            "companies": request.companies,
            "source_report": str(discovery_report.relative_to(WORKSPACE_ROOT)),
        },
        run_id=run_id,
    )
    
    # Launch orchestrator with deep research flag
    cmd = [
        sys.executable,
        "-m",
        "multiplium.orchestrator",
        "--config",
        str(config_path),
        "--deep-research",
        "--from-report",
        str(discovery_report),
        "--companies",
        json.dumps(request.companies),
        "--run-id",
        run_id,
        "--project-id",
        project_id,
    ]
    
    stdout_path = registry.stdout_path(run_id)
    env = os.environ.copy()
    
    # Ensure reports directory exists
    deep_research_dir = WORKSPACE_ROOT / "reports" / "deep_research" / project_id
    deep_research_dir.mkdir(parents=True, exist_ok=True)
    
    stdout_handle = stdout_path.open("w", encoding="utf-8", buffering=1)
    
    subprocess.Popen(
        cmd,
        cwd=str(WORKSPACE_ROOT),
        stdout=stdout_handle,
        stderr=stdout_handle,
        env=env,
        start_new_session=True,
        close_fds=False,
    )
    
    # Update project with run_id and status
    project["status"] = "deep_researching"
    project["current_run_id"] = run_id
    project["updated_at"] = datetime.utcnow().isoformat() + "Z"
    save_projects(projects)
    
    return {
        "status": "started",
        "run_id": run_id,
        "message": f"Deep research started on {len(request.companies)} companies",
        "project_id": project_id,
    }


@app.get("/projects/{project_id}/discovery-status", dependencies=[Depends(verify_api_key)])
def get_discovery_status(project_id: str) -> dict[str, object]:
    """Get current discovery run status for a project."""
    
    projects = load_projects()
    if project_id not in projects:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project = projects[project_id]
    run_id = project.get("current_run_id")
    
    if not run_id:
        return {
            "status": "no_run",
            "project_id": project_id,
            "message": "No discovery run found for this project",
            "can_retry": True,
        }
    
    # Get run snapshot
    if not registry.snapshot_exists(run_id):
        return {
            "status": "not_found",
            "run_id": run_id,
            "project_id": project_id,
            "can_retry": True,
        }
    
    snapshot = registry.load_snapshot(run_id)
    run_data = snapshot.to_dict()
    
    # Check for report
    report_path = WORKSPACE_ROOT / "reports" / "discoveries" / project_id / "report.json"
    has_report = report_path.exists()
    
    # Extract error info from last event if failed
    error_message = None
    if run_data.get("status") == "failed":
        last_event = run_data.get("last_event", {})
        error_message = last_event.get("error", "Discovery failed unexpectedly")
        # Update project status to allow retry
        if project.get("status") == "researching":
            project["status"] = "discovery_failed"
            project["updated_at"] = datetime.utcnow().isoformat() + "Z"
            save_projects(projects)
    
    # If completed, update project status and upload report to Supabase
    if run_data.get("status") == "completed" and has_report:
        # Check if this is discovery or deep research
        params = run_data.get("params", {})
        if params.get("deep_research"):
            project["status"] = "ready_for_review"
        else:
            project["status"] = "discovery_complete"
        
        rel_report_path = str(report_path.relative_to(WORKSPACE_ROOT))
        project["report_path"] = rel_report_path
        project["updated_at"] = datetime.utcnow().isoformat() + "Z"
        save_projects(projects)
        
        # Upload report to Supabase Storage for persistence
        try:
            with report_path.open("r") as f:
                report_data = json.load(f)
            upload_report_to_supabase(rel_report_path, report_data)
        except Exception as e:
            print(f"Failed to upload report to Supabase: {e}")
    
    # Extract cost data from run
    total_cost = run_data.get("total_cost", 0.0)
    providers_data = run_data.get("providers", {})
    provider_costs = {}
    for pname, pdata in providers_data.items():
        if isinstance(pdata, dict) and pdata.get("cost"):
            provider_costs[pname] = pdata["cost"]
    
    return {
        "status": run_data.get("status", "unknown"),
        "run_id": run_id,
        "project_id": project_id,
        "phase": run_data.get("phase", ""),
        "percent_complete": run_data.get("percent_complete", 0),
        "providers": run_data.get("providers", {}),
        "has_report": has_report,
        "report_path": str(report_path.relative_to(WORKSPACE_ROOT)) if has_report else None,
        "total_cost": total_cost,
        "provider_costs": provider_costs,
        "error": error_message,
        "can_retry": run_data.get("status") == "failed",
    }


@app.get("/projects/{project_id}/cost", dependencies=[Depends(verify_api_key)])
def get_project_cost(project_id: str) -> dict[str, object]:
    """Get cost breakdown for a project including all runs."""
    
    projects = load_projects()
    if project_id not in projects:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project = projects[project_id]
    
    # Aggregate costs from all runs for this project
    total_cost = 0.0
    discovery_cost = 0.0
    deep_research_cost = 0.0
    enrichment_cost = 0.0
    run_costs = []
    
    # Get all run snapshots for this project
    runs_data_dir = WORKSPACE_ROOT / "data" / "runs"
    if runs_data_dir.exists():
        for run_file in runs_data_dir.glob("*.json"):
            try:
                with run_file.open("r") as f:
                    run_data = json.load(f)
                
                if run_data.get("project_id") != project_id:
                    continue
                
                run_total = run_data.get("total_cost", 0.0)
                params = run_data.get("params", {})
                
                if params.get("deep_research"):
                    deep_research_cost += run_total
                elif params.get("test_run"):
                    discovery_cost += run_total  # Test runs are discovery
                else:
                    discovery_cost += run_total
                
                total_cost += run_total
                
                run_costs.append({
                    "run_id": run_data.get("run_id"),
                    "started_at": run_data.get("started_at"),
                    "status": run_data.get("status"),
                    "cost": run_total,
                    "type": "deep_research" if params.get("deep_research") else "discovery",
                })
            except Exception:
                continue
    
    return {
        "project_id": project_id,
        "total_cost": round(total_cost, 4),
        "discovery_cost": round(discovery_cost, 4),
        "deep_research_cost": round(deep_research_cost, 4),
        "enrichment_cost": round(enrichment_cost, 4),
        "currency": "USD",
        "runs": run_costs,
        "last_updated": datetime.utcnow().isoformat() + "Z",
    }


@app.get("/projects/{project_id}/test-run-results", dependencies=[Depends(verify_api_key)])
def get_test_run_results(project_id: str) -> dict[str, object]:
    """Get test run results for a project."""
    
    # Check for test run report
    report_path = WORKSPACE_ROOT / "reports" / "test_runs" / project_id / "report.json"
    
    if not report_path.exists():
        # Check if there's a timestamped report
        reports_dir = WORKSPACE_ROOT / "reports" / "test_runs" / project_id
        if reports_dir.exists():
            reports = list(reports_dir.glob("report_*.json"))
            if reports:
                report_path = sorted(reports, reverse=True)[0]
    
    if not report_path.exists():
        return {
            "status": "pending",
            "companies": [],
            "message": "Test run in progress or not started",
        }
    
    try:
        with report_path.open("r") as f:
            data = json.load(f)
        
        # Extract companies from providers
        companies = []
        for provider in data.get("providers", []):
            for finding in provider.get("findings", []):
                segment_name = finding.get("name", "Unknown")
                for company in finding.get("companies", []):
                    companies.append({
                        "company": company.get("company", "Unknown"),
                        "segment": segment_name,
                        "country": company.get("country", ""),
                        "summary": company.get("summary", ""),
                        "confidence_0to1": company.get("confidence_0to1", 0.5),
                    })
        
        return {
            "status": "completed",
            "companies": companies,
            "total_companies": len(companies),
            "report_path": str(report_path.relative_to(WORKSPACE_ROOT)),
        }
        
    except Exception as e:
        return {
            "status": "error",
            "companies": [],
            "message": str(e),
        }


@app.post("/projects/{project_id}/approve-test-run", dependencies=[Depends(verify_api_key)])
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

@app.post("/enrich", dependencies=[Depends(verify_api_key)])
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


@app.post("/enrich-company-data", dependencies=[Depends(verify_api_key)])
async def enrich_company_data(request: EnrichCompanyDataRequest) -> dict[str, object]:
    """
    Enhanced company data enrichment using GPT-4o with structured output.
    
    This endpoint targets specific missing fields and returns data matching
    the company schema used in the dashboard.
    
    Supported missing_fields:
    - website: Company website URL
    - team: Founders, executives, team size
    - swot: SWOT analysis (strengths, weaknesses, opportunities, threats)
    - funding_rounds: Funding history with investors
    - competitors: Direct competitors and differentiation
    - key_clients: Notable customers/clients
    - kpi_alignment: Alignment with investment KPIs
    """
    from openai import AsyncOpenAI
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")
    
    client = AsyncOpenAI(api_key=api_key)
    
    company_name = request.company_name
    current_data = request.current_data
    missing_fields = request.missing_fields or ["website", "team", "swot", "funding_rounds", "competitors"]
    
    # Build field-specific instructions
    field_instructions = []
    
    if "website" in missing_fields:
        field_instructions.append('"website": "https://company-website.com" (official company URL)')
    
    if "team" in missing_fields:
        field_instructions.append('''"team": {
    "size": "50-100 employees",
    "founders": [{"name": "John Doe", "background": "Ex-Google, Stanford MBA"}],
    "executives": [{"name": "Jane Smith", "title": "CEO"}]
  }''')
    
    if "swot" in missing_fields:
        field_instructions.append('''"swot": {
    "strengths": ["Strong technology platform", "Experienced team"],
    "weaknesses": ["Limited market presence", "High burn rate"],
    "opportunities": ["Growing market", "Partnership potential"],
    "threats": ["Competition", "Regulatory changes"]
  }''')
    
    if "funding_rounds" in missing_fields:
        field_instructions.append('''"funding_rounds": [
    {"round_type": "Series A", "amount": 10000000, "currency": "USD", "investors": ["Investor A", "Investor B"]}
  ]''')
    
    if "competitors" in missing_fields:
        field_instructions.append('''"competitors": {
    "direct": [{"name": "CompetitorCo", "description": "Similar product offering"}],
    "differentiation": "Unique AI-powered approach"
  }''')
    
    if "key_clients" in missing_fields:
        field_instructions.append('''"key_clients": [
    {"name": "Enterprise Corp", "geographic_market": "North America", "notable_reference": "Case study available"}
  ]''')
    
    if "kpi_alignment" in missing_fields:
        field_instructions.append('"kpi_alignment": ["Strong revenue growth", "High customer retention"]')
    
    fields_json_example = ",\n  ".join(field_instructions)
    
    # Build context from existing data
    context_parts = []
    if current_data.get("summary"):
        context_parts.append(f"Summary: {current_data['summary']}")
    if current_data.get("country"):
        context_parts.append(f"Country: {current_data['country']}")
    if current_data.get("segment"):
        context_parts.append(f"Segment: {current_data['segment']}")
    if current_data.get("website"):
        context_parts.append(f"Website: {current_data['website']}")
    
    context_str = "\n".join(context_parts) if context_parts else "No existing data available"
    
    prompt = f"""Research and provide detailed information about "{company_name}".

EXISTING DATA:
{context_str}

MISSING FIELDS TO RESEARCH:
{', '.join(missing_fields)}

Research this company thoroughly and return ONLY the following JSON structure with data for the missing fields.
Only include fields where you have confident, accurate information.
For any field where data is unavailable or uncertain, omit it from the response.

Expected JSON structure:
{{
  {fields_json_example}
}}

IMPORTANT:
- Provide real, verifiable data only
- For funding_rounds, use numeric amounts (not strings like "$10M")
- For team, include actual names if publicly known
- For swot, provide 2-4 items per category
- For competitors, include 2-5 direct competitors if known
"""

    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": """You are an expert company research analyst with access to comprehensive business intelligence.
Your role is to provide accurate, detailed company information based on publicly available data.
Always verify information before including it. If uncertain, omit the field rather than guess.
Return well-structured JSON that matches the expected schema exactly."""
                },
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            max_tokens=1500,
            temperature=0.3,  # Lower temperature for more factual responses
        )
        
        result = json.loads(response.choices[0].message.content or "{}")
        
        # Post-process funding_rounds to ensure numeric amounts
        if "funding_rounds" in result:
            for round_data in result["funding_rounds"]:
                if isinstance(round_data.get("amount"), str):
                    # Try to parse string amounts like "$10M" into numbers
                    amount_str = round_data["amount"].replace("$", "").replace(",", "").strip()
                    try:
                        if "B" in amount_str.upper():
                            round_data["amount"] = float(amount_str.upper().replace("B", "")) * 1_000_000_000
                        elif "M" in amount_str.upper():
                            round_data["amount"] = float(amount_str.upper().replace("M", "")) * 1_000_000
                        elif "K" in amount_str.upper():
                            round_data["amount"] = float(amount_str.upper().replace("K", "")) * 1_000
                        else:
                            round_data["amount"] = float(amount_str)
                    except (ValueError, TypeError):
                        pass  # Keep as-is if parsing fails
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Company data enrichment failed: {str(e)}")


# ============================================================================
# Conversational Chat Endpoints (GPT-5.1)
# ============================================================================

def parse_artifacts(text: str) -> dict:
    """Extract structured artifacts from AI response text."""
    artifacts = {
        "thesis": None,
        "kpis": [],
        "value_chain": [],
    }
    
    # Extract thesis
    thesis_match = re.search(r'\[THESIS_START\](.*?)\[THESIS_END\]', text, re.DOTALL)
    if thesis_match:
        artifacts["thesis"] = thesis_match.group(1).strip()
    
    # Extract KPIs
    kpi_matches = re.findall(r'\[KPI_START\](.*?)\[KPI_END\]', text, re.DOTALL)
    for kpi_str in kpi_matches:
        try:
            kpi = json.loads(kpi_str.strip())
            artifacts["kpis"].append(kpi)
        except json.JSONDecodeError:
            pass
    
    # Extract value chain segments
    segment_matches = re.findall(r'\[SEGMENT_START\](.*?)\[SEGMENT_END\]', text, re.DOTALL)
    for seg_str in segment_matches:
        try:
            segment = json.loads(seg_str.strip())
            artifacts["value_chain"].append(segment)
        except json.JSONDecodeError:
            pass
    
    return artifacts


def clean_response_for_display(text: str) -> str:
    """Remove artifact markers from text for clean display, keeping the content."""
    # Remove thesis markers but keep content
    text = re.sub(r'\[THESIS_START\]', '\n📋 **Investment Thesis:**\n', text)
    text = re.sub(r'\[THESIS_END\]', '\n', text)
    
    # Remove KPI markers but format nicely
    text = re.sub(r'\[KPI_START\]', '\n📊 **KPI:** ', text)
    text = re.sub(r'\[KPI_END\]', '\n', text)
    
    # Remove segment markers but format nicely
    text = re.sub(r'\[SEGMENT_START\]', '\n🔗 **Segment:** ', text)
    text = re.sub(r'\[SEGMENT_END\]', '\n', text)
    
    return text.strip()


async def stream_chat_response(
    session_id: str,
    messages: list[dict],
) -> AsyncGenerator[str, None]:
    """Stream chat response from GPT-5.1."""
    from openai import AsyncOpenAI
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        yield f"data: {json.dumps({'error': 'OpenAI API key not configured'})}\n\n"
        return
    
    client = AsyncOpenAI(api_key=api_key)
    
    try:
        # Use GPT-5.1 with streaming
        # Note: Using gpt-4o as fallback if gpt-5.1 not available
        model = os.getenv("CHAT_MODEL", "gpt-5.1")
        
        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            max_completion_tokens=2000,
            temperature=0.7,
        )
        
        full_response = ""
        
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_response += content
                
                # Send chunk to client
                yield f"data: {json.dumps({'type': 'chunk', 'content': content})}\n\n"
        
        # Parse artifacts from full response
        artifacts = parse_artifacts(full_response)
        
        # Store in session
        CHAT_SESSIONS[session_id].append({
            "role": "assistant",
            "content": full_response,
        })
        
        # Send completion event with artifacts
        yield f"data: {json.dumps({'type': 'done', 'artifacts': artifacts})}\n\n"
        
    except Exception as e:
        error_msg = str(e)
        # If model not found, suggest fallback
        if "model" in error_msg.lower() and "not found" in error_msg.lower():
            yield f"data: {json.dumps({'type': 'error', 'error': f'Model not available. Please check CHAT_MODEL env var. Error: {error_msg}'})}\n\n"
        else:
            yield f"data: {json.dumps({'type': 'error', 'error': error_msg})}\n\n"


@app.post("/projects/chat", dependencies=[Depends(verify_api_key)])
async def chat_stream(request: ChatRequest):
    """
    Stream a conversational response from GPT-5.1 Context Guide.
    
    Uses Server-Sent Events (SSE) to stream the response in real-time.
    The response includes artifact markers that the frontend parses to display
    structured KPIs, thesis, and value chain segments inline.
    """
    session_id = request.session_id
    
    # Initialize session if new
    if session_id not in CHAT_SESSIONS:
        CHAT_SESSIONS[session_id] = []
        
        # Add system prompt with optional context
        system_content = CONTEXT_GUIDE_SYSTEM_PROMPT
        if request.client_name or request.project_name:
            system_content += f"\n\n## Project Context\n"
            if request.client_name:
                system_content += f"- Client: {request.client_name}\n"
            if request.project_name:
                system_content += f"- Project: {request.project_name}\n"
        
        CHAT_SESSIONS[session_id].append({
            "role": "system",
            "content": system_content,
        })
    
    # Add user message
    CHAT_SESSIONS[session_id].append({
        "role": "user",
        "content": request.message,
    })
    
    # Return streaming response
    return StreamingResponse(
        stream_chat_response(session_id, CHAT_SESSIONS[session_id]),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/projects/chat/finalize", dependencies=[Depends(verify_api_key)])
async def finalize_chat(request: ChatFinalizeRequest) -> dict:
    """
    Extract final structured data from a chat session.
    
    Returns the aggregated artifacts (thesis, KPIs, value chain) from
    the entire conversation for use in creating the project.
    """
    session_id = request.session_id
    
    if session_id not in CHAT_SESSIONS:
        raise HTTPException(status_code=404, detail="Chat session not found")
    
    messages = CHAT_SESSIONS[session_id]
    
    # Aggregate all artifacts from assistant messages
    final_artifacts = {
        "thesis": "",
        "kpis": [],
        "value_chain": [],
    }
    
    for msg in messages:
        if msg["role"] == "assistant":
            artifacts = parse_artifacts(msg["content"])
            
            # Use the latest thesis
            if artifacts["thesis"]:
                final_artifacts["thesis"] = artifacts["thesis"]
            
            # Collect unique KPIs (by name)
            existing_kpi_names = {k["name"] for k in final_artifacts["kpis"]}
            for kpi in artifacts["kpis"]:
                if kpi.get("name") and kpi["name"] not in existing_kpi_names:
                    final_artifacts["kpis"].append(kpi)
                    existing_kpi_names.add(kpi["name"])
            
            # Collect unique segments (by segment name)
            existing_segment_names = {s["segment"] for s in final_artifacts["value_chain"]}
            for segment in artifacts["value_chain"]:
                if segment.get("segment") and segment["segment"] not in existing_segment_names:
                    final_artifacts["value_chain"].append(segment)
                    existing_segment_names.add(segment["segment"])
    
    # Extract brief from conversation (summarize user inputs)
    user_messages = [m["content"] for m in messages if m["role"] == "user"]
    brief_summary = " ".join(user_messages[:3])[:500]  # First 3 messages, truncated
    
    return {
        "session_id": session_id,
        "framework": final_artifacts,
        "brief_summary": brief_summary,
        "message_count": len([m for m in messages if m["role"] != "system"]),
    }


@app.delete("/projects/chat/{session_id}", dependencies=[Depends(verify_api_key)])
def delete_chat_session(session_id: str) -> dict:
    """Delete a chat session."""
    if session_id in CHAT_SESSIONS:
        del CHAT_SESSIONS[session_id]
    return {"status": "deleted"}


@app.get("/projects/chat/{session_id}/history", dependencies=[Depends(verify_api_key)])
def get_chat_history(session_id: str) -> dict:
    """Get chat history for a session."""
    if session_id not in CHAT_SESSIONS:
        raise HTTPException(status_code=404, detail="Chat session not found")
    
    # Return messages without system prompt
    messages = [
        {"role": m["role"], "content": m["content"]}
        for m in CHAT_SESSIONS[session_id]
        if m["role"] != "system"
    ]
    
    return {"session_id": session_id, "messages": messages}


# ============================================================================
# Project Chat Persistence (tied to project ID) - Supabase + file fallback
# ============================================================================

CHAT_DATA_DIR = DATA_ROOT / "data" / "chats"


class SaveChatRequest(BaseModel):
    messages: list[dict] = Field(description="Chat messages to save")
    artifacts: dict = Field(default={}, description="Extracted artifacts")


@app.post("/projects/{project_id}/chat/save", dependencies=[Depends(verify_api_key)])
def save_project_chat(project_id: str, request: SaveChatRequest) -> dict:
    """Save chat messages and artifacts for a project to Supabase (and file fallback)."""
    now = datetime.utcnow().isoformat() + "Z"
    
    # Try Supabase first
    if supabase_client:
        try:
            row = {
                "project_id": project_id,
                "messages": request.messages,
                "artifacts": request.artifacts,
                "updated_at": now,
            }
            supabase_client.table("chats").upsert(
                row,
                on_conflict="project_id"
            ).execute()
            
            # Also update the in-memory session if it exists
            session_id = f"project_{project_id}"
            if session_id in CHAT_SESSIONS:
                system_msg = next((m for m in CHAT_SESSIONS[session_id] if m["role"] == "system"), None)
                CHAT_SESSIONS[session_id] = [system_msg] if system_msg else []
                CHAT_SESSIONS[session_id].extend(request.messages)
            
            return {"status": "saved", "project_id": project_id, "source": "supabase"}
        except Exception as e:
            print(f"Supabase chat save error, falling back to file: {e}")
    
    # File fallback
    CHAT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    chat_file = CHAT_DATA_DIR / f"{project_id}.json"
    
    chat_data = {
        "project_id": project_id,
        "messages": request.messages,
        "artifacts": request.artifacts,
        "updated_at": now,
    }
    
    with chat_file.open("w") as f:
        json.dump(chat_data, f, indent=2)
    
    # Also update the in-memory session if it exists
    session_id = f"project_{project_id}"
    if session_id in CHAT_SESSIONS:
        system_msg = next((m for m in CHAT_SESSIONS[session_id] if m["role"] == "system"), None)
        CHAT_SESSIONS[session_id] = [system_msg] if system_msg else []
        CHAT_SESSIONS[session_id].extend(request.messages)
    
    return {"status": "saved", "project_id": project_id, "source": "file"}


@app.get("/projects/{project_id}/chat/load", dependencies=[Depends(verify_api_key)])
def load_project_chat(project_id: str) -> dict:
    """Load saved chat messages and artifacts for a project from Supabase (or file fallback)."""
    
    # Try Supabase first
    if supabase_client:
        try:
            response = supabase_client.table("chats").select("*").eq("project_id", project_id).single().execute()
            if response.data:
                return {
                    "project_id": project_id,
                    "messages": response.data.get("messages", []),
                    "artifacts": response.data.get("artifacts", {}),
                    "updated_at": response.data.get("updated_at"),
                    "found": True,
                    "source": "supabase",
                }
            else:
                return {
                    "project_id": project_id,
                    "messages": [],
                    "artifacts": {},
                    "found": False,
                    "source": "supabase",
                }
        except Exception as e:
            # No row found or other error - fall back to file
            if "0 rows" not in str(e):
                print(f"Supabase chat load error, falling back to file: {e}")
    
    # File fallback
    chat_file = CHAT_DATA_DIR / f"{project_id}.json"
    
    if not chat_file.exists():
        return {
            "project_id": project_id,
            "messages": [],
            "artifacts": {},
            "found": False,
            "source": "file",
        }
    
    try:
        with chat_file.open("r") as f:
            chat_data = json.load(f)
        
        return {
            "project_id": project_id,
            "messages": chat_data.get("messages", []),
            "artifacts": chat_data.get("artifacts", {}),
            "updated_at": chat_data.get("updated_at"),
            "found": True,
            "source": "file",
        }
    except Exception as e:
        return {
            "project_id": project_id,
            "messages": [],
            "artifacts": {},
            "found": False,
            "error": str(e),
            "source": "file",
        }


@app.post("/projects/{project_id}/chat/stream", dependencies=[Depends(verify_api_key)])
async def project_chat_stream(project_id: str, request: ChatRequest):
    """
    Stream a conversational response for a specific project.
    Uses project_id as session identifier for persistence.
    """
    # Use project_id as session key
    session_id = f"project_{project_id}"
    
    # Initialize session if new
    if session_id not in CHAT_SESSIONS:
        CHAT_SESSIONS[session_id] = []
        
        # Try to load existing chat history
        chat_file = CHAT_DATA_DIR / f"{project_id}.json"
        if chat_file.exists():
            try:
                with chat_file.open("r") as f:
                    chat_data = json.load(f)
                    saved_messages = chat_data.get("messages", [])
                    if saved_messages:
                        # Add system prompt first
                        system_content = CONTEXT_GUIDE_SYSTEM_PROMPT
                        if request.client_name or request.project_name:
                            system_content += f"\n\n## Project Context\n"
                            if request.client_name:
                                system_content += f"- Client: {request.client_name}\n"
                            if request.project_name:
                                system_content += f"- Project: {request.project_name}\n"
                        
                        CHAT_SESSIONS[session_id].append({
                            "role": "system",
                            "content": system_content,
                        })
                        # Add saved messages
                        CHAT_SESSIONS[session_id].extend(saved_messages)
            except Exception:
                pass
        
        # If still empty, add system prompt
        if not CHAT_SESSIONS[session_id]:
            system_content = CONTEXT_GUIDE_SYSTEM_PROMPT
            if request.client_name or request.project_name:
                system_content += f"\n\n## Project Context\n"
                if request.client_name:
                    system_content += f"- Client: {request.client_name}\n"
                if request.project_name:
                    system_content += f"- Project: {request.project_name}\n"
            
            CHAT_SESSIONS[session_id].append({
                "role": "system",
                "content": system_content,
            })
    
    # Add user message
    CHAT_SESSIONS[session_id].append({
        "role": "user",
        "content": request.message,
    })
    
    # Return streaming response
    return StreamingResponse(
        stream_chat_response(session_id, CHAT_SESSIONS[session_id]),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# =============================================================================
# Reviews API - Server-side storage for company reviews (Supabase + file fallback)
# =============================================================================

REVIEWS_DATA_DIR = DATA_ROOT / "data" / "reviews"
REVIEWS_DATA_DIR.mkdir(parents=True, exist_ok=True)


class SaveReviewsRequest(BaseModel):
    """Request to save reviews for a project."""
    reviews: dict[str, dict]  # company_name -> review data


@app.get("/projects/{project_id}/reviews", dependencies=[Depends(verify_api_key)])
def load_project_reviews(project_id: str) -> dict:
    """Load saved reviews for a project from Supabase (or file fallback)."""
    
    # Try Supabase first
    if supabase_client:
        try:
            response = supabase_client.table("reviews").select("*").eq("project_id", project_id).execute()
            if response.data:
                # Convert rows to dict format
                reviews = {}
                latest_updated = None
                for row in response.data:
                    reviews[row["company_name"]] = {
                        "company": row["company_name"],
                        "status": row.get("status", "pending"),
                        "score": row.get("score"),
                        "notes": row.get("notes", ""),
                        "dataFlags": row.get("data_flags", []),
                        "dataEdits": row.get("data_edits", {}),
                        "reviewedAt": row.get("reviewed_at"),
                    }
                    if row.get("updated_at"):
                        if not latest_updated or row["updated_at"] > latest_updated:
                            latest_updated = row["updated_at"]
                
                return {
                    "project_id": project_id,
                    "reviews": reviews,
                    "updated_at": latest_updated,
                    "found": True,
                    "source": "supabase",
                }
            else:
                return {
                    "project_id": project_id,
                    "reviews": {},
                    "found": False,
                    "source": "supabase",
                }
        except Exception as e:
            print(f"Supabase error, falling back to file: {e}")
    
    # File fallback
    reviews_file = REVIEWS_DATA_DIR / f"{project_id}.json"
    
    if not reviews_file.exists():
        return {
            "project_id": project_id,
            "reviews": {},
            "found": False,
            "source": "file",
        }
    
    try:
        with reviews_file.open("r") as f:
            reviews_data = json.load(f)
        
        return {
            "project_id": project_id,
            "reviews": reviews_data.get("reviews", {}),
            "updated_at": reviews_data.get("updated_at"),
            "found": True,
            "source": "file",
        }
    except Exception as e:
        return {
            "project_id": project_id,
            "reviews": {},
            "found": False,
            "error": str(e),
            "source": "file",
        }


@app.put("/projects/{project_id}/reviews", dependencies=[Depends(verify_api_key)])
def save_project_reviews(project_id: str, request: SaveReviewsRequest) -> dict:
    """Save reviews for a project to Supabase (and file fallback)."""
    import httpx  # Using httpx instead of requests (already in dependencies)
    
    now = datetime.utcnow().isoformat() + "Z"
    saved_count = 0
    
    # Try Supabase REST API directly (more reliable than Python client)
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
    
    if supabase_url and supabase_key:
        try:
            rows_to_upsert = []
            for company_name, review_data in request.reviews.items():
                row = {
                    "project_id": project_id,
                    "company_name": company_name,
                    "status": review_data.get("status", "pending"),
                    "score": review_data.get("score"),
                    "notes": review_data.get("notes", ""),
                    "data_flags": review_data.get("dataFlags", []),
                    "data_edits": review_data.get("dataEdits", {}),
                    "reviewed_at": review_data.get("reviewedAt"),
                    "updated_at": now,
                }
                rows_to_upsert.append(row)
            
            # Use REST API directly for upsert
            if rows_to_upsert:
                headers = {
                    "apikey": supabase_key,
                    "Authorization": f"Bearer {supabase_key}",
                    "Content-Type": "application/json",
                    "Prefer": "resolution=merge-duplicates",
                }
                with httpx.Client(timeout=30.0) as client:
                    response = client.post(
                        f"{supabase_url}/rest/v1/reviews",
                        headers=headers,
                        json=rows_to_upsert,
                    )
                
                if response.status_code in [200, 201]:
                    saved_count = len(rows_to_upsert)
                    return {
                        "status": "saved",
                        "project_id": project_id,
                        "review_count": saved_count,
                        "source": "supabase",
                    }
                else:
                    print(f"Supabase REST API error: {response.status_code} - {response.text[:500]}")
        except Exception as e:
            import traceback
            print(f"Supabase save error, falling back to file: {e}")
            print(f"Full traceback: {traceback.format_exc()}")
    
    # File fallback
    reviews_file = REVIEWS_DATA_DIR / f"{project_id}.json"
    
    # Load existing reviews to merge
    existing_reviews = {}
    if reviews_file.exists():
        try:
            with reviews_file.open("r") as f:
                existing_data = json.load(f)
                existing_reviews = existing_data.get("reviews", {})
        except:
            pass
    
    # Merge new reviews with existing (new takes precedence)
    merged_reviews = {**existing_reviews, **request.reviews}
    
    reviews_data = {
        "project_id": project_id,
        "reviews": merged_reviews,
        "updated_at": now,
    }
    
    try:
        with reviews_file.open("w") as f:
            json.dump(reviews_data, f, indent=2)
        
        return {
            "status": "saved",
            "project_id": project_id,
            "review_count": len(merged_reviews),
            "source": "file",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save reviews: {e}")


# =============================================================================
# Frameworks API - Server-side storage for thesis/KPIs/valueChain
# =============================================================================

class SaveFrameworkRequest(BaseModel):
    """Request to save framework for a project."""
    thesis: str = ""
    kpis: list[dict] = []
    value_chain: list[dict] = []


@app.get("/projects/{project_id}/framework", dependencies=[Depends(verify_api_key)])
def load_project_framework(project_id: str) -> dict:
    """Load saved framework for a project from Supabase."""
    
    if supabase_client:
        try:
            response = supabase_client.table("frameworks").select("*").eq("project_id", project_id).single().execute()
            if response.data:
                return {
                    "project_id": project_id,
                    "thesis": response.data.get("thesis", ""),
                    "kpis": response.data.get("kpis", []),
                    "value_chain": response.data.get("value_chain", []),
                    "updated_at": response.data.get("updated_at"),
                    "found": True,
                    "source": "supabase",
                }
        except Exception as e:
            if "0 rows" not in str(e):
                print(f"Supabase framework load error: {e}")
    
    return {
        "project_id": project_id,
        "thesis": "",
        "kpis": [],
        "value_chain": [],
        "found": False,
        "source": "supabase",
    }


@app.put("/projects/{project_id}/framework", dependencies=[Depends(verify_api_key)])
def save_project_framework(project_id: str, request: SaveFrameworkRequest) -> dict:
    """Save framework for a project to Supabase."""
    now = datetime.utcnow().isoformat() + "Z"
    
    if supabase_client:
        try:
            row = {
                "project_id": project_id,
                "thesis": request.thesis,
                "kpis": request.kpis,
                "value_chain": request.value_chain,
                "updated_at": now,
            }
            supabase_client.table("frameworks").upsert(
                row,
                on_conflict="project_id"
            ).execute()
            
            return {
                "status": "saved",
                "project_id": project_id,
                "source": "supabase",
            }
        except Exception as e:
            print(f"Supabase framework save error: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to save framework: {e}")
    
    raise HTTPException(status_code=500, detail="Supabase not configured")


# Debug endpoint to check Supabase connection
@app.get("/debug/supabase-status")
def check_supabase_status():
    """Check if Supabase is connected and working."""
    status = {
        "supabase_client_exists": supabase_client is not None,
        "supabase_url": os.getenv("SUPABASE_URL", "NOT SET"),
        "supabase_key_set": bool(os.getenv("SUPABASE_SERVICE_KEY")),
        "init_error": SUPABASE_INIT_ERROR,
    }
    
    if supabase_client:
        try:
            # Try a simple query
            response = supabase_client.table("reviews").select("count").limit(1).execute()
            status["test_query"] = "success"
            status["test_result"] = str(response.data)
        except Exception as e:
            status["test_query"] = "failed"
            status["test_error"] = str(e)
    
    return status


# Debug endpoint to test upsert and see error
@app.get("/debug/test-upsert")
def test_supabase_upsert():
    """Test upserting a single review to see any errors."""
    from datetime import datetime
    
    if not supabase_client:
        return {"error": "Supabase client not initialized", "init_error": SUPABASE_INIT_ERROR}
    
    try:
        now = datetime.utcnow().isoformat() + "Z"
        test_row = {
            "project_id": "test_project",
            "company_name": f"TestCompany_{now[:10]}",
            "status": "approved",
            "notes": "Test upsert",
            "data_flags": [],
            "data_edits": {},
            "updated_at": now,
        }
        
        response = supabase_client.table("reviews").upsert([test_row]).execute()
        
        return {
            "success": True,
            "response_data": str(response.data)[:500],
            "row_inserted": test_row,
        }
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }


# Debug endpoint to test REST API upsert directly
@app.get("/debug/test-rest-upsert")
def test_rest_api_upsert():
    """Test REST API upsert directly (bypassing Python client)."""
    import httpx  # Using httpx instead of requests
    from datetime import datetime
    
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
    
    if not supabase_url or not supabase_key:
        return {"error": "Supabase URL or key not set", "url": supabase_url, "key_set": bool(supabase_key)}
    
    try:
        now = datetime.utcnow().isoformat() + "Z"
        test_row = {
            "project_id": "test_rest_api",
            "company_name": f"RESTTest_{now[:19]}",
            "status": "approved",
            "notes": "REST API test",
            "data_flags": [],
            "data_edits": {},
            "updated_at": now,
        }
        
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates",
        }
        
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{supabase_url}/rest/v1/reviews",
                headers=headers,
                json=[test_row],
            )
        
        return {
            "success": response.status_code in [200, 201],
            "status_code": response.status_code,
            "response_text": response.text[:500] if response.text else "empty",
            "row_sent": test_row,
        }
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }

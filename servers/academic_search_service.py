from __future__ import annotations

from fastapi import FastAPI

from .clients.academic import search_academic_papers
from .common import make_endpoint

app = FastAPI(title="Multiplium Academic Search MCP Service")

app.post("/mcp/academic")(make_endpoint(search_academic_papers))

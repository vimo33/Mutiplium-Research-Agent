from __future__ import annotations

from fastapi import FastAPI

from .clients import search_patents
from .common import make_endpoint

app = FastAPI(title="Multiplium Patents MCP Service")

app.post("/mcp/patents")(make_endpoint(search_patents))

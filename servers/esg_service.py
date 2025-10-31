from __future__ import annotations

from fastapi import FastAPI

from .clients.esg import lookup_esg_ratings
from .common import make_endpoint

app = FastAPI(title="Multiplium ESG MCP Service")

app.post("/mcp/esg")(make_endpoint(lookup_esg_ratings))

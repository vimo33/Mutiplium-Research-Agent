from __future__ import annotations

from fastapi import FastAPI

from .clients import lookup_company_profile
from .common import make_endpoint

app = FastAPI(title="Multiplium Crunchbase MCP Service")

app.post("/mcp/crunchbase")(make_endpoint(lookup_company_profile))

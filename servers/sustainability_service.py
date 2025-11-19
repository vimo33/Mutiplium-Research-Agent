"""Sustainability ratings and certifications MCP service."""
from __future__ import annotations

from fastapi import FastAPI

from .clients import sustainability
from .common import make_endpoint

app = FastAPI(title="Multiplium Sustainability & Certifications MCP Service")

app.post("/mcp/sustainability")(make_endpoint(sustainability.lookup_sustainability_ratings))
app.post("/mcp/certifications")(make_endpoint(sustainability.check_certifications))
app.post("/mcp/sdg")(make_endpoint(sustainability.calculate_sdg_alignment))


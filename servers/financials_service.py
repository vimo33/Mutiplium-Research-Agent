from __future__ import annotations

from fastapi import FastAPI

from .clients import fetch_financial_metrics
from .common import make_endpoint

app = FastAPI(title="Multiplium Financial Metrics MCP Service")

app.post("/mcp/financials")(make_endpoint(fetch_financial_metrics))

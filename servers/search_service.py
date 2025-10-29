from __future__ import annotations

from fastapi import FastAPI

from .clients import fetch_page_content, search_web
from .common import make_endpoint

app = FastAPI(title="Multiplium Search & Fetch MCP Service")

app.post("/mcp/search")(make_endpoint(search_web))
app.post("/mcp/fetch")(make_endpoint(fetch_page_content))

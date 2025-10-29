"""Combined FastAPI application exposing all MCP tool endpoints.

This allows deployments (e.g., Render) to run a single web service that mounts
each existing tool under a distinct prefix:

- /search/mcp/...
- /crunchbase/mcp/...
- /patents/mcp/...
- /financials/mcp/...
"""

from __future__ import annotations

from fastapi import FastAPI

from .crunchbase_service import app as crunchbase_app
from .financials_service import app as financials_app
from .patents_service import app as patents_app
from .search_service import app as search_app


app = FastAPI(title="Multiplium MCP Tool Suite")

# Mount individual tool apps under stable prefixes so existing routes remain
# unchanged aside from the added prefix.
app.mount("/search", search_app)
app.mount("/crunchbase", crunchbase_app)
app.mount("/patents", patents_app)
app.mount("/financials", financials_app)


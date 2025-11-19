from __future__ import annotations

from fastapi import FastAPI

from .academic_search_service import app as academic_app
from .crunchbase_service import app as crunchbase_app
from .esg_service import app as esg_app
from .financials_service import app as financials_app
from .patents_service import app as patents_app
from .search_service import app as search_app
from .sustainability_service import app as sustainability_app

app = FastAPI(title="Multiplium MCP Tool Suite")

# Mount individual tool apps under stable prefixes
app.mount("/search", search_app)
app.mount("/crunchbase", crunchbase_app)
app.mount("/patents", patents_app)
app.mount("/financials", financials_app)
app.mount("/esg", esg_app)
app.mount("/academic", academic_app)
app.mount("/sustainability", sustainability_app)

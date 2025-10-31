from __future__ import annotations

from typing import Any, TypedDict


class ToolLibraryEntry(TypedDict):
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]


DEFAULT_TOOL_LIBRARY: dict[str, ToolLibraryEntry] = {
    "search_web": {
        "description": "Search trusted news and company sources for investment-relevant information.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query combining sector, value-chain segment, or KPI.",
                },
                "max_results": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 5,
                    "description": "Maximum number of results to return ordered by relevance.",
                },
                "freshness_days": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 365,
                    "default": 90,
                    "description": "Optional freshness window (days) to bias towards recent items.",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "url": {"type": "string"},
                            "summary": {"type": "string"},
                            "published_at": {"type": "string"},
                            "source": {"type": "string"},
                        },
                        "required": ["title", "url"],
                        "additionalProperties": True,
                    },
                }
            },
            "required": ["results"],
            "additionalProperties": True,
        },
    },
    "fetch_content": {
        "description": "Fetch and sanitize full-page content from an approved URL for analysis.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "HTTP(S) URL from an approved domain.",
                }
            },
            "required": ["url"],
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "content_type": {"type": "string"},
                "status_code": {"type": "integer"},
            },
            "required": ["content"],
            "additionalProperties": True,
        },
    },
    "lookup_crunchbase": {
        "description": "Retrieve structured company profile, funding, and leadership data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company": {
                    "type": "string",
                    "description": "Canonical company name or Crunchbase permalink.",
                }
            },
            "required": ["company"],
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "profile": {"type": "object"},
                "funding_rounds": {"type": "array"},
                "investors": {"type": "array"},
            },
            "required": ["profile"],
            "additionalProperties": True,
        },
    },
    "lookup_patents": {
        "description": "Search patent databases for filings relevant to the thesis and KPIs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Keyword or boolean query targeting the technology domain.",
                },
                "max_results": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 25,
                    "default": 10,
                    "description": "Maximum number of patent filings to retrieve.",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "patents": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "publication_number": {"type": "string"},
                            "assignee": {"type": "string"},
                            "url": {"type": "string"},
                            "abstract": {"type": "string"},
                            "publication_date": {"type": "string"},
                        },
                        "required": ["title", "publication_number"],
                        "additionalProperties": True,
                    },
                }
            },
            "required": ["patents"],
            "additionalProperties": True,
        },
    },
    "financial_metrics": {
        "description": "Return up-to-date financial metrics and KPI values for a company.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company": {
                    "type": "string",
                    "description": "Company name or ticker symbol.",
                },
                "metrics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of metric identifiers to filter (e.g., revenue_growth, gross_margin).",
                },
                "period": {
                    "type": "string",
                    "description": "Optional trailing period such as 'TTM', 'FY2023', or 'Q2-2024'.",
                },
            },
            "required": ["company"],
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "metrics": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "object",
                        "properties": {
                            "value": {"type": ["number", "string"]},
                            "unit": {"type": "string"},
                            "as_of": {"type": "string"},
                            "source": {"type": "string"},
                        },
                        "required": ["value"],
                        "additionalProperties": True,
                    },
                }
            },
            "required": ["metrics"],
            "additionalProperties": True,
        },
    },
}

from __future__ import annotations

from typing import Any, TypedDict


class ToolLibraryEntry(TypedDict):
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]


DEFAULT_TOOL_LIBRARY: dict[str, ToolLibraryEntry] = {
    "search_web": {
        "description": "Search trusted news and company sources for investment-relevant information. PARALLEL TOOL: Use alongside perplexity_search for maximum coverage. Use 'search_depth': 'advanced' for deeper research.",
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
                    "description": "Maximum number of results to return.",
                },
                "search_depth": {
                    "type": "string",
                    "enum": ["basic", "advanced"],
                    "default": "basic",
                    "description": "Use 'advanced' for higher quality, more detailed search results on complex topics. Basic is faster for simple lookups.",
                },
                "include_domains": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "A list of domains to specifically include in the search results (e.g., ['techcrunch.com', 'wsj.com']).",
                },
                "topic": {
                    "type": "string",
                    "enum": ["general", "news", "finance"],
                    "default": "general",
                    "description": "Set the topic to 'finance' or 'news' to focus the search on relevant sources.",
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
                        },
                        "required": ["title", "url"],
                    },
                }
            },
        },
    },
    "perplexity_search": {
        "description": "Direct web search using Perplexity AI with real-time data and citations. PARALLEL TOOL: Use alongside search_web for maximum coverage. Returns ranked results with authoritative sources.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for current information on companies, technologies, or market trends.",
                },
                "max_results": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 5,
                    "description": "Maximum number of results to return.",
                },
                "search_recency_filter": {
                    "type": "string",
                    "enum": ["day", "week", "month", "year"],
                    "description": "Filter results by recency (optional). Use 'day' or 'week' for latest news.",
                },
            },
            "required": ["query"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "results": {"type": "array"},
                "content": {"type": "string"},
                "citations": {"type": "array"},
            },
        },
    },
    "perplexity_ask": {
        "description": "Conversational AI with web search for quick questions and explanations. Uses sonar-pro model for fast, accurate answers with citations. Great for understanding technologies, validating claims, or getting summaries.",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Question to ask about a company, technology, or concept.",
                },
                "return_related_questions": {
                    "type": "boolean",
                    "default": False,
                    "description": "Include related follow-up questions in response.",
                },
            },
            "required": ["question"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
                "citations": {"type": "array"},
                "related_questions": {"type": "array"},
            },
        },
    },
    "perplexity_research": {
        "description": "Deep, comprehensive research reports using sonar-deep-research model. Ideal for thorough company analysis, technology assessments, and market research. Returns detailed multi-paragraph reports with citations. Use for high-priority companies requiring extensive validation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Research topic (e.g., 'FarmWise agricultural robotics impact on vineyard sustainability').",
                },
                "focus_areas": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific areas to focus on (e.g., ['ROI data', 'customer case studies', 'environmental impact']).",
                },
            },
            "required": ["topic"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "report": {"type": "string"},
                "citations": {"type": "array"},
                "word_count": {"type": "integer"},
            },
        },
    },
    "perplexity_reason": {
        "description": "Advanced reasoning and analytical problem-solving using sonar-reasoning-pro model. Perfect for complex analysis like comparing technologies, evaluating investment theses, or assessing market fit. Provides structured logical reasoning with citations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "problem": {
                    "type": "string",
                    "description": "Problem or question requiring analysis (e.g., 'Compare precision irrigation ROI vs traditional methods for vineyards').",
                },
                "context": {
                    "type": "string",
                    "description": "Additional context for the analysis (optional).",
                },
            },
            "required": ["problem"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "analysis": {"type": "string"},
                "citations": {"type": "array"},
            },
        },
    },
    "lookup_esg_ratings": {
        "description": "Retrieve Environmental, Social, and Governance (ESG) ratings and data for a public company to assess its impact and sustainability performance.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company": {
                    "type": "string",
                    "description": "Company name or ticker symbol.",
                }
            },
            "required": ["company"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "esg_data": {"type": "object"}
            },
        },
    },
    "search_academic_papers": {
        "description": "Search for peer-reviewed scientific papers, academic journals, and university studies to validate technological claims or research topics.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Keywords related to the technology, scientific concept, or research area.",
                },
                "max_results": {
                    "type": "integer",
                    "default": 5,
                    "description": "Maximum number of papers to return.",
                },
            },
            "required": ["query"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "papers": {
                    "type": "array",
                    "items": {"type": "object"},
                }
            },
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
    "lookup_sustainability_ratings": {
        "description": "Retrieve comprehensive sustainability ratings and ESG scores from multiple providers (CDP, MSCI, Sustainalytics, CSRHub) to assess environmental and social impact performance.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company": {
                    "type": "string",
                    "description": "Company name or ticker symbol to look up sustainability ratings for.",
                }
            },
            "required": ["company"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "ratings": {"type": "array"},
                "environmental_score": {"type": ["number", "null"]},
                "social_score": {"type": ["number", "null"]},
                "governance_score": {"type": ["number", "null"]},
            },
        },
    },
    "check_certifications": {
        "description": "Check if a company holds impact and sustainability certifications like B Corp, Fair Trade, ISO 14001, Regenerative Organic Certified, or Carbon Neutral status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company": {
                    "type": "string",
                    "description": "Company name to check certifications for.",
                },
                "certification_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of specific certification types to check (e.g., ['B Corp', 'Fair Trade', 'ISO 14001']).",
                },
            },
            "required": ["company"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "certifications": {"type": "array"}
            },
        },
    },
    "calculate_sdg_alignment": {
        "description": "Calculate UN Sustainable Development Goal (SDG) alignment by mapping company activities and impact areas to the 17 SDGs. Returns alignment scores and specific SDG targets.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company_description": {
                    "type": "string",
                    "description": "Brief description of the company's business model and activities.",
                },
                "activities": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of specific company activities or products.",
                },
                "impact_areas": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of impact areas or outcomes the company targets.",
                },
            },
            "required": ["company_description"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "aligned_sdgs": {"type": "array"},
                "primary_sdgs": {"type": "array"},
                "total_sdgs_aligned": {"type": "integer"},
            },
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
    "extract_content": {
        "description": "Extract structured, clean content from one or more web pages. More powerful than fetch_content - extracts main text, removes ads/navigation, and provides metadata. Ideal for deep research on company pages, case studies, and documentation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of URLs to extract content from (up to 10 URLs).",
                },
                "include_raw_content": {
                    "type": "boolean",
                    "default": False,
                    "description": "Include raw HTML content in response (use for debugging or specialized extraction).",
                },
            },
            "required": ["urls"],
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
                            "url": {"type": "string"},
                            "title": {"type": "string"},
                            "content": {"type": "string"},
                            "raw_content": {"type": "string"},
                        },
                    },
                }
            },
        },
    },
    "map_website": {
        "description": "Create a structured map of a website's pages and structure. Discovers all accessible pages, their relationships, and content types. Useful for understanding company documentation, product portfolios, and organizational structure.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Website URL to map (e.g., 'https://company.com').",
                },
                "max_pages": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "default": 10,
                    "description": "Maximum number of pages to discover and map.",
                },
            },
            "required": ["url"],
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "pages": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string"},
                            "title": {"type": "string"},
                            "depth": {"type": "integer"},
                        },
                    },
                },
                "structure": {"type": "object"},
            },
        },
    },
    "crawl_website": {
        "description": "Systematically crawl a website to extract comprehensive content. Follows links up to specified depth, extracting structured content from each page. Best for thorough research on company impact reports, sustainability pages, and detailed case studies.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Starting URL for crawl (e.g., 'https://company.com/sustainability').",
                },
                "max_depth": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                    "default": 2,
                    "description": "Maximum crawl depth (1 = current page only, 2 = current + linked pages).",
                },
                "max_pages": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "default": 10,
                    "description": "Maximum total pages to crawl.",
                },
            },
            "required": ["url"],
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "pages": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string"},
                            "title": {"type": "string"},
                            "content": {"type": "string"},
                            "depth": {"type": "integer"},
                        },
                    },
                },
                "metadata": {"type": "object"},
            },
        },
    },
}

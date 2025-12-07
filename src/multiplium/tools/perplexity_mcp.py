"""Perplexity MCP Integration via Official MCP Server.

Best Practices Applied:
- Structured prompts with explicit format requirements
- System prompts for response formatting guidance
- Adaptive timeouts based on operation type
- Robust rate limiting with exponential backoff
- Comprehensive error handling with retries
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any

import httpx
import structlog

log = structlog.get_logger()

# Model-specific configurations
MODEL_CONFIGS = {
    "sonar": {
        "timeout": 30.0,
        "description": "Fast search, basic answers",
        "cost_per_request": 0.001,
    },
    "sonar-pro": {
        "timeout": 60.0,
        "description": "Enhanced search, better accuracy",
        "cost_per_request": 0.005,
    },
    "sonar-reasoning-pro": {
        "timeout": 120.0,
        "description": "Complex reasoning and analysis",
        "cost_per_request": 0.005,
    },
    "sonar-deep-research": {
        "timeout": 600.0,  # 10 minutes
        "description": "Comprehensive multi-source research",
        "cost_per_request": 0.02,
    },
}

# System prompts for different use cases
SYSTEM_PROMPTS = {
    "structured_data": """You are a precise data extraction assistant. 
When asked for specific information, respond with ONLY the requested data in the exact format specified.
Do not add explanations, context, or additional information unless explicitly asked.
If information cannot be found, respond with 'NOT FOUND' for that field.""",

    "company_enrichment": """You are a company research assistant focused on finding factual business information.
For each company, provide precise, verifiable data.
Always include the source of your information when possible.
If you cannot find verified information, say 'NOT FOUND' rather than guessing.""",

    "research": """You are a thorough research assistant.
Provide comprehensive, well-cited information.
Structure your responses clearly with sections and bullet points.
Always cite your sources.""",
}


class PerplexityMCPClient:
    """
    Client for Perplexity's API with optimized methods for research and enrichment.
    
    Features:
    - Model-specific timeouts and configurations
    - System prompts for better response formatting
    - Rate limiting with configurable intervals
    - Comprehensive error handling
    """
    
    def __init__(
        self,
        api_key: str | None = None,
        min_request_interval: float = 1.0,
    ) -> None:
        self.api_key = api_key or os.getenv("PERPLEXITY_API_KEY") or os.getenv("PPLX_API_KEY")
        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY or PPLX_API_KEY is required")
        
        # Perplexity API endpoints
        self.chat_url = "https://api.perplexity.ai/chat/completions"
        
        # Rate limiting: Configurable requests/minute
        self._last_request_time = 0.0
        self._min_request_interval = min_request_interval
        self._consecutive_errors = 0
        self._lock = asyncio.Lock()
        
        # Request tracking for monitoring
        self._request_count = 0
        self._total_cost = 0.0
    
    async def _rate_limit(self) -> None:
        """Ensure we don't exceed rate limits with adaptive backoff."""
        async with self._lock:
            now = time.time()
            
            # Adaptive interval based on recent errors
            interval = self._min_request_interval
            if self._consecutive_errors > 0:
                # Exponential backoff: 2^errors seconds, max 30 seconds
                interval = min(2 ** self._consecutive_errors, 30)
                log.warning(
                    "perplexity.backoff",
                    consecutive_errors=self._consecutive_errors,
                    backoff_seconds=interval,
                )
            
            time_since_last = now - self._last_request_time
            if time_since_last < interval:
                wait_time = interval - time_since_last
                log.debug("perplexity.rate_limit", wait_seconds=wait_time)
                await asyncio.sleep(wait_time)
            
            self._last_request_time = time.time()
    
    async def _call_perplexity_api(
        self, 
        model: str, 
        messages: list[dict[str, str]],
        timeout_override: float | None = None,
        **kwargs: Any
    ) -> dict[str, Any]:
        """
        Call Perplexity Chat Completions API with rate limiting and error handling.
        
        Args:
            model: Model name (sonar, sonar-pro, sonar-reasoning-pro, sonar-deep-research)
            messages: List of message dicts with role and content
            timeout_override: Optional timeout override (otherwise uses model default)
            **kwargs: Additional API parameters
        """
        await self._rate_limit()
        
        # Get model-specific config
        model_config = MODEL_CONFIGS.get(model, MODEL_CONFIGS["sonar-pro"])
        timeout = timeout_override or model_config["timeout"]
        
        try:
            payload = {
                "model": model,
                "messages": messages,
                **kwargs
            }
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            
            log.debug(
                "perplexity.request",
                model=model,
                timeout=timeout,
                message_count=len(messages),
            )
            
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(self.chat_url, json=payload, headers=headers)
            
            response.raise_for_status()
            result = response.json()
            
            # Success - reset error counter and track metrics
            self._consecutive_errors = 0
            self._request_count += 1
            self._total_cost += model_config["cost_per_request"]
            
            log.debug(
                "perplexity.response",
                model=model,
                request_count=self._request_count,
                total_cost=f"${self._total_cost:.4f}",
            )
            
            return result
            
        except httpx.HTTPStatusError as exc:
            self._consecutive_errors += 1
            
            # Check for rate limit errors specifically
            if exc.response.status_code == 429:
                log.warning(
                    "perplexity.rate_limited",
                    retry_after=exc.response.headers.get("Retry-After", "unknown"),
                )
            
            log.error(
                "perplexity.api_error",
                status=exc.response.status_code,
                response=exc.response.text[:500],
                consecutive_errors=self._consecutive_errors,
            )
            return {
                "error": f"HTTP {exc.response.status_code}: {exc.response.text[:200]}",
                "content": "",
                "status_code": exc.response.status_code,
            }
            
        except httpx.TimeoutException as exc:
            self._consecutive_errors += 1
            log.error(
                "perplexity.timeout",
                model=model,
                timeout=timeout,
                error=str(exc),
            )
            return {
                "error": f"Request timed out after {timeout}s",
                "content": "",
                "timeout": True,
            }
            
        except Exception as exc:
            self._consecutive_errors += 1
            log.error(
                "perplexity.api_error",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return {"error": str(exc), "content": ""}
    
    def get_stats(self) -> dict[str, Any]:
        """Get client statistics for monitoring."""
        return {
            "request_count": self._request_count,
            "total_cost": round(self._total_cost, 4),
            "consecutive_errors": self._consecutive_errors,
        }
    
    async def search(
        self,
        query: str,
        max_results: int = 5,
        search_recency_filter: str | None = None,
    ) -> dict[str, Any]:
        """
        Direct web search using Perplexity Search API.
        
        Args:
            query: Search query
            max_results: Maximum number of results (default: 5)
            search_recency_filter: Filter by recency ("day", "week", "month", "year")
        """
        log.info("perplexity.search", query=query, max_results=max_results)
        
        messages = [{"role": "user", "content": query}]
        kwargs = {
            "return_citations": True,
            "return_images": False,
        }
        if search_recency_filter:
            kwargs["search_recency_filter"] = search_recency_filter
        
        result = await self._call_perplexity_api(
            model="sonar",
            messages=messages,
            **kwargs
        )
        
        # Transform to match expected format
        if "error" in result:
            return {"query": query, "results": [], "error": result["error"]}
        
        # Extract content and citations
        content = ""
        citations = []
        if "choices" in result and len(result["choices"]) > 0:
            choice = result["choices"][0]
            content = choice.get("message", {}).get("content", "")
            citations = choice.get("citations", [])
        
        # Format as search results
        results = []
        for i, citation in enumerate(citations[:max_results]):
            results.append({
                "title": f"Source {i+1}",
                "url": citation,
                "summary": content[:500] if i == 0 else "",  # First result gets content
                "source": "Perplexity",
            })
        
        return {
            "query": query,
            "content": content,
            "results": results,
            "citations": citations,
        }
    
    async def ask(
        self,
        question: str,
        return_related_questions: bool = False,
        system_prompt: str | None = None,
        structured: bool = False,
    ) -> dict[str, Any]:
        """
        General-purpose conversational AI with real-time web search.
        Uses sonar-pro model for quick questions.
        
        Args:
            question: Question to ask
            return_related_questions: Include related questions in response
            system_prompt: Optional system prompt for response formatting
            structured: If True, uses structured_data system prompt for precise extraction
        """
        log.info("perplexity.ask", question=question[:100], structured=structured)
        
        # Build messages with optional system prompt
        messages = []
        
        if structured:
            messages.append({
                "role": "system",
                "content": SYSTEM_PROMPTS["structured_data"],
            })
        elif system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt,
            })
        
        messages.append({"role": "user", "content": question})
        
        kwargs = {
            "return_citations": True,
            "return_related_questions": return_related_questions,
        }
        
        result = await self._call_perplexity_api(
            model="sonar-pro",
            messages=messages,
            **kwargs
        )
        
        if "error" in result:
            return {"question": question, "answer": "", "error": result["error"]}
        
        # Extract answer and metadata
        answer = ""
        citations = []
        related_questions = []
        
        if "choices" in result and len(result["choices"]) > 0:
            choice = result["choices"][0]
            answer = choice.get("message", {}).get("content", "")
            citations = choice.get("citations", [])
            related_questions = choice.get("related_questions", [])
        
        return {
            "question": question,
            "answer": answer,
            "citations": citations,
            "related_questions": related_questions,
        }
    
    async def enrich_company(
        self,
        company_name: str,
        segment: str | None = None,
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Specialized method for company data enrichment.
        
        Optimized for extracting structured company information with high accuracy.
        Uses system prompts and structured question format for reliable parsing.
        
        Args:
            company_name: Name of the company to research
            segment: Optional business segment/industry context
            fields: List of fields to retrieve (default: website, country)
        
        Returns:
            Dict with extracted fields and metadata
        """
        if fields is None:
            fields = ["website", "country"]
        
        log.info(
            "perplexity.enrich_company",
            company=company_name,
            segment=segment,
            fields=fields,
        )
        
        # Build highly structured prompt for reliable extraction
        field_instructions = []
        for i, field in enumerate(fields, 1):
            if field == "website":
                field_instructions.append(
                    f"{i}. WEBSITE: Official company website URL (format: https://example.com)"
                )
            elif field == "country":
                field_instructions.append(
                    f"{i}. COUNTRY: Headquarters country (just the country name, e.g., 'United States')"
                )
            elif field == "founded":
                field_instructions.append(
                    f"{i}. FOUNDED: Year the company was founded (just the year, e.g., '2015')"
                )
            elif field == "employees":
                field_instructions.append(
                    f"{i}. EMPLOYEES: Approximate number of employees (e.g., '50-100' or '500+')"
                )
            else:
                field_instructions.append(f"{i}. {field.upper()}: {field}")
        
        context = f" in the {segment} sector" if segment else ""
        
        question = f"""Find the following information for the company "{company_name}"{context}:

{chr(10).join(field_instructions)}

Respond with ONLY the requested information in this exact format:
{chr(10).join(f'{f.upper()}: [value or NOT FOUND]' for f in fields)}"""

        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPTS["company_enrichment"],
            },
            {
                "role": "user",
                "content": question,
            },
        ]
        
        result = await self._call_perplexity_api(
            model="sonar-pro",
            messages=messages,
            return_citations=True,
            timeout_override=45.0,  # Slightly longer for company research
        )
        
        if "error" in result:
            return {
                "company": company_name,
                "fields": {f: None for f in fields},
                "error": result["error"],
                "success": False,
            }
        
        # Extract answer
        answer = ""
        citations = []
        if "choices" in result and len(result["choices"]) > 0:
            choice = result["choices"][0]
            answer = choice.get("message", {}).get("content", "")
            citations = choice.get("citations", [])
        
        # Parse structured response
        extracted_fields = self._parse_structured_response(answer, fields)
        
        return {
            "company": company_name,
            "fields": extracted_fields,
            "raw_response": answer,
            "citations": citations,
            "success": any(v is not None for v in extracted_fields.values()),
        }
    
    def _parse_structured_response(
        self,
        response: str,
        expected_fields: list[str],
    ) -> dict[str, str | None]:
        """
        Parse a structured response looking for field: value patterns.
        
        Handles various formats:
        - FIELD: value
        - Field: value
        - **Field:** value
        """
        import re
        
        result = {field: None for field in expected_fields}
        
        if not response:
            return result
        
        for field in expected_fields:
            # Try multiple patterns for each field
            patterns = [
                rf"{field.upper()}:\s*(.+?)(?:\n|$)",
                rf"\*\*{field.upper()}:\*\*\s*(.+?)(?:\n|$)",
                rf"{field.title()}:\s*(.+?)(?:\n|$)",
                rf"\*\*{field.title()}:\*\*\s*(.+?)(?:\n|$)",
            ]
            
            for pattern in patterns:
                match = re.search(pattern, response, re.IGNORECASE)
                if match:
                    value = match.group(1).strip()
                    # Clean up common artifacts
                    value = value.rstrip(".,;:")
                    value = re.sub(r"\s*\[.*?\]\s*$", "", value)  # Remove trailing citations
                    
                    # Check for "not found" variants
                    if value.lower() in ("not found", "n/a", "unknown", "none", "-"):
                        result[field] = None
                    else:
                        result[field] = value
                    break
        
        return result
    
    async def research(
        self,
        topic: str,
        focus_areas: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Deep, comprehensive research using sonar-deep-research model.
        Ideal for thorough analysis and detailed reports.
        
        Args:
            topic: Research topic
            focus_areas: Specific areas to focus on (optional)
        """
        log.info("perplexity.research", topic=topic[:100])
        
        # Build research prompt
        prompt = f"Provide a comprehensive research report on: {topic}"
        if focus_areas:
            prompt += f"\n\nFocus on these specific areas:\n" + "\n".join(f"- {area}" for area in focus_areas)
        
        messages = [{"role": "user", "content": prompt}]
        kwargs = {
            "return_citations": True,
        }
        
        result = await self._call_perplexity_api(
            model="sonar-deep-research",
            messages=messages,
            **kwargs
        )
        
        if "error" in result:
            return {"topic": topic, "report": "", "error": result["error"]}
        
        # Extract report and citations
        report = ""
        citations = []
        
        if "choices" in result and len(result["choices"]) > 0:
            choice = result["choices"][0]
            report = choice.get("message", {}).get("content", "")
            citations = choice.get("citations", [])
        
        return {
            "topic": topic,
            "report": report,
            "citations": citations,
            "word_count": len(report.split()),
        }
    
    async def reason(
        self,
        problem: str,
        context: str | None = None,
    ) -> dict[str, Any]:
        """
        Advanced reasoning and problem-solving using sonar-reasoning-pro model.
        Perfect for complex analytical tasks.
        
        Args:
            problem: Problem or question requiring reasoning
            context: Additional context (optional)
        """
        log.info("perplexity.reason", problem=problem[:100])
        
        # Build reasoning prompt
        prompt = problem
        if context:
            prompt = f"Context: {context}\n\nProblem: {problem}"
        
        messages = [{"role": "user", "content": prompt}]
        kwargs = {
            "return_citations": True,
        }
        
        result = await self._call_perplexity_api(
            model="sonar-reasoning-pro",
            messages=messages,
            **kwargs
        )
        
        if "error" in result:
            return {"problem": problem, "analysis": "", "error": result["error"]}
        
        # Extract reasoning and citations
        analysis = ""
        citations = []
        
        if "choices" in result and len(result["choices"]) > 0:
            choice = result["choices"][0]
            analysis = choice.get("message", {}).get("content", "")
            citations = choice.get("citations", [])
        
        return {
            "problem": problem,
            "analysis": analysis,
            "citations": citations,
        }


# Global client instance
_client: PerplexityMCPClient | None = None


def get_client() -> PerplexityMCPClient:
    """Get or create the global Perplexity MCP client."""
    global _client
    if _client is None:
        _client = PerplexityMCPClient()
    return _client


# Convenience functions for direct use
async def search_web(
    query: str,
    max_results: int = 5,
    search_recency_filter: str | None = None,
) -> dict[str, Any]:
    """Search the web using Perplexity."""
    client = get_client()
    return await client.search(query, max_results, search_recency_filter)


async def ask_question(
    question: str,
    return_related_questions: bool = False,
) -> dict[str, Any]:
    """Ask a question using Perplexity."""
    client = get_client()
    return await client.ask(question, return_related_questions)


async def research_topic(
    topic: str,
    focus_areas: list[str] | None = None,
) -> dict[str, Any]:
    """Research a topic using Perplexity deep research."""
    client = get_client()
    return await client.research(topic, focus_areas)


async def reason_about(
    problem: str,
    context: str | None = None,
) -> dict[str, Any]:
    """Reason about a problem using Perplexity."""
    client = get_client()
    return await client.reason(problem, context)


async def enrich_company(
    company_name: str,
    segment: str | None = None,
    fields: list[str] | None = None,
) -> dict[str, Any]:
    """
    Enrich company data using Perplexity's structured extraction.
    
    Args:
        company_name: Name of the company to research
        segment: Optional business segment/industry context
        fields: List of fields to retrieve (default: website, country)
    
    Returns:
        Dict with extracted fields and metadata
    """
    client = get_client()
    return await client.enrich_company(company_name, segment, fields)


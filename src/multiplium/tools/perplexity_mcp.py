"""Perplexity MCP Integration via Official MCP Server."""
from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any

import httpx
import structlog

log = structlog.get_logger()


class PerplexityMCPClient:
    """Client for Perplexity's MCP server with 4 research tools."""
    
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("PERPLEXITY_API_KEY") or os.getenv("PPLX_API_KEY")
        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY or PPLX_API_KEY is required")
        
        # Perplexity API endpoints
        self.chat_url = "https://api.perplexity.ai/chat/completions"
        self.timeout = 600.0  # 10 minutes for deep research
        
        # Rate limiting: Conservative 60 requests/minute
        self._last_request_time = 0.0
        self._min_request_interval = 1.0  # 1 second between requests
        self._lock = asyncio.Lock()
    
    async def _rate_limit(self) -> None:
        """Ensure we don't exceed rate limits."""
        async with self._lock:
            now = time.time()
            time_since_last = now - self._last_request_time
            if time_since_last < self._min_request_interval:
                wait_time = self._min_request_interval - time_since_last
                log.debug("perplexity.rate_limit", wait_seconds=wait_time)
                await asyncio.sleep(wait_time)
            self._last_request_time = time.time()
    
    async def _call_perplexity_api(
        self, 
        model: str, 
        messages: list[dict[str, str]],
        **kwargs: Any
    ) -> dict[str, Any]:
        """Call Perplexity Chat Completions API with rate limiting."""
        await self._rate_limit()
        
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
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.chat_url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as exc:
            log.error(
                "perplexity.api_error",
                status=exc.response.status_code,
                response=exc.response.text[:500],
            )
            return {
                "error": f"HTTP {exc.response.status_code}: {exc.response.text[:200]}",
                "content": "",
            }
        except Exception as exc:
            log.error("perplexity.api_error", error=str(exc))
            return {"error": str(exc), "content": ""}
    
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
    ) -> dict[str, Any]:
        """
        General-purpose conversational AI with real-time web search.
        Uses sonar-pro model for quick questions.
        
        Args:
            question: Question to ask
            return_related_questions: Include related questions in response
        """
        log.info("perplexity.ask", question=question[:100])
        
        messages = [{"role": "user", "content": question}]
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


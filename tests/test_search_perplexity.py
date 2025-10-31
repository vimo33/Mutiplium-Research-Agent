from __future__ import annotations

from servers.clients.search import _extract_perplexity_results


def test_extract_perplexity_results_with_citations() -> None:
    payload = {
        "choices": [
            {
                "message": {
                    "content": [{"type": "output_text", "text": "Answer body."}],
                    "citations": [
                        {
                            "citations": [
                                {
                                    "title": "Example Source",
                                    "url": "https://example.com/article",
                                    "snippet": "Key findings from the article.",
                                    "published_at": "2025-10-01",
                                }
                            ]
                        }
                    ],
                }
            }
        ]
    }

    results = _extract_perplexity_results(payload, max_results=5)
    assert len(results) == 1
    assert results[0]["url"] == "https://example.com/article"
    assert results[0]["summary"] == "Key findings from the article."
    assert results[0]["source"] == "example.com"


def test_extract_perplexity_results_without_citations_falls_back_to_summary() -> None:
    payload = {
        "choices": [
            {
                "message": {
                    "content": [
                        {"type": "output_text", "text": "Summary response outlining findings."}
                    ],
                    "citations": [],
                }
            }
        ]
    }

    results = _extract_perplexity_results(payload, max_results=3)
    assert len(results) == 1
    assert results[0]["summary"].startswith("Summary response outlining findings.")
    assert results[0]["source"] == "perplexity.ai"

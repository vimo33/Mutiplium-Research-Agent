# Deep Research Feature Guide

## Overview

The deep research feature allows you to take an existing discovery report and enrich the top N companies with comprehensive investment data. This is useful when you want to:

1. Run discovery first (fast, inexpensive) to find companies
2. Review the results and validate the company list
3. Launch deep research on the most promising companies

## Quick Start

### Option 1: Using the Dashboard UI (Recommended)

1. **Start the dashboard:**
   ```bash
   ./scripts/start_dashboard.sh
   ```
   This opens http://localhost:5173 in your browser.

2. **Navigate to the "Reports" tab** in the dashboard

3. **Select a discovery report** from the list

4. **Configure deep research:**
   - Choose how many top companies to research (default: 25)
   - The UI shows cost and time estimates

5. **Launch deep research** and monitor progress in real-time

### Option 2: Using the CLI

Run deep research directly from a report file:

```bash
python -m multiplium.orchestrator \
  --config config/dev.yaml \
  --from-report reports/new/report_20251106T150232Z.json \
  --deep-research \
  --top-n 25
```

## What Deep Research Provides

Deep research enriches each company with **9 comprehensive data points**:

1. **Executive Summary** (from discovery)
2. **Technology & Value Chain** (from discovery)
3. **Evidence of Impact** ✨ Enhanced with deep dive
4. **Key Clients** ✨ Enhanced with more references
5. **Team** ✨ NEW - Founders, executives, team size
6. **Competitors** ✨ NEW - Competitive landscape
7. **Financials** ✨ NEW - Funding, revenue, 3-year metrics
8. **Cap Table** ✨ NEW - Investors, ownership structure
9. **SWOT Analysis** ✨ NEW - Strengths, weaknesses, opportunities, threats

## Cost & Time Estimates

| Companies | Cost (est.) | Time (est.) | Notes |
|-----------|-------------|-------------|-------|
| 10        | $0.10       | ~14 min     | 5 concurrent |
| 25        | $0.25       | ~35 min     | 5 concurrent |
| 50        | $0.50       | ~70 min     | 5 concurrent |
| 100       | $1.00       | ~140 min    | 5 concurrent |

**Cost breakdown (optimized):**
- **Perplexity Pro:** $0.005/company (financial data ONLY - best for Crunchbase)
- **OpenAI GPT-4o:** $0.005/company (team, competitors, evidence, SWOT - cost-effective)
- **Total:** ~$0.01/company (50% cost reduction!)

## API Endpoints

### List Reports
```http
GET /reports
```

Returns all discovery reports with metadata:
```json
{
  "reports": [
    {
      "path": "reports/new/report_20251106T150232Z.json",
      "filename": "report_20251106T150232Z.json",
      "timestamp": "2025-11-06T15:02:32Z",
      "total_companies": 180,
      "has_deep_research": false,
      "providers": ["openai", "google"]
    }
  ]
}
```

### Launch Deep Research
```http
POST /deep-research
Content-Type: application/json

{
  "report_path": "reports/new/report_20251106T150232Z.json",
  "top_n": 25,
  "config_path": "config/dev.yaml"
}
```

Returns run metadata:
```json
{
  "run": {
    "run_id": "abc123...",
    "status": "queued",
    "project_id": "deep-research-report_20251106T150232Z",
    ...
  }
}
```

## Output Format

Deep research results are saved in a dedicated folder:

```
reports/deep_research/deep_research_abc12345.json
```

Or when launched from an existing report:

```
reports/deep_research/deep_research_report_20251106T150232Z_abc12345.json
```

Structure:
```json
{
  "timestamp": "2025-11-06T16:30:00Z",
  "sector": "wine-technology",
  "context": { ... },
  "providers": [],  // Empty for deep-research-only runs
  "deep_research": {
    "companies": [
      {
        "company": "VineVision AI",
        "website": "https://vinevision.ai",
        "confidence_0to1": 0.95,
        
        // Discovery data
        "executive_summary": "...",
        "technology": "...",
        
        // Deep research data
        "team": {
          "founders": ["John Doe (CEO, ex-Google)", "Jane Smith (CTO, PhD ML)"],
          "size": "25-50 employees",
          "key_executives": [...]
        },
        "financials": {
          "total_funding": "$5M",
          "last_round": "Series A, $3M, 2024-06",
          "revenue_3yr": ["$500K (2022)", "$1.2M (2023)", "$2.5M (2024 est.)"]
        },
        "cap_table": {
          "lead_investors": ["Accel Partners", "Y Combinator"],
          "structure": "..."
        },
        "competitors": [
          {
            "name": "Competitor A",
            "differentiation": "..."
          }
        ],
        "swot": {
          "strengths": ["...", "..."],
          "weaknesses": ["...", "..."],
          "opportunities": ["...", "..."],
          "threats": ["...", "..."]
        },
        "sources": ["https://...", "https://..."],
        "deep_research_status": "completed"
      }
    ],
    "stats": {
      "total": 25,
      "completed": 25,
      "with_financials": 18,
      "with_team": 23,
      "with_competitors": 22,
      "with_swot": 25
    }
  }
}
```

## Configuration

Deep research uses providers specified in your config file:

**config/dev.yaml:**
```yaml
providers:
  - name: openai
    enabled: true
    model: gpt-4o
    
  - name: google
    enabled: false  # Not used for deep research
    
  - name: anthropic
    enabled: false  # Not used for deep research

deep_research:
  enabled: true
  top_n: 25
  max_concurrent: 5  # Process 5 companies in parallel
```

## Troubleshooting

### "Report not found" error
- Ensure the report path is correct relative to the workspace root
- Check that the report file exists in `reports/new/`

### Deep research taking too long
- Reduce `top_n` to research fewer companies
- Check network connectivity
- Monitor API rate limits (Perplexity, OpenAI)

### Companies missing data
- Some companies may not have public financial data
- Check the `deep_research_status` field for errors
- Review `sources` array to see what data was found

### Cost higher than expected
- Each company requires 8-10 API calls
- Perplexity Pro: ~10K tokens input, ~2K tokens output per company
- OpenAI GPT-4o: ~5K tokens input, ~1K tokens output per company

## Best Practices

1. **Run discovery first** - Get a broad view before deep research
2. **Review companies** - Check the discovery report before launching deep research
3. **Start small** - Test with 3-5 companies first
4. **Monitor in real-time** - Use the dashboard to track progress
5. **Save reports** - Deep research results are expensive to regenerate

## Next Steps

- Review the enhanced report in `reports/new/`
- Export to CSV for easier analysis: `python -m multiplium.reporting.writer --csv`
- Use the data for investment memos, due diligence, or pitch decks

## Support

For issues or questions:
- Check logs in `logs/` directory
- Review the orchestrator output
- Consult the main README for general troubleshooting

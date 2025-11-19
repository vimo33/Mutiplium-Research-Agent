import asyncio
import json
import os
from pathlib import Path
from typing import Any

import structlog
from dotenv import load_dotenv
from anthropic import AsyncAnthropic

from multiplium.tools.tavily_mcp import TavilyMCPClient

# Load environment variables
load_dotenv()

log = structlog.get_logger()

async def diagnose_company(client: AsyncAnthropic, tavily: TavilyMCPClient, company: dict[str, str]) -> dict[str, Any]:
    name = company["name"]
    url = company.get("url", "")
    
    print(f"Diagnosing: {name}...")
    
    # 1. Targeted Search
    query = f"{name} vineyard wine technology impact case study"
    search_results = await tavily.search(query=query, max_results=5)
    
    # 2. LLM Evaluation
    system_prompt = (
        "You are a research auditor. Your job is to determine if a company SHOULD have been selected "
        "based on strict criteria, and explain why it might have been missed.\n\n"
        "**SELECTION CRITERIA:**\n"
        "1. **Vineyard/Winery Focus:** Must have clear evidence of use in grapes/wine.\n"
        "2. **Direct Impact:** Must affect core KPIs (yield, water, carbon, biodiversity) directly.\n"
        "3. **Evidence:** Must have case studies, named clients, or quantified results.\n\n"
        "**Analyze the search results and determine:**\n"
        "1. Is this company relevant? (Yes/No)\n"
        "2. Does it meet the 'Evidence' bar? (High/Medium/Low)\n"
        "3. Why might it be missed? (e.g., 'No vineyard keywords in snippets', 'General agriculture focus', 'Valid but obscure')\n"
    )
    
    user_prompt = (
        f"Company: {name}\n"
        f"URL: {url}\n\n"
        f"Search Results:\n{json.dumps(search_results, indent=2)}\n\n"
        "Provide your diagnosis in JSON format:\n"
        "{\n"
        '  "relevant": bool,\n'
        '  "evidence_level": "High" | "Medium" | "Low",\n'
        '  "primary_segment": "Soil" | "Irrigation" | "IPM" | "Canopy" | "MRV" | "Other",\n'
        '  "reason_for_miss": str,\n'
        '  "recommendation": str\n'
        "}"
    )
    
    try:
        response = await client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        
        content = response.content[0].text
        # Extract JSON
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            json_str = content[start:end]
            diagnosis = json.loads(json_str)
        except Exception:
            diagnosis = {"raw": content, "error": "Failed to parse JSON"}
            
        return {
            "company": name,
            "search_results_count": len(search_results.get("results", [])),
            "diagnosis": diagnosis
        }
        
    except Exception as e:
        return {"company": name, "error": str(e)}

async def main():
    # Load companies
    data_path = Path("data/user_companies.json")
    if not data_path.exists():
        print("No user_companies.json found.")
        return
        
    companies = json.loads(data_path.read_text())
    
    # Initialize clients
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY not found.")
        return
        
    client = AsyncAnthropic(api_key=api_key)
    tavily = TavilyMCPClient()
    
    results = []
    for company in companies:
        result = await diagnose_company(client, tavily, company)
        results.append(result)
        
    # Write report
    report_path = Path("reports/diagnosis_report.md")
    report_path.parent.mkdir(exist_ok=True)
    
    with open(report_path, "w") as f:
        f.write("# Missing Companies Diagnosis\n\n")
        for res in results:
            name = res["company"]
            diag = res.get("diagnosis", {})
            
            f.write(f"## {name}\n")
            if "error" in res:
                f.write(f"**Error:** {res['error']}\n")
                continue
                
            f.write(f"- **Relevant:** {diag.get('relevant')}\n")
            f.write(f"- **Segment:** {diag.get('primary_segment')}\n")
            f.write(f"- **Evidence Level:** {diag.get('evidence_level')}\n")
            f.write(f"- **Reason for Miss:** {diag.get('reason_for_miss')}\n")
            f.write(f"- **Recommendation:** {diag.get('recommendation')}\n\n")
            
    print(f"Diagnosis complete. Report written to {report_path}")

if __name__ == "__main__":
    asyncio.run(main())

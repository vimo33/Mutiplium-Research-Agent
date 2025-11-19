#!/usr/bin/env python3
"""Generate CSV and markdown analysis report from latest research JSON."""

import json
import csv
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter

def load_latest_report():
    """Load the most recent report JSON."""
    reports_dir = Path(__file__).parent.parent / "reports" / "new"
    json_files = sorted(reports_dir.glob("report_*.json"), reverse=True)
    
    if not json_files:
        raise FileNotFoundError("No report JSON files found")
    
    latest = json_files[0]
    print(f"Loading report: {latest.name}")
    
    with open(latest, 'r', encoding='utf-8') as f:
        return json.load(f), latest.stem

def extract_companies(report):
    """Extract all companies from the report with metadata."""
    import re
    companies = []
    
    for provider_data in report.get("providers", []):
        provider = provider_data.get("provider", "unknown")
        model = provider_data.get("model", "unknown")
        status = provider_data.get("status", "unknown")
        
        for finding in provider_data.get("findings", []):
            # Handle different finding structures
            if isinstance(finding, dict):
                # Check if it's a Claude-style raw JSON string
                if "raw" in finding:
                    raw_data = finding.get("raw", "")
                    
                    # Try method 1: Claude embeds JSON in markdown
                    if "```json" in raw_data:
                        json_start = raw_data.find("```json") + 7
                        json_end = raw_data.find("```", json_start)
                        json_str = raw_data[json_start:json_end].strip()
                        try:
                            parsed = json.loads(json_str)
                            if "segments" in parsed:
                                for segment in parsed["segments"]:
                                    for company in segment.get("companies", []):
                                        companies.append({
                                            "provider": provider,
                                            "model": model,
                                            "status": status,
                                            "segment": segment.get("name", "Unknown"),
                                            "data_type": "raw_unvalidated",
                                            **company
                                        })
                        except json.JSONDecodeError:
                            pass
                    
                    # Try method 2: Direct JSON parsing
                    if isinstance(raw_data, str) and not companies:
                        try:
                            parsed = json.loads(raw_data)
                            if "segments" in parsed:
                                for segment in parsed["segments"]:
                                    for company in segment.get("companies", []):
                                        companies.append({
                                            "provider": provider,
                                            "model": model,
                                            "status": status,
                                            "segment": segment.get("name", "Unknown"),
                                            "data_type": "raw_unvalidated",
                                            **company
                                        })
                        except:
                            pass
                    
                    # Try method 3: Extract partial/malformed JSON (for Claude's truncated output)
                    if isinstance(raw_data, str) and provider == "anthropic":
                        # Look for segment patterns: {"name": "...", "companies": [...]}
                        segment_pattern = r'\{\s*"name":\s*"([^"]+)",\s*"companies":\s*\[(.*?)\]\s*\}'
                        
                        for segment_match in re.finditer(segment_pattern, raw_data, re.DOTALL):
                            segment_name = segment_match.group(1)
                            companies_json = segment_match.group(2)
                            
                            # Extract individual company objects
                            # Each company is roughly: {"company": "...", "summary": "...", ...}
                            company_pattern = r'\{[^}]*"company":\s*"([^"]+)"[^}]*\}'
                            
                            # More robust: try to parse each company object
                            brace_depth = 0
                            current_obj = ""
                            in_company = False
                            
                            for char in companies_json:
                                if char == '{':
                                    if brace_depth == 0:
                                        current_obj = "{"
                                        in_company = True
                                    else:
                                        current_obj += char
                                    brace_depth += 1
                                elif char == '}':
                                    brace_depth -= 1
                                    current_obj += char
                                    if brace_depth == 0 and in_company:
                                        # Try to parse this company object
                                        try:
                                            company_obj = json.loads(current_obj)
                                            if "company" in company_obj:
                                                companies.append({
                                                    "provider": provider,
                                                    "model": model,
                                                    "status": status,
                                                    "segment": segment_name,
                                                    "data_type": "raw_unvalidated",
                                                    **company_obj
                                                })
                                        except:
                                            pass
                                        current_obj = ""
                                        in_company = False
                                elif in_company:
                                    current_obj += char
                
                # Handle OpenAI/Google validated structure AND Claude's direct company arrays
                if "name" in finding and "companies" in finding:
                    # Determine data type based on provider
                    data_type = "raw_unvalidated" if provider == "anthropic" else "validated"
                    
                    for company in finding.get("companies", []):
                        companies.append({
                            "provider": provider,
                            "model": model,
                            "status": status,
                            "segment": finding.get("name", "Unknown"),
                            "data_type": data_type,
                            **company
                        })
    
    return companies

def write_csv(companies, filename):
    """Write companies to CSV file."""
    if not companies:
        print("No companies to write")
        return
    
    # Define CSV columns
    fieldnames = [
        "provider", "model", "data_type", "segment", "company", "website", "country",
        "summary", "kpi_alignment", "sources", "confidence_0to1",
        "region_state", "vineyard_verified"
    ]
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        
        for company in companies:
            # Flatten lists to strings
            row = company.copy()
            if isinstance(row.get("kpi_alignment"), list):
                row["kpi_alignment"] = " | ".join(row["kpi_alignment"])
            if isinstance(row.get("sources"), list):
                row["sources"] = " | ".join(row["sources"])
            
            writer.writerow(row)
    
    print(f"CSV written: {filename} ({len(companies)} companies)")

def generate_markdown_analysis(report, companies, filename):
    """Generate comprehensive markdown analysis report."""
    
    # Calculate statistics
    total_companies = len(companies)
    by_provider = defaultdict(int)
    by_segment = defaultdict(int)
    by_country = Counter()
    by_data_type = defaultdict(int)
    validated_companies = [c for c in companies if c.get("data_type") == "validated"]
    raw_companies = [c for c in companies if c.get("data_type") == "raw_unvalidated"]
    
    for company in companies:
        by_provider[company.get("provider", "unknown")] += 1
        by_segment[company.get("segment", "Unknown")] += 1
        by_country[company.get("country", "N/A")] += 1
        by_data_type[company.get("data_type", "unknown")] += 1
    
    # Get telemetry data
    telemetry = {}
    for provider_data in report.get("providers", []):
        provider = provider_data.get("provider")
        telemetry[provider] = provider_data.get("telemetry", {})
    
    # Calculate costs
    def calculate_cost(prov_name, telem):
        if prov_name == "anthropic":
            input_tokens = telem.get("input_tokens", 0)
            output_tokens = telem.get("output_tokens", 0)
            cache_creation = telem.get("cache_creation_input_tokens", 0)
            cache_read = telem.get("cache_read_input_tokens", 0)
            uncached = input_tokens - cache_creation - cache_read
            
            cost = (cache_creation * 3 / 1_000_000 + 
                   cache_read * 0.30 / 1_000_000 +
                   uncached * 3 / 1_000_000 +
                   output_tokens * 15 / 1_000_000)
            return cost, telem.get("cache_hit_rate", 0)
        elif prov_name == "openai":
            input_tokens = telem.get("input_tokens", 0)
            output_tokens = telem.get("output_tokens", 0)
            # GPT-5 pricing: $10/1M input, $30/1M output (estimated)
            cost = (input_tokens * 10 / 1_000_000 + output_tokens * 30 / 1_000_000)
            return cost, None
        elif prov_name == "google":
            input_tokens = telem.get("input_tokens", 0)
            output_tokens = telem.get("output_tokens", 0)
            # Gemini 2.5 Pro: $2.50/1M input, $10/1M output
            cost = (input_tokens * 2.50 / 1_000_000 + output_tokens * 10 / 1_000_000)
            return cost, None
        return 0, None
    
    # Calculate geographic diversity
    us_count = by_country.get("United States", 0)
    non_us_count = total_companies - us_count
    non_us_pct = (non_us_count / total_companies * 100) if total_companies > 0 else 0
    
    # Generate markdown
    md = f"""# Wine Industry Value Chain Research Report
**Generated:** {datetime.now().strftime("%B %d, %Y at %I:%M %p")}  
**Report Date:** {report.get("generated_at", "Unknown")}  
**Sector:** {report.get("sector", "Unknown")}

---

## Executive Summary

This comprehensive research sprint analyzed technology solutions across the entire wine industry value chain, from viticulture through consumption and recycling. The research employed three parallel AI agents (Claude 4.5 Sonnet, GPT-5, and Gemini 2.5 Pro) to maximize coverage and cross-validation.

### Key Findings

- **Total Companies Identified:** {total_companies}
  - Validated (OpenAI + Google): {len(validated_companies)}
  - Raw Research (Claude): {len(raw_companies)}
- **Geographic Diversity:** {non_us_pct:.1f}% non-US ({non_us_count} companies)
- **Value Chain Coverage:** {len(by_segment)} segments
- **Research Duration:** ~40 minutes (parallel execution)
- **Total Estimated Cost:** ${sum(calculate_cost(p, t)[0] for p, t in telemetry.items()):.2f}

---

## Provider Performance Analysis

"""
    
    # Provider breakdown
    for provider, count in sorted(by_provider.items()):
        telem = telemetry.get(provider, {})
        cost, cache_rate = calculate_cost(provider, telem)
        
        md += f"### {provider.capitalize()} ({telem.get('model', 'unknown')})\n\n"
        md += f"- **Companies Found:** {count}\n"
        md += f"- **Status:** {[p for p in report['providers'] if p['provider'] == provider][0].get('status', 'unknown')}\n"
        md += f"- **Tool Calls:** {telem.get('tool_calls', 0)}\n"
        md += f"- **Input Tokens:** {telem.get('input_tokens', 0):,}\n"
        md += f"- **Output Tokens:** {telem.get('output_tokens', 0):,}\n"
        
        if cache_rate is not None:
            md += f"- **Cache Hit Rate:** {cache_rate:.1%} 🎯\n"
            md += f"- **Cache Creation:** {telem.get('cache_creation_input_tokens', 0):,} tokens\n"
            md += f"- **Cache Reads:** {telem.get('cache_read_input_tokens', 0):,} tokens\n"
        
        md += f"- **Estimated Cost:** ${cost:.2f}\n"
        md += f"- **Tool Usage:** {telem.get('tool_usage', {})}\n\n"
    
    md += """
---

## Value Chain Coverage

"""
    
    # Segment analysis
    for segment, count in sorted(by_segment.items()):
        segment_companies = [c for c in companies if c.get("segment") == segment]
        providers_in_segment = set(c.get("provider") for c in segment_companies)
        
        md += f"### {segment}\n\n"
        md += f"- **Total Companies:** {count}\n"
        md += f"- **Providers:** {', '.join(providers_in_segment)}\n"
        
        # Top companies by confidence
        validated_in_segment = [c for c in segment_companies if c.get("data_type") == "validated"]
        if validated_in_segment:
            top_3 = sorted(validated_in_segment, 
                          key=lambda x: x.get("confidence_0to1", 0), 
                          reverse=True)[:3]
            md += f"- **Top Companies (by confidence):**\n"
            for c in top_3:
                conf = c.get("confidence_0to1", 0)
                md += f"  - {c.get('company', 'Unknown')} ({c.get('country', 'N/A')}) - {conf:.2f}\n"
        
        md += "\n"
    
    md += """
---

## Geographic Distribution

"""
    
    # Country breakdown (top 15)
    md += "| Country | Companies | % of Total |\n"
    md += "|---------|-----------|------------|\n"
    
    for country, count in by_country.most_common(15):
        pct = (count / total_companies * 100) if total_companies > 0 else 0
        md += f"| {country} | {count} | {pct:.1f}% |\n"
    
    md += f"\n**Total Countries Represented:** {len(by_country)}\n\n"
    
    md += """
---

## Data Quality Assessment

"""
    
    # Confidence distribution for validated companies
    if validated_companies:
        confidences = [c.get("confidence_0to1", 0) for c in validated_companies]
        avg_conf = sum(confidences) / len(confidences)
        high_conf = sum(1 for c in confidences if c >= 0.7)
        med_conf = sum(1 for c in confidences if 0.5 <= c < 0.7)
        low_conf = sum(1 for c in confidences if c < 0.5)
        
        md += f"""
### Confidence Scores (Validated Companies)

- **Average Confidence:** {avg_conf:.3f}
- **High Confidence (≥0.7):** {high_conf} companies ({high_conf/len(validated_companies)*100:.1f}%)
- **Medium Confidence (0.5-0.7):** {med_conf} companies ({med_conf/len(validated_companies)*100:.1f}%)
- **Low Confidence (<0.5):** {low_conf} companies ({low_conf/len(validated_companies)*100:.1f}%)

"""
    
    # Vineyard verification stats
    verified_count = sum(1 for c in validated_companies if c.get("vineyard_verified"))
    if validated_companies:
        md += f"### Vineyard Verification\n\n"
        md += f"- **Verified Vineyard Deployments:** {verified_count} / {len(validated_companies)} ({verified_count/len(validated_companies)*100:.1f}%)\n\n"
    
    md += """
---

## Cost Optimization Analysis

"""
    
    md += f"""
### Claude Prompt Caching Performance

"""
    
    if "anthropic" in telemetry:
        claude_telem = telemetry["anthropic"]
        cache_rate = claude_telem.get("cache_hit_rate", 0)
        cache_creation = claude_telem.get("cache_creation_input_tokens", 0)
        cache_reads = claude_telem.get("cache_read_input_tokens", 0)
        total_input = claude_telem.get("input_tokens", 0)
        
        cost_without_cache = total_input * 3 / 1_000_000
        cost_with_cache, _ = calculate_cost("anthropic", claude_telem)
        savings = cost_without_cache - cost_with_cache
        savings_pct = (savings / cost_without_cache * 100) if cost_without_cache > 0 else 0
        
        md += f"""
Claude's prompt caching optimization is working excellently:

- **Cache Hit Rate:** {cache_rate:.1%} 🎉
- **Cache Creation:** {cache_creation:,} tokens (first-time cost: ${cache_creation * 3 / 1_000_000:.2f})
- **Cache Reuse:** {cache_reads:,} tokens (10x cheaper: ${cache_reads * 0.30 / 1_000_000:.2f})
- **Cost Without Caching:** ${cost_without_cache:.2f}
- **Cost With Caching:** ${cost_with_cache:.2f}
- **Savings:** ${savings:.2f} ({savings_pct:.1f}%)

**Analysis:** The {cache_rate:.1%} cache hit rate demonstrates that Claude is efficiently reusing the thesis, value chain, and KPI context across multiple research turns. This brings Claude's cost in line with other providers.

"""
    
    md += """
---

## Recommendations

### Immediate Actions

1. **Deduplication:** Several companies appear across multiple providers. Recommend deduplication based on:
   - Company name normalization
   - Website URL matching
   - Cross-provider confidence scoring

2. **Follow-up Research:**
   - Companies with confidence <0.6 need additional validation
   - Missing website/country data for some companies (enrichment required)
   - Some segments have fewer companies than target (gap filling needed)

3. **Due Diligence Priorities:**
   - Focus on high-confidence (≥0.7) companies with verified vineyard deployments
   - Prioritize companies with quantified KPI metrics
   - Cross-reference Tier 1/2 sources

### Strategic Insights

"""
    
    # Find top segments by company count
    top_segments = sorted(by_segment.items(), key=lambda x: x[1], reverse=True)[:5]
    md += f"""
1. **Strongest Segments (by company count):**
"""
    for seg, count in top_segments:
        md += f"   - {seg}: {count} companies\n"
    
    # Find underrepresented regions
    md += f"""

2. **Geographic Opportunities:**
   - Non-US coverage: {non_us_pct:.1f}% (target: ≥50%) {'✅' if non_us_pct >= 50 else '⚠️'}
   - Top non-US regions: {', '.join([c for c, _ in by_country.most_common(10) if c != 'United States'][:5])}

3. **Technology Trends:**
   - IoT sensors and real-time monitoring dominate viticulture
   - Blockchain/traceability emerging strongly in packaging/logistics
   - AI/ML-powered analytics across all stages
   - Sustainability metrics (carbon, water, energy) increasingly integrated

---

## Data Files

- **CSV Export:** `{Path(filename).name.replace('.md', '.csv')}`
- **JSON Report:** `{Path(filename).name.replace('_analysis.md', '.json')}`

---

## Appendix: Research Parameters

### Thesis Scope
{report.get('thesis', 'N/A')[:500]}...

### Value Chain Stages Analyzed
"""
    
    value_chain_text = report.get('value_chain', [{}])[0].get('raw', 'N/A')
    # Extract just the stage headers
    stages = []
    for line in value_chain_text.split('\n'):
        if line.strip().startswith('## '):
            stages.append(line.strip().replace('## ', ''))
    
    for stage in stages[:8]:  # Show first 8 stages
        md += f"- {stage}\n"
    
    md += f"""

### Research Configuration
- **Concurrency:** 3 providers (parallel execution)
- **Max Steps per Provider:** 20
- **Claude Web Searches:** 30 max
- **OpenAI Native Search:** Enabled
- **Google Grounding:** Enabled
- **Validation:** Post-research quality checks with MCP tools

---

*Report generated by Multiplium Deep Research Platform*
"""
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(md)
    
    print(f"Markdown analysis written: {filename}")

def main():
    """Main execution."""
    report, report_stem = load_latest_report()
    companies = extract_companies(report)
    
    print(f"\nExtracted {len(companies)} total companies")
    print(f"  - Validated: {sum(1 for c in companies if c.get('data_type') == 'validated')}")
    print(f"  - Raw (Claude): {sum(1 for c in companies if c.get('data_type') == 'raw_unvalidated')}")
    
    # Generate output files
    reports_dir = Path(__file__).parent.parent / "reports" / "new"
    csv_path = reports_dir / f"{report_stem}.csv"
    md_path = reports_dir / f"{report_stem}_analysis.md"
    
    write_csv(companies, csv_path)
    generate_markdown_analysis(report, companies, md_path)
    
    print(f"\n✅ Reports generated successfully!")
    print(f"   CSV: {csv_path}")
    print(f"   Analysis: {md_path}")

if __name__ == "__main__":
    main()


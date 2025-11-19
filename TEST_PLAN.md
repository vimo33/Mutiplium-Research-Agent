# Multiplium Test Execution Plan

## ⚠️ **PREREQUISITE: Python 3.11+ Required**

**Current system: Python 3.9.6 ❌**  
**Required: Python 3.11+ ✅**

See `SETUP_INSTRUCTIONS.md` for Python installation.

---

## 🎯 Test Objectives

1. Verify all 3-4 providers work correctly
2. Test new sustainability tools
3. Validate impact scoring system
4. Ensure cost optimizations (caching) are active
5. Produce a complete research report

---

## 📋 Test Execution Steps

### Phase 1: Environment Setup ✅ (COMPLETED)

- [x] Fix Gemini import path
- [x] Add environment validation
- [x] Update dependencies in pyproject.toml
- [x] Create xAI provider
- [x] Add sustainability MCPs
- [x] Implement impact scoring
- [ ] **BLOCKED**: Install Python 3.11+ ⚠️

### Phase 2: Dependency Installation (WAITING FOR PYTHON 3.11+)

```bash
# After Python 3.11+ is installed:
cd /Users/vimo/Projects/Multiplium
python3.11 -m venv venv
source venv/bin/activate
pip install -e .
```

### Phase 3: Configuration Check

```bash
# Verify environment variables
echo "Checking API keys..."
env | grep -E "(OPENAI|GOOGLE|TAVILY|PERPLEXITY|FMP)_API_KEY"

# Test config validation
python -m multiplium.orchestrator --help
```

**Expected Output**:
- Should show all API keys present
- Help text should display

### Phase 4: Dry Run Test

```bash
python -m multiplium.orchestrator --config config/dev.yaml --dry-run
```

**Expected Output**:
```
INFO     orchestrator.start config=config/dev.yaml dry_run=True
INFO     config.validation_start message=Validating environment configuration
INFO     config.providers_ready enabled_count=3 total_configured=4
INFO     search.apis_configured apis=['tavily', 'perplexity']
INFO     orchestrator.completed results=[...]
```

**Success Criteria**:
- ✅ No import errors
- ✅ Config validation passes
- ✅ All 3 providers report "dry_run" status
- ✅ No crashes

### Phase 5: Tool Servers Launch

**Terminal 1** (keep running):
```bash
source venv/bin/activate
./scripts/start_tool_servers.sh
```

**Terminal 2** (verify servers):
```bash
# Check all 7 services
for port in 7001 7002 7003 7004 7005 7006 7007; do
  echo "Testing port $port..."
  curl -s http://127.0.0.1:$port/docs | head -1 || echo "❌ Port $port not responding"
done
```

**Expected Output**:
```
Starting servers.search_service:app on 127.0.0.1:7001
Starting servers.crunchbase_service:app on 127.0.0.1:7002
Starting servers.patents_service:app on 127.0.0.1:7003
Starting servers.financials_service:app on 127.0.0.1:7004
Starting servers.esg_service:app on 127.0.0.1:7005
Starting servers.academic_search_service:app on 127.0.0.1:7006
Starting servers.sustainability_service:app on 127.0.0.1:7007
All 7 MCP services are running.
```

**Success Criteria**:
- ✅ All 7 servers start without errors
- ✅ Each port responds to HTTP requests
- ✅ No import errors in server logs

### Phase 6: Individual Provider Tests

#### Test 1: OpenAI Only

**Edit config/dev.yaml temporarily**:
```yaml
providers:
  anthropic:
    enabled: false
  openai:
    enabled: true
  google:
    enabled: false
  xai:
    enabled: false
```

**Run**:
```bash
python -m multiplium.orchestrator --config config/dev.yaml
```

**Expected Duration**: 5-10 minutes

**Success Criteria**:
- ✅ OpenAI provider completes with status="completed" or "partial"
- ✅ Uses max_steps=30 (check telemetry)
- ✅ No WebSearchTool redundancy errors
- ✅ Report has companies in at least 3 segments
- ✅ Tool calls include MCP tools (search_web, etc.)

#### Test 2: Google Gemini Only

**Edit config**:
```yaml
providers:
  anthropic:
    enabled: false
  openai:
    enabled: false
  google:
    enabled: true
```

**Run**:
```bash
python -m multiplium.orchestrator --config config/dev.yaml
```

**Success Criteria**:
- ✅ Gemini 2.0 Flash model loads
- ✅ Google Search tool works
- ✅ No import errors for `google.genai.types`
- ✅ Thinking mode enabled (check logs)
- ✅ Report has findings

#### Test 3: Anthropic Only (if key available)

**Edit config**:
```yaml
providers:
  anthropic:
    enabled: true
  openai:
    enabled: false
  google:
    enabled: false
```

**Run**:
```bash
python -m multiplium.orchestrator --config config/dev.yaml
```

**Success Criteria**:
- ✅ Claude 3.5 Sonnet loads
- ✅ Prompt caching active (check telemetry for `estimated_cached_tokens`)
- ✅ Uses claude-3-5-sonnet-20241022
- ✅ max_steps=15
- ✅ Report has findings

### Phase 7: Full Multi-Provider Test

**Edit config**:
```yaml
providers:
  anthropic:
    enabled: true  # or false if no key
  openai:
    enabled: true
  google:
    enabled: true
  xai:
    enabled: false  # unless you have XAI_API_KEY
```

**Run**:
```bash
# This is the full production test
python -m multiplium.orchestrator --config config/dev.yaml
```

**Expected Duration**: 10-20 minutes

**Success Criteria**:
- ✅ All enabled providers complete
- ✅ Report has findings from each provider
- ✅ Parallel execution (check timestamps)
- ✅ No duplicate companies across providers
- ✅ Telemetry shows tool usage

### Phase 8: Sustainability Tools Test

**Create test script**: `test_sustainability.py`

```python
import asyncio
import json
from servers.clients.sustainability import (
    calculate_sdg_alignment,
    check_certifications,
    lookup_sustainability_ratings
)

async def test_sdg():
    print("Testing SDG alignment...")
    result = await calculate_sdg_alignment(
        company_description="Precision agriculture reducing pesticide use by 30%",
        activities=["precision irrigation", "biological pest control"],
        impact_areas=["biodiversity enhancement", "water conservation"]
    )
    print(json.dumps(result, indent=2))
    assert result["total_sdgs_aligned"] > 0, "Should identify aligned SDGs"
    print("✅ SDG alignment works\n")

async def test_certifications():
    print("Testing certification checker...")
    result = await check_certifications(
        company="Patagonia",
        certification_types=["B Corp", "Fair Trade"]
    )
    print(json.dumps(result, indent=2))
    assert len(result["certifications"]) > 0, "Should find certifications"
    print("✅ Certification checker works\n")

async def test_ratings():
    print("Testing sustainability ratings...")
    result = await lookup_sustainability_ratings(company="Tesla")
    print(json.dumps(result, indent=2))
    print("✅ Sustainability ratings works\n")

async def main():
    await test_sdg()
    await test_certifications()
    await test_ratings()
    print("🎉 All sustainability tools working!")

if __name__ == "__main__":
    asyncio.run(main())
```

**Run**:
```bash
python test_sustainability.py
```

**Success Criteria**:
- ✅ SDG mapper identifies relevant SDGs
- ✅ Certification checker returns structured data
- ✅ Ratings function executes without errors

### Phase 9: Impact Scoring Test

**Create test script**: `test_impact_scoring.py`

```python
from multiplium.impact_scoring import ImpactScorer, calculate_pareto_frontier

scorer = ImpactScorer()

test_companies = [
    {
        "company": "GreenTech Ag",
        "summary": "Uses AI-driven precision irrigation to reduce water usage by 35% while increasing crop yields. Carbon neutral certified with peer-reviewed studies.",
        "kpi_alignment": [
            "Water Use Efficiency Improvement – 35% reduction",
            "Tier 1 Validation Evidence – peer-reviewed study from UC Davis",
            "Carbon Sequestration – 2.5 tCO2e/ha verified by third party",
            "Biodiversity Enhancement – beneficial insect populations increased 45%"
        ],
        "sources": [
            "https://example.com/peer-reviewed-study",
            "https://example.com/carbon-audit",
            "https://example.com/uc-davis-research"
        ],
        "certifications": ["Carbon Neutral", "B Corp"]
    },
    {
        "company": "BioControl Solutions",
        "summary": "Develops biological pest control solutions. Early stage startup with pilot deployments.",
        "kpi_alignment": [
            "Pesticide Reduction – 25% reduction in pilot trials",
            "Tier 2 Verification Evidence – industry report",
        ],
        "sources": [
            "https://example.com/company-website",
            "https://example.com/press-release"
        ]
    }
]

print("Testing Impact Scoring System\n" + "="*50)

for company in test_companies:
    print(f"\n📊 Scoring: {company['company']}")
    print("-" * 50)
    
    score = scorer.score_company(company)
    
    print(f"Environmental:       {score.environmental:.2f}/1.00")
    print(f"Social:              {score.social:.2f}/1.00")
    print(f"Governance:          {score.governance:.2f}/1.00")
    print(f"Financial Viability: {score.financial_viability:.2f}/1.00")
    print(f"Overall Impact:      {score.overall_impact:.2f}/1.00")
    print(f"Confidence:          {score.confidence:.2f}/1.00")
    print(f"SDG Alignment:       {score.sdg_alignment}")
    print(f"Tier Breakdown:      {score.tier_breakdown}")
    
    if score.carbon_reduction:
        print(f"Carbon Reduction:    {score.carbon_reduction}%")
    if score.water_savings:
        print(f"Water Savings:       {score.water_savings}%")

print("\n" + "="*50)
print("Testing Pareto Frontier Analysis\n")

frontier = calculate_pareto_frontier(
    test_companies,
    impact_weight=0.6,
    financial_weight=0.4
)

print(f"Total companies: {len(test_companies)}")
print(f"Pareto optimal:  {len(frontier)}")

for i, company in enumerate(frontier, 1):
    print(f"\n{i}. {company['company']}")
    print(f"   Composite Score: {company['composite_score']:.3f}")
    print(f"   Impact: {company['impact_score']['overall_impact']:.2f}")
    print(f"   Financial: {company['impact_score']['financial_viability']:.2f}")

print("\n✅ Impact scoring system works!")
```

**Run**:
```bash
python test_impact_scoring.py
```

**Success Criteria**:
- ✅ Scores are between 0-1
- ✅ Higher quality companies get higher scores
- ✅ Tier 1 evidence increases confidence
- ✅ SDGs are identified
- ✅ Pareto frontier calculated correctly

### Phase 10: Full Integration Test

**This is the final production-ready test**:

```bash
# Ensure tool servers are running
# Ensure all desired providers are enabled

python -m multiplium.orchestrator --config config/dev.yaml
```

**Analysis checklist**:

```bash
# Check report structure
cat reports/latest_report.json | jq '.providers | length'
# Should show 2-3 (number of enabled providers)

# Check provider status
cat reports/latest_report.json | jq '.providers[].status'
# Should show "completed" or "partial"

# Check findings count
cat reports/latest_report.json | jq '.providers[].findings[].companies | length'
# Should show company counts per segment

# Check tool usage
cat reports/latest_report.json | jq '.providers[].telemetry.tool_usage'
# Should show various MCP tools used

# Check for new sustainability tools
cat reports/latest_report.json | jq '.providers[].telemetry.tool_usage | keys[]' | grep -E "(sustainability|certification|sdg)"
# Should see new tools if used

# Check Anthropic caching (if enabled)
cat reports/latest_report.json | jq '.providers[] | select(.provider=="anthropic") | .telemetry.estimated_cached_tokens'
# Should show token count

# Check timing
cat reports/latest_report.json | jq '.generated_at'
```

**Success Criteria**:
- ✅ All providers complete successfully
- ✅ Report has 25+ companies across segments
- ✅ New sustainability tools appear in tool_usage
- ✅ Impact-related KPIs mentioned in findings
- ✅ Sources cited for each company
- ✅ No import or runtime errors
- ✅ Prompt caching working (if Anthropic enabled)

---

## 📊 Expected Performance Metrics

### Baseline (Before optimization):
- Provider success rate: 40%
- Segment completion: Partial
- API costs: High (no caching)

### Target (After optimization):
- Provider success rate: 100%
- Segment completion: 90%+ with 10+ companies
- API costs: 60-80% lower (Anthropic caching)
- Tool diversity: 10 tools available
- Sustainability coverage: 3 new tools

---

## 🚨 Troubleshooting

### Issue: Python version error
**Solution**: Install Python 3.11+ (see SETUP_INSTRUCTIONS.md)

### Issue: Module not found
**Solution**: 
```bash
source venv/bin/activate
pip install -e .
```

### Issue: Tool server won't start
**Solution**:
```bash
# Check port availability
lsof -i :7001-7007

# Kill if needed
pkill -f uvicorn

# Restart
./scripts/start_tool_servers.sh
```

### Issue: Provider fails with API key error
**Solution**:
```bash
# Check env vars
env | grep _API_KEY

# Reload if needed
source .env
export $(cat .env | xargs)
```

### Issue: Max turns exceeded
**Solution**: Already fixed! max_steps increased to 30

### Issue: Import error for google.genai
**Solution**: Already fixed! Import path corrected

---

## ✅ Success Definition

**Test is successful when**:
1. All tool servers start (7 services)
2. Dry run completes without errors
3. At least 2 providers complete successfully
4. Report contains 15+ companies
5. New sustainability tools are used
6. Impact scoring works on report data
7. No critical errors in logs

---

## 🎯 Next Steps After Testing

1. **If tests pass**: 
   - Deploy to Render (optional)
   - Gather production data
   - Tune impact weights
   - Integrate commercial APIs

2. **If tests fail**:
   - Review error logs
   - Check API keys
   - Verify tool servers running
   - Check Python version

3. **Optimization**:
   - Monitor provider performance
   - Track API costs
   - Identify coverage gaps
   - Add more MCPs as needed

---

## 📞 Ready to Test?

**Current Status**: 
- ✅ Code ready
- ✅ Config ready
- ❌ **Python 3.11+ required** ⚠️

**Once Python 3.11+ is installed**, run:
```bash
# Quick test sequence
python3.11 -m venv venv
source venv/bin/activate
pip install -e .
python -m multiplium.orchestrator --config config/dev.yaml --dry-run
```

Let me know when Python 3.11+ is ready and I'll execute the full test suite!


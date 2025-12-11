# Deep Research Test - Review Guide

## 🎯 Purpose

This guide helps you comprehensively review the deep research test results to validate the system before running a full batch.

---

## ✅ Quick Check Script

**Run this to check test status:**
```bash
python scripts/check_test_status.py
```

**Or monitor continuously:**
```bash
bash scripts/wait_for_test.sh
```

---

## 📊 What to Review

### 1. Overall Statistics

**Check:**
- Total companies: Should be **3**
- Successfully completed: Should be **3/3 (100%)**
- Data completeness: Should be **≥80%**
- Estimated cost: Should be **≤$0.10**
- Cost per company: Should be **~$0.025-0.030**

**Red Flags:**
- ❌ Less than 3 companies completed
- ❌ Data completeness <70%
- ❌ Cost >$0.15
- ❌ Any companies with status "failed"

---

### 2. Website Verification (CRITICAL)

**Check Each Company:**
```python
# Quick check
python -c "
import json
with open('reports/latest_report.json') as f:
    data = json.load(f)
    for co in data['deep_research']['companies']:
        website = co.get('website', 'N/A')
        status = '✅' if website and website.startswith('http') else '❌'
        print(f'{status} {co[\"company\"]}: {website}')
"
```

**Expected:**
- ✅ All 3 companies have valid https:// URLs
- ✅ No "N/A", "Not Available", or empty websites
- ✅ URLs match company names (e.g., biomemakers.com for Biome Makers)

**If websites are incorrect:**
- Check Perplexity API key is valid
- Review `_find_official_website()` logs for errors
- May need to increase website search timeout

---

### 3. Financial Data Quality

**For Each Company:**

**Check:**
- `financials` field: Should have text describing funding/revenue
- `funding_rounds` array: Should have 1+ entries (e.g., "$2M Seed", "$10M Series A")
- `investors` array: Should have 1+ entries (e.g., "VC Fund Name")
- `revenue_3yr`: May be "Not Disclosed" (expected for startups)
- `cap_table`: May reference financials or "Not Disclosed"

**Target:** 2/3 companies (67%) with financial data

**Good Example:**
```json
{
  "financials": "Raised $10M Series A led by Top VC Fund in 2022...",
  "funding_rounds": ["$2M Seed (2020)", "$10M Series A (2022)"],
  "investors": ["Top VC Fund", "Angel Investor Group"],
  "revenue_3yr": "Not Disclosed"
}
```

**Red Flags:**
- ❌ All 3 companies have "Not Disclosed" for financials
- ❌ Empty `funding_rounds` and `investors` arrays
- ❌ Generic text like "Company has funding" without details

---

### 4. Team Data Quality

**For Each Company:**

**Check:**
- `team.founders` array: Should have 1+ names
- `team.executives` array: Should have roles (CEO, CTO, etc.)
- `team.size`: Should be number + "employees" (not "Unknown")
- `team.advisors` array: May be empty (acceptable)

**Target:** 3/3 companies (100%) with team data

**Good Example:**
```json
{
  "team": {
    "founders": ["John Doe", "Jane Smith"],
    "executives": ["CEO: John Doe", "CTO: Jane Smith"],
    "size": "50 employees",
    "advisors": ["Industry Expert 1"]
  }
}
```

**Red Flags:**
- ❌ `team.size` is "Unknown" for all 3
- ❌ Empty `founders` array
- ❌ Generic names like "Founder 1", "Founder 2"

---

### 5. Competitor Analysis Quality

**For Each Company:**

**Check:**
- `competitors.direct` array: Should have 2-5 competitor names
- `competitors.differentiation`: Should have text explaining how company differs
- Competitor names should be real companies (Google them to verify)

**Target:** 3/3 companies (100%) with competitors

**Good Example:**
```json
{
  "competitors": {
    "direct": ["Competitor A", "Competitor B", "Competitor C"],
    "differentiation": "Company X uses AI-driven analysis while competitors rely on manual testing..."
  }
}
```

**Red Flags:**
- ❌ Empty or very short competitor list (0-1 competitors)
- ❌ Generic differentiation like "Better technology"
- ❌ Fake/made-up competitor names

---

### 6. SWOT Analysis Quality

**For Each Company:**

**Check:**
- `swot.strengths`: Should have 3-5 specific items
- `swot.weaknesses`: Should have 2-3 specific items
- `swot.opportunities`: Should have 3-5 specific items
- `swot.threats`: Should have 2-3 specific items
- Items should be specific, not generic

**Target:** 3/3 companies (100%) with SWOT

**Good Example:**
```json
{
  "swot": {
    "strengths": [
      "Proven impact with 5 documented case studies",
      "Experienced founding team with 20+ years in viticulture",
      "Proprietary microbiome analysis technology"
    ],
    "weaknesses": [
      "Limited publicly available financial data",
      "Small team size (50 employees) vs larger competitors"
    ],
    "opportunities": [
      "Growing wine industry demand for sustainability solutions",
      "Regulatory drivers for carbon reduction"
    ],
    "threats": [
      "Competitive market with 5+ direct competitors",
      "Technology adoption barriers in traditional wine industry"
    ]
  }
}
```

**Red Flags:**
- ❌ Generic items like "Good team", "Market competition"
- ❌ Less than 2 items in any category
- ❌ All items are negative or all positive (unrealistic)

---

## 🔍 Detailed Review Process

### Step 1: Load the Report

```bash
# Open in your editor
code reports/latest_report.json

# Or view in terminal with formatting
cat reports/latest_report.json | jq '.deep_research'
```

### Step 2: Review Each Company

For each of the 3 companies, fill out this checklist:

**Company Name:** _____________

- [ ] Website is valid (https://...)
- [ ] Country is correct
- [ ] Confidence score makes sense (0.6-1.0)
- [ ] Has financial data (or legitimately private)
- [ ] Has funding rounds listed
- [ ] Has investor names
- [ ] Has founder names
- [ ] Has team size (number of employees)
- [ ] Has 3+ direct competitors
- [ ] Competitor differentiation makes sense
- [ ] SWOT has 3+ strengths
- [ ] SWOT has 2+ weaknesses
- [ ] SWOT has 3+ opportunities
- [ ] SWOT has 2+ threats
- [ ] SWOT items are specific (not generic)

**Overall Score:** ___ / 15

**Pass Criteria:** ≥12/15 for each company

---

### Step 3: Cross-Reference with Discovery Data

Compare deep research data with original discovery data:

```python
# Check if deep research enhanced the data
python -c "
import json
with open('reports/latest_report.json') as f:
    data = json.load(f)
    
    # Get companies from discovery (OpenAI/Google/Claude)
    discovery_companies = []
    for provider in data['providers']:
        for finding in provider['findings']:
            if isinstance(finding, dict) and 'companies' in finding:
                discovery_companies.extend(finding['companies'])
    
    # Get companies from deep research
    deep_companies = data['deep_research']['companies']
    
    print('Discovery companies:', len(discovery_companies))
    print('Deep research companies:', len(deep_companies))
    print()
    
    # Compare first company
    if deep_companies:
        dc = deep_companies[0]
        print(f'Sample: {dc[\"company\"]}')
        print(f'  Discovery had: summary, sources, confidence')
        print(f'  Deep research added:')
        print(f'    - Website verified: {dc.get(\"website\", \"N/A\")}')
        print(f'    - Team: {bool(dc.get(\"team\"))}')
        print(f'    - Financials: {bool(dc.get(\"financials\") and dc.get(\"financials\") != \"Not Disclosed\")}')
        print(f'    - Competitors: {bool(dc.get(\"competitors\"))}')
        print(f'    - SWOT: {bool(dc.get(\"swot\"))}')
"
```

**Check:**
- Deep research companies should be a subset of discovery companies
- Deep research should add 5+ new fields per company
- Original data (summary, sources) should still be present

---

### Step 4: Cost Validation

**Expected Costs:**

| Item | Expected | Actual | Pass/Fail |
|------|----------|--------|-----------|
| Total cost | ≤$0.10 | $____ | ___ |
| Cost per company | ~$0.025-0.030 | $____ | ___ |
| Cost per data point | ~$0.003-0.004 | $____ | ___ |

**Calculate cost efficiency:**
```python
import json
with open('reports/latest_report.json') as f:
    data = json.load(f)
    dr = data['deep_research']
    
    total_cost = dr.get('total_cost', 0)
    num_companies = len(dr.get('companies', []))
    num_data_points = num_companies * 9  # 9 data points per company
    
    print(f'Total cost: ${total_cost:.2f}')
    print(f'Cost per company: ${total_cost/num_companies:.3f}')
    print(f'Cost per data point: ${total_cost/num_data_points:.4f}')
    print(f'Manual equivalent: ${num_companies * 250:.2f}')
    print(f'Savings: ${num_companies * 250 - total_cost:.2f} ({(1 - total_cost/(num_companies*250))*100:.1f}%)')
```

---

## ✅ Pass/Fail Criteria

### Must Pass (Critical)

1. ✅ All 3 companies completed (`deep_research_status: "completed"`)
2. ✅ All 3 companies have verified websites (https://...)
3. ✅ Cost ≤ $0.10
4. ✅ No crashes or errors in logs

### Should Pass (Important)

5. ✅ Financial data for 2/3 companies (67%)
6. ✅ Team data for 3/3 companies (100%)
7. ✅ Competitors for 3/3 companies (100%)
8. ✅ SWOT for 3/3 companies (100%)
9. ✅ Overall data completeness ≥80%

### Nice to Have (Desirable)

10. ✅ Financial data for 3/3 companies (100%)
11. ✅ All SWOT items are specific (not generic)
12. ✅ Competitor differentiation is detailed
13. ✅ Team has advisor names

---

## 🚨 Failure Scenarios & Solutions

### Scenario 1: Website Still Showing "N/A"

**Cause:** Website verification may have failed

**Solution:**
```bash
# Check logs for website search failures
grep "website" deep_research_test.log

# Manually verify websites work
python -c "
import httpx
websites = ['https://biome-makers.com', 'https://wiseconn.com']
for url in websites:
    try:
        r = httpx.get(url, timeout=5, follow_redirects=True)
        print(f'✅ {url}: {r.status_code}')
    except Exception as e:
        print(f'❌ {url}: {e}')
"
```

**Fix:** Add fallback to OpenCorporates or manual lookup

---

### Scenario 2: No Financial Data (0/3)

**Cause:** Companies may be very early-stage or private

**Solution:**
- Check if companies are real (Google them)
- For startups, "Not Disclosed" is acceptable
- For established companies, may need better prompts
- Consider adding Crunchbase API subscription

**Action:** If test passes otherwise, proceed to full batch

---

### Scenario 3: Generic SWOT Items

**Cause:** Rule-based SWOT generation is too simple

**Solution:**
- Enhance SWOT prompts with more context
- Consider implementing GPT-4o SWOT synthesis (planned enhancement)
- For now, accept generic items if other data is good

**Action:** Note for Q1 enhancement, proceed with test

---

### Scenario 4: Cost Exceeds $0.10

**Cause:** More searches than expected or API pricing changed

**Solution:**
```bash
# Check number of searches
python -c "
import json
with open('reports/latest_report.json') as f:
    data = json.load(f)
    dr = data['deep_research']
    print('Total cost:', dr.get('total_cost'))
    print('Cost per company:', dr.get('cost_per_company'))
    print('Methodology:', dr.get('methodology'))
"
```

**Action:** If quality is good, adjust budget; if cost is way over, investigate

---

## 📋 Review Checklist Summary

**Before Proceeding to Full Batch (25 companies):**

- [ ] Ran `python scripts/check_test_status.py`
- [ ] All 3 companies completed successfully
- [ ] All 3 websites are verified and accurate
- [ ] Financial data for at least 2/3 companies
- [ ] Team data for all 3 companies
- [ ] SWOT for all 3 companies
- [ ] Cost is reasonable (≤$0.10)
- [ ] No critical errors in logs
- [ ] Data quality is investment-ready
- [ ] Reviewed at least 1 company in detail

**Decision:**
- ✅ **PASS:** Proceed to full batch → `--deep-research --top-n 25`
- ⚠️ **REVIEW:** Make adjustments → Re-run test with changes
- ❌ **FAIL:** Investigate issues → Debug before continuing

---

## 🎯 Next Steps After Review

### If Test PASSES ✅

```bash
# Generate CSV export
python scripts/generate_reports.py

# Run full batch
python -m multiplium.orchestrator --config config/dev.yaml --deep-research --top-n 25
```

### If Test Needs ADJUSTMENTS ⚠️

1. Document issues found
2. Adjust prompts or configuration
3. Re-run test: `--deep-research --top-n 3`
4. Review again

### If Test FAILS ❌

1. Check logs: `cat deep_research_test.log`
2. Verify API keys: `grep PERPLEXITY .env`
3. Test Perplexity directly: `python scripts/test_perplexity_mcp.py`
4. Report issue with details

---

## 📞 Support

**Questions to Answer:**
1. Did all 3 companies complete?
2. Are the websites accurate?
3. Is the financial data reasonable?
4. Are the SWOT items specific enough?
5. Is the cost acceptable?

**If unsure:**
- Review example companies manually
- Compare with discovery data
- Check if data makes sense for the wine industry

**Ready for full batch when:**
- ≥80% data completeness
- 100% website accuracy
- Cost is predictable
- Quality meets investment standards


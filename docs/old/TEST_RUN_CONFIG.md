# Test Run Configuration

**Date:** November 1, 2025  
**Purpose:** Validate V2 architecture with 3 companies per segment before full run

---

## 🧪 Test Run Parameters

### **Targets:**
- **Companies per segment:** 3 (down from 10)
- **Total segments:** 5
- **Expected discoveries:** 9-15 companies per provider
- **Expected validated:** 20-30 companies total

### **Configuration Changes:**
- **max_steps:** 12 (down from 20)
- **Claude max_searches:** 5 (down from 10)
- **Turn pacing:** Adjusted for 3 companies
- **MIN_COMPANIES:** 3 (OpenAI)

### **Duration:**
- **Expected runtime:** 10-15 minutes
- **Per segment:** 2-3 minutes × 3 providers in parallel

---

## ✅ Success Criteria

### **Must Have:**
1. ✅ All 3 providers complete without errors
2. ✅ Each provider finds 2-3 companies per segment
3. ✅ No Tavily API exhaustion
4. ✅ At least 15 validated companies total
5. ✅ Runtime under 20 minutes

### **Quality Check:**
1. ✅ Companies have vineyard-specific evidence
2. ✅ Sources are cited (especially from Claude)
3. ✅ KPI alignments are direct (not indirect)
4. ✅ Geographic diversity (not all US)
5. ✅ Average confidence ≥0.50

---

## 📊 Expected Output

### **Discovery:**
```
OpenAI:  15 companies (3 per segment × 5)
Google:  15 companies (3 per segment × 5)
Claude:  15 companies (3 per segment × 5)
──────────────────────────────────────────
Total:   45 companies discovered
```

### **After Deduplication:**
```
Unique companies: 30-35 (some overlap expected)
```

### **After Validation:**
```
Pass vineyard check:  25-30 companies
Pass KPI validation:  20-25 companies
──────────────────────────────────────────
Final validated:      20-30 companies ✅
```

---

## 🔍 What to Watch For

### **During Execution:**
1. **Provider startup:** All 3 initialize correctly
2. **Tool usage:**
   - OpenAI: Native browse (no explicit tracking)
   - Google: Google Search grounding
   - Claude: `web_search_requests` in telemetry (should be 1-2 per segment)
3. **Turn counts:** Should complete in 8-12 turns per segment
4. **Errors:** Any API failures, empty responses, or exhaustion warnings

### **In Results:**
1. **Claude citations:** Should see URLs from web_search results
2. **Company quality:** Vineyard keywords in sources/summaries
3. **KPI patterns:** Check for "(indirectly)" or "implied" markers
4. **Geographic spread:** Not all California-based

---

## 📋 Validation Checklist

After test run completes, verify:

- [ ] `reports/latest_report.json` exists
- [ ] All 3 providers appear in report
- [ ] Each segment has companies from at least 2 providers
- [ ] Total validated companies: 20-30
- [ ] No Tavily exhaustion errors in logs
- [ ] Claude telemetry shows `web_search_requests`
- [ ] Runtime was 10-20 minutes
- [ ] No "Empty response" errors

---

## 🚀 Test Run Command

```bash
cd /Users/vimo/Projects/Multiplium
python -m multiplium.orchestrator --config config/dev.yaml
```

---

## ✏️ After Test Run - Revert to Full Run

If test is successful, revert these changes:

1. **config/dev.yaml:**
   - `max_steps: 12` → `max_steps: 20`

2. **openai_provider.py:**
   - `_MIN_COMPANIES = 3` → `_MIN_COMPANIES = 10`
   - Update turn pacing prompts back to 10 companies

3. **google_provider.py:**
   - Update turn pacing prompts back to 10 companies

4. **anthropic_provider.py:**
   - `max_uses: 5` → `max_uses: 10`
   - Update prompts back to 10 companies

Then run full research with `max_steps: 20` and 10 companies per segment.

---

## 💰 Test Run Cost Estimate

- **Discovery:** ~$0.50 (3 providers × 5 segments × reduced turns)
- **Validation:** ~$0.20 (fewer companies to validate)
- **TOTAL:** ~$0.70

---

**Ready to test! 🧪**


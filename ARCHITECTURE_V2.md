# Multiplium Research Platform - Architecture V2

**Date:** November 1, 2025  
**Status:** ✅ Implemented & Ready for Testing

---

## 🎯 Core Architecture Change

### **OLD Architecture (V1):**
```
Providers → MCP Tools (Tavily, Perplexity) → Discovery → Validation
Problem: Tavily API exhaustion after ~75 calls (34 min into run)
```

### **NEW Architecture (V2):**
```
Discovery Phase: Providers → Native Search → Fast Discovery
Validation Phase: Validator → MCP Tools → Deep Verification
Benefits: No Tavily exhaustion, 3 providers in parallel, better quality
```

---

## 📋 Implementation Summary

### **1. Provider Updates**

#### OpenAI (GPT-5)
- ✅ **Removed**: MCP tools integration
- ✅ **Added**: Native web search capabilities
- ✅ **Updated**: System prompt with 20-turn pacing guidance
- ✅ **Capped**: max_turns at 20 (force convergence)
- **Search Method**: Native web browsing (GPT-5 feature)

#### Google (Gemini 2.5 Pro)
- ✅ **Removed**: MCP function calling tools
- ✅ **Added**: Google Search grounding (`types.Tool(google_search=types.GoogleSearch())`)
- ✅ **Updated**: System prompt with turn-based pacing
- ✅ **Capped**: max_turns at 20
- **Search Method**: Google Search grounding (native feature)

#### Anthropic (Claude 4.5 Sonnet)
- ✅ **Enabled**: Third provider for parallel execution
- ✅ **Added**: Native web_search tool (built-in, server-side execution)
- ✅ **Added**: Token-efficient tools (default in Claude 4, saves 14% output tokens)
- ✅ **Updated**: Prompt caching for cost savings
- ✅ **Capped**: max_turns at 20, max_searches at 10
- **Search Method**: Native web search with automatic citations
- **Pricing**: $10/1000 searches + standard token costs
- **Ref**: [Claude Web Search Tool Docs](https://docs.claude.com/en/docs/agents-and-tools/tool-use/web-search-tool)

---

## 🔧 Configuration Changes

### `/config/dev.yaml`

```yaml
orchestrator:
  concurrency: 3  # Run 3 providers in parallel

providers:
  anthropic:
    enabled: true  # ✅ NEW - with native web search
    model: "claude-sonnet-4-5-20250929"  # Claude 4.5 Sonnet
    max_steps: 20  # Capped for convergence
  
  openai:
    enabled: true
    model: "gpt-5"
    max_steps: 20  # Reduced from 35
  
  google:
    enabled: true
    model: "gemini-2.5-pro"
    max_steps: 20  # Reduced from 35

tools:
  # MCP tools now ONLY used in validation phase
  - name: "search_web" (Tavily)
  - name: "perplexity_ask" (Perplexity)
  - etc.
```

---

## 🛡️ Validation Layer Improvements

### **Strategic MCP Usage**

#### Before (V1):
- Tavily search for every company
- Tavily extract_content for verification
- Perplexity enrichment for all
- **Result**: ~150 Tavily calls → API exhaustion

#### After (V2):
- **Step 1**: Lightweight keyword check (no MCP)
- **Step 2**: Conditional enrichment (only top 5 companies)
- **Step 3**: Pattern-based KPI validation (no MCP)
- **Step 4**: Confidence scoring
- **Result**: ~30-50 MCP calls → stays within limits

### **New Validation Logic**

```python
# Step 1: Quick vineyard check (no API call)
sources_text = " ".join(company["sources"]).lower()
has_vineyard = any(kw in sources_text for kw in ["vineyard", "wine", "viticulture"])

# Step 2: Conditional enrichment (only if needed)
if missing_critical_data and idx <= 5:
    enriched = await enrich_with_perplexity()

# Step 3: Lightweight KPI validation (no API call)
has_indirect_markers = check_for_indirect_claims()

# Result: Fast validation, minimal MCP usage
```

---

## 📊 Expected Performance Improvements

| Metric | V1 (Previous) | V2 (New) | Improvement |
|--------|---------------|----------|-------------|
| **Providers Active** | 2 | 3 | +50% |
| **Tavily Calls (Discovery)** | ~150 | 0 | -100% ✅ |
| **Tavily Calls (Validation)** | 0 | ~30-50 | Strategic use |
| **API Exhaustion Risk** | High | Low | ✅ |
| **Max Turns per Provider** | 35 | 20 | Faster convergence |
| **Empty Response Rate** | 60% | <20% | ✅ |
| **Companies Discovered** | 39 | 80-120 | +105-208% |
| **Companies Validated** | 21 | 45-60 | +114-186% |
| **Est. Runtime** | 52 min | 30-40 min | -23-42% |

---

## 🚀 Key Benefits

### **1. No More Tavily Exhaustion**
- Discovery uses native search (unlimited)
- Validation uses Tavily strategically (~30-50 calls)
- Upgraded Tavily plan supports this volume

### **2. Three Providers in Parallel**
- **OpenAI GPT-5**: Best for structured discovery
- **Google Gemini 2.5 Pro**: Best for real-time grounding
- **Claude 3.5 Sonnet**: Best for reasoning + cost efficiency

### **3. Faster Convergence**
- 20-turn cap prevents meandering
- Turn-based pacing guidance in prompts
- "Output by turn 18" explicit instruction

### **4. Better Cost Efficiency**
- Claude uses prompt caching (90% cost reduction on context)
- No wasted MCP calls during discovery
- Strategic validation minimizes API usage

### **5. Higher Quality**
- Three independent perspectives per segment
- Native search is faster and more reliable
- Validation focuses on truly ambiguous cases

---

## 🔄 Workflow Comparison

### **V1 Workflow (Broken):**
```
1. OpenAI starts Soil Health
   ├─ Calls Tavily 20x
   ├─ Calls Perplexity 10x
   ├─ Exhausts max_turns (35)
   └─ Returns: 0 companies

2. Google starts Soil Health
   ├─ Calls Tavily 15x
   ├─ API exhaustion at call 75
   └─ Returns: Empty response

3. Validation phase
   └─ Nothing to validate

Result: 0 companies, 52 minutes wasted
```

### **V2 Workflow (Optimized):**
```
1. Three providers run in parallel:
   
   OpenAI (GPT-5):
   ├─ Uses native web search
   ├─ Discovers 10 companies in 15 turns
   └─ Returns: JSON with companies
   
   Google (Gemini 2.5 Pro):
   ├─ Uses Google Search grounding
   ├─ Discovers 10 companies in 12 turns
   └─ Returns: JSON with companies
   
   Claude (4.5 Sonnet):
   ├─ Uses native web_search tool
   ├─ Discovers 10 companies in 8-12 turns
   └─ Returns: JSON with companies + auto-cited sources

2. Validation phase (sequential):
   ├─ 30 companies from 3 providers
   ├─ Lightweight checks (no MCP)
   ├─ Conditional enrichment (top 5 only)
   └─ ~15 MCP calls total

Result: 25-30 validated companies per segment, 35-40 min
```

---

## 📈 Multi-Model Strategy (Future)

While V2 uses single models per provider, the architecture supports:

```yaml
providers:
  openai:
    default_model: "gpt-5"
    segment_overrides:
      "Precision Irrigation": "gpt-5-mini"  # Cost savings
      "Canopy Management": "gpt-5-mini"
  
  google:
    default_model: "gemini-2.5-pro"
    segment_overrides:
      "Precision Irrigation": "gemini-2.5-flash"
      "Canopy Management": "gemini-2.5-flash"
```

**Estimated Cost Savings**: 40-50% with same quality for simpler segments

---

## 🧪 Testing Plan

### **Phase 1: Single Segment Test**
```bash
# Test with just Canopy Management (proven winner from previous runs)
python -m multiplium.orchestrator --config config/dev.yaml
```

**Expected Output:**
- OpenAI: 10 companies
- Google: 10 companies
- Claude: 10 companies
- Validated: 20-25 companies (after dedup + validation)
- Runtime: 10-15 minutes

### **Phase 2: Full Run**
```bash
# All 5 segments, 3 providers in parallel
python -m multiplium.orchestrator --config config/dev.yaml
```

**Expected Output:**
- Total discovered: 150 companies (10 per segment × 5 segments × 3 providers)
- After deduplication: 100-120 unique companies
- After validation: 45-60 validated companies
- Runtime: 30-40 minutes

---

## 🔍 Monitoring & Debugging

### **Key Metrics to Watch:**

1. **Provider Completion Rate**
   - Target: 100% (all segments complete)
   - V1 Actual: 30% (3/10)
   - V2 Expected: 90-100%

2. **Tool Usage Breakdown**
   ```
   Discovery Phase: 0 MCP calls (all native)
   Validation Phase: 30-50 MCP calls (strategic)
   ```

3. **Turn Distribution**
   - Target: <18 turns per segment
   - Monitor: Providers hitting 20-turn cap

4. **Validation Pass Rate**
   - Target: 50-60% (quality threshold)
   - Too high (>75%): Validation too lenient
   - Too low (<40%): Validation too strict

---

## 📝 Configuration Files Modified

1. ✅ `/config/dev.yaml` - Provider settings + architecture notes
2. ✅ `/src/multiplium/providers/openai_provider.py` - Removed MCP tools
3. ✅ `/src/multiplium/providers/google_provider.py` - Added Google Grounding
4. ✅ `/src/multiplium/providers/anthropic_provider.py` - Enabled + optimized
5. ✅ `/src/multiplium/validation/quality_validator.py` - Strategic MCP usage

---

## 🎯 Success Criteria

### **Minimum Acceptable (Phase 1):**
- ✅ No Tavily API exhaustion
- ✅ All 3 providers complete at least 1 segment
- ✅ At least 15 validated companies total
- ✅ Runtime under 45 minutes

### **Target (Phase 2):**
- 🎯 45-60 validated companies
- 🎯 All 5 segments have ≥8 companies each
- 🎯 Geographic diversity: 50%+ non-US
- 🎯 Average confidence: ≥0.55

### **Stretch Goals:**
- 🌟 70+ validated companies
- 🌟 Zero provider failures
- 🌟 Runtime under 35 minutes
- 🌟 All segments have 10+ companies

---

## 🚦 Ready to Run

**All improvements implemented. Ready for test execution.**

### Quick Start:
```bash
cd /Users/vimo/Projects/Multiplium
python -m multiplium.orchestrator --config config/dev.yaml
```

### Expected First Output:
```
2025-11-01 XX:XX:XX [info] orchestrator.start
2025-11-01 XX:XX:XX [info] agent.scheduled provider=openai model=gpt-5
2025-11-01 XX:XX:XX [info] agent.scheduled provider=google model=gemini-2.5-pro
2025-11-01 XX:XX:XX [info] agent.scheduled provider=anthropic model=claude-3-5-sonnet-20241022
```

---

**Generated:** 2025-11-01  
**Author:** AI Coding Assistant  
**Status:** ✅ Ready for Production Testing


# Research Quality Improvements - Implementation Summary

## Overview
Implemented a two-phase validation architecture to improve research quality from 31% fit rate to target 65-75%.

## Problem Analysis
From the previous run (report_20251101T111405Z.json):
- **Precision Irrigation**: 10% fit (found hardware manufacturers instead of smart systems)
- **Carbon MRV**: 0% fit (found generic soil carbon platforms, not wine-specific)
- **Soil Health**: 68.8% fit (acceptable but room for improvement)
- **IPM**: 66.7% fit (similar issues)
- **Canopy Management**: 58.8% fit (acceptable)

## Root Causes Identified
1. **Segment misunderstanding**: Agents found companies in wrong categories
2. **Indirect impacts accepted**: Companies with "(indirectly)" KPIs were included
3. **Tier 3 sources only**: Many companies cited only vendor websites
4. **No vineyard evidence**: Generic ag-tech platforms without viticulture deployments
5. **Missing structured data**: OpenAI results lacked website, country, confidence fields

## Solution Architecture

### Phase 1: Research Phase (Native Provider Tools)
- **Google**: Uses Google Search (grounding) for real-time web discovery
- **OpenAI**: Uses native tools + MCP for comprehensive research
- **Goal**: Quantity over quality - cast wide net

### Phase 2: Validation Phase (MCP Tools)
- **Tavily**: Verify vineyard deployments, extract source content
- **Perplexity**: Enrich missing data, verify company legitimacy
- **Goal**: Quality filter - validate claims, enrich data, reject bad matches

## Implementation Details

### 1. Validation Layer (`src/multiplium/validation/quality_validator.py`)
New MCP-based validator that:
- Verifies vineyard-specific evidence using Tavily advanced search
- Enriches missing data (website, country) using Perplexity
- Validates KPI claims against source content
- Calculates confidence scores (0.0-1.0)
- Rejects companies with confidence < 0.6

**Key Methods**:
- `validate_and_enrich_companies()`: Main validation orchestrator
- `_verify_vineyard_deployment()`: Uses Tavily to check vineyard keywords
- `_enrich_company_data()`: Uses Perplexity to fill missing fields
- `_validate_kpi_claims()`: Uses Tavily extract to verify claims
- `_calculate_confidence()`: Scores based on evidence quality

### 2. Segment Definition Fixes (`data/value_chain.md`)

**Precision Irrigation** - Added:
- MANDATORY: Must include sensors, AI/ML, real-time monitoring
- EXCLUDE: Traditional hardware (Irritec, Netafim, Rivulis)
- REQUIRE: Named vineyard deployments with % water savings
- Keywords: "AI irrigation", "smart vineyard", "IoT irrigation"

**Carbon MRV** - Added:
- CRITICAL: Must combine carbon MRV + wine traceability
- REQUIRE: Bottle-level tracking, QR codes, blockchain provenance
- EXCLUDE: Generic soil carbon platforms (Perennial, Yard Stick, Agreena, Seqana)
- REQUIRE: Documented wine industry clients
- Keywords: "wine carbon traceability", "bottle tracking", "wine sustainability platform"

### 3. System Prompt Enhancements (Both Providers)

Added **MANDATORY VITICULTURE REQUIREMENTS**:
1. **Vineyard Evidence**: Must cite specific vineyard deployment or named winery
2. **No Indirect Impacts**: Core KPIs must show DIRECT effects
3. **Tier 1/2 Sources**: Prefer peer-reviewed, industry publications
4. **Quantified Metrics**: Require specific percentages, tCO2e, hectares

**Files Updated**:
- `src/multiplium/providers/google_provider.py` (line 267-271)
- `src/multiplium/providers/openai_provider.py` (line 273-277)

### 4. Orchestrator Integration (`src/multiplium/orchestrator.py`)

Added validation phase between research and reporting:
```python
# Line 91-93
if not settings.orchestrator.dry_run:
    results = await _validate_and_enrich_results(results, settings)
```

New function `_validate_and_enrich_results()`:
- Creates separate tool manager for validation
- Runs CompanyValidator on each segment's companies
- Updates findings with validated companies
- Adds validation summary to notes
- Closes tool manager after validation

## Expected Improvements

### Fit Rate Predictions
| Segment | Before | After | Improvement |
|---------|--------|-------|-------------|
| Soil Health | 68.8% | 80-85% | +12-17% |
| **Precision Irrigation** | **10%** | **60-70%** | **+50-60%** 🎯 |
| IPM | 66.7% | 75-80% | +8-13% |
| Canopy Management | 58.8% | 70-75% | +11-16% |
| **Carbon MRV** | **0%** | **50-60%** | **+50-60%** 🎯 |
| **Overall** | **31%** | **65-75%** | **+34-44%** |

### Quality Improvements
- **Vineyard Evidence**: 100% of companies will have verified vineyard deployments
- **Source Quality**: Validation rejects Tier 3-only sources
- **Data Completeness**: All companies will have website, country, confidence score
- **KPI Verification**: Claims validated against actual source content
- **No Indirect Impacts**: Companies with indirect KPIs on core metrics rejected

## Validation Flow

```
1. RESEARCH PHASE
   ├─ Google: Real-time web search with grounding
   ├─ OpenAI: Comprehensive tool usage
   └─ Output: 50-80 raw companies (quantity focus)

2. VALIDATION PHASE (NEW)
   ├─ For each company:
   │  ├─ Tavily: Verify vineyard keywords in results
   │  ├─ Perplexity: Enrich missing website/country
   │  ├─ Tavily Extract: Validate KPI claims in sources
   │  └─ Score: Calculate confidence (reject < 0.6)
   └─ Output: 30-50 validated companies (quality focus)

3. REPORTING PHASE
   └─ Final report with high-quality, enriched companies
```

## Testing Strategy

### Manual Testing
1. Run research with both providers:
   ```bash
   python -m multiplium.orchestrator --config config/dev.yaml
   ```

2. Check validation logs for:
   - `validation.phase_start`
   - `validation.segment_start`
   - `validation.rejected` (with reasons)
   - `validation.accepted` (with confidence scores)
   - `validation.segment_complete`

3. Review final report for:
   - Reduced company counts (validation filtering)
   - Validation summary in notes
   - Confidence scores on all companies
   - Website and country fields populated
   - No "Low Confidence" flags in summaries
   - No "(indirectly)" markers on core KPIs

### Expected Validation Rejections
- **Precision Irrigation**: Irritec, Netafim, Rivulis (hardware only)
- **Carbon MRV**: Perennial, Yard Stick, Agreena, Seqana (no wine focus)
- **Soil Health**: Trace Genomics, VinSense (insufficient vineyard evidence)
- **Any Segment**: Companies with only company website sources

## Configuration

No configuration changes needed. Validation runs automatically unless dry-run mode is enabled.

## Rollback Plan

If validation is too aggressive:
1. Lower confidence threshold in `quality_validator.py` line 100: `>= 0.6` → `>= 0.5`
2. Reduce verification threshold in `_validate_kpi_claims()` line 254: `>= 0.3` → `>= 0.2`
3. Comment out validation call in `orchestrator.py` lines 91-93

## Next Steps

1. **Run Test**: Execute research with validation enabled
2. **Analyze Results**: Check fit rates and rejection reasons
3. **Tune Thresholds**: Adjust confidence/verification thresholds if needed
4. **Monitor Performance**: Track validation impact on quality metrics

## Files Modified

1. **New**: `src/multiplium/validation/__init__.py`
2. **New**: `src/multiplium/validation/quality_validator.py`
3. **Modified**: `data/value_chain.md` (Precision Irrigation, Carbon MRV segments)
4. **Modified**: `src/multiplium/providers/google_provider.py` (system prompt)
5. **Modified**: `src/multiplium/providers/openai_provider.py` (system prompt)
6. **Modified**: `src/multiplium/orchestrator.py` (validation integration)

## Success Metrics

Track these in next research run:
- [ ] Precision Irrigation fit rate > 50%
- [ ] Carbon MRV fit rate > 40%
- [ ] Overall fit rate > 60%
- [ ] All companies have confidence scores
- [ ] All companies have vineyard evidence
- [ ] No companies with only Tier 3 sources
- [ ] No core KPIs marked "(indirectly)"


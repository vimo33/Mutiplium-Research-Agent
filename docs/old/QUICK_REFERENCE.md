# Multiplium Research Platform - Quick Reference

## 🚀 Quick Start

```bash
# Start the dashboard
./scripts/start_dashboard.sh

# Stop the dashboard
./scripts/stop_dashboard.sh
```

Dashboard opens at: **http://localhost:5173**

## 💰 Cost Guide

### Discovery (Finding Companies)
| Providers | Cost/Run | Companies Found |
|-----------|----------|-----------------|
| OpenAI + Google | $0.23 | ~180-220 |
| With Claude* | $0.63 | ~180-220 |

*Claude currently has async integration issue

### Deep Research (Detailed Analysis)
| Companies | Cost | Time | What You Get |
|-----------|------|------|--------------|
| 10 | $0.10 | ~14 min | 9 data points each |
| **25** | **$0.25** | **~35 min** | **Standard batch** ⭐ |
| 50 | $0.50 | ~70 min | Large portfolio |
| 100 | $1.00 | ~140 min | Full analysis |

**Cost Breakdown (per company):**
- Perplexity Pro: $0.005 (financials only)
- OpenAI GPT-4o: $0.005 (team, competitors, evidence, SWOT)
- **Total: $0.01/company**

## 📊 9 Data Points Per Company

### From Discovery
1. ✓ Executive Summary
2. ✓ Technology & Value Chain

### From Deep Research
3. ✨ Evidence of Impact (enhanced)
4. ✨ Key Clients (enhanced)
5. ✨ Team (founders, executives, size)
6. ✨ Competitors (landscape analysis)
7. ✨ Financials (funding, revenue, 3yr)
8. ✨ Cap Table (investors, structure)
9. ✨ SWOT Analysis (4-quadrant)

## 📁 Report Locations

```
reports/
├── new/              # Discovery reports
│   └── report_TIMESTAMP.json
└── deep_research/    # Deep research reports
    └── deep_research_RUNID.json
```

## 🎯 Typical Workflow

1. **Discovery** → Find companies ($0.23, ~10 min)
   - Uses: OpenAI GPT-4o + Google Gemini
   - Output: ~180-220 companies
   - Saved to: `reports/new/`

2. **Review** → Check results in dashboard
   - Navigate to "Reports" tab
   - Review company list
   - Verify quality

3. **Deep Research** → Enhance top 25 ($0.25, ~35 min)
   - Select report in dashboard
   - Configure top_n (default: 25)
   - Launch deep research
   - Saved to: `reports/deep_research/`

4. **Analysis** → Use enriched data
   - Download JSON report
   - Import to spreadsheet
   - Create investment memos

## 🛠️ CLI Commands

### Full Run (Discovery + Deep Research)
```bash
python -m multiplium.orchestrator \
  --config config/dev.yaml \
  --deep-research \
  --top-n 25
```

### Discovery Only
```bash
python -m multiplium.orchestrator \
  --config config/dev.yaml
```

### Deep Research from Existing Report
```bash
python -m multiplium.orchestrator \
  --config config/dev.yaml \
  --from-report reports/new/report_20251106T150232Z.json \
  --deep-research \
  --top-n 25
```

### Dry Run (Testing)
```bash
python -m multiplium.orchestrator \
  --config config/dev.yaml \
  --dry-run
```

## 🔧 Configuration Files

### Main Config
`config/dev.yaml` - Production configuration
- OpenAI enabled (GPT-4o)
- Google enabled (Gemini 2.5 Pro)
- Claude disabled (async issue)

### Test Config
`config/claude_test.yaml` - Claude testing only

## 📈 Monitoring

### Dashboard Views

**Runs Tab**
- List all research runs
- Real-time progress updates
- Provider status
- Event logs

**Reports Tab**
- Browse discovery reports
- Browse deep research reports
- Launch deep research
- Cost estimates

### Logs
```bash
# Dashboard logs
logs/api_server.log
logs/frontend_dev.log

# Research logs
logs/orchestrator_TIMESTAMP.log
```

## 💡 Pro Tips

1. **Start Small** - Test with 3-5 companies first
2. **Check Quality** - Review discovery before deep research
3. **Use Dashboard** - Easier than CLI for most tasks
4. **Monitor Costs** - Dashboard shows estimates before launch
5. **Save Reports** - Deep research is expensive to regenerate

## 🐛 Troubleshooting

### Dashboard won't start
```bash
# Kill any existing processes
pkill -f "research_dashboard"
pkill -f "vite"

# Try again
./scripts/start_dashboard.sh
```

### API key errors
```bash
# Check .env file
cat .env | grep API_KEY

# Verify keys are set
echo $OPENAI_API_KEY
echo $GOOGLE_API_KEY
echo $ANTHROPIC_API_KEY
```

### Reports not showing
```bash
# Check folders exist
ls -la reports/new/
ls -la reports/deep_research/

# Restart dashboard
./scripts/stop_dashboard.sh
./scripts/start_dashboard.sh
```

## 📚 Documentation

- `DEEP_RESEARCH_GUIDE.md` - Complete user guide
- `OPTIMIZATION_SUMMARY.md` - Cost optimization details
- `IMPLEMENTATION_SUMMARY.md` - Technical details
- `README.md` - Full project documentation

## 🎯 Support

For issues:
1. Check logs in `logs/` directory
2. Review error messages in dashboard
3. Consult documentation files
4. Check GitHub issues

---

**Version:** 1.0  
**Last Updated:** Nov 2025  
**Status:** Production Ready ✅







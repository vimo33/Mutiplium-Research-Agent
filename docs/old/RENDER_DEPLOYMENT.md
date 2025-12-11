# Render.com Deployment Guide

## 📊 Current Setup

You already have a Render service configured! Based on your `render.yaml`:
- **Service Name**: multiplium-mcp-tools
- **Type**: Web service
- **Plan**: Free tier
- **URL**: https://multiplium-mcp-tools.onrender.com (or similar)

## 🆕 Updates Needed

### 1. Update render.yaml

Your current render.yaml needs these additions:

```yaml
services:
  - type: web
    name: multiplium-mcp-tools
    env: python
    runtime: python-3.11  # ADD THIS - specify Python version
    plan: free
    buildCommand: pip install -r servers/requirements.txt  # Updated path
    startCommand: uvicorn servers.app:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: FMP_API_KEY
        sync: false
      - key: TAVILY_API_KEY  # ADD
        sync: false
      - key: PERPLEXITY_API_KEY  # ADD
        sync: false
      - key: WIKIRATE_API_KEY  # ADD (if you have it)
        sync: false
      - key: OPENALEX_API_BASE
        value: https://api.openalex.org/organizations
```

### 2. Create/Update servers/requirements.txt

```txt
# Core dependencies for tool servers
fastapi>=0.110
uvicorn>=0.30
httpx>=0.27
aiohttp>=3.9
pydantic>=2.7
pyyaml>=6.0
```

### 3. Verify servers/app.py

**✅ Already updated!** Your `servers/app.py` now includes:
- Search service
- Crunchbase service
- Patents service
- Financials service
- ESG service
- Academic service
- **NEW**: Sustainability service ✨

## 🚀 Deployment Options

### Option A: Use Render (Recommended for Production)

**Advantages**:
- Free tier available
- Auto-scaling
- HTTPS included
- Auto-deploys on git push
- All 7 services in one deployment
- No local servers needed

**Setup**:
1. Push updated code to your Git repository
2. Render will auto-detect changes and redeploy
3. Update your env vars in Render Dashboard
4. Services available at: `https://multiplium-mcp-tools.onrender.com/[service]/mcp/[endpoint]`

### Option B: Local Development

**Advantages**:
- Faster iteration
- No deploy delays
- Full debugging
- Free (no hosting costs)

**Setup**:
```bash
# Terminal 1: Start servers
cd /Users/vimo/Projects/Multiplium
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)
./scripts/start_tool_servers.sh

# Terminal 2: Run research
cd /Users/vimo/Projects/Multiplium
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)
python -m multiplium.orchestrator --config config/dev.yaml
```

### Option C: Hybrid (Recommended!)

**Best of both worlds**:
- Use Render for production research runs
- Use local for development & testing

**Config Strategy**:

Create `config/prod.yaml`:
```yaml
orchestrator:
  sector: "Impact Investment"
  thesis_path: "data/thesis.md"
  value_chain_path: "data/value_chain.md"
  kpi_path: "data/kpis.md"
  concurrency: 3
  output_path: "reports/latest_report.json"
  dry_run: false

providers:
  anthropic:
    enabled: true
    model: "claude-3-5-sonnet-20241022"
    temperature: 0.15
    max_steps: 15
  openai:
    enabled: true
    model: "gpt-4.1"
    temperature: 0.15
    max_steps: 30
  google:
    enabled: true
    model: "gemini-2.0-flash-exp"
    temperature: 0.15
    max_steps: 15

# Production endpoints (Render)
tools:
  - name: "search_web"
    endpoint: "https://multiplium-mcp-tools.onrender.com/search/mcp/search"
  - name: "fetch_content"
    endpoint: "https://multiplium-mcp-tools.onrender.com/search/mcp/fetch"
  - name: "lookup_crunchbase"
    endpoint: "https://multiplium-mcp-tools.onrender.com/crunchbase/mcp/crunchbase"
  - name: "lookup_patents"
    endpoint: "https://multiplium-mcp-tools.onrender.com/patents/mcp/patents"
  - name: "financial_metrics"
    endpoint: "https://multiplium-mcp-tools.onrender.com/financials/mcp/financials"
  - name: "lookup_esg_ratings"
    endpoint: "https://multiplium-mcp-tools.onrender.com/esg/mcp/esg"
  - name: "search_academic_papers"
    endpoint: "https://multiplium-mcp-tools.onrender.com/academic/mcp/academic"
  - name: "lookup_sustainability_ratings"
    endpoint: "https://multiplium-mcp-tools.onrender.com/sustainability/mcp/sustainability"
  - name: "check_certifications"
    endpoint: "https://multiplium-mcp-tools.onrender.com/sustainability/mcp/certifications"
  - name: "calculate_sdg_alignment"
    endpoint: "https://multiplium-mcp-tools.onrender.com/sustainability/mcp/sdg"
```

Keep `config/dev.yaml` with local endpoints for development.

## 📝 Deployment Steps

### If Using Render:

1. **Create servers/requirements.txt** (if not exists):
```bash
cd /Users/vimo/Projects/Multiplium
cat > servers/requirements.txt << 'EOF'
fastapi>=0.110
uvicorn>=0.30
httpx>=0.27
aiohttp>=3.9
pydantic>=2.7
pyyaml>=6.0
EOF
```

2. **Update render.yaml** with new env vars

3. **Commit and push**:
```bash
git add servers/app.py servers/sustainability_service.py servers/clients/sustainability.py servers/requirements.txt render.yaml
git commit -m "Add sustainability service to MCP tools"
git push origin main
```

4. **Update Environment Variables in Render Dashboard**:
   - Go to https://dashboard.render.com
   - Select your service
   - Go to Environment tab
   - Add:
     - `TAVILY_API_KEY`
     - `PERPLEXITY_API_KEY`
     - `WIKIRATE_API_KEY` (when you have it)

5. **Render will auto-deploy** (takes ~2-3 minutes)

6. **Test endpoints**:
```bash
# Replace with your actual Render URL
RENDER_URL="https://multiplium-mcp-tools.onrender.com"

curl "$RENDER_URL/docs"  # Should show API docs
curl "$RENDER_URL/sustainability/docs"  # Sustainability service docs
```

7. **Update your local config** to use Render:
```bash
# Switch to production config
python -m multiplium.orchestrator --config config/prod.yaml
```

## 🧪 Testing Deployment

### Test Render Services:

```bash
# Set your Render URL
export RENDER_URL="https://multiplium-mcp-tools.onrender.com"

# Test each service
curl -X POST "$RENDER_URL/sustainability/mcp/sdg" \
  -H "Content-Type: application/json" \
  -d '{"name":"calculate_sdg_alignment","args":[],"kwargs":{"company_description":"Clean energy company","activities":["solar panels"],"impact_areas":["climate"]}}'
```

## 💰 Cost Considerations

**Render Free Tier**:
- ✅ 750 hours/month (enough for continuous uptime)
- ✅ HTTPS included
- ✅ Auto-deploys
- ⚠️ Spins down after 15 min inactivity (takes ~30s to wake up)
- ⚠️ 512MB RAM limit

**Upgrade if needed**:
- Starter plan: $7/month (no spin-down, more RAM)

## 🔐 Security Best Practices

1. **Never commit API keys** ✅ Already using env vars
2. **Use Render's secret management** for production
3. **Rotate keys regularly**
4. **Monitor usage** in provider dashboards

## 📊 Monitoring

After deployment:

1. **Check Render Logs**:
   - Go to Render Dashboard → Your Service → Logs
   - Look for startup messages from all 7 services

2. **Monitor API Usage**:
   - OpenAI: platform.openai.com/usage
   - Google: console.cloud.google.com
   - Anthropic: console.anthropic.com/settings/cost

3. **Check Research Reports**:
   - Reports saved locally in `reports/`
   - Review tool usage in telemetry

## 🎯 Recommendation

**For your use case:**

1. **Start with local** (what you're doing now):
   - Faster iteration
   - Full debugging
   - Test all features

2. **Deploy to Render** once stable:
   - No need to keep laptop running
   - More reliable for long research runs
   - Can run scheduled jobs

3. **Use hybrid approach**:
   - Development: Local servers
   - Production: Render deployment
   - Switch via config files

## 🆘 Troubleshooting

**Issue**: Render deploy fails
**Solution**: Check logs in Render Dashboard, verify requirements.txt

**Issue**: Service times out
**Solution**: Render free tier spins down - first request is slow

**Issue**: Import errors
**Solution**: Ensure all dependencies in servers/requirements.txt

**Issue**: 502 Bad Gateway
**Solution**: Check Render logs, service might still be starting

## ✅ Current Status

- ✅ Code ready for Render
- ✅ servers/app.py updated with sustainability service
- ✅ All 7 services integrated
- 📋 TODO: Create servers/requirements.txt
- 📋 TODO: Update render.yaml with new env vars
- 📋 TODO: Git push to trigger deploy
- 📋 TODO: Add env vars in Render Dashboard

Let me know if you want to proceed with Render deployment or continue local testing first!


# Multiplium Platform Deployment Guide

This guide covers deploying the Multiplium research platform for partner access.

## Architecture Overview

```
┌─────────────────┐     ┌──────────────────────────┐     ┌─────────────────────┐
│   Partners      │────▶│  Frontend (Static)       │────▶│  Dashboard API      │
│   (Browser)     │     │  multiplium-dashboard    │     │  research_dashboard │
└─────────────────┘     └──────────────────────────┘     └──────────┬──────────┘
                                                                     │
                        ┌──────────────────────────┐                 │
                        │  MCP Tool Servers        │◀────────────────┤
                        │  multiplium-mcp-tools    │                 │
                        └──────────────────────────┘                 │
                                                                     ▼
                        ┌──────────────────────────────────────────────────────┐
                        │  LLM APIs (OpenAI, Anthropic, Google)                │
                        └──────────────────────────────────────────────────────┘
```

## Quick Start: Render.com Deployment

### Prerequisites

1. A Render.com account (free tier works)
2. This repository connected to Render
3. API keys for LLM providers (OpenAI, etc.)

### Step 1: Deploy via Render Blueprint

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click "New" → "Blueprint"
3. Connect your repository
4. Render will detect `render.yaml` and create 3 services:
   - `multiplium-mcp-tools` - MCP tool servers
   - `multiplium-dashboard-api` - Backend API
   - `multiplium-dashboard` - Frontend static site

### Step 2: Configure Environment Variables

In Render Dashboard, set these environment variables for **multiplium-dashboard-api**:

| Variable | Description | Required |
|----------|-------------|----------|
| `DASHBOARD_API_KEY` | Shared API key for partner access | Yes |
| `OPENAI_API_KEY` | OpenAI API key | Yes |
| `ANTHROPIC_API_KEY` | Anthropic API key | Optional |
| `GOOGLE_API_KEY` | Google AI API key | Optional |
| `TAVILY_API_KEY` | Tavily search API key | Optional |
| `PERPLEXITY_API_KEY` | Perplexity API key | Optional |

For **multiplium-mcp-tools**:

| Variable | Description |
|----------|-------------|
| `FMP_API_KEY` | Financial Modeling Prep key |
| `TAVILY_API_KEY` | Tavily search API key |
| `PERPLEXITY_API_KEY` | Perplexity API key |

### Step 3: Generate API Key for Partners

Generate a secure API key:
```bash
# On macOS/Linux
openssl rand -hex 32

# Or use Python
python -c "import secrets; print(secrets.token_hex(32))"
```

Set this as `DASHBOARD_API_KEY` in Render and share it with your partners.

### Step 4: Access the Platform

After deployment completes (~3-5 minutes):

- **Frontend**: `https://multiplium-dashboard.onrender.com`
- **API**: `https://multiplium-dashboard-api.onrender.com`
- **API Docs**: `https://multiplium-dashboard-api.onrender.com/docs`

Partners access the frontend URL and enter the shared API key when prompted.

## Authentication

The platform uses simple API key authentication:

- Partners enter the API key once when first accessing the dashboard
- The key is stored in browser localStorage
- All API requests include `X-API-Key` header
- If no `DASHBOARD_API_KEY` is set, authentication is disabled (dev mode)

### Security Notes

- Use a strong, randomly generated API key
- Rotate the key periodically
- In production, restrict CORS origins via `ALLOWED_ORIGINS` env var
- Consider upgrading to per-user authentication for sensitive deployments

## Local Development

Run locally without authentication:

```bash
# Terminal 1: Start API server
cd /path/to/Multiplium
python -m uvicorn servers.research_dashboard:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Start frontend
cd dashboard
npm run dev
```

Access at http://localhost:5173

## Configuration Files

| File | Purpose |
|------|---------|
| `config/dev.yaml` | Local development with mixed local/remote tools |
| `config/prod.yaml` | Production with all remote tool endpoints |
| `render.yaml` | Render.com deployment specification |

## Data Persistence

The dashboard stores data in:
- `/data` directory on Render (persistent disk)
- Local `data/` directory in development

Data includes:
- `data/projects.json` - Project metadata
- `data/runs/` - Run snapshots
- `data/chats/` - Chat session history
- `reports/` - Generated research reports

## Troubleshooting

### Cold Start Delays

Render free tier services spin down after 15 minutes of inactivity. First request may take 30-60 seconds. Consider:
- Upgrading to Starter plan ($7/mo) for always-on
- Implementing a health check ping

### API Key Not Working

1. Verify the key matches exactly (no extra spaces)
2. Check Render logs for authentication errors
3. Clear browser localStorage and re-enter key

### Reports Not Saving

1. Verify the `/data` disk is mounted in Render
2. Check `DATA_ROOT` environment variable is set
3. Review Render logs for file permission errors

## Upgrading

To update the deployment:

```bash
git push origin main
```

Render auto-deploys on push to the connected branch.

## Cost Estimate

**Render.com Free Tier:**
- 750 hours/month per service (enough for 24/7)
- 1GB persistent disk included
- HTTPS included

**Paid Options:**
- Starter: $7/month per service (no cold starts)
- Standard: $25/month per service (more resources)

**LLM API Costs:**
- Varies by usage
- Typical research run: $0.50-$5.00 depending on depth
- Monitor usage in provider dashboards

# Multiplium Setup & Test Instructions

## 🚨 **CRITICAL: Python Version Required**

**Your system has Python 3.9.6, but this project requires Python 3.11+**

### Option 1: Install Python 3.11+ (Recommended)

**Using Homebrew** (macOS):
```bash
# Install Python 3.11
brew install python@3.11

# Verify installation
python3.11 --version
```

**Using pyenv** (recommended for multiple Python versions):
```bash
# Install pyenv if not already installed
brew install pyenv

# Install Python 3.11
pyenv install 3.11.9

# Set as project Python
cd /Users/vimo/Projects/Multiplium
pyenv local 3.11.9
```

### Option 2: Use Docker (Alternative)

Create a `Dockerfile`:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -e .
CMD ["python", "-m", "multiplium.orchestrator", "--config", "config/dev.yaml"]
```

## 📦 Setup Steps (After Installing Python 3.11+)

### Step 1: Create Virtual Environment
```bash
cd /Users/vimo/Projects/Multiplium

# Create venv with Python 3.11
python3.11 -m venv venv

# Activate it
source venv/bin/activate

# Verify Python version
python --version  # Should show 3.11.x
```

### Step 2: Install Dependencies
```bash
# Upgrade pip first
pip install --upgrade pip

# Install project
pip install -e .

# Verify installations
python -c "import anthropic, openai; from google import genai; print('✅ SDKs installed')"
python -c "import uvicorn, fastapi; print('✅ Server dependencies installed')"
```

### Step 3: Verify Package Installation
```bash
python -c "from multiplium.config_validator import validate_all_on_startup; print('✅ Multiplium installed')"
```

### Step 4: Test Configuration
```bash
python -m multiplium.orchestrator --config config/dev.yaml --dry-run
```

## 🎯 Your Current Environment Status

Based on detection:

- ✅ **API Keys Configured**:
  - OPENAI_API_KEY
  - GOOGLE_GENAI_API_KEY
  - TAVILY_API_KEY
  - PERPLEXITY_API_KEY
  - FMP_API_KEY
  - WikiRate key (mentioned)

- ❌ **Python Version**: 3.9.6 (need 3.11+)
- ❓ **Virtual Environment**: None detected
- ✅ **Dependencies**: Globally installed but can't use multiplium package

## 🚀 Quick Start (Once Python 3.11+ is ready)

### Test Sequence:

**1. Activate venv:**
```bash
source venv/bin/activate
```

**2. Test dry run:**
```bash
python -m multiplium.orchestrator --config config/dev.yaml --dry-run
```

**3. Start tool servers (separate terminal):**
```bash
source venv/bin/activate
./scripts/start_tool_servers.sh
```

**4. Run full test:**
```bash
python -m multiplium.orchestrator --config config/dev.yaml
```

## 🔧 Render.com Deployment

You have a render.yaml configured. To update it with new sustainability service:

### Update render.yaml:
```yaml
services:
  - type: web
    name: multiplium-mcp-tools
    env: python
    runtime: python-3.11  # ADD THIS LINE
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn servers.app:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: FMP_API_KEY
        sync: false
      - key: TAVILY_API_KEY
        sync: false
      - key: PERPLEXITY_API_KEY
        sync: false
      - key: WIKIRATE_API_KEY  # ADD THIS
        sync: false
      - key: OPENALEX_API_BASE
        value: https://api.openalex.org/organizations
```

### Update servers/requirements.txt:
```txt
fastapi>=0.110
uvicorn>=0.30
httpx>=0.27
aiohttp>=3.9
pydantic>=2.7
```

### Deployment Decision:

**Option A: Use Render (Recommended for production)**
- Already configured
- Handles all 7 services in one deployment
- Free tier available
- Auto-scaling
- **Update**: Push changes, Render auto-deploys

**Option B: Local Development**
- Run tool servers locally during development
- Use Render for production
- Faster iteration

**Recommendation**: 
1. **Development**: Run locally with `./scripts/start_tool_servers.sh`
2. **Production**: Use Render deployment
3. **Update config/dev.yaml endpoints**:
   ```yaml
   # For local development:
   endpoint: "http://127.0.0.1:7001/mcp/search"
   
   # For production (after Render deploy):
   endpoint: "https://multiplium-mcp-tools.onrender.com/search/mcp/search"
   ```

## 🧪 Testing Checklist

Once Python 3.11+ is installed:

- [ ] Create venv with Python 3.11+
- [ ] Install dependencies (`pip install -e .`)
- [ ] Test dry run
- [ ] Start tool servers locally
- [ ] Test with one provider
- [ ] Test with all providers
- [ ] Check report output
- [ ] Test impact scoring
- [ ] Deploy to Render (optional)

## 📝 Next Steps

1. **Install Python 3.11+** (choose method above)
2. **Create venv**
3. **Install dependencies**
4. **Run tests** (I'll continue once Python is ready)

## 🆘 Need Help?

If you get stuck:
1. Check Python version: `python --version`
2. Check venv is activated: `which python` should show venv path
3. Check dependencies: `pip list | grep -E "(anthropic|openai|google-genai)"`
4. Check API keys: `env | grep _API_KEY`

Let me know when Python 3.11+ is ready and I'll continue with the testing!


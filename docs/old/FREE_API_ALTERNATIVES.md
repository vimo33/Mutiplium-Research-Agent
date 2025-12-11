# Free API Alternatives for MCP Tools

## ✅ Already Using Free/Freemium APIs

### 1. **Search APIs** (CONFIGURED ✓)
- **Tavily** - https://tavily.com/
  - ✅ Free tier: 1,000 API calls/month
  - Already configured in your .env
  
- **Perplexity** - https://www.perplexity.ai/
  - ✅ Free tier available
  - Already configured in your .env

- **DuckDuckGo Instant Answer API** - https://api.duckduckgo.com/
  - ✅ FREE, no API key needed
  - Already integrated as fallback

### 2. **Financial Data** (CONFIGURED ✓)
- **Financial Modeling Prep (FMP)** - https://site.financialmodelingprep.com/
  - ✅ Free tier: 250 requests/day
  - Already configured in your .env

## 🆕 New Free Alternatives to Add

### 3. **ESG & Sustainability Data**

#### **WikiRate** (YOU HAVE THIS! ✓)
- **Website**: https://wikirate.org/
- **API Docs**: https://wikirate.org/API
- **What it provides**: Corporate ESG metrics, supply chain data
- **Free tier**: Open data, free API access
- **Signup**: Create account at https://wikirate.org/account/signup
- **API Key**: Generate at https://wikirate.org/account/tokens
- **ENV VAR**: `WIKIRATE_API_KEY`
- **Integration Status**: Need to add to sustainability service

#### **CSRHub**
- **Website**: https://www.csrhub.com/
- **API**: https://www.csrhub.com/api
- **What it provides**: Sustainability ratings (Community, Employees, Environment, Governance)
- **Free tier**: Limited free access (contact for trial)
- **Signup**: https://www.csrhub.com/content/free-csr-api-access
- **ENV VAR**: `CSRHUB_API_KEY`
- **Status**: Stub already in code

#### **Open ESG**
- **Website**: https://opensustainability.tech/
- **What it provides**: Aggregated ESG data
- **Free tier**: Open source data
- **Status**: Research needed for API access

### 4. **Company Data**

#### **OpenAlex** (FREE! ✓)
- **Website**: https://openalex.org/
- **API**: https://docs.openalex.org/
- **What it provides**: Academic papers, company research profiles
- **Free tier**: COMPLETELY FREE, no API key needed
- **Rate limits**: 100,000 requests/day (generous!)
- **Already integrated**: Used for Crunchbase alternative
- **ENV VAR**: None needed!

#### **Companies House (UK)**
- **Website**: https://www.gov.uk/government/organisations/companies-house
- **API**: https://developer-specs.company-information.service.gov.uk/
- **What it provides**: UK company data, filings, directors
- **Free tier**: FREE with registration
- **Signup**: https://developer.company-information.service.gov.uk/
- **ENV VAR**: `COMPANIES_HOUSE_API_KEY`
- **Use case**: UK company verification

#### **OpenCorporates**
- **Website**: https://opencorporates.com/
- **API**: https://api.opencorporates.com/
- **What it provides**: Global company registry data
- **Free tier**: 500 requests/month
- **Signup**: https://opencorporates.com/api_accounts/new
- **ENV VAR**: `OPENCORPORATES_API_KEY`
- **Use case**: Company verification, global coverage

### 5. **Patent Data**

#### **USPTO PatentsView** (FREE! ✓)
- **Website**: https://patentsview.org/
- **API**: https://patentsview.org/apis/api
- **What it provides**: US patent data
- **Free tier**: COMPLETELY FREE
- **Already integrated**: In patents service
- **ENV VAR**: None needed!

#### **EPO Open Patent Services**
- **Website**: https://www.epo.org/
- **API**: https://www.epo.org/en/searching-for-patents/data/web-services
- **What it provides**: European patent data
- **Free tier**: FREE
- **Signup**: Register at https://developers.epo.org/
- **ENV VAR**: `EPO_API_KEY`
- **Use case**: European patent coverage

### 6. **Academic Research**

#### **OpenAlex** (FREE! ✓)
- Already covered above - used for academic papers
- **Already integrated** in academic_search_service

#### **Semantic Scholar**
- **Website**: https://www.semanticscholar.org/
- **API**: https://api.semanticscholar.org/
- **What it provides**: AI-powered academic paper search
- **Free tier**: 100 requests/5 minutes (5,000/month with key)
- **Signup**: https://www.semanticscholar.org/product/api#api-key-form
- **ENV VAR**: `SEMANTIC_SCHOLAR_API_KEY`
- **Use case**: Better academic search

#### **CORE**
- **Website**: https://core.ac.uk/
- **API**: https://core.ac.uk/services/api
- **What it provides**: Open access research papers
- **Free tier**: FREE with registration
- **Signup**: https://core.ac.uk/services/api#registration
- **ENV VAR**: `CORE_API_KEY`

### 7. **Certifications & Standards**

#### **B Corp Directory** (FREE!)
- **Website**: https://www.bcorporation.net/en-us/find-a-b-corp/
- **API**: No official API, but can scrape public directory
- **What it provides**: B Corp certified companies
- **Free tier**: Public data
- **Integration**: Web scraping or manual checks

#### **Fair Trade Directory**
- **Website**: https://www.fairtradecertified.org/
- **Directory**: https://www.fairtradecertified.org/business/find-fairtrade-products
- **API**: No official API
- **Integration**: Web scraping

#### **ISO Certified Companies**
- **Website**: https://www.iso.org/
- **Search**: https://www.iso.org/certification-bodies.html
- **API**: Limited access
- **Free tier**: Directory browsing

### 8. **Climate & Carbon Data**

#### **Carbon Interface**
- **Website**: https://www.carboninterface.com/
- **API**: https://docs.carboninterface.com/
- **What it provides**: Carbon emission calculations
- **Free tier**: 200 requests/month
- **Signup**: https://www.carboninterface.com/
- **ENV VAR**: `CARBON_INTERFACE_API_KEY`

#### **Climatiq**
- **Website**: https://www.climatiq.io/
- **API**: https://www.climatiq.io/docs
- **What it provides**: Emission factors database
- **Free tier**: 3,000 requests/month
- **Signup**: https://app.climatiq.io/signup
- **ENV VAR**: `CLIMATIQ_API_KEY`

### 9. **Supply Chain Transparency**

#### **Open Supply Hub**
- **Website**: https://opensupplyhub.org/
- **API**: https://opensupplyhub.org/api/docs
- **What it provides**: Factory locations, supply chain data
- **Free tier**: FREE, open data
- **ENV VAR**: None needed
- **Use case**: Supply chain tracking

### 10. **News & Sentiment** (for ESG events)

#### **News API**
- **Website**: https://newsapi.org/
- **API**: https://newsapi.org/docs
- **What it provides**: News articles, headlines
- **Free tier**: 100 requests/day
- **Signup**: https://newsapi.org/register
- **ENV VAR**: `NEWS_API_KEY`
- **Use case**: ESG controversy detection

#### **MediaStack**
- **Website**: https://mediastack.com/
- **API**: https://mediastack.com/documentation
- **What it provides**: Real-time news
- **Free tier**: 500 requests/month
- **Signup**: https://mediastack.com/product
- **ENV VAR**: `MEDIASTACK_API_KEY`

## 📊 Priority Recommendation for You

### **IMMEDIATE** (Add this week):
1. ✅ **WikiRate** - You already have the key! Just need to integrate
2. **Semantic Scholar** - Best free academic search (5,000/month)
3. **Carbon Interface** - Carbon calculations (200/month)
4. **Companies House** - UK company data (unlimited free)

### **HIGH PRIORITY** (Add next):
5. **OpenCorporates** - Global company verification (500/month)
6. **Climatiq** - Emission factors (3,000/month)
7. **News API** - ESG news monitoring (100/day)

### **MEDIUM PRIORITY** (Nice to have):
8. **CSRHub** - ESG ratings (trial access)
9. **EPO** - European patents
10. **Open Supply Hub** - Supply chain data

## 💰 Cost Summary

**Currently spending on APIs**: $0 (all free tiers!)

**Free API budget available**:
- Tavily: 1,000 requests/month
- FMP: 250 requests/day (7,500/month)
- Perplexity: Free tier
- OpenAlex: 100,000/day (unlimited!)
- USPTO: Unlimited
- DuckDuckGo: Unlimited

**Additional free with signup**:
- WikiRate: Unlimited (open data)
- Semantic Scholar: 5,000/month
- Carbon Interface: 200/month
- Climatiq: 3,000/month
- Companies House: Unlimited (UK)
- OpenCorporates: 500/month
- News API: 100/day (3,000/month)

**Total potential**: ~20,000+ API calls/month across all services - FREE!

## 🔗 Quick Signup Links

Create accounts at these to get API keys:

1. **WikiRate**: https://wikirate.org/account/signup (YOU HAVE THIS)
2. **Semantic Scholar**: https://www.semanticscholar.org/product/api#api-key-form
3. **Carbon Interface**: https://www.carboninterface.com/
4. **Companies House**: https://developer.company-information.service.gov.uk/get-started
5. **OpenCorporates**: https://opencorporates.com/api_accounts/new
6. **Climatiq**: https://app.climatiq.io/signup
7. **News API**: https://newsapi.org/register
8. **CSRHub**: https://www.csrhub.com/content/free-csr-api-access

## 📝 Environment Variables to Add

Add these to your `.env` file as you get the keys:

```bash
# Already have these ✓
OPENAI_API_KEY=...
GOOGLE_GENAI_API_KEY=...
TAVILY_API_KEY=...
PERPLEXITY_API_KEY=...
FMP_API_KEY=...

# Add when ready:
WIKIRATE_API_KEY=...              # You have this!
SEMANTIC_SCHOLAR_API_KEY=...      # High priority
CARBON_INTERFACE_API_KEY=...      # High priority
COMPANIES_HOUSE_API_KEY=...       # High priority
OPENCORPORATES_API_KEY=...        # High priority
CLIMATIQ_API_KEY=...              # Medium priority
NEWS_API_KEY=...                  # Medium priority
CSRHUB_API_KEY=...                # When available
EPO_API_KEY=...                   # Optional
CORE_API_KEY=...                  # Optional
MEDIASTACK_API_KEY=...            # Optional
```

## 🎯 Integration Status

- ✅ **Working now**: Tavily, Perplexity, DuckDuckGo, FMP, OpenAlex, USPTO
- 🔄 **Ready to integrate**: WikiRate (you have key)
- 📋 **Planned**: All others listed above

All of these are **FREE** - no credit card required for basic tiers!


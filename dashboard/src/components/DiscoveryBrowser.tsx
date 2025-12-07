import { useState, useEffect, useMemo } from 'react';
import { Card, Badge, SearchInput, Button, SegmentTag, CountryTag, ConfidenceBadge } from './ui';
import './DiscoveryBrowser.css';

interface DiscoveryCompany {
  company: string;
  summary?: string;
  website?: string;
  country?: string;
  segment?: string;
  confidence_0to1?: number;
  kpi_alignment?: string[];
  sources?: string[];
  vineyard_verified?: boolean;
  provider?: string;
}

interface DiscoveryReport {
  path: string;
  filename: string;
  timestamp: string;
  total_companies: number;
  has_deep_research: boolean;
  providers: string[];
  report_type: string;
  sector?: string;
}

interface ReportData {
  generated_at?: string;
  sector: string;
  providers: Array<{
    provider: string;
    model: string;
    findings: any[];
  }>;
}

interface DiscoveryBrowserProps {
  onCreateProject?: () => void;
  onInitiateDeepResearch?: (reportPath: string, companies: string[]) => Promise<any>;
}

// Icons
const SearchIcon = (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="7" cy="7" r="5" />
    <path d="M11 11l3 3" strokeLinecap="round" />
  </svg>
);

const DeepResearchIcon = (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M8 2v12M2 8h12" strokeLinecap="round" />
    <circle cx="8" cy="8" r="6" />
  </svg>
);

const CheckIcon = (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M3 8l4 4 6-6" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

export function DiscoveryBrowser({
  onCreateProject,
  onInitiateDeepResearch,
}: DiscoveryBrowserProps) {
  const [reports, setReports] = useState<DiscoveryReport[]>([]);
  const [selectedReport, setSelectedReport] = useState<string | null>(null);
  const [reportData, setReportData] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCompanies, setSelectedCompanies] = useState<Set<string>>(new Set());
  const [expandedCompany, setExpandedCompany] = useState<string | null>(null);
  const [selectedSegment, setSelectedSegment] = useState<string>('all');
  const [selectedProvider, setSelectedProvider] = useState<string>('all');
  const [initiatingResearch, setInitiatingResearch] = useState(false);

  // Load available reports
  useEffect(() => {
    loadReports();
  }, []);

  // Load report data when selection changes
  useEffect(() => {
    if (selectedReport) {
      loadReportData(selectedReport);
    }
  }, [selectedReport]);

  async function loadReports() {
    try {
      const response = await fetch('http://localhost:8000/reports');
      const data = await response.json();
      const discoveryReports = data.reports.filter(
        (r: any) => r.report_type === 'discovery'
      );
      setReports(discoveryReports);
      if (discoveryReports.length > 0) {
        setSelectedReport(discoveryReports[0].path);
      }
      setLoading(false);
    } catch (err) {
      setError('Failed to load reports');
      setLoading(false);
    }
  }

  async function loadReportData(path: string) {
    try {
      setLoading(true);
      const response = await fetch(`http://localhost:8000/reports/${encodeURIComponent(path)}/raw`);
      if (!response.ok) throw new Error('Failed to fetch report');
      const data = await response.json();
      setReportData(data);
      setSelectedCompanies(new Set());
      setLoading(false);
    } catch (err) {
      setError('Failed to load report data');
      setLoading(false);
    }
  }

  // Extract companies from report
  const allCompanies = useMemo(() => {
    if (!reportData?.providers) return [];
    
    const companies: DiscoveryCompany[] = [];
    
    reportData.providers.forEach(provider => {
      if (provider.findings) {
        provider.findings.forEach(finding => {
          if (finding.companies) {
            finding.companies.forEach((company: any) => {
              companies.push({
                company: company.company,
                summary: company.summary,
                website: company.website,
                country: company.country,
                segment: company.segment || finding.name,
                confidence_0to1: company.confidence_0to1,
                kpi_alignment: company.kpi_alignment,
                sources: company.sources,
                vineyard_verified: company.vineyard_verified,
                provider: provider.provider,
              });
            });
          }
        });
      }
    });
    
    // Deduplicate by company name
    const seen = new Set<string>();
    return companies.filter(c => {
      if (seen.has(c.company)) return false;
      seen.add(c.company);
      return true;
    });
  }, [reportData]);

  // Get unique segments and providers
  const segments = useMemo(() => {
    const segs = new Set<string>();
    allCompanies.forEach(c => {
      if (c.segment) segs.add(c.segment);
    });
    return Array.from(segs).sort();
  }, [allCompanies]);

  const providers = useMemo(() => {
    const provs = new Set<string>();
    allCompanies.forEach(c => {
      if (c.provider) provs.add(c.provider);
    });
    return Array.from(provs).sort();
  }, [allCompanies]);

  // Filter companies
  const filteredCompanies = useMemo(() => {
    let result = allCompanies;

    if (selectedSegment !== 'all') {
      result = result.filter(c => c.segment === selectedSegment);
    }

    if (selectedProvider !== 'all') {
      result = result.filter(c => c.provider === selectedProvider);
    }

    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter(c =>
        c.company.toLowerCase().includes(query) ||
        c.summary?.toLowerCase().includes(query) ||
        c.country?.toLowerCase().includes(query)
      );
    }

    return result;
  }, [allCompanies, selectedSegment, selectedProvider, searchQuery]);

  const toggleCompanySelection = (company: string) => {
    setSelectedCompanies(prev => {
      const next = new Set(prev);
      if (next.has(company)) {
        next.delete(company);
      } else {
        next.add(company);
      }
      return next;
    });
  };

  const selectAll = () => {
    setSelectedCompanies(new Set(filteredCompanies.map(c => c.company)));
  };

  const clearSelection = () => {
    setSelectedCompanies(new Set());
  };

  const handleInitiateDeepResearch = async () => {
    if (!selectedReport || selectedCompanies.size === 0 || !onInitiateDeepResearch) return;
    
    setInitiatingResearch(true);
    try {
      await onInitiateDeepResearch(selectedReport, Array.from(selectedCompanies));
    } catch (error) {
      console.error('Failed to initiate deep research:', error);
    } finally {
      setInitiatingResearch(false);
    }
  };

  if (loading && !reportData) {
    return (
      <div className="discovery-browser">
        <div className="loading-state">
          <div className="loading-spinner" />
          <p className="loading-state__text">Loading discovery reports...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="discovery-browser">
        <div className="empty-state">
          <div className="empty-state__icon">⚠️</div>
          <h3 className="empty-state__title">Error Loading Data</h3>
          <p className="empty-state__message">{error}</p>
        </div>
      </div>
    );
  }

  if (reports.length === 0) {
    return (
      <div className="discovery-browser">
        <div className="page-header">
          <h1 className="page-header__title">Discovery Browser</h1>
          <p className="page-header__subtitle">Browse and analyze discovery reports</p>
        </div>
        <div className="empty-state">
          <div className="empty-state__icon">🔍</div>
          <h3 className="empty-state__title">No Discovery Reports</h3>
          <p className="empty-state__message">
            Run a discovery to find companies in your target sector.
          </p>
          {onCreateProject && (
            <Button variant="primary" onClick={onCreateProject}>
              Start New Project
            </Button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="discovery-browser">
      {/* Header */}
      <div className="page-header">
        <div className="page-header__content">
          <h1 className="page-header__title">Discovery Browser</h1>
          <p className="page-header__subtitle">
            {reportData?.sector || 'Research findings'} • {allCompanies.length} companies discovered
          </p>
        </div>
        {onCreateProject && (
          <Button variant="secondary" onClick={onCreateProject}>
            + New Project
          </Button>
        )}
      </div>

      {/* Report Selector & Filters */}
      <div className="discovery-browser__toolbar">
        <div className="discovery-browser__report-selector">
          <label>Report:</label>
          <select
            value={selectedReport || ''}
            onChange={(e) => setSelectedReport(e.target.value)}
          >
            {reports.map(r => (
              <option key={r.path} value={r.path}>
                {r.filename} ({r.total_companies} companies)
              </option>
            ))}
          </select>
        </div>

        <div className="discovery-browser__filters">
          <SearchInput
            placeholder="Search companies..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onClear={() => setSearchQuery('')}
          />
          
          <select
            className="filter-select"
            value={selectedSegment}
            onChange={(e) => setSelectedSegment(e.target.value)}
          >
            <option value="all">All Segments</option>
            {segments.map(seg => (
              <option key={seg} value={seg}>{seg}</option>
            ))}
          </select>

          <select
            className="filter-select"
            value={selectedProvider}
            onChange={(e) => setSelectedProvider(e.target.value)}
          >
            <option value="all">All Providers</option>
            {providers.map(prov => (
              <option key={prov} value={prov}>{prov}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Selection Bar */}
      <div className="discovery-browser__selection-bar">
        <div className="discovery-browser__selection-info">
          <Badge variant={selectedCompanies.size > 0 ? 'primary' : 'default'}>
            {selectedCompanies.size} selected
          </Badge>
          <span className="discovery-browser__count">
            Showing {filteredCompanies.length} of {allCompanies.length}
          </span>
        </div>
        
        <div className="discovery-browser__selection-actions">
          <button className="text-btn" onClick={selectAll}>Select All</button>
          <button className="text-btn" onClick={clearSelection}>Clear</button>
          
          {onInitiateDeepResearch && (
            <Button
              variant="primary"
              disabled={selectedCompanies.size === 0 || initiatingResearch}
              onClick={handleInitiateDeepResearch}
            >
              {initiatingResearch ? (
                <>Initiating...</>
              ) : (
                <>
                  {DeepResearchIcon}
                  <span>Deep Research ({selectedCompanies.size})</span>
                </>
              )}
            </Button>
          )}
        </div>
      </div>

      {/* Company Grid */}
      {filteredCompanies.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state__icon">🔍</div>
          <h3 className="empty-state__title">No companies found</h3>
          <p className="empty-state__message">
            Try adjusting your filters or search query
          </p>
        </div>
      ) : (
        <div className="discovery-browser__grid">
          {filteredCompanies.map((company, index) => (
            <Card 
              key={`${company.company}-${index}`}
              hover
              className={`discovery-card ${expandedCompany === company.company ? 'discovery-card--expanded' : ''} ${selectedCompanies.has(company.company) ? 'discovery-card--selected' : ''}`}
            >
              <div className="discovery-card__header">
                <button
                  className={`discovery-card__checkbox ${selectedCompanies.has(company.company) ? 'discovery-card__checkbox--checked' : ''}`}
                  onClick={(e) => { e.stopPropagation(); toggleCompanySelection(company.company); }}
                >
                  {selectedCompanies.has(company.company) && CheckIcon}
                </button>
                
                <div 
                  className="discovery-card__title-row"
                  onClick={() => setExpandedCompany(
                    expandedCompany === company.company ? null : company.company
                  )}
                >
                  <h3 className="discovery-card__title">{company.company}</h3>
                  {company.vineyard_verified && (
                    <Badge variant="success">Verified</Badge>
                  )}
                </div>
              </div>

              <div className="discovery-card__meta">
                {company.segment && <SegmentTag segment={company.segment} />}
                {company.country && <CountryTag country={company.country} />}
                {company.confidence_0to1 !== undefined && (
                  <ConfidenceBadge confidence={company.confidence_0to1} />
                )}
                {company.provider && (
                  <Badge variant="default" className="provider-badge">
                    {company.provider}
                  </Badge>
                )}
              </div>
              
              {company.summary && (
                <p className="discovery-card__summary">
                  {expandedCompany === company.company 
                    ? company.summary 
                    : company.summary.slice(0, 150) + (company.summary.length > 150 ? '...' : '')}
                </p>
              )}

              {expandedCompany === company.company && (
                <div className="discovery-card__details">
                  {company.kpi_alignment && company.kpi_alignment.length > 0 && (
                    <div className="discovery-card__kpis">
                      <h4>KPI Alignment</h4>
                      <ul>
                        {company.kpi_alignment.map((kpi, i) => (
                          <li key={i}>{kpi}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  
                  {company.sources && company.sources.length > 0 && (
                    <div className="discovery-card__sources">
                      <h4>Sources</h4>
                      <ul>
                        {company.sources.map((source, i) => {
                          try {
                            const hostname = new URL(source).hostname;
                            return (
                              <li key={i}>
                                <a href={source} target="_blank" rel="noopener noreferrer">
                                  {hostname}
                                </a>
                              </li>
                            );
                          } catch {
                            return <li key={i}>{source}</li>;
                          }
                        })}
                      </ul>
                    </div>
                  )}

                  {company.website && (
                    <a 
                      href={company.website} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="discovery-card__website"
                      onClick={(e) => e.stopPropagation()}
                    >
                      Visit Website →
                    </a>
                  )}
                </div>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

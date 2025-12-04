import { useState, useEffect, useMemo } from 'react';
import { Card, Badge, SearchInput, Button, SegmentTag, CountryTag, ConfidenceBadge } from './ui';
import './DiscoveryView.css';

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
}

interface DiscoveryReport {
  generated_at: string;
  sector: string;
  providers: Array<{
    provider: string;
    model: string;
    findings: any[];
  }>;
}

interface DiscoveryViewProps {
  selectedSegments: string[];
  shortlistedCompanies: string[];
  onToggleShortlist: (company: string) => void;
}

export function DiscoveryView({
  selectedSegments,
  shortlistedCompanies,
  onToggleShortlist,
}: DiscoveryViewProps) {
  const [reports, setReports] = useState<{ path: string; filename: string }[]>([]);
  const [selectedReport, setSelectedReport] = useState<string | null>(null);
  const [reportData, setReportData] = useState<DiscoveryReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedCompany, setExpandedCompany] = useState<string | null>(null);

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

  // Filter companies
  const filteredCompanies = useMemo(() => {
    let result = allCompanies;

    if (selectedSegments.length > 0) {
      result = result.filter(c => 
        c.segment && selectedSegments.some(seg => c.segment?.toLowerCase().includes(seg.toLowerCase()))
      );
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
  }, [allCompanies, selectedSegments, searchQuery]);

  if (loading && !reportData) {
    return (
      <div className="loading-state">
        <div className="loading-spinner" />
        <p className="loading-state__text">Loading discovery reports...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="empty-state">
        <div className="empty-state__icon">⚠️</div>
        <h3 className="empty-state__title">Error Loading Data</h3>
        <p className="empty-state__message">{error}</p>
      </div>
    );
  }

  return (
    <div className="discovery-view">
      {/* Header */}
      <div className="page-header">
        <h1 className="page-header__title">Discovery Reports</h1>
        <p className="page-header__subtitle">
          {reportData?.sector || 'Research findings'} • {allCompanies.length} companies discovered
        </p>
      </div>

      {/* Filter Bar */}
      <div className="filter-bar">
        <div className="filter-bar__search">
          <SearchInput
            placeholder="Search companies..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onClear={() => setSearchQuery('')}
          />
        </div>
        
        <div className="filter-bar__filters">
          <select
            className="filter-select"
            value={selectedReport || ''}
            onChange={(e) => setSelectedReport(e.target.value)}
          >
            {reports.map(r => (
              <option key={r.path} value={r.path}>
                {r.filename}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Stats */}
      <div className="stats-row">
        <Badge variant="default">
          {filteredCompanies.length} of {allCompanies.length} companies
        </Badge>
        {reportData?.providers && (
          <Badge variant="primary">
            {reportData.providers.length} provider{reportData.providers.length > 1 ? 's' : ''}
          </Badge>
        )}
      </div>

      {/* Company List */}
      {filteredCompanies.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state__icon">🔍</div>
          <h3 className="empty-state__title">No companies found</h3>
          <p className="empty-state__message">
            Try adjusting your filters or search query
          </p>
        </div>
      ) : (
        <div className="discovery-list">
          {filteredCompanies.map((company) => (
            <Card 
              key={company.company} 
              hover
              className={`discovery-card ${expandedCompany === company.company ? 'discovery-card--expanded' : ''}`}
              onClick={() => setExpandedCompany(
                expandedCompany === company.company ? null : company.company
              )}
            >
              <div className="discovery-card__header">
                <div className="discovery-card__title">
                  <button
                    className={`discovery-card__star ${shortlistedCompanies.includes(company.company) ? 'discovery-card__star--active' : ''}`}
                    onClick={(e) => { e.stopPropagation(); onToggleShortlist(company.company); }}
                  >
                    ★
                  </button>
                  <h3>{company.company}</h3>
                  {company.vineyard_verified && (
                    <Badge variant="success">Verified</Badge>
                  )}
                </div>
                <div className="discovery-card__meta">
                  {company.segment && <SegmentTag segment={company.segment} />}
                  {company.country && <CountryTag country={company.country} />}
                  {company.confidence_0to1 && (
                    <ConfidenceBadge confidence={company.confidence_0to1} />
                  )}
                </div>
              </div>
              
              {company.summary && (
                <p className="discovery-card__summary">
                  {expandedCompany === company.company 
                    ? company.summary 
                    : company.summary.slice(0, 200) + (company.summary.length > 200 ? '...' : '')}
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
                        {company.sources.map((source, i) => (
                          <li key={i}>
                            <a href={source} target="_blank" rel="noopener noreferrer">
                              {new URL(source).hostname}
                            </a>
                          </li>
                        ))}
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



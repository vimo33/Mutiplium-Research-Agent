import { useState, useEffect, useMemo, useRef } from 'react';
import type { Project } from '../types';
import { Button, Badge, SearchInput, Card, SegmentTag, CountryTag, ConfidenceBadge } from './ui';
import { getApiBaseUrl, getAuthHeaders } from '../api';
import './DiscoveryReviewView.css';

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

interface DiscoveryReviewViewProps {
  project: Project;
  onBack: () => void;
  onStartDeepResearch: (selectedCompanies: string[]) => Promise<void>;
  onSkipDeepResearch: () => void;
}

const BackIcon = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M12 15l-5-5 5-5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const CheckIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M3 8l4 4 6-6" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

export function DiscoveryReviewView({
  project,
  onBack,
  onStartDeepResearch,
  onSkipDeepResearch,
}: DiscoveryReviewViewProps) {
  const [companies, setCompanies] = useState<DiscoveryCompany[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCompanies, setSelectedCompanies] = useState<Set<string>>(new Set());
  const [expandedCompany, setExpandedCompany] = useState<string | null>(null);
  const [selectedSegment, setSelectedSegment] = useState<string>('all');
  const [selectedProvider, setSelectedProvider] = useState<string>('all');
  const [starting, setStarting] = useState(false);

  // Load companies from discovery report
  useEffect(() => {
    loadDiscoveryCompanies();
  }, [project.id]);

  async function loadDiscoveryCompanies() {
    try {
      setLoading(true);
      
      // First check if project already has a report path (legacy projects)
      let reportPath = project.reportPath;
      
      // If no reportPath on project, try to get it from discovery status API
      if (!reportPath) {
        const statusResponse = await fetch(`${getApiBaseUrl()}/projects/${project.id}/discovery-status`, {
          headers: getAuthHeaders(),
        });
        if (statusResponse.ok) {
          const statusData = await statusResponse.json();
          reportPath = statusData.report_path;
        }
      }
      
      if (!reportPath) {
        throw new Error('No discovery report found');
      }

      const response = await fetch(`${getApiBaseUrl()}/reports/${encodeURIComponent(reportPath)}/raw`, {
        headers: getAuthHeaders(),
      });
      if (!response.ok) throw new Error('Failed to fetch report');
      const data = await response.json();

      // Extract companies from providers
      const extractedCompanies: DiscoveryCompany[] = [];
      data.providers?.forEach((provider: any) => {
        provider.findings?.forEach((finding: any) => {
          finding.companies?.forEach((company: any) => {
            extractedCompanies.push({
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
        });
      });

      // Deduplicate by company name
      const seen = new Set<string>();
      const uniqueCompanies = extractedCompanies.filter(c => {
        if (seen.has(c.company)) return false;
        seen.add(c.company);
        return true;
      });

      setCompanies(uniqueCompanies);
      
      // Auto-select all initially
      setSelectedCompanies(new Set(uniqueCompanies.map(c => c.company)));
      
      setLoading(false);
    } catch (err) {
      console.error('Error loading discovery companies:', err);
      setError(err instanceof Error ? err.message : 'Failed to load companies');
      setLoading(false);
    }
  }

  // Get unique segments and providers
  const segments = useMemo(() => {
    const segs = new Set<string>();
    companies.forEach(c => {
      if (c.segment) segs.add(c.segment);
    });
    return Array.from(segs).sort();
  }, [companies]);

  const providers = useMemo(() => {
    const provs = new Set<string>();
    companies.forEach(c => {
      if (c.provider) provs.add(c.provider);
    });
    return Array.from(provs).sort();
  }, [companies]);

  // Filter companies
  const filteredCompanies = useMemo(() => {
    let result = companies;

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
  }, [companies, selectedSegment, selectedProvider, searchQuery]);

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

  const handleStartDeepResearch = async () => {
    if (selectedCompanies.size === 0) return;
    
    setStarting(true);
    try {
      await onStartDeepResearch(Array.from(selectedCompanies));
    } catch (error) {
      console.error('Failed to start deep research:', error);
      setError('Failed to start deep research');
    } finally {
      setStarting(false);
    }
  };

  if (loading) {
    return (
      <div className="discovery-review">
        <div className="discovery-review__loading">
          <div className="loading-spinner" />
          <p>Loading discovery results...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="discovery-review">
        <div className="discovery-review__error">
          <h3>Error Loading Discovery Results</h3>
          <p>{error}</p>
          <Button variant="secondary" onClick={onBack}>Go Back</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="discovery-review">
      {/* Header */}
      <div className="discovery-review__header">
        <div className="discovery-review__header-left">
          <button className="discovery-review__back" onClick={onBack}>
            <BackIcon />
            <span>Back</span>
          </button>
          <div>
            <h1 className="discovery-review__title">Discovery Complete</h1>
            <p className="discovery-review__subtitle">
              {companies.length} companies discovered · Select companies for deep research
            </p>
          </div>
        </div>
      </div>

      {/* Toolbar */}
      <div className="discovery-review__toolbar">
        <div className="discovery-review__search">
          <SearchInput
            placeholder="Search companies..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onClear={() => setSearchQuery('')}
          />
        </div>
        
        <select
          className="discovery-review__select"
          value={selectedSegment}
          onChange={(e) => setSelectedSegment(e.target.value)}
        >
          <option value="all">All Segments</option>
          {segments.map(seg => (
            <option key={seg} value={seg}>{seg}</option>
          ))}
        </select>

        <select
          className="discovery-review__select"
          value={selectedProvider}
          onChange={(e) => setSelectedProvider(e.target.value)}
        >
          <option value="all">All Providers</option>
          {providers.map(prov => (
            <option key={prov} value={prov}>{prov}</option>
          ))}
        </select>
      </div>

      {/* Selection Bar */}
      <div className="discovery-review__selection-bar">
        <div className="discovery-review__selection-info">
          <Badge variant={selectedCompanies.size > 0 ? 'primary' : 'default'}>
            {selectedCompanies.size} selected
          </Badge>
          <span className="discovery-review__count">
            Showing {filteredCompanies.length} of {companies.length}
          </span>
        </div>
        
        <div className="discovery-review__selection-actions">
          <button className="discovery-review__text-btn" onClick={selectAll}>Select All</button>
          <button className="discovery-review__text-btn" onClick={clearSelection}>Clear</button>
          
          <Button
            variant="secondary"
            onClick={onSkipDeepResearch}
            disabled={starting}
          >
            Skip Deep Research
          </Button>
          
          <Button
            variant="primary"
            disabled={selectedCompanies.size === 0 || starting}
            onClick={handleStartDeepResearch}
          >
            {starting ? 'Starting...' : `Start Deep Research (${selectedCompanies.size})`}
          </Button>
        </div>
      </div>

      {/* Company Grid */}
      {filteredCompanies.length === 0 ? (
        <div className="discovery-review__empty">
          <h3>No companies found</h3>
          <p>Try adjusting your filters or search query</p>
        </div>
      ) : (
        <div className="discovery-review__grid">
          {filteredCompanies.map((company, index) => (
            <Card 
              key={`${company.company}-${index}`}
              hover
              className={`discovery-review__card ${selectedCompanies.has(company.company) ? 'discovery-review__card--selected' : ''}`}
            >
              <div className="discovery-review__card-header">
                <button
                  className={`discovery-review__checkbox ${selectedCompanies.has(company.company) ? 'discovery-review__checkbox--checked' : ''}`}
                  onClick={(e) => { e.stopPropagation(); toggleCompanySelection(company.company); }}
                >
                  {selectedCompanies.has(company.company) && <CheckIcon />}
                </button>
                
                <div 
                  className="discovery-review__card-title-row"
                  onClick={() => setExpandedCompany(
                    expandedCompany === company.company ? null : company.company
                  )}
                >
                  <h3 className="discovery-review__card-title">{company.company}</h3>
                  {company.vineyard_verified && (
                    <Badge variant="success">Verified</Badge>
                  )}
                </div>
              </div>

              <div className="discovery-review__card-meta">
                {company.segment && <SegmentTag segment={company.segment} />}
                {company.country && <CountryTag country={company.country} />}
                {company.confidence_0to1 !== undefined && (
                  <ConfidenceBadge confidence={company.confidence_0to1} />
                )}
                {company.provider && (
                  <Badge variant="default" className="discovery-review__provider-badge">
                    {company.provider}
                  </Badge>
                )}
              </div>
              
              {company.summary && (
                <p className="discovery-review__card-summary">
                  {expandedCompany === company.company 
                    ? company.summary 
                    : company.summary.slice(0, 150) + (company.summary.length > 150 ? '...' : '')}
                </p>
              )}

              {expandedCompany === company.company && (
                <div className="discovery-review__card-details">
                  {company.kpi_alignment && company.kpi_alignment.length > 0 && (
                    <div className="discovery-review__card-kpis">
                      <h4>KPI Alignment</h4>
                      <ul>
                        {company.kpi_alignment.map((kpi, i) => (
                          <li key={i}>{kpi}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  
                  {company.sources && company.sources.length > 0 && (
                    <div className="discovery-review__card-sources">
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
                      className="discovery-review__card-website"
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

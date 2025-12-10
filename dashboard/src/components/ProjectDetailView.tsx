import { useState, useEffect, useMemo, useRef } from 'react';
import type { Project, ResearchFramework, ProjectCost } from '../types';
import { CompanyCard, CompanyData } from './CompanyCard';
import { CompanyDetail } from './CompanyDetail';
import { CompareView } from './CompareView';
import { FloatingCompareBar } from './FloatingCompareBar';
import { ContextPopup } from './ContextPopup';
import { ReportTab } from './ReportTab';
import { useReviews } from '../hooks/useReviews';
import { Button, Badge, SearchInput, ProgressRing, Toggle } from './ui';
import { getApiBaseUrl, getAuthHeaders } from '../api';
import './ProjectDetailView.css';

interface ProjectDetailViewProps {
  project: Project;
  onBack: () => void;
  onUpdateProject: (updates: Partial<Project>) => void;
  shortlistedCompanies: string[];
  onToggleShortlist: (company: string) => void;
}

type ViewTab = 'companies' | 'review' | 'summary';
type ContextPopupType = 'thesis' | 'kpis' | 'valueChain' | 'brief' | null;

// Icons
const ThesisIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M8 2v12M4 6l4-4 4 4M4 10l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const KpiIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M2 14l4-6 3 3 5-7" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const ChainIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="4" cy="8" r="2" />
    <circle cx="12" cy="8" r="2" />
    <path d="M6 8h4" />
  </svg>
);

const BriefIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <rect x="2" y="2" width="12" height="12" rx="2" />
    <path d="M5 5h6M5 8h6M5 11h3" strokeLinecap="round" />
  </svg>
);

// Icons
const BackIcon = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M12 15l-5-5 5-5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const GridIcon = () => (
  <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5">
    <rect x="2" y="2" width="5" height="5" rx="1" />
    <rect x="11" y="2" width="5" height="5" rx="1" />
    <rect x="2" y="11" width="5" height="5" rx="1" />
    <rect x="11" y="11" width="5" height="5" rx="1" />
  </svg>
);

const ListIcon = () => (
  <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M3 4h12M3 9h12M3 14h12" strokeLinecap="round" />
  </svg>
);

const DownloadIcon = () => (
  <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M9 3v9m0 0l-3-3m3 3l3-3M3 15h12" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

export function ProjectDetailView({
  project,
  onBack,
  onUpdateProject,
  shortlistedCompanies,
  onToggleShortlist,
}: ProjectDetailViewProps) {
  // State
  const [activeTab, setActiveTab] = useState<ViewTab>('companies');
  const [companies, setCompanies] = useState<CompanyData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCompany, setSelectedCompany] = useState<CompanyData | null>(null);
  const [compareList, setCompareList] = useState<string[]>([]);
  const [showCompareView, setShowCompareView] = useState(false);
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [showShortlistedOnly, setShowShortlistedOnly] = useState(false);
  const [contextPopup, setContextPopup] = useState<ContextPopupType>(null);
  const [projectCost, setProjectCost] = useState<ProjectCost | null>(null);

  // Load companies from report
  useEffect(() => {
    if (project.reportPath) {
      loadCompanies(project.reportPath);
    } else {
      setLoading(false);
    }
  }, [project.reportPath]);

  // Load project cost data
  useEffect(() => {
    if (project.id) {
      fetch(`${getApiBaseUrl()}/projects/${project.id}/cost`, {
        headers: getAuthHeaders(),
      })
        .then(res => res.json())
        .then(data => setProjectCost({
          totalCost: data.total_cost || 0,
          discoveryCost: data.discovery_cost || 0,
          deepResearchCost: data.deep_research_cost || 0,
          enrichmentCost: data.enrichment_cost || 0,
          currency: data.currency || 'USD',
          lastUpdated: data.last_updated,
        }))
        .catch(err => console.error('Failed to load project cost:', err));
    }
  }, [project.id]);

  // Load framework from Supabase (thesis/KPIs/valueChain)
  useEffect(() => {
    if (!project.id) return;
    
    fetch(`${getApiBaseUrl()}/projects/${project.id}/framework`, {
      headers: getAuthHeaders(),
    })
      .then(res => res.json())
      .then(data => {
        if (data.found) {
          // Merge Supabase framework with local project framework
          const hasRemoteData = data.thesis || data.kpis?.length > 0 || data.value_chain?.length > 0;
          const hasLocalData = project.framework.thesis || project.framework.kpis?.length > 0 || project.framework.valueChain?.length > 0;
          
          // Only update if Supabase has data and local doesn't, or Supabase is newer
          if (hasRemoteData && !hasLocalData) {
            onUpdateProject({
              framework: {
                thesis: data.thesis || project.framework.thesis,
                kpis: data.kpis?.length > 0 ? data.kpis : project.framework.kpis,
                valueChain: data.value_chain?.length > 0 ? data.value_chain : project.framework.valueChain,
              },
            });
          }
        }
      })
      .catch(err => console.warn('Failed to load framework from server:', err));
  }, [project.id]);

  async function loadCompanies(reportPath: string) {
    try {
      setLoading(true);
      const response = await fetch(
        `${getApiBaseUrl()}/reports/${encodeURIComponent(reportPath)}/raw`,
        { headers: getAuthHeaders() }
      );
      if (!response.ok) throw new Error('Failed to fetch report');
      const data = await response.json();
      setCompanies(data.deep_research?.companies || []);
      setLoading(false);
    } catch (err) {
      setError('Failed to load companies');
      setLoading(false);
    }
  }

  // Reviews hook (for review tab)
  const segmentFilteredCompanies = useMemo(() => {
    const segments = project.framework.valueChain.map(vc => vc.segment);
    if (segments.length === 0) return companies;
    return companies.filter(c => 
      c.segment && segments.some(seg => c.segment?.includes(seg))
    );
  }, [companies, project.framework.valueChain]);

  const reviewsHook = useReviews(segmentFilteredCompanies, project.id);

  // Filter companies
  const filteredCompanies = useMemo(() => {
    let result = segmentFilteredCompanies;

    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter(c =>
        c.company.toLowerCase().includes(query) ||
        c.summary?.toLowerCase().includes(query) ||
        c.country?.toLowerCase().includes(query)
      );
    }

    // Shortlisted only
    if (showShortlistedOnly) {
      result = result.filter(c => shortlistedCompanies.includes(c.company));
    }

    return result;
  }, [segmentFilteredCompanies, searchQuery, showShortlistedOnly, shortlistedCompanies]);

  // Compute which companies appear in multiple value chain segments
  const companySegmentMap = useMemo(() => {
    const segmentMap: Record<string, string[]> = {};
    const valueChainSegments = project.framework.valueChain.map(vc => vc.segment);
    
    companies.forEach(company => {
      const companySegments: string[] = [];
      
      // Check each value chain segment
      valueChainSegments.forEach(segment => {
        if (company.segment?.toLowerCase().includes(segment.toLowerCase())) {
          companySegments.push(segment);
        }
      });
      
      // If no match found but company has a segment, use it
      if (companySegments.length === 0 && company.segment) {
        companySegments.push(company.segment);
      }
      
      segmentMap[company.company] = companySegments;
    });
    
    return segmentMap;
  }, [companies, project.framework.valueChain]);

  // Compare functionality
  const toggleCompare = (companyName: string) => {
    setCompareList(prev =>
      prev.includes(companyName)
        ? prev.filter(c => c !== companyName)
        : prev.length < 4 ? [...prev, companyName] : prev
    );
  };

  const clearCompareList = () => {
    setCompareList([]);
    setShowCompareView(false);
  };

  const removeFromCompare = (companyName: string) => {
    setCompareList(prev => prev.filter(c => c !== companyName));
  };

  const handleCompare = () => {
    if (compareList.length >= 2) {
      setShowCompareView(true);
    }
  };

  // Company navigation for detail panel
  const selectedIndex = useMemo(() => {
    if (!selectedCompany) return -1;
    return filteredCompanies.findIndex(c => c.company === selectedCompany.company);
  }, [filteredCompanies, selectedCompany]);

  const handlePrevCompany = () => {
    if (selectedIndex > 0) {
      setSelectedCompany(filteredCompanies[selectedIndex - 1]);
    }
  };

  const handleNextCompany = () => {
    if (selectedIndex < filteredCompanies.length - 1) {
      setSelectedCompany(filteredCompanies[selectedIndex + 1]);
    }
  };

  // Get compare companies data
  const compareCompanies = useMemo(() => {
    return companies.filter(c => compareList.includes(c.company));
  }, [companies, compareList]);

  // Export CSV
  const exportCSV = () => {
    const headers = ['Company', 'Country', 'Segment', 'Status', 'Score', 'Confidence'];
    const rows = filteredCompanies.map(c => {
      const review = reviewsHook.getReview(c.company);
      return [
        c.company,
        c.country || '',
        c.segment || '',
        review?.status || 'pending',
        review?.score || '',
        c.confidence_0to1 ? `${Math.round(c.confidence_0to1 * 100)}%` : '',
      ].join(',');
    });
    
    const csv = [headers.join(','), ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${project.projectName.replace(/\s+/g, '_')}_companies.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Update framework (local + Supabase)
  const handleUpdateFramework = (updates: Partial<ResearchFramework>) => {
    const newFramework = { ...project.framework, ...updates };
    
    // Update locally
    onUpdateProject({
      framework: newFramework,
    });
    
    // Sync to Supabase
    fetch(`${getApiBaseUrl()}/projects/${project.id}/framework`, {
      method: 'PUT',
      headers: getAuthHeaders(),
      body: JSON.stringify({
        thesis: newFramework.thesis,
        kpis: newFramework.kpis,
        value_chain: newFramework.valueChain,
      }),
    }).catch(err => console.error('Failed to save framework to server:', err));
  };

  // Calculate stats
  const stats = useMemo(() => ({
    total: filteredCompanies.length,
    reviewed: reviewsHook.stats.reviewed,
    approved: reviewsHook.stats.approved,
    rejected: reviewsHook.stats.rejected,
    pending: reviewsHook.stats.pending,
    progress: reviewsHook.stats.percentComplete,
  }), [filteredCompanies.length, reviewsHook.stats]);

  // Status badge
  const statusConfig: Record<string, { label: string; variant: 'default' | 'primary' | 'success' | 'warning' | 'danger' }> = {
    draft: { label: 'Draft', variant: 'default' },
    test_run: { label: 'Test Run', variant: 'primary' },
    pending_approval: { label: 'Pending Approval', variant: 'warning' },
    researching: { label: 'Researching', variant: 'primary' },
    discovery_failed: { label: 'Discovery Failed', variant: 'danger' },
    discovery_complete: { label: 'Discovery Complete', variant: 'success' },
    deep_researching: { label: 'Deep Research', variant: 'primary' },
    ready_for_review: { label: 'Ready for Review', variant: 'warning' },
    completed: { label: 'Completed', variant: 'success' },
  };

  const { label: statusLabel, variant: statusVariant } = statusConfig[project.status] || statusConfig.draft;

  return (
    <div className="project-detail">
      {/* Header */}
      <div className="project-detail__header">
        <div className="project-detail__header-left">
          <button className="project-detail__back" onClick={onBack} title="Back to Projects">
            <BackIcon />
            <span>Projects</span>
          </button>
          <div className="project-detail__header-divider" />
          <div>
            <h1 className="project-detail__title">{project.projectName}</h1>
            <div className="project-detail__meta">
              <span className="project-detail__client">{project.clientName}</span>
              <Badge variant={statusVariant}>{statusLabel}</Badge>
            </div>
          </div>
        </div>
        <div className="project-detail__header-right">
          {/* Context Buttons */}
          <div className="project-detail__context-buttons">
            <button
              className="project-detail__context-btn"
              onClick={() => setContextPopup('thesis')}
              title="View Investment Thesis"
            >
              <ThesisIcon />
              <span>Thesis</span>
            </button>
            <button
              className="project-detail__context-btn"
              onClick={() => setContextPopup('kpis')}
              title="View KPIs"
            >
              <KpiIcon />
              <span>KPIs</span>
              {project.framework.kpis.length > 0 && (
                <Badge variant="default" size="sm">{project.framework.kpis.length}</Badge>
              )}
            </button>
            <button
              className="project-detail__context-btn"
              onClick={() => setContextPopup('valueChain')}
              title="View Value Chain"
            >
              <ChainIcon />
              <span>Value Chain</span>
              {project.framework.valueChain.length > 0 && (
                <Badge variant="default" size="sm">{project.framework.valueChain.length}</Badge>
              )}
            </button>
            <button
              className="project-detail__context-btn"
              onClick={() => setContextPopup('brief')}
              title="View Research Brief"
            >
              <BriefIcon />
              <span>Brief</span>
            </button>
          </div>
          <div className="project-detail__header-separator" />
          <ProgressRing progress={stats.progress} size="lg" />
          <div className="project-detail__stats-summary">
            <span className="project-detail__stats-value">{stats.total}</span>
            <span className="project-detail__stats-label">companies</span>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="project-detail__tabs">
        <button
          className={`project-detail__tab ${activeTab === 'companies' ? 'project-detail__tab--active' : ''}`}
          onClick={() => setActiveTab('companies')}
        >
          Companies
          <Badge variant={activeTab === 'companies' ? 'primary' : 'default'} size="sm">
            {stats.total}
          </Badge>
        </button>
        <button
          className={`project-detail__tab ${activeTab === 'review' ? 'project-detail__tab--active' : ''}`}
          onClick={() => setActiveTab('review')}
        >
          Report
          {stats.reviewed > 0 && (
            <Badge variant="success" size="sm">{stats.reviewed}</Badge>
          )}
        </button>
        <button
          className={`project-detail__tab ${activeTab === 'summary' ? 'project-detail__tab--active' : ''}`}
          onClick={() => setActiveTab('summary')}
        >
          Summary
        </button>

        <div className="project-detail__tabs-spacer" />
      </div>

      {/* Main Content */}
      <div className="project-detail__content">
        {/* Main Area - Full Width */}
        <div className="project-detail__main project-detail__main--full">
          {/* Toolbar - only show search/shortlist/export for companies tab */}
          {activeTab === 'companies' && (
            <div className="project-detail__toolbar">
              <div className="project-detail__search">
                <SearchInput
                  placeholder="Search companies..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onClear={() => setSearchQuery('')}
                />
              </div>

              <Toggle
                label="Shortlisted only"
                checked={showShortlistedOnly}
                onChange={(e) => setShowShortlistedOnly(e.target.checked)}
                size="sm"
              />

              <div className="project-detail__view-toggle">
                <button
                  className={`project-detail__view-btn ${viewMode === 'grid' ? 'project-detail__view-btn--active' : ''}`}
                  onClick={() => setViewMode('grid')}
                >
                  <GridIcon />
                </button>
                <button
                  className={`project-detail__view-btn ${viewMode === 'list' ? 'project-detail__view-btn--active' : ''}`}
                  onClick={() => setViewMode('list')}
                >
                  <ListIcon />
                </button>
              </div>

              <Button variant="secondary" size="sm" onClick={exportCSV}>
                <DownloadIcon />
                Export
              </Button>
            </div>
          )}

          {/* Loading / Error */}
          {loading && (
            <div className="project-detail__loading">
              <div className="loading-spinner" />
              <p>Loading companies...</p>
            </div>
          )}

          {error && (
            <div className="project-detail__error">
              <p>{error}</p>
            </div>
          )}

          {/* Companies Tab */}
          {!loading && !error && activeTab === 'companies' && (
            <div className={`project-detail__companies project-detail__companies--${viewMode}`}>
              {filteredCompanies.length === 0 ? (
                <div className="project-detail__empty">
                  <p>No companies found</p>
                </div>
              ) : (
                filteredCompanies.map((company, index) => (
                  <CompanyCard
                    key={`${company.company}-${index}`}
                    company={company}
                    isShortlisted={shortlistedCompanies.includes(company.company)}
                    isSelected={selectedCompany?.company === company.company}
                    isCompareSelected={compareList.includes(company.company)}
                    onToggleShortlist={() => onToggleShortlist(company.company)}
                    onSelect={() => setSelectedCompany(company)}
                    onToggleCompare={() => toggleCompare(company.company)}
                    allSegments={companySegmentMap[company.company] || []}
                    reviewStatus={reviewsHook.getReview(company.company)?.status}
                  />
                ))
              )}
            </div>
          )}

          {/* Report Tab */}
          {!loading && !error && activeTab === 'review' && (
            <ReportTab
              companies={filteredCompanies}
              getReview={reviewsHook.getReview}
              onExportCSV={exportCSV}
              onSelectCompany={(company) => setSelectedCompany(company)}
            />
          )}

          {/* Summary Tab */}
          {activeTab === 'summary' && (
            <div className="project-detail__summary">
              <div className="project-detail__summary-grid">
                <div className="project-detail__summary-card">
                  <h3>Review Progress</h3>
                  <div className="project-detail__summary-stat">
                    <ProgressRing progress={stats.progress} size="xl" />
                    <div>
                      <span className="project-detail__summary-value">{stats.reviewed}</span>
                      <span className="project-detail__summary-label">of {stats.total} reviewed</span>
                    </div>
                  </div>
                </div>

                <div className="project-detail__summary-card">
                  <h3>Decisions</h3>
                  <div className="project-detail__summary-decisions">
                    <div className="project-detail__decision project-detail__decision--approved">
                      <span className="project-detail__decision-value">{stats.approved}</span>
                      <span className="project-detail__decision-label">Approved</span>
                    </div>
                    <div className="project-detail__decision project-detail__decision--rejected">
                      <span className="project-detail__decision-value">{stats.rejected}</span>
                      <span className="project-detail__decision-label">Rejected</span>
                    </div>
                    <div className="project-detail__decision project-detail__decision--pending">
                      <span className="project-detail__decision-value">{stats.pending}</span>
                      <span className="project-detail__decision-label">Pending</span>
                    </div>
                  </div>
                </div>

                <div className="project-detail__summary-card">
                  <h3>Research Costs</h3>
                  <div className="project-detail__cost-breakdown">
                    <div className="project-detail__cost-item project-detail__cost-item--total">
                      <span className="project-detail__cost-label">Total</span>
                      <span className="project-detail__cost-value">
                        ${projectCost?.totalCost?.toFixed(2) || '0.00'}
                      </span>
                    </div>
                    <div className="project-detail__cost-item">
                      <span className="project-detail__cost-label">Discovery</span>
                      <span className="project-detail__cost-value">
                        ${projectCost?.discoveryCost?.toFixed(2) || '0.00'}
                      </span>
                    </div>
                    <div className="project-detail__cost-item">
                      <span className="project-detail__cost-label">Deep Research</span>
                      <span className="project-detail__cost-value">
                        ${projectCost?.deepResearchCost?.toFixed(2) || '0.00'}
                      </span>
                    </div>
                    <div className="project-detail__cost-item">
                      <span className="project-detail__cost-label">Enrichment</span>
                      <span className="project-detail__cost-value">
                        ${projectCost?.enrichmentCost?.toFixed(2) || '0.00'}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="project-detail__summary-card project-detail__summary-card--full">
                  <h3>Value Chain Coverage</h3>
                  <div className="project-detail__value-chain-stats">
                    {project.framework.valueChain.map((vc, i) => {
                      const count = companies.filter(c => c.segment?.includes(vc.segment)).length;
                      return (
                        <div key={i} className="project-detail__value-chain-item">
                          <span className="project-detail__value-chain-name">{vc.segment}</span>
                          <Badge variant="default">{count}</Badge>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Floating Compare Bar */}
      <FloatingCompareBar
        selectedCompanies={compareCompanies}
        onRemove={removeFromCompare}
        onClear={clearCompareList}
        onCompare={handleCompare}
        maxCompanies={4}
      />

      {/* Compare View Modal */}
      {showCompareView && compareCompanies.length >= 2 && (
        <div className="compare-modal-overlay" onClick={() => setShowCompareView(false)}>
          <div className="compare-modal" onClick={(e) => e.stopPropagation()}>
            <CompareView
              companies={compareCompanies}
              onClose={() => setShowCompareView(false)}
              shortlistedCompanies={shortlistedCompanies}
              onToggleShortlist={onToggleShortlist}
            />
          </div>
        </div>
      )}

      {/* Company Detail Slide Panel */}
      <div
        className={`slide-panel-overlay ${selectedCompany ? 'slide-panel-overlay--open' : ''}`}
        onClick={() => setSelectedCompany(null)}
      />
      <div className={`slide-panel ${selectedCompany ? 'slide-panel--open' : ''}`}>
        {selectedCompany && (
          <CompanyDetail
            company={selectedCompany}
            isShortlisted={shortlistedCompanies.includes(selectedCompany.company)}
            onToggleShortlist={() => onToggleShortlist(selectedCompany.company)}
            onClose={() => setSelectedCompany(null)}
            // Review action props
            review={reviewsHook.getReview(selectedCompany.company)}
            onApprove={() => reviewsHook.setStatus(selectedCompany.company, 'approved')}
            onReject={() => reviewsHook.setStatus(selectedCompany.company, 'rejected')}
            onMaybe={() => reviewsHook.setStatus(selectedCompany.company, 'maybe')}
            onScoreChange={(score) => reviewsHook.setScore(selectedCompany.company, score)}
            onToggleCompare={() => toggleCompare(selectedCompany.company)}
            isCompareSelected={compareList.includes(selectedCompany.company)}
            // Navigation props
            onPrev={handlePrevCompany}
            onNext={handleNextCompany}
            hasPrev={selectedIndex > 0}
            hasNext={selectedIndex < filteredCompanies.length - 1}
            currentIndex={selectedIndex}
            totalCount={filteredCompanies.length}
          />
        )}
      </div>

      {/* Context Popups */}
      {contextPopup === 'thesis' && (
        <ContextPopup
          type="thesis"
          title="Investment Thesis"
          content={project.framework.thesis}
          onClose={() => setContextPopup(null)}
        />
      )}
      {contextPopup === 'kpis' && (
        <ContextPopup
          type="kpis"
          title="Key Performance Indicators"
          content={project.framework.kpis}
          onClose={() => setContextPopup(null)}
        />
      )}
      {contextPopup === 'valueChain' && (
        <ContextPopup
          type="valueChain"
          title="Value Chain Segments"
          content={project.framework.valueChain}
          onClose={() => setContextPopup(null)}
        />
      )}
      {contextPopup === 'brief' && (
        <ContextPopup
          type="brief"
          title="Research Brief"
          content={`**Objective:** ${project.brief.objective || 'Not defined'}

**Target Stages:** ${project.brief.targetStages?.join(', ') || 'Not defined'}

**Investment Size:** ${project.brief.investmentSize || 'Not defined'}

**Geography:** ${project.brief.geography?.join(', ') || 'Not defined'}

**Technologies:** ${project.brief.technologies?.join(', ') || 'Not defined'}

**Additional Notes:** ${project.brief.additionalNotes || 'None'}`}
          onClose={() => setContextPopup(null)}
        />
      )}
    </div>
  );
}


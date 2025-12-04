import { useState, useEffect, useMemo } from 'react';
import type { Project, ResearchFramework } from '../types';
import { CompanyCard, CompanyData } from './CompanyCard';
import { CompanyDetail } from './CompanyDetail';
import { ContextPanel } from './ContextPanel';
import { ReviewCard } from './ReviewCard';
import { useReviews } from '../hooks/useReviews';
import { Button, Badge, SearchInput, ProgressRing, Toggle } from './ui';
import './ProjectDetailView.css';

interface ProjectDetailViewProps {
  project: Project;
  onBack: () => void;
  onUpdateProject: (updates: Partial<Project>) => void;
  shortlistedCompanies: string[];
  onToggleShortlist: (company: string) => void;
}

type ViewTab = 'companies' | 'review' | 'summary';

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
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [showShortlistedOnly, setShowShortlistedOnly] = useState(false);
  const [showContextPanel, setShowContextPanel] = useState(true);

  // Load companies from report
  useEffect(() => {
    if (project.reportPath) {
      loadCompanies(project.reportPath);
    } else {
      setLoading(false);
    }
  }, [project.reportPath]);

  async function loadCompanies(reportPath: string) {
    try {
      setLoading(true);
      const response = await fetch(
        `http://localhost:8000/reports/${encodeURIComponent(reportPath)}/raw`
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

  const reviewsHook = useReviews(segmentFilteredCompanies);

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

  // Compare toggle
  const toggleCompare = (companyName: string) => {
    setCompareList(prev =>
      prev.includes(companyName)
        ? prev.filter(c => c !== companyName)
        : prev.length < 4 ? [...prev, companyName] : prev
    );
  };

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

  // Update framework
  const handleUpdateFramework = (updates: Partial<ResearchFramework>) => {
    onUpdateProject({
      framework: { ...project.framework, ...updates },
    });
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
  const statusConfig: Record<string, { label: string; variant: 'default' | 'primary' | 'success' | 'warning' }> = {
    draft: { label: 'Draft', variant: 'default' },
    test_run: { label: 'Test Run', variant: 'primary' },
    pending_approval: { label: 'Pending Approval', variant: 'warning' },
    researching: { label: 'Researching', variant: 'primary' },
    ready_for_review: { label: 'Ready for Review', variant: 'warning' },
    completed: { label: 'Completed', variant: 'success' },
  };

  const { label: statusLabel, variant: statusVariant } = statusConfig[project.status] || statusConfig.draft;

  return (
    <div className="project-detail">
      {/* Header */}
      <div className="project-detail__header">
        <div className="project-detail__header-left">
          <button className="project-detail__back" onClick={onBack}>
            <BackIcon />
          </button>
          <div>
            <h1 className="project-detail__title">{project.projectName}</h1>
            <div className="project-detail__meta">
              <span className="project-detail__client">{project.clientName}</span>
              <Badge variant={statusVariant}>{statusLabel}</Badge>
            </div>
          </div>
        </div>
        <div className="project-detail__header-right">
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
          Review
          {stats.pending > 0 && (
            <Badge variant="warning" size="sm">{stats.pending}</Badge>
          )}
        </button>
        <button
          className={`project-detail__tab ${activeTab === 'summary' ? 'project-detail__tab--active' : ''}`}
          onClick={() => setActiveTab('summary')}
        >
          Summary
        </button>

        <div className="project-detail__tabs-spacer" />

        <Button 
          variant="ghost" 
          size="sm"
          onClick={() => setShowContextPanel(!showContextPanel)}
        >
          {showContextPanel ? 'Hide Context' : 'Show Context'}
        </Button>
      </div>

      {/* Main Content */}
      <div className="project-detail__content">
        {/* Context Panel */}
        {showContextPanel && (
          <div className="project-detail__sidebar">
            <ContextPanel
              project={project}
              onUpdateFramework={handleUpdateFramework}
              isEditable={project.status === 'draft' || project.status === 'pending_approval'}
              compact
            />
          </div>
        )}

        {/* Main Area */}
        <div className="project-detail__main">
          {/* Toolbar */}
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
                filteredCompanies.map((company) => (
                  <CompanyCard
                    key={company.company}
                    company={company}
                    isShortlisted={shortlistedCompanies.includes(company.company)}
                    isSelected={selectedCompany?.company === company.company}
                    isCompareSelected={compareList.includes(company.company)}
                    onToggleShortlist={() => onToggleShortlist(company.company)}
                    onSelect={() => setSelectedCompany(company)}
                    onToggleCompare={() => toggleCompare(company.company)}
                  />
                ))
              )}
            </div>
          )}

          {/* Review Tab */}
          {!loading && !error && activeTab === 'review' && (
            <div className="project-detail__review">
              {filteredCompanies.map((company, index) => (
                <ReviewCard
                  key={company.company}
                  company={company}
                  review={reviewsHook.getReview(company.company)}
                  isActive={reviewsHook.currentIndex === index}
                  isShortlisted={shortlistedCompanies.includes(company.company)}
                  isCompareSelected={compareList.includes(company.company)}
                  onSelect={() => reviewsHook.goToIndex(index)}
                  onToggleShortlist={() => onToggleShortlist(company.company)}
                  onToggleCompare={() => toggleCompare(company.company)}
                  onApprove={() => reviewsHook.setStatus(company.company, 'approved')}
                  onReject={() => reviewsHook.setStatus(company.company, 'rejected')}
                  onMaybe={() => reviewsHook.setStatus(company.company, 'maybe')}
                  onScoreChange={(score) => reviewsHook.setScore(company.company, score)}
                  onEditData={() => {}}
                />
              ))}
            </div>
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
          />
        )}
      </div>
    </div>
  );
}


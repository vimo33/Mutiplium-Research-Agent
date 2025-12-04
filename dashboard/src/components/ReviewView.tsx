import { useState, useEffect, useMemo, useCallback } from 'react';
import { useReviews } from '../hooks/useReviews';
import { ReviewCard } from './ReviewCard';
import { ReviewSummary } from './ReviewSummary';
import { DataQualityPanel } from './DataQualityPanel';
import { CompareView } from './CompareView';
import { CompanyData } from './CompanyCard';
import { Button, Badge, SearchInput, ProgressRing } from './ui';
import type { ReviewStatus } from '../types';
import './ReviewView.css';

interface ReviewViewProps {
  selectedSegments: string[];
  shortlistedCompanies: string[];
  onToggleShortlist: (company: string) => void;
}

// Icons
const CheckIcon = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M4 10l4 4 8-8" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const XIcon = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M5 5l10 10M15 5L5 15" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const QuestionIcon = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="10" cy="10" r="8" />
    <path d="M7 7.5a3 3 0 014.5 2.5c0 1.5-2.5 2-2.5 3.5M10 15h.01" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const ChevronLeftIcon = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M12 15l-5-5 5-5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const ChevronRightIcon = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M8 5l5 5-5 5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const CompareIcon = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
    <rect x="2" y="3" width="6" height="14" rx="1" />
    <rect x="12" y="3" width="6" height="14" rx="1" />
  </svg>
);

const DownloadIcon = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M10 3v10m0 0l-3-3m3 3l3-3M4 17h12" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

export function ReviewView({
  selectedSegments,
  shortlistedCompanies,
  onToggleShortlist,
}: ReviewViewProps) {
  // State
  const [allCompanies, setAllCompanies] = useState<CompanyData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [showCompare, setShowCompare] = useState(false);
  const [compareList, setCompareList] = useState<string[]>([]);
  const [showDataPanel, setShowDataPanel] = useState(false);
  const [showSummary, setShowSummary] = useState(false);
  
  // Load companies from latest report
  useEffect(() => {
    loadCompanies();
  }, []);
  
  async function loadCompanies() {
    try {
      setLoading(true);
      const response = await fetch('http://localhost:8000/reports');
      const data = await response.json();
      const deepResearchReports = data.reports.filter(
        (r: any) => r.report_type === 'deep_research'
      );
      
      if (deepResearchReports.length > 0) {
        const reportResponse = await fetch(
          `http://localhost:8000/reports/${encodeURIComponent(deepResearchReports[0].path)}/raw`
        );
        const reportData = await reportResponse.json();
        setAllCompanies(reportData.deep_research?.companies || []);
      }
      setLoading(false);
    } catch (err) {
      setError('Failed to load companies. Make sure the API server is running.');
      setLoading(false);
    }
  }
  
  // Filter by segments
  const segmentFilteredCompanies = useMemo(() => {
    if (selectedSegments.length === 0) return allCompanies;
    return allCompanies.filter(c => 
      c.segment && selectedSegments.some(seg => c.segment?.includes(seg))
    );
  }, [allCompanies, selectedSegments]);
  
  // Use reviews hook
  const {
    filteredCompanies,
    currentCompany,
    currentReview,
    currentIndex,
    stats,
    filterStatus,
    sortBy,
    setStatus,
    setScore,
    setNotes,
    addFlag,
    removeFlag,
    setDataEdit,
    setFilter,
    setSort,
    goToIndex,
    goToNext,
    goToPrev,
    getReview,
    approveAndNext,
    rejectAndNext,
    maybeAndNext,
    exportToCSV,
  } = useReviews(segmentFilteredCompanies);
  
  // Search filter
  const searchFilteredCompanies = useMemo(() => {
    if (!searchQuery) return filteredCompanies;
    const query = searchQuery.toLowerCase();
    return filteredCompanies.filter(c =>
      c.company.toLowerCase().includes(query) ||
      c.summary?.toLowerCase().includes(query) ||
      c.country?.toLowerCase().includes(query)
    );
  }, [filteredCompanies, searchQuery]);
  
  // Compare toggle
  const toggleCompare = useCallback((companyName: string) => {
    setCompareList(prev => 
      prev.includes(companyName)
        ? prev.filter(c => c !== companyName)
        : prev.length < 4 ? [...prev, companyName] : prev
    );
  }, []);
  
  // Companies for compare view
  const compareCompanies = useMemo(() => {
    return allCompanies.filter(c => compareList.includes(c.company));
  }, [allCompanies, compareList]);
  
  // Keyboard shortcuts
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      // Don't trigger if typing in input
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }
      
      if (!currentCompany) return;
      
      switch (e.key.toLowerCase()) {
        case 'a':
          approveAndNext(currentCompany.company);
          break;
        case 'r':
          rejectAndNext(currentCompany.company);
          break;
        case 'm':
          maybeAndNext(currentCompany.company);
          break;
        case 'n':
        case 'arrowright':
          goToNext();
          break;
        case 'p':
        case 'arrowleft':
          goToPrev();
          break;
        case 'e':
          setShowDataPanel(true);
          break;
        case 'escape':
          setShowDataPanel(false);
          setShowCompare(false);
          break;
      }
    }
    
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [currentCompany, approveAndNext, rejectAndNext, maybeAndNext, goToNext, goToPrev]);
  
  // Filter tabs
  const filterTabs: Array<{ id: ReviewStatus | 'all' | 'flagged'; label: string; count: number }> = [
    { id: 'all', label: 'All', count: stats.total },
    { id: 'pending', label: 'Pending', count: stats.pending },
    { id: 'approved', label: 'Approved', count: stats.approved },
    { id: 'rejected', label: 'Rejected', count: stats.rejected },
    { id: 'maybe', label: 'Maybe', count: stats.maybe },
    { id: 'flagged', label: 'Flagged', count: stats.flagged },
  ];
  
  // Loading state
  if (loading) {
    return (
      <div className="loading-state">
        <div className="loading-spinner" />
        <p className="loading-state__text">Loading companies for review...</p>
      </div>
    );
  }
  
  // Error state
  if (error) {
    return (
      <div className="empty-state">
        <div className="empty-state__icon">⚠️</div>
        <h3 className="empty-state__title">Error Loading Data</h3>
        <p className="empty-state__message">{error}</p>
      </div>
    );
  }
  
  // Compare view
  if (showCompare && compareCompanies.length >= 2) {
    return (
      <CompareView
        companies={compareCompanies}
        onClose={() => setShowCompare(false)}
        shortlistedCompanies={shortlistedCompanies}
        onToggleShortlist={onToggleShortlist}
      />
    );
  }
  
  // Summary view
  if (showSummary) {
    return (
      <ReviewSummary
        stats={stats}
        companies={allCompanies}
        getReview={getReview}
        onClose={() => setShowSummary(false)}
        onExport={exportToCSV}
      />
    );
  }
  
  return (
    <div className="review-view">
      {/* Header */}
      <div className="review-view__header">
        <div className="review-view__header-left">
          <h1 className="review-view__title">Review Queue</h1>
          <p className="review-view__subtitle">
            {stats.reviewed} of {stats.total} reviewed ({stats.percentComplete}%)
          </p>
        </div>
        <div className="review-view__header-right">
          <ProgressRing progress={stats.percentComplete} size="lg" />
        </div>
      </div>
      
      {/* Progress bar */}
      <div className="review-view__progress">
        <div 
          className="review-view__progress-fill"
          style={{ width: `${stats.percentComplete}%` }}
        />
      </div>
      
      {/* Toolbar */}
      <div className="review-view__toolbar">
        <div className="review-view__search">
          <SearchInput
            placeholder="Search companies..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onClear={() => setSearchQuery('')}
          />
        </div>
        
        <div className="review-view__sort">
          <label>Sort by:</label>
          <select 
            value={sortBy} 
            onChange={(e) => setSort(e.target.value as any)}
            className="review-view__select"
          >
            <option value="confidence">Confidence</option>
            <option value="name">Name</option>
            <option value="status">Status</option>
            <option value="score">Score</option>
          </select>
        </div>
        
        <div className="review-view__actions">
          {compareList.length >= 2 && (
            <Button 
              variant="secondary" 
              onClick={() => setShowCompare(true)}
            >
              <CompareIcon />
              Compare ({compareList.length})
            </Button>
          )}
          {compareList.length > 0 && (
            <Button variant="ghost" onClick={() => setCompareList([])}>
              Clear
            </Button>
          )}
          <Button variant="secondary" onClick={() => setShowSummary(true)}>
            Summary
          </Button>
          <Button variant="secondary" onClick={exportToCSV}>
            <DownloadIcon />
            Export CSV
          </Button>
        </div>
      </div>
      
      {/* Filter tabs */}
      <div className="review-view__tabs">
        {filterTabs.map(tab => (
          <button
            key={tab.id}
            className={`review-view__tab ${filterStatus === tab.id ? 'review-view__tab--active' : ''}`}
            onClick={() => setFilter(tab.id)}
          >
            {tab.label}
            <Badge 
              variant={filterStatus === tab.id ? 'primary' : 'default'}
              size="sm"
            >
              {tab.count}
            </Badge>
          </button>
        ))}
      </div>
      
      {/* Main content */}
      <div className="review-view__content">
        {/* Company list */}
        <div className="review-view__list">
          {searchFilteredCompanies.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state__icon">📋</div>
              <h3 className="empty-state__title">No companies found</h3>
              <p className="empty-state__message">
                Try adjusting your filters or search query
              </p>
            </div>
          ) : (
            searchFilteredCompanies.map((company, index) => (
              <ReviewCard
                key={company.company}
                company={company}
                review={getReview(company.company)}
                isActive={currentIndex === index}
                isShortlisted={shortlistedCompanies.includes(company.company)}
                isCompareSelected={compareList.includes(company.company)}
                onSelect={() => goToIndex(index)}
                onToggleShortlist={() => onToggleShortlist(company.company)}
                onToggleCompare={() => toggleCompare(company.company)}
                onApprove={() => setStatus(company.company, 'approved')}
                onReject={() => setStatus(company.company, 'rejected')}
                onMaybe={() => setStatus(company.company, 'maybe')}
                onScoreChange={(score) => setScore(company.company, score)}
                onEditData={() => {
                  goToIndex(index);
                  setShowDataPanel(true);
                }}
              />
            ))
          )}
        </div>
        
        {/* Quick action bar */}
        {currentCompany && (
          <div className="review-view__action-bar">
            <div className="review-view__nav">
              <Button 
                variant="ghost" 
                onClick={goToPrev}
                disabled={currentIndex === 0}
              >
                <ChevronLeftIcon />
                Prev (P)
              </Button>
              <span className="review-view__counter">
                {currentIndex + 1} / {searchFilteredCompanies.length}
              </span>
              <Button 
                variant="ghost" 
                onClick={goToNext}
                disabled={currentIndex >= searchFilteredCompanies.length - 1}
              >
                Next (N)
                <ChevronRightIcon />
              </Button>
            </div>
            
            <div className="review-view__current">
              <span className="review-view__current-name">
                {currentCompany.company}
              </span>
            </div>
            
            <div className="review-view__quick-actions">
              <Button 
                variant="success" 
                onClick={() => approveAndNext(currentCompany.company)}
              >
                <CheckIcon />
                Approve (A)
              </Button>
              <Button 
                variant="danger" 
                onClick={() => rejectAndNext(currentCompany.company)}
              >
                <XIcon />
                Reject (R)
              </Button>
              <Button 
                variant="warning" 
                onClick={() => maybeAndNext(currentCompany.company)}
              >
                <QuestionIcon />
                Maybe (M)
              </Button>
            </div>
          </div>
        )}
      </div>
      
      {/* Keyboard shortcuts help */}
      <div className="review-view__shortcuts">
        <span className="review-view__shortcut"><kbd>A</kbd> Approve</span>
        <span className="review-view__shortcut"><kbd>R</kbd> Reject</span>
        <span className="review-view__shortcut"><kbd>M</kbd> Maybe</span>
        <span className="review-view__shortcut"><kbd>←/→</kbd> Navigate</span>
        <span className="review-view__shortcut"><kbd>E</kbd> Edit data</span>
      </div>
      
      {/* Data quality panel slide-out */}
      <div 
        className={`slide-panel-overlay ${showDataPanel ? 'slide-panel-overlay--open' : ''}`}
        onClick={() => setShowDataPanel(false)}
      />
      <div className={`slide-panel ${showDataPanel ? 'slide-panel--open' : ''}`}>
        {showDataPanel && currentCompany && (
          <DataQualityPanel
            company={currentCompany}
            review={currentReview}
            onAddFlag={(flag) => addFlag(currentCompany.company, flag)}
            onRemoveFlag={(flag) => removeFlag(currentCompany.company, flag)}
            onEditField={(field, value) => setDataEdit(currentCompany.company, field, value)}
            onClose={() => setShowDataPanel(false)}
          />
        )}
      </div>
    </div>
  );
}


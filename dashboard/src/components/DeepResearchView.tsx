import { useState, useEffect, useMemo } from 'react';
import { CompanyCard, CompanyData } from './CompanyCard';
import { CompanyDetail } from './CompanyDetail';
import { SearchInput, Button, Badge, Toggle } from './ui';
import { CompareView } from './CompareView';
import './DeepResearchView.css';

interface DeepResearchReport {
  generated_at: string;
  sector: string;
  deep_research?: {
    companies: CompanyData[];
  };
}

interface DeepResearchViewProps {
  selectedSegments: string[];
  shortlistedCompanies: string[];
  onToggleShortlist: (company: string) => void;
}

export function DeepResearchView({
  selectedSegments,
  shortlistedCompanies,
  onToggleShortlist,
}: DeepResearchViewProps) {
  const [reports, setReports] = useState<{ path: string; filename: string }[]>([]);
  const [selectedReport, setSelectedReport] = useState<string | null>(null);
  const [reportData, setReportData] = useState<DeepResearchReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // UI State
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCompany, setSelectedCompany] = useState<CompanyData | null>(null);
  const [compareList, setCompareList] = useState<string[]>([]);
  const [showCompare, setShowCompare] = useState(false);
  const [showShortlistedOnly, setShowShortlistedOnly] = useState(false);
  const [minConfidence, setMinConfidence] = useState(0);

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
      const deepResearchReports = data.reports.filter(
        (r: any) => r.report_type === 'deep_research'
      );
      setReports(deepResearchReports);
      if (deepResearchReports.length > 0) {
        setSelectedReport(deepResearchReports[0].path);
      }
      setLoading(false);
    } catch (err) {
      setError('Failed to load reports. Make sure the API server is running.');
      setLoading(false);
    }
  }

  async function loadReportData(path: string) {
    try {
      setLoading(true);
      // Fetch raw JSON file
      const response = await fetch(`http://localhost:8000/reports/${encodeURIComponent(path)}/raw`);
      if (!response.ok) throw new Error('Failed to fetch report');
      const data = await response.json();
      setReportData(data);
      setLoading(false);
    } catch (err) {
      // Try direct file access as fallback
      try {
        const response = await fetch(`/reports/${path}`);
        const data = await response.json();
        setReportData(data);
        setLoading(false);
      } catch {
        setError('Failed to load report data');
        setLoading(false);
      }
    }
  }

  // Get all companies from report
  const allCompanies = useMemo(() => {
    if (!reportData?.deep_research?.companies) return [];
    return reportData.deep_research.companies;
  }, [reportData]);

  // Get unique segments
  const segments = useMemo(() => {
    const segmentSet = new Set<string>();
    allCompanies.forEach(c => {
      if (c.segment) segmentSet.add(c.segment);
    });
    return Array.from(segmentSet).sort();
  }, [allCompanies]);

  // Filter companies
  const filteredCompanies = useMemo(() => {
    let result = allCompanies;

    // Segment filter
    if (selectedSegments.length > 0) {
      result = result.filter(c => 
        c.segment && selectedSegments.some(seg => c.segment?.includes(seg))
      );
    }

    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter(c =>
        c.company.toLowerCase().includes(query) ||
        c.summary?.toLowerCase().includes(query) ||
        c.country?.toLowerCase().includes(query)
      );
    }

    // Confidence filter
    if (minConfidence > 0) {
      result = result.filter(c => (c.confidence_0to1 || 0) >= minConfidence);
    }

    // Shortlisted only
    if (showShortlistedOnly) {
      result = result.filter(c => shortlistedCompanies.includes(c.company));
    }

    return result;
  }, [allCompanies, selectedSegments, searchQuery, minConfidence, showShortlistedOnly, shortlistedCompanies]);

  // Compare toggle
  const toggleCompare = (companyName: string) => {
    setCompareList(prev => 
      prev.includes(companyName)
        ? prev.filter(c => c !== companyName)
        : prev.length < 4 ? [...prev, companyName] : prev
    );
  };

  // Get companies for comparison
  const compareCompanies = useMemo(() => {
    return allCompanies.filter(c => compareList.includes(c.company));
  }, [allCompanies, compareList]);

  if (loading && !reportData) {
    return (
      <div className="loading-state">
        <div className="loading-spinner" />
        <p className="loading-state__text">Loading deep research data...</p>
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

  return (
    <div className="deep-research-view">
      {/* Header */}
      <div className="page-header">
        <h1 className="page-header__title">Deep Research</h1>
        <p className="page-header__subtitle">
          {reportData?.sector || 'Investment research'} • {allCompanies.length} companies
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
          
          <select
            className="filter-select"
            value={minConfidence}
            onChange={(e) => setMinConfidence(Number(e.target.value))}
          >
            <option value={0}>All Confidence</option>
            <option value={0.6}>60%+</option>
            <option value={0.7}>70%+</option>
            <option value={0.8}>80%+</option>
          </select>
          
          <Toggle
            label="Shortlisted only"
            checked={showShortlistedOnly}
            onChange={(e) => setShowShortlistedOnly(e.target.checked)}
            size="sm"
          />
        </div>

        <div className="filter-bar__actions">
          {compareList.length >= 2 && (
            <Button variant="primary" onClick={() => setShowCompare(true)}>
              Compare ({compareList.length})
            </Button>
          )}
          {compareList.length > 0 && (
            <Button variant="ghost" onClick={() => setCompareList([])}>
              Clear
            </Button>
          )}
        </div>
      </div>

      {/* Stats */}
      <div className="stats-row">
        <Badge variant="default">
          {filteredCompanies.length} of {allCompanies.length} companies
        </Badge>
        {selectedSegments.length > 0 && (
          <Badge variant="primary">
            {selectedSegments.length} segment{selectedSegments.length > 1 ? 's' : ''} selected
          </Badge>
        )}
        {shortlistedCompanies.length > 0 && (
          <Badge variant="warning">
            {shortlistedCompanies.length} shortlisted
          </Badge>
        )}
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
        <div className="company-grid">
          {filteredCompanies.map((company) => (
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
          ))}
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
          />
        )}
      </div>

      {/* Compare Bar */}
      <div className={`compare-bar ${compareList.length > 0 ? 'compare-bar--visible' : ''}`}>
        <div className="compare-bar__content">
          <div className="compare-bar__info">
            <span className="compare-bar__count">
              {compareList.length} selected for comparison
            </span>
            <div className="compare-bar__companies">
              {compareList.map(name => (
                <Badge key={name} variant="info" onRemove={() => toggleCompare(name)}>
                  {name}
                </Badge>
              ))}
            </div>
          </div>
          <div className="compare-bar__actions">
            <Button 
              variant="primary" 
              disabled={compareList.length < 2}
              onClick={() => setShowCompare(true)}
            >
              Compare Now
            </Button>
            <Button variant="ghost" onClick={() => setCompareList([])}>
              Clear All
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}


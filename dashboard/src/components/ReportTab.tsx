import { useMemo, useState } from 'react';
import type { CompanyData } from './CompanyCard';
import type { CompanyReview, ReviewStatus } from '../types';
import { Badge } from './ui';
import './ReportTab.css';

interface ReportTabProps {
  companies: CompanyData[];
  getReview: (company: string) => CompanyReview | undefined;
  onExportCSV?: () => void; // Made optional since not used in UI anymore
  onSelectCompany?: (company: CompanyData) => void;
}

const CheckIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M3 7l3 3 5-6" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const XIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M3 3l8 8M11 3L3 11" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const QuestionIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="7" cy="7" r="5" />
    <path d="M5.5 5.5a1.5 1.5 0 012.25 1.13c0 .75-1.12 1.12-1.12 1.87M7 10h.01" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const SortIcon = ({ direction }: { direction: 'asc' | 'desc' | null }) => (
  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path 
      d="M6 2v8M6 2L3 5M6 2l3 3" 
      strokeLinecap="round" 
      strokeLinejoin="round"
      opacity={direction === 'asc' ? 1 : 0.3}
    />
    <path 
      d="M6 10l-3-3M6 10l3-3" 
      strokeLinecap="round" 
      strokeLinejoin="round"
      opacity={direction === 'desc' ? 1 : 0.3}
    />
  </svg>
);

// Status badge config
const statusConfig: Record<ReviewStatus, { label: string; variant: 'success' | 'danger' | 'warning' | 'default'; icon: JSX.Element }> = {
  pending: { label: 'Pending', variant: 'default', icon: <span>-</span> },
  approved: { label: 'Approved', variant: 'success', icon: <CheckIcon /> },
  rejected: { label: 'Rejected', variant: 'danger', icon: <XIcon /> },
  maybe: { label: 'Maybe', variant: 'warning', icon: <QuestionIcon /> },
  needs_review: { label: 'Needs Review', variant: 'default', icon: <span>!</span> },
};

type SortField = 'company' | 'segment' | 'status' | 'score' | 'confidence';
type SortDirection = 'asc' | 'desc';
type FilterStatus = 'all' | 'reviewed' | ReviewStatus;

export function ReportTab({
  companies,
  getReview,
  onSelectCompany,
}: ReportTabProps) {
  const [filterStatus, setFilterStatus] = useState<FilterStatus>('all');
  const [sortField, setSortField] = useState<SortField>('score');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

  // Calculate stats
  const stats = useMemo(() => {
    let approved = 0;
    let rejected = 0;
    let maybe = 0;
    let pending = 0;

    companies.forEach(c => {
      const review = getReview(c.company);
      const status = review?.status || 'pending';
      if (status === 'approved') approved++;
      else if (status === 'rejected') rejected++;
      else if (status === 'maybe') maybe++;
      else pending++;
    });

    const reviewed = approved + rejected + maybe;
    const total = companies.length;
    const avgScore = companies.reduce((sum, c) => {
      const review = getReview(c.company);
      return sum + (review?.score || 0);
    }, 0) / (reviewed || 1);

    return { total, reviewed, approved, rejected, maybe, pending, avgScore };
  }, [companies, getReview]);

  // Filter and sort companies
  const filteredCompanies = useMemo(() => {
    let result = [...companies];

    // Status filter
    if (filterStatus !== 'all') {
      result = result.filter(c => {
        const review = getReview(c.company);
        const status = review?.status || 'pending';
        if (filterStatus === 'reviewed') {
          return status !== 'pending';
        }
        return status === filterStatus;
      });
    }

    // Sort
    result.sort((a, b) => {
      const reviewA = getReview(a.company);
      const reviewB = getReview(b.company);
      let comparison = 0;

      switch (sortField) {
        case 'company':
          comparison = a.company.localeCompare(b.company);
          break;
        case 'segment':
          comparison = (a.segment || '').localeCompare(b.segment || '');
          break;
        case 'status':
          const statusOrder = { approved: 1, maybe: 2, rejected: 3, pending: 4, needs_review: 5 };
          const statusA = reviewA?.status || 'pending';
          const statusB = reviewB?.status || 'pending';
          comparison = statusOrder[statusA] - statusOrder[statusB];
          break;
        case 'score':
          comparison = (reviewB?.score || 0) - (reviewA?.score || 0);
          break;
        case 'confidence':
          comparison = (b.confidence_0to1 || 0) - (a.confidence_0to1 || 0);
          break;
      }

      return sortDirection === 'asc' ? comparison : -comparison;
    });

    return result;
  }, [companies, filterStatus, sortField, sortDirection, getReview]);

  // Handle sort click
  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('desc');
    }
  };

  // Render score stars
  const renderScore = (score: number | undefined) => {
    if (!score) return <span className="report-tab__no-score">-</span>;
    return (
      <div className="report-tab__score-stars">
        {[1, 2, 3, 4, 5].map(s => (
          <span key={s} className={`report-tab__star ${s <= score ? 'report-tab__star--filled' : ''}`}>
            ★
          </span>
        ))}
      </div>
    );
  };

  return (
    <div className="report-tab">
      {/* Stats Summary */}
      <div className="report-tab__stats">
        <div className="report-tab__stat">
          <span className="report-tab__stat-value">{stats.total}</span>
          <span className="report-tab__stat-label">Total</span>
        </div>
        <div className="report-tab__stat report-tab__stat--reviewed">
          <span className="report-tab__stat-value">{stats.reviewed}</span>
          <span className="report-tab__stat-label">Reviewed</span>
        </div>
        <div className="report-tab__stat report-tab__stat--approved">
          <span className="report-tab__stat-value">{stats.approved}</span>
          <span className="report-tab__stat-label">Approved</span>
        </div>
        <div className="report-tab__stat report-tab__stat--rejected">
          <span className="report-tab__stat-value">{stats.rejected}</span>
          <span className="report-tab__stat-label">Rejected</span>
        </div>
        <div className="report-tab__stat report-tab__stat--maybe">
          <span className="report-tab__stat-value">{stats.maybe}</span>
          <span className="report-tab__stat-label">Maybe</span>
        </div>
        <div className="report-tab__stat">
          <span className="report-tab__stat-value">{stats.avgScore.toFixed(1)}</span>
          <span className="report-tab__stat-label">Avg Score</span>
        </div>
      </div>

      {/* Toolbar - filters only */}
      <div className="report-tab__toolbar">
        <div className="report-tab__filters">
          <select
            className="report-tab__select"
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value as FilterStatus)}
          >
            <option value="all">All Companies</option>
            <option value="reviewed">Reviewed Only</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="maybe">Maybe</option>
            <option value="pending">Pending</option>
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="report-tab__table-container">
        <table className="report-tab__table">
          <thead>
            <tr>
              <th onClick={() => handleSort('company')} className="report-tab__th--sortable">
                Company
                <SortIcon direction={sortField === 'company' ? sortDirection : null} />
              </th>
              <th onClick={() => handleSort('segment')} className="report-tab__th--sortable">
                Segment
                <SortIcon direction={sortField === 'segment' ? sortDirection : null} />
              </th>
              <th>Country</th>
              <th onClick={() => handleSort('status')} className="report-tab__th--sortable">
                Status
                <SortIcon direction={sortField === 'status' ? sortDirection : null} />
              </th>
              <th onClick={() => handleSort('score')} className="report-tab__th--sortable">
                Score
                <SortIcon direction={sortField === 'score' ? sortDirection : null} />
              </th>
              <th onClick={() => handleSort('confidence')} className="report-tab__th--sortable">
                Confidence
                <SortIcon direction={sortField === 'confidence' ? sortDirection : null} />
              </th>
              <th>Notes</th>
            </tr>
          </thead>
          <tbody>
            {filteredCompanies.length === 0 ? (
              <tr>
                <td colSpan={7} className="report-tab__empty">
                  No companies match your filters
                </td>
              </tr>
            ) : (
              filteredCompanies.map(company => {
                const review = getReview(company.company);
                const status = review?.status || 'pending';
                const config = statusConfig[status];

                return (
                  <tr
                    key={company.company}
                    className={`report-tab__row report-tab__row--${status}`}
                    onClick={() => onSelectCompany?.(company)}
                  >
                    <td className="report-tab__company-name">{company.company}</td>
                    <td>{company.segment || '-'}</td>
                    <td>{company.country || '-'}</td>
                    <td>
                      <Badge variant={config.variant} size="sm">
                        {config.icon}
                        {config.label}
                      </Badge>
                    </td>
                    <td>{renderScore(review?.score)}</td>
                    <td>
                      {company.confidence_0to1
                        ? `${Math.round(company.confidence_0to1 * 100)}%`
                        : '-'}
                    </td>
                    <td className="report-tab__notes">
                      {review?.notes ? (
                        <span title={review.notes}>
                          {review.notes.length > 50
                            ? review.notes.slice(0, 50) + '...'
                            : review.notes}
                        </span>
                      ) : '-'}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Footer */}
      <div className="report-tab__footer">
        <span className="report-tab__count">
          Showing {filteredCompanies.length} of {companies.length} companies
        </span>
      </div>
    </div>
  );
}

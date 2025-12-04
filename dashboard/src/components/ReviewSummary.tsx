import type { CompanyData } from './CompanyCard';
import type { CompanyReview } from '../types';
import { Button, Badge, Card, ProgressRing } from './ui';
import './ReviewSummary.css';

interface ReviewSummaryProps {
  stats: {
    total: number;
    reviewed: number;
    pending: number;
    approved: number;
    rejected: number;
    maybe: number;
    flagged: number;
    avgScore: number;
    percentComplete: number;
  };
  companies: CompanyData[];
  getReview: (company: string) => CompanyReview | undefined;
  onClose: () => void;
  onExport: () => void;
}

// Icons
const BackIcon = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M12 15l-5-5 5-5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const DownloadIcon = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M10 3v10m0 0l-3-3m3 3l3-3M4 17h12" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const CheckIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="12" cy="12" r="10" />
    <path d="M8 12l2.5 2.5L16 9" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const XCircleIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="12" cy="12" r="10" />
    <path d="M9 9l6 6M15 9l-6 6" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const QuestionCircleIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="12" cy="12" r="10" />
    <path d="M9 9a3 3 0 015 2c0 1.5-2 2-2 4M12 17h.01" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const StarIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
    <path d="M8 1.5l1.76 3.57 3.94.57-2.85 2.78.67 3.93L8 10.47l-3.52 1.88.67-3.93L2.3 5.64l3.94-.57L8 1.5z" />
  </svg>
);

export function ReviewSummary({
  stats,
  companies,
  getReview,
  onClose,
  onExport,
}: ReviewSummaryProps) {
  // Get approved companies for display
  const approvedCompanies = companies
    .filter(c => getReview(c.company)?.status === 'approved')
    .map(c => ({
      ...c,
      review: getReview(c.company)!,
    }))
    .sort((a, b) => (b.review.score || 0) - (a.review.score || 0));
  
  // Calculate segment breakdown
  const segmentStats: Record<string, { total: number; approved: number; rejected: number }> = {};
  companies.forEach(c => {
    const segment = c.segment || 'Unknown';
    if (!segmentStats[segment]) {
      segmentStats[segment] = { total: 0, approved: 0, rejected: 0 };
    }
    segmentStats[segment].total++;
    const review = getReview(c.company);
    if (review?.status === 'approved') segmentStats[segment].approved++;
    if (review?.status === 'rejected') segmentStats[segment].rejected++;
  });
  
  // Calculate score distribution
  const scoreDistribution = [0, 0, 0, 0, 0]; // Index 0-4 for scores 1-5
  companies.forEach(c => {
    const review = getReview(c.company);
    if (review?.score) {
      scoreDistribution[review.score - 1]++;
    }
  });
  const maxScoreCount = Math.max(...scoreDistribution, 1);
  
  return (
    <div className="review-summary">
      {/* Header */}
      <div className="review-summary__header">
        <Button variant="ghost" onClick={onClose}>
          <BackIcon />
          Back to Review
        </Button>
        <h1 className="review-summary__title">Review Summary</h1>
        <Button variant="primary" onClick={onExport}>
          <DownloadIcon />
          Export Approved (CSV)
        </Button>
      </div>
      
      {/* Stats cards */}
      <div className="review-summary__stats">
        <Card className="review-summary__stat-card review-summary__stat-card--progress">
          <div className="review-summary__stat-main">
            <ProgressRing progress={stats.percentComplete} size="xl" />
            <div>
              <span className="review-summary__stat-value">{stats.percentComplete}%</span>
              <span className="review-summary__stat-label">Complete</span>
            </div>
          </div>
          <p className="review-summary__stat-detail">
            {stats.reviewed} of {stats.total} companies reviewed
          </p>
        </Card>
        
        <Card className="review-summary__stat-card review-summary__stat-card--approved">
          <div className="review-summary__stat-icon review-summary__stat-icon--success">
            <CheckIcon />
          </div>
          <span className="review-summary__stat-value">{stats.approved}</span>
          <span className="review-summary__stat-label">Approved</span>
          <span className="review-summary__stat-percent">
            {stats.total > 0 ? Math.round((stats.approved / stats.total) * 100) : 0}%
          </span>
        </Card>
        
        <Card className="review-summary__stat-card review-summary__stat-card--rejected">
          <div className="review-summary__stat-icon review-summary__stat-icon--danger">
            <XCircleIcon />
          </div>
          <span className="review-summary__stat-value">{stats.rejected}</span>
          <span className="review-summary__stat-label">Rejected</span>
          <span className="review-summary__stat-percent">
            {stats.total > 0 ? Math.round((stats.rejected / stats.total) * 100) : 0}%
          </span>
        </Card>
        
        <Card className="review-summary__stat-card review-summary__stat-card--maybe">
          <div className="review-summary__stat-icon review-summary__stat-icon--warning">
            <QuestionCircleIcon />
          </div>
          <span className="review-summary__stat-value">{stats.maybe}</span>
          <span className="review-summary__stat-label">Maybe</span>
          <span className="review-summary__stat-percent">
            {stats.total > 0 ? Math.round((stats.maybe / stats.total) * 100) : 0}%
          </span>
        </Card>
      </div>
      
      <div className="review-summary__content">
        {/* Left column: Score distribution + Segment breakdown */}
        <div className="review-summary__column">
          {/* Score distribution */}
          <Card className="review-summary__section">
            <h3 className="review-summary__section-title">Score Distribution</h3>
            <div className="review-summary__score-chart">
              {scoreDistribution.map((count, index) => (
                <div key={index} className="review-summary__score-bar">
                  <div className="review-summary__score-label">
                    {index + 1} <StarIcon />
                  </div>
                  <div className="review-summary__score-track">
                    <div 
                      className="review-summary__score-fill"
                      style={{ width: `${(count / maxScoreCount) * 100}%` }}
                    />
                  </div>
                  <span className="review-summary__score-count">{count}</span>
                </div>
              ))}
            </div>
            {stats.avgScore > 0 && (
              <div className="review-summary__avg-score">
                Average Score: <strong>{stats.avgScore.toFixed(1)}</strong> / 5
              </div>
            )}
          </Card>
          
          {/* Segment breakdown */}
          <Card className="review-summary__section">
            <h3 className="review-summary__section-title">By Segment</h3>
            <div className="review-summary__segments">
              {Object.entries(segmentStats)
                .sort((a, b) => b[1].approved - a[1].approved)
                .map(([segment, data]) => (
                  <div key={segment} className="review-summary__segment">
                    <span className="review-summary__segment-name">
                      {formatSegment(segment)}
                    </span>
                    <div className="review-summary__segment-stats">
                      <Badge variant="success" size="sm">
                        {data.approved}
                      </Badge>
                      <Badge variant="danger" size="sm">
                        {data.rejected}
                      </Badge>
                      <span className="review-summary__segment-total">
                        / {data.total}
                      </span>
                    </div>
                  </div>
                ))}
            </div>
          </Card>
        </div>
        
        {/* Right column: Approved companies */}
        <div className="review-summary__column review-summary__column--wide">
          <Card className="review-summary__section">
            <div className="review-summary__section-header">
              <h3 className="review-summary__section-title">Approved Companies</h3>
              <Badge variant="success">{approvedCompanies.length}</Badge>
            </div>
            
            {approvedCompanies.length === 0 ? (
              <p className="review-summary__empty">
                No companies approved yet. Keep reviewing!
              </p>
            ) : (
              <div className="review-summary__approved-list">
                {approvedCompanies.map((c, index) => (
                  <div key={c.company} className="review-summary__approved-item">
                    <span className="review-summary__approved-rank">#{index + 1}</span>
                    <div className="review-summary__approved-info">
                      <span className="review-summary__approved-name">{c.company}</span>
                      {c.country && (
                        <span className="review-summary__approved-country">{c.country}</span>
                      )}
                    </div>
                    <div className="review-summary__approved-score">
                      {c.review.score ? (
                        <>
                          {c.review.score} <StarIcon />
                        </>
                      ) : (
                        <span className="review-summary__no-score">No score</span>
                      )}
                    </div>
                    {c.review.notes && (
                      <span className="review-summary__approved-notes">
                        {truncate(c.review.notes, 50)}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>
      
      {/* Data quality summary */}
      {stats.flagged > 0 && (
        <Card className="review-summary__quality">
          <h3 className="review-summary__section-title">Data Quality Issues</h3>
          <p className="review-summary__quality-text">
            <Badge variant="warning">{stats.flagged}</Badge> companies have data quality flags that may need attention.
          </p>
        </Card>
      )}
    </div>
  );
}

// Helpers
function formatSegment(segment: string): string {
  return segment
    .replace(/^\d+\.\s*/, '')
    .replace(/\s*\([^)]*\)/, '')
    .trim();
}

function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength).trim() + '...';
}


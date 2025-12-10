import { useState } from 'react';
import type { CompanyData } from './CompanyCard';
import type { CompanyReview, ReviewStatus, DataQualityFlag } from '../types';
import { Card, Badge, ConfidenceRing, CountryTag, SegmentTag } from './ui';
import './ReviewCard.css';

interface ReviewCardProps {
  company: CompanyData;
  review?: CompanyReview;
  isActive: boolean;
  isShortlisted: boolean;
  isCompareSelected: boolean;
  onSelect: () => void;
  onToggleShortlist: () => void;
  onToggleCompare: () => void;
  onApprove: () => void;
  onReject: () => void;
  onMaybe: () => void;
  onScoreChange: (score: number) => void;
  onEditData: () => void;
}

// Icons
const StarIcon = ({ filled }: { filled: boolean }) => (
  <svg width="18" height="18" viewBox="0 0 18 18" fill={filled ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.5">
    <path d="M9 1.5l2 4 4.5.65-3.25 3.16.77 4.5L9 11.67l-4 2.14.77-4.5L2.5 6.15 7 5.5 9 1.5z" />
  </svg>
);

const CheckIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M3 8l3 3 7-7" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const XIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M4 4l8 8M12 4L4 12" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const QuestionIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="8" cy="8" r="6" />
    <path d="M6 6a2 2 0 013 1.5c0 1-1.5 1.5-1.5 2.5M8 12h.01" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const CompareIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <rect x="1.5" y="2.5" width="5" height="11" rx="1" />
    <rect x="9.5" y="2.5" width="5" height="11" rx="1" />
  </svg>
);

const EditIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M11 2l3 3-9 9H2v-3l9-9z" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const WarningIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
    <path d="M7 1L13 12H1L7 1zM7 5v3M7 10h.01" stroke="currentColor" strokeWidth="1" strokeLinecap="round" />
  </svg>
);

// Status badge colors
const statusConfig: Record<ReviewStatus, { label: string; variant: 'success' | 'danger' | 'warning' | 'info' | 'default' }> = {
  pending: { label: 'Pending', variant: 'default' },
  approved: { label: 'Approved', variant: 'success' },
  rejected: { label: 'Rejected', variant: 'danger' },
  maybe: { label: 'Maybe', variant: 'warning' },
};

// Flag labels
const flagLabels: Record<DataQualityFlag, string> = {
  missing_website: 'No website',
  missing_financials: 'No financials',
  missing_team: 'No team data',
  missing_swot: 'No SWOT',
  low_confidence: 'Low confidence',
  incorrect_data: 'Data flagged',
};

export function ReviewCard({
  company,
  review,
  isActive,
  isShortlisted,
  isCompareSelected,
  onSelect,
  onToggleShortlist,
  onToggleCompare,
  onApprove,
  onReject,
  onMaybe,
  onScoreChange,
  onEditData,
}: ReviewCardProps) {
  const [showNotes, setShowNotes] = useState(false);
  
  const status = review?.status || 'pending';
  const score = review?.score || 0;
  const flags = review?.dataFlags || [];
  const confidence = company.confidence_0to1 ?? 0.5;
  
  // Funding info
  const fundingRounds = company.financial_enrichment?.funding_rounds || company.funding_rounds || [];
  const totalFunding = fundingRounds.reduce((sum, r) => sum + (r.amount || 0), 0);
  
  const formatFunding = (amount: number) => {
    if (amount >= 1000000) return `$${(amount / 1000000).toFixed(1)}M`;
    if (amount >= 1000) return `$${(amount / 1000).toFixed(0)}K`;
    return amount > 0 ? `$${amount}` : 'Undisclosed';
  };
  
  return (
    <Card
      hover
      selected={isActive}
      className={`review-card ${isActive ? 'review-card--active' : ''} review-card--${status}`}
      onClick={onSelect}
    >
      <div className="review-card__content">
        {/* Left: Company info */}
        <div className="review-card__info">
          {/* Header row */}
          <div className="review-card__header">
            <button
              className={`review-card__star ${isShortlisted ? 'review-card__star--active' : ''}`}
              onClick={(e) => { e.stopPropagation(); onToggleShortlist(); }}
              aria-label={isShortlisted ? 'Remove from shortlist' : 'Add to shortlist'}
            >
              <StarIcon filled={isShortlisted} />
            </button>
            <h3 className="review-card__name">{company.company}</h3>
            <Badge variant={statusConfig[status].variant} size="sm">
              {statusConfig[status].label}
            </Badge>
          </div>
          
          {/* Tags row */}
          <div className="review-card__tags">
            {company.country && <CountryTag country={company.country} />}
            {company.segment && <SegmentTag segment={company.segment} />}
          </div>
          
          {/* Summary */}
          {company.summary && (
            <p className="review-card__summary">
              {truncate(company.summary, 120)}
            </p>
          )}
          
          {/* Metrics row */}
          <div className="review-card__metrics">
            <div className="review-card__metric">
              <ConfidenceRing confidence={confidence} size="sm" />
              <span>{Math.round(confidence * 100)}%</span>
            </div>
            <div className="review-card__metric">
              <span className="review-card__metric-label">Team</span>
              <span>{company.team?.size || 'Unknown'}</span>
            </div>
            <div className="review-card__metric">
              <span className="review-card__metric-label">Funding</span>
              <span>{formatFunding(totalFunding)}</span>
            </div>
          </div>
          
          {/* Data quality flags */}
          {flags.length > 0 && (
            <div className="review-card__flags">
              {flags.map(flag => (
                <span key={flag} className="review-card__flag">
                  <WarningIcon />
                  {flagLabels[flag]}
                </span>
              ))}
            </div>
          )}
          
          {/* Notes preview */}
          {review?.notes && (
            <div className="review-card__notes-preview">
              <strong>Notes:</strong> {truncate(review.notes, 80)}
            </div>
          )}
        </div>
        
        {/* Right: Actions */}
        <div className="review-card__actions">
          {/* Score */}
          <div className="review-card__score">
            <span className="review-card__score-label">Score</span>
            <div className="review-card__score-stars">
              {[1, 2, 3, 4, 5].map(s => (
                <button
                  key={s}
                  className={`review-card__score-star ${score >= s ? 'review-card__score-star--filled' : ''}`}
                  onClick={(e) => { e.stopPropagation(); onScoreChange(s); }}
                  aria-label={`Rate ${s} out of 5`}
                >
                  <StarIcon filled={score >= s} />
                </button>
              ))}
            </div>
          </div>
          
          {/* Quick actions */}
          <div className="review-card__quick-actions">
            <button
              className={`review-card__action review-card__action--approve ${status === 'approved' ? 'review-card__action--active' : ''}`}
              onClick={(e) => { e.stopPropagation(); onApprove(); }}
              aria-label="Approve"
              title="Approve"
            >
              <CheckIcon />
            </button>
            <button
              className={`review-card__action review-card__action--reject ${status === 'rejected' ? 'review-card__action--active' : ''}`}
              onClick={(e) => { e.stopPropagation(); onReject(); }}
              aria-label="Reject"
              title="Reject"
            >
              <XIcon />
            </button>
            <button
              className={`review-card__action review-card__action--maybe ${status === 'maybe' ? 'review-card__action--active' : ''}`}
              onClick={(e) => { e.stopPropagation(); onMaybe(); }}
              aria-label="Maybe"
              title="Maybe"
            >
              <QuestionIcon />
            </button>
          </div>
          
          {/* Secondary actions */}
          <div className="review-card__secondary-actions">
            <button
              className={`review-card__secondary ${isCompareSelected ? 'review-card__secondary--active' : ''}`}
              onClick={(e) => { e.stopPropagation(); onToggleCompare(); }}
              aria-label={isCompareSelected ? 'Remove from compare' : 'Add to compare'}
              title="Compare"
            >
              <CompareIcon />
            </button>
            <button
              className="review-card__secondary"
              onClick={(e) => { e.stopPropagation(); onEditData(); }}
              aria-label="Edit data"
              title="Edit data"
            >
              <EditIcon />
            </button>
          </div>
        </div>
      </div>
    </Card>
  );
}

// Helpers
function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength).trim() + '...';
}


import type { ReviewStatus } from '../types';
import { Card, SegmentTag, CountryTag, ConfidenceRing, SwotDots, Badge } from './ui';
import './CompanyCard.css';

// Company data type (matches deep research JSON structure)
export interface CompanyData {
  company: string;
  summary?: string;
  website?: string;
  country?: string;
  segment?: string;
  confidence_0to1?: number;
  deep_research_status?: string;
  team?: {
    founders?: Array<{ name: string; background?: string }>;
    executives?: Array<{ title: string; name: string }>;
    size?: string;
  };
  funding_rounds?: Array<{
    round_type: string;
    amount?: number;
    currency?: string;
    investors?: string[];
  }>;
  financial_enrichment?: {
    entity_classification?: {
      likely_sector?: string;
      is_listed?: boolean;
    };
    funding_rounds?: Array<{
      round_type: string;
      amount?: number;
      currency?: string;
      investors?: string[];
    }>;
  };
  swot?: {
    strengths?: string[];
    weaknesses?: string[];
    opportunities?: string[];
    threats?: string[];
  };
  evidence_of_impact?: {
    case_studies?: string[];
    awards?: string[];
    academic_papers?: string[];
  };
  competitors?: {
    direct?: Array<{ name: string; description?: string }>;
    differentiation?: string;
  };
  key_clients?: Array<{
    name: string;
    geographic_market?: string;
    notable_reference?: string;
  }>;
  kpi_alignment?: string[];
  sources?: string[];
}

interface CompanyCardProps {
  company: CompanyData;
  isShortlisted: boolean;
  isSelected: boolean;
  isCompareSelected: boolean;
  onToggleShortlist: () => void;
  onSelect: () => void;
  onToggleCompare: () => void;
  allSegments?: string[]; // All value chain segments this company appears in
  reviewStatus?: ReviewStatus; // Review status for visual indicator
}

// Star icon
const StarIcon = ({ filled }: { filled: boolean }) => (
  <svg 
    width="20" 
    height="20" 
    viewBox="0 0 20 20" 
    fill={filled ? "currentColor" : "none"} 
    stroke="currentColor" 
    strokeWidth="1.5"
  >
    <path d="M10 2.5l2.2 4.46 4.93.72-3.57 3.48.84 4.92L10 13.71l-4.4 2.37.84-4.92-3.57-3.48 4.93-.72L10 2.5z" />
  </svg>
);

// Compare checkbox icon
const CheckboxIcon = ({ checked }: { checked: boolean }) => (
  <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
    <rect 
      x="1" y="1" width="16" height="16" rx="4" 
      stroke="currentColor" 
      strokeWidth="1.5"
      fill={checked ? "var(--color-primary)" : "none"}
    />
    {checked && (
      <path 
        d="M5 9l2.5 2.5L13 6" 
        stroke="white" 
        strokeWidth="2" 
        strokeLinecap="round" 
        strokeLinejoin="round"
      />
    )}
  </svg>
);

// Multi-segment icon
const MultiSegmentIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="4" cy="7" r="2" />
    <circle cx="10" cy="4" r="2" />
    <circle cx="10" cy="10" r="2" />
    <path d="M6 7h2M6 6l2-1M6 8l2 1" strokeLinecap="round" />
  </svg>
);

// Warning icon for missing data
const WarningIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M7 4.5v3M7 9.5h.01" strokeLinecap="round" />
    <path d="M6.36 1.64L1.36 10.5a.75.75 0 00.64 1.14h10a.75.75 0 00.64-1.14L7.64 1.64a.75.75 0 00-1.28 0z" />
  </svg>
);

// Review status icons
const ReviewCheckIcon = () => (
  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M2 6l3 3 5-6" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const ReviewXIcon = () => (
  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M2 2l8 8M10 2L2 10" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const ReviewMaybeIcon = () => (
  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="6" cy="6" r="4.5" />
    <path d="M4.5 4.5a1.5 1.5 0 012.25 1.13c0 .75-1.12 1.12-1.12 1.87M6 9h.01" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

// Review status config
const reviewStatusConfig: Record<ReviewStatus, { icon: JSX.Element; variant: 'success' | 'danger' | 'warning' | 'default' }> = {
  pending: { icon: <span>-</span>, variant: 'default' },
  approved: { icon: <ReviewCheckIcon />, variant: 'success' },
  rejected: { icon: <ReviewXIcon />, variant: 'danger' },
  maybe: { icon: <ReviewMaybeIcon />, variant: 'warning' },
  needs_review: { icon: <span>!</span>, variant: 'default' },
};

// Field checks for missing data detection
const FIELD_CHECKS = [
  { key: 'website', check: (c: CompanyData) => !!c.website && c.website.length > 0 },
  { key: 'team', check: (c: CompanyData) => !!(c.team?.founders?.length || c.team?.executives?.length || c.team?.size) },
  { key: 'swot', check: (c: CompanyData) => !!(c.swot?.strengths?.length || c.swot?.weaknesses?.length) },
  { key: 'funding', check: (c: CompanyData) => !!(c.funding_rounds?.length || c.financial_enrichment?.funding_rounds?.length) },
];

export function CompanyCard({
  company,
  isShortlisted,
  isSelected,
  isCompareSelected,
  onToggleShortlist,
  onSelect,
  onToggleCompare,
  allSegments = [],
  reviewStatus,
}: CompanyCardProps) {
  const confidence = company.confidence_0to1 ?? 0.5;
  const swot = company.swot || {};
  
  // Get funding info
  const fundingRounds = company.financial_enrichment?.funding_rounds || company.funding_rounds || [];
  const latestFunding = fundingRounds[0];
  const totalFunding = fundingRounds.reduce((sum, r) => sum + (r.amount || 0), 0);
  
  // Get team info
  const team = company.team;
  const founderCount = team?.founders?.length || 0;
  const teamSize = team?.size || 'Unknown';
  
  // Get sector
  const sector = company.financial_enrichment?.entity_classification?.likely_sector || '';
  
  // Get evidence counts
  const evidence = company.evidence_of_impact || {};
  const caseStudyCount = evidence.case_studies?.length || 0;
  const awardCount = evidence.awards?.length || 0;
  
  // Count missing data fields
  const missingCount = FIELD_CHECKS.filter(f => !f.check(company)).length;
  
  // Format funding amount
  const formatFunding = (amount: number, currency = 'USD') => {
    if (amount >= 1000000) {
      return `$${(amount / 1000000).toFixed(1)}M`;
    } else if (amount >= 1000) {
      return `$${(amount / 1000).toFixed(0)}K`;
    }
    return `$${amount}`;
  };

  return (
    <Card 
      hover 
      selected={isSelected}
      className={`company-card ${isCompareSelected ? 'company-card--compare' : ''}`}
      onClick={onSelect}
    >
      {/* Header */}
      <div className="company-card__header">
        <div className="company-card__header-row">
          <button 
            className={`company-card__star ${isShortlisted ? 'company-card__star--active' : ''}`}
            onClick={(e) => { e.stopPropagation(); onToggleShortlist(); }}
            aria-label={isShortlisted ? 'Remove from shortlist' : 'Add to shortlist'}
          >
            <StarIcon filled={isShortlisted} />
          </button>
          <h3 className="company-card__name">{company.company}</h3>
          {/* Review Status Badge */}
          {reviewStatus && reviewStatus !== 'pending' && (
            <div className={`company-card__review-badge company-card__review-badge--${reviewStatus}`}>
              {reviewStatusConfig[reviewStatus].icon}
            </div>
          )}
        </div>
        <div className="company-card__tags">
          {company.country && <CountryTag country={company.country} />}
          {company.segment && <SegmentTag segment={company.segment} />}
          {sector && (
            <Badge variant="default">
              {formatSector(sector)}
            </Badge>
          )}
          {allSegments.length > 1 && (
            <div className="company-card__multi-segment" title={`Appears in: ${allSegments.join(', ')}`}>
              <MultiSegmentIcon />
              <span>{allSegments.length} chains</span>
            </div>
          )}
        </div>
      </div>

      {/* Key Metrics Row */}
      <div className="company-card__metrics">
        <div className="company-card__metric">
          <span className="company-card__metric-label">Team</span>
          <span className="company-card__metric-value">{teamSize}</span>
          <span className="company-card__metric-sub">
            {founderCount > 0 ? `${founderCount} founder${founderCount > 1 ? 's' : ''}` : ''}
          </span>
        </div>
        <div className="company-card__metric">
          <span className="company-card__metric-label">Funding</span>
          <span className="company-card__metric-value">
            {totalFunding > 0 ? formatFunding(totalFunding) : 'Undisclosed'}
          </span>
          <span className="company-card__metric-sub">
            {latestFunding?.round_type || ''}
          </span>
        </div>
      </div>

      {/* Traction */}
      {company.summary && (
        <div className="company-card__traction">
          <span className="company-card__traction-label">Traction</span>
          <p className="company-card__traction-text">
            "{truncate(company.summary, 100)}"
          </p>
          <div className="company-card__traction-stats">
            {caseStudyCount > 0 && (
              <span>{caseStudyCount} case stud{caseStudyCount === 1 ? 'y' : 'ies'}</span>
            )}
            {awardCount > 0 && (
              <span>{awardCount} award{awardCount === 1 ? '' : 's'}</span>
            )}
          </div>
        </div>
      )}

      {/* SWOT Summary */}
      <div className="company-card__swot">
        <span className="company-card__swot-label">SWOT</span>
        <div className="company-card__swot-grid">
          <div className="company-card__swot-item">
            <SwotDots count={swot.strengths?.length || 0} variant="strength" />
            <span>Strengths</span>
          </div>
          <div className="company-card__swot-item">
            <SwotDots count={swot.weaknesses?.length || 0} variant="weakness" />
            <span>Weaknesses</span>
          </div>
          <div className="company-card__swot-item">
            <SwotDots count={swot.opportunities?.length || 0} variant="opportunity" />
            <span>Opportunities</span>
          </div>
          <div className="company-card__swot-item">
            <SwotDots count={swot.threats?.length || 0} variant="threat" />
            <span>Threats</span>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="company-card__footer">
        <div className="company-card__confidence">
          <ConfidenceRing confidence={confidence} size="sm" />
          <span className="company-card__confidence-label">Confidence</span>
        </div>
        {missingCount > 0 && (
          <div className="company-card__missing-data" title={`${missingCount} field${missingCount > 1 ? 's' : ''} missing`}>
            <WarningIcon />
            <span className="company-card__missing-count">{missingCount}</span>
          </div>
        )}
        <button 
          className={`company-card__compare ${isCompareSelected ? 'company-card__compare--active' : ''}`}
          onClick={(e) => { e.stopPropagation(); onToggleCompare(); }}
          aria-label={isCompareSelected ? 'Remove from comparison' : 'Add to comparison'}
        >
          <CheckboxIcon checked={isCompareSelected} />
          <span>Compare</span>
        </button>
      </div>
    </Card>
  );
}

// Helpers
function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength).trim() + '...';
}

function formatSector(sector: string): string {
  return sector
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}


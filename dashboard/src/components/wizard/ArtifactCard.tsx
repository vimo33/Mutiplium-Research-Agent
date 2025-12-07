import { useState } from 'react';
import type { KPI, ValueChainSegment } from '../../types';
import './ArtifactCard.css';

interface ThesisCardProps {
  type: 'thesis';
  title: string;
  content: string;
  items?: never;
  onEdit?: (content: string) => void;
}

interface KPICardProps {
  type: 'kpis';
  title: string;
  content?: never;
  items: KPI[];
  onEdit?: (items: KPI[]) => void;
}

interface ValueChainCardProps {
  type: 'valueChain';
  title: string;
  content?: never;
  items: ValueChainSegment[];
  onEdit?: (items: ValueChainSegment[]) => void;
}

type ArtifactCardProps = ThesisCardProps | KPICardProps | ValueChainCardProps;

// Chevron icon for expand/collapse
function ChevronIcon({ expanded }: { expanded: boolean }) {
  return (
    <svg 
      width="16" 
      height="16" 
      viewBox="0 0 24 24" 
      fill="none" 
      stroke="currentColor" 
      strokeWidth="2"
      className={`artifact-card__chevron ${expanded ? 'artifact-card__chevron--expanded' : ''}`}
    >
      <path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// Icon for artifact type
function ArtifactIcon({ type }: { type: 'thesis' | 'kpis' | 'valueChain' }) {
  switch (type) {
    case 'thesis':
      return (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <path d="M14 2v6h6" />
          <path d="M16 13H8M16 17H8M10 9H8" />
        </svg>
      );
    case 'kpis':
      return (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 20V10M18 20V4M6 20v-4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    case 'valueChain':
      return (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20" />
          <path d="M2 12h20" />
        </svg>
      );
  }
}

export function ArtifactCard(props: ArtifactCardProps) {
  const [expanded, setExpanded] = useState(true);
  const { type, title } = props;

  const getTypeLabel = () => {
    switch (type) {
      case 'thesis': return 'Thesis';
      case 'kpis': return 'KPIs';
      case 'valueChain': return 'Value Chain';
    }
  };

  const getTypeColor = () => {
    switch (type) {
      case 'thesis': return 'var(--artifact-thesis)';
      case 'kpis': return 'var(--artifact-kpi)';
      case 'valueChain': return 'var(--artifact-segment)';
    }
  };

  return (
    <div className={`artifact-card artifact-card--${type}`} style={{ '--accent-color': getTypeColor() } as React.CSSProperties}>
      <button 
        className="artifact-card__header"
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
      >
        <div className="artifact-card__header-left">
          <span className="artifact-card__icon">
            <ArtifactIcon type={type} />
          </span>
          <span className="artifact-card__type">{getTypeLabel()}</span>
          <span className="artifact-card__title">{title}</span>
        </div>
        <ChevronIcon expanded={expanded} />
      </button>

      {expanded && (
        <div className="artifact-card__content">
          {type === 'thesis' && (
            <div className="artifact-card__thesis">
              {props.content.split('\n\n').map((paragraph, idx) => (
                <p key={idx}>{paragraph}</p>
              ))}
            </div>
          )}

          {type === 'kpis' && (
            <div className="artifact-card__kpis">
              {props.items.map((kpi, idx) => (
                <div key={idx} className="artifact-card__kpi">
                  <div className="artifact-card__kpi-header">
                    <span className="artifact-card__kpi-name">{kpi.name}</span>
                    {kpi.target && (
                      <span className="artifact-card__kpi-target">{kpi.target}</span>
                    )}
                  </div>
                  {kpi.rationale && (
                    <p className="artifact-card__kpi-rationale">{kpi.rationale}</p>
                  )}
                </div>
              ))}
            </div>
          )}

          {type === 'valueChain' && (
            <div className="artifact-card__segments">
              {props.items.map((segment, idx) => (
                <div key={idx} className="artifact-card__segment">
                  <div className="artifact-card__segment-number">{idx + 1}</div>
                  <div className="artifact-card__segment-content">
                    <span className="artifact-card__segment-name">{segment.segment}</span>
                    {segment.description && (
                      <p className="artifact-card__segment-desc">{segment.description}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Summary card for displaying aggregated artifacts in a compact form
interface ArtifactSummaryProps {
  thesis?: string;
  kpis: KPI[];
  valueChain: ValueChainSegment[];
  onViewDetails?: () => void;
}

export function ArtifactSummary({ thesis, kpis, valueChain, onViewDetails }: ArtifactSummaryProps) {
  const hasThesis = !!thesis;
  const kpiCount = kpis.length;
  const segmentCount = valueChain.length;

  return (
    <div className="artifact-summary">
      <div className="artifact-summary__header">
        <h4>Generated Framework</h4>
        {onViewDetails && (
          <button className="artifact-summary__view-btn" onClick={onViewDetails}>
            View Details
          </button>
        )}
      </div>
      
      <div className="artifact-summary__items">
        <div className={`artifact-summary__item ${hasThesis ? 'artifact-summary__item--complete' : ''}`}>
          <ArtifactIcon type="thesis" />
          <span>Investment Thesis</span>
          <span className="artifact-summary__status">
            {hasThesis ? '✓' : '○'}
          </span>
        </div>
        
        <div className={`artifact-summary__item ${kpiCount >= 3 ? 'artifact-summary__item--complete' : ''}`}>
          <ArtifactIcon type="kpis" />
          <span>{kpiCount} KPIs</span>
          <span className="artifact-summary__status">
            {kpiCount >= 3 ? '✓' : `${kpiCount}/3`}
          </span>
        </div>
        
        <div className={`artifact-summary__item ${segmentCount >= 3 ? 'artifact-summary__item--complete' : ''}`}>
          <ArtifactIcon type="valueChain" />
          <span>{segmentCount} Segments</span>
          <span className="artifact-summary__status">
            {segmentCount >= 3 ? '✓' : `${segmentCount}/3`}
          </span>
        </div>
      </div>
    </div>
  );
}


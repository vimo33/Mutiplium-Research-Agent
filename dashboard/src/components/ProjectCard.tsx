import { useEffect, useState } from 'react';
import type { Project, ProjectCost } from '../types';
import { Card, Badge, ProgressRing, Button } from './ui';
import { fetchProjectCost } from '../api';
import './ProjectCard.css';

interface ProjectCardProps {
  project: Project;
  onSelect: () => void;
  onReview: () => void;
  onArchive?: () => void;
  onUnarchive?: () => void;
  onDelete?: () => void;
}

// Status badge mapping
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

// Icons
const ClientIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M8 2v12M2 8h12M4 4l8 8M12 4L4 12" strokeLinecap="round" />
  </svg>
);

const CompanyIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <rect x="2" y="3" width="12" height="11" rx="1" />
    <path d="M5 7h6M5 10h4" strokeLinecap="round" />
  </svg>
);

const CalendarIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <rect x="2" y="3" width="12" height="11" rx="1" />
    <path d="M2 6h12M5 1v3M11 1v3" strokeLinecap="round" />
  </svg>
);

const ChevronRightIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M6 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const ArchiveIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M2 4h12M2 4v9a1 1 0 001 1h10a1 1 0 001-1V4M6 7h4" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M4 4V3a1 1 0 011-1h6a1 1 0 011 1v1" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const RestoreIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M2 8a6 6 0 1011.5-2.5" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M14 2v4h-4" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const DollarIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M8 1v14M11 4H6.5a2.5 2.5 0 000 5h3a2.5 2.5 0 010 5H5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

function formatCost(cost: number): string {
  if (cost === 0) return '$0.00';
  if (cost < 0.01) return '<$0.01';
  return `$${cost.toFixed(2)}`;
}

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function formatTime(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
  });
}

export function ProjectCard({ project, onSelect, onReview, onArchive, onUnarchive, onDelete }: ProjectCardProps) {
  const { label: statusLabel, variant: statusVariant } = statusConfig[project.status] || statusConfig.draft;
  const [cost, setCost] = useState<number | null>(null);
  
  // Fetch project cost
  useEffect(() => {
    let cancelled = false;
    
    // Skip legacy/imported projects that don't exist in the API
    if (!project.id.startsWith('legacy_')) {
      fetchProjectCost(project.id)
        .then((data) => {
          if (!cancelled) {
            setCost(data.total_cost);
          }
        })
        .catch(() => {
          // Ignore errors - cost display is optional
        });
    }
    
    return () => {
      cancelled = true;
    };
  }, [project.id]);
  
  // Calculate review progress
  const { totalCompanies, approved, rejected, maybe, pending } = project.stats;
  const reviewed = approved + rejected + maybe;
  const reviewProgress = totalCompanies > 0 ? Math.round((reviewed / totalCompanies) * 100) : 0;
  
  // Determine primary action
  const showReviewButton = project.status === 'ready_for_review' && pending > 0;
  const showApproveButton = project.status === 'pending_approval';
  
  return (
    <Card className="project-card" onClick={onSelect}>
      {/* Status indicator */}
      <div className={`project-card__status-bar project-card__status-bar--${project.status}`} />
      
      {/* Header */}
      <div className="project-card__header">
        <div className="project-card__title-row">
          <div className="project-card__title-group">
            <h3 className="project-card__title">{project.projectName}</h3>
            <Badge variant={statusVariant} size="sm">{statusLabel}</Badge>
          </div>
          {onArchive && (
            <button
              className="project-card__archive-btn"
              onClick={(e) => {
                e.stopPropagation();
                onArchive();
              }}
              title="Archive project"
            >
              <ArchiveIcon />
            </button>
          )}
          {onUnarchive && (
            <button
              className="project-card__archive-btn project-card__archive-btn--restore"
              onClick={(e) => {
                e.stopPropagation();
                onUnarchive();
              }}
              title="Restore project"
            >
              <RestoreIcon />
            </button>
          )}
        </div>
        
        <div className="project-card__client">
          <ClientIcon />
          <span>{project.clientName}</span>
        </div>
      </div>
      
      {/* Stats Grid */}
      <div className="project-card__stats">
        <div className="project-card__stat">
          <CompanyIcon />
          <span className="project-card__stat-value">{totalCompanies}</span>
          <span className="project-card__stat-label">companies</span>
        </div>
        
        {totalCompanies > 0 && (
          <>
            <div className="project-card__stat project-card__stat--approved">
              <span className="project-card__stat-value">{approved}</span>
              <span className="project-card__stat-label">approved</span>
            </div>
            <div className="project-card__stat project-card__stat--rejected">
              <span className="project-card__stat-value">{rejected}</span>
              <span className="project-card__stat-label">rejected</span>
            </div>
            <div className="project-card__stat project-card__stat--pending">
              <span className="project-card__stat-value">{pending}</span>
              <span className="project-card__stat-label">pending</span>
            </div>
          </>
        )}
        
        {/* Cost indicator */}
        {cost !== null && cost > 0 && (
          <div className="project-card__stat project-card__stat--cost" title="Total API cost for this project">
            <DollarIcon />
            <span className="project-card__stat-value">{formatCost(cost)}</span>
            <span className="project-card__stat-label">API cost</span>
          </div>
        )}
      </div>
      
      {/* Progress */}
      {totalCompanies > 0 && (
        <div className="project-card__progress">
          <div className="project-card__progress-bar">
            <div 
              className="project-card__progress-fill"
              style={{ width: `${reviewProgress}%` }}
            />
          </div>
          <span className="project-card__progress-text">
            {reviewProgress}% reviewed
          </span>
        </div>
      )}
      
      {/* Value Chain Preview */}
      {project.framework.valueChain.length > 0 && (
        <div className="project-card__segments">
          {project.framework.valueChain.slice(0, 4).map((vc, i) => (
            <Badge key={i} variant="default" size="sm">
              {vc.segment}
            </Badge>
          ))}
          {project.framework.valueChain.length > 4 && (
            <Badge variant="default" size="sm">
              +{project.framework.valueChain.length - 4}
            </Badge>
          )}
        </div>
      )}
      
      {/* Footer */}
      <div className="project-card__footer">
        <div className="project-card__date">
          <CalendarIcon />
          <span>{formatDate(project.createdAt)} at {formatTime(project.createdAt)}</span>
        </div>
        
        <div className="project-card__actions">
          {showReviewButton && (
            <Button 
              variant="primary" 
              size="sm"
              onClick={(e) => {
                e.stopPropagation();
                onReview();
              }}
            >
              Review ({pending})
            </Button>
          )}
          {showApproveButton && (
            <Button 
              variant="success" 
              size="sm"
              onClick={(e) => {
                e.stopPropagation();
                onSelect();
              }}
            >
              Approve Test Run
            </Button>
          )}
          <button 
            className="project-card__details-btn"
            onClick={(e) => {
              e.stopPropagation();
              onSelect();
            }}
          >
            Details
            <ChevronRightIcon />
          </button>
        </div>
      </div>
    </Card>
  );
}


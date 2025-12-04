import type { Project } from '../types';
import { Card, Badge, ProgressRing, Button } from './ui';
import './ProjectCard.css';

interface ProjectCardProps {
  project: Project;
  onSelect: () => void;
  onReview: () => void;
  onDelete?: () => void;
}

// Status badge mapping
const statusConfig: Record<string, { label: string; variant: 'default' | 'primary' | 'success' | 'warning' | 'danger' }> = {
  draft: { label: 'Draft', variant: 'default' },
  test_run: { label: 'Test Run', variant: 'primary' },
  pending_approval: { label: 'Pending Approval', variant: 'warning' },
  researching: { label: 'Researching', variant: 'primary' },
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

export function ProjectCard({ project, onSelect, onReview, onDelete }: ProjectCardProps) {
  const { label: statusLabel, variant: statusVariant } = statusConfig[project.status] || statusConfig.draft;
  
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
        <div className="project-card__title-group">
          <h3 className="project-card__title">{project.projectName}</h3>
          <Badge variant={statusVariant} size="sm">{statusLabel}</Badge>
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


import { useState, useMemo } from 'react';
import type { Project, ProjectStatus } from '../types';
import { ProjectCard } from './ProjectCard';
import { Button, Badge, SearchInput } from './ui';
import './ProjectsView.css';

interface ProjectsViewProps {
  projects: Project[];
  isLoading?: boolean;
  error?: string | null;
  onSelectProject: (project: Project) => void;
  onReviewProject: (project: Project) => void;
  onNewProject: () => void;
  onArchiveProject?: (projectId: string) => void;
  onUnarchiveProject?: (projectId: string) => void;
  onDeleteProject?: (projectId: string) => void;
  isArchivedView?: boolean;
}

// Filter options
type FilterOption = 'all' | 'needs_review' | 'in_progress' | 'completed';

const filterConfig: Record<FilterOption, { label: string; statuses: ProjectStatus[] }> = {
  all: { label: 'All Projects', statuses: [] },
  needs_review: { 
    label: 'Needs Review', 
    statuses: ['ready_for_review', 'pending_approval', 'discovery_complete'] 
  },
  in_progress: { 
    label: 'In Progress', 
    statuses: ['draft', 'test_run', 'researching', 'deep_researching', 'discovery_failed'] 
  },
  completed: { 
    label: 'Completed', 
    statuses: ['completed'] 
  },
};

// Icons
const PlusIcon = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M10 4v12M4 10h12" strokeLinecap="round" />
  </svg>
);

const FolderIcon = () => (
  <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M6 12v28a2 2 0 002 2h32a2 2 0 002-2V18a2 2 0 00-2-2H24l-4-4H8a2 2 0 00-2 2z" />
  </svg>
);

// Loading spinner
const LoadingSpinner = () => (
  <div className="projects-view__loading">
    <div className="projects-view__spinner" />
    <p>Loading projects from reports...</p>
  </div>
);

export function ProjectsView({
  projects,
  isLoading = false,
  error,
  onSelectProject,
  onReviewProject,
  onNewProject,
  onArchiveProject,
  onUnarchiveProject,
  onDeleteProject,
  isArchivedView = false,
}: ProjectsViewProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState<FilterOption>('all');

  // Filter projects: show those with 50+ companies OR in active workflow states
  const successfulProjects = useMemo(() => {
    return projects.filter(p => 
      p.stats.totalCompanies >= 50 || 
      ['draft', 'test_run', 'pending_approval', 'researching', 'discovery_complete', 'discovery_failed', 'deep_researching', 'ready_for_review'].includes(p.status)
    );
  }, [projects]);

  // Apply filters
  const filteredProjects = useMemo(() => {
    let result = successfulProjects;

    // Status filter
    if (activeFilter !== 'all') {
      const { statuses } = filterConfig[activeFilter];
      result = result.filter(p => statuses.includes(p.status));
    }

    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter(p =>
        p.projectName.toLowerCase().includes(query) ||
        p.clientName.toLowerCase().includes(query) ||
        p.brief.objective.toLowerCase().includes(query)
      );
    }

    // Sort by most recent
    return result.sort((a, b) => 
      new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
    );
  }, [successfulProjects, activeFilter, searchQuery]);

  // Calculate summary stats
  const summaryStats = useMemo(() => {
    const total = successfulProjects.length;
    const totalCompanies = successfulProjects.reduce((sum, p) => sum + p.stats.totalCompanies, 0);
    const reviewed = successfulProjects.reduce((sum, p) => 
      sum + p.stats.approved + p.stats.rejected + p.stats.maybe, 0
    );
    const needsReview = successfulProjects.filter(p => 
      p.status === 'ready_for_review' || p.status === 'pending_approval'
    ).length;
    
    return { total, totalCompanies, reviewed, needsReview };
  }, [successfulProjects]);

  // Filter counts
  const filterCounts = useMemo(() => ({
    all: successfulProjects.length,
    needs_review: successfulProjects.filter(p => 
      ['ready_for_review', 'pending_approval', 'discovery_complete'].includes(p.status)
    ).length,
    in_progress: successfulProjects.filter(p => 
      ['draft', 'test_run', 'researching', 'deep_researching', 'discovery_failed'].includes(p.status)
    ).length,
    completed: successfulProjects.filter(p => p.status === 'completed').length,
  }), [successfulProjects]);

  return (
    <div className="projects-view">
      {/* Header */}
      <div className="projects-view__header">
        <div className="projects-view__header-left">
          <h1 className="projects-view__title">
            {isArchivedView ? 'Archived Projects' : 'Research Projects'}
          </h1>
          <p className="projects-view__subtitle">
            {isArchivedView 
              ? 'View and restore previously archived research projects'
              : 'Manage your investment research across sectors and clients'}
          </p>
        </div>
        {!isArchivedView && (
          <Button variant="primary" onClick={onNewProject} icon={<PlusIcon />}>
            New Research
          </Button>
        )}
      </div>

      {/* Summary Stats */}
      {summaryStats.total > 0 && (
        <div className="projects-view__summary">
          <div className="projects-view__summary-stat">
            <span className="projects-view__summary-value">{summaryStats.total}</span>
            <span className="projects-view__summary-label">projects</span>
          </div>
          <div className="projects-view__summary-divider" />
          <div className="projects-view__summary-stat">
            <span className="projects-view__summary-value">{summaryStats.totalCompanies.toLocaleString()}</span>
            <span className="projects-view__summary-label">companies</span>
          </div>
          <div className="projects-view__summary-divider" />
          {summaryStats.needsReview > 0 && (
            <>
              <div className="projects-view__summary-stat projects-view__summary-stat--highlight">
                <span className="projects-view__summary-value">{summaryStats.needsReview}</span>
                <span className="projects-view__summary-label">needs review</span>
              </div>
              <div className="projects-view__summary-divider" />
            </>
          )}
          <div className="projects-view__summary-stat">
            <span className="projects-view__summary-value">{summaryStats.reviewed.toLocaleString()}</span>
            <span className="projects-view__summary-label">reviewed</span>
          </div>
        </div>
      )}

      {/* Toolbar */}
      <div className="projects-view__toolbar">
        <div className="projects-view__search">
          <SearchInput
            placeholder="Search projects..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onClear={() => setSearchQuery('')}
          />
        </div>

        <div className="projects-view__filters">
          {(Object.keys(filterConfig) as FilterOption[]).map((filter) => (
            <button
              key={filter}
              className={`projects-view__filter ${activeFilter === filter ? 'projects-view__filter--active' : ''}`}
              onClick={() => setActiveFilter(filter)}
            >
              {filterConfig[filter].label}
              <Badge 
                variant={activeFilter === filter ? 'primary' : 'default'} 
                size="sm"
              >
                {filterCounts[filter]}
              </Badge>
            </button>
          ))}
        </div>
      </div>

      {/* Loading State */}
      {isLoading && <LoadingSpinner />}

      {/* Error State */}
      {error && (
        <div className="projects-view__error">
          <p>Error loading reports: {error}</p>
        </div>
      )}

      {/* Project Grid */}
      {!isLoading && filteredProjects.length === 0 ? (
        <div className="projects-view__empty">
          <div className="projects-view__empty-icon">
            <FolderIcon />
          </div>
          <h3 className="projects-view__empty-title">
            {isArchivedView
              ? 'No archived projects'
              : searchQuery || activeFilter !== 'all' 
                ? 'No projects found' 
                : 'No research projects yet'}
          </h3>
          <p className="projects-view__empty-message">
            {isArchivedView
              ? 'Projects you archive will appear here'
              : searchQuery || activeFilter !== 'all'
                ? 'Try adjusting your search or filters'
                : 'Start your first research project to discover investment opportunities'}
          </p>
          {!isArchivedView && !searchQuery && activeFilter === 'all' && (
            <Button variant="primary" onClick={onNewProject} icon={<PlusIcon />}>
              Start New Research
            </Button>
          )}
        </div>
      ) : (
        <div className="projects-view__grid">
          {filteredProjects.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              onSelect={() => onSelectProject(project)}
              onReview={() => onReviewProject(project)}
              onArchive={
                isArchivedView
                  ? undefined
                  : onArchiveProject 
                    ? () => onArchiveProject(project.id) 
                    : undefined
              }
              onUnarchive={
                isArchivedView && onUnarchiveProject 
                  ? () => onUnarchiveProject(project.id) 
                  : undefined
              }
              onDelete={onDeleteProject ? () => onDeleteProject(project.id) : undefined}
            />
          ))}
        </div>
      )}
    </div>
  );
}


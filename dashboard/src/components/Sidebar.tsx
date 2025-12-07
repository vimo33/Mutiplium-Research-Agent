import { ReactNode } from 'react';
import './Sidebar.css';

interface SidebarProps {
  currentView: string;
  onViewChange: (view: string) => void;
  projectName?: string;
  onBackToProjects?: () => void;
  reviewPendingCount?: number;
  reviewProgress?: number;
  archivedCount?: number;
  onNewProject?: () => void;
}

// Icons as inline SVGs
const ProjectsIcon = (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
    <rect x="3" y="3" width="6" height="6" rx="1" />
    <rect x="11" y="3" width="6" height="6" rx="1" />
    <rect x="3" y="11" width="6" height="6" rx="1" />
    <rect x="11" y="11" width="6" height="6" rx="1" />
  </svg>
);

const RunsIcon = (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M3 5h14M3 10h14M3 15h14" strokeLinecap="round" />
  </svg>
);

const BackIcon = (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M12 5l-5 5 5 5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const SettingsIcon = (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="10" cy="10" r="2.5" />
    <path d="M10 3v2M10 15v2M17 10h-2M5 10H3M14.95 5.05l-1.41 1.41M6.46 13.54l-1.41 1.41M14.95 14.95l-1.41-1.41M6.46 6.46L5.05 5.05" />
  </svg>
);

const DiscoveryIcon = (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="8" cy="8" r="5" />
    <path d="M12 12l5 5" strokeLinecap="round" />
    <path d="M8 5v6M5 8h6" strokeLinecap="round" />
  </svg>
);

const PlusIcon = (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M10 4v12M4 10h12" strokeLinecap="round" />
  </svg>
);

const ArchiveIcon = (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M3 5h14M3 5v11a1 1 0 001 1h12a1 1 0 001-1V5M7 9h6" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M5 5V4a1 1 0 011-1h8a1 1 0 011 1v1" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

// Logo SVG
const LogoIcon = (
  <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
    <defs>
      <linearGradient id="logoGrad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stopColor="#6B5CFF" />
        <stop offset="100%" stopColor="#9B8CFF" />
      </linearGradient>
    </defs>
    <rect x="2" y="2" width="24" height="24" rx="6" fill="url(#logoGrad)" />
    <path d="M9 14l3 3 7-7" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

interface NavItem {
  id: string;
  label: string;
  icon: ReactNode;
  badge?: number;
}

export function Sidebar({
  currentView,
  onViewChange,
  projectName,
  onBackToProjects,
  reviewPendingCount = 0,
  archivedCount = 0,
  onNewProject,
}: SidebarProps) {
  // When inside a project, show minimal nav with back button
  const isInProject = currentView === 'project-detail';

  const mainNavItems: NavItem[] = [
    { id: 'projects', label: 'Projects', icon: ProjectsIcon },
    { id: 'archived', label: 'Archived', icon: ArchiveIcon, badge: archivedCount > 0 ? archivedCount : undefined },
  ];

  const adminNavItems: NavItem[] = [
    { id: 'runs', label: 'Run History', icon: RunsIcon },
    { id: 'settings', label: 'Settings', icon: SettingsIcon },
  ];

  return (
    <aside className="sidebar">
      {/* Logo Header */}
      <div className="sidebar__header">
        <div className="sidebar__logo" onClick={() => onViewChange('projects')}>
          {LogoIcon}
          <div className="sidebar__logo-text">
            <span className="sidebar__logo-title">Multiplium</span>
            <span className="sidebar__logo-subtitle">Research Platform</span>
          </div>
        </div>
      </div>

      {/* New Project Button */}
      {onNewProject && (
        <div className="sidebar__new-project">
          <button className="sidebar__new-project-btn" onClick={onNewProject}>
            <span className="sidebar__new-project-icon">{PlusIcon}</span>
            <span>New Project</span>
          </button>
        </div>
      )}

      {/* Project Context Bar (when inside a project) */}
      {isInProject && projectName && (
        <div className="sidebar__project-context">
          <button className="sidebar__back-btn" onClick={onBackToProjects}>
            {BackIcon}
            <span>Back to Projects</span>
          </button>
          <div className="sidebar__project-name">
            {projectName}
          </div>
        </div>
      )}

      {/* Main Navigation */}
      <nav className="sidebar__nav">
        <ul className="sidebar__nav-list">
          {mainNavItems.map((item) => (
            <li key={item.id}>
              <button
                className={`sidebar__nav-item ${currentView === item.id ? 'sidebar__nav-item--active' : ''}`}
                onClick={() => onViewChange(item.id)}
              >
                <span className="sidebar__nav-icon">{item.icon}</span>
                <span className="sidebar__nav-label">{item.label}</span>
                {item.badge && item.badge > 0 && (
                  <span className="sidebar__nav-badge">{item.badge}</span>
                )}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      {/* Stats Summary (when projects exist) */}
      {reviewPendingCount > 0 && (
        <div className="sidebar__stats">
          <div className="sidebar__stat">
            <span className="sidebar__stat-value">{reviewPendingCount}</span>
            <span className="sidebar__stat-label">Pending Reviews</span>
          </div>
        </div>
      )}

      {/* Admin Section */}
      <div className="sidebar__admin">
        <div className="sidebar__section-divider">
          <span>Admin</span>
        </div>
        <ul className="sidebar__nav-list">
          {adminNavItems.map((item) => (
            <li key={item.id}>
              <button
                className={`sidebar__nav-item sidebar__nav-item--secondary ${currentView === item.id ? 'sidebar__nav-item--active' : ''}`}
                onClick={() => onViewChange(item.id)}
              >
                <span className="sidebar__nav-icon">{item.icon}</span>
                <span className="sidebar__nav-label">{item.label}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>

      {/* Footer */}
      <div className="sidebar__footer">
        <div className="sidebar__version">v1.0.0</div>
      </div>
    </aside>
  );
}

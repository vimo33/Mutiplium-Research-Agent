import { ReactNode } from 'react';
import { Checkbox } from './ui';
import './Sidebar.css';

// Navigation items
interface NavItem {
  id: string;
  label: string;
  icon: ReactNode;
}

interface SidebarProps {
  currentView: string;
  onViewChange: (view: string) => void;
  segments: string[];
  selectedSegments: string[];
  onSegmentToggle: (segment: string) => void;
  onSelectAllSegments: () => void;
  onClearSegments: () => void;
  shortlistedCompanies: string[];
  onShortlistClick: (company: string) => void;
  onClearShortlist: () => void;
}

// Icons as inline SVGs
const DashboardIcon = (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
    <rect x="2" y="2" width="7" height="7" rx="1.5" />
    <rect x="11" y="2" width="7" height="7" rx="1.5" />
    <rect x="2" y="11" width="7" height="7" rx="1.5" />
    <rect x="11" y="11" width="7" height="7" rx="1.5" />
  </svg>
);

const DiscoveryIcon = (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
    <circle cx="10" cy="10" r="7" />
    <path d="M10 6v4l2.5 2.5" strokeLinecap="round" />
  </svg>
);

const ResearchIcon = (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M3 4h14M3 8h10M3 12h14M3 16h7" strokeLinecap="round" />
  </svg>
);

function StarIconSmall() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
      <path d="M8 1.5l1.76 3.57 3.94.57-2.85 2.78.67 3.93L8 10.47l-3.52 1.88.67-3.93L2.3 5.64l3.94-.57L8 1.5z" />
    </svg>
  );
}

const NAV_ITEMS: NavItem[] = [
  { id: 'runs', label: 'Dashboard', icon: DashboardIcon },
  { id: 'discovery', label: 'Discovery', icon: DiscoveryIcon },
  { id: 'research', label: 'Deep Research', icon: ResearchIcon },
];

export function Sidebar({
  currentView,
  onViewChange,
  segments,
  selectedSegments,
  onSegmentToggle,
  onSelectAllSegments,
  onClearSegments,
  shortlistedCompanies,
  onShortlistClick,
  onClearShortlist,
}: SidebarProps) {
  const allSelected = segments.length > 0 && selectedSegments.length === segments.length;
  const someSelected = selectedSegments.length > 0 && selectedSegments.length < segments.length;

  return (
    <aside className="sidebar">
      {/* Logo */}
      <div className="sidebar__header">
        <div className="sidebar__logo">
          <span className="sidebar__logo-icon">🍇</span>
          <span className="sidebar__logo-text">Multiplium</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="sidebar__nav">
        <div className="sidebar__section-title">Navigation</div>
        <ul className="sidebar__nav-list">
          {NAV_ITEMS.map((item) => (
            <li key={item.id}>
              <button
                className={`sidebar__nav-item ${currentView === item.id ? 'sidebar__nav-item--active' : ''}`}
                onClick={() => onViewChange(item.id)}
              >
                <span className="sidebar__nav-icon">{item.icon}</span>
                <span className="sidebar__nav-label">{item.label}</span>
              </button>
            </li>
          ))}
        </ul>
      </nav>

      {/* Segment Filters */}
      {(currentView === 'discovery' || currentView === 'research') && segments.length > 0 && (
        <div className="sidebar__section">
          <div className="sidebar__section-header">
            <span className="sidebar__section-title">
              Segments ({selectedSegments.length}/{segments.length})
            </span>
            <button
              className="sidebar__section-action"
              onClick={allSelected ? onClearSegments : onSelectAllSegments}
            >
              {allSelected ? 'Clear' : 'All'}
            </button>
          </div>
          <div className="sidebar__segment-list">
            {segments.map((segment) => (
              <Checkbox
                key={segment}
                label={formatSegmentName(segment)}
                checked={selectedSegments.includes(segment)}
                onChange={() => onSegmentToggle(segment)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Shortlist */}
      <div className="sidebar__section sidebar__section--shortlist">
        <div className="sidebar__section-header">
          <span className="sidebar__section-title">
            <StarIconSmall /> Shortlist ({shortlistedCompanies.length})
          </span>
          {shortlistedCompanies.length > 0 && (
            <button className="sidebar__section-action" onClick={onClearShortlist}>
              Clear
            </button>
          )}
        </div>
        {shortlistedCompanies.length === 0 ? (
          <p className="sidebar__empty-text">
            Star companies to add them to your shortlist
          </p>
        ) : (
          <ul className="sidebar__shortlist">
            {shortlistedCompanies.map((company) => (
              <li key={company} className="sidebar__shortlist-item">
                <button
                  className="sidebar__shortlist-btn"
                  onClick={() => onShortlistClick(company)}
                >
                  <span className="sidebar__shortlist-name">{company}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}

// Helper to format segment names
function formatSegmentName(segment: string): string {
  return segment
    .replace(/^\d+\.\s*/, '') // Remove leading numbers
    .replace(/\s*\([^)]*\)/, '') // Remove parenthetical
    .trim();
}


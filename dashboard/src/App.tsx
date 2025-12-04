import { useState, useEffect, useCallback } from "react";
import { Sidebar } from "./components/Sidebar";
import { DeepResearchView } from "./components/DeepResearchView";
import { DiscoveryView } from "./components/DiscoveryView";
import { RunsView } from "./components/RunsView";
import { ReviewView } from "./components/ReviewView";
import { ProjectsView } from "./components/ProjectsView";
import { ProjectDetailView } from "./components/ProjectDetailView";
import { NewResearchWizard } from "./components/wizard";
import { useProjects } from "./hooks";
import type { Project } from "./types";
import "./App.css";

// Local storage keys
const SHORTLIST_STORAGE_KEY = "multiplium_shortlist";
const REVIEWS_STORAGE_KEY = "multiplium_reviews";

// Default segments for wine value chain
const DEFAULT_SEGMENTS = [
  "Grape Production (Viticulture)",
  "Wine Production (Vinification)",
  "Packaging & Bottling",
  "Distribution & Logistics",
  "Retail & Sales",
  "Marketing & Branding",
  "Consumption",
  "Recycling & Aftermarket",
];

type AppView = "projects" | "project-detail" | "runs" | "discovery" | "research" | "review";

export default function App() {
  // View state - default to projects (home)
  const [currentView, setCurrentView] = useState<AppView>("projects");
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [showWizard, setShowWizard] = useState(false);
  
  // Projects hook
  const {
    projects,
    createProject,
    updateProject,
    deleteProject,
    getProject,
    getReviewProgress,
  } = useProjects();
  
  // Segment filter state
  const [selectedSegments, setSelectedSegments] = useState<string[]>(DEFAULT_SEGMENTS);
  
  // Shortlist state (persisted to localStorage)
  const [shortlistedCompanies, setShortlistedCompanies] = useState<string[]>(() => {
    try {
      const stored = localStorage.getItem(SHORTLIST_STORAGE_KEY);
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });

  // Review stats for sidebar (read from localStorage)
  const [reviewStats, setReviewStats] = useState({ pending: 0, progress: 0 });

  // Persist shortlist to localStorage
  useEffect(() => {
    localStorage.setItem(SHORTLIST_STORAGE_KEY, JSON.stringify(shortlistedCompanies));
  }, [shortlistedCompanies]);

  // Watch for review changes to update sidebar stats
  useEffect(() => {
    const updateReviewStats = () => {
      try {
        const stored = localStorage.getItem(REVIEWS_STORAGE_KEY);
        if (stored) {
          const reviews = JSON.parse(stored);
          const entries = Object.values(reviews) as any[];
          const total = entries.length;
          const reviewed = entries.filter(r => r.status !== 'pending').length;
          setReviewStats({
            pending: total - reviewed,
            progress: total > 0 ? Math.round((reviewed / total) * 100) : 0,
          });
        }
      } catch {
        // Ignore errors
      }
    };

    // Initial load
    updateReviewStats();

    // Listen for storage changes (cross-tab sync)
    window.addEventListener('storage', updateReviewStats);
    
    // Poll for changes in same tab (since localStorage events don't fire in same tab)
    const interval = setInterval(updateReviewStats, 2000);
    
    return () => {
      window.removeEventListener('storage', updateReviewStats);
      clearInterval(interval);
    };
  }, []);

  // Segment toggle handlers
  const handleSegmentToggle = useCallback((segment: string) => {
    setSelectedSegments(prev =>
      prev.includes(segment)
        ? prev.filter(s => s !== segment)
        : [...prev, segment]
    );
  }, []);

  const handleSelectAllSegments = useCallback(() => {
    setSelectedSegments(DEFAULT_SEGMENTS);
  }, []);

  const handleClearSegments = useCallback(() => {
    setSelectedSegments([]);
  }, []);

  // Shortlist handlers
  const handleToggleShortlist = useCallback((company: string) => {
    setShortlistedCompanies(prev =>
      prev.includes(company)
        ? prev.filter(c => c !== company)
        : [...prev, company]
    );
  }, []);

  const handleClearShortlist = useCallback(() => {
    setShortlistedCompanies([]);
  }, []);

  const handleShortlistClick = useCallback((company: string) => {
    // Navigate to the review view when clicking a shortlisted company
    setCurrentView("review");
  }, []);

  // Project handlers
  const handleSelectProject = useCallback((project: Project) => {
    setSelectedProject(project);
    setCurrentView("project-detail");
    
    // Update segments from project framework
    if (project.framework.valueChain.length > 0) {
      setSelectedSegments(project.framework.valueChain.map(vc => vc.segment));
    }
  }, []);

  const handleReviewProject = useCallback((project: Project) => {
    setSelectedProject(project);
    setCurrentView("project-detail");
  }, []);

  const handleNewProject = useCallback(() => {
    setShowWizard(true);
  }, []);

  const handleWizardComplete = useCallback((projectData: Partial<Project>) => {
    const project = createProject(
      projectData.clientName || '',
      projectData.projectName || '',
      projectData.brief
    );
    
    // Update with framework
    if (projectData.framework) {
      updateProject(project.id, { framework: projectData.framework });
    }
    
    setShowWizard(false);
    setSelectedProject({ ...project, ...projectData } as Project);
    setCurrentView("project-detail");
  }, [createProject, updateProject]);

  const handleUpdateProject = useCallback((updates: Partial<Project>) => {
    if (selectedProject) {
      updateProject(selectedProject.id, updates);
      setSelectedProject({ ...selectedProject, ...updates });
    }
  }, [selectedProject, updateProject]);

  const handleBackToProjects = useCallback(() => {
    setSelectedProject(null);
    setCurrentView("projects");
  }, []);

  // View change handler - wrapped to handle type
  const handleViewChange = useCallback((view: string) => {
    setCurrentView(view as AppView);
    if (view === "projects") {
      setSelectedProject(null);
    }
  }, []);

  // Render current view
  const renderView = () => {
    // Show wizard overlay
    if (showWizard) {
      return (
        <NewResearchWizard
          onComplete={handleWizardComplete}
          onCancel={() => setShowWizard(false)}
        />
      );
    }

    switch (currentView) {
      case "projects":
        return (
          <ProjectsView
            projects={projects}
            onSelectProject={handleSelectProject}
            onReviewProject={handleReviewProject}
            onNewProject={handleNewProject}
            onDeleteProject={deleteProject}
          />
        );
      case "project-detail":
        if (!selectedProject) {
          setCurrentView("projects");
          return null;
        }
        return (
          <ProjectDetailView
            project={selectedProject}
            onBack={handleBackToProjects}
            onUpdateProject={handleUpdateProject}
            shortlistedCompanies={shortlistedCompanies}
            onToggleShortlist={handleToggleShortlist}
          />
        );
      case "runs":
        return <RunsView />;
      case "discovery":
        return (
          <DiscoveryView
            selectedSegments={selectedSegments}
            shortlistedCompanies={shortlistedCompanies}
            onToggleShortlist={handleToggleShortlist}
          />
        );
      case "review":
        return (
          <ReviewView
            selectedSegments={selectedSegments}
            shortlistedCompanies={shortlistedCompanies}
            onToggleShortlist={handleToggleShortlist}
          />
        );
      case "research":
      default:
        return (
          <DeepResearchView
            selectedSegments={selectedSegments}
            shortlistedCompanies={shortlistedCompanies}
            onToggleShortlist={handleToggleShortlist}
          />
        );
    }
  };

  // Don't show sidebar for wizard or project detail
  const showSidebar = !showWizard && currentView !== "project-detail";

  return (
    <div className="app-layout">
      {showSidebar && (
        <Sidebar
          currentView={currentView}
          onViewChange={handleViewChange}
          segments={selectedSegments.length > 0 ? selectedSegments : DEFAULT_SEGMENTS}
          selectedSegments={selectedSegments}
          onSegmentToggle={handleSegmentToggle}
          onSelectAllSegments={handleSelectAllSegments}
          onClearSegments={handleClearSegments}
          shortlistedCompanies={shortlistedCompanies}
          onShortlistClick={handleShortlistClick}
          onClearShortlist={handleClearShortlist}
          reviewPendingCount={reviewStats.pending}
          reviewProgress={reviewStats.progress}
        />
      )}
      <main className={`app-main ${!showSidebar ? 'app-main--full' : ''}`}>
        <div className="app-content">
          {renderView()}
        </div>
      </main>
    </div>
  );
}

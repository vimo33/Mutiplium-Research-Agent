import { useState, useEffect, useCallback } from "react";
import { Sidebar } from "./components/Sidebar";
import { RunsView } from "./components/RunsView";
import { ProjectsView } from "./components/ProjectsView";
import { ProjectDetailView } from "./components/ProjectDetailView";
import { DiscoveryProgress } from "./components/DiscoveryProgress";
import { DiscoveryReviewView } from "./components/DiscoveryReviewView";
import { DiscoveryBrowser } from "./components/DiscoveryBrowser";
import { ApiKeyPrompt } from "./components/ApiKeyPrompt";
import { NewResearchWizard, ResumeProjectWizard } from "./components/wizard";
import { useProjects } from "./hooks";
import { hasApiKey, clearApiKey, getApiBaseUrl, getAuthHeaders, isAuthRequired } from "./api";
import type { Project } from "./types";
import "./App.css";

// Local storage keys
const SHORTLIST_STORAGE_KEY = "multiplium_shortlist";
const REVIEWS_STORAGE_KEY = "multiplium_reviews";

type AppView = "projects" | "archived" | "project-detail" | "runs" | "discovery" | "settings";
type AuthState = "checking" | "required" | "authenticated";

export default function App() {
  // Authentication state - start with 'checking' to auto-detect
  const [authState, setAuthState] = useState<AuthState>("checking");
  
  // Check authentication on mount
  useEffect(() => {
    async function checkAuth() {
      // If already have a stored key, we're authenticated
      if (hasApiKey()) {
        setAuthState("authenticated");
        return;
      }
      // Check if backend requires auth
      const required = await isAuthRequired();
      setAuthState(required ? "required" : "authenticated");
    }
    checkAuth();
  }, []);
  
  // Handle logout
  const handleLogout = useCallback(() => {
    clearApiKey();
    setAuthState("required");
  }, []);

  // Show loading spinner while checking auth
  if (authState === "checking") {
    return (
      <div className="auth-loading">
        <div className="auth-loading-spinner" />
        <p>Loading...</p>
      </div>
    );
  }

  // If auth required and not authenticated, show API key prompt
  if (authState === "required") {
    return <ApiKeyPrompt onAuthenticated={() => setAuthState("authenticated")} />;
  }

  // View state - default to projects (home)
  const [currentView, setCurrentView] = useState<AppView>("projects");
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [showWizard, setShowWizard] = useState(false);
  const [resumeProject, setResumeProject] = useState<Project | null>(null);
  
  // Projects hook
  const {
    projects,
    archivedProjects,
    isLoading: projectsLoading,
    error: projectsError,
    createProject,
    updateProject,
    archiveProject,
    unarchiveProject,
    deleteProject,
  } = useProjects();
  
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
    
    // Poll for changes in same tab
    const interval = setInterval(updateReviewStats, 2000);
    
    return () => {
      window.removeEventListener('storage', updateReviewStats);
      clearInterval(interval);
    };
  }, []);

  // Shortlist handlers
  const handleToggleShortlist = useCallback((company: string) => {
    setShortlistedCompanies(prev =>
      prev.includes(company)
        ? prev.filter(c => c !== company)
        : [...prev, company]
    );
  }, []);

  // Project handlers
  const handleSelectProject = useCallback((project: Project) => {
    // If project is in draft status, resume the wizard
    if (project.status === 'draft') {
      setResumeProject(project);
    } else {
      setSelectedProject(project);
      setCurrentView("project-detail");
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

  // Handle resuming a draft project
  const handleResumeComplete = useCallback((projectData: Partial<Project>) => {
    if (resumeProject) {
      // Update the existing project
      updateProject(resumeProject.id, {
        ...projectData,
        status: projectData.status || 'researching',
      });
      
      const updatedProject = { ...resumeProject, ...projectData, status: projectData.status || 'researching' };
      setResumeProject(null);
      setSelectedProject(updatedProject as Project);
      // If starting research, stay on discovery progress view
      if (updatedProject.status === 'researching') {
        setCurrentView("project-detail");
      } else {
        setCurrentView("project-detail");
      }
    }
  }, [resumeProject, updateProject]);

  // Handle discovery completion
  const handleDiscoveryComplete = useCallback(() => {
    if (selectedProject) {
      updateProject(selectedProject.id, { status: 'discovery_complete' });
      setSelectedProject({ ...selectedProject, status: 'discovery_complete' });
    }
  }, [selectedProject, updateProject]);

  // Handle starting deep research from discovery review
  const handleStartDeepResearch = useCallback(async (selectedCompanies: string[]) => {
    if (!selectedProject) return;
    
    try {
      const response = await fetch(`${getApiBaseUrl()}/projects/${selectedProject.id}/start-deep-research`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          companies: selectedCompanies,
        }),
      });
      
      if (response.status === 401) {
        handleLogout();
        return;
      }
      
      if (!response.ok) throw new Error('Failed to start deep research');
      
      // Update project status to deep_researching
      updateProject(selectedProject.id, { status: 'deep_researching' });
      setSelectedProject({ ...selectedProject, status: 'deep_researching' });
    } catch (error) {
      console.error('Failed to start deep research:', error);
      throw error;
    }
  }, [selectedProject, updateProject, handleLogout]);

  // Handle skipping deep research
  const handleSkipDeepResearch = useCallback(() => {
    if (selectedProject) {
      updateProject(selectedProject.id, { status: 'ready_for_review' });
      setSelectedProject({ ...selectedProject, status: 'ready_for_review' });
    }
  }, [selectedProject, updateProject]);

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

  // Handle initiating deep research from discovery browser
  const handleInitiateDeepResearch = useCallback(async (reportPath: string, companies: string[]) => {
    try {
      const response = await fetch(`${getApiBaseUrl()}/deep-research`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          report_path: reportPath,
          companies: companies,
          top_n: companies.length || 5,
        }),
      });
      
      if (response.status === 401) {
        handleLogout();
        return;
      }
      
      if (!response.ok) throw new Error('Failed to initiate deep research');
      const data = await response.json();
      // Navigate to runs view to see progress
      setCurrentView('runs');
      return data;
    } catch (error) {
      console.error('Failed to initiate deep research:', error);
      throw error;
    }
  }, [handleLogout]);

  // View change handler
  const handleViewChange = useCallback((view: string) => {
    setCurrentView(view as AppView);
    if (view === "projects") {
      setSelectedProject(null);
    }
  }, []);

  // Render current view
  const renderView = () => {
    // Show new project wizard
    if (showWizard) {
      return (
        <NewResearchWizard
          onComplete={handleWizardComplete}
          onCancel={() => setShowWizard(false)}
        />
      );
    }

    // Show resume wizard for draft projects
    if (resumeProject) {
      return (
        <ResumeProjectWizard
          project={resumeProject}
          onComplete={handleResumeComplete}
          onCancel={() => setResumeProject(null)}
        />
      );
    }

    switch (currentView) {
      case "projects":
        return (
          <ProjectsView
            projects={projects}
            isLoading={projectsLoading}
            error={projectsError}
            onSelectProject={handleSelectProject}
            onReviewProject={handleReviewProject}
            onNewProject={handleNewProject}
            onArchiveProject={archiveProject}
            onDeleteProject={deleteProject}
          />
        );
      case "archived":
        return (
          <ProjectsView
            projects={archivedProjects}
            isLoading={projectsLoading}
            error={projectsError}
            onSelectProject={handleSelectProject}
            onReviewProject={handleReviewProject}
            onNewProject={handleNewProject}
            onUnarchiveProject={unarchiveProject}
            onDeleteProject={deleteProject}
            isArchivedView
          />
        );
      case "project-detail":
        if (!selectedProject) {
          setCurrentView("projects");
          return null;
        }
        // Show discovery progress if project is actively researching or failed
        if (selectedProject.status === 'researching' || selectedProject.status === 'discovery_failed') {
          return (
            <DiscoveryProgress
              project={selectedProject}
              onComplete={handleDiscoveryComplete}
              onBack={handleBackToProjects}
            />
          );
        }
        // Show discovery review if discovery is complete
        if (selectedProject.status === 'discovery_complete') {
          return (
            <DiscoveryReviewView
              project={selectedProject}
              onBack={handleBackToProjects}
              onStartDeepResearch={handleStartDeepResearch}
              onSkipDeepResearch={handleSkipDeepResearch}
            />
          );
        }
        // Show discovery progress for deep research phase too
        if (selectedProject.status === 'deep_researching') {
          return (
            <DiscoveryProgress
              project={selectedProject}
              onComplete={() => {
                if (selectedProject) {
                  updateProject(selectedProject.id, { status: 'ready_for_review' });
                  setSelectedProject({ ...selectedProject, status: 'ready_for_review' });
                }
              }}
              onBack={handleBackToProjects}
            />
          );
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
      case "settings":
        return (
          <div className="settings-placeholder">
            <h2>Settings</h2>
            <p>Settings panel coming soon...</p>
            <div style={{ marginTop: '2rem' }}>
              <button 
                onClick={handleLogout}
                style={{
                  padding: '0.75rem 1.5rem',
                  background: 'var(--status-rejected)',
                  color: 'white',
                  border: 'none',
                  borderRadius: 'var(--radius-md)',
                  cursor: 'pointer',
                }}
              >
                Sign Out
              </button>
            </div>
          </div>
        );
      default:
        return (
          <ProjectsView
            projects={projects}
            onSelectProject={handleSelectProject}
            onReviewProject={handleReviewProject}
            onNewProject={handleNewProject}
            onDeleteProject={deleteProject}
          />
        );
    }
  };

  // Only hide sidebar for wizard flows
  const showSidebar = !showWizard && !resumeProject;
  const isFullWidth = showWizard || resumeProject;

  return (
    <div className="app-layout">
      {showSidebar && (
        <Sidebar
          currentView={currentView}
          onViewChange={handleViewChange}
          projectName={selectedProject?.projectName}
          onBackToProjects={handleBackToProjects}
          reviewPendingCount={reviewStats.pending}
          reviewProgress={reviewStats.progress}
          archivedCount={archivedProjects.length}
          onNewProject={handleNewProject}
        />
      )}
      <main className={`app-main ${isFullWidth ? 'app-main--full' : ''}`}>
        <div className="app-content">
          {renderView()}
        </div>
      </main>
    </div>
  );
}

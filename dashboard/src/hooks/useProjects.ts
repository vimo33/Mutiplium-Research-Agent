import { useState, useEffect, useCallback } from 'react';
import type { Project, ProjectStatus, ResearchBrief, ResearchFramework, ProjectStats } from '../types';

const PROJECTS_STORAGE_KEY = 'multiplium_projects';

// Generate unique ID
function generateId(): string {
  return `proj_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

// Default empty stats
const defaultStats: ProjectStats = {
  totalCompanies: 0,
  enrichedCompanies: 0,
  approved: 0,
  rejected: 0,
  maybe: 0,
  pending: 0,
  flagged: 0,
};

// Default empty brief
const defaultBrief: ResearchBrief = {
  objective: '',
  targetStages: [],
  investmentSize: '',
  geography: [],
  technologies: [],
  additionalNotes: '',
};

// Default empty framework
const defaultFramework: ResearchFramework = {
  thesis: '',
  kpis: [],
  valueChain: [],
};

export function useProjects() {
  const [projects, setProjects] = useState<Project[]>(() => {
    try {
      const stored = localStorage.getItem(PROJECTS_STORAGE_KEY);
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });

  // Persist to localStorage
  useEffect(() => {
    localStorage.setItem(PROJECTS_STORAGE_KEY, JSON.stringify(projects));
  }, [projects]);

  // Create a new project
  const createProject = useCallback((
    clientName: string,
    projectName: string,
    brief?: Partial<ResearchBrief>
  ): Project => {
    const now = new Date().toISOString();
    const newProject: Project = {
      id: generateId(),
      clientName,
      projectName,
      brief: { ...defaultBrief, ...brief },
      framework: defaultFramework,
      status: 'draft',
      stats: defaultStats,
      createdAt: now,
      updatedAt: now,
    };
    
    setProjects(prev => [newProject, ...prev]);
    return newProject;
  }, []);

  // Update project
  const updateProject = useCallback((id: string, updates: Partial<Project>) => {
    setProjects(prev => prev.map(p => 
      p.id === id 
        ? { ...p, ...updates, updatedAt: new Date().toISOString() }
        : p
    ));
  }, []);

  // Update brief
  const updateBrief = useCallback((id: string, brief: Partial<ResearchBrief>) => {
    setProjects(prev => prev.map(p =>
      p.id === id
        ? { 
            ...p, 
            brief: { ...p.brief, ...brief },
            updatedAt: new Date().toISOString()
          }
        : p
    ));
  }, []);

  // Update framework
  const updateFramework = useCallback((id: string, framework: Partial<ResearchFramework>) => {
    setProjects(prev => prev.map(p =>
      p.id === id
        ? {
            ...p,
            framework: { ...p.framework, ...framework },
            updatedAt: new Date().toISOString()
          }
        : p
    ));
  }, []);

  // Update status
  const updateStatus = useCallback((id: string, status: ProjectStatus) => {
    setProjects(prev => prev.map(p =>
      p.id === id
        ? { ...p, status, updatedAt: new Date().toISOString() }
        : p
    ));
  }, []);

  // Update stats
  const updateStats = useCallback((id: string, stats: Partial<ProjectStats>) => {
    setProjects(prev => prev.map(p =>
      p.id === id
        ? {
            ...p,
            stats: { ...p.stats, ...stats },
            updatedAt: new Date().toISOString()
          }
        : p
    ));
  }, []);

  // Delete project
  const deleteProject = useCallback((id: string) => {
    setProjects(prev => prev.filter(p => p.id !== id));
  }, []);

  // Get single project
  const getProject = useCallback((id: string): Project | undefined => {
    return projects.find(p => p.id === id);
  }, [projects]);

  // Get projects with 50+ companies (successful projects)
  const getSuccessfulProjects = useCallback((): Project[] => {
    return projects.filter(p => p.stats.totalCompanies >= 50);
  }, [projects]);

  // Get projects by status
  const getProjectsByStatus = useCallback((status: ProjectStatus): Project[] => {
    return projects.filter(p => p.status === status);
  }, [projects]);

  // Calculate review progress percentage
  const getReviewProgress = useCallback((project: Project): number => {
    const { totalCompanies, approved, rejected, maybe } = project.stats;
    if (totalCompanies === 0) return 0;
    const reviewed = approved + rejected + maybe;
    return Math.round((reviewed / totalCompanies) * 100);
  }, []);

  return {
    projects,
    createProject,
    updateProject,
    updateBrief,
    updateFramework,
    updateStatus,
    updateStats,
    deleteProject,
    getProject,
    getSuccessfulProjects,
    getProjectsByStatus,
    getReviewProgress,
  };
}


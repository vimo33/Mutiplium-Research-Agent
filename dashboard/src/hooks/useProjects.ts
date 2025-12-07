import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import type { Project, ProjectStatus, ResearchBrief, ResearchFramework, ProjectStats, KPI, ValueChainSegment } from '../types';
import { listReports, fetchReportData, type Report, getApiBaseUrl, getAuthHeaders } from '../api';

const PROJECTS_STORAGE_KEY = 'multiplium_projects';

// Generate unique ID based on report path to ensure consistency
function generateIdFromPath(path: string): string {
  // Create a consistent hash from the path
  return `legacy_${path.replace(/[^a-zA-Z0-9]/g, '_').slice(0, 50)}`;
}

// Generate unique ID for new projects
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

// Parse KPIs from report data
function parseKPIs(reportData: any): KPI[] {
  if (!reportData?.kpis?.raw) return [];
  
  const kpis: KPI[] = [];
  const kpiText = Array.isArray(reportData.kpis.raw) 
    ? reportData.kpis.raw.join('\n') 
    : reportData.kpis.raw;
  
  // Extract KPI names from markdown tables or headings
  const kpiMatches = kpiText.match(/\*\*([^*]+)\*\*/g) || [];
  kpiMatches.slice(0, 10).forEach((match: string) => {
    const name = match.replace(/\*\*/g, '').trim();
    if (name && name.length < 100) {
      kpis.push({ name, target: '', rationale: '' });
    }
  });
  
  return kpis;
}

// Parse value chain from report data
function parseValueChain(reportData: any): ValueChainSegment[] {
  if (!reportData?.value_chain) return [];
  
  const valueChain: ValueChainSegment[] = [];
  const vcData = Array.isArray(reportData.value_chain) 
    ? reportData.value_chain 
    : [reportData.value_chain];
  
  vcData.forEach((vc: any) => {
    const raw = typeof vc === 'string' ? vc : (vc.raw || '');
    
    // Extract segment headings from markdown (## 1. Segment Name)
    const segmentMatches = raw.match(/##\s*\d+\.\s*([^\n]+)/g) || [];
    segmentMatches.forEach((match: string) => {
      const segment = match.replace(/##\s*\d+\.\s*/, '').trim();
      if (segment && segment.length < 100) {
        valueChain.push({ segment, description: '' });
      }
    });
  });
  
  return valueChain;
}

// Count companies from providers
function countCompanies(reportData: any): number {
  let count = 0;
  
  if (reportData?.providers && Array.isArray(reportData.providers)) {
    reportData.providers.forEach((provider: any) => {
      if (provider.findings && Array.isArray(provider.findings)) {
        provider.findings.forEach((finding: any) => {
          if (finding.raw) {
            // Count company objects in JSON
            const companyMatches = finding.raw.match(/"company"\s*:/g);
            if (companyMatches) {
              count += companyMatches.length;
            }
          }
        });
      }
    });
  }
  
  return count;
}

// Convert an API report to a Project object
function reportToProject(report: Report, reportData?: any): Project {
  const timestamp = report.timestamp || new Date().toISOString();
  
  // Extract info from report data
  let thesis = '';
  let kpis: KPI[] = [];
  let valueChain: ValueChainSegment[] = [];
  let totalCompanies = report.total_companies || 0;
  let sector = 'Wine Industry Value Chain';
  
  if (reportData) {
    thesis = reportData.thesis || '';
    sector = reportData.sector || 'Wine Industry Value Chain';
    kpis = parseKPIs(reportData);
    valueChain = parseValueChain(reportData);
    
    const companyCount = countCompanies(reportData);
    if (companyCount > 0) {
      totalCompanies = companyCount;
    }
  }

  // Format date for project name
  const dateStr = new Date(timestamp).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });

  const projectName = sector !== 'Unknown Sector' 
    ? sector 
    : `${report.report_type === 'deep_research' ? 'Deep Research' : 'Discovery'} - ${dateStr}`;

  return {
    id: generateIdFromPath(report.path),
    clientName: 'Legacy Import',
    projectName,
    brief: {
      ...defaultBrief,
      objective: thesis ? thesis.slice(0, 500) : `${report.report_type} research`,
    },
    framework: {
      thesis: thesis.slice(0, 5000),
      kpis,
      valueChain,
    },
    status: 'ready_for_review' as ProjectStatus,
    reportPath: report.path,
    stats: {
      ...defaultStats,
      totalCompanies,
      pending: totalCompanies,
    },
    createdAt: timestamp,
    updatedAt: timestamp,
    archived: false,
  };
}

export function useProjects() {
  const [projects, setProjects] = useState<Project[]>(() => {
    try {
      const stored = localStorage.getItem(PROJECTS_STORAGE_KEY);
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });
  
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Helper to convert API project to frontend Project format
  const apiProjectToProject = useCallback((apiProject: any): Project => {
    return {
      id: apiProject.id,
      clientName: apiProject.client_name || '',
      projectName: apiProject.project_name || '',
      brief: {
        objective: apiProject.brief?.objective || '',
        targetStages: apiProject.brief?.target_stages || [],
        investmentSize: apiProject.brief?.investment_size || '',
        geography: apiProject.brief?.geography || [],
        technologies: apiProject.brief?.technologies || [],
        additionalNotes: apiProject.brief?.additional_notes || '',
      },
      framework: {
        thesis: apiProject.framework?.thesis || '',
        kpis: (apiProject.framework?.kpis || []).map((k: any) => ({
          name: k.name || '',
          target: k.target || '',
          rationale: k.rationale || '',
        })),
        valueChain: (apiProject.framework?.value_chain || []).map((v: any) => ({
          segment: v.segment || '',
          description: v.description || '',
        })),
      },
      status: apiProject.status || 'draft',
      reportPath: apiProject.report_path,
      testRunReportPath: apiProject.test_run_report_path,
      stats: {
        totalCompanies: apiProject.stats?.total_companies || 0,
        enrichedCompanies: apiProject.stats?.enriched_companies || 0,
        approved: apiProject.stats?.approved || 0,
        rejected: apiProject.stats?.rejected || 0,
        maybe: apiProject.stats?.maybe || 0,
        pending: apiProject.stats?.pending || 0,
        flagged: apiProject.stats?.flagged || 0,
      },
      createdAt: apiProject.created_at || new Date().toISOString(),
      updatedAt: apiProject.updated_at || new Date().toISOString(),
      archived: apiProject.archived || false,
    };
  }, []);

  // Track if we've already loaded to prevent double-fetching
  const hasLoaded = useRef(false);

  // Load projects from backend API and legacy reports on mount
  useEffect(() => {
    // Prevent double-loading in React strict mode
    if (hasLoaded.current) return;
    hasLoaded.current = true;

    const loadAllProjects = async () => {
      try {
        setIsLoading(true);
        setError(null);
        
        // 1. Fetch projects from backend API
        let apiProjects: Project[] = [];
        try {
          const response = await fetch(`${getApiBaseUrl()}/projects`, {
            headers: getAuthHeaders(),
          });
          if (response.ok) {
            const data = await response.json();
            if (data.projects && typeof data.projects === 'object') {
              // projects is a dict, convert to array
              apiProjects = Object.values(data.projects).map(apiProjectToProject);
            }
          }
        } catch (err) {
          console.warn('Could not fetch projects from backend:', err);
        }
        
        // 2. Also fetch legacy reports
        const { reports } = await listReports();
        const legacyProjects: Project[] = [];
        
        if (reports && reports.length > 0) {
          // Sort by total_companies (desc) then by timestamp (desc) to prioritize meaningful reports
          const sortedReports = reports
            .sort((a, b) => {
              // First by company count (higher is better)
              const companyDiff = (b.total_companies || 0) - (a.total_companies || 0);
              if (companyDiff !== 0) return companyDiff;
              // Then by timestamp
              return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
            });
          
          const processedPaths = new Set<string>();
          
          for (const report of sortedReports) {
            if (processedPaths.has(report.path)) continue;
            processedPaths.add(report.path);
            if (legacyProjects.length >= 50) break;
            
            try {
              const reportData = await fetchReportData(report.path);
              const project = reportToProject(report, reportData);
              legacyProjects.push(project);
            } catch (err) {
              const project = reportToProject(report);
              legacyProjects.push(project);
            }
          }
        }
        
        // 3. Merge all projects: API projects take priority, but preserve local state
        setProjects(prev => {
          // Build a map of local state to preserve (archived, reviews, etc.)
          const localStateById = new Map<string, { archived?: boolean; archivedAt?: string }>();
          const localStateByPath = new Map<string, { archived?: boolean; archivedAt?: string }>();
          
          prev.forEach(p => {
            const state = { archived: p.archived, archivedAt: p.archivedAt };
            localStateById.set(p.id, state);
            if (p.reportPath) {
              localStateByPath.set(p.reportPath, state);
            }
          });
          
          // Merge local state into new projects
          const mergeLocalState = (project: Project): Project => {
            const stateById = localStateById.get(project.id);
            const stateByPath = project.reportPath ? localStateByPath.get(project.reportPath) : undefined;
            const localState = stateById || stateByPath;
            
            if (localState && localState.archived) {
              return { ...project, archived: localState.archived, archivedAt: localState.archivedAt };
            }
            return project;
          };
          
          const allProjects = [
            ...apiProjects.map(mergeLocalState),
            ...legacyProjects.map(mergeLocalState),
            ...prev
          ];
          
          // Dedupe by ID AND reportPath, keeping first occurrence (API projects first)
          const seenIds = new Set<string>();
          const seenPaths = new Set<string>();
          const deduped = allProjects.filter(p => {
            if (seenIds.has(p.id)) return false;
            if (p.reportPath && seenPaths.has(p.reportPath)) return false;
            seenIds.add(p.id);
            if (p.reportPath) seenPaths.add(p.reportPath);
            return true;
          });
          
          // Sort by createdAt descending
          return deduped.sort((a, b) => 
            new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
          );
        });
      } catch (err) {
        console.error('Failed to load projects:', err);
        setError(err instanceof Error ? err.message : 'Failed to load projects');
      } finally {
        setIsLoading(false);
      }
    };
    
    loadAllProjects();
  }, [apiProjectToProject]);

  // Persist to localStorage whenever projects change
  useEffect(() => {
    localStorage.setItem(PROJECTS_STORAGE_KEY, JSON.stringify(projects));
  }, [projects]);

  // Get active (non-archived) projects sorted by date descending
  const activeProjects = useMemo(() => {
    return projects
      .filter(p => !p.archived)
      .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
  }, [projects]);

  // Get archived projects
  const archivedProjects = useMemo(() => {
    return projects
      .filter(p => p.archived)
      .sort((a, b) => new Date(b.archivedAt || b.updatedAt).getTime() - new Date(a.archivedAt || a.updatedAt).getTime());
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
      archived: false,
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

  // Archive project
  const archiveProject = useCallback((id: string) => {
    const now = new Date().toISOString();
    setProjects(prev => prev.map(p =>
      p.id === id
        ? { ...p, archived: true, archivedAt: now, updatedAt: now }
        : p
    ));
  }, []);

  // Unarchive project
  const unarchiveProject = useCallback((id: string) => {
    setProjects(prev => prev.map(p =>
      p.id === id
        ? { ...p, archived: false, archivedAt: undefined, updatedAt: new Date().toISOString() }
        : p
    ));
  }, []);

  // Delete project permanently
  const deleteProject = useCallback((id: string) => {
    setProjects(prev => prev.filter(p => p.id !== id));
  }, []);

  // Get single project
  const getProject = useCallback((id: string): Project | undefined => {
    return projects.find(p => p.id === id);
  }, [projects]);

  // Get projects with 50+ companies (successful projects)
  const getSuccessfulProjects = useCallback((): Project[] => {
    return activeProjects.filter(p => p.stats.totalCompanies >= 50);
  }, [activeProjects]);

  // Get projects by status
  const getProjectsByStatus = useCallback((status: ProjectStatus): Project[] => {
    return activeProjects.filter(p => p.status === status);
  }, [activeProjects]);

  // Calculate review progress percentage
  const getReviewProgress = useCallback((project: Project): number => {
    const { totalCompanies, approved, rejected, maybe } = project.stats;
    if (totalCompanies === 0) return 0;
    const reviewed = approved + rejected + maybe;
    return Math.round((reviewed / totalCompanies) * 100);
  }, []);
  
  // Clear all data and reload
  const clearAndReload = useCallback(() => {
    localStorage.removeItem(PROJECTS_STORAGE_KEY);
    setProjects([]);
    window.location.reload();
  }, []);

  return {
    projects: activeProjects,  // Return active projects by default
    archivedProjects,
    allProjects: projects,
    isLoading,
    error,
    createProject,
    updateProject,
    updateBrief,
    updateFramework,
    updateStatus,
    updateStats,
    archiveProject,
    unarchiveProject,
    deleteProject,
    getProject,
    getSuccessfulProjects,
    getProjectsByStatus,
    getReviewProgress,
    clearAndReload,
  };
}

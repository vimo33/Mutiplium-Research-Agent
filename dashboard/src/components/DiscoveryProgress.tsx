import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import type { Project } from '../types';
import { Button, ProgressRing, Badge } from './ui';
import { getApiBaseUrl, getAuthHeaders } from '../api';
import './DiscoveryProgress.css';

interface DiscoveryProgressProps {
  project: Project;
  onComplete: () => void;
  onBack: () => void;
}

interface ProviderCost {
  input_tokens: number;
  output_tokens: number;
  tool_calls: number;
  input_cost: number;
  output_cost: number;
  tool_cost: number;
  total_cost: number;
  currency: string;
}

interface ProviderStatus {
  name: string;
  status: string;
  progress: number;
  last_message?: string;
  companies_found?: number;
  tool_calls?: number;
  errors?: string[];
  cost?: ProviderCost;
}

interface DiscoveryStatus {
  status: string;
  run_id?: string;
  phase?: string;
  percent_complete?: number;
  providers?: Record<string, ProviderStatus>;
  has_report?: boolean;
  report_path?: string;
  message?: string;
  total_cost?: number;
  provider_costs?: Record<string, ProviderCost>;
  error?: string;
  can_retry?: boolean;
}

interface DiscoveryCompany {
  company: string;
  segment?: string;
  timestamp?: string;
}

export function DiscoveryProgress({ project, onComplete, onBack }: DiscoveryProgressProps) {
  const [status, setStatus] = useState<DiscoveryStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [startTime] = useState<number>(Date.now());
  const [elapsedTime, setElapsedTime] = useState<number>(0);
  const [discoveredCompanies, setDiscoveredCompanies] = useState<DiscoveryCompany[]>([]);
  const [retrying, setRetrying] = useState(false);

  // Update elapsed time
  useEffect(() => {
    const interval = setInterval(() => {
      setElapsedTime(Date.now() - startTime);
    }, 1000);
    return () => clearInterval(interval);
  }, [startTime]);

  // Format elapsed time
  const formatElapsedTime = (ms: number): string => {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    
    if (hours > 0) {
      return `${hours}h ${minutes % 60}m`;
    } else if (minutes > 0) {
      return `${minutes}m ${seconds % 60}s`;
    } else {
      return `${seconds}s`;
    }
  };

  // Poll for status
  const fetchStatus = useCallback(async () => {
    try {
      const response = await fetch(`${getApiBaseUrl()}/projects/${project.id}/discovery-status`, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        setStatus(data);

        // If completed with report, notify parent (set to discovery_complete)
        if (data.status === 'completed' && data.has_report) {
          onComplete();
        }
      }
    } catch (err) {
      console.error('Error fetching status:', err);
    }
  }, [project.id, onComplete]);

  // Fetch run logs
  const fetchLogs = useCallback(async (runId: string) => {
    try {
      const response = await fetch(`${getApiBaseUrl()}/runs/${runId}/events?limit=50`, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        const events = data.events || [];
        const logMessages = events
          .filter((e: any) => e.type && e.type !== 'snapshot')
          .map((e: any) => {
            const time = new Date(e.ts).toLocaleTimeString();
            return `[${time}] ${e.type}: ${e.provider || ''} ${e.message || e.status || ''}`;
          })
          .reverse();
        setLogs(logMessages);
      }
    } catch (err) {
      // Ignore errors
    }
  }, []);

  // Start polling
  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 3000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  // Fetch logs when we have a run_id
  useEffect(() => {
    if (status?.run_id) {
      fetchLogs(status.run_id);
      const interval = setInterval(() => fetchLogs(status.run_id!), 5000);
      return () => clearInterval(interval);
    }
  }, [status?.run_id, fetchLogs]);

  // Retry discovery
  const handleRetry = async () => {
    try {
      setRetrying(true);
      setError(null);
      const response = await fetch(`${getApiBaseUrl()}/projects/${project.id}/retry-discovery`, {
        method: 'POST',
        headers: getAuthHeaders(),
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to retry discovery');
      }
      // Reset status to trigger polling
      setStatus(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to retry discovery');
    } finally {
      setRetrying(false);
    }
  };

  // Check if discovery failed
  const hasFailed = status?.status === 'failed';

  // Get provider list
  const providers = status?.providers ? Object.entries(status.providers) : [];
  const activeProviders = providers.filter(([_, p]) => p.status === 'running');
  const completedProviders = providers.filter(([_, p]) => p.status === 'completed');

  // Calculate overall progress
  const overallProgress = status?.percent_complete || 0;
  const totalCompanies = providers.reduce((sum, [_, p]) => sum + (p.companies_found || 0), 0);
  const totalToolCalls = providers.reduce((sum, [_, p]) => sum + (p.tool_calls || 0), 0);
  const totalCost = status?.total_cost || 0;

  // Tool activity aggregation (simulated from tool_calls)
  const toolActivity = useMemo(() => {
    const toolCalls = totalToolCalls;
    // Estimate distribution (in production, get from actual tool logs)
    return [
      { name: 'Tavily', calls: Math.floor(toolCalls * 0.5), icon: '🔍' },
      { name: 'Perplexity', calls: Math.floor(toolCalls * 0.3), icon: '🧠' },
      { name: 'OpenCorp', calls: Math.floor(toolCalls * 0.2), icon: '🏢' },
    ];
  }, [totalToolCalls]);

  return (
    <div className="discovery-progress">
      <div className="discovery-progress__header">
        <button className="discovery-progress__back" onClick={onBack}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M15 18l-6-6 6-6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
        <div>
          <h1 className="discovery-progress__title">
            {hasFailed ? 'Discovery Failed' : 'Discovery in Progress'}
          </h1>
          <p className="discovery-progress__subtitle">{project.projectName}</p>
        </div>
      </div>

      <div className="discovery-progress__content">
        {/* Error state with retry */}
        {hasFailed && (
          <div className="discovery-progress__error-card">
            <div className="discovery-progress__error-icon">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <path d="M12 8v4M12 16h.01" strokeLinecap="round" />
              </svg>
            </div>
            <h3 className="discovery-progress__error-title">Discovery encountered an error</h3>
            <p className="discovery-progress__error-message">
              {status?.error || 'The discovery process failed unexpectedly.'}
            </p>
            <div className="discovery-progress__error-actions">
              <Button 
                variant="primary" 
                onClick={handleRetry}
                disabled={retrying}
              >
                {retrying ? 'Retrying...' : 'Retry Discovery'}
              </Button>
              <Button variant="secondary" onClick={onBack}>
                Back to Projects
              </Button>
            </div>
          </div>
        )}

        {/* Main progress card - show when not failed */}
        {!hasFailed && (
          <div className="discovery-progress__main">
            <div className="discovery-progress__ring">
              <ProgressRing 
                progress={overallProgress} 
                size="xl"
                showLabel={false}
              />
              <div className="discovery-progress__ring-text">
                <span className="discovery-progress__percent">{Math.round(overallProgress)}%</span>
                <span className="discovery-progress__label">Complete</span>
              </div>
            </div>

            <div className="discovery-progress__stats">
              <div className="discovery-progress__stat">
                <span className="discovery-progress__stat-value">{totalCompanies}</span>
                <span className="discovery-progress__stat-label">Companies Found</span>
              </div>
              <div className="discovery-progress__stat">
                <span className="discovery-progress__stat-value">{totalToolCalls}</span>
                <span className="discovery-progress__stat-label">Tool Calls</span>
              </div>
              <div className="discovery-progress__stat">
                <span className="discovery-progress__stat-value">${totalCost.toFixed(2)}</span>
                <span className="discovery-progress__stat-label">Cost</span>
              </div>
            </div>

            <div className="discovery-progress__phase">
              <span className="discovery-progress__phase-label">Elapsed:</span>
              <span className="discovery-progress__phase-value">{formatElapsedTime(elapsedTime)}</span>
              <span className="discovery-progress__phase-label" style={{ marginLeft: '1rem' }}>Phase:</span>
              <span className="discovery-progress__phase-value">{status?.phase || 'Initializing...'}</span>
            </div>
          </div>
        )}

        {/* Provider cards */}
        <div className="discovery-progress__providers">
          <h3>AI Research Agents</h3>
          <div className="discovery-progress__provider-grid">
            {providers.length === 0 ? (
              <div className="discovery-progress__provider discovery-progress__provider--loading">
                <div className="discovery-progress__provider-icon">
                  <div className="discovery-progress__spinner" />
                </div>
                <div className="discovery-progress__provider-info">
                  <span className="discovery-progress__provider-name">Starting agents...</span>
                  <span className="discovery-progress__provider-status">Please wait</span>
                </div>
              </div>
            ) : (
              providers.map(([name, provider]) => (
                <div 
                  key={name} 
                  className={`discovery-progress__provider discovery-progress__provider--${provider.status}`}
                >
                  <div className="discovery-progress__provider-icon">
                    {provider.status === 'running' ? (
                      <div className="discovery-progress__spinner" />
                    ) : provider.status === 'completed' ? (
                      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M9 12l2 2 4-4" />
                        <circle cx="12" cy="12" r="10" />
                      </svg>
                    ) : (
                      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="12" cy="12" r="10" />
                      </svg>
                    )}
                  </div>
                  <div className="discovery-progress__provider-info">
                    <span className="discovery-progress__provider-name">{name}</span>
                    <span className="discovery-progress__provider-status">
                      {provider.companies_found || 0} companies · {provider.tool_calls || 0} tool calls
                      {provider.cost && ` · $${provider.cost.total_cost.toFixed(3)}`}
                    </span>
                    {provider.last_message && (
                      <span className="discovery-progress__provider-last-message">
                        {provider.last_message}
                      </span>
                    )}
                  </div>
                  <div className="discovery-progress__provider-progress">
                    <div 
                      className="discovery-progress__provider-bar"
                      style={{ width: `${provider.progress || 0}%` }}
                    />
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Tool Activity */}
        {toolActivity.length > 0 && totalToolCalls > 0 && (
          <div className="discovery-progress__tools">
            <h3>Tool Activity</h3>
            <div className="discovery-progress__tool-list">
              {toolActivity.map((tool) => (
                <div key={tool.name} className="discovery-progress__tool-item">
                  <span className="discovery-progress__tool-icon">{tool.icon}</span>
                  <span className="discovery-progress__tool-name">{tool.name}</span>
                  <div className="discovery-progress__tool-bar-container">
                    <div 
                      className="discovery-progress__tool-bar"
                      style={{ width: `${(tool.calls / totalToolCalls) * 100}%` }}
                    />
                  </div>
                  <Badge variant="default" size="sm">{tool.calls}</Badge>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Activity log */}
        <div className="discovery-progress__logs">
          <h3>Activity Log</h3>
          <div className="discovery-progress__log-list">
            {logs.length === 0 ? (
              <div className="discovery-progress__log-empty">
                Waiting for activity...
              </div>
            ) : (
              logs.slice(0, 20).map((log, idx) => (
                <div key={idx} className="discovery-progress__log-item">
                  {log}
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Error display */}
      {error && (
        <div className="discovery-progress__error">
          <span>{error}</span>
          <Button variant="ghost" onClick={() => setError(null)}>Dismiss</Button>
        </div>
      )}
    </div>
  );
}


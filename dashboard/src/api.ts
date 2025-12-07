import type { RunEvent, RunSnapshot } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

// =============================================================================
// API Key Management
// =============================================================================

const API_KEY_STORAGE_KEY = "multiplium_api_key";

/**
 * Get the stored API key from localStorage.
 */
export function getApiKey(): string | null {
  return localStorage.getItem(API_KEY_STORAGE_KEY);
}

/**
 * Store the API key in localStorage.
 */
export function setApiKey(key: string): void {
  localStorage.setItem(API_KEY_STORAGE_KEY, key);
}

/**
 * Clear the stored API key.
 */
export function clearApiKey(): void {
  localStorage.removeItem(API_KEY_STORAGE_KEY);
}

/**
 * Check if an API key is stored.
 */
export function hasApiKey(): boolean {
  return !!getApiKey();
}

// =============================================================================
// API Request Helper
// =============================================================================

/**
 * Build headers for API requests, including API key if available.
 */
function buildHeaders(additionalHeaders?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...additionalHeaders,
  };
  
  const apiKey = getApiKey();
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }
  
  return headers;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: buildHeaders(init?.headers as Record<string, string>),
  });
  
  if (response.status === 401) {
    // Clear invalid API key and throw specific error
    clearApiKey();
    throw new Error("Authentication required. Please enter your API key.");
  }
  
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

/**
 * Verify the API key is valid by calling the auth-check endpoint.
 */
export async function verifyApiKey(key: string): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE}/auth-check`, {
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": key,
      },
    });
    return response.ok;
  } catch {
    return false;
  }
}

/**
 * Check if the backend requires authentication.
 * Returns true if auth is required, false if no auth configured (dev mode).
 */
export async function isAuthRequired(): Promise<boolean> {
  try {
    // Try to access a protected endpoint without auth
    const response = await fetch(`${API_BASE}/projects`, {
      headers: { "Content-Type": "application/json" },
    });
    // If 401, auth is required. Otherwise, no auth needed.
    return response.status === 401;
  } catch {
    // Network error - assume auth required to be safe
    return true;
  }
}

/**
 * Get the API base URL (useful for SSE connections).
 */
export function getApiBaseUrl(): string {
  return API_BASE;
}

/**
 * Get headers for fetch requests (useful for SSE/streaming).
 */
export function getAuthHeaders(): Record<string, string> {
  return buildHeaders();
}

export async function fetchRuns(): Promise<RunSnapshot[]> {
  const data = await request<{ runs: RunSnapshot[] }>("/runs");
  return data.runs ?? [];
}

export async function fetchRun(runId: string): Promise<RunSnapshot> {
  return request<RunSnapshot>(`/runs/${runId}`);
}

export async function fetchRunEvents(
  runId: string,
  limit = 200,
): Promise<RunEvent[]> {
  const data = await request<{ events: RunEvent[] }>(
    `/runs/${runId}/events?limit=${limit}`,
  );
  return data.events ?? [];
}

export type LaunchRunPayload = {
  project_id?: string;
  config_path: string;
  deep_research: boolean;
  top_n: number;
  dry_run: boolean;
};

export async function launchRun(payload: LaunchRunPayload): Promise<RunSnapshot> {
  const data = await request<{ run: RunSnapshot }>("/runs", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return data.run;
}

export type Report = {
  path: string;
  filename: string;
  timestamp: string;
  total_companies: number;
  has_deep_research: boolean;
  providers: string[];
  report_type: 'discovery' | 'deep_research';
};

export async function listReports(): Promise<{ reports: Report[] }> {
  return request<{ reports: Report[] }>("/reports");
}

export type DeepResearchPayload = {
  report_path: string;
  top_n: number;
  config_path: string;
};

export async function createDeepResearch(payload: DeepResearchPayload): Promise<{ run: RunSnapshot }> {
  return request<{ run: RunSnapshot }>("/deep-research", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// Fetch raw report JSON data
export async function fetchReportData(reportPath: string): Promise<any> {
  return request<any>(`/reports/${encodeURIComponent(reportPath)}/raw`);
}

// Cost tracking types
export interface ProjectCostResponse {
  project_id: string;
  total_cost: number;
  discovery_cost: number;
  deep_research_cost: number;
  enrichment_cost: number;
  currency: string;
  runs: Array<{
    run_id: string;
    started_at: string;
    status: string;
    cost: number;
    type: 'discovery' | 'deep_research';
  }>;
  last_updated: string;
}

export async function fetchProjectCost(projectId: string): Promise<ProjectCostResponse> {
  return request<ProjectCostResponse>(`/projects/${projectId}/cost`);
}


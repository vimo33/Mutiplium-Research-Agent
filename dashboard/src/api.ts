import type { RunEvent, RunSnapshot } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
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


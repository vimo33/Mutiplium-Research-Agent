export type ProviderSnapshot = {
  name: string;
  status: string;
  progress: number;
  last_message?: string | null;
  tool_calls?: number;
  companies_found?: number;
  errors?: string[];
};

export type RunSnapshot = {
  run_id: string;
  project_id: string;
  status: string;
  phase: string;
  percent_complete: number;
  started_at: string;
  finished_at?: string | null;
  config_path?: string | null;
  params?: Record<string, unknown>;
  report_path?: string | null;
  providers: Record<string, ProviderSnapshot>;
  last_event?: Record<string, unknown> | null;
};

export type RunEvent = {
  ts: string;
  type: string;
  [key: string]: unknown;
};


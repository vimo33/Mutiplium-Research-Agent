import { FormEvent, useEffect, useMemo, useState } from "react";
import { fetchRun, fetchRunEvents, fetchRuns, launchRun } from "../api";
import type { RunEvent, RunSnapshot } from "../types";
import { Card, Button, Badge, Toggle } from "./ui";
import "./RunsView.css";

const RUNS_POLL_INTERVAL = 5000;
const DETAIL_POLL_INTERVAL = 4000;

const DEFAULT_FORM = {
  projectId: "",
  configPath: "config/dev.yaml",
  deepResearch: false,
  dryRun: false,
  topN: 25,
};

function formatDate(value?: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

function formatDuration(start?: string, end?: string | null): string {
  if (!start) return "—";
  const finish = end ? new Date(end).getTime() : Date.now();
  const ms = finish - new Date(start).getTime();
  const minutes = Math.floor(ms / 60000);
  const seconds = Math.floor((ms % 60000) / 1000);
  return `${minutes}m ${seconds}s`;
}

function ProviderCard({ snapshot }: { snapshot: RunSnapshot }) {
  const providers = Object.values(snapshot.providers ?? {});
  if (!providers.length) {
    return (
      <Card className="runs-card">
        <h4>Providers</h4>
        <p className="runs-empty">No providers registered yet.</p>
      </Card>
    );
  }
  return (
    <Card className="runs-card">
      <h4>Providers</h4>
      <div className="providers-grid">
        {providers.map((provider) => (
          <div key={provider.name} className="provider-tile">
            <div className="provider-header">
              <strong>{provider.name}</strong>
              <StatusBadge status={provider.status} />
            </div>
            <div className="progress-bar">
              <span
                className="progress-bar__fill"
                style={{ width: `${provider.progress ?? 0}%` }}
              />
            </div>
            <p className="provider-meta">
              {provider.progress?.toFixed(1) ?? 0}% ·{" "}
              {provider.tool_calls ?? 0} tool calls ·{" "}
              {provider.companies_found ?? 0} companies
            </p>
            {provider.last_message && (
              <p className="provider-message">{provider.last_message}</p>
            )}
            {provider.errors?.length ? (
              <details className="provider-errors">
                <summary>Errors ({provider.errors.length})</summary>
                <ul>
                  {provider.errors.map((err, idx) => (
                    <li key={idx}>{err}</li>
                  ))}
                </ul>
              </details>
            ) : null}
          </div>
        ))}
      </div>
    </Card>
  );
}

function EventLog({ events }: { events: RunEvent[] }) {
  if (!events.length) {
    return (
      <Card className="runs-card">
        <h4>Event Log</h4>
        <p className="runs-empty">No events yet.</p>
      </Card>
    );
  }
  return (
    <Card className="runs-card">
      <h4>Event Log</h4>
      <div className="event-log">
        {events.map((event, idx) => (
          <div key={`${event.ts}-${idx}`} className="event-row">
            <div className="event-meta">
              <span className="event-ts">
                {new Date(event.ts).toLocaleTimeString()}
              </span>
              <span className="event-type">{event.type}</span>
            </div>
            <pre>{JSON.stringify({ ...event, ts: undefined, type: undefined }, null, 2)}</pre>
          </div>
        ))}
      </div>
    </Card>
  );
}

function StatusBadge({ status }: { status: string }) {
  let variant: 'default' | 'success' | 'warning' | 'danger' | 'primary' = 'default';
  switch (status) {
    case 'completed':
      variant = 'success';
      break;
    case 'running':
      variant = 'warning';
      break;
    case 'failed':
      variant = 'danger';
      break;
    case 'queued':
      variant = 'primary';
      break;
  }
  return <Badge variant={variant}>{status}</Badge>;
}

export function RunsView() {
  const [runs, setRuns] = useState<RunSnapshot[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [runDetail, setRunDetail] = useState<RunSnapshot | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [formState, setFormState] = useState(DEFAULT_FORM);
  const [isLaunching, setIsLaunching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadRuns();
    const interval = setInterval(loadRuns, RUNS_POLL_INTERVAL);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!selectedRunId) {
      setRunDetail(null);
      setEvents([]);
      return;
    }
    loadRunDetail(selectedRunId);
    const interval = setInterval(
      () => loadRunDetail(selectedRunId),
      DETAIL_POLL_INTERVAL,
    );
    return () => clearInterval(interval);
  }, [selectedRunId]);

  async function loadRuns() {
    try {
      const data = await fetchRuns();
      setRuns(data);
      if (!selectedRunId && data.length) {
        setSelectedRunId(data[0].run_id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function loadRunDetail(runId: string) {
    try {
      const [snapshot, latestEvents] = await Promise.all([
        fetchRun(runId),
        fetchRunEvents(runId),
      ]);
      setRunDetail(snapshot);
      setEvents(latestEvents);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleLaunch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsLaunching(true);
    setError(null);
    try {
      const created = await launchRun({
        project_id: formState.projectId || undefined,
        config_path: formState.configPath,
        deep_research: formState.deepResearch,
        top_n: formState.topN,
        dry_run: formState.dryRun,
      });
      setFormState(DEFAULT_FORM);
      await loadRuns();
      setSelectedRunId(created.run_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsLaunching(false);
    }
  }

  const selectedRun = useMemo(
    () => runs.find((run) => run.run_id === selectedRunId) ?? runDetail,
    [runs, runDetail, selectedRunId],
  );

  return (
    <div className="runs-view">
      <div className="page-header">
        <h1 className="page-header__title">Dashboard</h1>
        <p className="page-header__subtitle">
          Track discovery and deep research runs in real time
        </p>
      </div>

      <div className="runs-grid">
        <div className="runs-column">
          <Card className="runs-card">
            <h3>Start New Run</h3>
            <form onSubmit={handleLaunch} className="run-form">
              <label className="form-field">
                <span className="form-label">Config Path</span>
                <input
                  type="text"
                  value={formState.configPath}
                  onChange={(e) =>
                    setFormState({ ...formState, configPath: e.target.value })
                  }
                  required
                  className="form-input"
                />
              </label>
              <label className="form-field">
                <span className="form-label">Project ID</span>
                <input
                  type="text"
                  value={formState.projectId}
                  onChange={(e) =>
                    setFormState({ ...formState, projectId: e.target.value })
                  }
                  placeholder="auto"
                  className="form-input"
                />
              </label>
              <label className="form-field">
                <span className="form-label">Top N (deep research)</span>
                <input
                  type="number"
                  min={1}
                  value={formState.topN}
                  onChange={(e) =>
                    setFormState({
                      ...formState,
                      topN: Number(e.target.value) || 1,
                    })
                  }
                  className="form-input"
                />
              </label>
              <Toggle
                label="Enable Deep Research"
                checked={formState.deepResearch}
                onChange={(e) =>
                  setFormState({
                    ...formState,
                    deepResearch: e.target.checked,
                  })
                }
              />
              <Toggle
                label="Dry Run (no live tools)"
                checked={formState.dryRun}
                onChange={(e) =>
                  setFormState({
                    ...formState,
                    dryRun: e.target.checked,
                  })
                }
              />
              <Button type="submit" disabled={isLaunching} fullWidth>
                {isLaunching ? "Launching..." : "Start Run"}
              </Button>
            </form>
          </Card>

          <Card className="runs-card">
            <h3>Runs</h3>
            {error && <p className="error-message">{error}</p>}
            {runs.length === 0 ? (
              <p className="runs-empty">No runs yet.</p>
            ) : (
              <div className="runs-table-wrapper">
                <table className="runs-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Status</th>
                      <th>Phase</th>
                      <th>Progress</th>
                      <th>Started</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map((run) => (
                      <tr
                        key={run.run_id}
                        className={run.run_id === selectedRunId ? "selected-row" : ""}
                        onClick={() => setSelectedRunId(run.run_id)}
                      >
                        <td className="run-id">{run.run_id.slice(0, 8)}</td>
                        <td><StatusBadge status={run.status} /></td>
                        <td>{run.phase}</td>
                        <td>{run.percent_complete.toFixed(1)}%</td>
                        <td>{formatDate(run.started_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>

        <div className="runs-column">
          <Card className="runs-card">
            <h3>Run Detail</h3>
            {!selectedRun ? (
              <p className="runs-empty">Select a run to view detail.</p>
            ) : (
              <div className="detail-grid">
                <div className="detail-item">
                  <span className="detail-label">Run ID</span>
                  <span className="detail-value">{selectedRun.run_id}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Project</span>
                  <span className="detail-value">{selectedRun.project_id}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Status</span>
                  <StatusBadge status={selectedRun.status} />
                </div>
                <div className="detail-item">
                  <span className="detail-label">Phase</span>
                  <span className="detail-value">{selectedRun.phase}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Progress</span>
                  <span className="detail-value">{selectedRun.percent_complete.toFixed(1)}%</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Started</span>
                  <span className="detail-value">{formatDate(selectedRun.started_at)}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Finished</span>
                  <span className="detail-value">{formatDate(selectedRun.finished_at)}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Duration</span>
                  <span className="detail-value">
                    {formatDuration(selectedRun.started_at, selectedRun.finished_at)}
                  </span>
                </div>
              </div>
            )}
          </Card>

          {selectedRun && <ProviderCard snapshot={selectedRun} />}
          {selectedRun && <EventLog events={events} />}
        </div>
      </div>
    </div>
  );
}



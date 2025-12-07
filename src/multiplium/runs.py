"""
Run Registry for tracking orchestration runs.

Provides file-based persistence for run snapshots, events, and status tracking.
Designed to work both locally and in cloud deployments with persistent storage.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class ProviderStatus:
    """Status of a single provider within a run."""
    name: str
    status: str = "pending"  # pending, running, completed, failed
    started_at: str | None = None
    completed_at: str | None = None
    companies_found: int = 0
    cost: float = 0.0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProviderStatus":
        return cls(**data)


@dataclass
class RunSnapshot:
    """Snapshot of a run's current state."""
    run_id: str
    project_id: str
    config_path: str
    params: dict[str, Any] = field(default_factory=dict)
    status: str = "queued"  # queued, running, completed, failed
    phase: str = ""
    percent_complete: float = 0.0
    providers: dict[str, ProviderStatus] = field(default_factory=dict)
    started_at: str = ""
    completed_at: str | None = None
    report_path: str | None = None
    error: str | None = None
    total_cost: float = 0.0
    last_event: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        # Convert ProviderStatus objects to dicts
        result["providers"] = {
            name: status.to_dict() if isinstance(status, ProviderStatus) else status
            for name, status in self.providers.items()
        }
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunSnapshot":
        # Convert provider dicts back to ProviderStatus objects
        providers = {}
        for name, status_data in data.get("providers", {}).items():
            if isinstance(status_data, dict):
                providers[name] = ProviderStatus.from_dict(status_data)
            else:
                providers[name] = status_data
        data["providers"] = providers
        return cls(**data)


class RunRegistry:
    """
    File-based registry for tracking orchestration runs.
    
    Stores run snapshots and events in JSON files for persistence.
    Supports both local development and cloud deployment with configurable
    data roots.
    """

    def __init__(
        self,
        workspace_root: Path | None = None,
        data_root: Path | None = None,
    ):
        """
        Initialize the run registry.
        
        Args:
            workspace_root: Root of the workspace (for code/config paths).
            data_root: Root for data storage (defaults to workspace_root).
                       In production, this might be a persistent disk mount.
        """
        self.workspace_root = workspace_root or Path.cwd()
        self.data_root = data_root or self.workspace_root
        
        # Ensure directories exist
        self._runs_dir = self.data_root / "data" / "runs"
        self._events_dir = self.data_root / "data" / "run_events"
        self._stdout_dir = self.data_root / "data" / "run_stdout"
        
        self._runs_dir.mkdir(parents=True, exist_ok=True)
        self._events_dir.mkdir(parents=True, exist_ok=True)
        self._stdout_dir.mkdir(parents=True, exist_ok=True)

    def _snapshot_path(self, run_id: str) -> Path:
        return self._runs_dir / f"{run_id}.json"

    def _events_path(self, run_id: str) -> Path:
        return self._events_dir / f"{run_id}.jsonl"

    def stdout_path(self, run_id: str) -> Path:
        """Get the path for stdout/stderr logging."""
        return self._stdout_dir / f"{run_id}.log"

    def snapshot_exists(self, run_id: str) -> bool:
        """Check if a run snapshot exists."""
        return self._snapshot_path(run_id).exists()

    def create_run(
        self,
        project_id: str,
        config_path: str,
        params: dict[str, Any] | None = None,
        run_id: str | None = None,
    ) -> RunSnapshot:
        """Create a new run and return its snapshot."""
        import uuid
        
        run_id = run_id or uuid.uuid4().hex
        now = datetime.utcnow().isoformat() + "Z"
        
        snapshot = RunSnapshot(
            run_id=run_id,
            project_id=project_id,
            config_path=config_path,
            params=params or {},
            status="queued",
            started_at=now,
        )
        
        self._save_snapshot(snapshot)
        self.append_event(run_id, "run.created", {"project_id": project_id})
        
        return snapshot

    def load_snapshot(self, run_id: str) -> RunSnapshot:
        """Load a run snapshot by ID."""
        path = self._snapshot_path(run_id)
        if not path.exists():
            raise FileNotFoundError(f"Run not found: {run_id}")
        
        with path.open("r") as f:
            data = json.load(f)
        return RunSnapshot.from_dict(data)

    def _save_snapshot(self, snapshot: RunSnapshot) -> None:
        """Save a run snapshot to disk."""
        path = self._snapshot_path(snapshot.run_id)
        with path.open("w") as f:
            json.dump(snapshot.to_dict(), f, indent=2)

    def update_snapshot(
        self,
        run_id: str,
        status: str | None = None,
        phase: str | None = None,
        percent_complete: float | None = None,
        report_path: str | None = None,
        error: str | None = None,
        project_id: str | None = None,
    ) -> RunSnapshot:
        """Update a run snapshot with new values."""
        snapshot = self.load_snapshot(run_id)
        
        if status is not None:
            snapshot.status = status
        if phase is not None:
            snapshot.phase = phase
        if percent_complete is not None:
            snapshot.percent_complete = percent_complete
        if report_path is not None:
            snapshot.report_path = report_path
        if error is not None:
            snapshot.error = error
        if project_id is not None:
            snapshot.project_id = project_id
        
        self._save_snapshot(snapshot)
        return snapshot

    def list_snapshots(self, limit: int = 50) -> list[RunSnapshot]:
        """List recent run snapshots, sorted by start time (newest first)."""
        snapshots = []
        
        for path in self._runs_dir.glob("*.json"):
            try:
                with path.open("r") as f:
                    data = json.load(f)
                snapshots.append(RunSnapshot.from_dict(data))
            except Exception:
                continue
        
        # Sort by started_at descending
        snapshots.sort(key=lambda s: s.started_at or "", reverse=True)
        return snapshots[:limit]

    def register_providers(self, run_id: str, provider_names: list[str]) -> None:
        """Register providers for a run."""
        snapshot = self.load_snapshot(run_id)
        
        for name in provider_names:
            if name not in snapshot.providers:
                snapshot.providers[name] = ProviderStatus(name=name)
        
        self._save_snapshot(snapshot)

    def set_provider_status(
        self,
        run_id: str,
        provider_name: str,
        status: str,
        companies_found: int | None = None,
        cost: float | None = None,
        error: str | None = None,
    ) -> None:
        """Update a provider's status within a run."""
        snapshot = self.load_snapshot(run_id)
        
        if provider_name not in snapshot.providers:
            snapshot.providers[provider_name] = ProviderStatus(name=provider_name)
        
        provider = snapshot.providers[provider_name]
        provider.status = status
        
        now = datetime.utcnow().isoformat() + "Z"
        if status == "running" and not provider.started_at:
            provider.started_at = now
        if status in ("completed", "failed"):
            provider.completed_at = now
        
        if companies_found is not None:
            provider.companies_found = companies_found
        if cost is not None:
            provider.cost = cost
            # Update total cost
            snapshot.total_cost = sum(
                p.cost for p in snapshot.providers.values()
                if isinstance(p, ProviderStatus)
            )
        if error is not None:
            provider.error = error
        
        self._save_snapshot(snapshot)

    def mark_phase(self, run_id: str, phase: str, percent: float) -> None:
        """Mark the current phase and progress of a run."""
        snapshot = self.load_snapshot(run_id)
        snapshot.phase = phase
        snapshot.percent_complete = percent
        
        if snapshot.status == "queued":
            snapshot.status = "running"
        
        self._save_snapshot(snapshot)
        self.append_event(run_id, "phase.changed", {"phase": phase, "percent": percent})

    def append_event(
        self,
        run_id: str,
        event_type: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Append an event to the run's event log."""
        now = datetime.utcnow().isoformat() + "Z"
        event = {
            "timestamp": now,
            "type": event_type,
            "data": data or {},
        }
        
        # Append to JSONL file
        events_path = self._events_path(run_id)
        with events_path.open("a") as f:
            f.write(json.dumps(event) + "\n")
        
        # Update last_event in snapshot
        try:
            snapshot = self.load_snapshot(run_id)
            snapshot.last_event = event
            self._save_snapshot(snapshot)
        except FileNotFoundError:
            pass

    def load_events(self, run_id: str, limit: int = 200) -> list[dict[str, Any]]:
        """Load events for a run."""
        events_path = self._events_path(run_id)
        if not events_path.exists():
            return []
        
        events = []
        with events_path.open("r") as f:
            for line in f:
                if line.strip():
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        
        # Return most recent events
        return events[-limit:] if len(events) > limit else events

    def complete_run(
        self,
        run_id: str,
        report_path: str | None = None,
        error: str | None = None,
    ) -> None:
        """Mark a run as completed."""
        snapshot = self.load_snapshot(run_id)
        now = datetime.utcnow().isoformat() + "Z"
        
        snapshot.status = "failed" if error else "completed"
        snapshot.completed_at = now
        snapshot.percent_complete = 100.0 if not error else snapshot.percent_complete
        
        if report_path:
            snapshot.report_path = report_path
        if error:
            snapshot.error = error
        
        self._save_snapshot(snapshot)
        
        event_type = "run.failed" if error else "run.completed"
        self.append_event(run_id, event_type, {
            "report_path": report_path,
            "error": error,
        })

    def fail_run(self, run_id: str, error: str) -> None:
        """Mark a run as failed."""
        self.complete_run(run_id, error=error)

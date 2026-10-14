"""Dependency-free run events, available before importing the analysis engine."""
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import uuid


def record(event, **details):
    return {**details, "time": datetime.now(timezone.utc).isoformat(), "event": event}


def append_event(path, event, **details):
    """Append a launcher event while the caller holds its job lock."""
    with Path(path).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record(event, **details), ensure_ascii=False, default=str) + "\n")


class RunLog:
    def __init__(self, out_dir):
        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:12]
        self.run_dir = Path(out_dir) / "runs" / self.run_id
        self.run_dir.mkdir(parents=True)
        self.event_path = self.run_dir / "events.jsonl"
        self.lock = threading.RLock()
        self.stream = self.event_path.open("a", encoding="utf-8", buffering=1)

    def event(self, event, **details):
        with self.lock:
            if not self.stream.closed:
                self.stream.write(json.dumps(record(event, **details), ensure_ascii=False, default=str) + "\n")

    def bootstrap_failure(self, task_dir, error):
        """Retain failures that happen before Context can write a summary."""
        message = f"{type(error).__name__}: {error}"
        self.event("run_finished", status="failed", error=message, phase="initialization")
        summary = {"task_dir": str(task_dir), "generated_at": datetime.now(timezone.utc).isoformat(),
                   "n_steps": 0, "total_elapsed": 0, "steps": [], "status": "failed", "error": message,
                   "run_id": self.run_id, "event_log": str(self.event_path)}
        for directory in (Path(task_dir) / "output", self.run_dir):
            (directory / "run_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        (Path(task_dir) / "output/run_summary.txt").write_text(f"Run failed during initialization\n{message}\n", encoding="utf-8")

    def close(self):
        with self.lock:
            self.stream.close()

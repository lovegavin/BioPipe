# src/task/context/base.py
"""Context — the runtime image of a manifest."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.core import ContextError, Form
from src.task.memory.config import MemoryConfig
from src.task.memory.runtime import MemoryRuntime


class Context:
    """Holds forms, params and task-scoped state."""

    def __init__(self, task_dir: Path, manifest: dict):
        self.task_dir = Path(task_dir).resolve()
        self.manifest = manifest
        self.params = manifest.get("params", {})
        self.forms: dict[str, Form] = {}
        self.metadata: dict = {}
        self.step_params: dict = {}
        self.artifacts: dict = {}
        self.output_validator = None
        self.written_outputs = set()

        self.out_dir = self.task_dir / "output"
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._run_status = "created"
        self._run_error = None
        self.memory = None
        config = MemoryConfig.parse(manifest)
        if config.enabled:
            self.memory = MemoryRuntime(config, self.out_dir, manifest)
            self.forms = self.memory.store

    def register_source(self, name: str, spec: dict) -> None:
        """Managed sources are read on first use; legacy mode stays eager."""
        from src.reader import read_source
        path = self.task_dir / spec["path"]
        def loader():
            return read_source(path, dims=spec["dims"], labels=spec.get("labels", {}),
                               **spec.get("args", {}))
        if self.memory:
            self.forms.register_source(name, loader, path.resolve())
        else:
            self[name] = loader()
            print(f"[source] {name}: shape={self[name].data.shape}, dims={self[name].dims}")

    def __getitem__(self, name: str) -> Form:
        if name not in self.forms:
            raise ContextError(
                f"Form '{name}' not in context. "
                f"Available: {sorted(self.forms)}"
            )
        return self.forms[name]

    def __setitem__(self, name: str, form: Form) -> None:
        form.validate()
        if self.output_validator is not None:
            self.output_validator(name, form)
        self.forms[name] = form
        self.written_outputs.add(name)

    def has(self, name: str) -> bool:
        return name in self.forms

    def finalize(self) -> None:
        """Write the run summary.

        Reads ``artifacts["exports"]`` populated by the runner and
        writes two files:

        * ``output/run_summary.json`` — machine-readable index
        * ``output/run_summary.txt``  — human-readable index

        The summary lists step names, elapsed times and the paths of
        per-step JSON files. It does not repeat step details.
        """
        exports = self.artifacts.get("exports", [])
        close_error = None
        memory_report = None
        if self.memory:
            try:
                memory_report = self.memory.close(self._run_status, self._run_error)
            except Exception as exc:
                close_error = exc
                self._run_status, self._run_error = "failed", exc
                memory_report = self.memory.close("failed", exc)

        summary = {
            "task_dir": str(self.task_dir),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "n_steps": len(exports),
            "total_elapsed": round(
                sum(e["elapsed"] for e in exports), 4
            ),
            "steps": exports,
            "status": self._run_status,
            "error": str(self._run_error) if self._run_error else None,
        }
        if memory_report:
            summary["run_id"] = self.memory.run_id
            summary["memory_report"] = str(self.memory.run_dir / "memory_report.json")
            summary["event_log"] = str(self.memory.event_path)
            summary["managed_peak_bytes"] = memory_report["managed_peak_bytes"]

        json_path = self.out_dir / "run_summary.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        txt_path = self.out_dir / "run_summary.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(self._render_text(summary))
        if self.memory:
            (self.memory.run_dir / "run_summary.json").write_text(
                json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        if close_error:
            raise close_error

    @staticmethod
    def _render_text(summary: dict) -> str:
        lines = []
        lines.append("=" * 60)
        lines.append("Run summary")
        lines.append("=" * 60)
        lines.append(f"task      : {summary['task_dir']}")
        lines.append(f"generated : {summary['generated_at']}")
        lines.append(f"steps     : {summary['n_steps']}")
        lines.append(f"elapsed   : {summary['total_elapsed']:.3f}s")
        lines.append(f"status    : {summary.get('status', 'complete')}")
        if summary.get("error"):
            lines.append(f"error     : {summary['error']}")
        lines.append("")
        lines.append("-" * 60)
        lines.append(f"{'#':<4}{'step':<20}{'elapsed':>10}   export")
        lines.append("-" * 60)

        for e in summary["steps"]:
            lines.append(
                f"{e['index']:<4}"
                f"{e['name']:<20}"
                f"{e['elapsed']:>9.3f}s   "
                f"{e['export_path']}"
            )

        lines.append("")
        lines.append("=" * 60)
        lines.append(
            "Per-step details are at the export paths above. "
            "This file is an index only."
        )
        lines.append("=" * 60)
        return "\n".join(lines) + "\n"

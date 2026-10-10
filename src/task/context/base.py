# src/task/context/base.py
"""Context — the runtime image of a manifest."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.core import ContextError, Form


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

        self.out_dir = self.task_dir / "output"
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def __getitem__(self, name: str) -> Form:
        if name not in self.forms:
            raise ContextError(
                f"Form '{name}' not in context. "
                f"Available: {sorted(self.forms)}"
            )
        return self.forms[name]

    def __setitem__(self, name: str, form: Form) -> None:
        form.validate()
        self.forms[name] = form

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

        summary = {
            "task_dir": str(self.task_dir),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "n_steps": len(exports),
            "total_elapsed": round(
                sum(e["elapsed"] for e in exports), 4
            ),
            "steps": exports,
        }

        json_path = self.out_dir / "run_summary.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        txt_path = self.out_dir / "run_summary.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(self._render_text(summary))

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
            "Per-step details are in output/steps/. "
            "This file is an index only."
        )
        lines.append("=" * 60)
        return "\n".join(lines) + "\n"
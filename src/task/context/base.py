# src/task/context/base.py
"""Context — the runtime image of a manifest."""

from __future__ import annotations

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
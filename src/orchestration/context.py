# src/orchestration/context.py
"""PipelineContext — the shared state passed between pipeline steps.

Every step receives exactly one context. Steps read inputs from
``ctx.forms`` and write outputs back to it. Non-form artefacts (figures,
JSON reports, trained model weights) go into ``ctx.artifacts``.

Steps must never communicate directly with each other. All shared
state flows through the context, which is the single source of truth
for a pipeline run.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class PipelineContext:
    """Mutable state container for a single pipeline run.

    Parameters
    ----------
    config : dict
        Fully validated manifest.
    task_dir : Path
        Root directory of the task. Inputs are resolved relative to it.
    out_dir : Path
        Directory for primary outputs.
    proc_dir : Path
        Directory for intermediate artefacts.
    fig_dir : Path
        Directory for figures.
    log_dir : Path
        Directory for logs.
    logger : logging.Logger
        Structured logger for the run.
    rng : np.random.Generator
        Seeded RNG shared by all steps. Ensures reproducibility.
    device : str
        Compute device for steps that support it (``"cpu"`` / ``"cuda"``).
    forms : dict
        In-memory domain forms keyed by form name.
    artifacts : dict
        Non-form outputs (figures, reports, models).
    metadata : dict
        Run metadata accumulated across steps (timings, versions, hashes).
    """

    config: dict
    task_dir: Path
    out_dir: Path
    proc_dir: Path
    fig_dir: Path
    log_dir: Path
    logger: logging.Logger
    rng: np.random.Generator
    device: str = "cpu"

    forms: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    # Form access
    # ------------------------------------------------------------------ #

    def get(self, name: str) -> Any:
        """Return the form registered under ``name``.

        Raises
        ------
        KeyError
            If no such form is present. This indicates a step ordering
            bug — the producing step has not run yet.
        """
        if name not in self.forms:
            raise KeyError(
                f"Form '{name}' is not available in the pipeline context. "
                f"Available: {sorted(self.forms.keys())}"
            )
        return self.forms[name]

    def put(self, name: str, form: Any) -> None:
        """Register a form under ``name``.

        The form is validated first. A form that fails ``validate()``
        never enters the context.
        """
        form.validate()
        self.forms[name] = form

    def has(self, name: str) -> bool:
        """Return True if the form is present."""
        return name in self.forms

    # ------------------------------------------------------------------ #
    # Metadata
    # ------------------------------------------------------------------ #

    def record_step(self, name: str, elapsed: float, **extra) -> None:
        """Append a step-timing record to ``metadata['steps']``."""
        self.metadata.setdefault("steps", []).append(
            {"name": name, "elapsed": float(elapsed), **extra}
        )
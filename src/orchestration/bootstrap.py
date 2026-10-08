# src/orchestration/bootstrap.py
"""Pipeline bootstrap: run layout, logging, context construction.

Every pipeline starts the same way: read the manifest, create the
standard directory layout, build a logger, seed the RNG and wrap it
all in a :class:`PipelineContext`. This module centralises that
sequence so individual pipelines do not duplicate it.

The layout follows the Output contract in architecture.md §7.4:

    <task_dir>/
        output/            primary results
        output/figures/    figures
        processed/         intermediate artefacts
        logs/              run.log
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import yaml

from src.orchestration.context import PipelineContext

# Standard subdirectory names.
OUTPUT_SUBDIR = "output"
PROCESSED_SUBDIR = "processed"
FIGURES_SUBDIR = "figures"
LOGS_SUBDIR = "logs"
MANIFEST_FILENAME = "manifest.yaml"


def load_manifest(task_dir: Path) -> dict:
    """Read ``manifest.yaml`` from a task directory.

    Parameters
    ----------
    task_dir : Path
        Task directory containing ``manifest.yaml``.

    Returns
    -------
    dict
        Parsed manifest.

    Raises
    ------
    FileNotFoundError
        If the manifest does not exist.
    """
    task_dir = Path(task_dir)
    path = task_dir / MANIFEST_FILENAME
    if not path.exists():
        raise FileNotFoundError(
            f"Missing manifest: {path}\n"
            f"Run scripts/init_task.py first."
        )
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_logger(pipeline_name: str, log_dir: Path) -> logging.Logger:
    """Create a fresh logger for a pipeline run.

    The logger writes to ``<log_dir>/run.log`` and to stderr. The name
    is namespaced by ``pipeline_name`` so two pipelines in one process
    do not share handlers. Calling this twice with the same name resets
    the handler list rather than duplicating output.
    """
    logger = logging.getLogger(f"biopipe.{pipeline_name}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )

    fh = logging.FileHandler(log_dir / "run.log", encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    return logger


def bootstrap_context(
    task_dir: Path,
    config: dict,
    pipeline_name: str,
) -> PipelineContext:
    """Create the standard run layout and a fully initialised context.

    Parameters
    ----------
    task_dir : Path
        Task directory. Resolved to an absolute path.
    config : dict
        Validated manifest.
    pipeline_name : str
        Pipeline identifier, used to namespace the logger.

    Returns
    -------
    PipelineContext
        Context with directories created, logger attached, RNG seeded,
        and ``metadata['seed']`` recorded.
    """
    task_dir = Path(task_dir).resolve()

    out_dir = task_dir / OUTPUT_SUBDIR
    proc_dir = task_dir / PROCESSED_SUBDIR
    fig_dir = out_dir / FIGURES_SUBDIR
    log_dir = task_dir / LOGS_SUBDIR

    for d in (out_dir, proc_dir, fig_dir, log_dir):
        d.mkdir(parents=True, exist_ok=True)

    logger = build_logger(pipeline_name, log_dir)

    runtime = config.get("runtime", {})
    seed = int(runtime.get("seed", 42))
    device = runtime.get("device", "cpu")

    ctx = PipelineContext(
        config=config,
        task_dir=task_dir,
        out_dir=out_dir,
        proc_dir=proc_dir,
        fig_dir=fig_dir,
        log_dir=log_dir,
        logger=logger,
        rng=np.random.default_rng(seed),
        device=device,
    )
    ctx.metadata["seed"] = seed
    return ctx


__all__ = [
    "load_manifest",
    "build_logger",
    "bootstrap_context",
    "OUTPUT_SUBDIR",
    "PROCESSED_SUBDIR",
    "FIGURES_SUBDIR",
    "LOGS_SUBDIR",
    "MANIFEST_FILENAME",
]
# scripts/run.py
"""Execute a pipeline against a task directory."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.orchestration.bootstrap import load_manifest  # noqa: E402
from src.pipelines import PIPELINES  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Run a BioPipe pipeline."
    )
    ap.add_argument("--task", required=True, help="Task directory.")
    args = ap.parse_args()

    task_dir = Path(args.task).resolve()

    # The manifest declares which pipeline to run. Reading it here
    # keeps this script pipeline-agnostic: it never names a concrete
    # pipeline class.
    try:
        config = load_manifest(task_dir)
    except FileNotFoundError as exc:
        raise SystemExit(str(exc))

    name = config.get("pipeline")
    if name not in PIPELINES:
        raise SystemExit(
            f"Unknown pipeline: '{name}'. "
            f"Available: {list(PIPELINES.keys())}"
        )

    plugin = PIPELINES[name]
    plugin.pipeline_class().run(task_dir)


if __name__ == "__main__":
    main()
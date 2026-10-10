# scripts/run.py
"""Execute a task described by task.yaml."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.reader import read_source  # noqa: E402
from src.task import Context, load_manifest, run  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/run.py <task_dir>")

    task_dir = Path(sys.argv[1]).resolve()
    manifest = load_manifest(task_dir / "task.yaml")
    ctx = Context(task_dir, manifest)

    for name, spec in manifest["sources"].items():
        abs_path = task_dir / spec["path"]
        form = read_source(
            abs_path,
            dims=spec["dims"],
            labels=spec.get("labels", {}),
            **spec.get("args", {}),
        )
        form.validate()
        ctx[name] = form
        print(f"[source] {name}: shape={form.data.shape}, dims={form.dims}")

    try:
        run(ctx, manifest["steps"])
    finally:
        ctx.finalize()

    print("Task finished")
    print(f"  summary : {ctx.out_dir / 'run_summary.txt'}")
    print(f"  json    : {ctx.out_dir / 'run_summary.json'}")


if __name__ == "__main__":
    main()
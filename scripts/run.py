# scripts/run.py
"""Execute a task described by task.yaml."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.reader import pick_reader  # noqa: E402
from src.task import Context, load_manifest, run  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/run.py <task_dir>")

    task_dir = Path(sys.argv[1]).resolve()
    manifest = load_manifest(task_dir / "task.yaml")
    ctx = Context(task_dir, manifest)

    for name, spec in manifest["sources"].items():
        abs_path = task_dir / spec["path"]
        reader = pick_reader(abs_path)
        form = reader.read(
            abs_path,
            dims=spec["dims"],
            labels=spec.get("labels", {}),
            **spec.get("args", {}),
        )
        form.validate()
        ctx[name] = form
        print(f"[source] {name}: shape={form.data.shape}, dims={form.dims}")

    run(ctx, manifest["steps"])
    print("Task finished")


if __name__ == "__main__":
    main()
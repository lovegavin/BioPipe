# scripts/run.py
"""Execute a task described by task.yaml."""

from __future__ import annotations

import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.task import Context, load_manifest, run  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task_dir", type=Path)
    parser.add_argument("--memory-mb", type=float, help="Managed data + workspace budget in MiB")
    parser.add_argument("--process-memory-mb", type=float, help="RSS admission limit in MiB")
    parser.add_argument("--disk-mb", type=float, help="Run-local spill quota in MiB")
    parser.add_argument("--cache-dir", help="Spill parent directory")
    parser.add_argument("--no-auto-spill", action="store_true")
    args = parser.parse_args()
    task_dir = args.task_dir.resolve()
    manifest = load_manifest(task_dir / "task.yaml")
    overrides = {key: value for key, value in (("budget_mb", args.memory_mb),
                  ("process_limit_mb", args.process_memory_mb), ("disk_limit_mb", args.disk_mb),
                  ("cache_dir", args.cache_dir)) if value is not None}
    if overrides or args.no_auto_spill:
        memory = manifest.setdefault("runtime", {}).setdefault("memory", {})
        memory.update(overrides)
        memory["enabled"] = True
        if args.no_auto_spill:
            memory["auto_spill"] = False
    ctx = Context(task_dir, manifest)
    try:
        for name, spec in manifest["sources"].items():
            ctx.register_source(name, spec)
        run(ctx, manifest["steps"])
    except BaseException as exc:
        ctx._run_status, ctx._run_error = "failed", exc
        raise
    finally:
        ctx.finalize()

    print("Task finished")
    print(f"  summary : {ctx.out_dir / 'run_summary.txt'}")
    print(f"  json    : {ctx.out_dir / 'run_summary.json'}")


if __name__ == "__main__":
    main()

"""Reproducible real CSV/branch/PCA/cache/CLI verification; no external data.

Run with the project environment: python scripts/verify_memory.py
Generated inputs, logs and verification.json stay in .verification/resource_demo.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parent.parent


def main():
    base = ROOT / ".verification" / "resource_demo"
    base.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["MPLCONFIGDIR"] = str(base / "matplotlib")
    temporary = base / "tmp"
    temporary.mkdir(exist_ok=True)
    env["TMP"] = env["TEMP"] = str(temporary)
    steps = [{"name": "select", "inputs": ["X"], "params": {
        "dim": "feature", "labels": [f"f{i}" for i in range(32 if j == 2 else 0, 64 if j == 2 else 32)],
        "output": f"Q{j}"}} for j in range(7)]
    steps += [{"name": "pca", "inputs": ["Q0"], "params": {"dim": "feature", "n_components": 2, "output": "P"}},
              {"name": "concat", "inputs": ["Q1", "Q2"], "params": {"axis": "feature", "output": "merged"}},
              {"name": "select", "inputs": ["X"], "params": {"dim": "feature", "labels": ["f0", "f1"], "output": "Back"}},
              {"name": "describe", "inputs": ["Back"]}]
    data = np.arange(512 * 64, dtype=np.float32).reshape(512, 64) % 17
    tasks = {}
    for mode in ("legacy", "managed"):
        directory = base / mode
        directory.mkdir(exist_ok=True)
        np.savetxt(directory / "data.csv", data, delimiter=",", header=",".join(f"f{i}" for i in range(64)), comments="", fmt="%.0f")
        sources = {"X": {"path": "data.csv", "dims": ["sample", "feature"], "labels": {"feature": "builtin"}}}
        manifest = {"name": "resource_demo", "sources": sources, "steps": steps}
        if mode == "managed":
            sources["unused"] = {"path": "deliberately_absent.csv", "dims": ["sample", "feature"]}
            manifest["runtime"] = {"memory": {"budget_mb": 1.8, "process_limit_mb": 512,
                                                "poll_ms": 5, "chunk_mb": .015625}}
        (directory / "task.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
        tasks[mode] = directory

    def execute(mode):
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / "run.py"), str(tasks[mode])],
                                cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
        log = tasks[mode] / "cli.log"
        log.write_text(result.stdout + result.stderr, encoding="utf-8")
        if result.returncode:
            raise RuntimeError(f"{mode} CLI failed; inspect {log}")
        return json.loads((tasks[mode] / "output" / "run_summary.json").read_text(encoding="utf-8"))

    legacy = execute("legacy")
    first = execute("managed")
    report = json.loads(Path(first["memory_report"]).read_text())
    second = execute("managed")
    assert first["run_id"] != second["run_id"]
    assert Path(first["memory_report"]).is_file()
    assert legacy["n_steps"] == first["n_steps"] == second["n_steps"] == 11
    assert all(s["status"] == "complete" for s in (legacy, first, second))
    for expected, got in zip(legacy["steps"], first["steps"]):
        left = json.loads((tasks["legacy"] / "output" / expected["export_path"]).read_text())
        right = json.loads((tasks["managed"] / "output" / got["export_path"]).read_text())
        if expected["name"] == "describe":
            for key in left["global"]:
                if left["global"][key] is not None:
                    assert np.isclose(left["global"][key], right["global"][key], rtol=2e-6, atol=2e-6)
        elif expected["name"] == "pca":
            np.testing.assert_allclose(left["singular_values"], right["singular_values"], rtol=1e-6)
        else:
            assert left == right
    records = [json.loads(line) for line in Path(report["event_log"]).read_text().splitlines()]
    assert not any(r["event"] == "source_loaded" and r["name"] == "unused" for r in records)
    assert report["event_counts"].get("spill", 0) and report["event_counts"].get("load", 0)
    assert report["admitted_peak_estimate_bytes"] <= report["budget_bytes"]
    final_arrays = {a["name"]: str(Path(a["disk_uri"]) / "data.npy")
                    for a in report["artifacts"] if a["disk_uri"]}
    np.testing.assert_array_equal(np.load(final_arrays["merged"], allow_pickle=False), data)
    summary = {"status": "passed", "checks": ["CLI", "lazy_unused_source", "branch_spill_reload",
                "PCA_equivalence", "concat_equivalence", "stream_describe_equivalence", "run_isolation"],
               "managed_budget_mib": report["budget_bytes"] / 1024**2,
               "managed_peak_mib": report["managed_peak_bytes"] / 1024**2,
               "admitted_peak_estimate_mib": report["admitted_peak_estimate_bytes"] / 1024**2,
               "sampled_process_rss_peak_mib": report["sampled_rss_peak_bytes"] / 1024**2,
               "events": report["event_counts"], "first_run": first["run_id"], "second_run": second["run_id"],
               "memory_report": first["memory_report"], "final_arrays": final_arrays,
               "limitations": "managed budget excludes interpreter baseline; RSS is sampled, not a hard limit"}
    target = base / "verification.json"
    target.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print("Verification:", target)


if __name__ == "__main__":
    main()

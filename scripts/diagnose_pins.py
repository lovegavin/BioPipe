# D:\biopipe\scripts\diagnose_pins.py
"""Report every stored pin and whether it matches the current bundled state."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from biopipe.packages import bundled_state  # noqa: E402

root = Path.home() / ".biopipe" / "studio"
s = bundled_state()
fresh_core = next(p["sha256"] for p in s["packages"] if p["name"] == "biopipe-core")
print(f"current biopipe-core sha256: {fresh_core}")
print()

print("--- jobs ---")
for path in sorted(root.rglob("plugins.lock.json")):
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"  [bad json] {path}: {exc}")
        continue
    core = next((p.get("sha256") for p in doc.get("packages", []) if p.get("name") == "biopipe-core"), None)
    mark = "OK " if core == fresh_core else "OLD"
    print(f"  [{mark}] {path}")
    print(f"          job core = {core}")

print()
print("--- sessions ---")
for path in sorted(root.rglob("*.json")):
    if path.name == "plugins.lock.json":
        continue
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        continue
    if not isinstance(doc, dict):
        continue
    for entry in (doc.get("workspace") or {}).get("documents") or []:
        if not isinstance(entry, dict):
            continue
        graph = entry.get("graph") or {}
        lock = graph.get("plugin_lock") or {}
        if not lock:
            continue
        core = (lock.get("annotate") or {}).get("sha256")
        mark = "OK " if core == fresh_core else "OLD"
        print(f"  [{mark}] {path}")
        print(f"          annotate pinned to = {core}")
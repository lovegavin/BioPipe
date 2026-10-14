# D:\biopipe\scripts\repin_all.py
"""Recursively repin every plugin_lock anywhere in a BioPipe profile."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from biopipe.packages import bundled_state  # noqa: E402

profile = Path.home() / ".biopipe" / "studio"
s = bundled_state()

fresh_lock = {
    "protocol_version": 1,
    "package_protocol_version": 1,
    "packages": s["packages"],
    "descriptors": s["descriptors"],
    "bundled_seen": sorted(p["name"] for p in s["packages"]),
    "generation": "repin",
}
fresh_impl = {d["id"]: d["implementation"] for d in s["descriptors"]}


def repin_locks(obj, stats):
    """Recursively rewrite any dict named plugin_lock."""
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            if k == "plugin_lock" and isinstance(v, dict):
                for key, old in list(v.items()):
                    new = fresh_impl.get(key, old)
                    if new != old:
                        v[key] = new
                        stats["locks"] += 1
            else:
                repin_locks(v, stats)
    elif isinstance(obj, list):
        for item in obj:
            repin_locks(item, stats)


jobs = 0
files = 0
stats = {"locks": 0}

for path in profile.rglob("*.json"):
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        continue

    # 1) job 的 plugins.lock.json —— 整体换新
    if path.name == "plugins.lock.json" and isinstance(doc, dict) and "packages" in doc:
        path.with_name(path.name + ".bak").write_bytes(path.read_bytes())
        path.write_text(
            json.dumps(fresh_lock, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        jobs += 1
        continue

    # 2) 任何其它 JSON 里出现 plugin_lock 的地方，递归刷
    before = stats["locks"]
    repin_locks(doc, stats)
    if stats["locks"] > before:
        path.with_name(path.name + ".bak").write_bytes(path.read_bytes())
        path.write_text(
            json.dumps(doc, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        files += 1

print(f"repinned jobs: {jobs}, files with locks updated: {files}, lock entries rewritten: {stats['locks']}")
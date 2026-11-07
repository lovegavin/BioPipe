"""Record every dependency probe: interpreter, command, output, verdict.

Run inside the server environment:
    python scripts/diagnose_dependencies.py --json /tmp/deps.json

The JSON file contains one record per operator/Reader: the declared
environment or external tools, the interpreter that was used, the exact import
command, its stdout/stderr and the resulting status. The same records are
appended to a human-readable log so a failed check can never be a mystery.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def descriptors() -> list[dict]:
    from operon.packages import bundled_manifest

    data = bundled_manifest()
    return [descriptor for package in data.get("packages", []) for descriptor in package.get("descriptors", [])]


def describe(entry: dict) -> dict:
    resources = entry.get("resources") or {}
    return {
        "id": entry.get("id"),
        "kind": entry.get("kind"),
        "environment": resources.get("environment"),
        "external_tools": list(resources.get("external_tools") or []),
        "dependency_imports": list(entry.get("dependency_imports") or []),
        "dependencies": list(entry.get("dependencies") or []),
    }


def run_imports(python: str, imports: list[str]) -> tuple[int, str, str]:
    script = ";".join(f"import {name}" for name in imports) or "pass"
    command = [python, "-c", script]
    result = subprocess.run(command, capture_output=True, text=True, timeout=300)
    return result.returncode, result.stdout, result.stderr


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=Path("dependency-diagnosis.json"))
    parser.add_argument("--log", type=Path, default=Path("dependency-diagnosis.log"))
    parser.add_argument("--only", default="", help="comma-separated descriptor ids")
    args = parser.parse_args()

    from operon.environments import resolve

    log_path = args.log.expanduser().resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    only = {item.strip() for item in args.only.split(',') if item.strip()}
    records = []
    started = datetime.now(timezone.utc).isoformat()
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"# dependency diagnosis {started} python={sys.executable}\n")
        for entry in descriptors():
            if only and entry.get('id') not in only:
                continue
            record = describe(entry)
            record["host_python"] = sys.executable
            environment = record["environment"]
            if record["external_tools"]:
                from operon.dependencies import find_tool
                missing = [name for name in record["external_tools"] if find_tool(name) is None]
                record.update(status="failed" if missing else "passed",
                              error=", ".join(f"{name}: not on PATH" for name in missing),
                              command="which " + " ".join(record["external_tools"]))
            elif environment:
                python = resolve(environment)
                record["environment_python"] = str(python) if python else ""
                if python is None:
                    record.update(status="failed", error="environment not installed", command="")
                else:
                    code, out, err = run_imports(str(python), record["dependency_imports"])
                    record.update(status="passed" if code == 0 else "failed",
                                  error="" if code == 0 else (err or out).strip().splitlines()[-1:],
                                  command=f"{python} -c " + ";".join(f"import {name}" for name in record["dependency_imports"]),
                                  stdout=out[-2000:], stderr=err[-4000:])
            else:
                code, out, err = run_imports(sys.executable, record["dependency_imports"])
                record.update(status="passed" if code == 0 else "failed",
                              error="" if code == 0 else (err or out).strip().splitlines()[-1:],
                              command=f"{sys.executable} -c " + ";".join(f"import {name}" for name in record["dependency_imports"]),
                              stdout=out[-2000:], stderr=err[-4000:])
            records.append(record)
            log.write(json.dumps(record, ensure_ascii=False) + "\n")

    args.json.write_text(json.dumps({"started": started, "records": records}, ensure_ascii=False, indent=2))
    failing = [record for record in records if record["status"] != "passed"]
    print(f"diagnosed {len(records)} entries; failing {len(failing)}")
    for record in failing:
        print(record["id"], "|", record.get("environment") or record.get("external_tools"), "|", record.get("error"))
    print("log:", log_path)
    print("json:", args.json.resolve())
    return 0 if not failing else 1


if __name__ == "__main__":
    raise SystemExit(main())

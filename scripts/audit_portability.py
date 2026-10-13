"""Reject developer filesystem paths in active source or distributable text files.

Historical output reports and legacy snapshots are not runtime defaults and are
excluded from the source audit. Neither is included in the desktop distribution.
"""
import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".py", ".cs", ".json", ".yaml", ".yml", ".toml", ".md", ".txt",
                 ".ps1", ".cmd", ".bat", ".ini", ".cfg", ".ts", ".tsx", ".js", ".html", ".css", ".csproj"}
# Do not match URL schemes, deliberate traversal fixtures, or computed paths.
LOCAL_PATH = re.compile(r"(?<![A-Za-z0-9_])(?:[A-Za-z]:[\\/]|/(?:home|Users)/)[^\s\"'<>]+")
EXCLUDED = {"__pycache__", "node_modules", "bin", "obj", ".git", ".venv", "venv", ".local", ".tmp", ".verification"}


def active_files(root):
    for folder in ("src", "biopipe", "biopipe_sdk", "desktop", "scripts", "routes", "docs", "examples", "frontend"):
        for file in (root / folder).rglob("*"):
            if not EXCLUDED.intersection(file.relative_to(root).parts) and file.is_file():
                yield file
    for file in root.iterdir():
        if file.is_file():
            yield file
    for file in (root / "tasks").rglob("*"):
        if file.is_file() and "output" not in file.relative_to(root).parts and file.suffix in {".py", ".yaml", ".yml"}:
            yield file


def audit_files(files, root):
    findings = []
    checked = 0
    for file in files:
        if file.suffix.lower() not in TEXT_SUFFIXES:
            continue
        checked += 1
        for number, line in enumerate(file.read_text(encoding="utf-8-sig").splitlines(), 1):
            for match in LOCAL_PATH.finditer(line):
                findings.append({"file": file.relative_to(root).as_posix(), "line": number, "path": match.group()})
    return {"checked": checked, "findings": findings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, help="Audit the actual extracted desktop distribution")
    args = parser.parse_args()
    root = args.package.resolve() if args.package else ROOT
    files = (f for f in root.rglob("*") if f.is_file() and "THIRD_PARTY_NOTICES" not in f.relative_to(root).parts) if args.package else active_files(root)
    result = audit_files(files, root)
    print(json.dumps(result, indent=2))
    raise SystemExit(bool(result["findings"]))


if __name__ == "__main__":
    main()

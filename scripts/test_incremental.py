#!/usr/bin/env python3
"""Run the strict incremental test slice for the current working tree.

The policy is deliberate:

* ordinary reader/operator changes run only the tests that reference the
  changed module, plus the static incremental gate;
* core/dispatch changes refuse to run incrementally and require ``--full``;
* frontend changes run the frontend tests and build;
* ``--full`` is the periodic safety net, not the per-change loop.

This script never rewrites code.  It exits non-zero when a changed module has
no referencing test, when a core path changes, or when any selected command
fails.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = "tests/test_incremental_gate.py"
DOC_TESTS = [
    "tests/test_docs_links.py",
    "tests/test_reference_docs.py",
    "tests/test_portability.py",
]
CORE_PATHS = [
    "src/core/",
    "src/reader/base.py",
    "src/reader/__init__.py",
    "src/reader/disk.py",
    "src/reader/readers/__init__.py",
    "src/task/step/base.py",
    "src/task/step/__init__.py",
    "src/task/step/steps/__init__.py",
    "src/task/runner.py",
    "src/task/manifest.py",
    "src/task/operator_catalog.py",
    "src/task/memory/",
    "src/task/context/",
    "src/web/graph.py",
    "src/web/service.py",
    "biopipe/registry.py",
    "biopipe/packages.py",
    "biopipe/targets.py",
    "biopipe/file_formats.py",
]


def _capture(command: list[str]) -> str:
    result = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, check=True
    )
    return result.stdout


def changed_files() -> list[str]:
    tracked = _capture(["git", "diff", "--name-only", "HEAD"]).splitlines()
    untracked = _capture(["git", "ls-files", "--others", "--exclude-standard"]).splitlines()
    return sorted({line.strip() for line in tracked + untracked if line.strip()})


def _is_core(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix) for prefix in CORE_PATHS)


def _test_texts() -> dict[Path, str]:
    return {
        path: path.read_text(encoding="utf-8", errors="replace")
        for path in (ROOT / "tests").glob("test_*.py")
    }


def _tests_for_module(relative: str, texts: dict[Path, str]) -> list[str]:
    path = ROOT / relative
    if not path.is_file() or path.name.startswith("_"):
        return []
    source = path.read_text(encoding="utf-8", errors="replace")
    stem = path.stem
    classes = re.findall(r"^class\s+(\w+)", source, re.MULTILINE)
    return [
        str(test.relative_to(ROOT))
        for test, text in texts.items()
        if stem in text or any(cls in text for cls in classes)
    ]


def classify(files: list[str]) -> tuple[set[str], list[str], bool, bool]:
    """Return (selected tests, changed modules, frontend, docs touched)."""
    texts = _test_texts()
    selected: set[str] = {GATE}
    modules: list[str] = []
    frontend = False
    docs = False
    for relative in files:
        if _is_core(relative):
            continue
        if relative.startswith(("src/task/step/steps/", "src/reader/readers/")) and relative.endswith(".py"):
            modules.append(relative)
        elif relative.startswith("tests/") and relative.endswith(".py"):
            selected.add(relative)
        elif relative.startswith("frontend/"):
            frontend = True
        elif relative.startswith("docs/") or relative in {
            "README.md",
            "AGENTS.md",
            "biopipe/builtin_packages.json",
            "scripts/build_reference_docs.py",
        }:
            docs = True
        elif relative.startswith("src/") and relative.endswith(".py"):
            # Unknown source file: the static gate still needs to see the tree.
            selected.add(GATE)
    if docs:
        selected.update(DOC_TESTS)
    for module in modules:
        related = _tests_for_module(module, texts)
        if not related:
            if Path(module).name.startswith("_"):
                # Internal helpers are covered through their importing
                # operators/readers; their direct module name is not a test
                # reference. The static gate still validates the generated
                # registry and every imported public module.
                continue
            raise SystemExit(
                f"incremental gate: no test references {module}; add a test or run --full for a reviewed exception"
            )
        selected.update(related)
    return selected, sorted(modules), frontend, docs


def _run(command: list[str], *, env: dict | None = None, cwd: Path | None = None) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd or ROOT, check=True, env=env)


def _ruff(files: list[str]) -> None:
    python_files = [f for f in files if f.endswith(".py")]
    if not python_files:
        return
    executable = Path(sys.executable).with_name("ruff")
    if not executable.is_file():
        found = shutil.which("ruff")
        if not found:
            print("! ruff not found; skipping lint gate", file=sys.stderr)
            return
        executable = Path(found)
    if not executable.is_file():
        print("! ruff not found; skipping lint gate", file=sys.stderr)
        return
    _run([str(executable), "check", "--select", "E9,F", *python_files])


def _new_warning_tests(files: list[str]) -> list[str]:
    return [
        f for f in files
        if f.startswith("tests/") and f.endswith(".py")
    ]


def run_incremental(files: list[str], *, dry_run: bool = False) -> int:
    core = [f for f in files if _is_core(f)]
    if core:
        print("incremental gate: core/dispatch change detected:", file=sys.stderr)
        for relative in core:
            print(f"  {relative}", file=sys.stderr)
        print("run `python scripts/test_incremental.py --full` for this change.", file=sys.stderr)
        return 2
    selected, modules, frontend, _docs = classify(files)
    env = os.environ.copy()
    env["BIPIPE_CHANGED_MODULES"] = os.pathsep.join(modules)
    pytest_command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--strict-config",
        "--strict-markers",
        "-x",
        "-ra",
        *sorted(selected),
    ]
    if dry_run:
        print("incremental files:", *files, sep="\n  ")
        print("changed modules:", *modules, sep="\n  ")
        print("pytest:", " ".join(pytest_command))
        print("frontend:", frontend)
        return 0
    _ruff(files)
    _run(pytest_command, env=env)
    warning_tests = _new_warning_tests(files)
    if warning_tests:
        _run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "--strict-config",
                "--strict-markers",
                "-x",
                "-W",
                "error",
                *sorted(warning_tests),
            ],
            env=env,
        )
    if frontend:
        npm = shutil.which("npm")
        if not npm:
            raise SystemExit("frontend changed but npm is not available")
        _run([npm, "test", "--", "--run"], env=env, cwd=ROOT / "frontend")
        _run([npm, "run", "build"], env=env, cwd=ROOT / "frontend")
    return 0


def run_full() -> int:
    _run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-rs",
            "--timeout=600",
            "--timeout-method=signal",
        ]
    )
    npm = shutil.which("npm")
    if npm:
        _run([npm, "test", "--", "--run"], cwd=ROOT / "frontend")
        _run([npm, "run", "build"], cwd=ROOT / "frontend")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="run the periodic full matrix")
    parser.add_argument("--dry-run", action="store_true", help="print the selection only")
    args = parser.parse_args()
    if args.full:
        return run_full()
    return run_incremental(changed_files(), dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())

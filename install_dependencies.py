#!/usr/bin/env python3
"""Install the dependencies declared by the installed BioPipe operator library.

The Studio "Repair dependencies" button runs the same backend path; this script
makes that path available on a headless server and on Windows.

What it does by default
-----------------------
Runs the library's own dependency session with ``repair=True``. Missing Python
packages are installed into immutable per-operator targets, exactly like the
Studio button. Operator environments, external binaries and databases are
declared separately and are only touched with ``--tools`` / ``--isolated``.

Examples
--------
    ./install-dependencies.sh --profile-dir /srv/biopipe --dry-run
    ./install-dependencies.sh --profile-dir /srv/biopipe
    ./install-dependencies.sh --profile-dir /srv/biopipe --tools
    .\\install-dependencies.ps1 -ProfileDir C:\\BioPipe -DryRun

Nothing here downloads operator weights or databases. Those remain explicit
``resources`` steps so a run never surprises a server with multi-GB traffic.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

TOOLS = (
    "quast",
    "minced",
    "flye",
    "infernal",
    "trnascan-se",
    "foldseek",
    "samtools",
    "bwa",
    "minimap2",
    "dssp",
    "vina",
)
HEAVY_TOOLS = ("antismash", "amrfinderplus")


def say(message: str) -> None:
    print(message, flush=True)


def find_profile(value: str | None) -> Path:
    if value:
        return Path(value).expanduser().resolve()
    env = os.environ.get("BIOPIPE_PROFILE") or os.environ.get("BIOPIPE_STUDIO_HOME")
    if env:
        return Path(env).expanduser().resolve()
    cwd = Path.cwd()
    if (cwd / "server.json").is_file():
        return cwd
    profiles = Path.home() / ".biopipe" / "profiles"
    if profiles.is_dir():
        candidates = sorted(p for p in profiles.iterdir() if (p / "server.json").is_file())
        if len(candidates) == 1:
            return candidates[0].resolve()
        if len(candidates) > 1:
            raise SystemExit(
                "Multiple BioPipe profiles found; pass --profile-dir:\n  "
                + "\n  ".join(str(p) for p in candidates)
            )
    raise SystemExit("No BioPipe profile found; pass --profile-dir <installation root>.")


def read_server(profile: Path) -> dict:
    path = profile / "server.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def find_code_root(profile: Path, server: dict) -> Path:
    for key in ("app_dir", "code_root"):
        value = server.get(key)
        if value and Path(value).is_dir():
            return Path(value).resolve()
    managed = profile / "managed-v1"
    if managed.is_dir():
        for candidate in sorted(managed.glob("code-*")):
            if (candidate / "src").is_dir():
                return candidate.resolve()
    if (profile / "src").is_dir() and (profile / "biopipe").is_dir():
        return profile.resolve()
    here = Path(__file__).resolve().parent
    if (here / "src").is_dir() and (here / "biopipe").is_dir():
        return here
    raise SystemExit("Could not locate the BioPipe code root; pass --code-root.")


def find_python(profile: Path, server: dict, explicit: str | None) -> str | None:
    if explicit:
        return str(Path(explicit).expanduser().resolve())
    for key in ("python", "python_executable"):
        value = server.get(key)
        if value and Path(value).is_file():
            return str(Path(value).resolve())
    if (Path(sys.prefix) / "biopipe").is_dir():
        return sys.executable
    managed = profile / "managed-v1"
    for pattern in ("env-*/bin/python", "env-*/Scripts/python.exe"):
        for candidate in sorted(managed.glob(pattern)):
            if candidate.is_file():
                return str(candidate.resolve())
    return None


def reexec(python: str | None) -> None:
    if not python:
        return
    current = Path(sys.executable).resolve()
    target = Path(python).resolve()
    if current == target:
        return
    say(f"Re-launching with the installation interpreter: {target}")
    os.execv(str(target), [str(target), str(Path(__file__).resolve()), *sys.argv[1:]])


def summarize(snapshot: dict) -> tuple[int, int, list[dict]]:
    entries = snapshot.get("entries", [])
    passed = sum(1 for item in entries if item.get("status") == "passed")
    failed = [item for item in entries if item.get("status") != "passed"]
    return passed, len(entries), failed


def repair_python(code_root: Path, profile: Path, dry_run: bool) -> int:
    if str(code_root) not in sys.path:
        sys.path.insert(0, str(code_root))
    from src.web.profile import make_settings
    from src.web.api import create_app

    frontend = code_root / "frontend" / "dist"
    frontend.mkdir(parents=True, exist_ok=True)
    index = frontend / "index.html"
    if not index.is_file():
        index.write_text("<!doctype html><title>BioPipe</title>\n", encoding="utf-8")

    settings = make_settings(code_root, frontend, profile_dir=str(profile))
    app = create_app(settings)
    service = app.state.service

    service.dependencies.check(repair=False)
    before = service.dependencies.snapshot()
    passed, total, failed = summarize(before)
    say(f"Python dependencies: {passed}/{total} ready, {len(failed)} missing")
    if dry_run:
        for item in failed[:40]:
            say(f"  MISSING {item.get('id')} :: {(item.get('error') or '').strip()[:160]}")
        if len(failed) > 40:
            say(f"  ... {len(failed) - 40} more")
        return 0

    if not failed:
        return 0
    say("Repairing missing Python dependencies (same path as Studio > Repair dependencies)...")
    service.dependencies.check(repair=True)
    after = service.dependencies.snapshot()
    passed, total, failed = summarize(after)
    say(f"Python dependencies after repair: {passed}/{total} ready, {len(failed)} still missing")
    for item in failed:
        say(f"  STILL-MISSING {item.get('id')} :: {(item.get('error') or '').strip()[:160]}")
    return 0 if not failed else 1


def find_conda() -> str | None:
    for name in ("mamba", "micromamba", "conda"):
        found = shutil.which(name)
        if found:
            return found
    for candidate in (
        Path.home() / "miniforge3" / "bin" / "mamba",
        Path.home() / "miniconda3" / "bin" / "conda",
        Path("/opt/conda/bin/conda"),
    ):
        if candidate.is_file():
            return str(candidate)
    return None


def install_tools(profile: Path, dry_run: bool, heavy: bool) -> int:
    conda = find_conda()
    if not conda:
        say("External tools: no mamba/conda found; install miniforge or put tools on PATH.")
        return 1
    target = profile / "managed-v1" / "env-tools"
    packages = list(TOOLS) + (list(HEAVY_TOOLS) if heavy else [])
    command = [
        conda,
        "create",
        "-y",
        "-p",
        str(target),
        "-c",
        "conda-forge",
        "-c",
        "bioconda",
        *packages,
    ]
    say("External tools: " + " ".join(command))
    if dry_run:
        return 0
    result = subprocess.run(command)
    if result.returncode == 0:
        say(f"External tools installed in {target}/bin (found automatically by find_tool).")
    return result.returncode


def environment_manifest(code_root: Path) -> dict:
    for candidate in (
        code_root / "library" / "seed" / "biopipe" / "environments.json",
        code_root / "biopipe" / "environments.json",
    ):
        if candidate.is_file():
            return json.loads(candidate.read_text(encoding="utf-8"))
    return {}


def install_isolated(code_root: Path, profile: Path, dry_run: bool, only: list[str]) -> int:
    manifest = environment_manifest(code_root)
    environments = manifest.get("environments", {})
    if not environments:
        say("Isolated environments: no environments.json found.")
        return 1
    conda = find_conda()
    root = Path(sys.prefix).resolve() / "external"
    failures = 0
    for name, spec in environments.items():
        if only and name not in only:
            continue
        target = root / name
        python = target / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if python.is_file():
            say(f"Isolated {name}: already installed at {target}")
            continue
        if not conda:
            say(f"Isolated {name}: no mamba/conda; create {target} with Python {spec.get('python')} manually.")
            failures += 1
            continue
        command = [
            conda,
            "create",
            "-y",
            "-p",
            str(target),
            "-c",
            "conda-forge",
            f"python={spec.get('python', '3.11')}",
            *[str(item) for item in spec.get("conda_packages", [])],
        ]
        say(f"Isolated {name}: " + " ".join(command))
        if dry_run:
            continue
        created = subprocess.run(command)
        if created.returncode != 0:
            failures += 1
            continue
        pip = target / ("Scripts/pip.exe" if os.name == "nt" else "bin/pip")
        installs: list[tuple[list[str], bool]] = []
        requirements = [str(item) for item in spec.get("requirements", [])]
        wheels = [str(item) for item in spec.get("pip_wheels", [])]
        no_deps = [str(item) for item in spec.get("no_deps", [])]
        if requirements:
            installs.append((requirements, False))
        if wheels:
            installs.append((wheels, False))
        if no_deps:
            installs.append((no_deps, True))
        for packages, bare in installs:
            command = [str(pip), "install", *packages]
            if bare:
                command.insert(2, "--no-deps")
            say(f"Isolated {name}: " + " ".join(command))
            if subprocess.run(command).returncode != 0:
                failures += 1
                break
        for weight in spec.get("weights", []) or []:
            say(f"Isolated {name}: weight {weight.get('path')} <- {weight.get('url')} (download manually)")
    return 0 if failures == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--profile-dir", help="BioPipe installation root (contains server.json).")
    parser.add_argument("--code-root", help="Application code directory; auto-detected.")
    parser.add_argument("--python", help="Python executable of the installation; auto-detected.")
    parser.add_argument("--dry-run", action="store_true", help="Probe and print, install nothing.")
    parser.add_argument("--tools", action="store_true", help="Install external binaries into managed-v1/env-tools.")
    parser.add_argument("--heavy", action="store_true", help="Include antiSMASH and AMRFinderPlus (large databases).")
    parser.add_argument("--isolated", action="store_true", help="Create the declared isolated environments.")
    parser.add_argument("--only-isolated", default="", help="Comma-separated isolated environment names.")
    parser.add_argument("--all", action="store_true", help="Python dependencies + tools + isolated environments.")
    args = parser.parse_args()

    profile = find_profile(args.profile_dir)
    server = read_server(profile)
    code_root = Path(args.code_root).expanduser().resolve() if args.code_root else find_code_root(profile, server)
    app_python = find_python(profile, server, args.python)
    reexec(app_python)

    say(f"Profile : {profile}")
    say(f"Code    : {code_root}")
    say(f"Python  : {sys.executable}")

    status = repair_python(code_root, profile, args.dry_run)
    if args.tools or args.all:
        status |= install_tools(profile, args.dry_run, args.heavy)
    if args.isolated or args.all:
        only = [item.strip() for item in args.only_isolated.split(",") if item.strip()]
        status |= install_isolated(code_root, profile, args.dry_run, only)
    return status


if __name__ == "__main__":
    raise SystemExit(main())

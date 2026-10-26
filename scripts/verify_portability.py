"""Windows relocation acceptance: existing Python, no copied virtual environment."""
from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    if os.name != "nt":
        raise SystemExit("Desktop relocation verification requires Windows; use tests/test_portability.py for the engine.")
    distribution = ROOT / "dist/BioPipe Studio"
    if not (distribution / "BioPipe Studio.exe").is_file():
        raise SystemExit("Build the desktop client first: scripts/build_desktop.ps1")
    directory = ROOT / ".verification" / ("move-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    relocated = directory / "BioPipe 中文"
    unrelated = directory / "unrelated cwd"
    unrelated.mkdir(parents=True)
    for name in ("src", "scripts", "biopipe", "biopipe_sdk"):
        shutil.copytree(ROOT / name, relocated / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    install = relocated / "dist/BioPipe Studio"
    shutil.copytree(distribution, install)
    # Use the distributable template, never a developer's private override.
    configuration = json.loads((ROOT / "desktop/biopipe-desktop.json").read_text(encoding="utf-8-sig"))
    config_file = install / "biopipe-desktop.json"
    config_file.write_text(json.dumps(configuration, indent=2), encoding="utf-8")
    executable = install / "BioPipe Studio.exe"
    assert not (relocated / ".venv").exists()
    startup = subprocess.STARTUPINFO()
    startup.dwFlags = subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    environment = {key: value for key, value in os.environ.items()
                   if key not in ("BIOPIPE_PYTHON", "BIOPIPE_BACKEND_ROOT", "VIRTUAL_ENV", "CONDA_PREFIX", "PYTHONPATH", "PYTHONHOME")}
    environment.update(PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    # Never read or replace the real user's remembered interpreter during tests.
    environment["BIOPIPE_RUNTIME_CONFIG"] = str(directory / "runtime.json")
    # Keep .NET's self-extraction and other transient files in the disposable
    # test profile, including when the test runner restricts the system TEMP.
    temporary = directory / "tmp"
    temporary.mkdir()
    environment.update(TEMP=str(temporary), TMP=str(temporary),
                       DOTNET_BUNDLE_EXTRACT_BASE_DIR=str(directory / "bundle"))
    environment["PATH"] = str(Path(sys.executable).parent) + os.pathsep + environment.get("PATH", "")
    checks = []

    def probe(env, success=True):
        response = subprocess.run([str(executable), "--check-runtime"], cwd=unrelated, env=env,
                                  startupinfo=startup, capture_output=True, text=True, encoding="utf-8", timeout=45)
        if not success:
            assert response.returncode != 0 and response.stderr.strip(), response.stdout
            return response.stderr
        assert response.returncode == 0, response.stdout + response.stderr
        paths = json.loads(response.stdout)
        assert Path(paths["Python"]).samefile(sys.executable), paths
        assert Path(paths["BackendRoot"]) == relocated
        assert Path(paths["EntryPoint"]).is_relative_to(relocated)
        assert Path(paths["Frontend"]).is_relative_to(install)
        return paths

    probe(environment)
    checks.append("Unchanged relative desktop layout, existing interpreter on PATH, unrelated cwd")
    env = dict(environment, BIOPIPE_PYTHON=sys.executable)
    env["PATH"] = ""
    probe(env)
    checks.append("Explicit BIOPIPE_PYTHON works without PATH discovery")
    # Test a relative configured interpreter if both drives match; otherwise the
    # same portable environment-variable form covers a Python on a different drive.
    try:
        configured = os.path.relpath(sys.executable, relocated)
    except ValueError:
        configured = "%PORTABILITY_PYTHON%"
    config_file.write_text(json.dumps({**configuration, "python": configured}), encoding="utf-8")
    probe(dict(environment, PORTABILITY_PYTHON=sys.executable))
    checks.append("Configured relative/expanded interpreter path")
    config_file.write_text(json.dumps(configuration), encoding="utf-8")
    stale = relocated / ".venv/Scripts/python.exe"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"Invalid copied virtual environment for this test")
    probe(environment)
    checks.append("Broken copied virtual environment falls back to a valid discovered environment")
    error = probe(dict(environment, BIOPIPE_PYTHON=str(directory / "missing-python.exe")), success=False)
    assert "missing-python.exe" in error
    checks.append("Invalid explicit interpreter fails with a diagnostic, without silently switching")
    # A bare PATH is no longer proof that the machine has no environment: the
    # host also checks Conda and Windows registrations. The explicit missing
    # interpreter case above is deterministic on every development machine.

    profile = directory / "用户 profile"
    response = subprocess.run([str(executable), "--smoke-test", "--profile-dir", str(profile)],
                              cwd=unrelated, env=environment, startupinfo=startup, timeout=90)
    logs = "\n".join(path.read_text(encoding="utf-8-sig") for path in (profile / "logs").glob("*.log"))
    assert response.returncode == 0, logs
    assert all(message in logs for message in ("Frontend ready", "Draft flushed to workspace", "Backend stopped", "Host stopped")), logs
    assert (profile / "workspace/.studio/workflows/workspace.json").is_file()
    checks.append("Relocated real WebView2 host loads the catalog, saves its draft and shuts down")
    result = {"status": "passed", "relocated_root": str(relocated), "profile": str(profile),
              "python": sys.executable, "checks": checks}
    (ROOT / ".verification/portability-desktop-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

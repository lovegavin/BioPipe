"""Regression: a relocated Windows host can reuse Python without terminal activation."""
from datetime import datetime
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, default=ROOT / "dist/BioPipe Studio/BioPipe Studio.exe")
    args = parser.parse_args()
    directory = ROOT / ".verification" / ("runtime-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    install = directory / "release 中文"
    install.mkdir(parents=True)
    executable = install / "BioPipe Studio.exe"
    shutil.copy2(args.executable, executable)
    configuration = {"backendRoot": str(ROOT), "python": "auto", "entryPoint": "scripts/desktop_server.py",
                     "frontend": str(ROOT / "frontend/dist")}
    (install / "biopipe-desktop.json").write_text(json.dumps(configuration), encoding="utf-8")
    cache = directory / "user home/.biopipe/runtime.json"
    cache.parent.mkdir(parents=True)
    cache.write_text(json.dumps({"schema_version": 1, "python": sys.executable}), encoding="utf-8")
    environment = {k: v for k, v in os.environ.items() if k not in
                   ("BIOPIPE_PYTHON", "BIOPIPE_BACKEND_ROOT", "VIRTUAL_ENV", "CONDA_PREFIX", "PYTHONPATH", "PYTHONHOME")}
    environment.update(PATH="", BIOPIPE_RUNTIME_CONFIG=str(cache), PYTHONIOENCODING="utf-8")
    checks = []

    def probe(env, success=True):
        result = subprocess.run([str(executable), "--check-runtime"], cwd=directory, env=env,
                                capture_output=True, text=True, encoding="utf-8", timeout=45,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        if not success:
            assert result.returncode != 0 and result.stderr, result.stdout
            return result.stderr
        assert result.returncode == 0, result.stdout + result.stderr
        paths = json.loads(result.stdout)
        assert Path(paths["Python"]).samefile(sys.executable), paths
        assert Path(paths["BackendRoot"]) == ROOT
        return paths

    before = cache.read_bytes()
    probe(environment)
    assert cache.read_bytes() == before
    checks.append("Remembered environment works with empty PATH, no activated venv, and unrelated cwd")
    error = probe(dict(environment, BIOPIPE_PYTHON=str(directory / "missing-python.exe")), success=False)
    assert "missing-python.exe" in error
    checks.append("An invalid explicit override never silently falls back to remembered Python")
    path_environment = dict(environment, PATH=str(Path(sys.executable).parent))
    for content in ('broken JSON', json.dumps({"schema_version": 1, "python": str(directory / "removed/python.exe")}),
                    json.dumps({"schema_version": 99, "python": sys.executable})):
        cache.write_text(content, encoding="utf-8")
        probe(path_environment)
        assert cache.read_text(encoding="utf-8") == content
    checks.append("Corrupt, removed and unsupported-version runtime records do not block fallback or get rewritten by diagnostics")
    # Conda's own environment registry is discoverable even outside an activated shell.
    cache.unlink()
    conda = directory / "user home/.conda/environments.txt"
    conda.parent.mkdir(parents=True)
    conda.write_text(str(Path(sys.executable).parents[1]) + "\n", encoding="utf-8")
    probe(dict(environment, USERPROFILE=str(directory / "user home")))
    checks.append("Registered Conda/venv prefix is discovered with no PATH or activation")
    # Python startup and the exe share the same bootstrap record format.
    child = subprocess.run([sys.executable, "-c", "from biopipe.runtime import remember_runtime; remember_runtime()"],
                           cwd=ROOT, env=environment, capture_output=True, text=True, encoding="utf-8", timeout=15)
    assert child.returncode == 0, child.stderr
    probe(environment)
    checks.append("Python runtime registration is readable by the relocated desktop host")
    profile = directory / "isolated profile"
    result = subprocess.run([str(executable), "--smoke-test", "--profile-dir", str(profile)],
                            cwd=directory, env=environment, timeout=90, creationflags=subprocess.CREATE_NO_WINDOW)
    logs = "\n".join(p.read_text(encoding="utf-8-sig") for p in (profile / "logs").glob("*.log"))
    assert result.returncode == 0, logs
    assert all(s in logs for s in ("Frontend ready", "Draft flushed to workspace", "Backend stopped", "Host stopped")), logs
    checks.append("Actual WebView2, backend, draft save and shutdown succeed with empty PATH")
    evidence = {"status": "passed", "directory": str(directory), "checks": checks}
    (ROOT / ".verification/runtime-discovery-result.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()

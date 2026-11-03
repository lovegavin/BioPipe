"""Dedicated interpreter environments for operators with conflicting pins."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def manifest_path() -> Path:
    return Path(__file__).with_name('environments.json')


def load() -> dict:
    return json.loads(manifest_path().read_text(encoding='utf-8')).get('environments', {})


def root() -> Path:
    value = os.environ.get('BIOPIPE_ENVIRONMENTS_ROOT')
    if value:
        return Path(value).expanduser()
    return Path(sys.prefix) / 'external'


def describe(name: str) -> dict:
    value = load().get(name)
    if value is None:
        raise ValueError(f'unknown isolated environment: {name}')
    return value


def resolve(name: str) -> Path | None:
    """Return the interpreter of a declared environment, when it exists."""
    env_var = 'BIOPIPE_ENV_' + name.upper()
    candidates = []
    if os.environ.get(env_var):
        candidates.append(Path(os.environ[env_var]).expanduser())
    base = root() / name
    candidates.extend([base / 'bin/python', base / 'Scripts/python.exe'])
    for path in candidates:
        if path.is_file() and os.access(path, os.X_OK):
            return path
    return None


def probe(name: str, imports=None) -> tuple[bool, str, str]:
    entry = describe(name)
    python = resolve(name)
    if python is None:
        return False, '', f'isolated environment {name!r} is not installed under {root() / name}'
    names = imports or entry.get('imports', [])
    script = ';'.join('import ' + module for module in names) or 'pass'
    result = subprocess.run([str(python), '-c', script], capture_output=True, text=True, timeout=300)
    if result.returncode:
        tail = (result.stderr or result.stdout).strip().splitlines()[-1:] or ['import failed']
        return False, str(python), tail[0]
    return True, str(python), ''


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description='Inspect isolated operator environments.')
    parser.add_argument('name', nargs='?')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    names = [args.name] if args.name else sorted(load())
    report = {}
    for name in names:
        ok, python, error = probe(name)
        report[name] = {'ok': ok, 'python': python, 'error': error}
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for name, value in report.items():
            print(('OK   ' if value['ok'] else 'FAIL ') + name, value['python'], value['error'])
    return 0 if all(value['ok'] for value in report.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np


def code_root() -> Path:
    """Locate the checkout that provides both ``biopipe`` and ``src``.

    Managed installs copy the package into ``site-packages`` while the sources
    live in a sibling ``code-<digest>`` directory, so the package parent alone is
    not enough for the worker's ``PYTHONPATH``.
    """
    import os
    import sys
    candidates = []
    if os.environ.get("BIOPIPE_CODE_ROOT"):
        candidates.append(Path(os.environ["BIOPIPE_CODE_ROOT"]))
    import biopipe
    candidates.append(Path(biopipe.__file__).resolve().parent.parent)
    candidates.extend(Path(prefix) for prefix in sys.path if prefix)
    candidates.extend(Path(sys.prefix).resolve().parent.glob("code-*"))
    for candidate in candidates:
        if (candidate / "src/task").is_dir() and (candidate / "biopipe").is_dir():
            return candidate
    raise RuntimeError("cannot locate the BioPipe source tree for the environment bridge")


def _write_form(directory: Path, index: int, form) -> dict:
    data_path = directory / f"input{index}.npy"
    np.save(data_path, np.asarray(form.data))
    meta = {"dims": list(form.dims), "labels": {k: dict(v) for k, v in form.labels.items()},
            "info": _jsonable(form.info)}
    (directory / f"input{index}.json").write_text(json.dumps(meta), encoding="utf-8")
    return meta


def _jsonable(value):
    if hasattr(value, "mapping") and hasattr(value, "inverse"):
        return {"__labelencoder__": dict(value.mapping)}
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def run_step(descriptor: dict, inputs, params: dict, python: Path, *, timeout: int = 3600):
    """Execute one step in ``python`` and return (form, export, console tail)."""
    from src.core.errors import StepError
    directory = Path(tempfile.mkdtemp(prefix="envbridge-"))
    request = {"entry_point": descriptor["entry_point"], "params": params, "inputs": []}
    for index, form in enumerate(inputs):
        request["inputs"].append(_write_form(directory, index, form))
    (directory / "request.json").write_text(json.dumps(request), encoding="utf-8")
    command = [str(python), "-m", "biopipe.env_worker", str(directory)]
    import os
    env = {
        "PYTHONPATH": str(code_root()),
        "PATH": "/usr/bin:/bin",
        "PYTHONNOUSERSITE": "1",
        # Isolated weight downloads use the reachable mirror by default.
        "HF_ENDPOINT": os.environ.get("HF_ENDPOINT", "https://hf-mirror.com"),
        "HF_HOME": os.environ.get("HF_HOME", str(Path.home() / ".cache/huggingface")),
    }
    completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout, env=env)
    if completed.returncode:
        tail = (completed.stderr or completed.stdout).strip().splitlines()[-6:]
        raise StepError("environment bridge failed with exit code " + str(completed.returncode) + ": " + " | ".join(tail))
    message = json.loads((directory / "result.json").read_text(encoding="utf-8"))
    if "error" in message:
        raise StepError(message["error"])
    from src.core.forms import Form
    data = np.load(directory / "output.npy", allow_pickle=False)
    form = Form(data=data, dims=message["dims"], labels=message["labels"], info=message.get("info", {}))
    return form, message.get("export", {}), "\n".join((completed.stderr or "").strip().splitlines()[-4:])


def proxy_step(descriptor: dict):
    """Build a Step-compatible proxy that executes in the environment interpreter."""
    from src.task.step.base import Step
    from src.core.errors import StepError

    class EnvironmentStep(Step):
        name = descriptor["id"]
        input_contracts = descriptor["contracts"]["inputs"]
        output_contract = descriptor["contracts"]["output"]
        supports_streaming = False
        _environment = (descriptor.get("resources") or {}).get("environment")

        def __init__(self):
            self._export_data = {}

        def run(self, ctx, inputs):
            python = resolve(self._environment)
            if python is None:
                raise StepError(f"{descriptor['id']}: isolated environment {self._environment!r} is not installed")
            form, export, tail = run_step(descriptor, inputs, dict(ctx.step_params), python,
                                          timeout=int(ctx.step_params.get("timeout_seconds", 3600)) + 60)
            ctx[ctx.step_params["output"]] = form
            self._export_data = export
            if tail:
                print(tail, file=sys.stderr)

        def export(self, ctx):
            return self._export_data

    return EnvironmentStep

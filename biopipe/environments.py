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

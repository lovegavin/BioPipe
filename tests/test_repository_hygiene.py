"""Runtime state, build output and secrets must never be tracked."""

from __future__ import annotations

import subprocess

FORBIDDEN_PREFIXES = (".studio/", "node_modules/", "dist/", "build/")
FORBIDDEN_SUFFIXES = (".pyc", ".pyo", ".log")
FORBIDDEN_NAMES = {".env", ".env.local", "id_rsa", "id_ed25519", "credentials.json"}


def _tracked():
    output = subprocess.run(["git", "ls-files", "-z"], capture_output=True, text=True, check=True).stdout
    return [item for item in output.split("\0") if item]


def test_no_runtime_state_tracked():
    bad = [path for path in _tracked() if path.startswith(FORBIDDEN_PREFIXES) or path.endswith(FORBIDDEN_SUFFIXES)]
    assert bad == [], f"runtime/build files are tracked: {bad[:12]}"


def test_no_private_key_material_tracked():
    bad = [path for path in _tracked() if path.rsplit("/", 1)[-1] in FORBIDDEN_NAMES]
    assert bad == [], f"credential files are tracked: {bad}"

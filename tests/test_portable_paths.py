"""Tracked paths must be checkable on Windows."""

from __future__ import annotations

import subprocess
from pathlib import Path

RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}
INVALID = set('<>:"|?*')


def _tracked():
    output = subprocess.run(["git", "ls-files", "-z"], capture_output=True, text=True, check=True).stdout
    return [Path(item) for item in output.split("\0") if item]


def test_no_windows_reserved_names():
    bad = [str(path) for path in _tracked() if path.name.split(".")[0].lower() in RESERVED]
    assert bad == [], f"Windows reserved file names are tracked: {bad}"


def test_no_invalid_characters_or_trailing_dots():
    bad = []
    for path in _tracked():
        for part in path.parts:
            if set(part) & INVALID or part.rstrip(" .") != part:
                bad.append(str(path))
                break
    assert bad == [], f"paths with Windows-invalid characters: {bad}"

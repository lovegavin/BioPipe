"""The generated reference must cover every built-in Reader/operator."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_reference_indexes_cover_catalog():
    operators = json.loads((ROOT / "library/seed/operator_index.json").read_text(encoding="utf-8"))
    readers = json.loads((ROOT / "library/seed/reader_index.json").read_text(encoding="utf-8"))
    from operon.packages import bundled_manifest
    descriptors = [descriptor for package in bundled_manifest()['packages'] for descriptor in package['descriptors']]
    assert {entry['id'] for entry in operators} == {d['id'] for d in descriptors if d['kind'] == 'operator'}
    assert {entry['id'] for entry in readers} == {d['id'] for d in descriptors if d['kind'] == 'reader'}
    for entry in operators + readers:
        page = ROOT / "library/seed" / entry["doc"]
        assert page.is_file(), entry["doc"]
        assert "## Purpose" in page.read_text(encoding="utf-8"), entry["doc"]
        descriptor = next(d for d in descriptors if d['id'] == entry['id'])
        assert descriptor['documentation']['status'] == entry['status']


def test_reference_check_mode():
    result = subprocess.run(
        [sys.executable, "scripts/build_operator_docs.py", "--check"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr

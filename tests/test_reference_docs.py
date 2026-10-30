"""The generated reference must cover every built-in Reader/operator."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_reference_indexes_cover_catalog():
    operators = json.loads((ROOT / "docs/reference/operator_index.json").read_text(encoding="utf-8"))
    readers = json.loads((ROOT / "docs/reference/reader_index.json").read_text(encoding="utf-8"))
    assert len(operators) == 200
    assert len(readers) == 76
    for entry in operators + readers:
        page = ROOT / entry["doc"]
        assert page.is_file(), entry["doc"]
        assert "## Processing rules" in page.read_text(encoding="utf-8"), entry["doc"]


def test_reference_check_mode():
    result = subprocess.run(
        [sys.executable, "scripts/build_reference_docs.py", "--check"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr

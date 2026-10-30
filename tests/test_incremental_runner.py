from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _runner():
    path = ROOT / "scripts" / "test_incremental.py"
    spec = importlib.util.spec_from_file_location("biopipe_test_incremental", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_core_changes_refuse_incremental(capsys):
    runner = _runner()
    assert runner._is_core("src/core/forms.py")
    assert runner._is_core("src/reader/base.py")
    assert not runner._is_core("src/reader/readers/wig_reader.py")
    assert runner.run_incremental(["src/core/forms.py"], dry_run=True) == 2
    assert "core/dispatch change" in capsys.readouterr().err


def test_frontend_and_docs_are_classified():
    runner = _runner()
    selected, modules, frontend, docs = runner.classify(["frontend/src/App.tsx", "docs/testing.md"])
    assert frontend is True
    assert docs is True
    assert modules == []
    assert "tests/test_incremental_gate.py" in selected
    assert "tests/test_docs_links.py" in selected
    assert "tests/test_reference_docs.py" in selected
    assert "tests/test_portability.py" in selected


def test_reader_module_maps_to_pick_reader_test():
    runner = _runner()
    selected, modules, frontend, _docs = runner.classify(["src/reader/readers/wig_reader.py"])
    assert modules == ["src/reader/readers/wig_reader.py"]
    assert frontend is False
    assert "tests/test_extension9.py" in selected

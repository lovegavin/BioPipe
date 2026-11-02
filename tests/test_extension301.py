"""boltz_affinity_summary: affinity JSON parsing."""

import json
from pathlib import Path

import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.boltz_affinity_summary import (
    affinity_rows,
    best_summary,
    collect_affinity,
    parse_affinity,
)


def _write(tmp_path, name, payload):
    folder = tmp_path / "predictions" / name
    folder.mkdir(parents=True)
    path = folder / f"affinity_{name}.json"
    path.write_text(json.dumps(payload))
    return path


def test_parse_and_collect(tmp_path):
    first = _write(tmp_path, "run_a", {"affinity_pred_value": -2.5, "affinity_probability_binary": 0.82})
    second = _write(tmp_path, "run_b", {"affinity_pred_value": -1.1, "affinity_probability_binary": 0.35, "affinity_pred_value1": -1.0, "affinity_probability_binary1": 0.4, "affinity_pred_value2": -1.2, "affinity_probability_binary2": 0.3})
    summary = parse_affinity(first)
    assert summary["name"] == "run_a"
    assert summary["affinity_pred_value"] == pytest.approx(-2.5)
    collected = collect_affinity(tmp_path / "predictions")
    assert [item["name"] for item in collected] == ["run_a", "run_b"]
    assert "affinity_pred_value2" in collected[1]
    best = best_summary(collected)
    assert best["best_name"] == "run_a"
    assert best["n_predictions"] == 2
    rows = affinity_rows(collected)
    assert rows[1]["has_variants"] == 1.0


def test_errors(tmp_path):
    with pytest.raises(StepError, match="is not a file"):
        parse_affinity(tmp_path / "missing.json")
    bad = tmp_path / "affinity_bad.json"
    bad.write_text("{not json")
    with pytest.raises(StepError, match="not valid JSON"):
        parse_affinity(bad)
    incomplete = tmp_path / "affinity_incomplete.json"
    incomplete.write_text(json.dumps({"affinity_pred_value": -1.0}))
    with pytest.raises(StepError, match="missing affinity_probability_binary"):
        parse_affinity(incomplete)
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(StepError, match="no affinity_"):
        collect_affinity(empty)


def test_run_matches_contract(tmp_path):
    _write(tmp_path, "run_a", {"affinity_pred_value": -2.5, "affinity_probability_binary": 0.82})
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    run(ctx, [{"name": "boltz_affinity_summary", "params": {"output": "affinity", "affinity_path": str(tmp_path / "predictions")}}])
    result = ctx["affinity"]
    assert result.dims == ["complex", "statistic"]
    assert result.data.shape == (1, 3)
    assert result.labels["complex"] == {"run_a": 0}
    assert result.data[0, 0] == pytest.approx(-2.5)
    assert result.info["best_probability"] == pytest.approx(0.82)


def test_run_requires_path(tmp_path):
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    with pytest.raises(StepError, match="affinity_path is required"):
        run(ctx, [{"name": "boltz_affinity_summary", "params": {"output": "affinity"}}])

# tasks/filter_by_demo/test_filter_by.py
"""Correctness tests for filter_by.

Run:
    python tasks/filter_by_demo/test_filter_by.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.core import Form, StepError                    # noqa: E402
from src.task.step.steps.filter_by import FilterByStep  # noqa: E402


class FakeContext:
    def __init__(self, params):
        self.step_params = dict(params)
        self.forms = {}
        self.metadata = {}

    def __setitem__(self, name, form):
        form.validate()
        self.forms[name] = form

    def __getitem__(self, name):
        return self.forms[name]


def make_data_form(data, dims=("row", "col")):
    """Build a data form. Row labels are r0, r1, ...; col labels c0, c1, ...

    The prefix is the first letter of the dim name, lowercased, so
    'row' -> 'r', 'col' -> 'c', 'cell' -> 'c', 'gene' -> 'g'.
    """
    data = np.asarray(data, dtype=np.float32)
    labels = {}
    for i, d in enumerate(dims):
        prefix = d[0].lower()
        labels[d] = {f"{prefix}{j}": j for j in range(data.shape[i])}
    return Form(
        data=data,
        dims=list(dims),
        labels=labels,
        info={"missing_code": np.nan},
    )


def make_metrics_form(values_by_stat, position_labels):
    """Build a metrics form with dims ['row', 'statistic'].

    values_by_stat: dict {stat_name: list of values}
    position_labels: list of row labels (must match the data form's
                     row labels for the intersection to be non-empty)
    """
    stats = list(values_by_stat.keys())
    data = np.array(
        [values_by_stat[s] for s in stats], dtype=np.float32
    ).T
    return Form(
        data=data,
        dims=["row", "statistic"],
        labels={
            "row": {l: i for i, l in enumerate(position_labels)},
            "statistic": {s: i for i, s in enumerate(stats)},
        },
        info={"missing_code": np.nan},
    )


def run(data_form, metrics_form, params):
    ctx = FakeContext(params)
    step = FilterByStep()
    step.run(ctx, [data_form, metrics_form])
    return ctx.forms[params.get("output", "filter_by")], step.export(ctx)


# ------------------------------------------------------------------ #
# Basic filtering
# ------------------------------------------------------------------ #

def test_min_rule():
    data = np.array([
        [1.0, 2.0],
        [3.0, 4.0],
        [5.0, 6.0],
        [7.0, 8.0],
    ])
    metrics = make_metrics_form(
        {"score": [0.5, 1.5, 2.5, 3.5]},
        ["r0", "r1", "r2", "r3"],
    )
    data_form = make_data_form(data)
    out, exp = run(data_form, metrics, {
        "dim": "row",
        "rules": [{"field": "score", "min": 1.0}],
        "output": "o",
    })
    assert out.data.shape[0] == 3
    assert exp["kept_labels"] == ["r1", "r2", "r3"]
    assert exp["dropped_labels"] == ["r0"]
    assert exp["n_removed"] == 1
    print("PASS test_min_rule")


def test_max_rule():
    data = np.array([
        [1.0, 2.0],
        [3.0, 4.0],
        [5.0, 6.0],
    ])
    metrics = make_metrics_form(
        {"score": [0.5, 1.5, 2.5]},
        ["r0", "r1", "r2"],
    )
    data_form = make_data_form(data)
    out, exp = run(data_form, metrics, {
        "dim": "row",
        "rules": [{"field": "score", "max": 2.0}],
        "output": "o",
    })
    assert out.data.shape[0] == 2
    assert exp["kept_labels"] == ["r0", "r1"]
    print("PASS test_max_rule")


def test_min_and_max():
    data = np.array([
        [1.0], [2.0], [3.0], [4.0], [5.0],
    ])
    metrics = make_metrics_form(
        {"score": [0.1, 0.5, 1.5, 3.0, 5.0]},
        ["r0", "r1", "r2", "r3", "r4"],
    )
    data_form = make_data_form(data)
    out, exp = run(data_form, metrics, {
        "dim": "row",
        "rules": [{"field": "score", "min": 0.5, "max": 3.0}],
        "output": "o",
    })
    assert out.data.shape[0] == 3
    assert exp["kept_labels"] == ["r1", "r2", "r3"]
    print("PASS test_min_and_max")


def test_multiple_rules_and():
    """All rules must pass (logical AND)."""
    data = np.zeros((5, 2), dtype=np.float32)
    metrics = make_metrics_form(
        {
            "a": [1.0, 2.0, 3.0, 4.0, 5.0],
            "b": [5.0, 4.0, 3.0, 2.0, 1.0],
        },
        ["r0", "r1", "r2", "r3", "r4"],
    )
    data_form = make_data_form(data)
    out, exp = run(data_form, metrics, {
        "dim": "row",
        "rules": [
            {"field": "a", "min": 2.0},
            {"field": "b", "min": 3.0},
        ],
        "output": "o",
    })
    # a >= 2: r1, r2, r3, r4
    # b >= 3: r0, r1, r2
    # AND: r1, r2
    assert exp["kept_labels"] == ["r1", "r2"]
    print("PASS test_multiple_rules_and")


# ------------------------------------------------------------------ #
# Alignment and NaN
# ------------------------------------------------------------------ #

def test_subset_alignment():
    """Only common labels between data and metrics are considered."""
    data = np.zeros((4, 2), dtype=np.float32)   # r0..r3
    # metrics has r1..r3 only
    metrics = Form(
        data=np.array([[1.0], [2.0], [3.0]], dtype=np.float32),
        dims=["row", "statistic"],
        labels={
            "row": {"r1": 0, "r2": 1, "r3": 2},
            "statistic": {"score": 0},
        },
        info={"missing_code": np.nan},
    )
    data_form = make_data_form(data)
    out, exp = run(data_form, metrics, {
        "dim": "row",
        "rules": [{"field": "score", "min": 2.0}],
        "output": "o",
    })
    assert exp["n_common"] == 3
    assert exp["kept_labels"] == ["r2", "r3"]
    print("PASS test_subset_alignment")


def test_nan_fails_rule():
    """A NaN in the metrics column fails any min/max rule."""
    data = np.zeros((3, 2), dtype=np.float32)
    metrics = make_metrics_form(
        {"score": [1.0, np.nan, 3.0]},
        ["r0", "r1", "r2"],
    )
    data_form = make_data_form(data)
    out, exp = run(data_form, metrics, {
        "dim": "row",
        "rules": [{"field": "score", "min": 0.5}],
        "output": "o",
    })
    assert exp["kept_labels"] == ["r0", "r2"]
    assert "r1" in exp["dropped_with_reason"]
    assert "missing" in exp["dropped_with_reason"]["r1"]
    print("PASS test_nan_fails_rule")


def test_dropped_reason_recorded():
    data = np.zeros((3, 1), dtype=np.float32)
    metrics = make_metrics_form(
        {"score": [1.0, 5.0, 10.0]},
        ["r0", "r1", "r2"],
    )
    data_form = make_data_form(data)
    _, exp = run(data_form, metrics, {
        "dim": "row",
        "rules": [{"field": "score", "max": 6.0}],
        "output": "o",
    })
    assert "r2" in exp["dropped_with_reason"]
    assert "max" in exp["dropped_with_reason"]["r2"]
    print("PASS test_dropped_reason_recorded")


# ------------------------------------------------------------------ #
# Labels preserved
# ------------------------------------------------------------------ #

def test_labels_preserved():
    data = np.zeros((4, 3), dtype=np.float32)
    metrics = make_metrics_form(
        {"score": [1.0, 2.0, 3.0, 4.0]},
        ["r0", "r1", "r2", "r3"],
    )
    data_form = make_data_form(data)
    out, _ = run(data_form, metrics, {
        "dim": "row",
        "rules": [{"field": "score", "min": 2.0}],
        "output": "o",
    })
    assert set(out.labels["row"].keys()) == {"r1", "r2", "r3"}
    assert out.labels["col"] == data_form.labels["col"]
    assert out.data.shape == (3, 3)
    print("PASS test_labels_preserved")


def test_axis_info_trimmed():
    """Axis-parallel info on the filtered dim follows the data."""
    data = np.array([
        [1.0, 2.0],
        [3.0, 4.0],
        [5.0, 6.0],
    ])
    data_form = make_data_form(data)
    data_form.info["chrom"] = ["chr1", "chr2", "chr3"]
    data_form.axis_info["row"] = ["chrom"]
    metrics = make_metrics_form(
        {"score": [1.0, 2.0, 3.0]},
        ["r0", "r1", "r2"],
    )
    out, _ = run(data_form, metrics, {
        "dim": "row",
        "rules": [{"field": "score", "min": 2.0}],
        "output": "o",
    })
    assert out.info["chrom"] == ["chr2", "chr3"]
    print("PASS test_axis_info_trimmed")


# ------------------------------------------------------------------ #
# Errors
# ------------------------------------------------------------------ #

def test_all_filtered_raises():
    data = np.zeros((3, 1), dtype=np.float32)
    metrics = make_metrics_form(
        {"score": [1.0, 2.0, 3.0]},
        ["r0", "r1", "r2"],
    )
    data_form = make_data_form(data)
    try:
        run(data_form, metrics, {
            "dim": "row",
            "rules": [{"field": "score", "min": 100.0}],
            "output": "o",
        })
    except StepError as exc:
        assert "every position" in str(exc)
        print("PASS test_all_filtered_raises")
        return
    raise AssertionError("did not raise on empty result")


def test_bad_params_raise():
    data = np.zeros((3, 1), dtype=np.float32)
    metrics = make_metrics_form(
        {"score": [1.0, 2.0, 3.0]},
        ["r0", "r1", "r2"],
    )
    data_form = make_data_form(data)
    for bad in (
        {"rules": [{"field": "score", "min": 1.0}]},   # no dim
        {"dim": "row"},                                 # no rules
        {"dim": "row", "rules": []},
        {"dim": "row", "rules": [{}]},                  # no field
        {"dim": "row", "rules": [{"field": "score"}]},  # no min/max
        {"dim": "row", "rules": [{"field": "nonexistent", "min": 0}]},
        {"dim": "nonexistent", "rules": [{"field": "score", "min": 0}]},
    ):
        try:
            run(data_form, metrics, {**bad, "output": "o"})
        except StepError:
            continue
        raise AssertionError(f"params={bad} did not raise")
    print("PASS test_bad_params_raise")


def main():
    tests = [
        test_min_rule,
        test_max_rule,
        test_min_and_max,
        test_multiple_rules_and,
        test_subset_alignment,
        test_nan_fails_rule,
        test_dropped_reason_recorded,
        test_labels_preserved,
        test_axis_info_trimmed,
        test_all_filtered_raises,
        test_bad_params_raise,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {t.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"ERROR {t.__name__}: {type(exc).__name__}: {exc}")
    print()
    print(f"{len(tests) - failed}/{len(tests)} passed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
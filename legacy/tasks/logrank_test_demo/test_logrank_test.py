# tasks/logrank_test_demo/test_logrank_test.py
"""Correctness tests for logrank_test.

Run:
    python tasks/logrank_test_demo/test_logrank_test.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.core import Form, StepError                    # noqa: E402
from src.reader.readers._encoder import LabelEncoder    # noqa: E402
from src.task.step.steps.logrank_test import (           # noqa: E402
    LogrankTestStep,
)


class FakeContext:
    def __init__(self, params, out_dir):
        self.step_params = dict(params)
        self.forms = {}
        self.metadata = {}
        self.out_dir = Path(out_dir)

    def __setitem__(self, name, form):
        form.validate()
        self.forms[name] = form

    def __getitem__(self, name):
        return self.forms[name]


def make_form(rows):
    """rows: list of dicts {sample, time, event, group}."""
    times = np.array([r["time"] for r in rows], dtype=np.float32)
    events = np.array([r["event"] for r in rows], dtype=np.float32)
    groups_raw = [r["group"] for r in rows]
    encoder = LabelEncoder()
    gcodes = encoder.fit_transform(groups_raw).astype(np.float32)

    data = np.stack([times, events, gcodes], axis=1)
    return Form(
        data=data,
        dims=["sample", "feature"],
        labels={
            "sample": {r["sample"]: i for i, r in enumerate(rows)},
            "feature": {"time": 0, "event": 1, "group": 2},
        },
        info={
            "missing_code": np.nan,
            "encoders": {"feature": {"group": encoder}},
        },
    )


def run(form, params):
    ctx = FakeContext(params, "tasks/logrank_test_demo/output")
    step = LogrankTestStep()
    step.run(ctx, [form])
    return ctx.forms[params.get("output", "logrank_test")], step.export(ctx)


# ------------------------------------------------------------------ #
# Two groups
# ------------------------------------------------------------------ #

def test_two_groups_clear_difference():
    """Two groups with obvious survival difference should yield a
    small p-value."""
    rows = []
    # Group A: early events
    for i in range(10):
        rows.append({
            "sample": f"a{i}",
            "time": 1.0 + i,
            "event": 1,
            "group": "A",
        })
    # Group B: late events
    for i in range(10):
        rows.append({
            "sample": f"b{i}",
            "time": 100.0 + i,
            "event": 1,
            "group": "B",
        })
    form = make_form(rows)
    out, exp = run(form, {
        "time_label": "time", "event_label": "event",
        "group_label": "group",
        "groups": ["A", "B"],
        "output": "out",
    })
    assert exp["groups"] == ["A", "B"]
    assert exp["n_total"] == 20
    assert exp["n_events"] == 20
    # Overall test
    assert exp["overall"]["df"] == 1
    assert exp["overall"]["P"] < 1e-6, exp["overall"]["P"]
    # No pairwise for two groups
    assert exp["pairwise"] == []
    # Form output
    assert out.data.shape == (1, 3)
    assert out.labels["comparison"] == {"overall": 0}
    print("PASS test_two_groups_clear_difference")


def test_two_groups_no_difference():
    """Two groups with identical distributions should yield a large
    p-value."""
    rows = []
    for i in range(20):
        g = "A" if i % 2 == 0 else "B"
        rows.append({
            "sample": f"s{i}",
            "time": float(i + 1),
            "event": 1,
            "group": g,
        })
    form = make_form(rows)
    _, exp = run(form, {
        "time_label": "time", "event_label": "event",
        "group_label": "group",
        "groups": ["A", "B"],
        "output": "out",
    })
    # Perfectly interleaved: no difference
    assert exp["overall"]["P"] > 0.5, exp["overall"]["P"]
    print("PASS test_two_groups_no_difference")


# ------------------------------------------------------------------ #
# Three groups + pairwise
# ------------------------------------------------------------------ #

def test_three_groups_pairwise():
    rows = []
    for i in range(8):
        rows.append({"sample": f"a{i}", "time": 1.0 + i,
                     "event": 1, "group": "A"})
        rows.append({"sample": f"b{i}", "time": 50.0 + i,
                     "event": 1, "group": "B"})
        rows.append({"sample": f"c{i}", "time": 100.0 + i,
                     "event": 1, "group": "C"})
    form = make_form(rows)
    out, exp = run(form, {
        "time_label": "time", "event_label": "event",
        "group_label": "group",
        "groups": ["A", "B", "C"],
        "pairwise": True,
        "output": "out",
    })
    assert exp["groups"] == ["A", "B", "C"]
    assert exp["overall"]["df"] == 2
    assert exp["overall"]["P"] < 1e-6
    # 3 pairwise comparisons
    assert len(exp["pairwise"]) == 3
    labels = {p["comparison"] for p in exp["pairwise"]}
    assert labels == {"A vs B", "A vs C", "B vs C"}
    # All pairwise also significant
    for p in exp["pairwise"]:
        assert p["P"] < 1e-6, p
        assert p["df"] == 1
    # Form has 1 + 3 rows
    assert out.data.shape == (4, 3)
    assert set(out.labels["comparison"].keys()) == {
        "overall", "A vs B", "A vs C", "B vs C"
    }
    print("PASS test_three_groups_pairwise")


def test_pairwise_off_by_default():
    """Without pairwise=true, only the overall row is produced."""
    rows = []
    for i in range(6):
        rows.append({"sample": f"a{i}", "time": 1.0 + i,
                     "event": 1, "group": "A"})
        rows.append({"sample": f"b{i}", "time": 10.0 + i,
                     "event": 1, "group": "B"})
        rows.append({"sample": f"c{i}", "time": 20.0 + i,
                     "event": 1, "group": "C"})
    form = make_form(rows)
    out, exp = run(form, {
        "time_label": "time", "event_label": "event",
        "group_label": "group",
        "groups": ["A", "B", "C"],
        "output": "out",
    })
    assert exp["pairwise"] == []
    assert out.data.shape == (1, 3)
    print("PASS test_pairwise_off_by_default")


# ------------------------------------------------------------------ #
# group_map
# ------------------------------------------------------------------ #

def test_group_map_collapses_substages():
    rows = []
    for i in range(5):
        rows.append({"sample": f"a{i}", "time": 1.0 + i,
                     "event": 1, "group": "Stage IA"})
        rows.append({"sample": f"b{i}", "time": 1.5 + i,
                     "event": 1, "group": "Stage IB"})
        rows.append({"sample": f"c{i}", "time": 100.0 + i,
                     "event": 1, "group": "Stage IIA"})
    form = make_form(rows)
    _, exp = run(form, {
        "time_label": "time", "event_label": "event",
        "group_label": "group",
        "group_map": {
            "Stage IA": "Stage I",
            "Stage IB": "Stage I",
            "Stage IIA": "Stage II",
        },
        "groups": ["Stage I", "Stage II"],
        "output": "out",
    })
    assert exp["groups"] == ["Stage I", "Stage II"]
    assert exp["groups_summary"]["Stage I"]["n"] == 10
    assert exp["groups_summary"]["Stage II"]["n"] == 5
    print("PASS test_group_map_collapses_substages")


# ------------------------------------------------------------------ #
# Censoring
# ------------------------------------------------------------------ #

def test_censoring_handled():
    """Censored observations should not count as events."""
    rows = [
        {"sample": "a0", "time": 1.0, "event": 1, "group": "A"},
        {"sample": "a1", "time": 2.0, "event": 0, "group": "A"},
        {"sample": "a2", "time": 3.0, "event": 0, "group": "A"},
        {"sample": "b0", "time": 10.0, "event": 1, "group": "B"},
        {"sample": "b1", "time": 20.0, "event": 0, "group": "B"},
        {"sample": "b2", "time": 30.0, "event": 0, "group": "B"},
    ]
    form = make_form(rows)
    _, exp = run(form, {
        "time_label": "time", "event_label": "event",
        "group_label": "group",
        "groups": ["A", "B"],
        "output": "out",
    })
    assert exp["n_events"] == 2
    assert exp["groups_summary"]["A"]["n_events"] == 1
    assert exp["groups_summary"]["B"]["n_events"] == 1
    print("PASS test_censoring_handled")


# ------------------------------------------------------------------ #
# Errors
# ------------------------------------------------------------------ #

def test_single_group_raises():
    rows = [
        {"sample": "s0", "time": 1.0, "event": 1, "group": "A"},
        {"sample": "s1", "time": 2.0, "event": 0, "group": "A"},
    ]
    form = make_form(rows)
    try:
        run(form, {
            "time_label": "time", "event_label": "event",
            "group_label": "group", "output": "out",
        })
    except StepError as exc:
        assert "at least 2 groups" in str(exc)
        print("PASS test_single_group_raises")
        return
    raise AssertionError("did not raise on single group")


def test_missing_group_raises():
    rows = [
        {"sample": "s0", "time": 1.0, "event": 1, "group": "A"},
        {"sample": "s1", "time": 2.0, "event": 0, "group": "B"},
    ]
    form = make_form(rows)
    try:
        run(form, {
            "time_label": "time", "event_label": "event",
            "group_label": "group",
            "groups": ["A", "C"],
            "output": "out",
        })
    except StepError as exc:
        assert "C" in str(exc)
        print("PASS test_missing_group_raises")
        return
    raise AssertionError("did not raise on missing group")


def test_bad_params_raise():
    rows = [
        {"sample": "s0", "time": 1.0, "event": 1, "group": "A"},
        {"sample": "s1", "time": 2.0, "event": 0, "group": "B"},
    ]
    form = make_form(rows)
    for bad in (
        {"event_label": "event", "group_label": "group"},
        {"time_label": "time", "group_label": "group"},
        {"time_label": "time", "event_label": "event"},
        {"time_label": "nonexistent", "event_label": "event",
         "group_label": "group"},
        {"time_label": "time", "event_label": "event",
         "group_label": "group", "group_map": ["not", "a", "dict"]},
    ):
        try:
            run(form, {**bad, "output": "out"})
        except StepError:
            continue
        raise AssertionError(f"params={bad} did not raise")
    print("PASS test_bad_params_raise")


def test_nan_rows_skipped():
    rows = [
        {"sample": "a0", "time": 1.0, "event": 1, "group": "A"},
        {"sample": "a1", "time": 2.0, "event": 1, "group": "A"},
        {"sample": "b0", "time": 10.0, "event": 1, "group": "B"},
        {"sample": "b1", "time": 20.0, "event": 1, "group": "B"},
    ]
    form = make_form(rows)
    form.data[2, 0] = np.nan    # kill b0's time
    _, exp = run(form, {
        "time_label": "time", "event_label": "event",
        "group_label": "group", "output": "out",
    })
    assert exp["groups_summary"]["B"]["n"] == 1
    assert exp["n_total"] == 3
    print("PASS test_nan_rows_skipped")


def main():
    tests = [
        test_two_groups_clear_difference,
        test_two_groups_no_difference,
        test_three_groups_pairwise,
        test_pairwise_off_by_default,
        test_group_map_collapses_substages,
        test_censoring_handled,
        test_single_group_raises,
        test_missing_group_raises,
        test_bad_params_raise,
        test_nan_rows_skipped,
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
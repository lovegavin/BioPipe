# tasks/diversity_demo/test_diversity.py
"""Correctness tests for diversity.

Run:
    python tasks/diversity_demo/test_diversity.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.core import Form, StepError                    # noqa: E402
from src.task.step.steps.diversity import DiversityStep  # noqa: E402


class FakeContext:
    def __init__(self, params):
        self.step_params = dict(params)
        self.forms = {}
        self.metadata = {}
        self.memory = None

    def __setitem__(self, name, form):
        form.validate()
        self.forms[name] = form

    def __getitem__(self, name):
        return self.forms[name]


def make_form(data, dims=("sample", "species")):
    """Labels use the full dim name as prefix, so 'sample' and
    'species' do not collide."""
    data = np.asarray(data, dtype=np.float32)
    labels = {}
    for i, d in enumerate(dims):
        labels[d] = {
            f"{d}{j}": j for j in range(data.shape[i])
        }
    return Form(
        data=data,
        dims=list(dims),
        labels=labels,
        info={"missing_code": np.nan},
    )


def run(form, params):
    ctx = FakeContext(params)
    step = DiversityStep()
    step.run(ctx, [form])
    return (
        ctx.forms[params.get("output", "diversity")],
        step.export(ctx),
    )


def _col(out, metric):
    idx = out.labels["metric"][metric]
    return out.data[:, idx]


# ------------------------------------------------------------------ #
# Hand-checked metrics
# ------------------------------------------------------------------ #

def test_richness():
    """Richness = number of non-zero entries."""
    data = np.array([
        [10, 0, 5, 0, 3],   # 3 non-zero
        [0, 0, 0, 0, 0],    # 0
        [1, 1, 1, 1, 1],    # 5
    ], dtype=np.float32)
    form = make_form(data)
    out, exp = run(form, {
        "dim": "species", "metrics": ["richness"], "output": "o",
    })
    assert out.dims == ["sample", "metric"]
    assert out.data.shape == (3, 1)
    assert _col(out, "richness").tolist() == [3.0, 0.0, 5.0]
    print("PASS test_richness")


def test_shannon_two_equal():
    """Two equally abundant species: H = log(2)."""
    data = np.array([[50, 50]], dtype=np.float32)
    form = make_form(data)
    out, _ = run(form, {
        "dim": "species", "metrics": ["shannon"], "output": "o",
    })
    assert abs(_col(out, "shannon")[0] - np.log(2)) < 1e-6
    print("PASS test_shannon_two_equal")


def test_shannon_one_species():
    """All in one species: H = 0."""
    data = np.array([[100, 0, 0, 0]], dtype=np.float32)
    form = make_form(data)
    out, _ = run(form, {
        "dim": "species", "metrics": ["shannon"], "output": "o",
    })
    assert abs(_col(out, "shannon")[0]) < 1e-9
    print("PASS test_shannon_one_species")


def test_shannon_four_equal():
    """Four equally abundant species: H = log(4)."""
    data = np.array([[25, 25, 25, 25]], dtype=np.float32)
    form = make_form(data)
    out, _ = run(form, {
        "dim": "species", "metrics": ["shannon"], "output": "o",
    })
    assert abs(_col(out, "shannon")[0] - np.log(4)) < 1e-6
    print("PASS test_shannon_four_equal")


def test_simpson_two_equal():
    """Two equally abundant species: 1 - (1/4 + 1/4) = 0.5."""
    data = np.array([[50, 50]], dtype=np.float32)
    form = make_form(data)
    out, _ = run(form, {
        "dim": "species", "metrics": ["simpson"], "output": "o",
    })
    assert abs(_col(out, "simpson")[0] - 0.5) < 1e-6
    print("PASS test_simpson_two_equal")


def test_simpson_one_species():
    """One species: 1 - 1 = 0."""
    data = np.array([[100, 0, 0]], dtype=np.float32)
    form = make_form(data)
    out, _ = run(form, {
        "dim": "species", "metrics": ["simpson"], "output": "o",
    })
    assert abs(_col(out, "simpson")[0]) < 1e-9
    print("PASS test_simpson_one_species")


def test_evenness_equal():
    """Perfectly even: H / log(S) = 1."""
    data = np.array([[25, 25, 25, 25]], dtype=np.float32)
    form = make_form(data)
    out, _ = run(form, {
        "dim": "species", "metrics": ["evenness"], "output": "o",
    })
    assert abs(_col(out, "evenness")[0] - 1.0) < 1e-6
    print("PASS test_evenness_equal")


def test_evenness_uneven():
    """One species dominates: evenness < 1."""
    data = np.array([[90, 5, 5]], dtype=np.float32)
    form = make_form(data)
    out, _ = run(form, {
        "dim": "species", "metrics": ["evenness"], "output": "o",
    })
    assert 0 < _col(out, "evenness")[0] < 1.0
    print("PASS test_evenness_uneven")


def test_gini_uniform():
    """Perfectly uniform distribution has Gini = 0."""
    data = np.array([[10, 10, 10, 10, 10]], dtype=np.float32)
    form = make_form(data)
    out, _ = run(form, {
        "dim": "species", "metrics": ["gini"], "output": "o",
    })
    assert abs(_col(out, "gini")[0]) < 1e-6
    print("PASS test_gini_uniform")


def test_gini_all_one():
    """All in one species, n=4 valid: Gini = 3/4."""
    data = np.array([[100, 0, 0, 0]], dtype=np.float32)
    form = make_form(data)
    out, _ = run(form, {
        "dim": "species", "metrics": ["gini"], "output": "o",
    })
    assert abs(_col(out, "gini")[0] - 0.75) < 1e-6
    print("PASS test_gini_all_one")


# ------------------------------------------------------------------ #
# Multiple metrics and axis handling
# ------------------------------------------------------------------ #

def test_multiple_metrics_order():
    data = np.array([[50, 50]], dtype=np.float32)
    form = make_form(data)
    out, exp = run(form, {
        "dim": "species",
        "metrics": ["richness", "shannon", "simpson"],
        "output": "o",
    })
    assert out.data.shape == (1, 3)
    assert list(out.labels["metric"].keys()) == [
        "richness", "shannon", "simpson"
    ]
    assert abs(_col(out, "richness")[0] - 2.0) < 1e-6
    assert abs(_col(out, "shannon")[0] - np.log(2)) < 1e-6
    assert abs(_col(out, "simpson")[0] - 0.5) < 1e-6
    print("PASS test_multiple_metrics_order")


def test_metric_as_string():
    data = np.array([[1, 1, 1, 1]], dtype=np.float32)
    form = make_form(data)
    out, _ = run(form, {
        "dim": "species", "metrics": "richness", "output": "o",
    })
    assert _col(out, "richness")[0] == 4.0
    print("PASS test_metric_as_string")


def test_along_sample_dim():
    data = np.array([
        [10, 10, 10],
        [20, 0, 0],
    ], dtype=np.float32)
    form = make_form(data, dims=("sample", "species"))
    out, _ = run(form, {
        "dim": "sample", "metrics": ["richness"], "output": "o",
    })
    assert out.dims == ["species", "metric"]
    # For each species, across the 2 samples: richness of [10,20]=2,
    # [10,0]=1, [10,0]=1
    assert _col(out, "richness").tolist() == [2.0, 1.0, 1.0]
    print("PASS test_along_sample_dim")


def test_nan_skipped():
    data = np.array([
        [50, np.nan, 50, 0],
        [100, 0, 0, 0],
    ], dtype=np.float32)
    form = make_form(data)
    out, _ = run(form, {
        "dim": "species",
        "metrics": ["richness", "shannon"],
        "output": "o",
    })
    # Sample 0: valid = {50, 50, 0}; richness = 2, shannon = log(2)
    # Sample 1: valid = {100, 0, 0}; richness = 1, shannon = 0
    assert _col(out, "richness").tolist() == [2.0, 1.0]
    assert abs(_col(out, "shannon")[0] - np.log(2)) < 1e-6
    print("PASS test_nan_skipped")


def test_zero_total_yields_nan():
    data = np.array([
        [0, 0, 0],
        [10, 10, 10],
    ], dtype=np.float32)
    form = make_form(data)
    out, _ = run(form, {
        "dim": "species", "metrics": ["shannon"], "output": "o",
    })
    assert np.isnan(_col(out, "shannon")[0])
    assert not np.isnan(_col(out, "shannon")[1])
    print("PASS test_zero_total_yields_nan")


# ------------------------------------------------------------------ #
# axis_info
# ------------------------------------------------------------------ #

def test_axis_info_dropped_for_reduced_dim():
    data = np.array([[10, 20, 30]], dtype=np.float32)
    form = make_form(data)
    form.info["batch"] = ["b0"]
    form.axis_info["sample"] = ["batch"]
    out, _ = run(form, {
        "dim": "sample", "metrics": ["richness"], "output": "o",
    })
    assert "batch" not in out.info
    assert "sample" not in out.axis_info
    print("PASS test_axis_info_dropped_for_reduced_dim")


def test_axis_info_kept_for_other_dim():
    data = np.array([[10, 20, 30]], dtype=np.float32)
    form = make_form(data)
    form.info["batch"] = ["b0"]
    form.axis_info["sample"] = ["batch"]
    out, _ = run(form, {
        "dim": "species", "metrics": ["richness"], "output": "o",
    })
    assert out.info.get("batch") == ["b0"]
    print("PASS test_axis_info_kept_for_other_dim")


# ------------------------------------------------------------------ #
# Errors
# ------------------------------------------------------------------ #

def test_bad_params_raise():
    data = np.array([[1, 2, 3]], dtype=np.float32)
    form = make_form(data)
    for bad in (
        {"metrics": ["richness"]},                     # no dim
        {"dim": "species"},                             # no metrics
        {"dim": "species", "metrics": []},
        {"dim": "species", "metrics": ["bogus"]},
        {"dim": "species", "metrics": ["richness", "richness"]},
        {"dim": "nonexistent", "metrics": ["richness"]},
        {"dim": "species", "metrics": 5},
    ):
        try:
            run(form, {**bad, "output": "o"})
        except StepError:
            continue
        raise AssertionError(f"params={bad} did not raise")
    print("PASS test_bad_params_raise")


def main():
    tests = [
        test_richness,
        test_shannon_two_equal,
        test_shannon_one_species,
        test_shannon_four_equal,
        test_simpson_two_equal,
        test_simpson_one_species,
        test_evenness_equal,
        test_evenness_uneven,
        test_gini_uniform,
        test_gini_all_one,
        test_multiple_metrics_order,
        test_metric_as_string,
        test_along_sample_dim,
        test_nan_skipped,
        test_zero_total_yields_nan,
        test_axis_info_dropped_for_reduced_dim,
        test_axis_info_kept_for_other_dim,
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
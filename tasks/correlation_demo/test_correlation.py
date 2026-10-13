# tasks/correlation_demo/test_correlation.py
"""Correctness tests for correlation.

Run:
    python tasks/correlation_demo/test_correlation.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.stats import kendalltau, pearsonr, spearmanr

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.core import Form, StepError                     # noqa: E402
from src.task.step.steps.correlation import CorrelationStep  # noqa: E402


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


def make_form(data, dims=("sample", "feature")):
    data = np.asarray(data, dtype=np.float64)
    labels = {}
    for i, d in enumerate(dims):
        labels[d] = {f"{d}{j}": j for j in range(data.shape[i])}
    return Form(
        data=data,
        dims=list(dims),
        labels=labels,
        info={"missing_code": np.nan},
    )


def run(form, params):
    ctx = FakeContext(params)
    step = CorrelationStep()
    step.run(ctx, [form])
    return (
        ctx.forms[params.get("output", "correlation")],
        step.export(ctx),
    )


# ------------------------------------------------------------------ #
# Structure
# ------------------------------------------------------------------ #

def test_output_shape_and_labels():
    rng = np.random.default_rng(0)
    data = rng.uniform(0, 10, size=(5, 8))
    form = make_form(data, dims=("sample", "feature"))
    out, exp = run(form, {
        "dim": "sample", "metric": "pearson", "output": "o",
    })
    assert out.dims == ["sample", "sample_b"]
    assert out.data.shape == (5, 5)
    assert out.labels["sample"] == form.labels["sample"]
    assert out.labels["sample_b"] == form.labels["sample"]
    print("PASS test_output_shape_and_labels")


def test_diagonal_is_one():
    rng = np.random.default_rng(1)
    data = rng.uniform(0, 10, size=(4, 6))
    form = make_form(data, dims=("sample", "feature"))
    out, _ = run(form, {
        "dim": "sample", "metric": "pearson", "output": "o",
    })
    assert np.allclose(np.diag(out.data), 1.0, atol=1e-6)
    print("PASS test_diagonal_is_one")


def test_symmetric():
    rng = np.random.default_rng(2)
    data = rng.uniform(0, 10, size=(5, 8))
    form = make_form(data, dims=("sample", "feature"))
    out, _ = run(form, {
        "dim": "sample", "metric": "pearson", "output": "o",
    })
    assert np.allclose(out.data, out.data.T, atol=1e-6)
    print("PASS test_symmetric")


# ------------------------------------------------------------------ #
# Metrics vs scipy
# ------------------------------------------------------------------ #

def test_pearson_matches_scipy():
    rng = np.random.default_rng(3)
    data = rng.normal(size=(6, 10))
    form = make_form(data, dims=("sample", "feature"))
    out, _ = run(form, {
        "dim": "sample", "metric": "pearson", "output": "o",
    })
    for i in range(6):
        for j in range(6):
            if i == j:
                continue
            r, _ = pearsonr(data[i], data[j])
            assert abs(out.data[i, j] - r) < 1e-6, (i, j)
    print("PASS test_pearson_matches_scipy")


def test_spearman_matches_scipy():
    rng = np.random.default_rng(4)
    data = rng.normal(size=(5, 12))
    form = make_form(data, dims=("sample", "feature"))
    out, _ = run(form, {
        "dim": "sample", "metric": "spearman", "output": "o",
    })
    for i in range(5):
        for j in range(i + 1, 5):
            r, _ = spearmanr(data[i], data[j])
            assert abs(out.data[i, j] - r) < 1e-6, (i, j)
    print("PASS test_spearman_matches_scipy")


def test_kendall_matches_scipy():
    rng = np.random.default_rng(5)
    data = rng.normal(size=(4, 10))
    form = make_form(data, dims=("sample", "feature"))
    out, _ = run(form, {
        "dim": "sample", "metric": "kendall", "output": "o",
    })
    for i in range(4):
        for j in range(i + 1, 4):
            tau, _ = kendalltau(data[i], data[j])
            assert abs(out.data[i, j] - tau) < 1e-6, (i, j)
    print("PASS test_kendall_matches_scipy")


# ------------------------------------------------------------------ #
# Hand-checked small cases
# ------------------------------------------------------------------ #

def test_pearson_perfect_positive():
    """Identical rows have correlation 1."""
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    data = np.vstack([x, x])
    form = make_form(data, dims=("sample", "feature"))
    out, _ = run(form, {
        "dim": "sample", "metric": "pearson", "output": "o",
    })
    assert abs(out.data[0, 1] - 1.0) < 1e-6
    print("PASS test_pearson_perfect_positive")


def test_pearson_perfect_negative():
    """Opposite rows have correlation -1."""
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    data = np.vstack([x, -x])
    form = make_form(data, dims=("sample", "feature"))
    out, _ = run(form, {
        "dim": "sample", "metric": "pearson", "output": "o",
    })
    assert abs(out.data[0, 1] - (-1.0)) < 1e-6
    print("PASS test_pearson_perfect_negative")


def test_cosine_hand_checked():
    """[1,0] and [0,1] are orthogonal: cosine = 0.
    [1,0] and [1,1]: dot=1, norm1=1, norm2=sqrt(2) -> 1/sqrt(2)."""
    data = np.array([
        [1.0, 0.0],
        [0.0, 1.0],
        [1.0, 1.0],
    ])
    form = make_form(data, dims=("sample", "feature"))
    out, _ = run(form, {
        "dim": "sample", "metric": "cosine",
        "min_valid": 2, "output": "o",
    })
    assert abs(out.data[0, 1] - 0.0) < 1e-6
    expected = 1.0 / np.sqrt(2.0)
    assert abs(out.data[0, 2] - expected) < 1e-6
    print("PASS test_cosine_hand_checked")


def test_jaccard_hand_checked():
    """[1,1,0,0] and [1,0,1,0]: intersection 1, union 3 -> 1/3."""
    data = np.array([
        [1.0, 1.0, 0.0, 0.0],
        [1.0, 0.0, 1.0, 0.0],
    ])
    form = make_form(data, dims=("sample", "feature"))
    out, _ = run(form, {
        "dim": "sample", "metric": "jaccard",
        "min_valid": 2, "output": "o",
    })
    assert abs(out.data[0, 1] - 1.0 / 3.0) < 1e-6
    print("PASS test_jaccard_hand_checked")


def test_overlap_hand_checked():
    """[1,1,0,0] and [1,0,1,0]: intersection 1, min size 2 -> 0.5."""
    data = np.array([
        [1.0, 1.0, 0.0, 0.0],
        [1.0, 0.0, 1.0, 0.0],
    ])
    form = make_form(data, dims=("sample", "feature"))
    out, _ = run(form, {
        "dim": "sample", "metric": "overlap",
        "min_valid": 2, "output": "o",
    })
    assert abs(out.data[0, 1] - 0.5) < 1e-6
    print("PASS test_overlap_hand_checked")


# ------------------------------------------------------------------ #
# NaN handling
# ------------------------------------------------------------------ #

def test_nan_handled_pairwise():
    """NaN cells are dropped pair by pair."""
    data = np.array([
        [1.0, 2.0, np.nan, 4.0],
        [1.0, 2.0, 3.0, 4.0],
    ])
    form = make_form(data, dims=("sample", "feature"))
    out, _ = run(form, {
        "dim": "sample", "metric": "pearson",
        "min_valid": 2, "output": "o",
    })
    # Pairwise on {1,2,4} vs {1,2,4} -> perfect correlation.
    assert abs(out.data[0, 1] - 1.0) < 1e-6
    print("PASS test_nan_handled_pairwise")


def test_min_valid_guard():
    """Pairs with too few shared valid cells yield NaN."""
    data = np.array([
        [1.0, np.nan, np.nan],
        [np.nan, 2.0, np.nan],
    ])
    form = make_form(data, dims=("sample", "feature"))
    out, _ = run(form, {
        "dim": "sample", "metric": "pearson",
        "min_valid": 2, "output": "o",
    })
    # No pair has >= 2 shared valid cells.
    assert np.isnan(out.data[0, 1])
    print("PASS test_min_valid_guard")


# ------------------------------------------------------------------ #
# Errors
# ------------------------------------------------------------------ #

def test_bad_params_raise():
    data = np.array([[1.0, 2.0], [3.0, 4.0]])
    form = make_form(data, dims=("sample", "feature"))
    for bad in (
        {"metric": "pearson"},                          # no dim
        {"dim": "sample", "metric": "bogus"},
        {"dim": "nonexistent", "metric": "pearson"},
        {"dim": "sample", "metric": "pearson", "min_valid": 0},
        {"dim": "sample", "metric": "pearson", "max_positions": 0},
    ):
        try:
            run(form, {**bad, "output": "o"})
        except StepError:
            continue
        raise AssertionError(f"params={bad} did not raise")
    print("PASS test_bad_params_raise")


def test_max_positions_guard():
    data = np.zeros((20, 5), dtype=np.float64)
    form = make_form(data, dims=("sample", "feature"))
    try:
        run(form, {
            "dim": "sample", "metric": "pearson",
            "max_positions": 10, "output": "o",
        })
    except StepError as exc:
        assert "positions" in str(exc)
        print("PASS test_max_positions_guard")
        return
    raise AssertionError("did not raise on too many positions")


def test_single_position_raises():
    data = np.zeros((1, 5), dtype=np.float64)
    form = make_form(data, dims=("sample", "feature"))
    try:
        run(form, {
            "dim": "sample", "metric": "pearson", "output": "o",
        })
    except StepError as exc:
        assert "only" in str(exc)
        print("PASS test_single_position_raises")
        return
    raise AssertionError("did not raise on single position")


def main():
    tests = [
        test_output_shape_and_labels,
        test_diagonal_is_one,
        test_symmetric,
        test_pearson_matches_scipy,
        test_spearman_matches_scipy,
        test_kendall_matches_scipy,
        test_pearson_perfect_positive,
        test_pearson_perfect_negative,
        test_cosine_hand_checked,
        test_jaccard_hand_checked,
        test_overlap_hand_checked,
        test_nan_handled_pairwise,
        test_min_valid_guard,
        test_bad_params_raise,
        test_max_positions_guard,
        test_single_position_raises,
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
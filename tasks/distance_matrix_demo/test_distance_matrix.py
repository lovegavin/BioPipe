# tasks/distance_matrix_demo/test_distance_matrix.py
"""Correctness tests for distance_matrix.

Run:
    python tasks/distance_matrix_demo/test_distance_matrix.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.spatial.distance import cdist

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.core import Form, StepError                        # noqa: E402
from src.task.step.steps.distance_matrix import (            # noqa: E402
    DistanceMatrixStep,
)


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
    data = np.asarray(data, dtype=np.float32)
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
    step = DistanceMatrixStep()
    step.run(ctx, [form])
    return (
        ctx.forms[params.get("output", "distance_matrix")],
        step.export(ctx),
    )


# ------------------------------------------------------------------ #
# Shape / structure
# ------------------------------------------------------------------ #

def test_output_shape_and_labels():
    rng = np.random.default_rng(0)
    data = rng.uniform(0, 10, size=(5, 4)).astype(np.float32)
    form = make_form(data, dims=("sample", "feature"))
    out, exp = run(form, {
        "dim": "sample", "metric": "euclidean", "output": "o",
    })
    assert out.dims == ["sample", "sample_b"]
    assert out.data.shape == (5, 5)
    assert out.labels["sample"] == form.labels["sample"]
    assert out.labels["sample_b"] == form.labels["sample"]
    print("PASS test_output_shape_and_labels")


def test_diagonal_is_zero():
    rng = np.random.default_rng(1)
    data = rng.uniform(0, 10, size=(4, 6)).astype(np.float32)
    form = make_form(data, dims=("sample", "feature"))
    out, _ = run(form, {
        "dim": "sample", "metric": "euclidean", "output": "o",
    })
    assert np.allclose(np.diag(out.data), 0.0, atol=1e-6)
    print("PASS test_diagonal_is_zero")


def test_symmetric():
    rng = np.random.default_rng(2)
    data = rng.uniform(0, 10, size=(5, 8)).astype(np.float32)
    form = make_form(data, dims=("sample", "feature"))
    out, _ = run(form, {
        "dim": "sample", "metric": "euclidean", "output": "o",
    })
    assert np.allclose(out.data, out.data.T, atol=1e-6)
    print("PASS test_symmetric")


# ------------------------------------------------------------------ #
# Metrics vs scipy
# ------------------------------------------------------------------ #

def test_euclidean_matches_scipy():
    rng = np.random.default_rng(3)
    data = rng.uniform(0, 10, size=(6, 5)).astype(np.float32)
    form = make_form(data, dims=("sample", "feature"))
    out, _ = run(form, {
        "dim": "sample", "metric": "euclidean", "output": "o",
    })
    expected = cdist(data.astype(np.float64), data.astype(np.float64),
                     metric="euclidean")
    assert np.allclose(out.data, expected, atol=1e-5)
    print("PASS test_euclidean_matches_scipy")


def test_manhattan_matches_scipy():
    rng = np.random.default_rng(4)
    data = rng.uniform(0, 10, size=(5, 4)).astype(np.float32)
    form = make_form(data, dims=("sample", "feature"))
    out, _ = run(form, {
        "dim": "sample", "metric": "manhattan", "output": "o",
    })
    expected = cdist(data.astype(np.float64), data.astype(np.float64),
                     metric="cityblock")
    assert np.allclose(out.data, expected, atol=1e-5)
    print("PASS test_manhattan_matches_scipy")


def test_cosine_matches_scipy():
    rng = np.random.default_rng(5)
    data = rng.uniform(0.1, 10, size=(5, 6)).astype(np.float32)
    form = make_form(data, dims=("sample", "feature"))
    out, _ = run(form, {
        "dim": "sample", "metric": "cosine", "output": "o",
    })
    expected = cdist(data.astype(np.float64), data.astype(np.float64),
                     metric="cosine")
    assert np.allclose(out.data, expected, atol=1e-5)
    print("PASS test_cosine_matches_scipy")


def test_braycurtis_matches_scipy():
    rng = np.random.default_rng(6)
    data = rng.uniform(0.1, 10, size=(4, 5)).astype(np.float32)
    form = make_form(data, dims=("sample", "feature"))
    out, _ = run(form, {
        "dim": "sample", "metric": "braycurtis", "output": "o",
    })
    expected = cdist(data.astype(np.float64), data.astype(np.float64),
                     metric="braycurtis")
    assert np.allclose(out.data, expected, atol=1e-5)
    print("PASS test_braycurtis_matches_scipy")


# ------------------------------------------------------------------ #
# Hand-checked small cases
# ------------------------------------------------------------------ #

def test_euclidean_hand_checked():
    """Two rows: [0, 0] and [3, 4]. Distance = 5."""
    data = np.array([
        [0.0, 0.0],
        [3.0, 4.0],
    ])
    form = make_form(data, dims=("sample", "feature"))
    out, _ = run(form, {
        "dim": "sample", "metric": "euclidean", "output": "o",
    })
    assert abs(out.data[0, 1] - 5.0) < 1e-6
    assert abs(out.data[1, 0] - 5.0) < 1e-6
    print("PASS test_euclidean_hand_checked")


def test_manhattan_hand_checked():
    """Two rows: [0, 0] and [3, 4]. Manhattan = 7."""
    data = np.array([
        [0.0, 0.0],
        [3.0, 4.0],
    ])
    form = make_form(data, dims=("sample", "feature"))
    out, _ = run(form, {
        "dim": "sample", "metric": "manhattan", "output": "o",
    })
    assert abs(out.data[0, 1] - 7.0) < 1e-6
    print("PASS test_manhattan_hand_checked")


def test_braycurtis_hand_checked():
    """Two rows: [1, 2] and [2, 1]. Bray-Curtis = 2/6 = 1/3."""
    data = np.array([
        [1.0, 2.0],
        [2.0, 1.0],
    ])
    form = make_form(data, dims=("sample", "feature"))
    out, _ = run(form, {
        "dim": "sample", "metric": "braycurtis", "output": "o",
    })
    assert abs(out.data[0, 1] - 1.0 / 3.0) < 1e-6
    print("PASS test_braycurtis_hand_checked")


def test_jaccard_hand_checked():
    """Two rows: [1, 1, 0, 0] and [1, 0, 1, 0].
    Jaccard: intersection = 1, union = 3 -> 1 - 1/3 = 2/3."""
    data = np.array([
        [1.0, 1.0, 0.0, 0.0],
        [1.0, 0.0, 1.0, 0.0],
    ])
    form = make_form(data, dims=("sample", "feature"))
    out, _ = run(form, {
        "dim": "sample", "metric": "jaccard", "output": "o",
    })
    assert abs(out.data[0, 1] - 2.0 / 3.0) < 1e-6
    print("PASS test_jaccard_hand_checked")


def test_hamming_hand_checked():
    """Two rows: [1, 0, 1, 0] and [1, 1, 0, 0].
    Two mismatches out of four -> 0.5."""
    data = np.array([
        [1.0, 0.0, 1.0, 0.0],
        [1.0, 1.0, 0.0, 0.0],
    ])
    form = make_form(data, dims=("sample", "feature"))
    out, _ = run(form, {
        "dim": "sample", "metric": "hamming", "output": "o",
    })
    assert abs(out.data[0, 1] - 0.5) < 1e-6
    print("PASS test_hamming_hand_checked")


# ------------------------------------------------------------------ #
# NaN handling
# ------------------------------------------------------------------ #

def test_nan_filled_with_zero():
    """NaN cells are replaced with 0 before computing distance."""
    data = np.array([
        [1.0, np.nan, 3.0],
        [1.0, 0.0, 3.0],
    ])
    form = make_form(data, dims=("sample", "feature"))
    out, _ = run(form, {
        "dim": "sample", "metric": "euclidean", "output": "o",
    })
    # After filling NaN with 0, both rows are identical.
    assert abs(out.data[0, 1]) < 1e-6
    print("PASS test_nan_filled_with_zero")


# ------------------------------------------------------------------ #
# Axis handling
# ------------------------------------------------------------------ #

def test_axis_second():
    """dim can be any axis."""
    rng = np.random.default_rng(7)
    data = rng.uniform(0, 10, size=(3, 5)).astype(np.float32)
    form = make_form(data, dims=("feature", "sample"))
    out, _ = run(form, {
        "dim": "sample", "metric": "euclidean", "output": "o",
    })
    assert out.dims == ["sample", "sample_b"]
    assert out.data.shape == (5, 5)
    print("PASS test_axis_second")


# ------------------------------------------------------------------ #
# Errors
# ------------------------------------------------------------------ #

def test_bad_params_raise():
    data = np.array([[1, 2, 3], [4, 5, 6]], dtype=np.float32)
    form = make_form(data, dims=("sample", "feature"))
    for bad in (
        {"metric": "euclidean"},                       # no dim
        {"dim": "sample", "metric": "bogus"},
        {"dim": "nonexistent", "metric": "euclidean"},
        {"dim": "sample", "metric": "euclidean", "max_positions": 0},
    ):
        try:
            run(form, {**bad, "output": "o"})
        except StepError:
            continue
        raise AssertionError(f"params={bad} did not raise")
    print("PASS test_bad_params_raise")


def test_max_positions_guard():
    data = np.zeros((20, 5), dtype=np.float32)
    form = make_form(data, dims=("sample", "feature"))
    try:
        run(form, {
            "dim": "sample", "metric": "euclidean",
            "max_positions": 10, "output": "o",
        })
    except StepError as exc:
        assert "positions" in str(exc)
        print("PASS test_max_positions_guard")
        return
    raise AssertionError("did not raise on too many positions")


def test_single_position_raises():
    data = np.zeros((1, 5), dtype=np.float32)
    form = make_form(data, dims=("sample", "feature"))
    try:
        run(form, {
            "dim": "sample", "metric": "euclidean", "output": "o",
        })
    except StepError as exc:
        assert "only" in str(exc)
        print("PASS test_single_position_raises")
        return
    raise AssertionError("did not raise on single position")


def main():
    tests = [
        test_output_shape_and_labels,
        test_diagonal_is_zero,
        test_symmetric,
        test_euclidean_matches_scipy,
        test_manhattan_matches_scipy,
        test_cosine_matches_scipy,
        test_braycurtis_matches_scipy,
        test_euclidean_hand_checked,
        test_manhattan_hand_checked,
        test_braycurtis_hand_checked,
        test_jaccard_hand_checked,
        test_hamming_hand_checked,
        test_nan_filled_with_zero,
        test_axis_second,
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
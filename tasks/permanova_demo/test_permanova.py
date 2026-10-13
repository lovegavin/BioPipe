# tasks/permanova_demo/test_permanova.py
"""Correctness tests for permanova.

Run:
    python tasks/permanova_demo/test_permanova.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.core import Form, StepError                     # noqa: E402
from src.reader.readers._encoder import LabelEncoder     # noqa: E402
from src.task.step.steps.permanova import PermanovaStep  # noqa: E402


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


def make_distance_form(D, sample_names, dim_name="sample"):
    D = np.asarray(D, dtype=np.float32)
    n = D.shape[0]
    labels = {s: i for i, s in enumerate(sample_names)}
    return Form(
        data=D,
        dims=[dim_name, f"{dim_name}_b"],
        labels={
            dim_name: dict(labels),
            f"{dim_name}_b": dict(labels),
        },
        info={"missing_code": np.nan},
    )


def make_meta_form(groups, sample_names, group_dim="sample"):
    enc = LabelEncoder()
    enc.fit_transform(list(groups))
    codes = enc.fit_transform(list(groups)).astype(np.float32)
    return Form(
        data=codes.reshape(-1, 1),
        dims=[group_dim, "feature"],
        labels={
            group_dim: {s: i for i, s in enumerate(sample_names)},
            "feature": {"group": 0},
        },
        info={
            "missing_code": np.nan,
            "encoders": {"feature": {"group": enc}},
        },
    )


def run(dist_form, meta_form, params):
    ctx = FakeContext(params)
    step = PermanovaStep()
    step.run(ctx, [dist_form, meta_form])
    return (
        ctx.forms[params.get("output", "permanova")],
        step.export(ctx),
    )


# ------------------------------------------------------------------ #
# Structure
# ------------------------------------------------------------------ #

def test_basic_structure():
    rng = np.random.default_rng(0)
    n = 12
    D = rng.uniform(0, 1, (n, n))
    D = (D + D.T) / 2
    np.fill_diagonal(D, 0)
    samples = [f"s{i}" for i in range(n)]
    groups = ["A"] * 6 + ["B"] * 6
    dist_form = make_distance_form(D, samples)
    meta_form = make_meta_form(groups, samples)
    out, exp = run(dist_form, meta_form, {
        "dist_dim": "sample", "group_dim": "sample",
        "group_label": "group",
        "n_permutations": 99, "random_state": 0,
        "output": "o",
    })
    assert out.dims == ["comparison", "statistic"]
    assert out.data.shape == (1, 4)
    assert out.labels["comparison"] == {"overall": 0}
    assert out.labels["statistic"] == {
        "F": 0, "R2": 1, "P": 2, "n_perm": 3
    }
    assert exp["n_samples"] == 12
    assert exp["n_permutations"] == 99
    assert 0 < exp["overall"]["P"] <= 1
    print("PASS test_basic_structure")


# ------------------------------------------------------------------ #
# Power: well-separated groups
# ------------------------------------------------------------------ #

def test_separated_groups_significant():
    """Two clusters with small within-group distance but large
    between-group distance should yield a small p-value."""
    n_a, n_b = 6, 6
    n = n_a + n_b
    D = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            same = (i < n_a) == (j < n_a)
            D[i, j] = 1.0 if same else 10.0
    samples = [f"s{i}" for i in range(n)]
    groups = ["A"] * n_a + ["B"] * n_b
    dist_form = make_distance_form(D, samples)
    meta_form = make_meta_form(groups, samples)
    _, exp = run(dist_form, meta_form, {
        "dist_dim": "sample", "group_dim": "sample",
        "group_label": "group",
        "n_permutations": 199, "random_state": 0,
        "output": "o",
    })
    assert exp["overall"]["P"] < 0.05, exp["overall"]["P"]
    assert exp["overall"]["F"] > 5.0
    assert 0 < exp["overall"]["R2"] < 1
    print("PASS test_separated_groups_significant")


def test_no_structure_not_significant():
    """Random grouping on a random distance matrix should have a
    small R2."""
    rng = np.random.default_rng(1)
    n = 12
    D = rng.uniform(0, 1, (n, n))
    D = (D + D.T) / 2
    np.fill_diagonal(D, 0)
    samples = [f"s{i}" for i in range(n)]
    groups = ["A"] * 6 + ["B"] * 6
    dist_form = make_distance_form(D, samples)
    meta_form = make_meta_form(groups, samples)
    _, exp = run(dist_form, meta_form, {
        "dist_dim": "sample", "group_dim": "sample",
        "group_label": "group",
        "n_permutations": 199, "random_state": 0,
        "output": "o",
    })
    assert exp["overall"]["R2"] < 0.4, exp["overall"]["R2"]
    print("PASS test_no_structure_not_significant")


# ------------------------------------------------------------------ #
# Hand-computed F on a tiny example
# ------------------------------------------------------------------ #

def test_hand_computed_f_and_r2():
    """2 + 2 samples, groups A={0,1}, B={2,3}.

    Distances:
        d(0,1) = 2
        d(2,3) = 2
        d(0,2) = d(0,3) = d(1,2) = d(1,3) = 10
        all diagonal = 0, symmetric

    a_ij = d_ij^2 / 2. The code uses a.sum() over the full
    symmetric matrix, which equals 2 * sum_{i<j} a_ij.

    a matrix:
        [[  0,   2,  50,  50],
         [  2,   0,  50,  50],
         [ 50,  50,   0,   2],
         [ 50,  50,   2,   0]]

    a.sum() = 408
    SS_T = 408 / 4 = 102
    SS_W = 4
    SS_A = 98
    F = (98 / 1) / (4 / 2) = 49
    R2 = 98 / 102
    """
    D = np.array([
        [0, 2, 10, 10],
        [2, 0, 10, 10],
        [10, 10, 0, 2],
        [10, 10, 2, 0],
    ], dtype=float)
    samples = ["a0", "a1", "b0", "b1"]
    groups = ["A", "A", "B", "B"]
    dist_form = make_distance_form(D, samples)
    meta_form = make_meta_form(groups, samples)
    _, exp = run(dist_form, meta_form, {
        "dist_dim": "sample", "group_dim": "sample",
        "group_label": "group",
        "n_permutations": 999, "random_state": 0,
        "output": "o",
    })
    assert abs(exp["overall"]["F"] - 49.0) < 1e-4, \
        exp["overall"]["F"]
    assert abs(exp["overall"]["R2"] - 98.0 / 102.0) < 1e-4, \
        exp["overall"]["R2"]
    print("PASS test_hand_computed_f_and_r2")


# ------------------------------------------------------------------ #
# Pairwise
# ------------------------------------------------------------------ #

def test_pairwise_runs():
    """Three groups, well separated -> pairwise tests produced."""
    n_a = n_b = n_c = 5
    n = n_a + n_b + n_c
    D = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            same = (i // 5) == (j // 5)
            D[i, j] = 1.0 if same else 10.0
    samples = [f"s{i}" for i in range(n)]
    groups = ["A"] * n_a + ["B"] * n_b + ["C"] * n_c
    dist_form = make_distance_form(D, samples)
    meta_form = make_meta_form(groups, samples)
    _, exp = run(dist_form, meta_form, {
        "dist_dim": "sample", "group_dim": "sample",
        "group_label": "group",
        "pairwise": True,
        "n_permutations": 199, "random_state": 0,
        "output": "o",
    })
    assert len(exp["pairwise"]) == 3   # A-B, A-C, B-C
    labels = {p["comparison"] for p in exp["pairwise"]}
    assert labels == {"A vs B", "A vs C", "B vs C"}
    print("PASS test_pairwise_runs")


# ------------------------------------------------------------------ #
# Groups argument
# ------------------------------------------------------------------ #

def test_groups_argument_filters():
    n = 10
    rng = np.random.default_rng(2)
    D = rng.uniform(0, 1, (n, n))
    D = (D + D.T) / 2
    np.fill_diagonal(D, 0)
    samples = [f"s{i}" for i in range(n)]
    groups = ["A"] * 4 + ["B"] * 3 + ["C"] * 3
    dist_form = make_distance_form(D, samples)
    meta_form = make_meta_form(groups, samples)
    _, exp = run(dist_form, meta_form, {
        "dist_dim": "sample", "group_dim": "sample",
        "group_label": "group",
        "groups": ["A", "B"],
        "n_permutations": 99, "random_state": 0,
        "output": "o",
    })
    assert exp["groups"] == ["A", "B"]
    # Samples in C are dropped.
    assert exp["n_samples"] == 7
    print("PASS test_groups_argument_filters")


def test_missing_group_raises():
    n = 6
    D = np.zeros((n, n))
    samples = [f"s{i}" for i in range(n)]
    groups = ["A", "A", "A", "B", "B", "B"]
    dist_form = make_distance_form(D, samples)
    meta_form = make_meta_form(groups, samples)
    try:
        run(dist_form, meta_form, {
            "dist_dim": "sample", "group_dim": "sample",
            "group_label": "group",
            "groups": ["A", "Z"],
            "n_permutations": 99, "output": "o",
        })
    except StepError as exc:
        assert "Z" in str(exc)
        print("PASS test_missing_group_raises")
        return
    raise AssertionError("did not raise")


# ------------------------------------------------------------------ #
# P-value and permutation behavior
# ------------------------------------------------------------------ #

def test_p_value_bounds():
    """P must be in (0, 1]."""
    rng = np.random.default_rng(3)
    n = 10
    D = rng.uniform(0, 1, (n, n))
    D = (D + D.T) / 2
    np.fill_diagonal(D, 0)
    samples = [f"s{i}" for i in range(n)]
    groups = ["A"] * 5 + ["B"] * 5
    dist_form = make_distance_form(D, samples)
    meta_form = make_meta_form(groups, samples)
    _, exp = run(dist_form, meta_form, {
        "dist_dim": "sample", "group_dim": "sample",
        "group_label": "group",
        "n_permutations": 199, "random_state": 0,
        "output": "o",
    })
    P = exp["overall"]["P"]
    assert 0 < P <= 1
    # With n_perm=199 and 1 pseudo-count, the minimum possible P is
    # 1 / 200 = 0.005.
    assert P >= 1 / 200 - 1e-9
    print("PASS test_p_value_bounds")


def test_reproducible_with_seed():
    """Same seed gives the same P."""
    rng = np.random.default_rng(4)
    n = 10
    D = rng.uniform(0, 1, (n, n))
    D = (D + D.T) / 2
    np.fill_diagonal(D, 0)
    samples = [f"s{i}" for i in range(n)]
    groups = ["A"] * 5 + ["B"] * 5
    dist_form = make_distance_form(D, samples)
    meta_form = make_meta_form(groups, samples)
    _, exp1 = run(dist_form, meta_form, {
        "dist_dim": "sample", "group_dim": "sample",
        "group_label": "group",
        "n_permutations": 99, "random_state": 42,
        "output": "o",
    })
    _, exp2 = run(dist_form, meta_form, {
        "dist_dim": "sample", "group_dim": "sample",
        "group_label": "group",
        "n_permutations": 99, "random_state": 42,
        "output": "o",
    })
    assert exp1["overall"]["P"] == exp2["overall"]["P"]
    print("PASS test_reproducible_with_seed")


# ------------------------------------------------------------------ #
# Errors
# ------------------------------------------------------------------ #

def test_bad_params_raise():
    n = 6
    D = np.zeros((n, n))
    samples = [f"s{i}" for i in range(n)]
    groups = ["A"] * 3 + ["B"] * 3
    dist_form = make_distance_form(D, samples)
    meta_form = make_meta_form(groups, samples)
    for bad in (
        {"dist_dim": "sample", "group_dim": "sample"},   # no group_label
        {"dist_dim": "sample", "group_dim": "sample",
         "group_label": "group", "n_permutations": 0},
        {"dist_dim": "nonexistent", "group_dim": "sample",
         "group_label": "group"},
        {"dist_dim": "sample", "group_dim": "sample",
         "group_label": "nonexistent"},
    ):
        try:
            run(dist_form, meta_form, {**bad, "output": "o"})
        except StepError:
            continue
        raise AssertionError(f"params={bad} did not raise")
    print("PASS test_bad_params_raise")


def test_single_group_raises():
    n = 4
    D = np.zeros((n, n))
    samples = [f"s{i}" for i in range(n)]
    groups = ["A", "A", "A", "A"]
    dist_form = make_distance_form(D, samples)
    meta_form = make_meta_form(groups, samples)
    try:
        run(dist_form, meta_form, {
            "dist_dim": "sample", "group_dim": "sample",
            "group_label": "group",
            "n_permutations": 99, "output": "o",
        })
    except StepError as exc:
        assert "at least 2 groups" in str(exc)
        print("PASS test_single_group_raises")
        return
    raise AssertionError("did not raise")


def main():
    tests = [
        test_basic_structure,
        test_separated_groups_significant,
        test_no_structure_not_significant,
        test_hand_computed_f_and_r2,
        test_pairwise_runs,
        test_groups_argument_filters,
        test_missing_group_raises,
        test_p_value_bounds,
        test_reproducible_with_seed,
        test_bad_params_raise,
        test_single_group_raises,
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
# tasks/cluster_axis_demo/test_cluster_axis.py
"""Correctness tests for cluster_axis.

Run:
    python tasks/cluster_axis_demo/test_cluster_axis.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.core import Form, StepError                    # noqa: E402
from src.task.step.steps.cluster_axis import (           # noqa: E402
    ClusterAxisStep,
)


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


def make_form(data, dims=("cell", "feature")):
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


def run(form, params):
    ctx = FakeContext(params)
    step = ClusterAxisStep()
    step.run(ctx, [form])
    return ctx.forms[params.get("output", "cluster_axis")], step.export(ctx)


# ------------------------------------------------------------------ #
# KMeans
# ------------------------------------------------------------------ #

def test_kmeans_three_blobs():
    """Three well-separated blobs in 2D become three clusters."""
    rng = np.random.default_rng(0)
    a = rng.normal([0, 0], 0.3, (20, 2))
    b = rng.normal([10, 10], 0.3, (20, 2))
    c = rng.normal([0, 10], 0.3, (20, 2))
    X = np.vstack([a, b, c])
    form = make_form(X, dims=("cell", "feature"))
    out, exp = run(form, {
        "dim": "cell", "method": "kmeans",
        "n_clusters": 3, "random_state": 0, "output": "o",
    })
    assert out.dims == ["cell", "cluster"]
    assert out.data.shape == (60, 1)
    assert exp["n_clusters"] == 3

    c0 = set(out.data[:20, 0].tolist())
    c1 = set(out.data[20:40, 0].tolist())
    c2 = set(out.data[40:60, 0].tolist())
    assert len(c0) == 1
    assert len(c1) == 1
    assert len(c2) == 1
    assert c0 != c1 and c1 != c2 and c2 != c0
    print("PASS test_kmeans_three_blobs")


def test_kmeans_two_clusters_1d():
    """Two groups on a line."""
    X = np.array([
        [0.0], [0.1], [0.2], [0.15],
        [10.0], [10.1], [9.9], [10.05],
    ], dtype=np.float32)
    form = make_form(X, dims=("cell", "feature"))
    out, exp = run(form, {
        "dim": "cell", "method": "kmeans",
        "n_clusters": 2, "output": "o",
    })
    assert exp["n_clusters"] == 2
    assert len(set(out.data[:4, 0].tolist())) == 1
    assert len(set(out.data[4:, 0].tolist())) == 1
    assert out.data[0, 0] != out.data[4, 0]
    print("PASS test_kmeans_two_clusters_1d")


# ------------------------------------------------------------------ #
# Hierarchical
# ------------------------------------------------------------------ #

def test_hierarchical_three_groups():
    rng = np.random.default_rng(1)
    a = rng.normal([0, 0], 0.2, (15, 2))
    b = rng.normal([10, 0], 0.2, (15, 2))
    c = rng.normal([5, 10], 0.2, (15, 2))
    X = np.vstack([a, b, c])
    form = make_form(X, dims=("cell", "feature"))
    out, exp = run(form, {
        "dim": "cell", "method": "hierarchical",
        "n_clusters": 3, "output": "o",
    })
    assert exp["n_clusters"] == 3
    # Each block should be single-cluster
    assert len(set(out.data[:15, 0].tolist())) == 1
    assert len(set(out.data[15:30, 0].tolist())) == 1
    assert len(set(out.data[30:45, 0].tolist())) == 1
    print("PASS test_hierarchical_three_groups")


# ------------------------------------------------------------------ #
# Louvain
# ------------------------------------------------------------------ #

def test_louvain_two_groups():
    try:
        import networkx  # noqa: F401
        from sklearn.neighbors import NearestNeighbors  # noqa: F401
    except ImportError:
        print("SKIP test_louvain_two_groups (deps missing)")
        return
    rng = np.random.default_rng(2)
    # Two dense clusters far apart
    a = rng.normal([0, 0], 0.5, (30, 2))
    b = rng.normal([20, 20], 0.5, (30, 2))
    X = np.vstack([a, b])
    form = make_form(X, dims=("cell", "feature"))
    out, exp = run(form, {
        "dim": "cell", "method": "louvain",
        "n_neighbors": 5, "resolution": 1.0, "random_state": 0,
        "output": "o",
    })
    assert exp["n_positions"] == 60
    # Should find 2-4 clusters; the two main blobs must be separated
    a_labels = set(out.data[:30, 0].tolist())
    b_labels = set(out.data[30:, 0].tolist())
    assert a_labels != b_labels or len(a_labels) > 1
    # The main cluster of block A must not contain any block B point
    # (strongest check: dominant cluster of each block is disjoint)
    from collections import Counter
    ca = Counter(out.data[:30, 0].tolist()).most_common(1)[0][0]
    cb = Counter(out.data[30:, 0].tolist()).most_common(1)[0][0]
    assert ca != cb, (ca, cb)
    print("PASS test_louvain_two_groups")


# ------------------------------------------------------------------ #
# Output structure
# ------------------------------------------------------------------ #

def test_output_shape_and_labels():
    rng = np.random.default_rng(3)
    X = rng.normal(size=(10, 4))
    form = make_form(X, dims=("cell", "feature"))
    out, exp = run(form, {
        "dim": "cell", "method": "kmeans",
        "n_clusters": 2, "output": "o",
    })
    assert out.dims == ["cell", "cluster"]
    assert out.data.shape == (10, 1)
    assert out.labels["cell"] == form.labels["cell"]
    assert out.labels["cluster"] == {"cluster": 0}
    assert len(exp["labels"]) == 10
    assert len(exp["clusters"]) == 10
    print("PASS test_output_shape_and_labels")


def test_cluster_ids_are_sequential():
    """Cluster ids are renumbered 0..n-1."""
    rng = np.random.default_rng(4)
    a = rng.normal([0, 0], 0.2, (10, 2))
    b = rng.normal([5, 5], 0.2, (10, 2))
    c = rng.normal([10, 0], 0.2, (10, 2))
    X = np.vstack([a, b, c])
    form = make_form(X, dims=("cell", "feature"))
    out, exp = run(form, {
        "dim": "cell", "method": "kmeans",
        "n_clusters": 3, "output": "o",
    })
    ids = sorted(set(int(v) for v in out.data[:, 0]))
    assert ids == list(range(exp["n_clusters"]))
    print("PASS test_cluster_ids_are_sequential")


def test_axis_info_ignored():
    """Cluster_axis does not carry axis_info from the input; the
    output form has no parallel info."""
    rng = np.random.default_rng(5)
    X = rng.normal(size=(8, 3))
    form = make_form(X, dims=("cell", "feature"))
    form.info["batch"] = ["b0"] * 8
    form.axis_info["cell"] = ["batch"]
    out, _ = run(form, {
        "dim": "cell", "method": "kmeans",
        "n_clusters": 2, "output": "o",
    })
    assert out.axis_info == {}
    assert out.info == {}
    print("PASS test_axis_info_ignored")


def test_with_nan():
    rng = np.random.default_rng(6)
    X = rng.normal(size=(10, 3))
    X[0, 1] = np.nan
    X[5, 2] = np.nan
    form = make_form(X, dims=("cell", "feature"))
    out, _ = run(form, {
        "dim": "cell", "method": "kmeans",
        "n_clusters": 3, "output": "o",
    })
    assert np.isfinite(out.data).all()
    print("PASS test_with_nan")


# ------------------------------------------------------------------ #
# Errors
# ------------------------------------------------------------------ #

def test_bad_params_raise():
    X = np.zeros((5, 3), dtype=np.float32)
    form = make_form(X, dims=("cell", "feature"))
    for bad in (
        {"method": "kmeans", "n_clusters": 2},       # no dim
        {"dim": "cell", "n_clusters": 2},             # no method
        {"dim": "cell", "method": "bogus", "n_clusters": 2},
        {"dim": "nonexistent", "method": "kmeans", "n_clusters": 2},
        {"dim": "cell", "method": "kmeans"},          # no n_clusters
        {"dim": "cell", "method": "kmeans", "n_clusters": 1},
        {"dim": "cell", "method": "kmeans", "n_clusters": 0},
    ):
        try:
            run(form, {**bad, "output": "o"})
        except StepError:
            continue
        raise AssertionError(f"params={bad} did not raise")
    print("PASS test_bad_params_raise")


def test_1d_rejected():
    data = np.zeros(5, dtype=np.float32)
    form = Form(
        data=data,
        dims=["cell"],
        labels={"cell": {f"c{i}": i for i in range(5)}},
        info={"missing_code": np.nan},
    )
    try:
        run(form, {"dim": "cell", "method": "kmeans",
                   "n_clusters": 2, "output": "o"})
    except StepError as exc:
        assert "at least 2 dims" in str(exc)
        print("PASS test_1d_rejected")
        return
    raise AssertionError("did not raise on 1D input")


def main():
    tests = [
        test_kmeans_three_blobs,
        test_kmeans_two_clusters_1d,
        test_hierarchical_three_groups,
        test_louvain_two_groups,
        test_output_shape_and_labels,
        test_cluster_ids_are_sequential,
        test_axis_info_ignored,
        test_with_nan,
        test_bad_params_raise,
        test_1d_rejected,
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
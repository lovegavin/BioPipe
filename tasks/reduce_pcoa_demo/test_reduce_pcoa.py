# tasks/reduce_pcoa_demo/test_reduce_pcoa.py
"""Correctness tests for reduce (including method='pcoa').

Run:
    python tasks/reduce_pcoa_demo/test_reduce_pcoa.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.core import Form, StepError                # noqa: E402
from src.task.step.steps.reduce import ReduceStep   # noqa: E402


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


def make_feature_form(data, dims=("feature", "sample")):
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


def make_distance_form(D, sample_names, dim_name="sample"):
    """Distance matrices are stored in float64 to avoid float32
    rounding noise being amplified by double centering."""
    D = np.asarray(D, dtype=np.float64)
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


def run(form, params):
    ctx = FakeContext(params)
    step = ReduceStep()
    step.run(ctx, [form])
    return (
        ctx.forms[params.get("output", "reduce")],
        step.export(ctx),
    )


def _euclidean_distance(points):
    """points: (n, d) -> (n, n) Euclidean distance matrix."""
    diff = points[:, None, :] - points[None, :, :]
    return np.sqrt((diff ** 2).sum(axis=2))


# ------------------------------------------------------------------ #
# PCA regression
# ------------------------------------------------------------------ #

def test_pca_still_works():
    rng = np.random.default_rng(0)
    data = rng.normal(size=(5, 20))
    form = make_feature_form(data, dims=("feature", "sample"))
    out, exp = run(form, {
        "dim": "feature", "method": "pca",
        "n_components": 3, "output": "o",
    })
    assert out.dims == ["sample", "component"]
    assert out.data.shape == (20, 3)
    assert exp["input_kind"] == "features"
    assert list(out.labels["component"].keys()) == [
        "PC1", "PC2", "PC3"
    ]
    print("PASS test_pca_still_works")


# ------------------------------------------------------------------ #
# PCoA: hand-checked on a Euclidean-embeddable distance
# ------------------------------------------------------------------ #

def test_pcoa_recovers_1d_coordinates():
    """Points on a line at positions [0, 1, 2, 5]. 1D data has
    exactly one positive eigenvalue in its double-centered matrix,
    so the operator outputs a single component proportional to the
    centered coordinates."""
    xs = np.array([0.0, 1.0, 2.0, 5.0])
    D = np.abs(xs[:, None] - xs[None, :])
    samples = [f"s{i}" for i in range(4)]
    form = make_distance_form(D, samples)
    out, exp = run(form, {
        "dim": "sample", "method": "pcoa",
        "n_components": 3, "output": "o",
    })
    assert out.dims == ["sample", "component"]
    assert out.data.shape == (4, 1)
    assert exp["n_components"] == 1
    assert exp["input_kind"] == "distance"
    assert list(out.labels["component"].keys()) == ["PCo1"]
    assert abs(exp["explained_variance_ratio"][0] - 1.0) < 1e-6

    pco1 = out.data[:, 0]
    centered = xs - xs.mean()
    mask = centered != 0
    ratio = pco1[mask] / centered[mask]
    assert np.allclose(ratio, ratio[0], rtol=1e-4), ratio
    print("PASS test_pcoa_recovers_1d_coordinates")


def test_pcoa_2d_embedded():
    """Points in 2D. PCo1+PCo2 should explain 100%."""
    rng = np.random.default_rng(1)
    xy = rng.normal(size=(8, 2))
    D = _euclidean_distance(xy)
    samples = [f"s{i}" for i in range(8)]
    form = make_distance_form(D, samples)
    out, exp = run(form, {
        "dim": "sample", "method": "pcoa",
        "n_components": 4, "output": "o",
    })
    # 2D data has 2 positive eigenvalues.
    assert exp["n_components"] == 2, exp["n_components"]
    evr = exp["explained_variance_ratio"]
    assert abs(evr[0] + evr[1] - 1.0) < 1e-6, evr
    print("PASS test_pcoa_2d_embedded")


def test_pcoa_3d_embedded():
    """Points in 3D. PCo1+PCo2+PCo3 should explain 100%."""
    rng = np.random.default_rng(2)
    xyz = rng.normal(size=(10, 3))
    D = _euclidean_distance(xyz)
    samples = [f"s{i}" for i in range(10)]
    form = make_distance_form(D, samples)
    _, exp = run(form, {
        "dim": "sample", "method": "pcoa",
        "n_components": 5, "output": "o",
    })
    assert exp["n_components"] == 3, exp["n_components"]
    evr = exp["explained_variance_ratio"]
    assert abs(evr[0] + evr[1] + evr[2] - 1.0) < 1e-6, evr
    print("PASS test_pcoa_3d_embedded")


def test_pcoa_distance_preserved():
    """For a Euclidean distance matrix, the PCoA coordinates must
    reproduce the original distances."""
    rng = np.random.default_rng(3)
    xy = rng.normal(size=(6, 2))
    D = _euclidean_distance(xy)
    samples = [f"s{i}" for i in range(6)]
    form = make_distance_form(D, samples)
    out, _ = run(form, {
        "dim": "sample", "method": "pcoa",
        "n_components": 6, "output": "o",
    })
    # 2D data -> 2 components.
    assert out.data.shape == (6, 2)
    coords = out.data
    recon_diff = coords[:, None, :] - coords[None, :, :]
    D_recon = np.sqrt((recon_diff ** 2).sum(axis=2))
    assert np.allclose(D, D_recon, atol=1e-4), \
        np.abs(D - D_recon).max()
    print("PASS test_pcoa_distance_preserved")


def test_pcoa_component_labels():
    """Component labels use the 'PCo' prefix and sequential numbers."""
    rng = np.random.default_rng(4)
    xyz = rng.normal(size=(6, 3))
    D = _euclidean_distance(xyz)
    samples = [f"s{i}" for i in range(6)]
    form = make_distance_form(D, samples)
    out, _ = run(form, {
        "dim": "sample", "method": "pcoa",
        "n_components": 3, "output": "o",
    })
    assert out.data.shape[1] == 3
    assert list(out.labels["component"].keys()) == [
        "PCo1", "PCo2", "PCo3"
    ]
    print("PASS test_pcoa_component_labels")


def test_pcoa_labels_preserved():
    """Output sample labels match input sample labels."""
    rng = np.random.default_rng(5)
    xyz = rng.normal(size=(4, 3))
    D = _euclidean_distance(xyz)
    samples = ["alpha", "beta", "gamma", "delta"]
    form = make_distance_form(D, samples)
    out, _ = run(form, {
        "dim": "sample", "method": "pcoa",
        "n_components": 3, "output": "o",
    })
    assert out.labels["sample"] == form.labels["sample"]
    print("PASS test_pcoa_labels_preserved")


def test_pcoa_n_components_capped():
    """If n_components exceeds the number of positive eigenvalues,
    k is capped."""
    rng = np.random.default_rng(6)
    xyz = rng.normal(size=(10, 3))
    D = _euclidean_distance(xyz)
    samples = [f"s{i}" for i in range(10)]
    form = make_distance_form(D, samples)
    out, exp = run(form, {
        "dim": "sample", "method": "pcoa",
        "n_components": 100, "output": "o",
    })
    # 3D data -> exactly 3 positive eigenvalues.
    assert exp["n_components"] == 3, exp["n_components"]
    assert out.data.shape == (10, 3)
    print("PASS test_pcoa_n_components_capped")


# ------------------------------------------------------------------ #
# Errors
# ------------------------------------------------------------------ #

def test_pcoa_on_feature_matrix_raises():
    rng = np.random.default_rng(7)
    data = rng.normal(size=(5, 8))
    form = make_feature_form(data, dims=("feature", "sample"))
    try:
        run(form, {
            "dim": "feature", "method": "pcoa", "output": "o",
        })
    except StepError as exc:
        assert "distance" in str(exc)
        print("PASS test_pcoa_on_feature_matrix_raises")
        return
    raise AssertionError("did not raise")


def test_pca_on_distance_matrix_raises():
    rng = np.random.default_rng(8)
    xy = rng.normal(size=(5, 2))
    D = _euclidean_distance(xy)
    samples = [f"s{i}" for i in range(5)]
    form = make_distance_form(D, samples)
    try:
        run(form, {
            "dim": "sample", "method": "pca", "output": "o",
        })
    except StepError as exc:
        assert "pcoa" in str(exc)
        print("PASS test_pca_on_distance_matrix_raises")
        return
    raise AssertionError("did not raise")


def test_non_square_rejected_for_pcoa():
    data = np.array([
        [0, 1, 2],
        [1, 0, 3],
    ], dtype=np.float32)
    form = Form(
        data=data,
        dims=["sample", "sample_b"],
        labels={
            "sample": {"a": 0, "b": 1},
            "sample_b": {"a": 0, "b": 1, "c": 2},
        },
        info={"missing_code": np.nan},
    )
    try:
        run(form, {
            "dim": "sample", "method": "pcoa", "output": "o",
        })
    except StepError:
        print("PASS test_non_square_rejected_for_pcoa")
        return
    raise AssertionError("did not raise")


def main():
    tests = [
        test_pca_still_works,
        test_pcoa_recovers_1d_coordinates,
        test_pcoa_2d_embedded,
        test_pcoa_3d_embedded,
        test_pcoa_distance_preserved,
        test_pcoa_component_labels,
        test_pcoa_labels_preserved,
        test_pcoa_n_components_capped,
        test_pcoa_on_feature_matrix_raises,
        test_pca_on_distance_matrix_raises,
        test_non_square_rejected_for_pcoa,
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
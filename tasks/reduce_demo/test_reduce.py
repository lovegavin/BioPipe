# tasks/reduce_demo/test_reduce.py
"""Correctness tests for reduce.

Run:
    python tasks/reduce_demo/test_reduce.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.core import Form, StepError               # noqa: E402
from src.task.step.steps.reduce import ReduceStep  # noqa: E402


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


def make_form(data, dims=("feature", "sample")):
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
    step = ReduceStep()
    step.run(ctx, [form])
    return ctx.forms[params.get("output", "reduce")], step.export(ctx)


# ------------------------------------------------------------------ #
# PCA
# ------------------------------------------------------------------ #

def test_pca_1d_axis():
    """Data varies only along one feature, so PC1 explains everything."""
    rng = np.random.default_rng(0)
    n = 30
    signal = rng.normal(0, 10, n)
    # 3 features that are all scaled versions of the same signal
    data = np.stack([signal, 2 * signal, -0.5 * signal], axis=0)
    # shape (3 features, 30 samples)
    form = make_form(data, dims=("feature", "sample"))
    out, exp = run(form, {
        "dim": "feature", "method": "pca",
        "n_components": 3, "standardize": False, "output": "o",
    })
    assert out.dims == ["sample", "component"]
    assert out.data.shape == (30, 3)
    assert exp["n_components"] == 3
    # PC1 should explain nearly everything
    evr = exp["explained_variance_ratio"]
    assert evr[0] > 0.99, evr
    print("PASS test_pca_1d_axis")


def test_pca_orthogonal_components():
    """Signals on two orthogonal directions -> PC1 and PC2 split them."""
    rng = np.random.default_rng(1)
    n = 50
    a = rng.normal(0, 5, n)
    b = rng.normal(0, 3, n)
    # 4 features: two load on a, two on b
    data = np.stack([a, a, b, b], axis=0)
    form = make_form(data, dims=("feature", "sample"))
    out, exp = run(form, {
        "dim": "feature", "method": "pca",
        "n_components": 2, "standardize": False, "output": "o",
    })
    evr = exp["explained_variance_ratio"]
    # Two components capture 100% of the variance
    assert evr[0] + evr[1] > 0.99
    assert evr[0] > evr[1]
    print("PASS test_pca_orthogonal_components")


def test_pca_components_ordered():
    """Explained variance is non-increasing."""
    rng = np.random.default_rng(2)
    data = rng.normal(size=(10, 40))
    form = make_form(data, dims=("feature", "sample"))
    _, exp = run(form, {
        "dim": "feature", "method": "pca",
        "n_components": 5, "output": "o",
    })
    evr = exp["explained_variance_ratio"]
    for i in range(len(evr) - 1):
        assert evr[i] >= evr[i + 1], evr
    print("PASS test_pca_components_ordered")


def test_pca_labels_preserved():
    """Output sample labels match input sample labels."""
    rng = np.random.default_rng(3)
    data = rng.normal(size=(5, 20))
    form = make_form(data, dims=("feature", "sample"))
    out, _ = run(form, {
        "dim": "feature", "method": "pca",
        "n_components": 3, "output": "o",
    })
    assert out.labels["sample"] == form.labels["sample"]
    assert set(out.labels["component"].keys()) == {"PC1", "PC2", "PC3"}
    print("PASS test_pca_labels_preserved")


def test_pca_reverse_orientation():
    """Input with the feature axis second still works."""
    rng = np.random.default_rng(4)
    data = rng.normal(size=(20, 5))   # samples x features
    form = make_form(data, dims=("sample", "feature"))
    out, exp = run(form, {
        "dim": "feature", "method": "pca",
        "n_components": 3, "output": "o",
    })
    assert out.dims == ["sample", "component"]
    assert out.data.shape == (20, 3)
    print("PASS test_pca_reverse_orientation")


def test_pca_with_nan():
    """NaN cells are filled with the column mean."""
    rng = np.random.default_rng(5)
    data = rng.normal(size=(4, 15))
    data[0, 3] = np.nan
    data[2, 7] = np.nan
    form = make_form(data, dims=("feature", "sample"))
    out, exp = run(form, {
        "dim": "feature", "method": "pca",
        "n_components": 2, "output": "o",
    })
    assert np.isfinite(out.data).all()
    assert out.data.shape == (15, 2)
    print("PASS test_pca_with_nan")


def test_pca_standardize_affects_result():
    """Standardizing changes the PCA scores."""
    rng = np.random.default_rng(6)
    data = rng.normal(size=(5, 30))
    data[0] *= 100   # one feature has huge scale
    form = make_form(data, dims=("feature", "sample"))

    _, exp_raw = run(form, {
        "dim": "feature", "method": "pca",
        "n_components": 2, "standardize": False, "output": "o1",
    })
    _, exp_std = run(form, {
        "dim": "feature", "method": "pca",
        "n_components": 2, "standardize": True, "output": "o2",
    })
    # The two should give different explained variance ratios
    evr_raw = exp_raw["explained_variance_ratio"][0]
    evr_std = exp_std["explained_variance_ratio"][0]
    assert abs(evr_raw - evr_std) > 1e-3
    print("PASS test_pca_standardize_affects_result")


# ------------------------------------------------------------------ #
# UMAP / t-SNE
# ------------------------------------------------------------------ #

def test_umap_shape_and_labels():
    try:
        import umap  # noqa: F401
    except ImportError:
        print("SKIP test_umap_shape_and_labels (umap-learn not installed)")
        return
    rng = np.random.default_rng(7)
    data = rng.normal(size=(8, 30))
    form = make_form(data, dims=("feature", "sample"))
    out, exp = run(form, {
        "dim": "feature", "method": "umap",
        "n_components": 2, "output": "o",
    })
    assert out.dims == ["sample", "component"]
    assert out.data.shape == (30, 2)
    assert exp["n_components"] == 2
    assert exp["explained_variance_ratio"] is None
    print("PASS test_umap_shape_and_labels")


def test_tsne_shape_and_labels():
    try:
        from sklearn.manifold import TSNE  # noqa: F401
    except ImportError:
        print("SKIP test_tsne_shape_and_labels (scikit-learn not installed)")
        return
    rng = np.random.default_rng(8)
    data = rng.normal(size=(6, 25))
    form = make_form(data, dims=("feature", "sample"))
    out, exp = run(form, {
        "dim": "feature", "method": "tsne",
        "n_components": 2, "perplexity": 5, "output": "o",
    })
    assert out.dims == ["sample", "component"]
    assert out.data.shape == (25, 2)
    print("PASS test_tsne_shape_and_labels")


# ------------------------------------------------------------------ #
# Errors
# ------------------------------------------------------------------ #

def test_bad_params_raise():
    data = np.zeros((3, 10), dtype=np.float32)
    form = make_form(data, dims=("feature", "sample"))
    for bad in (
        {"method": "pca"},                          # no dim
        {"dim": "feature"},                         # no method -> default pca, ok
        {"dim": "feature", "method": "bogus"},
        {"dim": "nonexistent", "method": "pca"},
        {"dim": "feature", "method": "pca", "n_components": 0},
        {"dim": "feature", "method": "pca", "n_components": -1},
    ):
        # skip the one that's actually valid
        if bad == {"dim": "feature"}:
            continue
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
        dims=["x"],
        labels={"x": {f"x{i}": i for i in range(5)}},
        info={"missing_code": np.nan},
    )
    try:
        run(form, {"dim": "x", "output": "o"})
    except StepError as exc:
        assert "2D" in str(exc)
        print("PASS test_1d_rejected")
        return
    raise AssertionError("did not raise on 1D input")


def test_n_components_capped():
    """If n_components exceeds min(shape), k is capped."""
    data = np.zeros((2, 10), dtype=np.float32)
    form = make_form(data, dims=("feature", "sample"))
    out, exp = run(form, {
        "dim": "feature", "method": "pca",
        "n_components": 50, "output": "o",
    })
    assert exp["n_components"] == 2
    assert out.data.shape == (10, 2)
    print("PASS test_n_components_capped")


def main():
    tests = [
        test_pca_1d_axis,
        test_pca_orthogonal_components,
        test_pca_components_ordered,
        test_pca_labels_preserved,
        test_pca_reverse_orientation,
        test_pca_with_nan,
        test_pca_standardize_affects_result,
        test_umap_shape_and_labels,
        test_tsne_shape_and_labels,
        test_bad_params_raise,
        test_1d_rejected,
        test_n_components_capped,
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
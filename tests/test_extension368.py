"""Tests for the co-expression network operators (B6)."""

from __future__ import annotations

import numpy as np
import pytest
from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.steps._coexpression_common import (
    adjacency,
    cor_pvalue,
    module_eigengenes,
    scale_free_fit,
    tom,
)
from src.task.step.steps.coexpression_modules import (
    CoexpressionModulesStep,
    cut_modules,
)
from src.task.step.steps.module_eigengenes import ModuleEigengenesStep
from src.task.step.steps.module_trait_correlation import (
    ModuleTraitCorrelationStep,
    correlation_matrix,
)
from src.task.step.steps.wgcna_soft_threshold import (
    WgcnaSoftThresholdStep,
    parse_powers,
)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _expr(matrix, samples, features):
    return Form(
        data=np.asarray(matrix, dtype=np.float64),
        dims=["sample", "feature"],
        labels={
            "sample": {name: index for index, name in enumerate(samples)},
            "feature": {name: index for index, name in enumerate(features)},
        },
    )


def _modules(values, features):
    return Form(
        data=np.asarray(values, dtype=np.float64).reshape(-1, 1),
        dims=["feature", "module"],
        labels={
            "feature": {name: index for index, name in enumerate(features)},
            "module": {"module": 0},
        },
    )


def _run(step, params, forms):
    ctx = Ctx(params)
    step.run(ctx, forms)
    return ctx["out"], step.export(ctx)


def _block_data(seed=0):
    rng = np.random.default_rng(seed)
    samples = [f"S{i}" for i in range(12)]
    features = [f"G{i}" for i in range(6)]
    base1 = rng.normal(size=12)
    base2 = rng.normal(size=12)
    X = np.column_stack(
        [
            base1 + 0.01 * rng.normal(size=12),
            base1 + 0.01 * rng.normal(size=12),
            base1 + 0.01 * rng.normal(size=12),
            base2 + 0.01 * rng.normal(size=12),
            base2 + 0.01 * rng.normal(size=12),
            base2 + 0.01 * rng.normal(size=12),
        ]
    )
    return X, samples, features


def test_parse_powers_orders_and_deduplicates() -> None:
    assert parse_powers("6,1,6,3") == [1, 3, 6]
    with pytest.raises(StepError):
        parse_powers("0,-2")


def test_tom_matches_closed_form_for_two_genes() -> None:
    R = np.array([[1.0, 0.5], [0.5, 1.0]])
    A = adjacency(R, 1.0)
    T = tom(A)
    # shared = A @ A has a zero off-diagonal here, so (0 + 0.5) / 1.0 = 0.5
    assert T[0, 1] == pytest.approx(0.5)
    assert T[0, 0] == 0.0


def test_scale_free_fit_is_linear_for_power_law_tail() -> None:
    counts = [400, 200, 133, 100, 80, 67, 57, 50, 44, 40]
    k = np.repeat(np.arange(1, 11, dtype=float), counts)
    fit = scale_free_fit(k, n_bins=9)
    assert fit["r_squared"] > 0.9
    assert fit["slope"] < 0
    assert np.isfinite(fit["adj_r_squared"])


def test_correlation_pvalue_edges() -> None:
    assert cor_pvalue(np.array([0.0]), 10)[0] == pytest.approx(1.0)
    assert cor_pvalue(np.array([1.0]), 10)[0] == pytest.approx(0.0, abs=1e-12)


def test_module_eigengenes_recovers_common_factor() -> None:
    base = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    X = np.column_stack([base, 2.0 * base])
    ids, ME, variance = module_eigengenes(X, np.array([1, 1]), scale=True)
    assert ids == [1]
    assert variance[0] == pytest.approx(1.0)
    corr = np.corrcoef(ME[:, 0], base)[0, 1]
    assert corr == pytest.approx(1.0, abs=1e-8)


def test_coexpression_modules_splits_two_blocks() -> None:
    X, samples, features = _block_data()
    labels, sizes, _, _ = cut_modules(
        X, beta=6, cut_height=0.9, merge_threshold=0.75, min_module_size=2
    )
    assert sizes == {1: 3, 2: 3}
    first, second = labels[0], labels[3]
    assert first != second
    assert list(labels) == [first, first, first, second, second, second]


def test_coexpression_modules_step_contract() -> None:
    X, samples, features = _block_data()
    out, info = _run(
        CoexpressionModulesStep(),
        {"cut_height": 0.9, "min_module_size": 2},
        [_expr(X, samples, features)],
    )
    assert out.dims == ["feature", "module"]
    assert out.data.shape == (6, 1)
    assert info["n_modules"] == 2
    assert info["n_grey"] == 0
    assert set(out.labels["feature"]) == set(features)


def test_coexpression_modules_rejects_unknown_cut() -> None:
    X, _, _ = _block_data()
    with pytest.raises(StepError):
        cut_modules(X, beta=6, cut_height=1.5, merge_threshold=0.75, min_module_size=2)


def test_coexpression_modules_grey_only_is_an_error() -> None:
    X, _, _ = _block_data()
    with pytest.raises(StepError):
        cut_modules(X, beta=6, cut_height=0.9, merge_threshold=0.75, min_module_size=99)


def test_soft_threshold_reports_decreasing_connectivity() -> None:
    X, samples, features = _block_data()
    out, info = _run(
        WgcnaSoftThresholdStep(),
        {"powers": "1,2,3,4", "max_features": 0},
        [_expr(X, samples, features)],
    )
    assert out.data.shape == (4, 6)
    mean_k = out.data[:, 3]
    assert np.all(np.diff(mean_k) < 0)
    assert info["n_powers"] == 4
    assert info["suggested_power"] in (1, 2, 3, 4)
    assert out.labels["power"] == {"1": 0, "2": 1, "3": 2, "4": 3}


def test_module_trait_correlation_perfect_associations() -> None:
    samples = [f"S{i}" for i in range(5)]
    traits = ["score"]
    ME = np.column_stack([np.arange(5.0), np.arange(5.0)[::-1]])
    form_me = Form(
        data=ME,
        dims=["sample", "module"],
        labels={
            "sample": {name: index for index, name in enumerate(samples)},
            "module": {"ME1": 0, "ME2": 1},
        },
    )
    form_trait = Form(
        data=np.arange(5.0).reshape(-1, 1),
        dims=["sample", "trait"],
        labels={
            "sample": {name: index for index, name in enumerate(samples)},
            "trait": {"score": 0},
        },
    )
    out, info = _run(ModuleTraitCorrelationStep(), {}, [form_me, form_trait])
    assert out.data.shape == (2, 3)
    assert out.labels["module_trait"] == {"ME1|score": 0, "ME2|score": 1}
    assert out.data[0, 0] == pytest.approx(1.0)
    assert out.data[1, 0] == pytest.approx(-1.0)
    assert out.data[0, 1] < 1e-10
    assert info["strongest_pair"] == "ME1|score"
    assert info["n_significant"] == 2


def test_correlation_matrix_requires_matching_samples() -> None:
    with pytest.raises(StepError):
        correlation_matrix(np.zeros((4, 2)), np.zeros((3, 1)))


def test_scale_free_fit_matches_wgcna_reference() -> None:
    """Reference values produced by WGCNA 1.73 scaleFreeFitIndex()."""
    k = np.array(
        [0.5, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12,
         14, 17, 20, 25, 30, 40, 50, 70, 100, 150, 200]
    )
    fit = scale_free_fit(k)
    assert fit["r_squared"] == pytest.approx(0.2312277, abs=5e-8)
    assert fit["slope"] == pytest.approx(-4.322488, abs=5e-7)
    assert fit["adj_r_squared"] == pytest.approx(0.01162644, abs=5e-8)

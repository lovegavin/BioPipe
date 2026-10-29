from __future__ import annotations

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.combat import CombatStep
from src.task.step.steps.ssgsea import SsgseaStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params
        self.metadata = {}


def _form(data, dims, labels, dtype=np.float32):
    value = Form(np.asarray(data, dtype=dtype), list(dims), labels,
                 {"missing_code": np.nan})
    value.validate()
    return value


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return ctx[params.get("output", step.name)], step.export(ctx)


def test_combat_mean_center_aligns_batches_and_preserves_sample_labels():
    expr = _form(
        [[1, 10, 3, 14], [2, 20, 4, 24]],
        ["gene", "sample"],
        {"gene": {"g0": 0, "g1": 1}, "sample": {"s0": 0, "s1": 1, "s2": 2, "s3": 3}},
    )
    meta = _form(
        [["A"], ["B"], ["A"], ["B"]],
        ["sample", "feature"],
        {"sample": {"s0": 0, "s1": 1, "s2": 2, "s3": 3}, "feature": {"batch": 0}},
        dtype=object,
    )
    out, export = _run(
        CombatStep(),
        {"feature_dim": "gene", "sample_dim": "sample", "batch_label": "batch",
         "method": "mean_center", "output": "corrected"},
        [expr, meta],
    )
    assert out.dims == ["gene", "sample"]
    assert out.labels["sample"] == {"s0": 0, "s1": 1, "s2": 2, "s3": 3}
    a = out.data[:, [0, 2]].mean(axis=1)
    b = out.data[:, [1, 3]].mean(axis=1)
    np.testing.assert_allclose(a, b, rtol=1e-6, atol=1e-6)
    np.testing.assert_allclose(a, [7.0, 12.5], rtol=1e-6, atol=1e-6)
    assert export["method"] == "mean_center"
    assert export["batches"] == ["A", "B"]


def test_ssgsea_scores_are_finite_normalized_and_labeled():
    expr = _form(
        [[1, 2, 3], [2, 4, 6], [3, 6, 9], [4, 8, 12], [5, 10, 15], [6, 12, 18]],
        ["gene", "sample"],
        {"gene": {f"g{i}": i for i in range(6)}, "sample": {"s0": 0, "s1": 1, "s2": 2}},
    )
    sets = _form(
        [[1, 0], [1, 0], [1, 0], [0, 1], [0, 1], [0, 1]],
        ["gene", "gene_set"],
        {"gene": {f"g{i}": i for i in range(6)}, "gene_set": {"A": 0, "B": 1}},
    )
    out, export = _run(
        SsgseaStep(),
        {"feature_dim": "gene", "sample_dim": "sample", "gene_dim": "gene",
         "gene_set_dim": "gene_set", "min_size": 2, "normalize": True},
        [expr, sets],
    )
    assert out.dims == ["sample", "gene_set"]
    assert out.labels["sample"] == {"s0": 0, "s1": 1, "s2": 2}
    assert out.labels["gene_set"] == {"A": 0, "B": 1}
    assert np.isfinite(out.data).all()
    assert float(np.abs(out.data).max()) <= 1.0
    assert export["sets_scored"] == ["A", "B"]


def test_combat_requires_every_expression_sample_in_metadata():
    expr = _form([[1, 2]], ["gene", "sample"], {"gene": {"g0": 0}, "sample": {"s0": 0, "s1": 1}})
    meta = _form([["A"]], ["sample", "feature"],
                 {"sample": {"s0": 0}, "feature": {"batch": 0}}, dtype=object)
    with pytest.raises(Exception, match="no batch label"):
        _run(CombatStep(), {"feature_dim": "gene", "sample_dim": "sample",
                    "batch_label": "batch", "method": "mean_center"}, [expr, meta])

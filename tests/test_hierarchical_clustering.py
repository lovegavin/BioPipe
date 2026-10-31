"""Hand checks for hierarchical clustering."""

from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.hierarchical_clustering import (
    HierarchicalClusteringStep,
)


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


FIXTURE = np.asarray(
    [[0, 0], [1, 0], [0, 1], [3, 3], [3, 4], [4, 3]], dtype=np.float64
)
EXPECTED_HEIGHTS = {
    "single": [1.0, 1.0, 1.0, 1.0, 3.605551275463989],
    "complete": [1.0, 1.0, 1.4142135623730951, 1.4142135623730951, 5.0],
    "average": [1.0, 1.0, 1.2071067811865475, 1.2071067811865475, 4.3203662802538867],
    "ward.D2": [1.0, 1.0, 1.2909944487358056, 1.2909944487358056, 7.348469228349534],
}


def _form(values=FIXTURE):
    return Form(
        data=values,
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(values.shape[0])},
            "feature": {f"f{j}": j for j in range(values.shape[1])},
        },
        info={"missing_code": np.nan},
    )


def _run(params=None, form=None):
    ctx = Ctx(params or {})
    step = HierarchicalClusteringStep()
    step.run(ctx, [form or _form()])
    name = (params or {}).get("output", step.name)
    return step.export(ctx), ctx[name]


def test_hierarchical_heights_and_clusters():
    for method, expected in EXPECTED_HEIGHTS.items():
        export, out = _run({"linkage": method, "n_clusters": 3})
        assert out.dims == ["sample", "cluster"]
        assert out.data.shape == (6, 1)
        assert list(out.labels["sample"]) == [f"s{i}" for i in range(6)]
        assert export["labels"] == [0, 0, 0, 1, 1, 2]
        assert export["heights"] == pytest.approx(expected, abs=1e-12)
        assert export["method"] == "hierarchical_clustering"
        assert export["linkage"] == method
        assert export["n_clusters"] == 3


def test_hierarchical_cophenetic_correlation_matches_r():
    export, _ = _run({"linkage": "average", "n_clusters": 3})
    assert export["cophenetic_correlation"] == pytest.approx(
        0.9714035035860376, abs=1e-12
    )
    assert len(export["merge"]) == 5


def test_hierarchical_manhattan_and_invalid_inputs():
    export, _ = _run({"linkage": "single", "metric": "manhattan", "n_clusters": 2})
    assert export["metric"] == "manhattan"
    assert export["labels"] == [0, 0, 0, 1, 1, 1]

    with pytest.raises(StepError, match="n_clusters"):
        _run({"n_clusters": 1})
    with pytest.raises(StepError, match="n_clusters"):
        _run({"n_clusters": 6})
    with pytest.raises(StepError, match="three samples"):
        _run(form=_form(FIXTURE[:2]))
    bad = FIXTURE.copy()
    bad[0, 0] = np.nan
    with pytest.raises(StepError, match="non-finite"):
        _run(form=_form(bad))

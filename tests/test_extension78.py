"""Hand checks for 0.86 Chao1 richness and rarefaction."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.chao1 import Chao1Step
from src.task.step.steps.rarefaction import RarefactionStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _run(step, params, form):
    ctx = Ctx(params)
    step.run(ctx, [form])
    return step.export(ctx), ctx[params.get("output", step.name)]


def _form(values):
    values = np.asarray(values, dtype=float)
    form = Form(
        data=values,
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(values.shape[0])},
            "feature": {f"f{i}": i for i in range(values.shape[1])},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


COUNTS = np.array(
    [
        [10, 20, 30, 0],
        [5, 0, 15, 30],
        [0, 0, 0, 0],
        [1, 1, 1, 1],
    ],
    dtype=float,
)


def test_chao1_matches_vegan():
    export, form = _run(Chao1Step(), {"output": "chao1"}, _form(COUNTS))
    assert form.data.shape == (4, 5)
    np.testing.assert_allclose(
        export["chao1"], [3.0, 3.0, 0.0, 10.0], rtol=0, atol=1e-6
    )
    np.testing.assert_allclose(
        export["observed"], [3.0, 3.0, 0.0, 4.0], rtol=0, atol=1e-6
    )
    np.testing.assert_allclose(
        export["singletons"], [0.0, 0.0, 0.0, 4.0], rtol=0, atol=1e-6
    )
    np.testing.assert_allclose(
        export["doubletons"], [0.0, 0.0, 0.0, 0.0], rtol=0, atol=1e-6
    )


def test_chao1_rejects_invalid_counts():
    with pytest.raises(StepError, match="non-negative"):
        _run(Chao1Step(), {"output": "chao1"}, _form([[1, -1]]))
    with pytest.raises(StepError, match="integers"):
        _run(Chao1Step(), {"output": "chao1"}, _form([[1, 1.5]]))
    with pytest.raises(StepError, match="no samples"):
        _run(Chao1Step(), {"output": "chao1"}, _form(np.empty((0, 2))))


RARE = np.array(
    [
        [10, 20, 30, 0],
        [5, 0, 15, 30],
        [2, 3, 5, 0],
    ],
    dtype=float,
)


def test_rarefaction_matches_vegan():
    export, form = _run(
        RarefactionStep(), {"depth": 10, "output": "rare"}, _form(RARE)
    )
    assert form.data.shape == (3, 1)
    np.testing.assert_allclose(
        export["rarefied"],
        [2.852110517597176, 2.671547890140520, 3.0],
        rtol=0,
        atol=1e-9,
    )


def test_rarefaction_rejects_bad_depth():
    with pytest.raises(StepError, match="positive integer"):
        _run(RarefactionStep(), {"depth": 0, "output": "rare"}, _form(RARE))
    with pytest.raises(StepError, match="exceeds total counts"):
        _run(RarefactionStep(), {"depth": 100, "output": "rare"}, _form(RARE))

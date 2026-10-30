"""Hand checks for the 0.37 effect-size and ordered-rank batch."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.cramer_v import CramerVStep
from src.task.step.steps.jonckheere_terpstra import JonckheereTerpstraStep
from src.task.step.steps.varimax_rotation import VarimaxRotationStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params


def _form(data, dims, labels):
    form = Form(np.asarray(data, dtype=np.float32), list(dims), labels, {"missing_code": np.nan})
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return ctx[params.get("output", step.name)], step.export(ctx)


def test_cramer_v_matches_desctools():
    table = _form(
        [[10, 20], [20, 10], [30, 10]],
        ["row", "column"],
        {"row": {"r0": 0, "r1": 1, "r2": 2}, "column": {"c0": 0, "c1": 1}},
    )
    out, info = _run(CramerVStep(), {}, [table])
    assert out.data.shape == (8, 1)
    assert info["V"] == pytest.approx(0.36324157862838946, rel=1e-12)
    assert info["chisq"] == pytest.approx(13.194444444444445, rel=1e-12)
    assert info["df"] == 2
    assert info["p"] == pytest.approx(0.001364152090848616, rel=1e-12)
    assert info["n"] == 100


def test_jonckheere_terpstra_matches_desctools_normal_approximation():
    values = np.array([1, 2, 3, 2, 3, 4, 4, 5, 6, 5, 6, 7], dtype=np.float32)
    groups = np.repeat(np.arange(1, 5), 3).astype(np.float32)
    form = _form(
        np.column_stack([values, groups]),
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(12)},
            "feature": {"value": 0, "group": 1},
        },
    )
    out, info = _run(
        JonckheereTerpstraStep(),
        {"value_label": "value", "group_label": "group"},
        [form],
    )
    assert out.data.shape == (7, 1)
    assert info["statistic"] == pytest.approx(49.5, rel=1e-12)
    assert info["z"] == pytest.approx(3.1980107453341566, rel=1e-12)
    assert info["p"] == pytest.approx(0.0013837912401648556, rel=1e-12)
    assert info["groups"] == ["1", "2", "3", "4"]
    assert info["group_sizes"] == [3, 3, 3, 3]


def test_varimax_rotation_matches_r_stats():
    loadings = _form(
        [
            [0.8, 0.2], [0.6, 0.4], [0.5, 0.5],
            [0.3, 0.7], [0.2, 0.8], [0.1, 0.9],
        ],
        ["variable", "factor"],
        {
            "variable": {f"v{i}": i for i in range(6)},
            "factor": {"f0": 0, "f1": 1},
        },
    )
    out, info = _run(VarimaxRotationStep(), {}, [loadings])
    assert out.data.shape == (6, 2)
    assert np.allclose(
        out.data,
        [
            [0.8145579, 0.1284345], [0.6330375, 0.3453455],
            [0.5422773, 0.4538009], [0.3607570, 0.6707119],
            [0.2699968, 0.7791673], [0.1792366, 0.8876228],
        ],
        atol=2e-6,
    )
    assert np.allclose(
        info["rotation"],
        [[0.9960782746585466, -0.08847638528586327],
         [0.08847638528586327, 0.9960782746585468]],
        atol=2e-8,
    )
    assert np.allclose(info["ss_loadings"], [1.5934753503051715, 2.1865246496948276], atol=2e-7)


def test_037_rejects_invalid_inputs():
    one_row = _form(
        [[5, 6]],
        ["row", "column"],
        {"row": {"r": 0}, "column": {"c0": 0, "c1": 1}},
    )
    with pytest.raises(StepError, match="at least two rows"):
        _run(CramerVStep(), {}, [one_row])

    one_group = _form(
        np.array([[1.0, 1.0], [2.0, 1.0]], dtype=np.float32),
        ["sample", "feature"],
        {"sample": {"s0": 0, "s1": 1}, "feature": {"value": 0, "group": 1}},
    )
    with pytest.raises(StepError, match="at least two groups"):
        _run(
            JonckheereTerpstraStep(),
            {"value_label": "value", "group_label": "group"},
            [one_group],
        )

    one_factor = _form(
        [[0.5], [0.6]],
        ["variable", "factor"],
        {"variable": {"v0": 0, "v1": 1}, "factor": {"f0": 0}},
    )
    with pytest.raises(StepError, match="at least two factors"):
        _run(VarimaxRotationStep(), {}, [one_factor])

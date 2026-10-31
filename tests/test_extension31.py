"""Hand checks for the 0.38 ordinal association batch."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.goodman_kruskal_gamma import GoodmanKruskalGammaStep
from src.task.step.steps.kendall_w import KendallWStep
from src.task.step.steps.somers_d import SomersDStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _form(data, dims, labels):
    form = Form(np.asarray(data, dtype=np.float32), list(dims), labels, {"missing_code": np.nan})
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


def _table():
    return _form(
        [[10, 5, 2], [6, 12, 4], [3, 7, 15]],
        ["row", "column"],
        {"row": {"low": 0, "mid": 1, "high": 2}, "column": {"a": 0, "b": 1, "c": 2}},
    )


def _ratings():
    return _form(
        [
            [1, 1, 2], [2, 3, 1], [3, 2, 3], [5, 4, 4], [4, 5, 5],
        ],
        ["subject", "rater"],
        {
            "subject": {f"s{i}": i for i in range(5)},
            "rater": {"r1": 0, "r2": 1, "r3": 2},
        },
    )


def test_somers_d_matches_desctools_for_both_directions():
    row, _ = _run(SomersDStep(), {"direction": "row"}, [_table()])
    assert row["D"] == pytest.approx(0.44885945548197204, rel=1e-12)
    assert row["concordant"] == 787
    assert row["discordant"] == 177

    column, _ = _run(SomersDStep(), {"direction": "column"}, [_table()])
    assert column["D"] == pytest.approx(0.45218680504077097, rel=1e-12)


def test_goodman_kruskal_gamma_matches_desctools():
    gamma, out = _run(GoodmanKruskalGammaStep(), {}, [_table()])
    assert gamma["gamma"] == pytest.approx(0.63278008298755184, rel=1e-12)
    assert gamma["concordant"] == 787
    assert gamma["discordant"] == 177
    assert out.data.shape == (6, 1)


def test_kendall_w_matches_desctools_column_ranks():
    w_value, out = _run(KendallWStep(), {}, [_ratings()])
    assert w_value["W"] == pytest.approx(0.84444444444444444, rel=1e-12)
    assert w_value["chisq"] == pytest.approx(10.133333333333333, rel=1e-12)
    assert w_value["df"] == 4
    assert w_value["p"] == pytest.approx(0.038240605326664866, rel=1e-12)
    assert w_value["S"] == pytest.approx(76.0)
    assert w_value["raters"] == ["r1", "r2", "r3"]
    assert out.data.shape == (7, 1)


def test_038_rejects_invalid_inputs():
    one_row = _form(
        [[3, 4]],
        ["row", "column"],
        {"row": {"r": 0}, "column": {"c0": 0, "c1": 1}},
    )
    with pytest.raises(StepError, match="at least two rows"):
        _run(SomersDStep(), {}, [one_row])
    with pytest.raises(StepError, match="direction"):
        _run(SomersDStep(), {"direction": "diagonal"}, [_table()])

    with pytest.raises(StepError, match="unknown raters"):
        _run(KendallWStep(), {"raters": ["missing"]}, [_ratings()])

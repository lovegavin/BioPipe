"""Hand checks for the 0.40 nonparametric/randomness tests."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.bartels_rank import BartelsRankStep
from src.task.step.steps.van_waerden import VanWaerdenStep
from src.task.step.steps.woolf_test import WoolfTestStep


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


def _van():
    x = np.arange(1.0, 11.0)
    expr = _form(x.reshape(1, -1), ["feature", "sample"], {
        "feature": {"x": 0}, "sample": {f"s{i}": i for i in range(10)},
    })
    meta = _form([[0]] * 5 + [[1]] * 5, ["sample", "label"], {
        "sample": {f"s{i}": i for i in range(10)}, "label": {"g": 0},
    })
    return expr, meta


def _bartels(n=10):
    expr = _form(np.arange(1.0, n + 1).reshape(-1, 1), ["sample", "feature"], {
        "sample": {f"s{i}": i for i in range(n)}, "feature": {"x": 0},
    })
    return expr


def _woolf():
    return _form([
        [10, 20, 30, 40],
        [15, 25, 35, 45],
        [20, 30, 40, 50],
    ], ["stratum", "feature"], {
        "stratum": {f"r{i}": i for i in range(3)},
        "feature": {name: i for i, name in enumerate(["a", "b", "c", "d"])},
    })


def test_van_waerden_matches_r():
    result, out = _run(VanWaerdenStep(), {
        "group_label": "g", "group_a": "0", "group_b": "1",
    }, list(_van()))
    assert result["statistic"] == pytest.approx(6.349304, rel=1e-5)
    assert result["df"] == 1
    assert result["p"] == pytest.approx(0.01174273, rel=1e-5)
    assert out.data.shape == (6, 1)


def test_bartels_rank_matches_r():
    result, out = _run(BartelsRankStep(), {"value_label": "x"}, [_bartels()])
    assert result["RVN"] == pytest.approx(0.1090909, rel=1e-5)
    assert result["z"] == pytest.approx(-3.2509408, rel=1e-6)
    assert result["mu"] == pytest.approx(2.0)
    assert result["var"] == pytest.approx(0.3383165, rel=1e-6)
    assert result["p"] == pytest.approx(0.001150238, rel=1e-5)
    assert out.data.shape == (7, 1)


def test_woolf_matches_r():
    result, out = _run(WoolfTestStep(), {}, [_woolf()])
    assert result["statistic"] == pytest.approx(0.1481616, rel=1e-5)
    assert result["df"] == 2
    assert result["p"] == pytest.approx(0.9285967, rel=1e-5)
    assert out.data.shape == (6, 1)


def test_040_rejects_invalid_inputs():
    expr, meta = _van()
    with pytest.raises(StepError, match="must differ"):
        _run(VanWaerdenStep(), {"group_label": "g", "group_a": "0", "group_b": "0"}, [expr, meta])
    with pytest.raises(StepError, match="at least 10"):
        _run(BartelsRankStep(), {"value_label": "x"}, [_bartels(9)])
    with pytest.raises(StepError, match="exactly four"):
        _run(WoolfTestStep(), {}, [_form([[1, 2, 3], [2, 3, 4]], ["stratum", "feature"], {
            "stratum": {"a": 0, "b": 1}, "feature": {"c0": 0, "c1": 1, "c2": 2},
        })])

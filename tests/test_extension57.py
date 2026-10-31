"""Hand checks for 0.64 epidemiological effect sizes."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.cohens_h import CohensHStep
from src.task.step.steps.odds_ratio import OddsRatioStep
from src.task.step.steps.risk_ratio import RiskRatioStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _table(values):
    data = np.asarray(values, dtype=np.float64)
    form = Form(
        data,
        ["row", "col"],
        {"row": {"exposed": 0, "unexposed": 1}, "col": {"event": 0, "no_event": 1}},
        {"missing_code": np.nan},
    )
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


TABLE = [[18, 12], [10, 20]]


def test_risk_ratio_matches_wald_reference():
    result, out = _run(RiskRatioStep(), {}, [_table(TABLE)])
    assert out.data.shape == (1, 6)
    assert out.data[0, 0] == pytest.approx(1.8, rel=1e-12)
    assert out.data[0, 1] == pytest.approx(1.0034442222671074, rel=1e-12)
    assert out.data[0, 2] == pytest.approx(3.2288790229712867, rel=1e-12)
    assert result["n"] == 60


def test_odds_ratio_matches_woolf_reference():
    result, out = _run(OddsRatioStep(), {}, [_table(TABLE)])
    assert out.data.shape == (1, 6)
    assert out.data[0, 0] == pytest.approx(3.0, rel=1e-12)
    assert out.data[0, 1] == pytest.approx(1.0461986908532277, rel=1e-12)
    assert out.data[0, 2] == pytest.approx(8.602572416392574, rel=1e-12)
    assert result["log_or"] == pytest.approx(np.log(3.0), rel=1e-12)


def test_cohens_h_matches_pwr_reference():
    result, out = _run(CohensHStep(), {}, [_table(TABLE)])
    assert out.data.shape == (1, 7)
    assert out.data[0, 0] == pytest.approx(0.5411948302444529, rel=1e-12)
    assert out.data[0, 1] == pytest.approx(0.035134305491788975, rel=1e-12)
    assert out.data[0, 2] == pytest.approx(1.0472553549971169, rel=1e-12)
    assert result["n1"] == 30 and result["n2"] == 30


def test_064_invalid_table_and_zero_cell():
    with pytest.raises(StepError, match="2x2"):
        _run(RiskRatioStep(), {}, [Form(np.ones((3, 2)), ["row", "col"], {"row": {}, "col": {}}, {})])
    with pytest.raises(StepError, match="positive"):
        _run(
            OddsRatioStep(),
            {"correction": "none"},
            [_table([[0, 10], [10, 20]])],
        )
    corrected, out = _run(
        OddsRatioStep(),
        {"correction": "haldane"},
        [_table([[0, 10], [10, 20]])],
    )
    assert np.isfinite(out.data).all()
    assert corrected["correction"] == "haldane"

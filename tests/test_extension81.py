"""Hand checks for 0.89 Bai-Perron multiple structural breaks."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.bai_perron import BaiPerronStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _run(step, params, form):
    ctx = Ctx(params)
    step.run(ctx, [form])
    return step.export(ctx), ctx[params.get("output", step.name)]


def _form(values, labels):
    values = np.asarray(values, dtype=float)
    form = Form(
        data=values,
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(values.shape[0])},
            "feature": {name: i for i, name in enumerate(labels)},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


def _fixture():
    n = 120
    i = np.arange(1, n + 1, dtype=float)
    x1 = np.sin(i / 5.0)
    x2 = np.cos(i / 7.0)
    y = 1.0 + 0.5 * x1 - 0.3 * x2 + 0.1 * np.sin(i * 1.7)
    y[40:80] += 2.0
    y[80:] -= 1.0
    return np.column_stack([y, x1, x2]), ("y", "x1", "x2")


def test_bai_perron_matches_r_breakpoints():
    values, labels = _fixture()
    export, out = _run(
        BaiPerronStep(),
        {
            "response_label": "y",
            "predictors": ["x1", "x2"],
            "n_breaks": 2,
            "min_segment": 0.15,
            "output": "segments",
        },
        _form(values, labels),
    )
    assert out.dims == ["segment", "term"]
    assert out.data.shape == (3, 3)
    assert out.labels["term"] == {"Intercept": 0, "x1": 1, "x2": 2}
    assert export["breaks"] == [40, 80]
    assert export["segments"] == [
        {"start": 1, "end": 40},
        {"start": 41, "end": 80},
        {"start": 81, "end": 120},
    ]
    assert export["rss"] == pytest.approx(0.5989, abs=2e-3)
    expected = np.array(
        [
            [1.001658477, 0.4907472, -0.2923898],
            [3.001149770, 0.5043395, -0.2967135],
            [0.001173379, 0.4974717, -0.3007148],
        ]
    )
    np.testing.assert_allclose(out.data, expected, rtol=0, atol=2e-5)
    assert out.info["n_breaks"] == 2
    assert out.info["n"] == 120


def test_bai_perron_one_break_shape():
    values, labels = _fixture()
    export, out = _run(
        BaiPerronStep(),
        {
            "response_label": "y",
            "predictors": ["x1"],
            "n_breaks": 1,
            "min_segment": 0.1,
        },
        _form(values, labels),
    )
    assert out.data.shape == (2, 2)
    assert len(export["breaks"]) == 1
    assert export["segments"][0]["start"] == 1
    assert export["segments"][-1]["end"] == 120


def test_bai_perron_rejects_invalid_design():
    values, labels = _fixture()
    form = _form(values, labels)
    with pytest.raises(StepError, match="n_breaks"):
        _run(BaiPerronStep(), {"response_label": "y", "predictors": ["x1"], "n_breaks": 0}, form)
    with pytest.raises(StepError, match="min_segment"):
        _run(BaiPerronStep(), {"response_label": "y", "predictors": ["x1"], "min_segment": 0.01}, form)
    with pytest.raises(StepError, match="not enough observations"):
        _run(
            BaiPerronStep(),
            {"response_label": "y", "predictors": ["x1"], "n_breaks": 5, "min_segment": 0.5},
            form,
        )
    with pytest.raises(StepError, match="not found"):
        _run(BaiPerronStep(), {"response_label": "missing", "predictors": ["x1"]}, form)

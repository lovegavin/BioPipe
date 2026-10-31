"""Hand checks for the 0.51 scale and dispersion tests."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.fligner_killeen import FlignerKilleenStep
from src.task.step.steps.mood_scale import MoodScaleStep
from src.task.step.steps.siegel_tukey import SiegelTukeyStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _form(data, dims, labels, encoders=None):
    form = Form(
        np.asarray(data, dtype=np.float64),
        list(dims),
        labels,
        {"missing_code": np.nan, "encoders": encoders or {}},
    )
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


def _grouped(values, groups):
    encoder = LabelEncoder()
    codes = encoder.fit_transform(groups)
    n = len(groups)
    expression = _form(
        np.asarray(values, dtype=float).reshape(1, -1),
        ["feature", "sample"],
        {"feature": {"value": 0}, "sample": {f"s{i}": i for i in range(n)}},
    )
    meta = _form(
        codes.reshape(-1, 1),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(n)}, "feature": {"group": 0}},
        {"feature": {"group": encoder}},
    )
    return expression, meta


def test_fligner_killeen_matches_r():
    a = [1, 2, 3, 4, 5, 6]
    b = [2, 4, 6, 8, 10, 12]
    c = [1, 3, 5, 7, 9, 11]
    expression, meta = _grouped(a + b + c, ["A"] * 6 + ["B"] * 6 + ["C"] * 6)
    result, out = _run(FlignerKilleenStep(), {"group_label": "group"}, [expression, meta])
    assert out.data.shape == (1, 5)
    assert out.data[0, 0] == pytest.approx(3.8539129401029886, rel=1e-6)
    assert out.data[0, 1] == pytest.approx(0.14559063431450478, rel=1e-6)
    assert out.data[0, 2] == 2
    assert out.data[0, 3] == 3
    assert out.data[0, 4] == 18
    assert result["test"] == "Fligner-Killeen"


def test_mood_scale_matches_r():
    a = [1, 2, 3, 4, 5, 6]
    b = [2, 4, 6, 8, 10, 12]
    expression, meta = _grouped(a + b, ["A"] * 6 + ["B"] * 6)
    result, out = _run(
        MoodScaleStep(),
        {"group_label": "group", "group_a": "A", "group_b": "B"},
        [expression, meta],
    )
    assert out.data.shape == (1, 5)
    assert out.data[0, 0] == pytest.approx(-0.72323757801982935, rel=1e-6)
    assert out.data[0, 1] == pytest.approx(0.46953393562819462, rel=1e-6)
    assert out.data[0, 2] == 6
    assert out.data[0, 3] == 6
    assert out.data[0, 4] == 1
    assert result["alternative"] == "two-sided"


def test_siegel_tukey_matches_r():
    x = [1, 2, 3, 4, 5]
    y = [2.5, 3.5, 4.5, 5.5, 6.5]
    expression, meta = _grouped(x + y, ["A"] * 5 + ["B"] * 5)
    result, out = _run(
        SiegelTukeyStep(),
        {"group_label": "group", "group_a": "A", "group_b": "B"},
        [expression, meta],
    )
    assert out.data.shape == (1, 4)
    assert out.data[0, 0] == 14
    assert out.data[0, 1] == pytest.approx(0.84126984126984128, rel=1e-6)
    assert out.data[0, 2] == 5
    assert out.data[0, 3] == 5
    assert result["exact"] is True


def test_siegel_tukey_rejects_ties():
    x = [1, 2, 3, 4, 5]
    y = [2, 3, 4, 5, 6]
    expression, meta = _grouped(x + y, ["A"] * 5 + ["B"] * 5)
    with pytest.raises(StepError, match="ties are not supported"):
        _run(
            SiegelTukeyStep(),
            {"group_label": "group", "group_a": "A", "group_b": "B"},
            [expression, meta],
        )

"""Hand checks for the 0.56 ordered and umbrella tests."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.chacko_test import ChackoTestStep
from src.task.step.steps.fligner_wolfe import FlignerWolfeStep
from src.task.step.steps.mack_wolfe import MackWolfeStep


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


def _grouped():
    values = np.array(
        [
            1, 2, 3, 4, 5, 6,
            2, 3, 4, 5, 6, 7,
            4, 5, 6, 7, 8, 9,
            3, 4, 5, 6, 7, 8,
        ],
        dtype=float,
    )
    groups = ["A"] * 6 + ["B"] * 6 + ["C"] * 6 + ["D"] * 6
    encoder = LabelEncoder()
    codes = encoder.fit_transform(groups)
    expression = _form(
        values.reshape(1, -1),
        ["feature", "sample"],
        {"feature": {"value": 0}, "sample": {f"s{i}": i for i in range(24)}},
    )
    meta = _form(
        codes.reshape(-1, 1),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(24)}, "feature": {"group": 0}},
        {"feature": {"group": encoder}},
    )
    return expression, meta


def test_chacko_matches_pmcmrplus():
    expression, meta = _grouped()
    result, out = _run(ChackoTestStep(), {"group_label": "group"}, [expression, meta])
    assert out.data.shape == (1, 5)
    assert out.data[0, 0] == pytest.approx(5.6716666666666651, rel=1e-6)
    assert out.data[0, 1] == pytest.approx(3.0)
    assert out.data[0, 2] == pytest.approx(0.12872406680233608, rel=1e-6)
    assert result["n_features"] == 1
    assert result["n_groups"] == 4


def test_fligner_wolfe_matches_pmcmrplus():
    expression, meta = _grouped()
    result, out = _run(
        FlignerWolfeStep(),
        {"group_label": "group", "control": "A"},
        [expression, meta],
    )
    assert out.data.shape == (1, 6)
    assert out.data[0, 0] == pytest.approx(1.9503674363248837, rel=1e-6)
    assert out.data[0, 1] == pytest.approx(0.025566170105179833, rel=1e-6)
    assert result["control"] == "A"
    assert result["n_groups"] == 4


def test_mack_wolfe_matches_pmcmrplus():
    expression, meta = _grouped()
    result, out = _run(
        MackWolfeStep(),
        {"group_label": "group", "peak": "C"},
        [expression, meta],
    )
    assert out.data.shape == (1, 5)
    assert out.data[0, 0] == pytest.approx(98.0)
    assert out.data[0, 1] == pytest.approx(1.6001893827313254, rel=1e-6)
    assert out.data[0, 2] == pytest.approx(0.054778288391342869, rel=1e-6)
    assert result["peak"] == "C"
    assert result["n_groups"] == 4


def test_056_rejects_invalid_inputs():
    expression, meta = _grouped()
    with pytest.raises(StepError, match="control"):
        _run(
            FlignerWolfeStep(),
            {"group_label": "group", "control": "missing"},
            [expression, meta],
        )
    with pytest.raises(StepError, match="peak"):
        _run(
            MackWolfeStep(),
            {"group_label": "group", "peak": "missing"},
            [expression, meta],
        )
    with pytest.raises(StepError, match="group_order"):
        _run(
            ChackoTestStep(),
            {"group_label": "group", "group_order": ["A", "B", "C"]},
            [expression, meta],
        )

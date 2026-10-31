"""Hand checks for the 0.57 all-pairs mean comparisons."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.snk_test import SnkTestStep
from src.task.step.steps.tamhane_t2 import TamhaneT2Step
from src.task.step.steps.tukey_test import TukeyTestStep


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
            1, 2, 3, 4, 5,
            2, 4, 6, 8, 10, 12,
            10, 12, 14, 16, 18,
            9, 11, 13, 15, 17, 19, 21,
        ],
        dtype=float,
    )
    groups = ["A"] * 5 + ["B"] * 6 + ["C"] * 5 + ["D"] * 7
    encoder = LabelEncoder()
    codes = encoder.fit_transform(groups)
    expression = _form(
        values.reshape(1, -1),
        ["feature", "sample"],
        {"feature": {"value": 0}, "sample": {f"s{i}": i for i in range(23)}},
    )
    meta = _form(
        codes.reshape(-1, 1),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(23)}, "feature": {"group": 0}},
        {"feature": {"group": encoder}},
    )
    return expression, meta


def test_tukey_matches_pmcmrplus():
    expression, meta = _grouped()
    result, out = _run(TukeyTestStep(), {"group_label": "group"}, [expression, meta])
    assert out.data.shape == (6, 8)
    expected_p = [
        0.26502273475490234,
        0.00044739595759790696,
        0.017760584803845236,
        6.5625131024704686e-05,
        0.0030277846633985916,
        0.96066284890560794,
    ]
    expected_q = [
        2.6734500973830602,
        7.0389923847879992,
        4.6785376704203552,
        8.294160804341562,
        5.8195681974958458,
        0.69118006702846346,
    ]
    assert out.data[:, 3].tolist() == pytest.approx(expected_p, rel=1e-6)
    assert out.data[:, 1].tolist() == pytest.approx(expected_q, rel=1e-6)
    assert result["n_comparisons"] == 6


def test_tamhane_t2_matches_pmcmrplus():
    expression, meta = _grouped()
    result, out = _run(TamhaneT2Step(), {"group_label": "group"}, [expression, meta])
    assert out.data.shape == (6, 8)
    expected_p = [
        0.26157925285918715,
        0.0028593777811823928,
        0.049165728391977526,
        0.00085746647125883868,
        0.025759111282225411,
        0.99826546041815489,
    ]
    expected_t = [
        2.3763541031440183,
        6.9570108523704342,
        3.3626912299068294,
        6.7434178433881966,
        3.5777087639996634,
        0.46291004988627571,
    ]
    assert out.data[:, 3].tolist() == pytest.approx(expected_p, rel=1e-6)
    assert out.data[:, 1].tolist() == pytest.approx(expected_t, rel=1e-6)
    assert result["n_comparisons"] == 6


def test_snk_matches_pmcmrplus():
    expression, meta = _grouped()
    result, out = _run(SnkTestStep(), {"group_label": "group"}, [expression, meta])
    assert out.data.shape == (6, 8)
    expected_p = [
        0.074054575763289443,
        0.00023621084901115363,
        0.003696209233425396,
        6.5625131024704686e-05,
        0.0016288889014157704,
        0.63062071739806569,
    ]
    assert out.data[:, 3].tolist() == pytest.approx(expected_p, rel=1e-6)
    assert out.data[:, 2].tolist() == pytest.approx([2, 3, 2, 4, 3, 2])
    assert result["n_comparisons"] == 6


def test_057_rejects_invalid_inputs():
    expression, meta = _grouped()
    with pytest.raises(StepError, match="group"):
        _run(TukeyTestStep(), {"group_label": "missing"}, [expression, meta])
    single = _form(
        np.array([[1, 2, 3, 4]], dtype=float),
        ["feature", "sample"],
        {"feature": {"value": 0}, "sample": {"s0": 0, "s1": 1, "s2": 2, "s3": 3}},
    )
    encoder = LabelEncoder()
    codes = encoder.fit_transform(["A", "A", "A", "A"])
    one_meta = _form(
        codes.reshape(-1, 1),
        ["sample", "feature"],
        {"sample": {"s0": 0, "s1": 1, "s2": 2, "s3": 3}, "feature": {"group": 0}},
        {"feature": {"group": encoder}},
    )
    with pytest.raises(StepError, match="at least two groups"):
        _run(TukeyTestStep(), {"group_label": "group"}, [single, one_meta])

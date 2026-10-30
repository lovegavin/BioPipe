"""Hand checks for 0.35 reliability and multivariate tests."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.canonical_correlation import CanonicalCorrelationStep
from src.task.step.steps.cronbach_alpha import CronbachAlphaStep
from src.task.step.steps.runs_test import RunsTestStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}
        self.metadata = {}


def _form(data, names, value_dim="feature", samples=None):
    data = np.asarray(data, dtype=np.float64)
    if data.ndim == 1:
        data = data[:, None]
    labels = samples or [f"s{i}" for i in range(data.shape[0])]
    form = Form(
        data,
        ["sample", value_dim],
        {
            "sample": {name: i for i, name in enumerate(labels)},
            value_dim: {name: i for i, name in enumerate(names)},
        },
        {"missing_code": np.nan},
    )
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return ctx[params.get("output", step.name)], step.export(ctx)


def _items():
    return np.asarray(
        [
            [1, 2, 2, 3],
            [2, 3, 3, 4],
            [3, 3, 4, 5],
            [4, 5, 4, 6],
            [5, 5, 6, 7],
            [2, 2, 3, 3],
            [3, 4, 4, 5],
            [4, 4, 5, 6],
            [5, 6, 6, 7],
            [3, 3, 4, 4],
        ],
        dtype=float,
    )


def test_cronbach_alpha_matches_r():
    out, info = _run(
        CronbachAlphaStep(),
        {},
        [_form(_items(), ["i1", "i2", "i3", "i4"], "item")],
    )
    assert out.dims == ["statistic", "value"]
    assert out.data.shape == (5, 1)
    assert info["raw_alpha"] == pytest.approx(0.98095238095238102, rel=1e-12)
    assert info["std_alpha"] == pytest.approx(0.98187204060071320, rel=1e-12)
    assert info["average_r"] == pytest.approx(0.93122823755510831, rel=1e-12)
    assert info["n_items"] == 4
    assert info["n_subjects"] == 10


def test_canonical_correlation_matches_r():
    i = np.arange(1, 21, dtype=float)
    x = np.column_stack([i, np.sin(i)])
    y = np.column_stack(
        [
            i
            + np.asarray(
                [
                    0.1,
                    -0.2,
                    0.3,
                    -0.1,
                    0.2,
                    0,
                    -0.3,
                    0.1,
                    0.2,
                    -0.1,
                    0.3,
                    -0.2,
                    0.1,
                    0,
                    -0.2,
                    0.2,
                    -0.1,
                    0.3,
                    0,
                    -0.3,
                ]
            ),
            np.cos(i),
        ]
    )
    out, info = _run(
        CanonicalCorrelationStep(),
        {},
        [
            _form(x, ["x1", "x2"], "x"),
            _form(y, ["y1", "y2"], "y"),
        ],
    )
    assert out.dims == ["component", "statistic"]
    assert out.data.shape == (2, 2)
    assert info["correlations"] == pytest.approx(
        [0.999512503815628284, 0.063233134692046916], rel=1e-12
    )
    assert info["n_subjects"] == 20


def test_runs_test_matches_r():
    values = np.asarray(
        [1, 2, 3, 2, 1, 2, 3, 4, 3, 2, 1, 2, 3, 4, 5], dtype=float
    )
    out, info = _run(
        RunsTestStep(),
        {"value_label": "value"},
        [_form(values, ["value"])],
    )
    assert out.data.shape == (9, 1)
    assert info["statistic"] == pytest.approx(0.65465367070797698, rel=1e-12)
    assert info["p"] == pytest.approx(0.51269076026192351, rel=1e-12)
    assert info["runs"] == 6
    assert info["expected_runs"] == pytest.approx(5.2, rel=1e-12)
    assert info["variance"] == pytest.approx(1.4933333333333334, rel=1e-12)
    assert info["n1"] == 7
    assert info["n2"] == 3
    assert info["n"] == 10


def test_parameter_errors():
    with pytest.raises(StepError, match="at least two items"):
        _run(CronbachAlphaStep(), {}, [_form(_items()[:, :1], ["i1"], "item")])
    values = np.asarray([1.0, 1.0, 1.0], dtype=float)
    with pytest.raises(StepError, match="both sides"):
        _run(
            RunsTestStep(),
            {"value_label": "value", "threshold": 0.5},
            [_form(values, ["value"])],
        )

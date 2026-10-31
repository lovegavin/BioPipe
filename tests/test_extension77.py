"""Tests for Weibull AFT and exact Hardy-Weinberg operators."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.aft import AftStep
from src.task.step.steps.hardy_weinberg import HardyWeinbergStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _aft_fixture():
    rng = np.random.default_rng(20261112)
    n = 90
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    shape = 1.4
    scale = np.exp(1.0 + 0.4 * x1 - 0.3 * x2)
    time = scale * (-np.log(rng.random(n))) ** (1.0 / shape)
    event = (time <= 3.0).astype(int)
    data = np.column_stack([time, event, x1, x2])
    form = Form(
        data=data,
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(n)},
            "feature": {name: i for i, name in enumerate(["time", "event", "x1", "x2"])},
        },
    )
    form.validate()
    return form


def _aft_run():
    step = AftStep()
    ctx = Ctx(
        {
            "time_label": "time",
            "event_label": "event",
            "covariates": ["x1", "x2"],
            "output": "fit",
        }
    )
    step.run(ctx, [_aft_fixture()])
    return step.export(ctx), ctx["fit"]


def _hwe_form(rows):
    data = np.asarray(rows, dtype=float)
    form = Form(
        data=data,
        dims=["variant", "feature"],
        labels={
            "variant": {f"v{i}": i for i in range(data.shape[0])},
            "feature": {name: i for i, name in enumerate(["AA", "AB", "BB"])},
        },
    )
    form.validate()
    return form


def _hwe_run(rows):
    step = HardyWeinbergStep()
    ctx = Ctx({"output": "hwe"})
    step.run(ctx, [_hwe_form(rows)])
    return step.export(ctx), ctx["hwe"]


def test_aft_matches_numerical_fixture():
    export, form = _aft_run()
    assert export["terms"] == ["Intercept", "x1", "x2"]
    assert form.info["n"] == 90
    assert form.info["events"] == export["events"]
    assert export["coef"] == pytest.approx(
        [1.248650, 0.918462, -0.434935], abs=3e-5
    )
    assert export["se"] == pytest.approx(
        [0.124445, 0.150640, 0.124619], abs=3e-5
    )
    assert export["shape"] == pytest.approx(1.094724, abs=2e-5)
    assert export["scale"] == pytest.approx(0.913473, abs=2e-5)
    assert export["loglik"] == pytest.approx(-120.493434, abs=2e-5)
    assert form.data.shape == (3, 7)


def test_hwe_exact_fixture():
    rows = [
        (30, 20, 10),
        (40, 5, 35),
        (35, 30, 35),
        (10, 10, 80),
        (0, 20, 0),
        (50, 0, 50),
    ]
    export, form = _hwe_run(rows)
    expected = [
        0.07767465115912098,
        4.713334922023663e-17,
        5.882470534401839e-05,
        2.538559375620213e-07,
        8.94713860811457e-06,
        1.1142241805814507e-30,
    ]
    assert export["exact_p"] == pytest.approx(expected, rel=2e-10, abs=1e-14)
    assert export["alt_freq"][0] == pytest.approx(1.0 / 3.0)
    assert export["obs_het"][0] == pytest.approx(1.0 / 3.0)
    assert export["exp_het"][0] == pytest.approx(4.0 / 9.0)
    assert export["fis"][0] == pytest.approx(0.25)
    assert form.info["n_variants"] == 6


def test_hwe_monomorphic_and_invalid():
    export, _ = _hwe_run([(50, 0, 50)])
    assert export["n"] == [100]
    assert export["alt_freq"] == [0.5]
    assert export["obs_het"] == [0.0]
    assert export["exact_p"][0] < 1e-20

    with pytest.raises(StepError, match="nonnegative integers"):
        _hwe_run([(1.5, 2, 3)])
    with pytest.raises(StepError, match="nonnegative integers"):
        _hwe_run([(-1, 2, 3)])
    with pytest.raises(StepError, match="at least one genotype"):
        _hwe_run([(0, 0, 0)])


def test_aft_invalid_inputs():
    step = AftStep()
    ctx = Ctx(
        {
            "time_label": "time",
            "event_label": "event",
            "covariates": ["x1"],
        }
    )
    data = _aft_fixture().data.copy()
    data[:, 1] = 2
    form = Form(
        data=data,
        dims=["sample", "feature"],
        labels=_aft_fixture().labels,
    )
    form.validate()
    with pytest.raises(StepError, match="event column"):
        step.run(ctx, [form])

    small = _aft_fixture()
    small.data = small.data[:4].copy()
    small.labels["sample"] = {f"s{i}": i for i in range(4)}
    small.validate()
    with pytest.raises(StepError, match="at least 10"):
        step.run(ctx, [small])

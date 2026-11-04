"""Tests for 1.10.0 confidence, goodness-of-fit and ordination operators."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.chisq_gof import ChisqGofStep
from src.task.step.steps.poisson_test import PoissonTestStep
from src.task.step.steps.proportion_ci import ProportionCiStep
from src.task.step.steps.rda import RdaStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params
        self.metadata = {}


def _form(data, dims, labels):
    form = Form(data=np.asarray(data, dtype=np.float64), dims=dims, labels=labels,
                info={})
    form.validate()
    return form


def _table(names, columns):
    feature_names = list(columns)
    data = np.column_stack([columns[name] for name in feature_names])
    return _form(
        data,
        ["sample", "feature"],
        {"sample": {name: i for i, name in enumerate(names)},
         "feature": {name: j for j, name in enumerate(feature_names)}},
    )


def _run(step, inputs, params):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return ctx[params.get("output", step.name)], step.export(ctx)


def _rows(form, dim):
    return form.data[..., :].reshape(-1) if dim is None else None


def test_proportion_ci_clopper_pearson_matches_r_values():
    names = [f"x{i}" for i in range(4)]
    table = _table(names, {"successes": [30, 4, 0, 10], "trials": [100, 10, 5, 10]})
    out, _ = _run(ProportionCiStep(), (table,),
                  {"successes_label": "successes", "trials_label": "trials",
                   "method": "clopper_pearson", "output": "out"})
    values = out.data
    assert values[0, 1] == pytest.approx(0.2124064, abs=1e-6)
    assert values[0, 2] == pytest.approx(0.3998147, abs=1e-6)
    assert values[2, 1] == 0.0
    assert values[2, 2] == pytest.approx(0.5218239, abs=1e-6)


def test_proportion_ci_wilson_and_errors():
    names = ["a"]
    table = _table(names, {"successes": [30], "trials": [100]})
    out, exported = _run(ProportionCiStep(), (table,),
                         {"successes_label": "successes", "trials_label": "trials",
                          "method": "wilson", "output": "out"})
    low, high = float(out.data[0, 1]), float(out.data[0, 2])
    assert 0.21 < low < 0.23
    assert 0.38 < high < 0.41
    assert exported["p_hat"] == pytest.approx([0.3])

    bad = _table(["b"], {"successes": [5], "trials": [3]})
    with pytest.raises(StepError, match="successes must lie"):
        _run(ProportionCiStep(), (bad,),
             {"successes_label": "successes", "trials_label": "trials"})
    with pytest.raises(StepError, match="unknown method"):
        _run(ProportionCiStep(), (table,),
             {"successes_label": "successes", "trials_label": "trials",
              "method": "jackknife"})


def test_poisson_test_exact_rates():
    table = _table(["n1"], {"counts": [5], "exposure": [1]})
    out, exported = _run(PoissonTestStep(), (table,),
                         {"counts_label": "counts", "exposure_label": "exposure",
                          "rate": 2.0, "output": "out"})
    rate, low, high, p_value, expected = out.data[0]
    assert rate == pytest.approx(5.0)
    assert expected == pytest.approx(2.0)
    assert low < 5.0 < high
    assert p_value == pytest.approx(0.05265302, abs=1e-6)
    assert exported["p_value"] == pytest.approx([p_value])


def test_poisson_test_one_sided_and_errors():
    table = _table(["n1"], {"counts": [5], "exposure": [1]})
    greater, _ = _run(PoissonTestStep(), (table,),
                      {"counts_label": "counts", "exposure_label": "exposure",
                       "rate": 2.0, "alternative": "greater", "output": "out"})
    assert greater.data[0, 3] == pytest.approx(0.052653, abs=1e-6)
    bad = _table(["n2"], {"counts": [3], "exposure": [0]})
    with pytest.raises(StepError, match="exposure must be positive"):
        _run(PoissonTestStep(), (bad,),
             {"counts_label": "counts", "exposure_label": "exposure"})


def test_chisq_gof_uniform_and_custom():
    table = _table(["a", "b", "c"], {"counts": [10, 20, 30]})
    out, _ = _run(ChisqGofStep(), (table,), {"counts_label": "counts"})
    assert out.data[0, 0] == pytest.approx(10.0)
    assert out.data[1, 0] == pytest.approx(2.0)
    assert out.data[2, 0] == pytest.approx(0.0067379, abs=1e-7)
    with pytest.raises(StepError, match="probabilities must have one entry"):
        _run(ChisqGofStep(), (table,),
             {"counts_label": "counts", "probabilities": [0.5, 0.5]})


def test_rda_recovers_constrained_structure():
    rng = np.random.default_rng(20261102)
    x = rng.normal(size=(12, 2))
    y = x @ np.array([[1.0, 0.0, 0.5], [0.0, 1.0, -0.5]]) + 0.1 * rng.normal(size=(12, 3))
    names = [f"s{i}" for i in range(12)]
    response = _form(y, ["sample", "response"],
                     {"sample": {n: i for i, n in enumerate(names)},
                      "response": {"y1": 0, "y2": 1, "y3": 2}})
    explanatory = _form(x, ["sample", "predictor"],
                        {"sample": {n: i for i, n in enumerate(names)},
                         "predictor": {"x1": 0, "x2": 1}})
    out, exported = _run(RdaStep(), (response, explanatory), {"output": "out"})
    eigenvalues = out.data[:, 0].astype(np.float64)
    proportions = out.data[:, 1].astype(np.float64)
    assert eigenvalues.size == 2
    assert eigenvalues[0] > eigenvalues[1] > 0
    assert proportions.sum() == pytest.approx(1.0)
    assert exported["rank"] == 2


def test_rda_rejects_mismatched_samples():
    response = _form([[1.0, 2.0], [2.0, 4.0], [3.0, 6.0]],
                     ["sample", "response"],
                     {"sample": {"a": 0, "b": 1, "c": 2},
                      "response": {"y1": 0, "y2": 1}})
    explanatory = _form([[1.0], [2.0], [3.0]], ["sample", "predictor"],
                        {"sample": {"a": 0, "b": 1, "z": 2},
                         "predictor": {"x": 0}})
    with pytest.raises(StepError, match="share sample labels"):
        _run(RdaStep(), (response, explanatory), {})

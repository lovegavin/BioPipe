"""Hand and authoritative checks for the 0.20 operator batch."""
from __future__ import annotations


import numpy as np
import pytest
import statsmodels.api as sm
from statsmodels.stats.diagnostic import het_breuschpagan
from statsmodels.stats.stattools import durbin_watson as sm_durbin_watson

from src.core import Form
from src.task.step.steps.anosim import AnosimStep
from src.task.step.steps.breusch_pagan import BreuschPaganStep
from src.task.step.steps.cohens_kappa import CohensKappaStep
from src.task.step.steps.durbin_watson import DurbinWatsonStep
from src.task.step.steps.egger_test import EggerTestStep
from src.task.step.steps.fleiss_kappa import FleissKappaStep
from src.task.step.steps.partial_mantel import PartialMantelStep
from src.task.step.steps.procrustes import ProcrustesStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params
        self.metadata = {}


def _form(data, dims, labels):
    form = Form(np.asarray(data, dtype=np.float32), list(dims), labels, {"missing_code": np.nan})
    form.validate()
    return form


def _labels(names):
    return {name: i for i, name in enumerate(names)}


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return ctx[params.get("output", step.name)], step.export(ctx)


def test_cohens_and_fleiss_kappa_match_statsmodels():
    table = _form([[20, 5], [10, 15]], ["rater_a", "rater_b"],
                  {"rater_a": _labels(["a", "b"]), "rater_b": _labels(["a", "b"])})
    out, info = _run(CohensKappaStep(), {}, [table])
    assert info["kappa"] == pytest.approx(0.4, rel=1e-6)
    assert info["p"] == pytest.approx(0.003892417, rel=1e-4)
    assert out.data.shape == (6, 1)

    counts = np.array([
        [0, 0, 0, 0, 14], [0, 2, 6, 4, 2], [0, 0, 3, 5, 6],
        [0, 3, 9, 2, 0], [2, 2, 8, 1, 1], [7, 7, 0, 0, 0],
        [3, 2, 6, 3, 0], [2, 5, 3, 2, 2], [6, 5, 2, 1, 0],
        [0, 2, 2, 3, 7],
    ], dtype=np.float32)
    form = _form(counts, ["subject", "category"],
                 {"subject": _labels([str(i) for i in range(10)]),
                  "category": _labels([str(i) for i in range(5)])})
    out, info = _run(FleissKappaStep(), {}, [form])
    assert info["kappa"] == pytest.approx(0.2099307, rel=1e-5)
    assert out.data.shape == (3, 1)


def test_breusch_pagan_and_durbin_watson_match_statsmodels():
    rng = np.random.default_rng(3)
    x = rng.normal(size=80)
    y = 1 + 0.5 * x + rng.normal(size=80) * (0.5 + 0.4 * np.abs(x))
    data = _form(np.column_stack([y, x]), ["sample", "variable"],
                 {"sample": _labels([str(i) for i in range(80)]),
                  "variable": _labels(["y", "x"])})
    out, info = _run(BreuschPaganStep(), {"response": "y"}, [data])
    design = sm.add_constant(x)
    expected = het_breuschpagan(sm.OLS(y, design).fit().resid, design)
    assert info["lm_statistic"] == pytest.approx(expected[0], rel=1e-5)
    assert info["lm_p"] == pytest.approx(expected[1], rel=1e-5)
    assert out.data.shape == (5, 1)

    out, info = _run(DurbinWatsonStep(), {"response": "y"}, [data])
    expected_dw = sm_durbin_watson(sm.OLS(y, design).fit().resid)
    assert info["dw"] == pytest.approx(expected_dw, rel=1e-7)
    assert out.data.shape == (2, 1)


def test_egger_test_matches_r_linear_regression():
    effect = np.array([0.2, -0.1, 0.4, 0.3, 0.05, 0.5], dtype=np.float32)
    se = np.array([0.05, 0.08, 0.1, 0.12, 0.07, 0.2], dtype=np.float32)
    form = _form(np.column_stack([effect, se]), ["study", "statistic"],
                 {"study": _labels([f"s{i}" for i in range(6)]),
                  "statistic": _labels(["effect", "se"])})
    out, info = _run(EggerTestStep(), {}, [form])
    assert info["intercept"] == pytest.approx(1.883214, rel=1e-5)
    assert info["slope"] == pytest.approx(0.0166146, rel=1e-4)
    assert info["p_intercept"] == pytest.approx(0.487185, rel=1e-4)
    assert info["p_slope"] == pytest.approx(0.9362847, rel=1e-4)
    assert out.data.shape == (9, 1)


def _distance_form(matrix):
    names = [f"s{i}" for i in range(matrix.shape[0])]
    return _form(matrix, ["sample", "sample_b"], {"sample": _labels(names), "sample_b": _labels(names)})


def test_anosim_matches_vegan_statistic():
    matrix = np.array([
        [0, 1, 2, 7, 8, 9], [1, 0, 3, 6, 7, 8], [2, 3, 0, 5, 6, 7],
        [7, 6, 5, 0, 1, 2], [8, 7, 6, 1, 0, 3], [9, 8, 7, 2, 3, 0],
    ], dtype=np.float32)
    meta = _form(np.array([[0], [0], [0], [1], [1], [1]]),
                 ["sample", "feature"],
                 {"sample": _labels([f"s{i}" for i in range(6)]), "feature": {"group": 0}})
    out, info = _run(AnosimStep(), {"group_label": "group", "n_perm": 99}, [_distance_form(matrix), meta])
    assert info["R"] == pytest.approx(1.0, abs=1e-7)
    assert info["n"] == 6 and info["n_groups"] == 2
    assert out.data.shape == (5, 1)


def test_procrustes_recovers_exact_rotation():
    x = np.array([[1, 2], [2, 1], [3, 4], [4, 3], [5, 6]], dtype=np.float32)
    rotation = np.array([[0.8, -0.6], [0.6, 0.8]])
    y = x @ rotation + np.array([2, -1])
    fx = _form(x, ["sample", "axis"],
               {"sample": _labels([f"s{i}" for i in range(5)]), "axis": _labels(["a0", "a1"])})
    fy = _form(y, ["sample", "axis"],
               {"sample": _labels([f"s{i}" for i in range(5)]), "axis": _labels(["a0", "a1"])})
    out, info = _run(ProcrustesStep(), {}, [fx, fy])
    assert info["ss"] == pytest.approx(0.0, abs=1e-8)
    assert info["r"] == pytest.approx(1.0, rel=1e-7)
    assert info["scale"] == pytest.approx(1.0, rel=1e-6)
    assert out.data.shape == (5, 1)


def test_partial_mantel_matches_vegan_statistic():
    a = np.array([[0, 1, 2, 7, 8, 9], [1, 0, 3, 6, 7, 8], [2, 3, 0, 5, 6, 7],
                  [7, 6, 5, 0, 1, 2], [8, 7, 6, 1, 0, 3], [9, 8, 7, 2, 3, 0]], dtype=np.float32)
    b = np.array([[0, 2, 3, 6, 7, 8], [2, 0, 4, 5, 6, 7], [3, 4, 0, 4, 5, 6],
                  [6, 5, 4, 0, 2, 3], [7, 6, 5, 2, 0, 4], [8, 7, 6, 3, 4, 0]], dtype=np.float32)
    c = np.array([[0, 1, 1, 5, 5, 6], [1, 0, 2, 5, 5, 6], [1, 2, 0, 4, 5, 6],
                  [5, 5, 4, 0, 1, 1], [5, 5, 5, 1, 0, 2], [6, 6, 6, 1, 2, 0]], dtype=np.float32)
    out, info = _run(PartialMantelStep(), {"n_perm": 99},
                     [_distance_form(a), _distance_form(b), _distance_form(c)])
    assert info["r"] == pytest.approx(0.923474, rel=1e-5)
    assert info["n"] == 6
    assert out.data.shape == (4, 1)

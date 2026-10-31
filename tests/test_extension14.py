"""Hand and authoritative checks for the 0.21 operator batch."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.decision_curve import DecisionCurveStep
from src.task.step.steps.delong_auc import DeLongAucStep
from src.task.step.steps.dunn_test import DunnTestStep
from src.task.step.steps.hosmer_lemeshow import HosmerLemeshowStep
from src.task.step.steps.linear_mixed_model import LinearMixedModelStep
from src.task.step.steps.ordinal_logistic import OrdinalLogisticStep
from src.task.step.steps.storey_qvalue import StoreyQvalueStep
from src.task.step.steps.stuart_maxwell import StuartMaxwellStep


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


def test_storey_qvalues_match_bh_and_fixed_pi0():
    p = np.array(
        [
            0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205, 0.212,
            0.216, 0.222, 0.251, 0.269, 0.275, 0.34, 0.341, 0.384, 0.569,
            0.594, 0.696, 0.762, 0.94, 0.942, 0.97, 0.986,
        ],
        dtype=np.float32,
    )
    form = _form(
        p.reshape(-1, 1),
        ["feature", "statistic"],
        {"feature": _labels([f"g{i}" for i in range(len(p))]), "statistic": {"pvalue": 0}},
    )
    out, info = _run(StoreyQvalueStep(), {"value_dim": "statistic"}, [form])
    expected = np.array(
        [
            0.016, 0.064, 0.1344, 0.1344, 0.1344, 0.16, 0.169142857143,
            0.314285714286, 0.314285714286, 0.314285714286, 0.314285714286,
            0.314285714286, 0.314285714286, 0.314285714286, 0.341, 0.341,
            0.361411764706, 0.500210526316, 0.500210526316, 0.5568,
            0.580571428571, 0.63104, 0.63104, 0.63104, 0.63104,
        ],
        dtype=np.float64,
    )
    assert info["pi0"] == pytest.approx(0.64, rel=1e-6)
    assert np.allclose(out.data[:, 0], expected, atol=2e-5)
    assert out.data.shape == (len(p), 1)


def test_delong_auc_matches_proc_ci():
    labels = np.array([0] * 10 + [1] * 10, dtype=np.float32)
    scores = np.array(
        [
            0.05, 0.40, 0.15, 0.45, 0.25, 0.50, 0.35, 0.55, 0.45, 0.60,
            0.55, 0.65, 0.60, 0.70, 0.65, 0.75, 0.70, 0.80, 0.75, 0.85,
        ],
        dtype=np.float32,
    )
    names = [f"s{i}" for i in range(20)]
    label_form = _form(labels.reshape(-1, 1), ["sample", "label"],
                       {"sample": _labels(names), "label": {"label": 0}})
    score_form = _form(scores.reshape(-1, 1), ["sample", "score"],
                       {"sample": _labels(names), "score": {"score": 0}})
    out, info = _run(
        DeLongAucStep(),
        {"target_label": "label", "positive_label": "1", "score_label": "score"},
        [label_form, score_form],
    )
    assert info["auc"] == pytest.approx(0.98, rel=1e-7)
    assert info["ci_low"] == pytest.approx(0.937659938793, rel=1e-6)
    assert info["ci_high"] == pytest.approx(1.0, rel=1e-7)
    assert info["n_pos"] == 10 and info["n_neg"] == 10
    assert out.data.shape == (8, 1)


def test_dunn_matches_dunn_test():
    values = np.array(
        [1, 2, 2, 3, 4, 2, 3, 4, 5, 6, 4, 5, 6, 7, 8], dtype=np.float32
    )
    data = _form(
        values.reshape(1, -1),
        ["feature", "sample"],
        {"feature": {"expr": 0}, "sample": _labels([f"s{i}" for i in range(15)])},
    )
    meta = _form(
        np.array([[0], [0], [0], [0], [0], [1], [1], [1], [1], [1], [2], [2], [2], [2], [2]]),
        ["sample", "feature"],
        {"sample": _labels([f"s{i}" for i in range(15)]), "feature": {"group": 0}},
    )
    out, info = _run(DunnTestStep(), {"group_label": "group"}, [data, meta])
    assert info["n_groups"] == 3
    z = out.data[:, out.labels["statistic"]["z"]]
    praw = out.data[:, out.labels["statistic"]["P"]]
    padj = out.data[:, out.labels["statistic"]["P_adj"]]
    assert np.allclose(z, [-1.35689563192, -2.8209146032, -1.46401897128], atol=2e-5)
    assert np.allclose(praw, [0.0874071874886, 0.00239434743418, 0.0715943824427], atol=2e-5)
    # dunn.test's P.adjusted uses a non-monotone Holm variant; the operator
    # follows standard Holm (statsmodels multipletests).
    assert np.allclose(padj, [0.143188764885, 0.00718304230255, 0.143188764885], atol=2e-5)


def test_decision_curve_matches_dcurves():
    outcome = np.array([0, 1, 0, 1, 0, 1, 0, 1, 0, 0], dtype=np.float32)
    risk = np.array([0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95], dtype=np.float32)
    form = _form(
        np.column_stack([outcome, risk]),
        ["sample", "feature"],
        {"sample": _labels([f"s{i}" for i in range(10)]), "feature": _labels(["outcome", "risk"])},
    )
    out, info = _run(
        DecisionCurveStep(),
        {"outcome_label": "outcome", "risk_label": "risk", "thresholds": [0.2, 0.4, 0.6], "positive_label": "1"},
        [form],
    )
    nb = out.data[:, out.labels["statistic"]["net_benefit"]]
    assert np.allclose(nb, [0.175, -0.0666666667, -0.35], atol=2e-6)


def test_ordinal_logistic_matches_mass_polr():
    y = np.array([0, 1, 2, 0, 1, 2, 0, 1, 2, 0, 1, 2], dtype=np.float32)
    x = np.array([1, 2, 3, 2, 3, 4, 3, 4, 5, 4, 5, 6], dtype=np.float32)
    form = _form(
        np.column_stack([y, x]),
        ["sample", "feature"],
        {"sample": _labels([f"s{i}" for i in range(12)]), "feature": _labels(["y", "x"])},
    )
    out, info = _run(
        OrdinalLogisticStep(), {"response_label": "y", "predictors": ["x"]}, [form]
    )
    coef = out.data[:, out.labels["statistic"]["coef"]]
    assert coef[0] == pytest.approx(0.983237605203, rel=2e-4)
    assert coef[1] == pytest.approx(2.48556378685, rel=2e-4)
    assert coef[2] == pytest.approx(4.39686272255, rel=2e-4)
    assert info["loglike"] == pytest.approx(-10.7354485459, rel=1e-4)


def test_linear_mixed_model_matches_lme4():
    group = np.repeat(np.arange(4), 6).astype(np.float32)
    x = np.tile(np.arange(1, 7), 4).astype(np.float32)
    y = np.array([
        2.230925636013, 3.055454755394, 3.976353599363, 3.660887297726,
        4.475924473035, 5.039726085314, 3.712386418782, 3.928090592748,
        5.095342180996, 4.958363896364, 5.625295225238, 6.294525833239,
        4.382191393349, 4.688099306915, 6.034668688093, 5.306679274618,
        6.763581374276, 7.010742015405, 5.803848607638, 6.129679546362,
        7.127245761575, 6.640022254107, 7.976891460087, 8.586395492667,
    ], dtype=np.float32)
    form = _form(
        np.column_stack([y, x, group]),
        ["sample", "feature"],
        {"sample": _labels([f"s{i}" for i in range(24)]), "feature": _labels(["y", "x", "group"])},
    )
    out, info = _run(
        LinearMixedModelStep(),
        {"response_label": "y", "fixed_effects": ["x"], "group_label": "group"},
        [form],
    )
    assert info["group_var"] == pytest.approx(1.89809189484, rel=3e-4)
    assert info["residual_var"] == pytest.approx(0.120726328774, rel=3e-3)
    terms = out.labels["term"]
    coef = out.data[:, out.labels["statistic"]["coef"]]
    assert coef[terms["Intercept"]] == pytest.approx(3.5177141902, rel=3e-4)
    assert coef[terms["x"]] == pytest.approx(0.52474024529, rel=3e-4)



def test_hosmer_lemeshow_matches_resource_selection():
    outcome = np.array([0, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1, 0, 1, 1, 0, 1, 1, 0, 1], dtype=np.float32)
    probability = np.array(
        [.02, .05, .08, .11, .15, .19, .24, .29, .34, .39,
         .44, .49, .54, .59, .64, .69, .74, .79, .84, .95],
        dtype=np.float32,
    )
    names = [f"s{i}" for i in range(20)]
    form = _form(
        np.column_stack([outcome, probability]),
        ["sample", "feature"],
        {"sample": _labels(names), "feature": _labels(["outcome", "probability"])},
    )
    out, info = _run(
        HosmerLemeshowStep(),
        {"outcome_label": "outcome", "probability_label": "probability", "groups": 10},
        [form],
    )
    assert info["statistic"] == pytest.approx(18.6008, rel=1e-5)
    assert info["df"] == 8
    assert info["p"] == pytest.approx(0.017146656, rel=1e-5)
    assert info["n_bins"] == 10 and info["n"] == 20
    assert out.data.shape == (5, 1)


def test_stuart_maxwell_matches_desctools():
    table = np.array(
        [[5, 1, 1, 0], [2, 4, 0, 1], [0, 1, 3, 1], [0, 0, 2, 4]], dtype=int
    )
    a: list[int] = []
    b: list[int] = []
    for i, row in enumerate(table):
        for j, count in enumerate(row):
            a.extend([i + 1] * int(count))
            b.extend([j + 1] * int(count))
    names = [f"s{i}" for i in range(len(a))]
    form = _form(
        np.column_stack([np.asarray(a, dtype=float), np.asarray(b, dtype=float)]),
        ["sample", "feature"],
        {"sample": _labels(names), "feature": _labels(["a", "b"])},
    )
    out, info = _run(StuartMaxwellStep(), {"rater_a": "a", "rater_b": "b"}, [form])
    assert info["statistic"] == pytest.approx(0.4, rel=1e-9)
    assert info["df"] == 3
    assert info["p"] == pytest.approx(0.940242494839, rel=1e-9)
    assert info["n"] == 25 and info["n_categories"] == 4
    assert out.data.shape == (5, 1)

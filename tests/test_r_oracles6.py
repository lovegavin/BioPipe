"""Authoritative R checks for the 0.21 statistics operators."""
from __future__ import annotations

import shutil
import subprocess

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


R_SCRIPT = r"""
suppressPackageStartupMessages({
  library(pROC)
  library(dunn.test)
  library(dcurves)
  library(MASS)
  library(lme4)
  library(ResourceSelection)
  library(DescTools)
})

p <- c(0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205, 0.212,
       0.216, 0.222, 0.251, 0.269, 0.275, 0.34, 0.341, 0.384, 0.569,
       0.594, 0.696, 0.762, 0.94, 0.942, 0.97, 0.986)
pi0 <- mean(p >= 0.5) / (1 - 0.5)
qvals <- pmin(1, pi0 * p.adjust(p, method = "BH"))
cat("STOREY", paste(c(pi0, qvals), collapse = ","), "\n")

labels <- c(rep(0, 10), rep(1, 10))
scores <- c(0.05, 0.40, 0.15, 0.45, 0.25, 0.50, 0.35, 0.55, 0.45, 0.60,
            0.55, 0.65, 0.60, 0.70, 0.65, 0.75, 0.70, 0.80, 0.75, 0.85)
r <- roc(labels, scores, levels = c(0, 1), direction = "<", quiet = TRUE)
ci <- ci.auc(r, method = "delong")
cat("DELONG", paste(c(as.numeric(auc(r)), ci[1], ci[3]), collapse = ","), "\n")

x <- c(1, 2, 2, 3, 4, 2, 3, 4, 5, 6, 4, 5, 6, 7, 8)
g <- rep(c("a", "b", "c"), each = 5)
d <- dunn.test(x, g, method = "holm", kw = FALSE, table = FALSE)
cat("DUNNZ", paste(d$Z, collapse = ","), "\n")
cat("DUNNP", paste(d$P, collapse = ","), "\n")

df <- data.frame(
  outcome = c(0, 1, 0, 1, 0, 1, 0, 1, 0, 0),
  risk = c(0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95)
)
dc <- dca(outcome ~ risk, data = df, thresholds = c(0.2, 0.4, 0.6))
rr <- dc$dca[dc$dca$variable == "risk", ]
cat("DCA", paste(rr$net_benefit, collapse = ","), "\n")

y <- factor(c("low", "mid", "high", "low", "mid", "high", "low", "mid", "high",
              "low", "mid", "high"), levels = c("low", "mid", "high"), ordered = TRUE)
xx <- c(1, 2, 3, 2, 3, 4, 3, 4, 5, 4, 5, 6)
m <- polr(y ~ xx, method = "logistic", Hess = TRUE)
cat("ORD", paste(c(coef(m), m$zeta, as.numeric(logLik(m))), collapse = ","), "\n")

set.seed(2)
gg <- rep(letters[1:4], each = 6)
xxx <- rep(c(1, 2, 3, 4, 5, 6), 4)
yy <- 2 + 0.5 * xxx + rep(c(0, 1, 2, 3), each = 6) + rnorm(24, 0, 0.3)
mix <- lmer(yy ~ xxx + (1 | gg))
cat("MIX", paste(fixef(mix), collapse = ","), "\n")
vc <- as.data.frame(VarCorr(mix))
cat("MIXVC", paste(vc$vcov[1:2], collapse = ","), "\n")

hy <- c(0, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1, 0, 1, 1, 0, 1, 1, 0, 1)
hp <- c(.02, .05, .08, .11, .15, .19, .24, .29, .34, .39,
        .44, .49, .54, .59, .64, .69, .74, .79, .84, .95)
hl <- hoslem.test(hy, hp, g = 10)
cat("HL", paste(c(hl$statistic, hl$parameter, hl$p.value), collapse = ","), "\n")

st <- StuartMaxwellTest(matrix(c(5, 1, 1, 0, 2, 4, 0, 1,
                                  0, 1, 3, 1, 0, 0, 2, 4), nrow = 4, byrow = TRUE))
cat("STUART", paste(c(st$statistic, st$parameter, st$p.value), collapse = ","), "\n")
"""


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


def _r_values():
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript is not available")
    result = subprocess.run(
        ["Rscript", "-e", R_SCRIPT], capture_output=True, text=True, timeout=180
    )
    if result.returncode != 0:
        pytest.skip(f"R oracle failed: {result.stderr[-800:]}")
    values = {}
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 2:
            values[fields[0]] = [float(value) for value in fields[1].split(",")]
        elif fields:
            values[fields[0]] = []
    return values


def test_r_oracles_for_storey_delong_dunn_dca_ordinal_and_mixed():
    r = _r_values()
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
    assert info["pi0"] == pytest.approx(r["STOREY"][0], rel=1e-6)
    assert np.allclose(out.data[:, 0], r["STOREY"][1:], atol=2e-5)

    labels = np.array([0] * 10 + [1] * 10, dtype=np.float32)
    scores = np.array(
        [0.05, 0.40, 0.15, 0.45, 0.25, 0.50, 0.35, 0.55, 0.45, 0.60,
         0.55, 0.65, 0.60, 0.70, 0.65, 0.75, 0.70, 0.80, 0.75, 0.85],
        dtype=np.float32,
    )
    names = [f"s{i}" for i in range(20)]
    label_form = _form(labels.reshape(-1, 1), ["sample", "label"],
                       {"sample": _labels(names), "label": {"label": 0}})
    score_form = _form(scores.reshape(-1, 1), ["sample", "score"],
                       {"sample": _labels(names), "score": {"score": 0}})
    _, delong = _run(
        DeLongAucStep(),
        {"target_label": "label", "positive_label": "1", "score_label": "score"},
        [label_form, score_form],
    )
    assert delong["auc"] == pytest.approx(r["DELONG"][0], rel=1e-6)
    assert delong["ci_low"] == pytest.approx(r["DELONG"][1], rel=1e-5)
    assert delong["ci_high"] == pytest.approx(r["DELONG"][2], rel=1e-5)

    values = np.array([1, 2, 2, 3, 4, 2, 3, 4, 5, 6, 4, 5, 6, 7, 8], dtype=np.float32)
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
    dunn_out, _ = _run(DunnTestStep(), {"group_label": "group"}, [data, meta])
    assert np.allclose(
        dunn_out.data[:, dunn_out.labels["statistic"]["z"]], r["DUNNZ"], atol=2e-5
    )
    assert np.allclose(
        dunn_out.data[:, dunn_out.labels["statistic"]["P"]], r["DUNNP"], atol=2e-5
    )

    outcome = np.array([0, 1, 0, 1, 0, 1, 0, 1, 0, 0], dtype=np.float32)
    risk = np.array([0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95], dtype=np.float32)
    dc_form = _form(
        np.column_stack([outcome, risk]),
        ["sample", "feature"],
        {"sample": _labels([f"s{i}" for i in range(10)]), "feature": _labels(["outcome", "risk"])},
    )
    dc_out, _ = _run(
        DecisionCurveStep(),
        {"outcome_label": "outcome", "risk_label": "risk", "thresholds": [0.2, 0.4, 0.6]},
        [dc_form],
    )
    assert np.allclose(
        dc_out.data[:, dc_out.labels["statistic"]["net_benefit"]], r["DCA"], atol=2e-6
    )

    y = np.array([0, 1, 2, 0, 1, 2, 0, 1, 2, 0, 1, 2], dtype=np.float32)
    x = np.array([1, 2, 3, 2, 3, 4, 3, 4, 5, 4, 5, 6], dtype=np.float32)
    ord_form = _form(
        np.column_stack([y, x]),
        ["sample", "feature"],
        {"sample": _labels([f"s{i}" for i in range(12)]), "feature": _labels(["y", "x"])},
    )
    ord_out, ord_info = _run(
        OrdinalLogisticStep(), {"response_label": "y", "predictors": ["x"]}, [ord_form]
    )
    coef = ord_out.data[:, ord_out.labels["statistic"]["coef"]]
    assert coef[0] == pytest.approx(r["ORD"][0], rel=2e-4)
    assert coef[1] == pytest.approx(r["ORD"][1], rel=2e-4)
    assert coef[2] == pytest.approx(r["ORD"][2], rel=2e-4)
    assert ord_info["loglike"] == pytest.approx(r["ORD"][3], rel=1e-4)

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
    mix_form = _form(
        np.column_stack([y, x, group]),
        ["sample", "feature"],
        {"sample": _labels([f"s{i}" for i in range(24)]), "feature": _labels(["y", "x", "group"])},
    )
    mix_out, mix_info = _run(
        LinearMixedModelStep(),
        {"response_label": "y", "fixed_effects": ["x"], "group_label": "group"},
        [mix_form],
    )
    terms = mix_out.labels["term"]
    coef = mix_out.data[:, mix_out.labels["statistic"]["coef"]]
    assert coef[terms["Intercept"]] == pytest.approx(r["MIX"][0], rel=3e-4)
    assert coef[terms["x"]] == pytest.approx(r["MIX"][1], rel=3e-4)
    assert mix_info["group_var"] == pytest.approx(r["MIXVC"][0], rel=3e-4)
    assert mix_info["residual_var"] == pytest.approx(r["MIXVC"][1], rel=3e-3)


def test_hosmer_lemeshow_and_stuart_maxwell_match_r():
    r = _r_values()
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
    _, info = _run(
        HosmerLemeshowStep(),
        {"outcome_label": "outcome", "probability_label": "probability", "groups": 10},
        [form],
    )
    assert info["statistic"] == pytest.approx(r["HL"][0], rel=1e-6)
    assert info["df"] == int(r["HL"][1])
    assert info["p"] == pytest.approx(r["HL"][2], rel=1e-6)

    table = np.array(
        [[5, 1, 1, 0], [2, 4, 0, 1], [0, 1, 3, 1], [0, 0, 2, 4]], dtype=int
    )
    a = []
    b = []
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
    _, info = _run(StuartMaxwellStep(), {"rater_a": "a", "rater_b": "b"}, [form])
    assert info["statistic"] == pytest.approx(r["STUART"][0], rel=1e-6)
    assert info["df"] == int(r["STUART"][1])
    assert info["p"] == pytest.approx(r["STUART"][2], rel=1e-6)

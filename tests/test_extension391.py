"""Contract and numeric tests for the causal-inference operators."""
from __future__ import annotations

import math

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps._causal_utils import fit_logit, roc_auc_score
from src.task.step.steps.propensity_score import PropensityScoreStep
from src.task.step.steps.psm_match import PsmMatchStep
from src.task.step.steps.psm_balance import PsmBalanceStep
from src.task.step.steps.psm_effect import PsmEffectStep


class Ctx:
    def __init__(self, params):
        self.step_params = dict(params)
        self.outputs = {}
        self.artifacts = {}

    def __setitem__(self, key, value):
        self.outputs[key] = value

    def __getitem__(self, key):
        return self.outputs[key]

    def artifact_path(self, name):
        return f"/tmp/{name}"


def table(columns, sample_prefix="s"):
    names = list(columns)
    data = np.column_stack([np.asarray(columns[name], dtype=float) for name in names])
    labels = {name: index for index, name in enumerate(names)}
    n = data.shape[0]
    return Form(data, dims=["sample", "field"],
                labels={"sample": {f"{sample_prefix}{i}": i for i in range(n)},
                        "field": labels})


def score_form(values, prefix="s"):
    data = np.asarray(values, dtype=float).reshape(-1, 1)
    return Form(data, dims=["sample", "statistic"],
                labels={"sample": {f"{prefix}{i}": i for i in range(len(values))},
                        "statistic": {"propensity": 0}})


def run(step, inputs, params):
    step.name = step.definition["id"]
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return ctx, ctx.outputs[params["output"]]


def test_fit_logit_recovers_signal():
    x = np.array([-2.0, -1.0, 0.0, 0.5, 1.0, 2.0])
    y = np.array([0, 0, 1, 0, 1, 1], dtype=float)
    beta, iterations = fit_logit(x, y)
    assert beta[1] > 0
    assert iterations >= 1
    assert roc_auc_score(y.astype(int), 1.0 / (1.0 + np.exp(-(beta[0] + beta[1] * x)))) > 0.8


def test_propensity_score_outputs_and_auc():
    data = table({"treat": [0, 0, 0, 1, 1, 1],
                  "x": [-2, -1, 0.2, 0.1, 1, 2]})
    ctx, out = run(PropensityScoreStep(),
                   [data], {"output": "propensity", "treatment_field": "treat",
                            "covariate_fields": "x"})
    assert out.data.shape == (6, 2)
    assert out.info["auc"] > 0.8
    assert out.info["n_treated"] == 3
    assert np.all((out.data[:, 0] > 0) & (out.data[:, 0] < 1))
    assert out.data[4, 0] > out.data[2, 0]


def test_propensity_score_rejects_non_binary():
    data = table({"treat": [0, 1, 2, 1], "x": [0, 1, 2, 3]})
    with pytest.raises(StepError, match="0/1"):
        run(PropensityScoreStep(), [data],
            {"output": "propensity", "treatment_field": "treat", "covariate_fields": "x"})


def test_match_nearest_pairs():
    data = table({"treat": [1, 0, 1, 0]})
    scores = score_form([0.9, 0.85, 0.1, 0.2])
    ctx, out = run(PsmMatchStep(), [data, scores],
                   {"output": "matched", "treatment_field": "treat",
                    "score_field": "propensity", "caliper": 1.0, "ratio": 1})
    assert out.info["n_pairs"] == 2
    assert out.info["n_matched_units"] == 4
    pair = out.data[:, 1]
    assert pair[0] == pair[1] != 0
    assert pair[2] == pair[3] != 0


def test_match_caliper_excludes_far_controls():
    data = table({"treat": [1, 0]})
    scores = score_form([0.9, 0.1])
    ctx, out = run(PsmMatchStep(), [data, scores],
                   {"output": "matched", "treatment_field": "treat",
                    "score_field": "propensity", "caliper": 0.0})
    assert out.info["n_pairs"] == 0
    assert out.info["n_matched_units"] == 0


def test_balance_reduces_smd():
    data = table({"treat": [1, 1, 0, 0, 0, 0],
                  "x": [10.0, 11.0, 10.1, 11.1, -5.0, -4.0]})
    matched = Form(np.column_stack([[1, 1, 1, 1, 0, 0], [1, 1, 1, 1, 0, 0]]),
                   dims=["sample", "field"],
                   labels={"sample": {f"s{i}": i for i in range(6)},
                           "field": {"matched": 0, "pair_id": 1}})
    ctx, out = run(PsmBalanceStep(), [data, matched],
                   {"output": "balance", "treatment_field": "treat", "covariate_fields": "x"})
    smd_before, smd_after = out.data[0, 0], out.data[0, 1]
    assert smd_before > 1.0
    assert abs(smd_after) < 0.2
    assert out.info["n_treated"] == 2 and out.info["n_control"] == 2


def test_effect_att_and_standard_error():
    data = table({"treat": [0, 0, 1, 1], "re78": [1.0, 3.0, 5.0, 7.0]})
    matched = Form(np.column_stack([[1, 1, 1, 1], [1, 1, 2, 2]]),
                   dims=["sample", "field"],
                   labels={"sample": {f"s{i}": i for i in range(4)},
                           "field": {"matched": 0, "pair_id": 1}})
    ctx, out = run(PsmEffectStep(), [data, matched],
                   {"output": "effect", "treatment_field": "treat", "outcome_field": "re78"})
    values = {name: out.data[index, 0] for name, index in out.labels["statistic"].items()}
    assert values["att"] == pytest.approx(4.0)
    assert values["se"] == pytest.approx(math.sqrt(2.0))
    assert values["t_stat"] == pytest.approx(2.8284271247461903)
    assert values["p_value"] == pytest.approx(math.erfc(2.0))
    assert out.info["n_treated"] == 2


def test_match_rejects_unaligned_scores():
    data = table({"treat": [1, 0, 1, 0]})
    scores = score_form([0.5, 0.5])
    with pytest.raises(StepError, match="align"):
        run(PsmMatchStep(), [data, scores],
            {"output": "matched", "treatment_field": "treat", "score_field": "propensity"})

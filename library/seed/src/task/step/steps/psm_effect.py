"""Average treatment effect on the treated from a matched sample."""
from __future__ import annotations

import math

import numpy as np

from src.core import Form, StepError
from src.task.step.base import Step
from src.task.step.steps._causal_utils import column, matched_samples, treatment_vector


class PsmEffectStep(Step):
    """Estimate the ATT and its OLS standard error on matched units."""

    provider = "operon-core"
    parameters_file = "psm_effect.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "psm_effect",
        "version": "1.0.0",
        "kind": "operator",
        "title": "psm_effect",
        "description": "Matched difference in means with OLS standard error.",
        "category": "Causal Inference",
        "icon": "Calculator",
        "contracts": {
            "version": 1,
            "inputs": [
                {"version": 1, "numeric": True, "ndim": 2,
                 "dims": [{"param": "sample_dim", "default": "sample"},
                          {"param": "field_dim", "default": "field"}],
                 "labels": []},
                {"version": 1, "numeric": True, "ndim": 2,
                 "dims": [{"param": "sample_dim", "default": "sample"},
                          {"param": "field_dim", "default": "field"}],
                 "labels": []},
            ],
            "output": {"mode": "declare",
                       "schema": {"ndim": 2, "numeric": True, "info_open": True}},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False,
                      "estimate": "estimate_memory"},
        "inputs_arity": 2,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = sum(int(getattr(item, "data", np.zeros(0)).nbytes) for item in inputs or [])
        return max(2 * size, 16 * 1024 ** 2), 4 * 1024 ** 2

    def run(self, ctx, inputs):
        params = ctx.step_params
        operator = "psm_effect"
        data, matched = inputs[0], inputs[1]
        sample_dim = params.get("sample_dim", "sample")
        field_dim = params.get("field_dim", "field")
        treatment_field = params.get("treatment_field", "treat")
        outcome_field = params.get("outcome_field", "re78")
        y = treatment_vector(data, field_dim, treatment_field, operator)
        outcome = column(data, field_dim, outcome_field, operator)
        if not np.all(np.isfinite(outcome)):
            raise StepError(f"{operator}: outcome '{outcome_field}' must be finite")
        keep = matched_samples(matched, sample_dim, field_dim, operator)
        if keep.size != y.size:
            raise StepError(f"{operator}: matched flags do not align with samples")
        treated = keep & (y == 1)
        control = keep & (y == 0)
        if treated.sum() < 2 or control.sum() < 2:
            raise StepError(f"{operator}: matched sample is too small for an effect")
        treated_values = outcome[treated]
        control_values = outcome[control]
        att = float(treated_values.mean() - control_values.mean())
        design = np.column_stack([np.ones(int(treated.sum()) + int(control.sum())),
                                  np.concatenate([np.ones(int(treated.sum())),
                                                  np.zeros(int(control.sum()))])])
        values = np.concatenate([treated_values, control_values])
        beta, *_ = np.linalg.lstsq(design, values, rcond=None)
        residual = values - design @ beta
        dof = max(values.size - 2, 1)
        sigma2 = float(residual @ residual / dof)
        covariance = sigma2 * np.linalg.inv(design.T @ design)
        se = float(math.sqrt(max(covariance[1, 1], 0.0)))
        if se == 0:
            raise StepError(f"{operator}: effect standard error is zero")
        t_stat = att / se
        p_value = math.erfc(abs(t_stat) / math.sqrt(2.0))
        z = 1.959963984540054
        rows = [
            ["att", att], ["se", se], ["t_stat", t_stat], ["p_value", p_value],
            ["ci_low", att - z * se], ["ci_high", att + z * se],
            ["n_treated", float(treated.sum())], ["n_control", float(control.sum())],
        ]
        out = Form(
            np.asarray([[value] for _, value in rows], dtype=float)[:, 0:1],
            dims=["statistic", "value"],
            labels={"statistic": {name: index for index, (name, _) in enumerate(rows)},
                    "value": {"value": 0}},
            info={"att": att, "se": se, "n_treated": int(treated.sum()),
                  "n_control": int(control.sum()), "outcome_field": outcome_field},
        )
        out.validate()
        self._export_data = {
            "att": att, "se": se, "t_stat": t_stat, "p_value": p_value,
            "ci_low": att - z * se, "ci_high": att + z * se,
            "n_treated": int(treated.sum()), "n_control": int(control.sum()),
        }
        ctx[params.get("output", "effect")] = out

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))

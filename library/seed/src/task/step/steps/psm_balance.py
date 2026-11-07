"""Covariate balance before and after propensity-score matching."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.step.base import Step
from src.task.step.steps._causal_utils import (
    covariate_matrix, column, matched_samples, standardized_mean_difference,
    treatment_vector, variance_ratio,
)


class PsmBalanceStep(Step):
    """Report standardized mean differences and variance ratios."""

    provider = "operon-core"
    parameters_file = "psm_balance.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "psm_balance",
        "version": "1.0.0",
        "kind": "operator",
        "title": "psm_balance",
        "description": "Covariate balance diagnostics for a matched sample.",
        "category": "Causal Inference",
        "icon": "Scale",
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
        return max(3 * size, 16 * 1024 ** 2), 4 * 1024 ** 2

    def run(self, ctx, inputs):
        params = ctx.step_params
        operator = "psm_balance"
        data, matched = inputs[0], inputs[1]
        sample_dim = params.get("sample_dim", "sample")
        field_dim = params.get("field_dim", "field")
        treatment_field = params.get("treatment_field", "treat")
        covariates = str(params.get("covariate_fields", "age,educ,black,hispan,married,nodegree,re74,re75")).split(",")
        y = treatment_vector(data, field_dim, treatment_field, operator)
        X = covariate_matrix(data, field_dim, covariates, operator)
        if X.shape[0] != y.size:
            raise StepError(f"{operator}: covariates are not parallel to samples")
        keep = matched_samples(matched, sample_dim, field_dim, operator)
        if keep.size != y.size:
            raise StepError(f"{operator}: matched flags do not align with samples")
        treated_all = y == 1
        control_all = y == 0
        treated_after = treated_all & keep
        control_after = control_all & keep
        if treated_after.sum() < 2 or control_after.sum() < 2:
            raise StepError(f"{operator}: matched sample is too small for balance")
        names = [item.strip() for item in covariates if item.strip()]
        rows = []
        max_abs = 0.0
        for index, name in enumerate(names):
            column_values = X[:, index]
            before = standardized_mean_difference(column_values[treated_all],
                                                  column_values[control_all])
            after = standardized_mean_difference(column_values[treated_after],
                                                 column_values[control_after])
            rows.append([
                before,
                after,
                variance_ratio(column_values[treated_all], column_values[control_all]),
                variance_ratio(column_values[treated_after], column_values[control_after]),
            ])
            if np.isfinite(after):
                max_abs = max(max_abs, abs(after))
        out = Form(
            np.asarray(rows, dtype=float),
            dims=[params.get("covariate_dim", "covariate"), "statistic"],
            labels={params.get("covariate_dim", "covariate"): {name: i for i, name in enumerate(names)},
                    "statistic": {"smd_before": 0, "smd_after": 1,
                                  "vr_before": 2, "vr_after": 3}},
            info={
                "max_abs_smd_after": float(max_abs),
                "n_treated": int(treated_after.sum()),
                "n_control": int(control_after.sum()),
                "n_covariates": len(names),
            },
        )
        out.validate()
        self._export_data = {
            "n_covariates": len(names),
            "max_abs_smd_after": float(max_abs),
            "n_treated": int(treated_after.sum()),
            "n_control": int(control_after.sum()),
        }
        ctx[params.get("output", "balance")] = out

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))

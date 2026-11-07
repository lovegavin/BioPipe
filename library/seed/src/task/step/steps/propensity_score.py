"""Propensity score estimation by unpenalized logistic regression."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.step.base import Step
from src.task.step.steps._causal_utils import (
    covariate_matrix, fit_logit, roc_auc_score, sigmoid, treatment_vector,
)

_DEFAULT_COVARIATES = "age,educ,black,hispan,married,nodegree,re74,re75"


class PropensityScoreStep(Step):
    """Estimate propensity scores and report model fit."""

    provider = "operon-core"
    parameters_file = "propensity_score.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "propensity_score",
        "version": "1.0.0",
        "kind": "operator",
        "title": "propensity_score",
        "description": "Logistic propensity score for a binary treatment with covariates.",
        "category": "Causal Inference",
        "icon": "TrendingUp",
        "contracts": {
            "version": 1,
            "inputs": [
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
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = sum(int(getattr(item, "data", np.zeros(0)).nbytes) for item in inputs or [])
        return max(2 * size, 16 * 1024 ** 2), 4 * 1024 ** 2

    def run(self, ctx, inputs):
        params = ctx.step_params
        operator = "propensity_score"
        data = inputs[0]
        if getattr(data.data, "ndim", 0) != 2:
            raise StepError(f"{operator}: input must be a two-dimensional table")
        sample_dim = params.get("sample_dim", "sample")
        field_dim = params.get("field_dim", "field")
        treatment_field = params.get("treatment_field", "treat")
        covariates = str(params.get("covariate_fields", _DEFAULT_COVARIATES)).split(",")
        y = treatment_vector(data, field_dim, treatment_field, operator)
        X = covariate_matrix(data, field_dim, covariates, operator)
        if X.shape[0] != y.size:
            raise StepError(f"{operator}: covariates are not parallel to samples")
        beta, iterations = fit_logit(X, y.astype(float))
        eta = beta[0] + X @ beta[1:]
        propensity = sigmoid(eta)
        names = [item.strip() for item in covariates if item.strip()]
        coefficients = {"intercept": float(beta[0])}
        coefficients.update({name: float(value) for name, value in zip(names, beta[1:])})
        sample_labels = dict(data.labels.get(sample_dim, {}))
        if len(sample_labels) != y.size:
            sample_labels = {f"s{index}": index for index in range(y.size)}
        out = Form(
            np.column_stack([propensity, eta]),
            dims=[sample_dim, "statistic"],
            labels={sample_dim: sample_labels,
                    "statistic": {"propensity": 0, "logit": 1}},
            info={
                "coefficients": coefficients,
                "auc": float(roc_auc_score(y, propensity)),
                "n_samples": int(y.size),
                "n_treated": int(np.sum(y == 1)),
                "n_control": int(np.sum(y == 0)),
                "iterations": int(iterations),
                "treatment_field": treatment_field,
                "covariates": names,
            },
        )
        out.validate()
        self._export_data = {
            "n_samples": int(y.size),
            "n_treated": int(np.sum(y == 1)),
            "n_control": int(np.sum(y == 0)),
            "auc": float(roc_auc_score(y, propensity)),
            "ps_min": float(propensity.min()),
            "ps_max": float(propensity.max()),
            "iterations": int(iterations),
        }
        ctx[params.get("output", "propensity")] = out

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))

"""Pagel's lambda: phylogenetic signal of a continuous trait."""
from __future__ import annotations

import numpy as np
from scipy import optimize, stats

from src.core import Form, StepError
from src.task.step.base import Step
from src.task.step.steps._phylo_compare_utils import (
    lambda_loglik, load_comparative, tip_covariance,
)


class PhyloLambdaStep(Step):
    """Estimate Pagel's lambda by maximum likelihood under Brownian motion."""

    provider = "operon-core"
    parameters_file = "phylo_lambda.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "phylo_lambda",
        "version": "1.0.0",
        "kind": "operator",
        "title": "phylo_lambda",
        "description": "Maximum-likelihood Pagel's lambda for a continuous trait.",
        "category": "Phylogenetics",
        "icon": "Activity",
        "contracts": {
            "version": 1,
            "inputs": [
                {"version": 1, "numeric": True, "ndim": 2,
                 "dims": [{"param": "node_dim", "default": "node"},
                          {"param": "field_dim", "default": "field"}],
                 "labels": []},
                {"version": 1, "numeric": True, "ndim": 2,
                 "dims": [{"param": "sample_dim", "default": "sample"},
                          {"param": "statistic_dim", "default": "statistic"}],
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
        size = sum(int(getattr(item, "data", np.empty(0)).nbytes) for item in inputs) if inputs else 0
        return max(size * 4, 4 * 2 ** 20), 8 * 2 ** 20

    def run(self, ctx, inputs):
        params = ctx.step_params
        tree_form, trait_form = inputs[0], inputs[1]
        node_dim = str(params.get("node_dim", "node"))
        field_dim = str(params.get("field_dim", "field"))
        sample_dim = str(params.get("sample_dim", "sample"))
        statistic_dim = str(params.get("statistic_dim", "statistic"))
        value_field = str(params.get("value_field", "gc"))
        out_name = str(params.get("output", "lambda"))
        tree, values = load_comparative(
            tree_form, trait_form, node_dim, field_dim, sample_dim,
            statistic_dim, value_field, "phylo_lambda",
        )
        cov = tip_covariance(tree)

        def negative(lam):
            return -lambda_loglik(cov, values, float(lam))

        result = optimize.minimize_scalar(
            negative, bounds=(0.0, 1.0), method="bounded",
            options={"xatol": 1e-10},
        )
        if not result.success:
            raise StepError("phylo_lambda: lambda optimization did not converge")
        lam = float(result.x)
        log_likelihood = float(-result.fun)
        log_likelihood_zero = float(lambda_loglik(cov, values, 0.0))
        lr = 2.0 * (log_likelihood - log_likelihood_zero)
        p_value = float(0.5 * stats.chi2.sf(max(lr, 0.0), 1)) if lam > 1e-8 else 1.0

        summary = {
            "lambda": lam,
            "log_likelihood": log_likelihood,
            "log_likelihood_lambda0": log_likelihood_zero,
            "lr_statistic": float(lr),
            "p_value": p_value,
            "n_tips": len(tree.tips),
            "n_nodes": len(tree.names),
            "value_field": value_field,
        }
        rows = [
            ("lambda", lam),
            ("log_likelihood", log_likelihood),
            ("log_likelihood_lambda0", log_likelihood_zero),
            ("lr_statistic", float(lr)),
            ("p_value", p_value),
            ("n_tips", float(len(tree.tips))),
            ("n_nodes", float(len(tree.names))),
        ]
        data = np.asarray([[value] for _, value in rows], dtype=np.float64)
        out = Form(
            data,
            dims=[statistic_dim, "value"],
            labels={
                statistic_dim: {name: index for index, (name, _) in enumerate(rows)},
                "value": {"value": 0},
            },
            info=summary,
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = dict(summary)

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))

"""REML ancestral state reconstruction for a continuous trait."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.step.base import Step
from src.task.step.steps._phylo_compare_utils import (
    load_comparative, node_covariance, reml_ancestral, tip_covariance,
)


class PhyloAncestralStep(Step):
    """GLS/REML estimates of internal-node trait values under Brownian motion."""

    provider = "operon-core"
    parameters_file = "phylo_ancestral.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "phylo_ancestral",
        "version": "1.0.0",
        "kind": "operator",
        "title": "phylo_ancestral",
        "description": "REML ancestral states for a continuous trait on a tree.",
        "category": "Phylogenetics",
        "icon": "ArrowUp",
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
        out_name = str(params.get("output", "ancestral"))
        tree, values = load_comparative(
            tree_form, trait_form, node_dim, field_dim, sample_dim,
            statistic_dim, value_field, "phylo_ancestral",
        )
        cov = tip_covariance(tree)
        mean, inverse, residual = reml_ancestral(cov, values)
        cov_node, var_node = node_covariance(tree)
        internal = [node for node in range(len(tree.names)) if tree.children[node]]
        estimate = mean + cov_node @ (inverse @ residual)
        variance = var_node - np.einsum("ij,jk,ik->i", cov_node, inverse, cov_node)
        if np.any(variance < -1e-9):
            raise StepError(f"phylo_ancestral: negative ancestral variance {variance.min():.6g}")
        se = np.sqrt(np.clip(variance, 0.0, None))
        names = [tree.names[node] for node in internal]
        data = np.column_stack([estimate, se]).astype(np.float64)
        labels = {
            "node": {name: index for index, name in enumerate(names)},
            statistic_dim: {"estimate": 0, "standard_error": 1},
        }
        info = {
            "root_estimate": float(mean),
            "n_internal": len(internal),
            "n_tips": len(tree.tips),
            "value_field": value_field,
        }
        out = Form(data, dims=["node", statistic_dim], labels=labels, info=info)
        out.validate()
        ctx[out_name] = out
        self._export_data = dict(info)

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))

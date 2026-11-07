"""Felsenstein independent contrasts for a continuous trait."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._phylo_compare_utils import (
    felsenstein_contrasts, load_comparative,
)


class PhyloContrastsStep(Step):
    """Phylogenetically independent contrasts (Felsenstein 1985)."""

    provider = "operon-core"
    parameters_file = "phylo_contrasts.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "phylo_contrasts",
        "version": "1.0.0",
        "kind": "operator",
        "title": "phylo_contrasts",
        "description": "Felsenstein independent contrasts for a continuous trait.",
        "category": "Phylogenetics",
        "icon": "GitBranch",
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
        out_name = str(params.get("output", "contrasts"))
        tree, values = load_comparative(
            tree_form, trait_form, node_dim, field_dim, sample_dim,
            statistic_dim, value_field, "phylo_contrasts",
        )
        nodes, contrasts, variances = felsenstein_contrasts(tree, values)
        names = [tree.names[node] for node in nodes]
        data = np.column_stack([contrasts, variances]).astype(np.float64)
        labels = {
            "node": {name: index for index, name in enumerate(names)},
            statistic_dim: {"contrast": 0, "variance": 1},
        }
        info = {
            "n_contrasts": len(nodes),
            "n_tips": len(tree.tips),
            "total_variance": float(np.sum(variances)),
            "value_field": value_field,
        }
        out = Form(data, dims=["node", statistic_dim], labels=labels, info=info)
        out.validate()
        ctx[out_name] = out
        self._export_data = dict(info)

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))

"""Prune named tips from a rooted tree."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._tree_ops_utils import (
    encode_tree,
    newick_from_nodes,
    prune_tips,
    tip_nodes,
    tree_from_form,
    walk,
)


class TreePruneTipsStep(Step):
    provider = "operon-core"
    parameters_file = "tree_prune_tips.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "tree_prune_tips",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Prune tree tips",
        "description": (
            "Remove the named tips from a rooted tree, drop internal nodes that "
            "lose every child and merge the two edges of any node left with a "
            "single child."
        ),
        "category": "Genome",
        "icon": "Scissors",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        {"param": "node_dim", "default": "node"},
                        {"param": "field_dim", "default": "field"},
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {
            "memory_modes": ["full"],
            "supports_cuda": False,
            "estimate": "estimate_memory",
        },
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = int(getattr(inputs[0], "data", np.empty(0)).nbytes) if inputs else 0
        return max(size * 3, 4 * 2**20), size

    def run(self, ctx: Context, inputs) -> None:
        if not inputs:
            raise StepError("tree_prune_tips: a tree is required")
        params = ctx.step_params
        node_dim = str(params.get("node_dim", "node"))
        field_dim = str(params.get("field_dim", "field"))
        out_name = str(params.get("output", self.name))
        raw = str(params.get("tips", ""))
        remove = {item.strip() for item in raw.split(",") if item.strip()}
        if not remove:
            raise StepError("tree_prune_tips: parameter 'tips' is empty")

        root = tree_from_form(inputs[0], node_dim, field_dim, "tree_prune_tips")
        before = len(tip_nodes(root))
        pruned = prune_tips(root, remove)
        after = len(tip_nodes(pruned))
        out = encode_tree(pruned, node_dim, field_dim, out_name)
        out.info["newick"] = newick_from_nodes(pruned)
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_tips_before": before,
            "n_tips_after": after,
            "n_removed": before - after,
            "n_nodes": sum(1 for _ in walk(pruned)),
            "total_branch_length": float(np.nansum([node.length for node in walk(pruned)])),
        }

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))

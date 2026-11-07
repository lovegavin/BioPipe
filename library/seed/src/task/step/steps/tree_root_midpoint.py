"""Root a tree at the midpoint of its longest tip-to-tip path."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._tree_ops_utils import (
    encode_tree,
    midpoint_root,
    newick_from_nodes,
    tip_nodes,
    tree_diameter,
    tree_from_form,
    walk,
)


class TreeRootMidpointStep(Step):
    provider = "operon-core"
    parameters_file = "tree_root_midpoint.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "tree_root_midpoint",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Midpoint root a tree",
        "description": (
            "Root the tree at the midpoint of its longest tip-to-tip path. When "
            "the midpoint falls inside an edge a new root node splits that edge "
            "into two lengths whose sum is preserved."
        ),
        "category": "Genome",
        "icon": "GitCompare",
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
            raise StepError("tree_root_midpoint: a tree is required")
        params = ctx.step_params
        node_dim = str(params.get("node_dim", "node"))
        field_dim = str(params.get("field_dim", "field"))
        out_name = str(params.get("output", self.name))

        root = tree_from_form(inputs[0], node_dim, field_dim, "tree_root_midpoint")
        diameter, _, _ = tree_diameter(root)
        rooted = midpoint_root(root)
        out = encode_tree(rooted, node_dim, field_dim, out_name)
        out.info["newick"] = newick_from_nodes(rooted)
        out.validate()
        ctx[out_name] = out
        depths = []
        for tip in tip_nodes(rooted):
            total = 0.0
            node = tip
            while node.parent is not None:
                total += node.length
                node = node.parent
            depths.append(total)
        self._export_data = {
            "diameter": float(diameter),
            "n_tips": len(tip_nodes(rooted)),
            "n_nodes": sum(1 for _ in walk(rooted)),
            "max_root_to_tip": float(max(depths)),
            "min_root_to_tip": float(min(depths)),
            "total_branch_length": float(np.nansum([node.length for node in walk(rooted)])),
        }

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))

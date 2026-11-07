"""Robinson-Foulds and branch-score distance between two trees."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._phylo_common import load_tree
from ._phylo_infer import robinson_foulds


class PhylotreeDistanceStep(Step):
    provider = "operon-core"
    parameters_file = "phylo_tree_distance.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "phylo_tree_distance",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Tree topology distance",
        "description": (
            "Compare two trees on the same tips: Robinson-Foulds distance, "
            "normalised RF and Kuhner-Felsenstein branch score."
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
                },
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
                },
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
        "inputs_arity": 2,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = sum(int(getattr(item, "data", np.empty(0)).nbytes) for item in inputs) if inputs else 0
        return max(size * 2, 4 * 2**20), size

    def run(self, ctx: Context, inputs) -> None:
        if len(inputs) < 2:
            raise StepError("phylo_tree_distance: two trees are required")
        params = ctx.step_params
        node_dim = str(params.get("node_dim", "node"))
        field_dim = str(params.get("field_dim", "field"))
        statistic_dim = str(params.get("statistic_dim", "statistic"))
        out_name = str(params.get("output", self.name))

        tree_a = load_tree(inputs[0], node_dim, field_dim, label="phylo_tree_distance (tree A)")
        tree_b = load_tree(inputs[1], node_dim, field_dim, label="phylo_tree_distance (tree B)")
        summary = robinson_foulds(tree_a, tree_b)
        rows = [
            ("n_tips", float(summary["n_tips"])),
            ("rf", float(summary["rf"])),
            ("max_rf", float(summary["max_rf"])),
            ("normalized_rf", float(summary["normalized_rf"])),
            ("shared_splits", float(summary["shared_splits"])),
            ("splits_a", float(summary["splits_a"])),
            ("splits_b", float(summary["splits_b"])),
            ("branch_score", float(summary["branch_score"])),
            ("identical", 1.0 if summary["identical"] else 0.0),
        ]
        data = np.asarray([[value] for _, value in rows], dtype=np.float64)
        out = Form(
            data,
            dims=[statistic_dim, "value"],
            labels={
                statistic_dim: {name: index for index, (name, _) in enumerate(rows)},
                "value": {"value": 0},
            },
            info=dict(summary),
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = dict(summary)

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))

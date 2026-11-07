"""Shape statistics for a rooted tree (Sackin, Colless, cherries)."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._tree_ops_utils import balance_stats, tree_from_form


class TreeBalanceStep(Step):
    provider = "operon-core"
    parameters_file = "tree_balance.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "tree_balance",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Tree shape statistics",
        "description": (
            "Summarise the shape of a rooted tree: Sackin index, Colless index "
            "and normalised Colless (bifurcating trees only), cherry count and "
            "tip/internal node counts."
        ),
        "category": "Genome",
        "icon": "ChartBar",
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
        return max(size * 2, 4 * 2**20), size

    def run(self, ctx: Context, inputs) -> None:
        if not inputs:
            raise StepError("tree_balance: a tree is required")
        params = ctx.step_params
        node_dim = str(params.get("node_dim", "node"))
        field_dim = str(params.get("field_dim", "field"))
        statistic_dim = str(params.get("statistic_dim", "statistic"))
        out_name = str(params.get("output", self.name))

        root = tree_from_form(inputs[0], node_dim, field_dim, "tree_balance")
        stats = balance_stats(root)
        rows = [("n_tips", stats["n_tips"]), ("n_internal", stats["n_internal"]),
                ("sackin", stats["sackin"]), ("cherries", stats["cherries"])]
        if stats["colless"] is not None:
            rows.append(("colless", stats["colless"]))
            rows.append(("normalized_colless", stats["normalized_colless"]))
        data = np.asarray([[float(value)] for _, value in rows], dtype=np.float64)
        out = Form(
            data,
            dims=[statistic_dim, "value"],
            labels={
                statistic_dim: {name: index for index, (name, _) in enumerate(rows)},
                "value": {"value": 0},
            },
            info={"binary": bool(stats["binary"]), "sackin": float(stats["sackin"]),
                  "cherries": int(stats["cherries"]), "n_tips": stats["n_tips"]},
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = dict(stats)

    def export(self, ctx):
        data = dict(getattr(self, "_export_data", {}))
        return data

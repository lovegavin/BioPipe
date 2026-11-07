"""Greedy modularity communities for an undirected biological network."""
from __future__ import annotations

import numpy as np

from src.task.step.base import Step, Form
from src.task.context import Context

from ._network_utils import adjacency, greedy_communities, modularity, read_edges


class NetworkCommunitiesStep(Step):
    provider = "operon-core"
    parameters_file = "network_communities.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "network_communities",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Network communities",
        "description": "Greedy modularity (Clauset-Newman-Moore) communities for an undirected network.",
        "category": "Network",
        "icon": "Network",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        {"param": "edge_dim", "default": "edge"},
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
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = sum(int(getattr(item, "data", np.empty(0)).nbytes) for item in inputs) if inputs else 0
        return max(size * 4, 16 * 1024 * 1024), 4 * 1024 * 1024

    def run(self, ctx: Context, inputs):
        params = ctx.step_params
        nodes, edges = read_edges(
            inputs[0],
            str(params.get("edge_dim", "edge")),
            str(params.get("field_dim", "field")),
            str(params.get("node_a_field", "node_a")),
            str(params.get("node_b_field", "node_b")),
            str(params.get("weight_field", "")),
            "network_communities",
        )
        graph = adjacency(nodes, edges)
        resolution = float(params.get("resolution", 1.0))
        assignment, score = greedy_communities(graph, resolution=resolution)
        if resolution != 1.0:
            score = modularity(graph, assignment)
        out_name = str(params.get("output", "communities"))
        node_dim = str(params.get("node_dim", "node"))
        statistic_dim = str(params.get("statistic_dim", "statistic"))
        sizes = {}
        for name in nodes:
            sizes[assignment[name]] = sizes.get(assignment[name], 0) + 1
        data = np.asarray([[float(assignment[name])] for name in nodes], dtype=float)
        ctx[out_name] = Form(
            data,
            dims=[node_dim, statistic_dim],
            labels={node_dim: {name: index for index, name in enumerate(nodes)},
                    statistic_dim: {"community": 0}},
            info={"n_nodes": len(nodes), "n_communities": len(sizes),
                  "modularity": float(score), "sizes": sorted(sizes.values(), reverse=True)},
        )

    def export(self, ctx):
        form = ctx[str(ctx.step_params.get("output", "communities"))]
        return {"n_nodes": int(form.info["n_nodes"]),
                "n_communities": int(form.info["n_communities"]),
                "modularity": float(form.info["modularity"])}

"""Per-node centrality measures for an undirected biological network."""
from __future__ import annotations

import numpy as np

from src.task.step.base import Step, Form
from src.task.context import Context

from ._network_utils import (
    adjacency,
    betweenness,
    closeness,
    degrees,
    eigenvector,
    pagerank,
    read_edges,
)

_METRICS = ["degree", "betweenness", "closeness", "eigenvector", "pagerank"]


class NetworkCentralityStep(Step):
    provider = "operon-core"
    parameters_file = "network_centrality.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "network_centrality",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Network centrality",
        "description": "Degree, betweenness, closeness, eigenvector and PageRank centrality for every node.",
        "category": "Network",
        "icon": "Compass",
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
        return max(size * 4, 32 * 1024 * 1024), 8 * 1024 * 1024

    def run(self, ctx: Context, inputs):
        params = ctx.step_params
        nodes, edges = read_edges(
            inputs[0],
            str(params.get("edge_dim", "edge")),
            str(params.get("field_dim", "field")),
            str(params.get("node_a_field", "node_a")),
            str(params.get("node_b_field", "node_b")),
            str(params.get("weight_field", "")),
            "network_centrality",
        )
        graph = adjacency(nodes, edges)
        degree = degrees(graph)
        n = len(nodes)
        values = {
            "degree": {name: degree[name] / (n - 1) if n > 1 else 0.0 for name in nodes},
            "betweenness": betweenness(graph),
            "closeness": closeness(graph),
            "eigenvector": eigenvector(graph),
            "pagerank": pagerank(graph),
        }
        out_name = str(params.get("output", "centrality"))
        node_dim = str(params.get("node_dim", "node"))
        statistic_dim = str(params.get("statistic_dim", "statistic"))

        table = np.zeros((n, len(_METRICS)), dtype=float)
        for column, metric in enumerate(_METRICS):
            for row, name in enumerate(nodes):
                table[row, column] = values[metric][name]
        data = table
        ctx[out_name] = Form(
            data,
            dims=[node_dim, statistic_dim],
            labels={node_dim: {name: index for index, name in enumerate(nodes)},
                    statistic_dim: {metric: index for index, metric in enumerate(_METRICS)}},
            info={"n_nodes": n,
                  "top_degree": max(nodes, key=lambda name: values["degree"][name]),
                  "top_betweenness": max(nodes, key=lambda name: values["betweenness"][name]),
                  "top_pagerank": max(nodes, key=lambda name: values["pagerank"][name])},
        )

    def export(self, ctx):
        params = ctx.step_params
        form = ctx[str(params.get("output", "centrality"))]
        return {"n_nodes": int(form.info["n_nodes"]),
                "top_pagerank": form.info["top_pagerank"]}

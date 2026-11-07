"""Collapse poorly supported splits of a tree into polytomies."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.step.base import Step
from src.task.step.steps._phylo_common import load_tree
from src.task.step.steps._phylo_support_utils import read_support, split_label
from src.task.step.steps._tree_ops_utils import (
    encode_tree, newick_from_nodes, nodes_from_tree, suppress_unary, walk,
)


class PhyloSupportFilterStep(Step):
    """Remove splits whose bootstrap support is below a threshold."""

    provider = "operon-core"
    parameters_file = "phylo_support_filter.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "phylo_support_filter",
        "version": "1.0.0",
        "kind": "operator",
        "title": "phylo_support_filter",
        "description": "Collapse bootstrap splits below a support threshold.",
        "category": "Phylogenetics",
        "icon": "Filter",
        "contracts": {
            "version": 1,
            "inputs": [
                {"version": 1, "numeric": True, "ndim": 2,
                 "dims": [{"param": "node_dim", "default": "node"},
                          {"param": "field_dim", "default": "field"}],
                 "labels": []},
                {"version": 1, "numeric": True, "ndim": 2,
                 "dims": [{"param": "split_dim", "default": "split"},
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
        return max(size * 3, 4 * 2 ** 20), 2 * 2 ** 20

    def run(self, ctx, inputs):
        params = ctx.step_params
        node_dim = str(params.get("node_dim", "node"))
        field_dim = str(params.get("field_dim", "field"))
        split_dim = str(params.get("split_dim", "split"))
        statistic_dim = str(params.get("statistic_dim", "statistic"))
        support_field = str(params.get("support_field", "support"))
        threshold = float(params.get("min_support", 0.5))
        out_name = str(params.get("output", "tree"))
        tree = load_tree(inputs[0], node_dim, field_dim, "phylo_support_filter")
        support = read_support(inputs[1], split_dim, statistic_dim, support_field)
        root = nodes_from_tree(tree)
        tips = [node.name for node in walk(root) if not node.children]
        labels = {}
        for node in walk(root):
            if node is root or not node.children:
                continue
            below = {leaf.name for leaf in walk(node) if not leaf.children}
            if 2 <= len(below) <= len(tips) - 2:
                labels[id(node)] = split_label(below, tips)
        collapsed = 0
        for node in list(walk(root)):
            if node is root or not node.children or node.parent is None:
                continue
            label = labels.get(id(node))
            if label is None or label not in support:
                continue
            if support[label] >= threshold:
                continue
            parent = node.parent
            for child in list(node.children):
                child.parent = parent
                child.length += node.length
                parent.children.append(child)
            parent.children.remove(node)
            node.children = []
            node.parent = None
            collapsed += 1
        if collapsed == 0:
            raise StepError("phylo_support_filter: no split is below the threshold")
        root = suppress_unary(root)
        out = encode_tree(root, node_dim, field_dim, "tree")
        out.info["newick"] = newick_from_nodes(root)
        out.info["n_collapsed"] = collapsed
        out.info["min_support"] = threshold
        out.validate()
        ctx[out_name] = out
        self._export_data = {"n_collapsed": collapsed, "n_splits": len(labels)}

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))

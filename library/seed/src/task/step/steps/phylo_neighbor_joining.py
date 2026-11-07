"""Neighbour-joining tree construction from a distance matrix."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.reader.readers._encoder import get_encoder
from src.task.context import Context
from src.task.step.base import Step
from ._phylo_infer import neighbor_joining


class PhyloNeighborJoiningStep(Step):
    provider = "operon-core"
    parameters_file = "phylo_neighbor_joining.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "phylo_neighbor_joining",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Neighbour-joining tree",
        "description": (
            "Build a neighbour-joining tree from a square distance matrix and "
            "emit a node/field tree table plus a Newick representation."
        ),
        "category": "Genome",
        "icon": "TreeStructure",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        {"param": "taxon_dim", "default": "taxon"},
                        {"param": "taxon_b_dim", "default": "taxon_b"},
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
        return max(size * 2, 8 * 2**20), size

    def run(self, ctx: Context, inputs) -> None:
        if not inputs:
            raise StepError("phylo_neighbor_joining: a distance matrix is required")
        form = inputs[0]
        params = ctx.step_params
        taxon_dim = str(params.get("taxon_dim", "taxon"))
        taxon_b_dim = str(params.get("taxon_b_dim", "taxon_b"))
        node_dim = str(params.get("node_dim", "node"))
        field_dim = str(params.get("field_dim", "field"))
        out_name = str(params.get("output", self.name))

        if list(form.dims) != [taxon_dim, taxon_b_dim]:
            raise StepError(
                f"phylo_neighbor_joining: expected [{taxon_dim}, {taxon_b_dim}], got {list(form.dims)}"
            )
        row_labels = form.labels.get(taxon_dim, {})
        column_labels = form.labels.get(taxon_b_dim, {})
        if set(row_labels) != set(column_labels):
            raise StepError("phylo_neighbor_joining: row and column labels differ")
        names = [name for name, _ in sorted(row_labels.items(), key=lambda item: item[1])]
        order = [column_labels[name] for name in names]
        matrix = np.asarray(form.data, dtype=np.float64)[np.ix_(
            [row_labels[name] for name in names], order
        )]
        if np.any(~np.isfinite(matrix)):
            raise StepError("phylo_neighbor_joining: distance matrix contains missing values")

        edges, newick = neighbor_joining(matrix, names)
        fields = ["parent", "branch_length", "depth", "is_leaf"]
        parent_names = [parent for _, parent, _ in edges]
        encoder = get_encoder("labelencoder")
        parent_codes = encoder.fit_transform(parent_names)
        lengths = np.asarray([length for _, _, length in edges], dtype=np.float64)
        node_names = [node for node, _, _ in edges]
        index = {name: position for position, name in enumerate(node_names)}
        depth = np.zeros(len(node_names), dtype=np.float64)
        for name in node_names:
            cursor = name
            steps = 0
            while parent_names[index[cursor]] is not None:
                cursor = parent_names[index[cursor]]
                steps += 1
                if steps > len(node_names):
                    raise StepError("phylo_neighbor_joining: cycle in constructed tree")
            depth[index[name]] = steps
        has_child = {name: False for name in node_names}
        for parent in parent_names:
            if parent is not None:
                has_child[parent] = True
        leaf = np.asarray([0.0 if has_child[name] else 1.0 for name in node_names])
        data = np.column_stack([parent_codes, lengths, depth, leaf])
        out = Form(
            data,
            dims=[node_dim, field_dim],
            labels={
                node_dim: {name: position for position, name in enumerate(node_names)},
                field_dim: {name: position for position, name in enumerate(fields)},
            },
            info={
                "encoders": {field_dim: {"parent": encoder}},
                "newick": newick,
                "n_tips": len(names),
                "n_nodes": len(node_names),
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_tips": len(names),
            "n_nodes": len(node_names),
            "total_branch_length": float(lengths.sum()),
        }

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))

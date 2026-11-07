"""UPGMA tree from a pairwise distance matrix.

Unweighted pair-group method with arithmetic means: at each step the
closest clusters are joined at height ``d(i, j) / 2``; each child gets
the length ``height - child.height``; inter-cluster distances are
averaged with cluster sizes as weights. The result is ultrametric and
rooted, encoded like the Newick reader (parent / branch_length / depth /
is_leaf).
"""
from __future__ import annotations

import numpy as np

from src.task.context import Context
from src.task.step.base import Step

from ._tree_build_common import TreeNode, _InternalNamer, build_tree_form, distance_input


class UpgmaStep(Step):
    provider = 'operon-core'
    parameters_file = 'upgma.UpgmaStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'upgma',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'UPGMA tree',
     'category': 'Omics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'taxon_dim', 'default': 'taxon'},
                                        {'param': 'taxon_b_dim', 'default': 'taxon_b'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': True,
                                         'axis_info_open': True}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'dependencies': ['numpy>=1.26'],
     'dependency_imports': ['numpy'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'UPGMA (average linkage) tree from a symmetric pairwise distance matrix.'}

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        taxon_dim = ctx.step_params.get("taxon_dim", "taxon")
        taxon_b_dim = ctx.step_params.get("taxon_b_dim", "taxon_b")
        node_dim = ctx.step_params.get("node_dim", "node")
        field_dim = ctx.step_params.get("field_dim", "field")
        matrix, names = distance_input(form, taxon_dim, taxon_b_dim, "upgma")
        root, negative = _upgma(matrix, names)
        out = build_tree_form(root, node_dim, field_dim, "upgma", negative)
        ctx[ctx.step_params.get("output", self.name)] = out
        self._export = {
            "n_taxa": len(names),
            "taxa": list(names),
            "negative_branches_clipped": int(negative),
            "method": "upgma",
        }
        print(f"[{self.name}] n_taxa={len(names)}, negative_branches_clipped={negative}")

    def export(self, ctx: Context) -> dict:
        return self._export


def _upgma(matrix: np.ndarray, names) -> tuple[TreeNode, int]:
    distance = np.array(matrix, dtype=np.float64)
    distance = 0.5 * (distance + distance.T)
    live = [TreeNode(name) for name in names]
    sizes = [1 for _ in names]
    namer = _InternalNamer(names)
    negative = 0
    while len(live) > 1:
        m = len(live)
        ranked = np.array(distance, copy=True)
        np.fill_diagonal(ranked, np.inf)
        flat = int(np.argmin(ranked))
        i, j = divmod(flat, m)
        if i > j:
            i, j = j, i
        height = 0.5 * float(distance[i, j])
        parent = TreeNode(namer.next())
        parent.height = height
        parent.size = sizes[i] + sizes[j]
        for child in (live[i], live[j]):
            child.parent = parent
            length = height - child.height
            if length < 0:
                length = 0.0
                negative += 1
            child.length = float(length)
        parent.children = [live[i], live[j]]
        total = sizes[i] + sizes[j]
        new_row = (distance[i, :] * sizes[i] + distance[j, :] * sizes[j]) / total
        keep = [k for k in range(m) if k not in (i, j)]
        reduced = distance[np.ix_(keep, keep)]
        updated = np.zeros((len(keep) + 1, len(keep) + 1), dtype=np.float64)
        updated[: len(keep), : len(keep)] = reduced
        updated[-1, : len(keep)] = new_row[keep]
        updated[: len(keep), -1] = new_row[keep]
        distance = updated
        live = [live[k] for k in keep] + [parent]
        sizes = [sizes[k] for k in keep] + [total]
    root = live[0]
    root.parent = None
    root.length = np.nan
    return root, negative

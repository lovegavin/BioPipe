"""Neighbor-joining tree from a pairwise distance matrix.

The topology and branch lengths follow the Saitou-Nei neighbor-joining
algorithm: at each step the pair minimizing
``(m - 2) * d(i, j) - r(i) - r(j)`` is joined, with limb lengths
``d(i, j) / 2 + (r(i) - r(j)) / (2 * (m - 2))`` and ``d(i, j) - limb``.
The final two clusters are attached to a synthetic root with half of
their remaining distance.

The result is a ``node x field`` table in the same encoding used by the
Newick reader (parent / branch_length / depth / is_leaf), so it can be
consumed by the tree operators such as patristic distance.
"""
from __future__ import annotations

import numpy as np

from src.task.context import Context
from src.task.step.base import Step

from ._tree_build_common import TreeNode, _InternalNamer, build_tree_form, distance_input


class NeighborJoiningStep(Step):
    provider = 'operon-core'
    parameters_file = 'neighbor_joining.NeighborJoiningStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'neighbor_joining',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Neighbor joining tree',
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
     'description': 'Neighbor-joining tree from a symmetric pairwise distance matrix.'}

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        taxon_dim = ctx.step_params.get("taxon_dim", "taxon")
        taxon_b_dim = ctx.step_params.get("taxon_b_dim", "taxon_b")
        node_dim = ctx.step_params.get("node_dim", "node")
        field_dim = ctx.step_params.get("field_dim", "field")
        matrix, names = distance_input(form, taxon_dim, taxon_b_dim, "neighbor_joining")
        root, negative = _neighbor_joining(matrix, names)
        out = build_tree_form(root, node_dim, field_dim, "neighbor_joining", negative)
        ctx[ctx.step_params.get("output", self.name)] = out
        self._export = {
            "n_taxa": len(names),
            "taxa": list(names),
            "negative_branches_clipped": int(negative),
            "method": "neighbor_joining",
        }
        print(f"[{self.name}] n_taxa={len(names)}, negative_branches_clipped={negative}")

    def export(self, ctx: Context) -> dict:
        return self._export


def _neighbor_joining(matrix: np.ndarray, names) -> tuple[TreeNode, int]:
    distance = np.array(matrix, dtype=np.float64)
    distance = 0.5 * (distance + distance.T)
    live = [TreeNode(name) for name in names]
    namer = _InternalNamer(names)
    negative = 0
    while len(live) > 2:
        m = len(live)
        sums = distance.sum(axis=1)
        criteria = (m - 2.0) * distance - sums[:, None] - sums[None, :]
        np.fill_diagonal(criteria, np.inf)
        flat = int(np.argmin(criteria))
        i, j = divmod(flat, m)
        if i > j:
            i, j = j, i
        dij = float(distance[i, j])
        limb_i = 0.5 * dij + (sums[i] - sums[j]) / (2.0 * (m - 2))
        limb_j = dij - limb_i
        parent = TreeNode(namer.next())
        for child, limb in ((live[i], limb_i), (live[j], limb_j)):
            child.parent = parent
            if limb < 0:
                limb = 0.0
                negative += 1
            child.length = float(limb)
        parent.children = [live[i], live[j]]
        new_row = 0.5 * (distance[i, :] + distance[j, :] - dij)
        keep = [k for k in range(m) if k not in (i, j)]
        reduced = distance[np.ix_(keep, keep)]
        updated = np.zeros((len(keep) + 1, len(keep) + 1), dtype=np.float64)
        updated[: len(keep), : len(keep)] = reduced
        updated[-1, : len(keep)] = new_row[keep]
        updated[: len(keep), -1] = new_row[keep]
        distance = updated
        live = [live[k] for k in keep] + [parent]
    left, right = live[0], live[1]
    root = TreeNode(namer.next())
    root.children = [left, right]
    half = float(distance[0, 1]) / 2.0
    for child in (left, right):
        child.parent = root
        if half < 0:
            half = 0.0
            negative += 1
        child.length = half
    return root, negative

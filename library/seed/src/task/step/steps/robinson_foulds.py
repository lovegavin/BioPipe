"""Unweighted Robinson-Foulds distance between two trees.

Both inputs use the node x field encoding produced by the tree readers
(parent / branch_length / depth / is_leaf). The operator rebuilds each
topology with ``load_tree``, extracts the nontrivial bipartitions
(splits), canonically represents each split by its smaller side, and
reports the symmetric difference:

    rf            |splits(A) XOR splits(B)|
    max_rf        |splits(A)| + |splits(B)|
    normalized    rf / max_rf (0 when both trees have no nontrivial split)

The statistics match ``dendropy.calculate.treecompare.
unweighted_robinson_foulds_distance`` for unrooted topologies, with
trivial splits (size 1 and n - 1) excluded.
"""
from __future__ import annotations

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._phylo_common import load_tree
from ._stats20_common import scalar_form


class RobinsonFouldsStep(Step):
    provider = 'operon-core'
    parameters_file = 'robinson_foulds.RobinsonFouldsStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'robinson_foulds',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Robinson-Foulds distance',
     'category': 'Omics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'node_dim', 'default': 'node'},
                                        {'param': 'field_dim', 'default': 'field'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2},
                              {'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'node_dim_b', 'default': 'node'},
                                        {'param': 'field_dim_b', 'default': 'field'}],
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
     'inputs_arity': 2,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Unweighted Robinson-Foulds distance between two node x field trees.'}

    def run(self, ctx: Context, inputs) -> None:
        tree_a, tree_b = inputs
        node_dim = ctx.step_params.get("node_dim", "node")
        field_dim = ctx.step_params.get("field_dim", "field")
        node_dim_b = ctx.step_params.get("node_dim_b", "node")
        field_dim_b = ctx.step_params.get("field_dim_b", "field")
        first = load_tree(tree_a, node_dim, field_dim, "robinson_foulds: tree A")
        second = load_tree(tree_b, node_dim_b, field_dim_b, "robinson_foulds: tree B")
        tips_a = {first.names[index] for index in first.tips}
        tips_b = {second.names[index] for index in second.tips}
        if tips_a != tips_b:
            only_a = sorted(tips_a - tips_b)[:5]
            only_b = sorted(tips_b - tips_a)[:5]
            raise StepError(
                "robinson_foulds: the two trees must contain the same taxa "
                f"(only in A: {only_a}, only in B: {only_b})"
            )
        if len(tips_a) < 2:
            raise StepError("robinson_foulds: need at least two tips")
        splits_a = _splits(first)
        splits_b = _splits(second)
        false_positives = len(splits_a - splits_b)
        false_negatives = len(splits_b - splits_a)
        rf = false_positives + false_negatives
        max_rf = len(splits_a) + len(splits_b)
        normalized = float(rf) / float(max_rf) if max_rf else 0.0
        names = ["rf", "max_rf", "normalized_rf", "false_positives", "false_negatives", "n_tips"]
        values = [
            float(rf),
            float(max_rf),
            normalized,
            float(false_positives),
            float(false_negatives),
            float(len(tips_a)),
        ]
        out = scalar_form(values, names, "robinson_foulds")
        ctx[ctx.step_params.get("output", self.name)] = out
        self._export = {
            "rf": int(rf),
            "max_rf": int(max_rf),
            "normalized_rf": normalized,
            "n_tips": len(tips_a),
            "n_splits_a": len(splits_a),
            "n_splits_b": len(splits_b),
        }
        print(f"[{self.name}] rf={rf}, max_rf={max_rf}")

    def export(self, ctx: Context) -> dict:
        return self._export


def _descendant_tips(tree) -> dict[int, frozenset]:
    memo: dict[int, frozenset] = {}

    def collect(index: int) -> frozenset:
        cached = memo.get(index)
        if cached is not None:
            return cached
        if not tree.children[index]:
            values = frozenset([tree.names[index]])
        else:
            values = frozenset().union(*(collect(child) for child in tree.children[index]))
        memo[index] = values
        return values

    for index in range(len(tree.names)):
        collect(index)
    return memo


def _splits(tree) -> set[frozenset]:
    memo = _descendant_tips(tree)
    all_tips = frozenset(tree.names[index] for index in tree.tips)
    n = len(all_tips)
    splits: set[frozenset] = set()
    for index in range(len(tree.names)):
        if index == tree.root:
            continue
        part = _canonical(memo[index], all_tips)
        if len(part) < 2 or len(part) > n - 2:
            continue
        splits.add(part)
    return splits


def _canonical(part: frozenset, all_tips: frozenset) -> frozenset:
    """Represent a bipartition by its smaller side; ties break lexicographically."""
    other = all_tips - part
    if len(other) < len(part):
        return other
    if len(other) == len(part) and tuple(sorted(other)) < tuple(sorted(part)):
        return other
    return part


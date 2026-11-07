"""Cophenetic correlation between a tree and a sample distance matrix.

The cophenetic distance of two tips is the patristic distance implied
by the tree (sum of branch lengths along the path). This operator
compares that matrix, in tip order, with an observed sample distance
matrix and reports the Pearson correlation, its square, and the number
of tips and pairs.

It is the equivalent of ``ape::cophenetic.phylo`` followed by
``stats::cor`` with ``method = "pearson"``.
"""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._phylo_common import load_tree, tip_distances
from ._stats20_common import distance, scalar_form


class CopheneticCorrelationStep(Step):
    """Pearson correlation between tree patristic and observed distances."""

    provider = 'operon-core'
    parameters_file = 'cophenetic_correlation.CopheneticCorrelationStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'cophenetic_correlation',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Cophenetic correlation',
     'category': 'Statistics',
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
                               'dims': [{'param': 'sample_dim', 'default': 'sample'},
                                        {'param': 'sample_b_dim', 'default': 'sample_b'}],
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
     'description': 'Pearson correlation between tree patristic and observed sample distances.'}

    def run(self, ctx: Context, inputs) -> None:
        tree_form, matrix_form = inputs
        node_dim = ctx.step_params.get("node_dim", "node")
        field_dim = ctx.step_params.get("field_dim", "field")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        sample_b_dim = ctx.step_params.get("sample_b_dim", "sample_b")
        tree = load_tree(tree_form, node_dim, field_dim, "cophenetic_correlation: tree")
        matrix, labels = distance(
            matrix_form, sample_dim, sample_b_dim, "cophenetic_correlation"
        )
        tips = [tree.names[index] for index in tree.tips]
        if len(set(tips)) != len(tips):
            raise StepError("cophenetic_correlation: the tree has duplicate tip names")
        if set(tips) != set(labels):
            only_tree = sorted(set(tips) - set(labels))[:5]
            only_matrix = sorted(set(labels) - set(tips))[:5]
            raise StepError(
                "cophenetic_correlation: tree tips and distance labels differ "
                f"(only in tree: {only_tree}, only in matrix: {only_matrix})"
            )
        if len(tips) < 3:
            raise StepError("cophenetic_correlation: need at least three tips")
        order = [labels.index(name) for name in tips]
        observed = matrix[np.ix_(order, order)]
        expected = tip_distances(tree)
        lower = np.tril_indices(len(tips), -1)
        x = expected[lower]
        y = observed[lower]
        if np.std(x) <= 0.0 or np.std(y) <= 0.0:
            raise StepError(
                "cophenetic_correlation: distances are constant, correlation is undefined"
            )
        coefficient = float(np.corrcoef(x, y)[0, 1])
        out = scalar_form(
            [coefficient, coefficient * coefficient, float(len(tips)), float(x.size)],
            ["r", "r_squared", "n_tips", "n_pairs"],
            "cophenetic_correlation",
        )
        ctx[ctx.step_params.get("output", self.name)] = out
        self._export = {
            "r": coefficient,
            "r_squared": coefficient * coefficient,
            "n_tips": int(len(tips)),
            "n_pairs": int(x.size),
        }
        print(f"[{self.name}] r={coefficient:.6f}")

    def export(self, ctx: Context) -> dict:
        return self._export

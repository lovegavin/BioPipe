"""Patristic distances between the tips of a phylogenetic tree."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._phylo_common import load_tree, tip_distances


class PatristicDistanceStep(Step):
    """Sum of branch lengths along the path between every pair of tips."""

    provider = 'operon-core'
    parameters_file = 'patristic_distance.PatristicDistanceStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'patristic_distance',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Patristic distance',
        'category': 'Omics',
        'icon': 'TreeStructure',
        'contracts': {
            'version': 1,
            'inputs': [
                {'version': 1, 'numeric': True, 'info': {},
                 'dims': [{'param': 'node_dim', 'default': 'node'},
                          {'param': 'field_dim', 'default': 'field'}],
                 'labels': [], 'parallel': [], 'ndim': 2},
            ],
            'output': {'mode': 'declare',
                       'schema': {'ndim': 2,
                                  'numeric': True,
                                  'info_open': True,
                                  'axis_info_open': True}},
        },
        'resources': {'memory_modes': ['full'], 'supports_cuda': False,
                      'estimate': 'estimate_memory'},
        'inputs_arity': 1,
        'outputs': [],
        'output_parameter': 'output',
        'description': 'Patristic distance：接收 1 个输入，输出 tip × tip 距离矩阵；主要参数：节点维度、字段维度、tip 维度。',
    }

    def run(self, ctx: Context, inputs) -> None:
        tree_form = inputs[0]
        node_dim = ctx.step_params.get("node_dim", "node")
        field_dim = ctx.step_params.get("field_dim", "field")
        tip_dim = ctx.step_params.get("tip_dim", "tip")
        out_name = ctx.step_params.get("output", self.name)

        tree = load_tree(tree_form, node_dim, field_dim, label="patristic_distance")
        if len(tree.tips) < 2:
            raise StepError("patristic_distance: the tree needs at least two tips")
        matrix = tip_distances(tree)
        names = [tree.names[index] for index in tree.tips]
        out_dim_b = f"{tip_dim}_b"
        labels = {
            tip_dim: {name: index for index, name in enumerate(names)},
            out_dim_b: {name: index for index, name in enumerate(names)},
        }

        ctx[out_name] = Form(
            data=matrix.astype(np.float32),
            dims=[tip_dim, out_dim_b],
            labels=labels,
            info={
                "missing_code": np.nan,
                "representation": "patristic_distance",
                "n_tips": int(len(tree.tips)),
            },
        )
        finite = matrix[np.isfinite(matrix)]
        self._export_data = {
            "n_tips": int(len(tree.tips)),
            "mean": float(finite.mean()) if finite.size else None,
            "max": float(finite.max()) if finite.size else None,
        }
        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "n_tips": int(len(tree.tips)),
        }

    def export(self, ctx: Context) -> dict:
        return dict(self._export_data)

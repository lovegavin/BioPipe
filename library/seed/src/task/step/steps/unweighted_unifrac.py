"""Unweighted UniFrac distance between samples."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._microbiome import estimate, metadata
from src.task.step.steps._phylo_common import (
    abundance_matrix,
    load_tree,
    node_counts,
    unifrac_matrix,
)


class UnweightedUnifracStep(Step):
    """Unweighted UniFrac: fraction of unique branch length between two samples."""

    provider = 'operon-microbiome'
    parameters_file = 'unweighted_unifrac.UnweightedUnifracStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'unweighted_unifrac',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Unweighted UniFrac',
        'category': 'Omics',
        'icon': 'TreeStructure',
        'contracts': {
            'version': 1,
            'inputs': [
                {'version': 1, 'numeric': True, 'info': {},
                 'dims': [{'param': 'sample_dim', 'default': 'sample'},
                          {'param': 'taxon_dim', 'default': 'taxon'}],
                 'labels': [], 'parallel': [], 'ndim': 2},
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
        'inputs_arity': 2,
        'outputs': [],
        'output_parameter': 'output',
        'description': 'Unweighted UniFrac：接收 2 个输入，输出距离矩阵；主要参数：样本维度、类群维度、节点维度、字段维度。',
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return estimate(cls.name, inputs, params, profiles)

    def run(self, ctx: Context, inputs) -> None:
        counts_form, tree_form = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        taxon_dim = ctx.step_params.get("taxon_dim", "taxon")
        node_dim = ctx.step_params.get("node_dim", "node")
        field_dim = ctx.step_params.get("field_dim", "field")
        out_name = ctx.step_params.get("output", self.name)

        counts, samples, taxa = abundance_matrix(
            counts_form, sample_dim, taxon_dim, label="unweighted_unifrac"
        )
        if counts.shape[0] < 2:
            raise StepError("unweighted_unifrac: need at least two samples")
        tree = load_tree(tree_form, node_dim, field_dim, label="unweighted_unifrac")
        by_node = node_counts(counts, taxa, tree, label="unweighted_unifrac")
        matrix = unifrac_matrix(by_node, tree.length, weighted=False)

        out_dim_b = f"{sample_dim}_b"
        labels = {
            sample_dim: {name: index for index, name in enumerate(samples)},
            out_dim_b: {name: index for index, name in enumerate(samples)},
        }
        info, axes = metadata(counts_form, [sample_dim], "unweighted_unifrac")
        info.update(n_taxa=int(counts.shape[1]), n_tips=int(len(tree.tips)))
        ctx[out_name] = Form(
            data=matrix.astype(np.float32),
            dims=[sample_dim, out_dim_b],
            labels=labels,
            info=info,
            axis_info=axes,
        )
        finite = matrix[np.isfinite(matrix)]
        self._export_data = {
            "n_samples": int(counts.shape[0]),
            "n_taxa": int(counts.shape[1]),
            "n_tips": int(len(tree.tips)),
            "mean": float(finite.mean()) if finite.size else None,
            "max": float(finite.max()) if finite.size else None,
        }
        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "n_samples": int(counts.shape[0]),
            "n_tips": int(len(tree.tips)),
        }

    def export(self, ctx: Context) -> dict:
        return dict(self._export_data)

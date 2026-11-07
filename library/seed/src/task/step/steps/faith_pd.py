"""Faith's phylogenetic diversity (PD) for every sample."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._microbiome import estimate, metadata
from src.task.step.steps._phylo_common import (
    abundance_matrix,
    faith_pd_values,
    load_tree,
    node_counts,
)


class FaithPdStep(Step):
    """Faith's phylogenetic diversity: branch length spanned by the observed taxa."""

    provider = 'operon-microbiome'
    parameters_file = 'faith_pd.FaithPdStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'faith_pd',
        'version': '1.0.0',
        'kind': 'operator',
        'title': "Faith's phylogenetic diversity",
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
        'description': "Faith's PD：接收 2 个输入，输出 Form；主要参数：样本维度、类群维度、节点维度、字段维度。",
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
            counts_form, sample_dim, taxon_dim, label="faith_pd"
        )
        if counts.shape[0] < 1:
            raise StepError("faith_pd: the abundance table has no samples")
        tree = load_tree(tree_form, node_dim, field_dim, label="faith_pd")
        by_node = node_counts(counts, taxa, tree, label="faith_pd")
        pd = faith_pd_values(by_node, tree.length)
        observed = (counts > 0).sum(axis=1)
        data = np.stack(
            [pd, observed.astype(np.float64), np.full(pd.shape, len(tree.tips), dtype=np.float64)],
            axis=1,
        )

        info, axes = metadata(counts_form, [sample_dim], "faith_pd")
        info.update(n_taxa=int(counts.shape[1]), n_tips=int(len(tree.tips)))
        ctx[out_name] = Form(
            data=data.astype(np.float32),
            dims=[sample_dim, "statistic"],
            labels={
                sample_dim: {name: index for index, name in enumerate(samples)},
                "statistic": {"pd": 0, "n_taxa_observed": 1, "n_tips": 2},
            },
            info=info,
            axis_info=axes,
        )
        finite = pd[np.isfinite(pd)]
        self._export_data = {
            "n_samples": int(counts.shape[0]),
            "n_taxa": int(counts.shape[1]),
            "n_tips": int(len(tree.tips)),
            "mean_pd": float(finite.mean()) if finite.size else None,
            "min_pd": float(finite.min()) if finite.size else None,
            "max_pd": float(finite.max()) if finite.size else None,
        }
        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "n_samples": int(counts.shape[0]),
            "n_tips": int(len(tree.tips)),
        }

    def export(self, ctx: Context) -> dict:
        return dict(self._export_data)

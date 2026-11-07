"""Genomic relationship matrix from genotype dosages."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import labels_in_order, make_form, reorder


class RelatednessStep(Step):
    provider = 'operon-genetics'
    parameters_file = 'relatedness.RelatednessStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'relatedness',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Relatedness',
     'category': 'Omics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'variant_dim', 'default': 'variant'},
                                        {'param': 'sample_dim', 'default': 'sample'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': False,
                                         'axis_info_open': False,
                                         'info': {'missing_code': {'type': ['number', 'null']}}}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Relatedness：接收 1 个输入，输出 Form；主要参数：Variant Dim、样本维度、Min Maf。'}

    def run(self, ctx: Context, inputs) -> None:
        geno = inputs[0]
        variant_dim = ctx.step_params.get("variant_dim", "variant")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        min_maf = float(ctx.step_params.get("min_maf", 0.05))
        out_name = ctx.step_params.get("output", self.name)
        X = reorder(geno, sample_dim, variant_dim).astype(np.float64)
        samples = labels_in_order(geno, sample_dim)
        p = np.nanmean(X, axis=0) / 2.0
        maf = np.minimum(p, 1 - p)
        keep = np.isfinite(p) & (maf >= min_maf) & (p > 0) & (p < 1)
        if not keep.any():
            raise StepError("relatedness: no variants pass min_maf")
        X = X[:, keep]; p = p[keep]
        fill = np.where(np.isfinite(X), X, 2 * p)
        G = (fill - 2 * p) / np.sqrt(2 * p * (1 - p))
        G = np.where(np.isfinite(G), G, 0.0)
        grm = (G @ G.T) / float(G.shape[1])
        out = make_form(grm, [sample_dim, f"{sample_dim}_b"],
                        {sample_dim: {name: i for i, name in enumerate(samples)},
                         f"{sample_dim}_b": {name: i for i, name in enumerate(samples)}})
        ctx[out_name] = out
        self._export_data = {"n_samples": len(samples), "n_variants": int(keep.sum()),
                             "min_maf": min_maf, "mean_diagonal": float(np.mean(np.diag(grm)))}

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})

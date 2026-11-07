# src/task/step/steps/prs.py
"""Polygenic risk score from aligned genotype dosages and variant weights.

Inputs
------
genotype : [variant, sample] allele dosage (0/1/2 or continuous dosage)
weights  : [variant, statistic] with a beta-weight column

The operator assumes the genotype dosage and weight are already aligned
to the same effect allele. It deliberately does not guess strand or
effect-allele orientation. Missing genotypes contribute zero and are
counted in the export; the score is therefore a complete-case dosage
sum over the variants present in both inputs.
"""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import axis_labels, labels_in_order, make_form, reorder, require_dims


class PrsStep(Step):
    provider = 'operon-genetics'
    parameters_file = 'prs.PrsStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'prs',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Polygenic risk score',
     'category': 'Omics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'variant_dim', 'default': 'variant'},
                                        {'param': 'sample_dim', 'default': 'sample'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2},
                              {'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'variant_dim', 'default': 'variant'},
                                        {'param': 'stat_dim', 'default': 'statistic'}],
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
     'inputs_arity': 2,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Polygenic risk score：接收 2 个输入，输出 Form；主要参数：Variant Dim、样本维度、统计维度、Weight Label。'}

    def run(self, ctx: Context, inputs) -> None:
        genotype, weights = inputs
        variant_dim = ctx.step_params.get("variant_dim", "variant")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        stat_dim = ctx.step_params.get("stat_dim", "statistic")
        weight_label = ctx.step_params["weight_label"]
        out_name = ctx.step_params.get("output", self.name)
        require_dims(genotype, variant_dim, sample_dim, label="genotype")
        require_dims(weights, variant_dim, stat_dim, label="weights")
        if weight_label not in weights.labels[stat_dim]:
            raise StepError(f"prs: weight column {weight_label!r} not found")
        variants = labels_in_order(genotype, variant_dim)
        weight_variants = labels_in_order(weights, variant_dim)
        weight_set = set(weight_variants)
        common = [v for v in variants if v in weight_set]
        if not common:
            raise StepError("prs: no shared variant labels")
        g = reorder(genotype, variant_dim, sample_dim)
        w = reorder(weights, variant_dim, stat_dim)[:, weights.labels[stat_dim][weight_label]]
        g_index = {v: i for i, v in enumerate(variants)}
        w_index = {v: i for i, v in enumerate(weight_variants)}
        rows = np.asarray([g_index[v] for v in common])
        wrow = np.asarray([w_index[v] for v in common])
        dosage = g[rows, :]
        beta = w[wrow]
        finite = np.isfinite(dosage) & np.isfinite(beta)[:, None]
        contrib = np.where(finite, dosage * beta[:, None], 0.0)
        score = contrib.sum(axis=0)
        n_used = finite.sum(axis=0)
        samples = labels_in_order(genotype, sample_dim)
        data = np.column_stack([score, n_used]).astype(np.float32)
        form = make_form(
            data, [sample_dim, "statistic"],
            {sample_dim: axis_labels(samples, sample_dim),
             "statistic": {"score": 0, "n_variants": 1}},
        )
        ctx[out_name] = form
        self._export_data = {
            "n_variants_input": len(variants), "n_variants_used": len(common),
            "weights_column": weight_label, "samples": len(samples),
        }
        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "n_variants_used": len(common), "n_samples": len(samples),
        }

    def export(self, ctx: Context) -> dict:
        return self._export_data

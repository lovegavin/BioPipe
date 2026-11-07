"""Nei's Dxy, the between-population nucleotide divergence.

Per-variant mean number of pairwise differences between two populations,
matching ``allel.mean_pairwise_difference_between``. For biallelic counts
this equals ``p_a * (1 - p_b) + p_b * (1 - p_a)``. Groups are selected from
a metadata table, exactly like ``fst``. Variants with fewer than two called
genotypes in either group get NaN but keep their sample counts.
"""
from __future__ import annotations

import numpy as np

from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import labels_in_order, make_form
from ._popgen_common import prepare_genotypes
from ._popgen_group_common import group_indices


class DxyStep(Step):
    provider = 'operon-genetics'
    parameters_file = 'dxy.DxyStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
                  'id': 'dxy',
                  'version': '1.0.0',
                  'kind': 'operator',
                  'title': "Nei's Dxy (between-population divergence)",
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
                                            'dims': [{'param': 'sample_dim', 'default': 'sample'}],
                                            'labels': [],
                                            'parallel': [],
                                            'ndim': 2}],
                                'output': {'mode': 'declare',
                                           'schema': {'ndim': 2,
                                                      'numeric': True,
                                                      'info_open': True,
                                                      'axis_info_open': True}}},
                  'resources': {'memory_modes': ['full'],
                                'supports_cuda': False,
                                'estimate': 'estimate_memory'},
                  'inputs_arity': 2,
                  'outputs': [],
                  'output_parameter': 'output',
                  'description': "Nei's Dxy: mean pairwise difference between two populations."}

    def run(self, ctx: Context, inputs) -> None:
        geno, meta = inputs
        variant_dim = ctx.step_params.get("variant_dim", "variant")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        group_label = ctx.step_params["group_label"]
        group_a = ctx.step_params["group_a"]
        group_b = ctx.step_params["group_b"]
        out_name = ctx.step_params.get("output", self.name)

        X, ploidy = prepare_genotypes(geno, variant_dim, sample_dim, self.name)
        variants = labels_in_order(geno, variant_dim)
        ia, ib = group_indices(geno, sample_dim, meta, group_label,
                               group_a, group_b, self.name)

        rows = []
        for j in range(X.shape[0]):
            va = X[j, ia]
            vb = X[j, ib]
            va = va[np.isfinite(va)]
            vb = vb[np.isfinite(vb)]
            if len(va) < 2 or len(vb) < 2:
                rows.append([np.nan, len(va), len(vb), np.nan, np.nan])
                continue
            an_a = float(len(va)) * float(ploidy)
            an_b = float(len(vb)) * float(ploidy)
            alt_a = float(np.sum(va))
            alt_b = float(np.sum(vb))
            ref_a = an_a - alt_a
            ref_b = an_b - alt_b
            pa = alt_a / an_a
            pb = alt_b / an_b
            same = (ref_a * ref_b + alt_a * alt_b) / (an_a * an_b)
            dxy = 1.0 - same
            rows.append([float(dxy), len(va), len(vb), float(pa), float(pb)])

        out = make_form(
            rows,
            [variant_dim, "statistic"],
            {variant_dim: {name: i for i, name in enumerate(variants)},
             "statistic": {"dxy": 0, "n_a": 1, "n_b": 2,
                           "p_a": 3, "p_b": 4}},
        )
        ctx[out_name] = out
        self._export_data = {
            "n_variants": len(variants),
            "group_a": group_a,
            "group_b": group_b,
            "n_a": len(ia),
            "n_b": len(ib),
            "mean_dxy": float(np.nanmean(out.data[:, 0])),
        }

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})

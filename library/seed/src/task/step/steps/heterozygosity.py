"""Observed and expected heterozygosity per variant.

Computes, for diploid hard-call genotypes, the observed heterozygosity
``H_o = n_het / n_called``, the expected heterozygosity under HWE
``H_e = 2 p (1 - p)`` with ``p`` the alt allele frequency among called
genotypes, and the inbreeding coefficient ``F_IS = 1 - H_o / H_e``.
Matches ``allel.heterozygosity_observed`` and
``allel.heterozygosity_expected`` (ploidy 2). Variants with no called
sample or with ``H_e = 0`` get NaN.
"""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import labels_in_order, make_form
from ._popgen_common import prepare_genotypes


class HeterozygosityStep(Step):
    provider = 'operon-genetics'
    parameters_file = 'heterozygosity.HeterozygosityStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
                  'id': 'heterozygosity',
                  'version': '1.0.0',
                  'kind': 'operator',
                  'title': 'Heterozygosity',
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
                                                      'info_open': True,
                                                      'axis_info_open': True}}},
                  'resources': {'memory_modes': ['full'],
                                'supports_cuda': False,
                                'estimate': 'estimate_memory'},
                  'inputs_arity': 1,
                  'outputs': [],
                  'output_parameter': 'output',
                  'description': 'Observed/expected heterozygosity and F_IS per diploid variant.'}

    def run(self, ctx: Context, inputs) -> None:
        variant_dim = ctx.step_params.get("variant_dim", "variant")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        out_name = ctx.step_params.get("output", self.name)

        X, ploidy = prepare_genotypes(inputs[0], variant_dim, sample_dim, self.name)
        if ploidy != 2:
            raise StepError(
                f"heterozygosity: supports diploid hard calls only, got ploidy={ploidy}"
            )
        variants = labels_in_order(inputs[0], variant_dim)

        called = np.isfinite(X)
        n_called = called.sum(axis=1).astype(np.float64)
        het = (np.equal(X, 1.0) & called).sum(axis=1).astype(np.float64)
        alt = np.where(called, X, 0.0).sum(axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            p = np.where(n_called > 0, alt / (2.0 * n_called), np.nan)
            ho = np.where(n_called > 0, het / n_called, np.nan)
            he = 2.0 * p * (1.0 - p)
            fis = np.where(he > 0, 1.0 - ho / he, np.nan)
            he = np.where(n_called > 0, he, np.nan)

        rows = np.column_stack([n_called, p, ho, he, fis])
        out = make_form(
            rows,
            [variant_dim, "statistic"],
            {variant_dim: {name: i for i, name in enumerate(variants)},
             "statistic": {"n_called": 0, "alt_freq": 1, "ho": 2,
                           "he": 3, "fis": 4}},
        )
        ctx[out_name] = out
        self._export_data = {
            "n_variants": len(variants),
            "n_samples": int(X.shape[1]),
            "mean_ho": float(np.nanmean(ho)),
            "mean_he": float(np.nanmean(he)),
        }

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})

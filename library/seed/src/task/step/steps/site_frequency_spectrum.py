"""Site frequency spectrum for biallelic hard-call genotypes.

For every variant the derived (alt) allele count is the number of alt
alleles among the called chromosomes. The spectrum counts how many
variants carry each count.

Input: hard-call genotypes, [variant, sample], with the same number of
called chromosomes on every variant (for example a complete genotype
matrix, or a matrix subset that keeps only complete variants). Missing
calls make the number of chromosomes vary between variants, which makes
the folded spectrum ambiguous, so they are rejected instead of silently
masked.

Output: dims [frequency, statistic] with columns (sites, proportion).
Unfolded bins are 1 .. n-1, folded bins are 1 .. n//2 with minor allele
counts (as in ``allel.sfs`` and ``allel.sfs_folded``). Monomorphic sites
(frequency 0 and n) are not part of the spectrum; ``proportion`` divides
the bin count by the total number of input variants.
"""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._popgen_common import allele_counts, prepare_genotypes


class SiteFrequencySpectrumStep(Step):
    provider = 'operon-genetics'
    parameters_file = 'site_frequency_spectrum.SiteFrequencySpectrumStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'site_frequency_spectrum',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Site frequency spectrum',
     'category': 'Omics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {'missing_code': {'type': ['number', 'null']},
                                        'ploidy': {'type': 'integer', 'min': 1},
                                        'representation': {'type': 'string',
                                                           'const': 'hard_call',
                                                           'optional': True}},
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
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Unfolded or folded site frequency spectrum of biallelic variants.'}

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        label = "site_frequency_spectrum"
        variant_dim = ctx.step_params.get("variant_dim", "variant")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        folded = bool(ctx.step_params.get("folded", False))
        out_name = ctx.step_params.get("output", self.name)

        data, ploidy = prepare_genotypes(form, variant_dim, sample_dim, label)
        alt, an = allele_counts(data, ploidy)
        n_variants = int(alt.size)
        if n_variants == 0:
            raise StepError(f"{label}: requires at least one variant")
        if np.any(an <= 0):
            raise StepError(f"{label}: every variant needs at least one called genotype")
        chromosomes = np.rint(an).astype(np.int64)
        n_chromosomes = int(np.max(chromosomes))
        if n_chromosomes < 2:
            raise StepError(f"{label}: need at least two called chromosomes")
        if not np.all(chromosomes == n_chromosomes):
            observed = sorted({int(value) for value in chromosomes})
            raise StepError(
                f"{label}: requires a constant number of called chromosomes, found {observed}. "
                "Filter missing genotypes or subset samples first"
            )
        derived = np.rint(alt).astype(np.int64)
        if derived.min() < 0 or derived.max() > n_chromosomes:
            raise StepError(f"{label}: derived allele counts are outside [0, {n_chromosomes}]")
        segregating = int(np.count_nonzero((derived > 0) & (derived < n_chromosomes)))

        rows, labels = [], []
        highest = n_chromosomes // 2 if folded else n_chromosomes - 1
        for frequency in range(1, highest + 1):
            sites = int(np.count_nonzero(derived == frequency))
            if folded and frequency != n_chromosomes - frequency:
                sites += int(np.count_nonzero(derived == n_chromosomes - frequency))
            rows.append([sites, sites / n_variants])
            labels.append(str(frequency))

        output = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=["frequency", "statistic"],
            labels={"frequency": {name: i for i, name in enumerate(labels)},
                    "statistic": {"sites": 0, "proportion": 1}},
            info={"missing_code": np.nan,
                  "n_chromosomes": n_chromosomes,
                  "n_variants": n_variants,
                  "n_segregating": segregating,
                  "folded": folded},
        )
        output.validate()
        ctx[out_name] = output
        self._export_data = {"n_chromosomes": n_chromosomes,
                             "n_variants": n_variants,
                             "n_segregating": segregating,
                             "folded": folded}

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})

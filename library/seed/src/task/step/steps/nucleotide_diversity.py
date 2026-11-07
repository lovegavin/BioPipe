"""Nucleotide diversity (pi) over the whole input or fixed genomic windows.

Nucleotide diversity is the average number of differences between two
chromosomes sampled from the input:

    pi            sum over variants of the mean pairwise difference
    pi_per_site   pi / n_bases

Input: hard-call genotypes, [variant, sample], alt allele counts in
[0, ploidy], missing calls NaN. ``chrom`` and ``pos`` are read from the
variant axis labels or from ``axis_info``. Windows follow scikit-allel:
they start at the first annotated position, advance by ``step_size``
(default ``window_size``), are ``window_size`` long, and the last window
ends at the last position.

Output: dims [window, statistic] with columns
(start, end, n_variants, n_bases, pi, pi_per_site, mean_pairwise_difference).
Without ``pos`` there is one row per chromosome, start/end and n_bases are
NaN, and only the absolute ``pi`` is meaningful.
"""
from __future__ import annotations

import numpy as np

from src.task.context import Context
from src.task.step.base import Step

from ._popgen_common import (
    allele_counts,
    mean_pairwise_difference,
    positions_chroms,
    prepare_genotypes,
    statistic_form,
    window_label,
    windows_for,
)

COLUMNS = ["start", "end", "n_variants", "n_bases", "pi", "pi_per_site",
           "mean_pairwise_difference"]


class NucleotideDiversityStep(Step):
    provider = 'operon-genetics'
    parameters_file = 'nucleotide_diversity.NucleotideDiversityStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'nucleotide_diversity',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Nucleotide diversity',
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
     'description': 'Nucleotide diversity over the whole input or fixed genomic windows.'}

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        label = "nucleotide_diversity"
        variant_dim = ctx.step_params.get("variant_dim", "variant")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        window_size = ctx.step_params.get("window_size")
        step_size = ctx.step_params.get("step_size")
        out_name = ctx.step_params.get("output", self.name)

        data, ploidy = prepare_genotypes(form, variant_dim, sample_dim, label)
        alt, an = allele_counts(data, ploidy)
        mpd = mean_pairwise_difference(alt, an)
        pos, chrom = positions_chroms(form, variant_dim, label)
        records = windows_for(pos, chrom, data.shape[0], window_size, step_size, label)

        rows, labels = [], []
        for record in records:
            index = record["index"]
            n_variants = int(index.size)
            diversity = float(np.sum(np.nan_to_num(mpd[index], nan=0.0)))
            if np.isfinite(record["start"]) and np.isfinite(record["end"]):
                n_bases = float(record["end"] - record["start"] + 1.0)
            else:
                n_bases = np.nan
            per_site = diversity / n_bases if np.isfinite(n_bases) and n_bases > 0 else np.nan
            per_variant = diversity / n_variants if n_variants else np.nan
            rows.append([record["start"], record["end"], n_variants, n_bases,
                         diversity, float(per_site), float(per_variant)])
            labels.append(window_label(record["chrom"], record["start"], record["end"]))

        info = {"n_chromosomes": int(np.max(an)) if an.size else 0,
                "has_positions": pos is not None}
        out = statistic_form(rows, COLUMNS, labels, info)
        ctx[out_name] = out
        self._export_data = {"n_variants": int(data.shape[0]),
                             "n_windows": len(rows),
                             "total_pi": float(np.sum(np.nan_to_num(mpd, nan=0.0)))}

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})

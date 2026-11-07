"""Tajima's D over the whole input or fixed genomic windows.

Tajima's D compares two estimates of the population mutation rate:

    pi      sum over variants of the mean pairwise difference
    theta_w S / a1, with S the number of segregating sites and
            a1 = sum_{i=1}^{n-1} 1/i

    D = (pi - theta_w) / sqrt(e1 * S + e2 * S * (S - 1))

Input: hard-call genotypes, [variant, sample], alt allele counts in
[0, ploidy], missing calls NaN. ``chrom`` and ``pos`` are read from the
variant axis labels or from ``axis_info``. Windows follow scikit-allel:
they start at the first annotated position, advance by ``step_size``
(default ``window_size``), are ``window_size`` long, and the last window
ends at the last position. The number of called chromosomes is the maximum
across the input, as in scikit-allel.

Output: dims [window, statistic] with columns
(start, end, n_variants, n_segregating, pi, theta_w, tajima_d).
Without ``pos`` there is one row per chromosome and start/end are NaN.
"""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._popgen_common import (
    allele_counts,
    mean_pairwise_difference,
    positions_chroms,
    prepare_genotypes,
    statistic_form,
    tajima_constants,
    window_label,
    windows_for,
)

COLUMNS = ["start", "end", "n_variants", "n_segregating", "pi", "theta_w", "tajima_d"]


class TajimasDStep(Step):
    provider = 'operon-genetics'
    parameters_file = 'tajimas_d.TajimasDStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'tajimas_d',
     'version': '1.0.0',
     'kind': 'operator',
     'title': "Tajima's D",
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
     'description': "Tajima's D over the whole input or fixed genomic windows."}

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        label = "tajimas_d"
        variant_dim = ctx.step_params.get("variant_dim", "variant")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        window_size = ctx.step_params.get("window_size")
        step_size = ctx.step_params.get("step_size")
        min_sites = int(ctx.step_params.get("min_sites", 3))
        out_name = ctx.step_params.get("output", self.name)

        if min_sites < 1:
            raise StepError(f"{label}: min_sites must be a positive integer")
        data, ploidy = prepare_genotypes(form, variant_dim, sample_dim, label)
        alt, an = allele_counts(data, ploidy)
        mpd = mean_pairwise_difference(alt, an)
        n_chromosomes = int(np.max(an)) if an.size else 0
        if n_chromosomes < 3:
            raise StepError(
                f"{label}: Tajima's D needs at least three called chromosomes, "
                f"found {n_chromosomes}"
            )
        constants = tajima_constants(n_chromosomes)
        segregating = (alt > 0) & (alt < an)
        pos, chrom = positions_chroms(form, variant_dim, label)
        records = windows_for(pos, chrom, data.shape[0], window_size, step_size, label)

        rows, labels = [], []
        for record in records:
            index = record["index"]
            sites = int(np.count_nonzero(segregating[index]))
            diversity = float(np.sum(np.nan_to_num(mpd[index], nan=0.0)))
            theta_w = sites / constants["a1"]
            if sites >= min_sites and sites > 0:
                stdev = float(np.sqrt(constants["e1"] * sites
                                      + constants["e2"] * sites * (sites - 1)))
                statistic = (diversity - theta_w) / stdev if stdev > 0 else np.nan
            else:
                statistic = np.nan
            rows.append([record["start"], record["end"], int(index.size),
                         sites, diversity, theta_w, float(statistic)])
            labels.append(window_label(record["chrom"], record["start"], record["end"]))

        info = {"n_chromosomes": n_chromosomes, "min_sites": min_sites,
                "has_positions": pos is not None}
        out = statistic_form(rows, COLUMNS, labels, info)
        ctx[out_name] = out
        finite = [row[6] for row in rows if np.isfinite(row[6])]
        self._export_data = {"n_variants": int(data.shape[0]),
                             "n_chromosomes": n_chromosomes,
                             "n_windows": len(rows),
                             "mean_tajima_d": float(np.mean(finite)) if finite else None}

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})

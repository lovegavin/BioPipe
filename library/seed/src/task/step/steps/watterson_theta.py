"""Watterson's theta over the whole input or fixed genomic windows.

Watterson's estimator of the population mutation rate is

    theta_w = S / a1,   a1 = sum_{i=1}^{n-1} 1/i

with S the number of segregating sites and n the number of called
chromosomes (the maximum across the input, as in scikit-allel). The
per-site value divides the absolute theta by the number of bases in the
window.

Input: hard-call genotypes, [variant, sample], alt allele counts in
[0, ploidy], missing calls NaN. ``chrom`` and ``pos`` are read from the
variant axis labels or from ``axis_info``. Windows follow scikit-allel:
they start at the first annotated position, advance by ``step_size``
(default ``window_size``), are ``window_size`` long, and the last window
ends at the last position.

Output: dims [window, statistic] with columns
(start, end, n_variants, n_bases, n_segregating, theta_w, theta_w_per_site).
"""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._popgen_common import (
    allele_counts,
    positions_chroms,
    prepare_genotypes,
    statistic_form,
    tajima_constants,
    window_label,
    windows_for,
)

COLUMNS = ["start", "end", "n_variants", "n_bases", "n_segregating", "theta_w",
           "theta_w_per_site"]


class WattersonThetaStep(Step):
    provider = 'operon-genetics'
    parameters_file = 'watterson_theta.WattersonThetaStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'watterson_theta',
     'version': '1.0.0',
     'kind': 'operator',
     'title': "Watterson's theta",
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
     'description': "Watterson's theta over the whole input or fixed genomic windows."}

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        label = "watterson_theta"
        variant_dim = ctx.step_params.get("variant_dim", "variant")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        window_size = ctx.step_params.get("window_size")
        step_size = ctx.step_params.get("step_size")
        out_name = ctx.step_params.get("output", self.name)

        data, ploidy = prepare_genotypes(form, variant_dim, sample_dim, label)
        alt, an = allele_counts(data, ploidy)
        n_chromosomes = int(np.max(an)) if an.size else 0
        if n_chromosomes < 2:
            raise StepError(
                f"{label}: need at least two called chromosomes, found {n_chromosomes}"
            )
        constants = tajima_constants(n_chromosomes)
        segregating = (alt > 0) & (alt < an)
        pos, chrom = positions_chroms(form, variant_dim, label)
        records = windows_for(pos, chrom, data.shape[0], window_size, step_size, label)

        rows, labels = [], []
        for record in records:
            index = record["index"]
            sites = int(np.count_nonzero(segregating[index]))
            theta_w = sites / constants["a1"]
            if np.isfinite(record["start"]) and np.isfinite(record["end"]):
                n_bases = float(record["end"] - record["start"] + 1.0)
            else:
                n_bases = np.nan
            per_site = theta_w / n_bases if np.isfinite(n_bases) and n_bases > 0 else np.nan
            rows.append([record["start"], record["end"], int(index.size), n_bases,
                         sites, theta_w, float(per_site)])
            labels.append(window_label(record["chrom"], record["start"], record["end"]))

        info = {"n_chromosomes": n_chromosomes, "has_positions": pos is not None}
        out = statistic_form(rows, COLUMNS, labels, info)
        ctx[out_name] = out
        self._export_data = {"n_variants": int(data.shape[0]),
                             "n_chromosomes": n_chromosomes,
                             "n_windows": len(rows),
                             "total_segregating": int(np.count_nonzero(segregating))}

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})

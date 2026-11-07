"""Linkage disequilibrium decay over genomic distance.

For every pair of variants on one chromosome the squared Pearson
correlation of the alt allele dosage (0 .. ploidy) is computed, which equals
``allel.rogers_huff_r`` squared for complete hard calls. Pairs are binned by
physical distance in ``n_bins`` equal-width bins between 0 and
``max_distance`` base pairs; zero-distance pairs (duplicate positions) are
excluded because they are not independent loci.

Input: hard-call genotypes, [variant, sample], with ``pos`` and ``chrom``
read from the variant axis labels or from ``axis_info``. Only complete
variants (no missing call) and polymorphic variants (non-zero variance)
enter the correlation. The input must span a single chromosome; subset a
chromosome first when a VCF covers more.

Output: dims [distance_bin, statistic] with columns
(bin_start, bin_end, n_pairs, mean_r2, median_r2). Empty bins keep NaN
values and ``n_pairs`` 0.

``max_pairs`` is a guard against quadratic blow-up: the run fails with the
number of candidate pairs instead of materialising an unbounded matrix.
"""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._popgen_common import positions_chroms, prepare_genotypes, statistic_form

COLUMNS = ["bin_start", "bin_end", "n_pairs", "mean_r2", "median_r2"]


class LdDecayStep(Step):
    provider = 'operon-genetics'
    parameters_file = 'ld_decay.LdDecayStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'ld_decay',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'LD decay',
     'category': 'Omics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {'missing_code': {'type': ['number', 'null']},
                                        'ploidy': {'type': 'integer', 'min': 1},
                                        'representation': {'type': 'string',
                                                           'const': 'hard_call',
                                                           'optional': True},
                                        'pos': {'type': 'array'},
                                        'chrom': {'type': 'array', 'optional': True}},
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
     'description': 'LD decay: binned mean r^2 between variant dosages by distance.'}

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        label = "ld_decay"
        variant_dim = ctx.step_params.get("variant_dim", "variant")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        max_distance = int(ctx.step_params.get("max_distance", 100000))
        n_bins = int(ctx.step_params.get("n_bins", 20))
        max_pairs = int(ctx.step_params.get("max_pairs", 5000000))
        out_name = ctx.step_params.get("output", self.name)

        if max_distance < 1:
            raise StepError(f"{label}: max_distance must be a positive integer")
        if n_bins < 2:
            raise StepError(f"{label}: n_bins must be at least 2")
        if max_distance < n_bins:
            raise StepError(f"{label}: max_distance must be at least n_bins")
        if max_pairs < 2:
            raise StepError(f"{label}: max_pairs must be at least 2")

        data, _ = prepare_genotypes(form, variant_dim, sample_dim, label)
        pos, chrom = positions_chroms(form, variant_dim, label)
        if pos is None:
            raise StepError(f"{label}: info['pos'] is required")
        chromosome = None
        if chrom is not None:
            names = {str(value) for value in chrom}
            if len(names) > 1:
                raise StepError(
                    f"{label}: input spans multiple chromosomes {sorted(names)}; "
                    "select one chromosome first"
                )
            chromosome = next(iter(names))
        n_input = int(data.shape[0])
        complete = np.all(np.isfinite(data), axis=1)
        data = data[complete]
        pos = pos[complete]
        if data.shape[0] < 2:
            raise StepError(f"{label}: at least two complete variants are required")
        keep = data.std(axis=1) > 0
        data = data[keep]
        pos = pos[keep]
        if data.shape[0] < 2:
            raise StepError(f"{label}: at least two polymorphic complete variants are required")
        n_variants, n_samples = data.shape
        standardized = (data - data.mean(axis=1, keepdims=True)) / data.std(axis=1, keepdims=True)

        right = np.searchsorted(pos, pos + max_distance, side="right")
        candidates = int(np.clip(right - np.arange(n_variants) - 1, 0, None).sum())
        if candidates > max_pairs:
            raise StepError(
                f"{label}: {candidates} candidate pairs exceed max_pairs={max_pairs}; "
                "narrow the region, raise max_pairs or reduce the variant count"
            )

        width = max_distance / float(n_bins)
        buckets = [[] for _ in range(n_bins)]
        for i in range(n_variants):
            stop = int(right[i])
            if stop <= i + 1:
                continue
            j = np.arange(i + 1, stop)
            distance = pos[j] - pos[i]
            valid = distance > 0
            if not valid.any():
                continue
            j = j[valid]
            distance = distance[valid]
            r = (standardized[i] @ standardized[j].T) / float(n_samples)
            r2 = np.clip(r * r, 0.0, 1.0)
            index = np.clip(np.ceil(distance / width).astype(np.int64) - 1, 0, n_bins - 1)
            for bucket in np.unique(index):
                buckets[int(bucket)].append(r2[index == bucket])

        rows, labels, used_pairs = [], [], 0
        for bucket in range(n_bins):
            start = bucket * width
            end = (bucket + 1) * width
            values = np.concatenate(buckets[bucket]) if buckets[bucket] else np.empty(0)
            n_pairs = int(values.size)
            used_pairs += n_pairs
            rows.append([start, end, n_pairs,
                         float(np.mean(values)) if n_pairs else np.nan,
                         float(np.median(values)) if n_pairs else np.nan])
            labels.append(f"{round(start)}-{round(end)}")

        info = {"n_variants": n_input, "n_variants_used": n_variants,
                "n_pairs": used_pairs, "max_distance": max_distance,
                "n_bins": n_bins, "chromosome": chromosome}
        out = statistic_form(rows, COLUMNS, labels, info)
        ctx[out_name] = out
        self._export_data = {"n_variants": n_input, "n_variants_used": n_variants,
                             "n_pairs": used_pairs, "max_distance": max_distance,
                             "n_bins": n_bins, "chromosome": chromosome}

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})

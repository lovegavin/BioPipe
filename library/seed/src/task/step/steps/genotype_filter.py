"""Filter genotype variants by missingness and minor allele frequency.

The operator keeps a genotype Form in ``[variant, sample]`` order and drops
variants whose missing-call fraction exceeds ``max_missing_rate`` or whose
minor allele frequency is below ``min_maf`` (computed on called genotypes).
Labels and per-variant ``info`` arrays (``pos``, ``chrom``, ...) are filtered
in parallel so downstream LD operators see a consistent axis.
"""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps import _ld_utils as ld


class GenotypeFilterStep(Step):
    """Drop low-frequency or poorly called variants from a genotype matrix."""
    provider = 'operon-core'
    parameters_file = 'genotype_filter.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'genotype_filter',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'genotype_filter',
        'description': 'Filter genotype variants by minor allele frequency and missing-call rate.',
        'category': 'Genome',
        'icon': 'Filter',
        'contracts': {
            'version': 1,
            'inputs': [
                {'version': 1, 'kind': 'form', 'numeric': True, 'ndim': 2,
                 'dims': [{'param': 'variant_dim', 'default': 'variant'},
                          {'param': 'sample_dim', 'default': 'sample'}],
                 'labels': [],
                 'info': {'missing_code': {'type': ['number', 'null']},
                          'ploidy': {'type': 'integer', 'min': 1},
                          'pos': {'type': 'array', 'optional': True},
                          'chrom': {'type': 'array', 'optional': True}}},
            ],
            'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True,
                                                     'info_open': True, 'axis_info_open': True}},
        },
        'resources': {'memory_modes': ['full'], 'supports_cuda': False,
                      'estimate': 'estimate_memory'},
        'inputs_arity': 1,
        'outputs': [],
        'output_parameter': 'output',
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = int(getattr(inputs[0], 'nbytes', 0)) if inputs else 0
        return max(int(size * 1.5), 8 * 1024**2), 64 * 1024

    def run(self, ctx: Context, inputs) -> None:
        if not inputs or inputs[0] is None:
            raise StepError('genotype_filter requires a genotype matrix')
        form = inputs[0]
        params = dict(ctx.step_params)
        variant_dim = str(params.get('variant_dim') or 'variant')
        sample_dim = str(params.get('sample_dim') or 'sample')
        min_maf = float(params.get('min_maf', 0.0))
        max_missing_rate = float(params.get('max_missing_rate', 1.0))
        out_name = params.get('output') or self.name

        if not 0.0 <= min_maf <= 0.5:
            raise StepError('genotype_filter: min_maf must be within [0, 0.5]')
        if not 0.0 <= max_missing_rate <= 1.0:
            raise StepError('genotype_filter: max_missing_rate must be within [0, 1]')

        data = ld.genotype_matrix(form, variant_dim, sample_dim, 'genotype_filter')
        n_variants = data.shape[0]
        ploidy = int(form.info.get('ploidy') or 2)
        missing = ~np.isfinite(data)
        missing_rate = missing.mean(axis=1)
        with np.errstate(invalid='ignore'):
            frequency = np.nanmean(data, axis=1) / float(ploidy)
        maf = np.minimum(frequency, 1.0 - frequency)
        keep_missing = missing_rate <= max_missing_rate
        keep_maf = np.isfinite(maf) & (maf >= min_maf) & (maf > 0.0)
        keep = keep_missing & keep_maf

        if int(np.count_nonzero(keep)) < 2:
            raise StepError(
                'genotype_filter: fewer than two variants remain after filters '
                f'(kept {int(np.count_nonzero(keep))} of {n_variants})'
            )

        filtered = data[keep]
        axis = form.dims.index(variant_dim)
        out_data = filtered.T if axis == 1 else filtered

        labels = {}
        for dim, mapping in (form.labels or {}).items():
            if dim == variant_dim:
                ordered = sorted(mapping.items(), key=lambda item: item[1])
                kept_names = [name for index, (name, _) in enumerate(ordered) if keep[index]]
                labels[dim] = {name: i for i, name in enumerate(kept_names)}
            else:
                labels[dim] = dict(mapping)
        labels.setdefault(variant_dim, {})

        info = {}
        for key, value in form.info.items():
            if isinstance(value, np.ndarray) and value.ndim == 1 and value.size == n_variants:
                info[key] = value[keep]
            elif isinstance(value, (list, tuple)) and len(value) == n_variants:
                info[key] = [item for item, flag in zip(value, keep) if flag]
            else:
                info[key] = value
        info['n_input'] = int(n_variants)
        info['n_kept'] = int(np.count_nonzero(keep))
        info['min_maf'] = float(min_maf)
        info['max_missing_rate'] = float(max_missing_rate)

        axis_info = {
            dim: list(fields) for dim, fields in (form.axis_info or {}).items()
        }
        result = Form(
            data=np.asarray(out_data, dtype=np.float32),
            dims=list(form.dims),
            labels=labels,
            info=info,
            axis_info=axis_info,
        )
        result.validate()
        ctx[out_name] = result

        self._export_data = {
            'n_input': int(n_variants),
            'n_kept': int(np.count_nonzero(keep)),
            'n_dropped_missing': int(np.count_nonzero(~keep_missing)),
            'n_dropped_maf': int(np.count_nonzero(keep_missing & ~keep_maf)),
            'ploidy': ploidy,
            'min_maf': float(min_maf),
            'max_missing_rate': float(max_missing_rate),
        }

    def export(self, ctx: Context) -> dict:
        return dict(self._export_data)

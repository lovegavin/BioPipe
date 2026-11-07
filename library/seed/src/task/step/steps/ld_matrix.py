# src/task/step/steps/ld_matrix.py
"""Pairwise linkage-disequilibrium r^2 matrix from a genotype matrix.

r^2 is the squared Pearson correlation of dosages over the selected
complete-case variants, which is the same estimator plink2 reports with
``--r2-unphased`` (unphased hard calls, no haplotype estimation).
"""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps import _ld_utils as ld


class LdMatrixStep(Step):
    """Square r^2 matrix over a deterministic subset of variants."""
    provider = 'operon-core'
    parameters_file = 'ld_matrix.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'ld_matrix',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'ld_matrix',
        'description': 'Pairwise linkage-disequilibrium r^2 matrix (plink2 --r2-unphased compatible).',
        'category': 'Genome',
        'icon': 'Table',
        'contracts': {
            'version': 1,
            'inputs': [
                {'version': 1, 'kind': 'form', 'numeric': True, 'ndim': 2,
                 'dims': [{'param': 'variant_dim', 'default': 'variant'},
                          {'param': 'sample_dim', 'default': 'sample'}],
                 'labels': []},
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
        variants = int(params.get('max_variants', 300) or 300)
        samples = 64
        return max(int(variants * variants * 8 + variants * samples * 8), 8 * 1024**2), 64 * 1024

    def run(self, ctx: Context, inputs) -> None:
        if not inputs or inputs[0] is None:
            raise StepError('ld_matrix requires a genotype matrix')
        params = dict(ctx.step_params)
        variant_dim = str(params.get('variant_dim') or 'variant')
        sample_dim = str(params.get('sample_dim') or 'sample')
        max_variants = int(params.get('max_variants') or 0)
        min_maf = float(params.get('min_maf', 0.01))
        out_name = params.get('output') or self.name

        form = inputs[0]
        genotypes = ld.genotype_matrix(form, variant_dim, sample_dim, 'ld_matrix')
        positions = ld.variant_positions(form, genotypes.shape[0], 'ld_matrix')
        maf = ld.minor_allele_frequencies(genotypes)
        complete = ld.complete_variant_mask(genotypes)
        usable = complete & (maf >= min_maf) & (maf > 0.0)
        index = np.where(usable)[0]
        if index.size < 2:
            raise StepError('ld_matrix: fewer than two usable variants after filters')
        chosen = index[ld.select_variants(index.size, max_variants)]

        z = ld.standardize(genotypes[chosen], 'ld_matrix')
        matrix = ld.r2_matrix(z)

        source_labels = form.labels.get(variant_dim, {}) if getattr(form, 'labels', None) else {}
        names = [str(name) for name, _ in sorted(source_labels.items(), key=lambda kv: kv[1])]
        if len(names) != genotypes.shape[0]:
            names = [f'variant_{i}' for i in range(genotypes.shape[0])]
        chosen_names = [names[int(i)] for i in chosen]
        labels = {variant_dim: {name: i for i, name in enumerate(chosen_names)},
                  f'{variant_dim}_b': {name: i for i, name in enumerate(chosen_names)}}
        data = matrix.astype(np.float64)
        ctx[out_name] = Form(
            data,
            dims=[variant_dim, f'{variant_dim}_b'],
            labels=labels,
            info={
                'n_variants': int(matrix.shape[0]),
                'n_samples': int(genotypes.shape[1]),
                'n_dropped_missing': int(np.count_nonzero(~complete)),
                'n_dropped_maf': int(np.count_nonzero(complete & (maf < min_maf))),
                'min_maf': float(min_maf),
                'mean_r2': float(matrix[np.triu_indices_from(matrix, k=1)].mean()),
                'max_r2': float(matrix[np.triu_indices_from(matrix, k=1)].max()),
                'positions': [int(positions[int(i)]) for i in chosen],
            },
        )
        self._export_data = {
            'n_variants': int(matrix.shape[0]),
            'n_samples': int(genotypes.shape[1]),
            'n_dropped_missing': int(np.count_nonzero(~complete)),
            'n_dropped_maf': int(np.count_nonzero(complete & (maf < min_maf))),
            'mean_r2': float(matrix[np.triu_indices_from(matrix, k=1)].mean()),
            'max_r2': float(matrix[np.triu_indices_from(matrix, k=1)].max()),
        }

    def export(self, ctx: Context) -> dict:
        return dict(self._export_data)

"""Genetic relationship matrix from biallelic SNPs."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError

from src.task.step.base import Step

from . import _genotype_matrix_utils as geno


class GenotypeGrmStep(Step):
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'genotype_grm',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Genotype relationship matrix',
        'description': 'PLINK-style genetic relationship matrix (Z Z^T / M) over biallelic SNPs.',
        'category': 'Omics',
        'icon': 'Grid3x3',
        'contracts': {
            'version': 1,
            'inputs': [{
                'version': 1,
                'kind': 'file',
                'numeric': False,
                'ndim': 0,
                'dims': [],
                'info': {'representation': {'type': 'string', 'enum': ['vcf', 'vcf.gz']}},
            }],
            'output': {
                'mode': 'declare',
                'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True},
            },
        },
        'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
        'inputs_arity': 1,
        'outputs': [],
        'output_parameter': 'output',
    }
    parameters_file = 'genotype_grm.parameters.json'

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = 0
        for artifact in inputs or []:
            size += int(getattr(artifact, 'file_bytes', 0) or 0)
        return max(int(size * 6), 16 * 1024**2), 2 * 1024**2

    def run(self, ctx, inputs) -> None:
        if not inputs or not hasattr(inputs[0], 'files'):
            raise StepError('genotype_grm requires a VCF file artifact')
        artifact = inputs[0]
        artifact.validate()
        if artifact.format not in ('vcf', 'vcf.gz'):
            raise StepError(f'genotype_grm requires a VCF file, got {artifact.format!r}')
        params = dict(ctx.step_params)
        out_name = params.get('output') or self.name
        maf = float(params.get('maf') or 0.0)
        max_variants = int(params.get('max_variants') or 0)

        path = next(iter(artifact.files.values()))
        samples, _variants, genotypes = geno.load_genotypes(path, max_variants)
        matrix, _used, _frequency = geno.standardise(genotypes, maf)
        grm = geno.relationship_matrix(matrix)
        labels = {name: index for index, name in enumerate(samples)}
        form = Form(
            grm.astype(np.float32),
            dims=['sample_a', 'sample_b'],
            labels={'sample_a': labels, 'sample_b': labels},
            info={
                'n_samples': len(samples),
                'n_variants': int(genotypes.shape[0]),
                'n_variants_used': int(np.count_nonzero(np.any(matrix != 0, axis=1))),
                'diagonal_mean': float(np.mean(np.diag(grm))),
                'maf': maf,
            },
        )
        ctx[out_name] = form

    def export(self, ctx):
        out_name = (ctx.step_params or {}).get('output') or self.name
        info = ctx[out_name].info
        return {
            'n_samples': int(info.get('n_samples', 0)),
            'n_variants': int(info.get('n_variants', 0)),
            'diagonal_mean': float(info.get('diagonal_mean', 0.0)),
        }

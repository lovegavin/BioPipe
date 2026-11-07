"""Principal component analysis of genotype structure."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError

from src.task.step.base import Step

from . import _genotype_matrix_utils as geno


class GenotypePcaStep(Step):
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'genotype_pca',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Genotype PCA',
        'description': 'Principal components of a genetic relationship matrix built from biallelic SNPs.',
        'category': 'Omics',
        'icon': 'Compass',
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
    parameters_file = 'genotype_pca.parameters.json'

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = 0
        for artifact in inputs or []:
            size += int(getattr(artifact, 'file_bytes', 0) or 0)
        return max(int(size * 3), 8 * 1024**2), 1024**2

    def run(self, ctx, inputs) -> None:
        if not inputs or not hasattr(inputs[0], 'files'):
            raise StepError('genotype_pca requires a VCF file artifact')
        artifact = inputs[0]
        artifact.validate()
        if artifact.format not in ('vcf', 'vcf.gz'):
            raise StepError(f'genotype_pca requires a VCF file, got {artifact.format!r}')
        params = dict(ctx.step_params)
        out_name = params.get('output') or self.name
        maf = float(params.get('maf') or 0.0)
        n_components = int(params.get('n_components') or 10)
        max_variants = int(params.get('max_variants') or 0)

        path = next(iter(artifact.files.values()))
        samples, _variants, genotypes = geno.load_genotypes(path, max_variants)
        matrix, _used, _frequency = geno.standardise(genotypes, maf)
        grm = geno.relationship_matrix(matrix)
        values, vectors = geno.pca_decomposition(grm, n_components)
        components = geno.component_labels(values.size)
        total = float(np.sum(values)) or 1.0

        form = Form(
            vectors.astype(np.float32),
            dims=['sample', 'component'],
            labels={
                'sample': {name: index for index, name in enumerate(samples)},
                'component': {name: index for index, name in enumerate(components)},
            },
            info={
                'eigenvalues': [float(value) for value in values],
                'variance_explained': [float(value / total) for value in values],
                'n_samples': len(samples),
                'n_variants': int(genotypes.shape[0]),
                'n_variants_used': int(matrix.shape[0] - np.count_nonzero(np.all(matrix == 0, axis=1))),
                'n_components': int(values.size),
                'maf': maf,
            },
        )
        ctx[out_name] = form

    def export(self, ctx):
        out_name = (ctx.step_params or {}).get('output') or self.name
        form = ctx[out_name]
        info = form.info
        return {
            'n_samples': int(info.get('n_samples', 0)),
            'n_variants': int(info.get('n_variants', 0)),
            'n_components': int(info.get('n_components', 0)),
            'eigenvalues': list(info.get('eigenvalues', [])),
        }

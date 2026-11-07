"""Variant loadings of the genotype principal components."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError

from src.task.step.base import Step

from . import _genotype_matrix_utils as geno


class GenotypePcaLoadingsStep(Step):
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'genotype_pca_loadings',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Genotype PCA loadings',
        'description': 'Per-variant loadings of the genotype principal components (PLINK allele weights).',
        'category': 'Omics',
        'icon': 'Table',
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
    parameters_file = 'genotype_pca_loadings.parameters.json'

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = 0
        for artifact in inputs or []:
            size += int(getattr(artifact, 'file_bytes', 0) or 0)
        return max(int(size * 3), 8 * 1024**2), 1024**2

    def run(self, ctx, inputs) -> None:
        if not inputs or not hasattr(inputs[0], 'files'):
            raise StepError('genotype_pca_loadings requires a VCF file artifact')
        artifact = inputs[0]
        artifact.validate()
        if artifact.format not in ('vcf', 'vcf.gz'):
            raise StepError(f'genotype_pca_loadings requires a VCF file, got {artifact.format!r}')
        params = dict(ctx.step_params)
        out_name = params.get('output') or self.name
        maf = float(params.get('maf') or 0.0)
        n_components = int(params.get('n_components') or 10)
        max_variants = int(params.get('max_variants') or 0)

        path = next(iter(artifact.files.values()))
        samples, variants, genotypes = geno.load_genotypes(path, max_variants)
        matrix, used, _frequency = geno.standardise(genotypes, maf)
        grm = geno.relationship_matrix(matrix)
        values, vectors = geno.pca_decomposition(grm, n_components)

        loadings = np.zeros((len(variants), values.size), dtype=np.float64)
        if used.size:
            scaled = matrix[used] @ vectors
            loadings[used] = scaled / (2.0 * np.sqrt(values))[None, :]
        components = geno.component_labels(values.size)

        form = Form(
            loadings.astype(np.float32),
            dims=['variant', 'component'],
            labels={
                'variant': {name: index for index, name in enumerate(variants)},
                'component': {name: index for index, name in enumerate(components)},
            },
            info={
                'eigenvalues': [float(value) for value in values],
                'n_variants': len(variants),
                'n_variants_used': int(used.size),
                'n_components': int(values.size),
                'maf': maf,
            },
        )
        ctx[out_name] = form

    def export(self, ctx):
        out_name = (ctx.step_params or {}).get('output') or self.name
        info = ctx[out_name].info
        return {
            'n_variants': int(info.get('n_variants', 0)),
            'n_variants_used': int(info.get('n_variants_used', 0)),
            'n_components': int(info.get('n_components', 0)),
        }

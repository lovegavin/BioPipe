"""Concatenate two VCFs that share the same samples."""
from __future__ import annotations

from pathlib import Path

from src.core import FileArtifact, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps import _vcf_utils as vcf
from src.task.step.steps._native_results import output_directory, remember_native, result_file


def _read(path):
    meta, samples, records = [], [], []
    with vcf.open_text(path) as stream:
        for line in stream:
            if line.startswith('##'):
                meta.append(line.rstrip('\n'))
                continue
            if line.startswith('#CHROM'):
                samples = line.rstrip('\n').split('\t')[9:]
                continue
            parts = line.rstrip('\n').split('\t')
            if len(parts) < 8:
                raise StepError('vcf_concat: VCF record has fewer than 8 columns')
            records.append(parts)
    return meta, samples, records


class VcfConcatStep(Step):
    provider = 'operon-core'
    parameters_file = 'vcf_concat.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}},
                    {'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'file_artifact',
                      'representations': ['file_artifact'],
                      'metadata': {}}]},
        'protocol_version': 3,
        'id': 'vcf_concat',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'vcf_concat',
        'description': 'Concatenate two VCFs with identical samples into a single VCF.',
        'category': 'Genome',
        'icon': 'Layers',
        'contracts': {
            'version': 1,
            'inputs': [
                {'version': 1, 'kind': 'file', 'numeric': False, 'ndim': 0, 'dims': [],
                 'info': {'representation': {'type': 'string', 'enum': ['vcf', 'vcf.gz']}}},
                {'version': 1, 'kind': 'file', 'numeric': False, 'ndim': 0, 'dims': [],
                 'info': {'representation': {'type': 'string', 'enum': ['vcf', 'vcf.gz']}}},
            ],
            'output': {'mode': 'declare', 'schema': {
                'kind': 'file', 'numeric': False, 'ndim': 0, 'dims': [],
                'info': {'representation': {'type': 'string', 'const': 'vcf'}},
                'info_open': True}},
        },
        'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
        'inputs_arity': 2,
        'outputs': [],
        'output_parameter': 'output',
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = 0
        for artifact in inputs or []:
            size += int(getattr(artifact, 'file_bytes', 0) or 0)
        return max(int(size * 2.5), 16 * 1024**2), max(int(size * 1.1), 1024**2)

    def run(self, ctx: Context, inputs) -> None:
        if not inputs or len(inputs) < 2:
            raise StepError('vcf_concat requires two VCF files')
        artifacts = list(inputs[:2])
        for artifact in artifacts:
            if not isinstance(artifact, FileArtifact):
                raise StepError('vcf_concat requires VCF file artifacts')
            artifact.validate()
            if artifact.format not in ('vcf', 'vcf.gz'):
                raise StepError(f"vcf_concat requires VCF files, got {artifact.format!r}")

        params = dict(ctx.step_params)
        out_name = params.get('output') or self.name

        meta_a, samples_a, records_a = _read(next(iter(artifacts[0].files.values())))
        meta_b, samples_b, records_b = _read(next(iter(artifacts[1].files.values())))
        if samples_a != samples_b:
            raise StepError('vcf_concat: both VCFs must have identical samples in identical order')

        directory = output_directory(ctx, out_name)
        destination = Path(directory) / f'{out_name}.vcf'
        with destination.open('w', encoding='utf-8', newline='\n') as out:
            for line in meta_a:
                out.write(line + '\n')
            for line in meta_b:
                if line not in meta_a:
                    out.write(line + '\n')
            out.write('\t'.join(['#CHROM', 'POS', 'ID', 'REF', 'ALT', 'QUAL', 'FILTER', 'INFO'] +
                                (['FORMAT'] + samples_a if samples_a else [])) + '\n')
            for parts in records_a + records_b:
                out.write('\t'.join(parts) + '\n')

        files = [result_file('variants', destination, 'vcf', 'Concatenated VCF')]
        remember_native(ctx, str(out_name), files)
        ctx[out_name] = FileArtifact('vcf', {'variants': str(destination)},
                                     info={'samples': samples_a})
        self._result_files = files
        self._export_data = {
            'file': str(destination),
            'bytes': destination.stat().st_size,
            'n_records_a': len(records_a),
            'n_records_b': len(records_b),
            'n_total': len(records_a) + len(records_b),
            'n_samples': len(samples_a),
            'result_files': files,
        }

    def export(self, ctx: Context) -> dict:
        report = dict(getattr(self, '_export_data', {}))
        report['result_files'] = list(getattr(self, '_result_files', []))
        return report

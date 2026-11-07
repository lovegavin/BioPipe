"""Merge two VCFs into one sample-aware union of sites."""
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
                if line.rstrip('\n') not in meta:
                    meta.append(line.rstrip('\n'))
                continue
            if line.startswith('#CHROM'):
                columns = line.rstrip('\n').split('\t')
                samples = columns[9:]
                continue
            parts = line.rstrip('\n').split('\t')
            if len(parts) < 8:
                raise StepError('vcf_merge: VCF record has fewer than 8 columns')
            records.append(parts)
    return meta, samples, records


def _split_format(parts):
    if len(parts) <= 8:
        return [], {}
    keys = parts[8].split(':')
    values = {}
    for sample, blob in zip(_split_format.samples, parts[9:]):
        fields = blob.split(':')
        values[sample] = dict(zip(keys, fields))
    return keys, values


def _merge_record(a, b, samples_a, samples_b, union_samples, format_keys):
    values = {}
    for sample in union_samples:
        if a is not None and sample in samples_a:
            values[sample] = a['values'].get(sample, {})
        elif b is not None and sample in samples_b:
            values[sample] = b['values'].get(sample, {})
        else:
            values[sample] = {}
    cells = []
    for sample in union_samples:
        cell = values[sample]
        parts = []
        for key in format_keys:
            if key == 'GT':
                parts.append(cell.get('GT', './.'))
            else:
                parts.append(cell.get(key, '.'))
        cells.append(':'.join(parts))
    return cells


def _recount_info(info_text, cells):
    ac = 0
    an = 0
    for cell in cells:
        gt = cell.split(':')[0]
        for token in gt.replace('|', '/').split('/'):
            if token == '.' or token == '':
                continue
            an += 1
            if token == '1':
                ac += 1
    keep = []
    for token in info_text.split(';'):
        if token.startswith('AC=') or token.startswith('AN=') or token.startswith('AF='):
            continue
        if token and token != '.':
            keep.append(token)
    keep.append(f'AC={ac}')
    keep.append(f'AN={an}')
    keep.append(f'AF={ac / an:.6g}' if an else 'AF=0')
    return ';'.join(keep)


class VcfMergeStep(Step):
    provider = 'operon-core'
    parameters_file = 'vcf_merge.parameters.json'
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
        'id': 'vcf_merge',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'vcf_merge',
        'description': 'Merge two VCFs into a sample-aware union of sites (missing genotypes filled).',
        'category': 'Genome',
        'icon': 'GitCompare',
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
        return max(int(size * 3.0), 16 * 1024**2), max(int(size * 1.1), 1024**2)

    def run(self, ctx: Context, inputs) -> None:
        if not inputs or len(inputs) < 2:
            raise StepError('vcf_merge requires two VCF files')
        artifacts = list(inputs[:2])
        for artifact in artifacts:
            if not isinstance(artifact, FileArtifact):
                raise StepError('vcf_merge requires VCF file artifacts')
            artifact.validate()
            if artifact.format not in ('vcf', 'vcf.gz'):
                raise StepError(f"vcf_merge requires VCF files, got {artifact.format!r}")

        params = dict(ctx.step_params)
        out_name = params.get('output') or self.name

        meta_a, samples_a, records_a = _read(next(iter(artifacts[0].files.values())))
        meta_b, samples_b, records_b = _read(next(iter(artifacts[1].files.values())))
        if set(samples_a) & set(samples_b):
            raise StepError('vcf_merge: the two VCFs must not share sample names')
        union_samples = samples_a + samples_b
        _split_format.samples = samples_a

        def parse(parts, samples):
            if len(parts) <= 8:
                return {'keys': [], 'values': {}}
            keys = parts[8].split(':')
            values = {}
            for sample, blob in zip(samples, parts[9:]):
                values[sample] = dict(zip(keys, blob.split(':')))
            return {'keys': keys, 'values': values}

        sites = {}
        order = []
        for parts in records_a:
            key = (parts[0], int(parts[1]), parts[3], parts[4])
            if key not in sites:
                sites[key] = {'a': None, 'b': None}
                order.append(key)
            sites[key]['a'] = {'parts': parts, 'parsed': parse(parts, samples_a)}
        for parts in records_b:
            key = (parts[0], int(parts[1]), parts[3], parts[4])
            if key not in sites:
                sites[key] = {'a': None, 'b': None}
                order.append(key)
            sites[key]['b'] = {'parts': parts, 'parsed': parse(parts, samples_b)}

        order.sort(key=lambda k: (k[0], k[1]))

        directory = output_directory(ctx, out_name)
        destination = Path(directory) / f'{out_name}.vcf'
        n_both = sum(1 for k in order if sites[k]['a'] and sites[k]['b'])
        with destination.open('w', encoding='utf-8', newline='\n') as out:
            for line in meta_a:
                out.write(line + '\n')
            for line in meta_b:
                if line not in meta_a:
                    out.write(line + '\n')
            out.write('\t'.join(['#CHROM', 'POS', 'ID', 'REF', 'ALT', 'QUAL', 'FILTER', 'INFO', 'FORMAT'] + union_samples) + '\n')
            for key in order:
                entry = sites[key]
                a = entry['a']['parsed'] if entry['a'] else None
                b = entry['b']['parsed'] if entry['b'] else None
                base = entry['a']['parts'] if entry['a'] else entry['b']['parts']
                format_keys = list(a['keys']) if a else []
                for k in (b['keys'] if b else []):
                    if k not in format_keys:
                        format_keys.append(k)
                if not format_keys:
                    out.write('\t'.join(base[:8]) + '\n')
                    continue
                cells = _merge_record(a, b, samples_a, samples_b, union_samples, format_keys)
                info = _recount_info(base[7], cells) if 'GT' in format_keys else base[7]
                out.write('\t'.join(base[:7] + [info, ':'.join(format_keys)] + cells) + '\n')

        files = [result_file('variants', destination, 'vcf', 'Merged VCF')]
        remember_native(ctx, str(out_name), files)
        ctx[out_name] = FileArtifact('vcf', {'variants': str(destination)},
                                     info={'samples': union_samples})
        self._result_files = files
        self._export_data = {
            'file': str(destination),
            'bytes': destination.stat().st_size,
            'n_sites': len(order),
            'n_shared_sites': n_both,
            'n_samples': len(union_samples),
            'samples': union_samples,
            'result_files': files,
        }

    def export(self, ctx: Context) -> dict:
        report = dict(getattr(self, '_export_data', {}))
        report['result_files'] = list(getattr(self, '_result_files', []))
        return report

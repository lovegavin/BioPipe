"""Normalise and split VCF records against a reference FASTA."""
from __future__ import annotations

import re
from pathlib import Path

from operon_sdk import FileArtifact, Step, StepError

from src.task.step.steps import _vcf_transform as tx
from src.task.step.steps import _vcf_utils as vcf
from src.task.step.steps._native_results import output_directory, remember_native, result_file


def _remap(gt: str, allele: int) -> str:
    out = []
    for token in re.split(r'([|/])', gt):
        if token in ('|', '/'):
            out.append(token)
        elif token == '.' or token == '':
            out.append('.')
        else:
            out.append('1' if int(token) == allele else '0')
    return ''.join(out)


def _recount(gts, info_fields):
    ac = 0
    an = 0
    for gt in gts:
        for token in gt.replace('|', '/').split('/'):
            if token == '.':
                continue
            an += 1
            if token == '1':
                ac += 1
    info = {}
    for token in info_fields:
        if '=' in token:
            key, value = token.split('=', 1)
            info[key] = value
        elif token and token != '.':
            info[token] = ''
    info['AC'] = str(ac)
    info['AN'] = str(an)
    info['AF'] = f'{ac / an:.6g}' if an else '0'
    return ';'.join(f'{key}={value}' if value != '' else key for key, value in info.items())


class VcfNormalizeStep(Step):
    provider = 'operon-core'
    parameters_file = 'vcf_normalize.parameters.json'
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
        'version': '1.0.0',
        'kind': 'operator',
        'id': 'vcf_normalize',
        'title': 'VCF normalise',
        'description': 'Split multi-allelic records and left-align/trim indels against a reference FASTA.',
        'category': 'Genome',
        'icon': 'Filter',
        'inputs_arity': 2,
        'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
        'outputs': [],
        'output_parameter': 'output',
        'contracts': {
            'version': 1,
            'inputs': [
                {'version': 1, 'kind': 'file', 'numeric': False, 'ndim': 0, 'dims': [],
                 'info': {'representation': {'type': 'string', 'enum': ['vcf', 'vcf.gz']}}},
                {'version': 1, 'kind': 'file', 'numeric': False, 'ndim': 0, 'dims': [],
                 'info': {'representation': {'type': 'string', 'enum': ['fasta', 'fa', 'fna']}}},
            ],
            'output': {'mode': 'declare', 'schema': {
                'kind': 'file', 'numeric': False, 'ndim': 0, 'dims': [],
                'info': {'representation': {'type': 'string', 'const': 'vcf'}},
                'info_open': True}},
        },
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = 0
        for artifact in inputs or []:
            size += int(getattr(artifact, 'file_bytes', 0) or 0)
        return max(int(size * 3.0), 16 * 1024 ** 2), max(int(size * 1.1), 1024 ** 2)

    def run(self, ctx, inputs) -> None:
        if not inputs or len(inputs) < 2:
            raise StepError('vcf_normalize requires a VCF and a reference FASTA')
        vcf_artifact, fasta_artifact = inputs[0], inputs[1]
        if not isinstance(vcf_artifact, FileArtifact):
            raise StepError('vcf_normalize requires a VCF file artifact')
        vcf_artifact.validate()
        if vcf_artifact.format not in ('vcf', 'vcf.gz'):
            raise StepError(f"vcf_normalize requires a VCF file, got {vcf_artifact.format!r}")
        reference = tx.load_reference(tx.fasta_path(fasta_artifact, 'vcf_normalize'))

        params = dict(ctx.step_params)
        out_name = params.get('output') or self.definition['id']
        split = bool(params.get('split_multiallelic', True))
        max_records = int(params.get('max_records') or 0)

        directory = output_directory(ctx, out_name)
        destination = Path(directory) / f'{out_name}.vcf'
        source = next(iter(vcf_artifact.files.values()))

        n_in = n_out = n_split = n_relocated = 0
        header_lines = []
        emitted = []
        chrom_order = {}
        with vcf.open_text(source) as stream:
            for line in stream:
                if line.startswith('#'):
                    header_lines.append(line)
                    continue
                parts = line.rstrip('\n').split('\t')
                if len(parts) < 8:
                    raise StepError('vcf_normalize: VCF record has fewer than 8 columns')
                if max_records and n_in >= max_records:
                    continue
                n_in += 1
                chrom, pos, vid, ref, alt_text = parts[0], parts[1], parts[2], parts[3], parts[4]
                qual, filt, info_text = parts[5], parts[6], parts[7]
                rest = parts[8:]
                seq = reference.get(chrom) or reference.get(chrom.lstrip('chr')) or ''
                alts = tx.split_alts(alt_text)
                if not alts:
                    continue
                paired = list(zip(alts, tx.normalize(pos, ref, alts, seq)))
                if len(alts) > 1 and split:
                    n_split += 1
                selected = paired if split else [((alts[0]), (int(pos), ref.upper(), alt_text.upper()))]
                if not split and len(alts) == 1:
                    selected = [(alts[0], paired[0][1])]
                info_fields = tx.parse_info_fields(info_text)
                for orig_alt, (p, r, a) in selected:
                    if int(pos) != int(p) or ref.upper() != r or alt_text.upper() != a.upper():
                        n_relocated += 1
                    if split and len(alts) > 1:
                        allele_index = alts.index(orig_alt) + 1 if orig_alt in alts else 1
                        gts = [_remap(field.split(':')[0], allele_index) for field in rest[1:]] if rest else []
                        new_info = _recount(gts, info_fields)
                        emitted_rest = [rest[0]] + gts if rest else []
                    else:
                        new_info = info_text
                        emitted_rest = rest
                    fields = [chrom, str(p), vid, r, a, qual, filt, new_info] + emitted_rest
                    rank = chrom_order.setdefault(chrom, len(chrom_order))
                    emitted.append((rank, int(p), r, a, '\t'.join(fields)))
                    n_out += 1

        emitted.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
        with destination.open('w', encoding='utf-8', newline='\n') as out:
            for line in header_lines:
                out.write(line)
            for _rank, _pos, _ref, _alt, text in emitted:
                out.write(text + '\n')

        files = [result_file('variants', destination, 'vcf', 'Normalised VCF')]
        remember_native(ctx, str(out_name), files)
        ctx[out_name] = FileArtifact('vcf', {'variants': str(destination)},
                                     info={'split_multiallelic': split})
        self._result_files = files
        self._export_data = {
            'file': str(destination),
            'bytes': destination.stat().st_size,
            'n_in': n_in,
            'n_out': n_out,
            'n_split_records': n_split,
            'n_relocated': n_relocated,
            'split_multiallelic': split,
            'result_files': files,
        }

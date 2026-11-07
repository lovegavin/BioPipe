"""Call consensus variants from a BAM pileup against a reference FASTA.

Inputs: BAM FileArtifact + FASTA FileArtifact.
Output: VCF FileArtifact plus a summary report.

The caller is deliberately simple and deterministic: a position becomes a
variant when depth, base quality and alt-allele fraction clear the thresholds.
It is not a replacement for a probabilistic variant caller.
"""
from __future__ import annotations

import numpy as np

from src.core import FileArtifact, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._bam_utils import pileup_counts, read_fasta, read_header
from src.task.step.steps._native_results import output_directory, remember_native, result_file

_BASES = "ACGT"


class PileupVariantsStep(Step):
    """Call simple majority-allele variants from a BAM + reference FASTA."""
    provider = 'operon-core'
    parameters_file = 'pileup_variants.parameters.json'
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
        'id': 'pileup_variants',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'pileup_variants',
        'description': 'Call simple threshold-based variants from a BAM pileup and write a VCF.',
        'category': 'Quality Control',
        'icon': 'Dna',
        'contracts': {
            'version': 1,
            'inputs': [
                {
                    'version': 1,
                    'kind': 'file',
                    'numeric': False,
                    'ndim': 0,
                    'dims': [],
                    'info': {'representation': {'type': 'string', 'enum': ['bam']}},
                },
                {
                    'version': 1,
                    'kind': 'file',
                    'numeric': False,
                    'ndim': 0,
                    'dims': [],
                    'info': {'representation': {'type': 'string', 'enum': ['fasta']}},
                },
            ],
            'output': {'mode': 'declare', 'schema': {'kind': 'file', 'numeric': False, 'ndim': 0, 'dims': [],
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
        size = sum(int(getattr(item, 'file_bytes', 0) or 0) for item in inputs or [])
        return max(int(size * 0.5), 256 * 1024 ** 2), 1024 ** 2

    def run(self, ctx: Context, inputs) -> None:
        if len(inputs) < 2 or not isinstance(inputs[0], FileArtifact) or not isinstance(inputs[1], FileArtifact):
            raise StepError('pileup_variants requires a BAM and a FASTA file artifact')
        bam, fasta = inputs[0], inputs[1]
        bam.validate()
        fasta.validate()
        if bam.format != 'bam':
            raise StepError(f'pileup_variants requires a BAM file, got {bam.format!r}')
        if fasta.format not in ('fasta', 'fa'):
            raise StepError(f'pileup_variants requires a FASTA file, got {fasta.format!r}')
        params = dict(ctx.step_params)
        min_depth = int(params.get('min_depth') or 5)
        min_bq = int(params.get('min_base_quality') or 20)
        min_fraction = float(params.get('min_alt_fraction') or 0.8)
        min_alt_count = int(params.get('min_alt_count') or 2)
        min_mapq = int(params.get('min_mapq') or 0)
        max_records = int(params.get('max_records') or 0)
        out_name = params.get('output') or self.name
        bam_path = next(iter(bam.files.values()))
        fasta_path = next(iter(fasta.files.values()))

        try:
            _text, references = read_header(bam_path)
            sequences = read_fasta(fasta_path)
            counts = pileup_counts(bam_path, references, sequences, min_mapq=min_mapq,
                                   min_base_quality=min_bq, max_records=max_records)
        except ValueError as exc:
            raise StepError(f'pileup_variants: {exc}') from exc

        header = ['##fileformat=VCFv4.2', '##source=operon:pileup_variants']
        for name, length in references:
            header.append(f'##contig=<ID={name},length={length}>')
        header.append('#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO')
        lines = []
        n_snps = 0
        covered_positions = 0
        for name, length in references:
            ref_seq = sequences[name]
            array = counts[name]
            depth = array.sum(axis=0)
            covered_positions += int(np.count_nonzero(depth >= min_depth))
            ref_codes = np.asarray([_BASES.find(base) if base in _BASES else -1 for base in ref_seq], dtype=np.int8)
            alt_codes = array.argmax(axis=0).astype(np.int8)
            alt_counts = array.max(axis=0)
            with np.errstate(divide='ignore', invalid='ignore'):
                fraction = alt_counts / depth
            mask = (
                (depth >= min_depth)
                & (ref_codes >= 0)
                & (alt_codes != ref_codes)
                & (alt_counts >= min_alt_count)
                & (fraction >= min_fraction)
            )
            for position in np.flatnonzero(mask):
                ref = _BASES[int(ref_codes[position])]
                alt = _BASES[int(alt_codes[position])]
                lines.append(
                    f'{name}\t{int(position) + 1}\t.\t{ref}\t{alt}\t.\tPASS\t'
                    f'DP={int(depth[position])};AF={float(fraction[position]):.4f}'
                )
                n_snps += 1

        directory = output_directory(ctx, out_name)
        vcf_path = directory / f'{out_name}.vcf'
        vcf_path.write_bytes(('\n'.join(header + lines) + '\n').encode('utf-8'))
        result_files = [result_file('variants', str(vcf_path), 'vcf', 'Consensus variants')]
        remember_native(ctx, out_name, result_files)
        ctx[out_name] = FileArtifact('vcf', {'variants': str(vcf_path)}, info={'source': 'pileup_variants'})
        self._result_files = result_files
        self._export_data = {
            'n_variants': len(lines),
            'n_snps': n_snps,
            'n_covered_positions': covered_positions,
            'n_references': len(references),
            'min_depth': min_depth,
            'min_alt_fraction': min_fraction,
            'file': str(vcf_path),
            'bytes': int(vcf_path.stat().st_size),
            'result_files': result_files,
        }
        print(f'[pileup_variants] {len(lines)} variants over {covered_positions} covered positions')

    def export(self, ctx):
        return self._export_data

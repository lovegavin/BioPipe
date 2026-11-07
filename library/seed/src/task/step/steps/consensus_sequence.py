"""Build a consensus FASTA from a BAM pileup and a reference FASTA.

Inputs: BAM FileArtifact + FASTA FileArtifact.
Output: FASTA FileArtifact plus a summary report.

Positions below the depth threshold, or without a clear majority allele, are
emitted as ``N`` so downstream tools can see where the consensus is unsupported.
"""
from __future__ import annotations

import numpy as np

from src.core import FileArtifact, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._bam_utils import pileup_counts, read_fasta, read_header
from src.task.step.steps._native_results import output_directory, remember_native, result_file

_BASES = "ACGT"


def _wrap(sequence: str, width: int = 60) -> list:
    return [sequence[index: index + width] for index in range(0, len(sequence), width)]


class ConsensusSequenceStep(Step):
    """Build a majority-allele consensus genome in FASTA format."""
    provider = 'operon-core'
    parameters_file = 'consensus_sequence.parameters.json'
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
        'id': 'consensus_sequence',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'consensus_sequence',
        'description': 'Build a majority-allele consensus FASTA from a BAM pileup and reference.',
        'category': 'Quality Control',
        'icon': 'FileText',
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
                                                    'info': {'representation': {'type': 'string', 'const': 'fasta'}},
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
        return max(int(size * 0.5), 256 * 1024 ** 2), 8 * 1024 ** 2

    def run(self, ctx: Context, inputs) -> None:
        if len(inputs) < 2 or not isinstance(inputs[0], FileArtifact) or not isinstance(inputs[1], FileArtifact):
            raise StepError('consensus_sequence requires a BAM and a FASTA file artifact')
        bam, fasta = inputs[0], inputs[1]
        bam.validate()
        fasta.validate()
        if bam.format != 'bam':
            raise StepError(f'consensus_sequence requires a BAM file, got {bam.format!r}')
        if fasta.format not in ('fasta', 'fa'):
            raise StepError(f'consensus_sequence requires a FASTA file, got {fasta.format!r}')
        params = dict(ctx.step_params)
        min_depth = int(params.get('min_depth') or 5)
        min_bq = int(params.get('min_base_quality') or 20)
        min_fraction = float(params.get('min_fraction') or 0.6)
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
            raise StepError(f'consensus_sequence: {exc}') from exc

        letters = np.asarray(list(_BASES))
        records = []
        n_bases = 0
        n_called = 0
        n_substitutions = 0
        for name, _length in references:
            ref_seq = sequences[name]
            array = counts[name]
            depth = array.sum(axis=0)
            alt_codes = array.argmax(axis=0)
            alt_counts = array.max(axis=0)
            with np.errstate(divide='ignore', invalid='ignore'):
                fraction = alt_counts / depth
            called = (depth >= min_depth) & (fraction >= min_fraction)
            characters = np.full(len(ref_seq), 'N', dtype='<U1')
            characters[called] = letters[alt_codes[called]]
            consensus = ''.join(characters.tolist())
            ref_upper = ref_seq.upper()
            ref_codes = np.asarray(
                [_BASES.find(base) if base in _BASES else -1 for base in ref_upper], dtype=np.int8
            )
            n_substitutions += int(
                np.count_nonzero(called & (ref_codes >= 0) & (alt_codes != ref_codes))
            )
            n_bases += len(consensus)
            n_called += int(np.count_nonzero(called))
            records.append(f'>{name} consensus depth>={min_depth} fraction>={min_fraction}')
            records.extend(_wrap(consensus))

        directory = output_directory(ctx, out_name)
        fasta_out = directory / f'{out_name}.fasta'
        fasta_out.write_bytes(('\n'.join(records) + '\n').encode('utf-8'))
        result_files = [result_file('genome', str(fasta_out), 'fasta', 'Consensus genome')]
        remember_native(ctx, out_name, result_files)
        ctx[out_name] = FileArtifact('fasta', {'genome': str(fasta_out)}, info={'source': 'consensus_sequence'})
        self._result_files = result_files
        self._export_data = {
            'n_references': len(references),
            'n_bases': n_bases,
            'n_called_bases': n_called,
            'n_N_bases': n_bases - n_called,
            'n_substitutions': n_substitutions,
            'min_depth': min_depth,
            'min_fraction': min_fraction,
            'file': str(fasta_out),
            'bytes': int(fasta_out.stat().st_size),
            'result_files': result_files,
        }
        print(f'[consensus_sequence] {n_bases} bases, {n_called} called, {n_substitutions} substitutions')

    def export(self, ctx):
        return self._export_data

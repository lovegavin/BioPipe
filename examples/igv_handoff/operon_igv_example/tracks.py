"""Export merged genomic intervals to reusable BED and bedGraph file artifacts.

Coordinates are zero-based, half-open. Chromosomes come from the input Form's
axis metadata, never from a filename or assumed assembly. The value column is
selected by label. This example deliberately accepts only merged_intervals.
"""
from __future__ import annotations

import hashlib
import json
import math
import numbers
from pathlib import Path
import re
import uuid

from operon_sdk import FileArtifact, Step


def _coordinate(value):
    if isinstance(value, numbers.Integral):
        result = int(value)
    else:
        value = float(value)
        if not math.isfinite(value) or not value.is_integer() or abs(value) > 2**53:
            raise ValueError('Coordinates must be finite, exact integers')
        result = int(value)
    if result < 0:
        raise ValueError('Coordinates must be non-negative')
    return result


def write_tracks(form, directory, *, assembly, value_field='n_intervals', checkpoint=None):
    """Write an admitted Form incrementally; do not copy or sort its matrix.

This pure helper also makes coordinate validation testable without a GUI.
The upstream interval_merge operator already sorts chromosome and start.
"""
    if form.info.get('representation') != 'merged_intervals' or form.data.ndim != 2:
        raise ValueError('Expected the merged_intervals Form from interval_merge')
    row_axis, column_axis = form.dims
    fields = form.labels[column_axis]
    if not {'start', 'end', value_field} <= fields.keys():
        raise ValueError('Required named start, end and value columns are missing')
    chroms = form.info.get('chrom')
    if ('chrom' not in form.axis_info.get(row_axis, []) or chroms is None
            or len(chroms) != form.data.shape[0]):
        raise ValueError('Per-row chromosome axis metadata is required')
    if not isinstance(assembly, str) or not assembly.strip():
        raise ValueError('Declare the reference assembly explicitly')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    paths = {role: directory / name for role, name in
             [('bed', 'merged.bed'), ('bedgraph', 'values.bedgraph'), ('provenance', 'provenance.json')]}
    digests = {role: hashlib.sha256() for role in ('bed', 'bedgraph')}
    previous = None
    chromosomes = set()
    count = 0
    try:
        with paths['bed'].open('wb', buffering=65536) as bed, paths['bedgraph'].open('wb', buffering=65536) as signal:
            for index, row in enumerate(form.data):
                if checkpoint and index % 1024 == 0:
                    checkpoint()
                chrom = chroms[index]
                if not isinstance(chrom, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]+', chrom):
                    raise ValueError('Chromosome names must be nonempty track-safe identifiers')
                start, end = _coordinate(row[fields['start']]), _coordinate(row[fields['end']])
                value = float(row[fields[value_field]])
                if end <= start or not math.isfinite(value):
                    raise ValueError('Require start < end and finite signal values')
                if previous and (chrom < previous[0] or chrom == previous[0] and start < previous[1]):
                    raise ValueError('Input must be chromosome-sorted with non-overlapping intervals')
                previous = chrom, end
                name = f'merged_{index + 1}'
                records = {'bed': f'{chrom}\t{start}\t{end}\t{name}\n'.encode('utf-8'),
                           'bedgraph': f'{chrom}\t{start}\t{end}\t{value:.17g}\n'.encode('utf-8')}
                for role, stream in [('bed', bed), ('bedgraph', signal)]:
                    stream.write(records[role]); digests[role].update(records[role])
                chromosomes.add(chrom)
                count += 1
        if checkpoint:
            checkpoint()
        metadata = {'schema_version': 1, 'assembly': assembly, 'coordinate_system': '0-based-half-open',
                    'source_representation': 'merged_intervals', 'source_dimensions': form.dims,
                    'value_field': value_field, 'rows': count, 'chromosomes': sorted(chromosomes),
                    'files': {role: {'name': paths[role].name, 'sha256': digest.hexdigest()}
                              for role, digest in digests.items()}}
        paths['provenance'].write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8', newline='\n')
        return paths, metadata
    except BaseException:
        # Only these newly created task-local files can be removed on failure.
        for path in paths.values():
            path.unlink(missing_ok=True)
        directory.rmdir()
        raise


class GenomeTracks(Step):
    parameters_file = 'tracks.parameters.json'
    definition = {
        'protocol_version': 3, 'id': 'example.genome_tracks', 'version': '0.1.0',
        'kind': 'operator', 'title': 'Export genome tracks', 'category': 'data',
        'description': 'Export merged intervals as validated BED and bedGraph for IGV or other genome browsers.',
        'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [],
        'contracts': {'version': 1, 'inputs': [{'kind': 'form', 'ndim': 2, 'numeric': True,
                       'info': {'representation': {'const': 'merged_intervals'}}}],
                      'output': {'mode': 'declare', 'schema': {'kind': 'file', 'numeric': False,
                                 'info': {'representation': {'const': 'genome_tracks'}}}}},
        'resources': {'memory_modes': ['full'], 'estimate': 'estimate_memory', 'supports_cuda': False},
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        # Input storage is charged by the framework; output is a small reference.
        # In the worst case every row introduces a chromosome in the small
        # provenance index. Charge the set/list bookkeeping as well as buffers.
        return 256 * 1024 + int(inputs[0].data.shape[0]) * 256, 32 * 1024

    def run(self, ctx, inputs):
        params = ctx.step_params
        prefix = params['prefix']
        if not re.fullmatch(r'[a-zA-Z0-9_-]+', prefix):
            raise ValueError('Invalid artifact prefix')
        directory = ctx.artifact_path(f'{prefix}-{uuid.uuid4().hex}/placeholder').parent
        # artifact_path creates its parent; write_tracks owns a new child.
        directory = directory / 'tracks'
        def checkpoint():
            if (ctx.task_dir / 'cancel.requested').exists():
                raise RuntimeError('Run cancelled by user')
        paths, metadata = write_tracks(inputs[0], directory, assembly=params['assembly'],
                                       value_field=params['value_field'], checkpoint=checkpoint)
        ctx[params.get('output', self.name)] = FileArtifact('genome_tracks', {k: str(v) for k, v in paths.items()},
                                                          info={k: metadata[k] for k in ('assembly', 'coordinate_system', 'value_field')})
        self._report = metadata
        ctx.log(f'[example.genome_tracks] Exported {metadata["rows"]} intervals on {len(metadata["chromosomes"])} chromosomes')

    def export(self, ctx):
        return self._report

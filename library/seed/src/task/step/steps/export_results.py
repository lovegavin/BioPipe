"""One branch output operator, using the existing v3 FileArtifact contract."""
import csv
import json
import re
import shutil
from pathlib import Path, PureWindowsPath

import numpy as np

from src.core import FileArtifact, Form, StepError
from src.task.step.base import Step
from src.task.step.steps._native_results import output_directory, result_file
from biopipe.bytecode import io_path


def canonical_format(value):
    value = str(value).lower().lstrip('.')
    return {'fa': 'fasta', 'faa': 'fasta', 'fna': 'fasta', 'mmcif': 'cif'}.get(value, value)


def native_results(ctx, input_name):
    """Only use files from the current input's latest producer, never an ancestor."""
    if not input_name:
        return []
    from src.task.step import STEPS
    for entry in reversed(ctx.artifacts.get('exports', [])):
        cls = STEPS.get(entry['name'])
        if cls is None:
            continue
        names = list(cls.outputs)
        if cls.output_parameter:
            names.append(entry.get('params', {}).get(cls.output_parameter, cls.name))
        if input_name not in names:
            continue
        if len(set(names)) != 1:
            return []  # A multi-output report cannot attribute files to one port.
        cache = ctx.artifacts.get('native_results', {}).get(input_name, {})
        if cache.get('index') == entry['index']:
            return cache['files']
        # Isolated workers return the JSON report rather than the local cache.
        path = (ctx.out_dir / entry['export_path']).resolve()
        if not path.is_relative_to(ctx.out_dir.resolve()):
            raise StepError('export_results: producer report escapes the task output')
        with io_path(path).open(encoding='utf-8') as stream:
            report = json.load(stream)
        return report.get('result_files', []) if isinstance(report, dict) else []
    return []


def ordered_labels(form, axis):
    labels = form.labels[form.dims[axis]]
    return [label for label, position in sorted(labels.items(), key=lambda item: item[1])]


def write_array(path, array, buffer_bytes):
    if array.dtype.hasobject:
        raise StepError('export_results: object arrays cannot be exported as safe NPY')
    with io_path(path).open('wb') as handle:
        np.lib.format.write_array_header_2_0(handle, {
            'descr': np.lib.format.dtype_to_descr(array.dtype), 'shape': array.shape,
            'fortran_order': False})
        with np.nditer(array, flags=['external_loop', 'buffered', 'zerosize_ok'],
                       order='C', buffersize=max(1, buffer_bytes // max(1, array.dtype.itemsize))) as chunks:
            for chunk in chunks:
                handle.write(chunk.tobytes(order='C'))


def write_table(path, form, delimiter, include_labels):
    if form.data.ndim != 2:
        raise StepError('export_results: CSV/TSV requires two dimensions; use NPY or reshape explicitly')
    rows = ordered_labels(form, 0) if include_labels else None
    with io_path(path).open('w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle, delimiter=delimiter)
        if include_labels:
            writer.writerow([form.dims[0], *ordered_labels(form, 1)])
        for index, row in enumerate(form.data):
            writer.writerow(([rows[index]] if rows is not None else []) + row.tolist())


def write_fasta(path, form):
    sequences = form.info.get('sequences')
    if not isinstance(sequences, (list, tuple, np.ndarray)) or form.data.ndim < 1:
        raise StepError('export_results: FASTA needs info.sequences aligned with the first axis')
    if len(sequences) != form.data.shape[0]:
        raise StepError('export_results: sequence count differs from the first axis')
    for dim, keys in form.axis_info.items():
        if 'sequences' in keys and dim != form.dims[0]:
            raise StepError('export_results: info.sequences belongs to a different axis')
    names = ordered_labels(form, 0)
    with io_path(path).open('w', encoding='utf-8', newline='\n') as handle:
        for name, sequence in zip(names, sequences):
            if not isinstance(sequence, str) or not sequence or any(c in str(name) for c in '\r\n'):
                raise StepError('export_results: invalid FASTA label or sequence')
            chains = sequence.split('/')
            for index, chain in enumerate(chains, 1):
                if not re.fullmatch(r'[A-Za-z*.-]+', chain):
                    raise StepError('export_results: sequence contains unsupported FASTA characters')
                label = str(name) if len(chains) == 1 else f'{name}|chain={index}'
                handle.write('>' + label + '\n')
                for start in range(0, len(chain), 80):
                    handle.write(chain[start:start + 80] + '\n')


class ExportResultsStep(Step):
    provider = 'biopipe-core'
    parameters_file = 'export_results.parameters.json'
    definition = {
        'protocol_version': 3, 'id': 'export_results', 'version': '1.0.0',
        'kind': 'operator', 'title': 'Export results', 'category': 'data',
        'description': 'Export a branch as native files, a labelled table, NPY or FASTA while other branches continue.',
        'inputs_arity': 1, 'outputs': [], 'output_parameter': 'output',
        'dependencies': ['numpy>=1.24'], 'dependency_imports': ['numpy'],
        'contracts': {'version': 1, 'inputs': [{'kind': ['form', 'file']}],
                      'output': {'mode': 'declare', 'schema': {
                          'kind': 'file', 'numeric': False, 'ndim': 0, 'dims': [],
                          'info': {'representation': {'const': 'exported_files'}}, 'info_open': True}}},
        'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        buffer = int(float(params.get('buffer_mb', 1)) * 1024**2)
        metadata = sum(sum(len(v) for v in item.labels.values()) * 128
                       for item in inputs if hasattr(item, 'data'))
        row = max((item.data.shape[-1] * 128 for item in inputs
                   if hasattr(item, 'data') and item.data.ndim), default=0)
        return 3 * buffer + metadata + row, 65536

    def run(self, ctx, inputs):
        value = inputs[0]
        params = ctx.step_params
        requested = canonical_format(params.get('format', 'auto'))
        name = str(params.get('filename', ''))
        if name and (Path(name).name != name or PureWindowsPath(name).name != name
                     or name in {'.', '..'} or name.endswith('.') or PureWindowsPath(name).is_reserved()
                     or re.search(r'[<>:"/\\|?*\x00-\x1f]', name)):
            raise StepError('export_results: filename must be a plain portable basename')
        name = name.strip()
        names = params.get('_input_names', [])
        source_name = names[0] if names else None
        if isinstance(value, FileArtifact):
            value.validate()
            candidates = [result_file(role, path, value.info.get('formats', {}).get(role,
                              canonical_format(Path(path).suffix) or value.format))
                          for role, path in value.files.items()]
        else:
            candidates = native_results(ctx, source_name)
        matched = candidates if requested in {'auto', 'native'} else [
            entry for entry in candidates if canonical_format(entry.get('format', Path(entry['path']).suffix)) == requested]
        directory = output_directory(ctx, 'exports')
        files, formats, reused = {}, {}, []
        if matched:
            for index, entry in enumerate(matched, 1):
                source = Path(entry['path']).resolve()
                if not io_path(source).is_file():
                    raise StepError(f'export_results: native file no longer exists: {source.name}')
                if not isinstance(value, FileArtifact) and not source.is_relative_to(ctx.out_dir.resolve()):
                    raise StepError('export_results: producer native file escapes this task output')
                role = f'file_{index}'
                if source.is_relative_to(ctx.out_dir.resolve()) and not name:
                    target = source
                    reused.append(role)
                else:
                    filename = ((name if len(matched) == 1 else f'{name}-{index}') + source.suffix) if name else f'{index}-{source.name}'
                    target = directory / filename
                    pending = target.with_name(target.name + '.part')
                    try:
                        shutil.copyfile(io_path(source), io_path(pending))
                        io_path(pending).replace(io_path(target))
                    finally:
                        io_path(pending).unlink(missing_ok=True)
                files[role] = str(target)
                formats[role] = canonical_format(entry.get('format', source.suffix))
        else:
            if isinstance(value, FileArtifact) or requested in {'native', 'pdb', 'cif'}:
                raise StepError(f'export_results: no matching original {requested} file; keep the producer and export in one task or supply a FileArtifact')
            actual = ('csv' if value.data.ndim == 2 else 'npy') if requested == 'auto' else requested
            extension = {'fasta': 'fasta', 'csv': 'csv', 'tsv': 'tsv', 'npy': 'npy'}.get(actual)
            if extension is None:
                raise StepError(f'export_results: unsupported format {actual}')
            target = directory / ((name or 'result') + '.' + extension)
            pending = target.with_name(target.name + '.part')
            try:
                if actual in {'csv', 'tsv'}:
                    write_table(pending, value, ',' if actual == 'csv' else '\t', params.get('include_labels', True))
                elif actual == 'npy':
                    write_array(pending, value.data, int(float(params.get('buffer_mb', 1)) * 1024**2))
                else:
                    write_fasta(pending, value)
                io_path(pending).replace(io_path(target))
            finally:
                io_path(pending).unlink(missing_ok=True)
            files['data'], formats['data'] = str(target), actual
        if isinstance(value, FileArtifact):
            value.validate()  # Do not publish a copy of an input changed during I/O.
        artifact = FileArtifact('exported_files', files, info={'formats': formats,
                                  'source': source_name, 'requested_format': requested, 'reused_roles': reused})
        ctx[str(params.get('output', self.name))] = artifact
        self._report = {'format': requested, 'files': files, 'formats': formats, 'reused_roles': reused,
                        'bytes': artifact.file_bytes, 'source': source_name}

    def export(self, ctx):
        return self._report

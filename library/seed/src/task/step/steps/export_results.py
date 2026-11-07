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
from operon.bytecode import io_path


def canonical_format(value):
    value = str(value).lower().lstrip('.')
    return {'fa': 'fasta', 'faa': 'fasta', 'fna': 'fasta', 'mmcif': 'cif',
            'gb': 'genbank', 'gbk': 'genbank', 'gbff': 'genbank',
            'nwk': 'newick', 'new': 'newick'}.get(value, value)


def native_suffix(path):
    suffixes = path.suffixes
    if len(suffixes) >= 2 and (suffixes[-1].lower() in {'.gz', '.bz2', '.xz', '.zip', '.bai', '.crai', '.tbi', '.csi'}
                              or suffixes[-2].lower() == '.ome'):
        return ''.join(suffixes[-2:])
    return path.suffix


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
    provider = 'operon-core'
    parameters_file = 'export_results.parameters.json'
    definition = {
        'protocol_version': 3, 'id': 'export_results', 'version': '1.0.0',
        'kind': 'operator', 'title': 'Export results', 'category': 'data',
        'description': 'Export native files or convert annotated data to contact maps, sequences, genome tracks, networks and trees while other branches continue.',
        'inputs_arity': 1, 'outputs': [], 'output_parameter': 'output',
        'dependencies': ['numpy>=1.24', 'hictkpy>=1.4,<2', 'h5py>=3.8', 'biopython>=1.81'],
        'dependency_imports': ['numpy', 'hictkpy', 'h5py', 'Bio'],
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
        # The native contact writer also owns compression buffers and a bin table.
        contacts = params.get('format') in {'hic', 'cool'}
        if contacts and any(isinstance(item, FileArtifact) and any(
                canonical_format(item.info.get('formats', {}).get(role, Path(path).suffix)) == params['format']
                for role, path in item.files.items()) for item in inputs):
            contacts = False  # Original-file reuse needs no contact writer allocation.
        if contacts:
            for item in inputs:
                info = dict(item.info)
                if isinstance(item, FileArtifact):
                    candidates = [p for p in item.files.values() if Path(p).suffix.lower() in {'.cool', '.mcool'}]
                    if len(candidates) == 1:
                        import h5py
                        with h5py.File(candidates[0], 'r') as handle:
                            resolution = params.get('resolution') or info.get('resolution')
                            group = handle[f'/resolutions/{resolution}'] if 'resolutions' in handle and resolution else handle[info.get('group', '/')]
                            if 'chroms' in group:
                                info['chrom_sizes'] = dict(zip(group['chroms/name'].asstr()[:], map(int, group['chroms/length'][:])))
                                info['resolution'] = int(group.attrs.get('bin-size', resolution or 0))
                resolution = params.get('resolution') or info.get('resolution')
                sizes = params.get('chrom_sizes') or info.get('chrom_sizes')
                if resolution and isinstance(sizes, dict):
                    metadata += sum((int(size) + int(resolution) - 1) // int(resolution) for size in sizes.values()) * 128
        return (32 * 1024**2 if contacts else 0) + 3 * buffer + metadata + row, 65536

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
        conversion = dict(value.info.get('conversion') or {}) if isinstance(value, FileArtifact) else {}
        files, formats, reused = {}, {}, []
        if matched:
            native_names = [Path(entry['path']).name.casefold() for entry in matched]
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
                    original_name = source.name if native_names.count(source.name.casefold()) == 1 else f'{index}-{source.name}'
                    filename = (name + native_suffix(source) if len(matched) == 1 else f'{name}-{original_name}') if name else original_name
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
            if (isinstance(value, FileArtifact) and requested not in {'hic', 'cool'}) or requested in {'native', 'pdb', 'cif'}:
                raise StepError(f'export_results: no matching original {requested} file; keep the producer and export in one task or supply a FileArtifact')
            actual = ('csv' if value.data.ndim == 2 else 'npy') if requested == 'auto' else requested
            extension = {'fasta': 'fasta', 'csv': 'csv', 'tsv': 'tsv', 'npy': 'npy',
                         'hic': 'hic', 'cool': 'cool', 'genbank': 'gbk', 'bed': 'bed',
                         'bedgraph': 'bedgraph', 'graphml': 'graphml', 'newick': 'nwk'}.get(actual)
            if extension is None:
                raise StepError(f'export_results: unsupported format {actual}')
            target = directory / ((name or 'result') + '.' + extension)
            pending = target.with_name(target.name + '.part')
            try:
                if actual in {'csv', 'tsv'}:
                    write_table(pending, value, ',' if actual == 'csv' else '\t', params.get('include_labels', True))
                elif actual == 'npy':
                    write_array(pending, value.data, int(float(params.get('buffer_mb', 1)) * 1024**2))
                elif actual == 'fasta':
                    write_fasta(pending, value)
                elif actual in {'hic', 'cool'}:
                    from src.task.step.steps._export_contacts import write_contacts
                    conversion = write_contacts(pending, value, params, ctx, actual)
                else:
                    from src.task.step.steps import _export_domain as domain
                    if actual == 'genbank':
                        conversion = domain.write_genbank(pending, value, params)
                    elif actual in {'bed', 'bedgraph'}:
                        conversion = domain.write_track(pending, value, params, actual)
                    elif actual == 'graphml':
                        conversion = domain.write_graphml(pending, value, params)
                    else:
                        conversion = domain.write_newick(pending, value)
                io_path(pending).replace(io_path(target))
            finally:
                io_path(pending).unlink(missing_ok=True)
            files['data'], formats['data'] = str(target), actual
            if conversion:
                metadata = directory / ((name or 'result') + '.metadata.json')
                io_path(metadata).write_text(json.dumps(conversion, ensure_ascii=False, indent=2), encoding='utf-8')
                files['metadata'], formats['metadata'] = str(metadata), 'json'
        if isinstance(value, FileArtifact):
            value.validate()  # Do not publish a copy of an input changed during I/O.
        artifact = FileArtifact('exported_files', files, info={'formats': formats,
                                  'source': source_name, 'requested_format': requested, 'reused_roles': reused,
                                  'conversion': conversion})
        ctx[str(params.get('output', self.name))] = artifact
        self._report = {'format': requested, 'files': files, 'formats': formats, 'reused_roles': reused,
                        'bytes': artifact.file_bytes, 'source': source_name, 'conversion': conversion}

    def export(self, ctx):
        return self._report

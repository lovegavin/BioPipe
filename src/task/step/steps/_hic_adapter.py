"""Bridge file algorithms to the existing context, Form and memory interfaces."""
from pathlib import Path


def execute(operation, ctx, inputs):
    from src.core import FileArtifact, StepError
    from src.task.step.steps import _hic_tools as hic_tools
    if not inputs or not isinstance(inputs[0], FileArtifact):
        raise StepError(operation + " requires a file artifact as its first input")
    source = inputs[0]
    source.validate()
    params = dict(ctx.step_params)
    params.pop('_input_names', None)
    if operation == 'align_reads':
        if source.format != 'fastq': raise StepError('align_reads requires FASTQ')
        params['phred_offset'] = source.info.get('phred_offset', 33)
        result = hic_tools.align_reads(ctx, source.files, params)
    elif operation == 'build_contacts':
        result = hic_tools.build_contacts(ctx, source.files, source.format, params)
    else:
        if source.format != 'cool': raise StepError('analyze_contacts requires Cooler')
        params['group'] = source.info.get('group', '/')
        params['resolution'] = params.get('resolution') or source.info.get('resolution')
        auxiliaries = []
        for form in inputs[1:]:
            refs = form.info.get('hic_files')
            if not refs: raise StepError('Auxiliary input must be a Hi-C analysis output')
            record = FileArtifact('tsv', refs, fingerprints=form.info.get('hic_fingerprints', {}))
            record.validate()
            auxiliaries.append({'files': refs, 'info': form.info})
        result = hic_tools.analyze_contacts(ctx, source.files, params, auxiliaries)
    # Detect mutation of source files during a long external operation.
    source.validate()
    if operation == 'analyze_contacts':
        form = load_analysis(result, ctx, params)
    else:
        form = FileArtifact(result['format'], result['files'], result['info'])
    ctx[params.get('output', operation)] = form
    return {**result['summary'], 'files': result['files'], 'info': result['info']}


def load_analysis(result, ctx, params):
    """Admit small analysis products; keep the large source matrix on disk."""
    import numpy as np
    from src.core import FileArtifact, Form
    budget = int(params.get('memory_mb', 256) * 1024**2)
    if result['format'] == 'npz':
        import zipfile
        path = Path(result['files']['matrix'])
        with zipfile.ZipFile(path) as archive:
            if sum(item.file_size for item in archive.infolist()) * 3 > budget:
                raise ValueError('Pileup result exceeds the admitted workspace')
        with np.load(path, allow_pickle=False) as archive:
            matrix = archive['pileup']
        form = Form(matrix, ['offset1', 'offset2'],
                    {axis: {str(i): i for i in range(matrix.shape[n])} for n, axis in enumerate(['offset1', 'offset2'])},
                    {'missing_code': np.nan})
    else:
        path = Path(result['files']['table'])
        # TSV parsing uses strings plus encoded columns, hence a conservative
        # expansion check before delegating to the existing table Reader.
        if path.stat().st_size * 32 > budget:
            raise ValueError(f'Analysis table exceeds memory_mb; the complete TSV remains at {path}')
        from src.reader.readers.tsv_reader import TsvReader
        import csv
        with path.open(encoding='utf-8', newline='') as stream:
            rows = csv.reader(stream, delimiter='\t')
            header = next(rows, None)
            empty = next(rows, None) is None
        if not header or len(header) != len(set(header)):
            raise ValueError('Analysis output needs unique column names')
        if empty:
            # No significant loops is a valid scientific result, not a failed Reader.
            form = Form(np.empty((0, len(header))), ['record', 'statistic'],
                        {'record': {}, 'statistic': {name: i for i, name in enumerate(header)}},
                        {'missing_code': np.nan, 'empty_result': True})
        else:
            form = TsvReader().read(path, ['record', 'statistic'], {'record': 'auto', 'statistic': 'builtin'})
    ref = FileArtifact(result['format'], result['files'])
    form.info.update(result['info'])
    form.info['hic_files'], form.info['hic_fingerprints'] = ref.files, ref.fingerprints
    form.validate()
    return form

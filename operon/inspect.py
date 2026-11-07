"""Bounded input inspection; file size never requires materializing a dataset."""
from pathlib import Path


def inspect_source(path, reader_name=None, args=None, *, sample_rows=128):
    """Read a bounded text-table sample; other formats return metadata only.

    Statistics describe the sample, not an inferred whole dataset. Formats
    without bounded inspection must be inspected in a managed workflow.
    """
    from .packages import bundled_entries
    from .reader_selection import candidates
    path = Path(path).resolve()
    if not path.exists():
        raise FileNotFoundError(f'input file not found: {path}')
    if not isinstance(sample_rows, int) or not 1 <= sample_rows <= 10000:
        raise ValueError('sample_rows must be between 1 and 10000')
    selected = candidates([d for _, d in bundled_entries('reader')], path, reader_name, check_siblings=True)
    if len(selected) != 1:
        raise ValueError('Choose an explicit registered Reader ID for this input')
    descriptor = selected[0]
    template = descriptor.get('file_input') or {}
    dims = template.get('dims', ['sample', 'feature'])
    result = {'path': str(path), 'reader': descriptor['id'], 'file_bytes': path.stat().st_size,
              'dims': dims, 'shape': None, 'shape_exact': False,
              'suggested': {'reader': descriptor['id'], 'dims': dims, 'labels': template.get('labels', {})}}
    if descriptor['id'] not in {'CsvReader', 'TsvReader'}:
        result['limitation'] = 'Metadata only; use this Reader in a managed workflow for payload inspection.'
        return result
    import numpy as np
    try:
        import pandas as pd
    except ModuleNotFoundError as error:
        if error.name != 'pandas':
            raise
        result['limitation'] = 'Metadata only in the management runtime; inspect table contents using the registered Reader in a prepared execution environment.'
        return result
    from operon_sdk.protocol import validate_parameters
    options = validate_parameters(descriptor['parameters_schema'], args or {})
    frame = pd.read_csv(path, sep=options.get('sep', '\t' if descriptor['id'] == 'TsvReader' else ','),
                        header=0 if options.get('header', True) else None, nrows=sample_rows + 1)
    exact = len(frame) <= sample_rows
    frame = frame.iloc[:sample_rows]
    numeric = frame.select_dtypes(include='number').to_numpy(dtype=float)
    finite = numeric[np.isfinite(numeric)]
    result.update(shape=list(frame.shape), shape_exact=exact, sampled=not exact,
                  labels={dims[0]: {'count': len(frame), 'first': [str(i) for i in range(min(8, len(frame)))]},
                          dims[1]: {'count': len(frame.columns), 'first': list(map(str, frame.columns[:8]))}},
                  stats={'scope': 'sample', 'n_finite': int(finite.size),
                         'mean': float(finite.mean()) if finite.size else None,
                         'min': float(finite.min()) if finite.size else None,
                         'max': float(finite.max()) if finite.size else None},
                  head=frame.iloc[:3, :3].astype(object).where(pd.notna(frame.iloc[:3, :3]), None).values.tolist())
    return result

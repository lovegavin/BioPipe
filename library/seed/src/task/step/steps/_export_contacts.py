"""Bounded raw-contact export; never infer genomic coordinates from matrix indices."""
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from src.core import FileArtifact, StepError


def cancelled(ctx):
    if (ctx.task_dir / 'cancel.requested').exists():
        raise StepError('Run cancelled by user')


def counts(values):
    values = np.asarray(values)
    if (not np.issubdtype(values.dtype, np.number) or np.iscomplexobj(values)
            or not np.isfinite(values).all() or (values < 0).any()
            or (values != np.floor(values)).any() or (values > 2**24).any()):
        raise StepError('Contact export needs finite nonnegative integer raw counts (at most 2^24 per pixel); balanced/log/OE values cannot be converted to counts')
    return values


def sizes_and_resolution(info, params):
    sizes = params.get('chrom_sizes') or info.get('chrom_sizes')
    resolution = params.get('resolution') or info.get('resolution')
    if not isinstance(sizes, dict) or not sizes:
        raise StepError('Contact export needs full chrom_sizes; window endpoints are not chromosome lengths')
    if any(not isinstance(k, str) or not k or any(c.isspace() for c in k)
           or isinstance(v, bool) or not isinstance(v, (int, np.integer)) or v <= 0 for k, v in sizes.items()):
        raise StepError('chrom_sizes must map chromosome names to positive integer lengths')
    if isinstance(resolution, bool) or not isinstance(resolution, (int, np.integer)) or resolution <= 0:
        raise StepError('Contact export needs a positive integer resolution')
    return {k: int(v) for k, v in sizes.items()}, int(resolution)


@contextmanager
def contact_source(value, params, chunk, ctx):
    """Yield chromosome metadata plus an iterator of sparse upper-triangle batches."""
    if isinstance(value, FileArtifact):
        import h5py
        candidates = [p for p in value.files.values() if Path(p).suffix.lower() in {'.cool', '.mcool'}]
        if len(candidates) != 1:
            raise StepError('Contact conversion needs exactly one .cool/.mcool source; select a resolution for .mcool')
        with h5py.File(candidates[0], 'r') as handle:
            selected = params.get('resolution') or value.info.get('resolution')
            group_name = value.info.get('group', '/')
            if 'resolutions' in handle:
                if not selected:
                    raise StepError('Choose a resolution when converting .mcool')
                group_name = f'/resolutions/{selected}'
            group = handle[group_name]
            if group.attrs.get('storage-mode', 'symmetric-upper') != 'symmetric-upper':
                raise StepError('Contact conversion requires symmetric-upper Cooler storage')
            if group.attrs.get('bin-type', 'fixed') != 'fixed':
                raise StepError('Contact export requires fixed-size genomic bins')
            sizes = dict(zip(group['chroms/name'].asstr()[:], map(int, group['chroms/length'][:])))
            sizes, resolution = sizes_and_resolution({'chrom_sizes': sizes, 'resolution': group.attrs.get('bin-size')}, {})
            if selected and selected != resolution:
                raise StepError('Requested resolution differs from source; rebin explicitly before export')
            # Bin IDs must match the complete fixed-width genome grid used by the writer.
            cursor = 0
            for chrom_id, length in enumerate(sizes.values()):
                n = (length + resolution - 1) // resolution
                for start in range(0, n, chunk):
                    cancelled(ctx)
                    stop = min(n, start + chunk)
                    expected = np.arange(start, stop, dtype=np.int64) * resolution
                    sl = slice(cursor + start, cursor + stop)
                    if (not np.all(group['bins/chrom'][sl] == chrom_id)
                            or not np.array_equal(group['bins/start'][sl], expected)
                            or not np.array_equal(group['bins/end'][sl], np.minimum(expected + resolution, length))):
                        raise StepError('Source bins do not match its chromosome sizes and resolution')
                cursor += n
            if cursor != len(group['bins/start']):
                raise StepError('Source contains unexpected genomic bins')
            def batches():
                pixels = group['pixels']
                for start in range(0, len(pixels['count']), chunk):
                    cancelled(ctx)
                    end = start + chunk
                    a, b = pixels['bin1_id'][start:end], pixels['bin2_id'][start:end]
                    if (a > b).any() or (a < 0).any() or (b >= cursor).any():
                        raise StepError('Invalid symmetric-upper source pixel coordinates')
                    yield {'bin1_id': a, 'bin2_id': b, 'count': counts(pixels['count'][start:end])}
            assembly = params.get('assembly') or group.attrs.get('genome-assembly') or group.attrs.get('assembly') or value.info.get('assembly', 'unknown')
            import json
            inherited = value.info.get('conversion') or {}
            try:
                inherited = json.loads(group.attrs.get('metadata', '{}')).get('operon_export', inherited)
            except (TypeError, ValueError):
                pass
            yield sizes, resolution, str(assembly), batches(), {
                'coverage': inherited.get('coverage', 'source Cooler bins; coverage semantics inherited from source'),
                'region': inherited.get('region'), 'region2': inherited.get('region2'), 'source_group': group_name}
    else:
        info = value.info
        if info.get('representation') != 'contact_window' or info.get('balanced') is not False:
            raise StepError('Form contact export requires representation=contact_window and balanced=false; use raw counts')
        sizes, resolution = sizes_and_resolution(info, params)
        if value.data.ndim != 2 or value.data.shape[0] != value.data.shape[1]:
            raise StepError('Form contact export requires a square symmetric window with matching bin axes')
        offsets, offset = {}, 0
        for chrom, length in sizes.items():
            offsets[chrom] = offset
            offset += (length + resolution - 1) // resolution
        bins = []
        for axis, dim in zip(('bin1', 'bin2'), value.dims):
            keys = [axis + suffix for suffix in ('_chrom', '_start', '_end')]
            if any(k not in value.axis_info.get(dim, []) for k in keys):
                raise StepError('Contact coordinates must be declared in axis_info for each bin axis')
            arrays = [info.get(k, []) for k in keys]
            if any(len(a) != value.data.shape[0] for a in arrays):
                raise StepError('Contact coordinate lengths do not match the matrix')
            ids = []
            for chrom, start, end in zip(*arrays):
                if (chrom not in sizes or not isinstance(start, (int, np.integer))
                        or not isinstance(end, (int, np.integer)) or start < 0 or start % resolution
                        or start >= sizes[chrom] or end != min(start + resolution, sizes[chrom])):
                    raise StepError('Invalid bin coordinates for the declared chromosome sizes/resolution')
                ids.append(offsets[chrom] + int(start) // resolution)
            if len(set(ids)) != len(ids) or ids != sorted(ids):
                raise StepError('Contact bins must be unique and ordered by genomic position')
            bins.append(np.asarray(ids, dtype=np.int64))
        if not np.array_equal(*bins):
            raise StepError('Both contact axes must describe the same bins')
        def batches():
            data = value.data
            for i in range(len(bins[0])):
                for start in range(i, len(bins[1]), chunk):
                    cancelled(ctx)
                    end = min(len(bins[1]), start + chunk)
                    row = counts(data[i, start:end])
                    if not np.array_equal(row, data[start:end, i]):
                        raise StepError('Contact window must be symmetric; triangle-only matrices need an explicit reconstruction')
                    mask = row != 0
                    if mask.any():
                        yield {'bin1_id': np.full(mask.sum(), bins[0][i], dtype=np.int64),
                               'bin2_id': bins[1][start:end][mask], 'count': row[mask]}
        yield sizes, resolution, params.get('assembly') or info.get('assembly', 'unknown'), batches(), {
            'coverage': 'partial window; unexported regions are unobserved, not measured zero',
            'region': info.get('region'), 'region2': info.get('region2')}


def write_contacts(path, value, params, ctx, format):
    import hictkpy
    buffer = max(1, int(float(params.get('buffer_mb', 1)) * 1024**2))
    if ctx.memory:
        buffer = min(buffer, ctx.memory.config.chunk_bytes)
    # Python arrays, writer conversion and validation all need their own storage.
    chunk = max(1, buffer // 128)
    with contact_source(value, params, chunk, ctx) as (chroms, resolution, assembly, pixels, metadata):
        with TemporaryDirectory(prefix='contact-export-', dir=path.parent) as scratch:
            common = dict(assembly=str(assembly), tmpdir=scratch)
            if format == 'hic':
                writer = hictkpy.hic.FileWriter(str(path), chroms, resolution, n_threads=1,
                                               chunk_size=chunk, **common)
            else:
                writer = hictkpy.cooler.FileWriter(str(path), chroms, resolution, **common)
            try:
                for batch in pixels:
                    writer.add_pixels_from_dict({k: v.tolist() for k, v in batch.items()})
                cancelled(ctx)
                result = writer.finalize() if format == 'hic' else writer.finalize(chunk_size=chunk)
                del result
            finally:
                del writer
    if format == 'cool':
        import h5py
        import json
        with h5py.File(path, 'r+') as handle:
            handle.attrs['genome-assembly'] = str(assembly)
            handle.attrs['metadata'] = json.dumps({'operon_export': metadata})
    return {**metadata, 'chrom_sizes': chroms, 'resolution': resolution, 'assembly': assembly,
            'values': 'raw counts', 'normalizations': [], 'writer': 'hictkpy'}

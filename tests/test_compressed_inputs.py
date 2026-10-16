"""The picker, router and real parser must agree on external compression."""
import bz2
import gzip
import lzma
from pathlib import Path

import numpy as np
import pytest

from biopipe.packages import bundled_state
from src.reader import pick_reader, read_source
from src.web.assets import plan_input

CODECS = {'.gz': gzip.compress, '.bz2': bz2.compress, '.xz': lzma.compress}
GAF = ('!gaf-version: 2.2\n' + '\t'.join([
    'UniProtKB', 'P1', 'GENE1', '', 'GO:0008150', 'PMID:1', 'IDA', '',
    'P', 'Example', 'alias1|alias2', 'protein', 'taxon:9606', '20261015', 'TEST', '', '',
]) + '\n').encode()
VCF = (b'##fileformat=VCFv4.2\n'
       b'#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\ts1\ts2\n'
       b'1\t10\tv1\tA\tG\t.\tPASS\t.\tGT\t0/1\t1/1\n')
TEXT = {
    '.csv': b'a,b\n1,2\n3,4\n', '.tsv': b'a\tb\n1\t2\n',
    '.txt': b'a\tb\n1\t2\n', '.tab': b'a\tb\n1\t2\n',
    '.bed': b'chr1\t0\t10\n',
    '.gff3': b'##gff-version 3\nchr1\tsrc\tgene\t1\t10\t.\t+\t.\tID=g1\n',
    '.gtf': b'chr1\tsrc\tgene\t1\t10\t.\t+\t.\tgene_id "g1";\n',
    '.fa': b'>s1\nACGT\n>s2\nAGGT\n', '.gaf': GAF, '.vcf': VCF,
}
CASES = [(ext, suffix) for ext in TEXT
         for suffix in (['.gz'] if ext in ('.gaf', '.vcf') else CODECS)]


def assert_equivalent(path, compressed):
    catalog = {'readers': [d for d in bundled_state()['descriptors'] if d['kind'] == 'reader']}
    plain_plan = plan_input([path.name], catalog)
    source = plain_plan['source']
    expected = read_source(path, source['dims'], source['labels'])
    actual = read_source(compressed, source['dims'], source['labels'])
    np.testing.assert_array_equal(actual.data, expected.data)
    assert actual.dims == expected.dims and actual.labels == expected.labels
    assert actual.axis_info == expected.axis_info
    assert plan_input([compressed.name], catalog) == {**plain_plan, 'filename': compressed.name}
    return actual


@pytest.mark.parametrize(('ext', 'suffix'), CASES)
@pytest.mark.parametrize('uppercase', [False, True])
def test_text_compression_roundtrip(tmp_path, ext, suffix, uppercase):
    path = tmp_path / ('input' + ext)
    path.write_bytes(TEXT[ext])
    compressed = path.with_name(path.name + (suffix.upper() if uppercase else suffix))
    compressed.write_bytes(CODECS[suffix](path.read_bytes()))
    result = assert_equivalent(path, compressed)
    if ext == '.gaf':
        assert result.info['db_object_synonym'] == ['alias1|alias2']


@pytest.mark.parametrize('suffix', CODECS)
@pytest.mark.parametrize('ext', ['.h5ad', '.parquet'])
def test_outer_compression_of_binary_containers(tmp_path, suffix, ext):
    import pandas as pd
    path = tmp_path / ('input' + ext)
    if ext == '.h5ad':
        import anndata as ad
        ad.AnnData(np.arange(6, dtype=np.float32).reshape(2, 3)).write_h5ad(path, compression='gzip')
    else:
        pd.DataFrame({'a': [1., 2.], 'b': [3., 4.]}).to_parquet(path, compression='gzip')
    compressed = path.with_name(path.name + suffix)
    compressed.write_bytes(CODECS[suffix](path.read_bytes()))
    assert_equivalent(path, compressed)


def test_compressed_h5ad_keeps_disk_preparation(tmp_path, monkeypatch):
    import anndata as ad
    from src.task import Context, run
    path = tmp_path / 'large.h5ad'
    ad.AnnData(np.ones((600, 600), dtype=np.float32)).write_h5ad(path)
    compressed = path.with_name(path.name + '.gz')
    compressed.write_bytes(gzip.compress(path.read_bytes()))
    monkeypatch.setattr(ad, 'read_h5ad', lambda *a, **k: pytest.fail('Eager AnnData read is forbidden'))
    manifest = {'sources': {'X': {'path': str(compressed), 'dims': ['sample', 'feature'], 'labels': {}}},
                'steps': [{'name': 'describe', 'inputs': ['X']}],
                'runtime': {'memory': {'budget_mb': 1, 'chunk_mb': .01, 'keep': ['X']}}}
    ctx = Context(tmp_path, manifest)
    try:
        ctx.register_source('X', manifest['sources']['X'])
        entry = ctx.forms.entry('X')
        assert entry.source_probe['file_bytes'] == compressed.stat().st_size
        assert entry.source_probe['dense_bytes'] == 600 * 600 * 4
        run(ctx, manifest['steps'])
        assert entry.form is None and entry.disk
        matrix = np.load(entry.disk / 'data.npy', mmap_mode='r')
        assert matrix.shape == (600, 600) and matrix.sum() == 360000
        del matrix
    finally:
        ctx.finalize()


@pytest.mark.parametrize('suffix', ['.gz', '.GZ'])
def test_mtx_compressed_main_and_companions(tmp_path, suffix):
    files = {'matrix.mtx' + suffix: b'%%MatrixMarket matrix coordinate integer general\n2 2 2\n1 1 7\n2 2 9\n',
             'features.tsv.gz': b'g1\tGene1\ng2\tGene2\n', 'barcodes.tsv.gz': b'c1\nc2\n'}
    for name, data in files.items():
        (tmp_path / name).write_bytes(gzip.compress(data))
    catalog = {'readers': [d for d in bundled_state()['descriptors'] if d['kind'] == 'reader']}
    plan = plan_input(list(files), catalog)
    source = plan['source']
    result = read_source(tmp_path / plan['filename'], source['dims'], source['labels'])
    np.testing.assert_array_equal(result.data, [[7, 0], [0, 9]])
    assert list(result.labels['cell']) == ['c1', 'c2']


@pytest.mark.parametrize('filename', ['a.csv.zst', 'a.vcf.bz2', 'a.gaf.xz', 'a.pgen.gz'])
def test_unsupported_compression_fails_before_parser(tmp_path, filename):
    from src.core import ReaderError
    path = tmp_path / filename
    path.write_bytes(b'invalid content that must not reach a parser')
    path.with_suffix('.pvar').write_text('')
    path.with_suffix('.psam').write_text('')
    with pytest.raises(ReaderError, match='compression'):
        read_source(path, ['a', 'b'], {})


def test_compressed_binary_bed_is_not_misrouted_to_interval_reader(tmp_path):
    from src.core import ReaderError
    path = tmp_path / 'x.bed.gz'
    path.write_bytes(gzip.compress(b'\x6c\x1b\x01'))
    (tmp_path / 'x.bim').write_text('')
    (tmp_path / 'x.fam').write_text('')
    with pytest.raises(ReaderError):
        pick_reader(path)


def test_decompression_keeps_basename_and_cleans_parser_sidecars(tmp_path):
    from src.reader import _decompressed
    path = tmp_path / 'values.bin.gz'
    path.write_bytes(gzip.compress(b'data'))
    with _decompressed(path) as plain:
        assert plain.name == 'values.bin'
        assert plain.read_bytes() == b'data'
        sidecar = plain.with_suffix('.index')
        sidecar.write_text('index generated by parser')
    assert not plain.exists() and not sidecar.exists()
    assert path.exists()


@pytest.mark.parametrize('suffix', CODECS)
def test_bgen_wrapper_transport_and_handle_cleanup(tmp_path, monkeypatch, suffix):
    # Regression at the optional binary parser boundary; real BGEN files are
    # exercised separately against the upstream parser's published fixture.
    import bgen_reader
    from contextlib import contextmanager
    paths = []

    @contextmanager
    def open_bgen(path, **kwargs):
        from types import SimpleNamespace
        path = Path(path)
        assert path.read_bytes() == b'BGEN parser input'
        sidecar = path.with_suffix('.metadata2.mmm')
        with sidecar.open('wb') as stream:
            stream.write(b'index')
            paths.append((path, sidecar))
            yield SimpleNamespace(ids=['v1'], samples=['s1'],
                read=lambda: np.array([[[0., 1., 0.]]]))

    monkeypatch.setattr(bgen_reader, 'open_bgen', open_bgen)
    path = tmp_path / ('input.bgen' + suffix)
    path.write_bytes(CODECS[suffix](b'BGEN parser input'))
    result = read_source(path, ['variant', 'sample'], {})
    np.testing.assert_array_equal(result.data, [[1.]])
    assert all(not p.exists() for pair in paths for p in pair)


@pytest.mark.parametrize('failure', ['corrupt', 'reader'])
def test_temporary_files_cleaned_on_failure(tmp_path, monkeypatch, failure):
    import tempfile
    from src.core import ReaderError
    from src.reader import _decompressed
    stage = tmp_path / 'temp'
    stage.mkdir()
    monkeypatch.setattr(tempfile, 'tempdir', str(stage))
    path = tmp_path / 'bad.txt.gz'
    path.write_bytes(b'not gzip' if failure == 'corrupt' else gzip.compress(b'data'))
    with pytest.raises(ReaderError):
        with _decompressed(path):
            raise ReaderError('Parser failure')
    assert not list(stage.iterdir())


def test_custom_metadata_probe_gets_same_unwrapped_input_as_read(tmp_path, monkeypatch):
    import src.reader as readers
    from src.core import Form
    from src.core.contracts import reader_contract
    from src.reader.base import Reader
    from src.task import Context
    observed = []

    class HeaderReader(Reader):
        extensions = ['.header']
        output_contract = reader_contract()

        def probe(self, path, **args):
            assert path.read_bytes() == b'1,2'
            observed.append(path)
            return {'file_bytes': path.stat().st_size, 'dense_bytes': 8}

        def read(self, path, dims, labels, **args):
            assert path.read_bytes() == b'1,2'
            return Form(np.array([[1., 2.]], dtype=np.float32), dims,
                        {dims[0]: {'0': 0}, dims[1]: {'0': 0, '1': 1}}, {'missing_code': np.nan})

    monkeypatch.setattr(readers, 'READERS', [HeaderReader()])
    path = tmp_path / 'values.header.gz'
    path.write_bytes(gzip.compress(b'1,2'))
    ctx = Context(tmp_path, {'runtime': {'memory': {'budget_mb': 1}}})
    try:
        ctx.register_source('X', {'path': str(path), 'dims': ['row', 'column']})
        assert ctx.forms.entry('X').source_probe['file_bytes'] == path.stat().st_size
        np.testing.assert_array_equal(ctx['X'].data, [[1, 2]])
        assert observed and all(not p.exists() for p in observed)
    finally:
        ctx.finalize()

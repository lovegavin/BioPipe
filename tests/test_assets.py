"""Import every registered format without optional parsing libraries installed."""
import builtins
import asyncio
import gzip
from pathlib import Path

from fastapi.testclient import TestClient
import httpx
import pytest

from src.reader import pick_reader, read_source
from src.web.api import create_app
from src.web.assets import plan_input
from src.web.service import Settings
from src.web.profile import upload_limit_from_env

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def studio(tmp_path, monkeypatch):
    original = builtins.__import__
    def without_optional(name, *args, **kwargs):
        if name.split('.')[0] in {'anndata', 'h5py', 'pyarrow', 'fastparquet', 'bed_reader', 'bgen_reader', 'cyvcf2', 'pgenlib'}:
            raise ImportError(f'Intentionally unavailable: {name}')
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', without_optional)
    app = create_app(Settings(tmp_path, tmp_path / 's', ROOT / 'frontend/dist', testing=True, code_root=ROOT))
    with TestClient(app) as client:
        data = client.get('/api/bootstrap').json()
        client.headers['X-Studio-Token'] = data['token']
        yield client, data


def upload(client, files, base_dir='.'):
    start = client.post('/api/assets/batches', json={'filenames': list(files)})
    assert start.status_code == 200, start.text
    key = start.json()['id']
    for name, content in files.items():
        response = client.post('/api/assets', params={'filename': name, 'batch': key}, content=content)
        assert response.status_code == 200, response.text
    return key, client.post(f'/api/assets/batches/{key}/complete', json={'base_dir': base_dir})


@pytest.mark.parametrize(('reader', 'files'), [
    ('CsvReader', {'a.csv': b'a,b\n1,2\n'}),
    ('TxtReader', {'a.tsv': b'a\tb\n1\t2\n'}),
    ('BedReader', {'a.bed': b'chr1\t0\t10\n'}),
    ('Gff3Reader', {'a.gff3': b'##gff-version 3\n'}),
    ('GtfReader', {'a.gtf': b'#fixture\n'}),
    ('FastaReader', {'a.fa': b'>seq\nACGT\n'}),
    ('H5adReader', {'a.h5ad': b'opaque h5ad fixture'}),
    ('ParquetReader', {'a.parquet': b'opaque parquet fixture'}),
    ('BgenReader', {'a.bgen': b'opaque bgen fixture'}),
    ('VcfReader', {'a.vcf.gz': gzip.compress(b'##fileformat=VCFv4.2\n')}),
    ('Plink1Reader', {'a.bed': b'\x6c\x1b\x01', 'a.bim': b'1 rs1 0 10 A C\n', 'a.fam': b'0 s1 0 0 1 -9\n'}),
    ('Plink2Reader', {'a.pgen': b'opaque pgen fixture', 'a.pvar': b'#CHROM\tPOS\tID\tREF\tALT\n', 'a.psam': b'#IID\ns1\n'}),
    ('MtxReader', {'matrix.mtx.gz': gzip.compress(b'%%MatrixMarket matrix coordinate integer general\n1 1 1\n1 1 7\n'),
                   'features.tsv.gz': gzip.compress(b'g1\tGene1\n'), 'barcodes.tsv': b'cell1\n'}),
])
def test_all_readers_import_without_optional_dependencies(studio, reader, files):
    client, data = studio
    key, response = upload(client, files)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['reader'] == reader
    path = client.app.state.service.root / result['source']['path']
    assert type(pick_reader(path)).__name__ == reader
    for name, content in files.items():
        assert (path.parent / name).read_bytes() == content
    assert len(result['source']['dims']) == 2
    # The canvas and executable manifests remain compatible with existing Source.
    graph = data['demo']
    graph['nodes'] = [dict(graph['nodes'][0], source=result['source']), graph['nodes'][-1]]
    graph['edges'] = [{'id':'input-summary', 'source':graph['nodes'][0]['id'], 'target':'summary', 'targetHandle':'in-0'}]
    assert client.post('/api/workflows/prepare', json=graph).status_code == 200
    exported = client.post('/api/export', json=graph)
    assert exported.status_code == 200, exported.text
    assert client.post('/api/assets', params={'filename': next(iter(files)), 'batch': key}, content=b'replace').status_code == 422


def test_real_core_formats_and_mtx_after_upload(studio):
    client, _ = studio
    cases = [
        ({'x.csv.gz': gzip.compress(b'a,b\n1,2\n3,4\n')}, (2, 2)),
        ({'x.tsv': b'a\tb\n1\t2\n'}, (1, 2)),
        ({'x.bed': b'chr1\t0\t10\n'}, (1, 3)),
        ({'x.gff3': b'##gff-version 3\nchr1\tsrc\tgene\t1\t10\t.\t+\t.\tID=g1\n'}, (1, 9)),
        ({'x.gtf': b'chr1\tsrc\tgene\t1\t10\t.\t+\t.\tgene_id "g1";\n'}, (1, 9)),
        ({'x.fa': b'>s1\nACGT\n>s2\nAGGT\n'}, (2, 4)),
        ({'matrix.mtx': b'%%MatrixMarket matrix coordinate integer general\n1 1 1\n1 1 7\n',
          'features.tsv': b'g1\tGene1\n', 'barcodes.tsv.gz': gzip.compress(b'c1\n')}, (1, 1)),
    ]
    for files, shape in cases:
        _, response = upload(client, files)
        source = response.json()['source']
        form = read_source(client.app.state.service.root / source['path'], source['dims'], source['labels'], **source['args'])
        assert form.data.shape == shape
        if any(name.endswith(('.fa', '.mtx')) for name in files):
            assert 'encoders' not in form.info


@pytest.mark.parametrize('names', [
    ['a.pgen'], ['a.bed', 'a.bim'], ['matrix.mtx'], ['a.csv', 'b.csv'],
    ['a.exe'], ['../a.csv'], ['C:\\a.csv'], ['a.csv', 'A.csv'], ['NUL.csv'], ['a.csv.zst'],
    ['a.pgen.gz', 'a.pvar', 'a.psam'],
])
def test_invalid_or_incomplete_selection_is_rejected_before_transfer(studio, names):
    client, _ = studio
    assert client.post('/api/assets/batches', json={'filenames': names}).status_code == 422


def test_partial_upload_limits_cleanup_and_binary_bed(studio):
    client, _ = studio
    key = client.post('/api/assets/batches', json={'filenames':['a.csv']}).json()['id']
    assert client.post(f'/api/assets/batches/{key}/complete', json={}).status_code == 422
    assert client.post('/api/assets', params={'batch': key, 'filename':'other.csv'}, content=b'a').status_code == 422
    service = client.app.state.service
    service.settings.max_upload = 4
    assert client.post('/api/assets', params={'batch':key, 'filename':'a.csv'}, content=b'12345').status_code == 413
    assert not (service.assets_dir / key / 'a.csv').exists()
    assert not (service.assets_dir / key / '.a.csv.part').exists()
    assert client.post(f'/api/assets/batches/{key}/cancel', json={}).status_code == 200
    assert not (service.assets_dir / key).exists()
    assert client.post('/api/assets?filename=a.csv', content=b'').status_code == 422
    assert client.post('/api/assets?filename=a.bed', content=b'\x6c\x1b\x01').status_code == 422


def test_collision_free_sets_relative_paths_and_plugin_descriptors(studio):
    client, data = studio
    _, first = upload(client, {'same.csv': b'a\n1\n'}, 'tasks/demo')
    _, second = upload(client, {'same.csv': b'a\n2\n'})
    root = client.app.state.service.root
    first_path = (root / 'tasks/demo' / first.json()['source']['path']).resolve()
    assert first_path.read_bytes() == b'a\n1\n'
    assert first_path != root / second.json()['source']['path']
    plugin = {'name':'CustomReader', 'extensions':['.custom'], 'handles_compression':False,
              'file_input':{'dims':['row','column']}}
    assert plan_input(['a.custom.xz'], {'readers':[plugin]})['reader'] == 'CustomReader'
    for item in data['catalog']['readers']:
        assert item['extensions'][0] in data['upload_extensions']


def test_default_upload_streams_past_previous_256_mib_limit(studio):
    client, data = studio
    assert data['upload_limit_mb'] is None
    service = client.app.state.service
    chunk = b'0,1\n' * (1024**2 // 4)
    async def transfer():
        async def body():
            for index in range(257):
                yield chunk
                # A partial file must exist before the next chunk is requested:
                # this detects whole-body buffering as well as the former cap.
                partial = list(service.assets_dir.glob('*/.large.csv.part'))
                assert len(partial) == 1
                assert partial[0].stat().st_size == (index + 1) * len(chunk)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=client.app), base_url='http://testserver') as stream:
            return await stream.post('/api/assets?filename=large.csv', content=body(),
                                     headers={'X-Studio-Token': data['token'], 'Content-Type':'application/octet-stream'})
    response = asyncio.run(transfer())
    assert response.status_code == 200, response.text
    path = service.root / response.json()['path']
    try:
        assert path.stat().st_size == response.json()['bytes'] == 257 * 1024**2
    finally:
        path.unlink()  # Remove this test's generated 257 MiB payload.


@pytest.mark.parametrize(('raw', 'expected'), [(None, None), ('0', None), ('512', 512 * 1024**2)])
def test_optional_upload_limit_configuration(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv('BIOPIPE_STUDIO_MAX_UPLOAD_MB', raising=False)
    else:
        monkeypatch.setenv('BIOPIPE_STUDIO_MAX_UPLOAD_MB', raw)
    assert upload_limit_from_env() == expected


@pytest.mark.parametrize('raw', ['-1', 'many', '1.5'])
def test_invalid_upload_limit_is_not_silently_applied(monkeypatch, raw):
    monkeypatch.setenv('BIOPIPE_STUDIO_MAX_UPLOAD_MB', raw)
    with pytest.raises(ValueError, match='non-negative integer'):
        upload_limit_from_env()

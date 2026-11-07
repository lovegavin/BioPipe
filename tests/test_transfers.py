"""Real disk transfer invariants, including restart and lost acknowledgements."""
from concurrent.futures import ThreadPoolExecutor
import base64
import hashlib
import json
import os
from pathlib import Path
import threading

import pytest

from operon.remote.transfers import TransferStore, signature
from src.web.transfers import TransferClient, TransferCancelled


def setup(tmp_path, **options):
    def resolve(value):
        path = Path(value).resolve()
        if not path.is_relative_to(tmp_path.resolve()):
            raise ValueError('Outside server input roots')
        return path
    store = TransferStore(tmp_path/'server', resolve_input=resolve, chunk_bytes=17, scan_bytes=31, **options)
    client = TransferClient(store.dispatch, tmp_path/'client', chunk_bytes=13)
    return store, client, resolve


def source(tmp_path, content=bytes(range(256))*3, name='sample.pairs.gz'):
    path = tmp_path/name
    path.write_bytes(content)
    return path


def test_round_trip_progress_empty_and_content_reuse(tmp_path):
    store, client, _ = setup(tmp_path)
    path = source(tmp_path)
    events = []
    first = client.upload(path, progress=events.append)
    assert Path(first['path']).name == path.name
    assert Path(first['path']).read_bytes() == path.read_bytes()
    assert not first['reused'] and first['bytes'] == path.stat().st_size
    assert {'hashing', 'uploading', 'verifying'} <= {e['phase'] for e in events}
    second = client.upload(path)
    assert second['reused'] and second['path'] == first['path']
    downloaded = client.download(first, 'roundtrip.pairs.gz')
    assert Path(downloaded['path']).read_bytes() == path.read_bytes()
    assert client.download(first, 'roundtrip.pairs.gz')['reused']
    empty = client.upload(source(tmp_path, b'', 'empty.vcf'))
    assert empty['bytes'] == 0 and Path(empty['path']).read_bytes() == b''
    assert client.download(empty, 'empty.vcf')['bytes'] == 0


def test_lost_ack_then_daemon_restart_resumes_verified_prefix(tmp_path):
    store, client, resolve = setup(tmp_path)
    path = source(tmp_path)
    count = [0]
    def broken(method, params):
        result = store.dispatch(method, params)
        if method == 'transfer_chunk':
            count[0] += 1
            if count[0] == 3:
                raise ConnectionError('Response vanished after durable acknowledgement')
        return result
    client.rpc = broken
    with pytest.raises(ConnectionError): client.upload(path)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    receipt = store.root/'objects'/sha/'receipt.json'
    assert json.loads(receipt.read_text())['offset'] == 39
    # The new server has no in-memory digest states.
    restarted = TransferStore(store.root, resolve_input=resolve, chunk_bytes=17, scan_bytes=31)
    offsets, events = [], []
    def observed(method, params):
        if method == 'transfer_chunk': offsets.append(params['offset'])
        return restarted.dispatch(method, params)
    client.rpc = observed
    result = client.upload(path, progress=events.append)
    assert offsets[0] == 39
    assert any(e['phase'] == 'resumed' and e['bytes_done'] == 39 for e in events)
    assert Path(result['path']).read_bytes() == path.read_bytes()


def test_cancel_retains_prefix_and_unacknowledged_tail_is_truncated(tmp_path):
    store, client, _ = setup(tmp_path)
    path = source(tmp_path)
    cancel = threading.Event()
    def progress(event):
        if event['phase'] == 'uploading' and event['bytes_done'] >= 26: cancel.set()
    with pytest.raises(TransferCancelled): client.upload(path, cancel=cancel, progress=progress)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    part = store.root/'objects'/sha/'partial'
    with part.open('ab') as handle: handle.write(b'unacknowledged-crash-tail')
    state = store.begin(sha, path.stat().st_size, path.name)
    assert state['offset'] == part.stat().st_size == 26
    cancel.clear()
    assert client.upload(path, cancel=cancel)['bytes'] == path.stat().st_size


def test_corrupt_prefix_is_never_resumed_or_published(tmp_path):
    store, client, _ = setup(tmp_path)
    path = source(tmp_path)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    store.begin(sha, path.stat().st_size, path.name)
    store.chunk(sha, 0, base64.b64encode(b'wrong-prefix!').decode(), hashlib.sha256(b'wrong-prefix!').hexdigest())
    with pytest.raises(ValueError, match='prefix checksum'): client.upload(path)
    assert not (store.root/'objects'/sha/'blob').exists()


def test_chunk_checksum_bounds_and_full_digest_are_enforced(tmp_path):
    store, client, _ = setup(tmp_path)
    sha = hashlib.sha256(b'expected').hexdigest()
    store.begin(sha, 8, 'a.csv')
    with pytest.raises(ValueError, match='checksum'):
        store.chunk(sha, 0, base64.b64encode(b'garbage!').decode(), sha)
    with pytest.raises(ValueError, match='limit'):
        store.chunk(sha, 0, base64.b64encode(b'x'*18).decode(), hashlib.sha256(b'x'*18).hexdigest())
    store.chunk(sha, 0, base64.b64encode(b'garbage!').decode(), hashlib.sha256(b'garbage!').hexdigest())
    with pytest.raises(ValueError, match='Full transfer checksum'):
        client.scan({'sha256': sha, 'name': 'a.csv'})
    assert not (store.root/'objects'/sha/'blob').exists()


def test_source_mutation_and_changed_cache_are_detected(tmp_path):
    store, client, _ = setup(tmp_path)
    path = source(tmp_path)
    def mutate(event):
        if event['phase'] == 'uploading' and event['bytes_done'] == 13:
            path.write_bytes(b'x'*path.stat().st_size)
    with pytest.raises(ValueError, match='source changed'): client.upload(path, progress=mutate)
    result = client.upload(path)
    Path(result['path']).write_bytes(b'y'*result['bytes'])
    with pytest.raises(ValueError, match='checksum'): client.upload(path)
    with pytest.raises(ValueError, match='changed'): client.describe(result)


def test_download_interruption_resume_and_prefix_corruption(tmp_path):
    store, client, _ = setup(tmp_path)
    path = source(tmp_path)
    count = [0]
    def broken(method, params):
        if method == 'transfer_read':
            count[0] += 1
            if count[0] == 4: raise ConnectionError('Disconnected')
        return store.dispatch(method, params)
    client.rpc = broken
    with pytest.raises(ConnectionError): client.download(str(path), 'sample.gz')
    offsets = []
    def resumed(method, params):
        if method == 'transfer_read': offsets.append(params['offset'])
        return store.dispatch(method, params)
    client.rpc = resumed
    result = client.download(str(path), 'sample.gz')
    assert offsets[0] == 39 and Path(result['path']).read_bytes() == path.read_bytes()
    count[0] = 0; client.rpc = broken
    with pytest.raises(ConnectionError): client.download(str(path), 'bad.gz')
    (client.cache_dir/'bad.gz.operon-part').write_bytes(b'x'*39)
    client.rpc = resumed
    with pytest.raises(ValueError, match='prefix checksum'): client.download(str(path), 'bad.gz')
    assert not (client.cache_dir/'bad.gz').exists()


def test_download_response_corruption_and_source_mutation_are_rejected(tmp_path):
    store, client, _ = setup(tmp_path)
    path = source(tmp_path)
    def corrupt(method, params):
        result = store.dispatch(method, params)
        if method == 'transfer_read': result['base64_data'] = base64.b64encode(b'x'*result['bytes']).decode()
        return result
    client.rpc = corrupt
    with pytest.raises(ValueError, match='checksum'): client.download(str(path), 'bad')
    def change(method, params):
        if method == 'transfer_read': path.write_bytes(b'x'*path.stat().st_size)
        return store.dispatch(method, params)
    client.rpc = change
    with pytest.raises(ValueError, match='changed'): client.download(str(path), 'changed')


def test_paths_symlinks_and_cache_quota(tmp_path):
    store, client, _ = setup(tmp_path, quota_bytes=18)
    path = source(tmp_path, b'123456789')
    for name in ('../escape', '/absolute', r'a\b', 'NUL.csv', 'trailing.', ''):
        with pytest.raises(ValueError): store.begin(hashlib.sha256(b'').hexdigest(), 0, name)
    with pytest.raises(ValueError, match='owned cache'): client.download(str(path), tmp_path/'outside')
    result = client.upload(path)
    with pytest.raises(OSError, match='quota'): client.upload(source(tmp_path, b'x'*19, 'second'))
    with pytest.raises(ValueError, match='Outside'): client.describe(str(tmp_path.parent/'outside'))
    link = tmp_path/'link'
    try:
        link.symlink_to(path)
    except OSError:
        pytest.skip('Symlink creation requires Windows developer mode or elevation')
    with pytest.raises(ValueError, match='Symlinks'): client.upload(link)
    with pytest.raises(ValueError, match='Symlinks'): client.describe(str(link))


def test_concurrent_identical_senders_do_not_corrupt_data(tmp_path):
    store, client, _ = setup(tmp_path)
    path = source(tmp_path)
    clients = [TransferClient(store.dispatch, tmp_path/('client'+str(i)), chunk_bytes=13) for i in range(3)]
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda c: c.upload(path), clients))
    assert len({r['path'] for r in results}) == 1
    assert Path(results[0]['path']).read_bytes() == path.read_bytes()


def test_companion_materialization_names_reuse_and_fallback(tmp_path, monkeypatch):
    store, client, _ = setup(tmp_path)
    refs = [client.upload(source(tmp_path, bytes([i])*50, 'sample'+suffix)) for i, suffix in enumerate(('.bed', '.bim', '.fam'))]
    files = [{'name': Path(ref['path']).name, 'reference': ref} for ref in refs]
    group = client.materialize(files)
    assert sorted(p.name for p in Path(group['path']).iterdir()) == ['sample.bed', 'sample.bim', 'sample.fam']
    assert client.materialize(files)['reused']
    with pytest.raises(ValueError, match='Duplicate'): client.materialize(files+files[:1])
    with pytest.raises(ValueError): client.materialize([{'name': '../bad', 'reference': refs[0]}])
    renamed = [{'name': 'renamed.bed', 'reference': refs[0]}]
    monkeypatch.setattr(os, 'link', lambda *args, **kwargs: (_ for _ in ()).throw(OSError('No hardlinks')))
    copied = client.materialize(renamed)
    assert Path(copied['paths']['renamed.bed']).read_bytes() == bytes([0])*50


def test_read_and_scan_work_are_bounded(tmp_path, monkeypatch):
    store, client, _ = setup(tmp_path)
    path = source(tmp_path)
    observed = []
    original = store.dispatch
    def rpc(method, params):
        result = original(method, params)
        if method == 'transfer_chunk': assert len(base64.b64decode(params['base64_data'])) <= 13
        if method == 'transfer_scan': observed.append(result)
        return result
    client.rpc = rpc
    result = client.upload(path)
    scans = [e['offset'] for e in observed]
    assert scans[0] <= 31 and all(b-a <= 31 for a, b in zip(scans, scans[1:]))
    with pytest.raises(ValueError, match='chunk limit'):
        store.read(result['path'], signature(Path(result['path'])), 0, 18)


def test_deep_cache_copy_fallback_receipts_and_companions(tmp_path, monkeypatch):
    """Windows MAX_PATH must not break durable copy fallback or cache reuse."""
    from operon.bytecode import filesystem_path
    root = tmp_path / 'remote-cache'
    while len(str(root)) < 300:
        root /= 'nested-cache-' + 'x' * 48
    payload = bytes(range(256)) * 3
    original = source(tmp_path, payload, 'input.vcf.gz')
    fallback_calls = []
    def no_hardlinks(*args, **kwargs):
        fallback_calls.append(args)
        raise PermissionError('Synthetic filesystem does not support hardlinks')
    monkeypatch.setattr(os, 'link', no_hardlinks)
    store = TransferStore(root, resolve_input=lambda value: Path(value),
                          chunk_bytes=127, scan_bytes=191, quota_bytes=8192)
    client = TransferClient(store.dispatch, tmp_path / 'local-cache', chunk_bytes=113)
    result = client.upload(original)
    assert len(result['path']) > 260 and not result['path'].startswith('\\\\?\\')
    assert Path(filesystem_path(result['path'], resolve=False)).read_bytes() == payload
    assert fallback_calls
    receipt = root / 'objects' / result['sha256'] / 'receipt.json'
    record = json.loads(Path(filesystem_path(receipt, resolve=False)).read_text())
    assert record['complete'] and record['offset'] == len(payload)
    assert 'input.vcf.gz' in record['aliases']
    # New server state must reuse durable receipts without resending chunks.
    restarted = TransferStore(root, resolve_input=lambda value: Path(value),
                              chunk_bytes=127, scan_bytes=191, quota_bytes=8192)
    calls = []
    def observed(method, params):
        calls.append(method)
        return restarted.dispatch(method, params)
    client.rpc = observed
    again = client.upload(original)
    assert again['reused'] and again['path'] == result['path']
    assert 'transfer_chunk' not in calls
    files = [{'name': 'renamed.vcf.gz', 'reference': again}]
    group = client.materialize(files)
    assert Path(filesystem_path(group['paths']['renamed.vcf.gz'], resolve=False)).read_bytes() == payload
    assert not group['path'].startswith('\\\\?\\')
    assert client.materialize(files)['reused']
    downloaded = client.download(again, 'roundtrip.vcf.gz')
    assert Path(downloaded['path']).read_bytes() == payload
    assert client.download(again, 'roundtrip.vcf.gz')['reused']
    with pytest.raises(ValueError, match='owned cache'):
        restarted.owned(tmp_path / 'outside')


def test_deep_local_download_cache_resumes_and_reuses_receipt(tmp_path):
    from operon.bytecode import filesystem_path
    cache = tmp_path / 'downloads'
    while len(str(cache)) < 300:
        cache /= 'nested-download-' + 'x' * 45
    path = source(tmp_path, bytes(range(256)) * 5, 'server-input.pairs.gz')
    store = TransferStore(tmp_path / 'remote', resolve_input=lambda value: Path(value),
                          chunk_bytes=127, scan_bytes=191)
    client = TransferClient(store.dispatch, cache, chunk_bytes=97)
    cancel = threading.Event()
    def progress(event):
        if event['phase'] == 'downloading' and event['bytes_done'] >= 97:
            cancel.set()
    with pytest.raises(TransferCancelled):
        client.download(str(path), 'downloaded.pairs.gz', cancel=cancel, progress=progress)
    receipt = cache / 'downloaded.pairs.gz.operon-receipt.json'
    assert json.loads(Path(filesystem_path(receipt, resolve=False)).read_text())['offset'] == 97
    restarted = TransferClient(store.dispatch, cache, chunk_bytes=97)
    events = []
    result = restarted.download(str(path), 'downloaded.pairs.gz', progress=events.append)
    assert any(event['phase'] == 'resumed' and event['bytes_done'] == 97 for event in events)
    assert not result['path'].startswith('\\\\?\\')
    assert Path(filesystem_path(result['path'], resolve=False)).read_bytes() == path.read_bytes()
    assert not Path(filesystem_path(receipt, resolve=False)).exists()
    assert restarted.download(str(path), 'downloaded.pairs.gz')['reused']

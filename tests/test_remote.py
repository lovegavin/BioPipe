"""SSH control, offline canvas snapshots and server-owned worker regressions."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import threading
import time

import pytest
from fastapi.testclient import TestClient

from biopipe.remote.client import SSHConnection, HostKeyRequired, RemoteError
from biopipe.remote.protocol import Decoder, frames
from biopipe.remote.server import RemoteService
from biopipe.platforms import supported_systems, systems_status
from src.web.api import create_app
from src.web.models import Graph
from src.web.service import Settings
from src.web.remote_service import RemoteManager

ROOT = Path(__file__).resolve().parents[1]


def profile(**values):
    return dict(name='Test server', host='127.0.0.1', port=22, username='test', auth='password',
                key_path='', python='python3', app_dir='/opt/biopipe', workspace='/work', mode='exec', menu_choice='', **values)


@pytest.mark.parametrize('lineage', ['summary', 'graph'])
def test_reconnect_history_retains_child_lineage_after_reload(tmp_path, lineage):
    from types import SimpleNamespace
    child = {'id': 'server-child', 'name': 'Stage', 'status': 'running',
             'created_at': '2026-01-01', 'finished_at': None, 'error': None}
    if lineage == 'summary':
        child['execution_parent_id'] = 'exec-parent'
    else:
        child['graph'] = {'runtime': {'execution_parent_id': 'exec-parent'}}
    bootstrap = {'workspace': '/work', 'history': [child]}
    class Connection:
        connected = True
        def __init__(self, *args): self.info = deepcopy(bootstrap)
        def close(self): self.connected = False
    service = SimpleNamespace(directory=tmp_path)
    manager = RemoteManager(service, connection_factory=Connection)
    record = manager.save(profile())
    key = record['id']; wrapped = f'ssh-{key}-server-child'
    manager.connect(key, {})
    assert manager.history()[0]['execution_parent_id'] == 'exec-parent'
    assert manager.history()[0]['id'] == wrapped
    manager.close()
    # An older server may omit graph and parent fields on a later reconnect.
    # Its shorter summary must not erase a previously established association.
    bootstrap['history'] = [{k: v for k, v in child.items() if k not in ('graph', 'execution_parent_id')}]
    bootstrap['history'][0]['status'] = 'complete'
    reopened = RemoteManager(service, connection_factory=Connection)
    try:
        reopened.connect(key, {})
        assert len(reopened.history()) == 1
        assert reopened.history()[0]['execution_parent_id'] == 'exec-parent'
        assert reopened.history()[0]['status'] == 'complete'
        saved = json.loads(reopened.path.read_text(encoding='utf-8'))
        assert saved['jobs'][wrapped]['summary']['execution_parent_id'] == 'exec-parent'
    finally:
        reopened.close()


def test_framing_handles_noise_echo_and_large_unicode_metadata():
    payload = {'id': 'test', 'metadata': '输入路径🧬' * 5000}
    decoder = Decoder('R')
    assert decoder.feed('Welcome to the gateway\r\n') is None
    for part in frames(payload, 'Q'):
        assert decoder.feed(part) is None
    encoded = frames(payload, 'R')
    result = None
    for part in encoded:
        assert len(part) < 2048
        result = decoder.feed('\x1b[0m'+part.replace('\n', '\r\n'))
    assert result == payload
    damaged = frames({'x': 1}, 'R')[0].replace('eJ', 'aJ')
    with pytest.raises(ValueError): Decoder('R').feed(damaged)


def test_platform_catalog_derivation_does_not_change_author_protocol():
    item = {'resources': {'external_tools': ['bwa', 'samtools']}, 'dependencies': ['numpy>=1.26']}
    original = deepcopy(item)
    assert supported_systems(item) == ['linux'] and systems_status(item) == 'inferred'
    assert item == original
    assert supported_systems({'dependencies': ['numpy', 'pysam']}) == ['linux', 'macos']
    assert systems_status({'dependencies': ['unknown-library']}) == 'unknown'
    assert 'windows' in supported_systems({'dependencies': ['pysam; sys_platform == "linux"']})


def test_real_local_ssh_host_trust_and_transport():
    paramiko = pytest.importorskip('paramiko')
    key = paramiko.RSAKey.generate(2048)
    listener = socket.socket(); listener.bind(('127.0.0.1', 0)); listener.listen(3); listener.settimeout(10)
    errors, commands, transports = [], [], []
    class Server(paramiko.ServerInterface):
        def check_auth_password(self, username, password):
            return paramiko.AUTH_SUCCESSFUL if (username, password) == ('test', 'session-secret') else paramiko.AUTH_FAILED
        def get_allowed_auths(self, username): return 'password'
        def check_channel_request(self, kind, chanid): return paramiko.OPEN_SUCCEEDED
        def check_channel_exec_request(self, channel, command): commands.append(command.decode()); return True
    def serve():
        try:
            for _ in range(2):
                connection, _ = listener.accept()
                transport = paramiko.Transport(connection); transports.append(transport); transport.add_server_key(key)
                try:
                    transport.start_server(server=Server()); channel = transport.accept(5)
                except (EOFError, OSError):
                    continue
                if channel is None: continue
                channel.sendall(b'BIOPIPE_REMOTE_READY 1\n')
                decoder = Decoder('Q')
                for line in channel.makefile('r'):
                    request = decoder.feed(line.decode() if isinstance(line, bytes) else line)
                    if decoder.ack: channel.sendall(decoder.ack.encode())
                    if request is None: continue
                    value = {'protocol_version': 1} if request['method'] == 'bootstrap' else request['params']
                    for line in frames({'id': request['id'], 'ok': True, 'value': value}, 'R'):
                        channel.sendall(line.encode())
        except (EOFError, OSError): pass
        except Exception as exc: errors.append(exc)
    worker = threading.Thread(target=serve, daemon=True); worker.start()
    record = profile(); record['port'] = listener.getsockname()[1]
    try:
        with pytest.raises(HostKeyRequired) as first: SSHConnection(record, {'password': 'session-secret'})
        record['host_key'] = first.value.key
        client = SSHConnection(record, {'password': 'session-secret'})
        assert client.call('echo', {'path': '/数据/input.pairs.gz'}) == {'path': '/数据/input.pairs.gz'}
        assert 'session-secret' not in commands[-1]
        assert '-m biopipe.remote.server' in commands[-1]
        client.close()
    finally:
        for transport in transports: transport.close()
        listener.close(); worker.join(10)
    assert not errors


def test_numbered_gateway_attaches_with_blank_line_not_repeated_selection(monkeypatch):
    from types import SimpleNamespace
    import biopipe.remote.client as module
    tick = [0]
    def sleep(duration): tick[0] += duration
    monkeypatch.setattr(module, 'time', SimpleNamespace(monotonic=lambda: tick[0], sleep=sleep))
    class Channel:
        closed = False
        queue = [b'Choose a server:\n0 Example\nSelection>']
        sent = []
        def recv_ready(self): return bool(self.queue)
        def recv(self, size): return self.queue.pop(0)
        def sendall(self, value):
            self.sent.append(value)
            if self.sent == ['0\n', '\n']:
                self.queue.append(b'\n(account) user@host:~$ ')
    client = SSHConnection.__new__(SSHConnection); client.channel = Channel()
    client._enter_shell('0')
    assert client.channel.sent == ['0\n', '\n']


def test_container_gateway_envelopes_and_corrupt_frames_cannot_change_payload():
    import struct
    payload = {'id': 'reply', 'catalog': [hashlib.sha256(str(i).encode()).hexdigest() for i in range(5000)]}
    wire = b'Gateway banner\n' + b''.join(b'\x01\0\0\0'+struct.pack('!I',len(part))+part.encode()
                                         for part in frames(payload, 'R'))
    for chunk in (1, 7, 257, 65536):
        buffer = b''; decoder = Decoder('R'); response = None
        for offset in range(0,len(wire),chunk):
            buffer += wire[offset:offset+chunk]
            lines = buffer.split(b'\n'); buffer = lines.pop()
            for line in lines: response = decoder.feed(line.decode(errors='replace')) or response
        assert response == payload
    decoder = Decoder('R'); parts = frames(payload, 'R')
    decoder.feed(parts[0])
    with pytest.raises(ValueError): decoder.feed(parts[1].replace('BIOPIPE-R ', 'BIOPIPE-R bad'))
    assert decoder.ack is None
    for part in parts[1:]: response = decoder.feed(part)
    assert response == payload


def test_framed_transport_retries_damage_and_bounds_unresponsive_peer():
    from biopipe.remote.protocol import transmit
    payload = {'items': [hashlib.sha256(str(i).encode()).hexdigest() for i in range(100)]}
    decoder = Decoder('Q'); queue = []; sent = []; received = []
    def write(part):
        sent.append(part)
        if len(sent) == 1: return  # Simulate gateway truncation before receipt.
        result = decoder.feed(part)
        queue.append(decoder.ack)
        if result is not None: received.append(result)
    def read(deadline):
        if queue: return queue.pop(0)
        raise TimeoutError()
    transmit(payload, 'Q', write, read)
    assert received == [payload] and sent[0] == sent[1]
    assert all(len(part) == 1024 for part in sent)
    sent.clear()
    with pytest.raises(TimeoutError): transmit(payload, 'Q', sent.append, read)
    assert len(sent) == 3


@pytest.fixture
def remote_studio(tmp_path):
    remote = RemoteService(tmp_path/'server', input_roots=[tmp_path])
    class Connection:
        def __init__(self, record, credentials):
            self.connected = True
            self.info = remote.dispatch('bootstrap', {})
        def call(self, method, params=None): return remote.dispatch(method, params or {})
        def close(self): self.connected = False
    app = create_app(Settings(tmp_path/'editor', tmp_path/'editor/.studio', ROOT/'frontend/dist', testing=True, code_root=ROOT))
    # mount_remote handlers captured the original manager: replace its factory.
    manager = app.state.service.remotes
    manager.factory = Connection
    with TestClient(app) as client:
        client.headers['X-Studio-Token'] = client.get('/api/bootstrap').json()['token']
        record = client.post('/api/remote/profiles', json=profile()).json()
        client.post('/api/remote/'+record['id']+'/connect', json={'password': 'do-not-persist'}).raise_for_status()
        graph = deepcopy(remote.service.demo)
        graph['runtime'] = {'execution': {'kind': 'ssh', 'profile_id': record['id']}}
        graph['nodes'][0]['source']['path'] = str(remote.service.root/graph['nodes'][0]['source']['path'])
        yield client, manager, remote, record['id'], graph
    remote.service.shutdown()


def test_remote_paths_prepare_bundle_offline_and_secret_storage(remote_studio):
    client, manager, remote, key, graph = remote_studio
    response = client.post('/api/remote/'+key+'/browse', json={'path': str(remote.service.root), 'hidden': True})
    assert response.status_code == 200 and response.json()['entries']
    result = client.post('/api/workflows/prepare', json=graph)
    assert result.status_code == 200, result.text
    frozen = result.json()
    assert frozen['plugin_lock']
    assert client.post('/api/validate', json=frozen).status_code == 200
    assert 'do-not-persist' not in manager.path.read_text()
    client.post('/api/remote/'+key+'/disconnect')
    assert not manager.credentials
    assert client.post('/api/workflows/prepare', json=frozen).json() == frozen
    bundle = client.post('/api/workflows/export', json=frozen)
    assert bundle.status_code == 200
    from src.web.parameters import import_bundle
    restored = import_bundle(bundle.content)
    assert restored.runtime['execution']['profile_id'] == key
    assert restored.nodes[2].params == frozen['nodes'][2]['params']
    assert client.post('/api/jobs', json=frozen).status_code == 422


def test_remote_worker_survives_client_disconnect_and_keeps_logs_parameters(remote_studio):
    client, manager, remote, key, graph = remote_studio
    first = client.post('/api/jobs', json=graph)
    assert first.status_code == 202, first.text
    job = first.json(); assert job['id'].startswith('ssh-')
    directory = remote.service.jobs_dir/job['remote']['job_id']
    assert (directory/'parameters.json').is_file()
    assert not list(manager.service.jobs_dir.glob('*/parameters.json'))
    client.post('/api/remote/'+key+'/disconnect')
    deadline = time.monotonic()+30
    while remote.service.details(job['remote']['job_id'])['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(.1)
    client.post('/api/remote/'+key+'/connect', json={}).raise_for_status()
    completed = client.get('/api/jobs/'+job['id']).json()
    assert completed['status'] == 'complete', completed.get('error')
    assert completed['report'] and completed['summary']
    log = client.get('/api/jobs/'+job['id']+'/console')
    assert log.status_code == 200 and '[BioPipe launcher]' in log.text
    events = client.get('/api/jobs/'+job['id']+'/events')
    assert '"done": true' in events.text and 'run_finished' in events.text
    assert client.get('/api/jobs').json()[0]['remote']['profile_id'] == key
    # Server-side idempotency survives a lost submit response and reconnect.
    saved = json.loads((directory/'job.json').read_text(encoding='utf-8'))['graph']
    request_id = saved['runtime']['remote_request_id']
    same = remote.dispatch('run', {'graph': manager.prepare(Graph.model_validate(graph)).model_dump(mode='json'), 'request_id': request_id})
    assert same['id'] == job['remote']['job_id']
    with pytest.raises(ValueError, match='different graph'):
        remote.dispatch('run', {'graph': {**graph, 'name': 'different'}, 'request_id': request_id})


def test_remote_missing_profile_never_falls_back_to_local(remote_studio):
    client, manager, remote, key, graph = remote_studio
    graph['runtime']['execution'].pop('profile_id')
    response = client.post('/api/jobs', json=graph)
    assert response.status_code == 422
    assert not manager.service.jobs


def test_remote_compressed_source_uses_unwrapped_companion_names(remote_studio):
    client, manager, remote, key, graph = remote_studio
    source = remote.service.root/'input.bed.gz'
    source.write_bytes(b'')  # Detection is metadata-only, not a Reader execution.
    assert remote.dispatch('source', {'path': str(source)})['reader'] == 'BedReader'
    reader = next(r for r in remote.service.catalog['readers'] if r['id'] == 'Plink1Reader')
    for suffix in reader['requires_siblings']:
        (remote.service.root/('input'+suffix)).write_bytes(b'')
    # Binary PLINK does not declare external gzip support. Its companions must
    # still exclude the text BED Reader, rather than misclassifying the input.
    with pytest.raises(ValueError): remote.dispatch('source', {'path': str(source)})
    primary = source.with_suffix(''); primary.write_bytes(b'')
    assert remote.dispatch('source', {'path': str(primary)})['reader'] == reader['id']
    unsupported = remote.service.root/'input.csv.zst'; unsupported.write_bytes(b'')
    with pytest.raises(ValueError): remote.dispatch('source', {'path': str(unsupported)})


def test_remote_failure_logs_and_file_read_boundaries(remote_studio):
    client, manager, remote, key, graph = remote_studio
    with pytest.raises(ValueError, match='outside'):
        remote.dispatch('browse', {'path': str(remote.service.root.anchor)})
    source = remote.service.root/'broken.csv'
    source.write_text('', encoding='utf-8')
    graph['nodes'][0]['source']['path'] = str(source)
    response = client.post('/api/jobs', json=graph)
    assert response.status_code == 202, response.text
    job = response.json()
    deadline = time.monotonic()+30
    while time.monotonic() < deadline:
        finished = client.get('/api/jobs/'+job['id']).json()
        if finished['status'] != 'running': break
        time.sleep(.1)
    assert finished['status'] == 'failed' and finished['error']
    log = client.get('/api/jobs/'+job['id']+'/console')
    assert 'Traceback' in log.text

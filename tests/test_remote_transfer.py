"""Framed transfer integration through a real local SSH connection (no SFTP)."""
import base64
import hashlib
from pathlib import Path
import socket
import threading

import pytest

from biopipe.remote.client import SSHConnection
from biopipe.remote.protocol import Decoder, frames
from biopipe.remote.server import RemoteService
from biopipe.remote.transfers import TransferStore
from src.web.transfers import TransferClient


def test_remote_service_dispatch_preserves_input_allowlist(tmp_path, monkeypatch):
    import src.web.service as service_module
    settings = service_module.Settings
    monkeypatch.setattr(service_module, 'Settings', lambda *a, **kw: settings(*a, **kw, testing=True))
    remote = RemoteService(tmp_path/'remote', input_roots=[tmp_path])
    try:
        client = TransferClient(remote.dispatch, tmp_path/'client', chunk_bytes=1024)
        source = tmp_path/'input.vcf.gz'; source.write_bytes(b'synthetic compressed-placeholder\0'*500)
        result = client.upload(source)
        assert Path(result['path']).read_bytes() == source.read_bytes()
        assert client.describe(result)['sha256'] == result['sha256']
        with pytest.raises(ValueError, match='outside'):
            client.describe(str(tmp_path.parent/'unapproved'))
    finally:
        remote.service.shutdown()


def test_real_local_ssh_binary_upload_download_without_sftp(tmp_path):
    paramiko = pytest.importorskip('paramiko')
    key = paramiko.RSAKey.generate(2048)
    listener = socket.socket(); listener.bind(('127.0.0.1', 0)); listener.listen(1); listener.settimeout(10)
    errors, transports = [], []
    store = TransferStore(tmp_path/'server', resolve_input=lambda value: Path(value), scan_bytes=2048)

    class Server(paramiko.ServerInterface):
        def check_auth_password(self, username, password):
            return paramiko.AUTH_SUCCESSFUL if (username, password) == ('test', 'synthetic') else paramiko.AUTH_FAILED
        def get_allowed_auths(self, username): return 'password'
        def check_channel_request(self, kind, chanid): return paramiko.OPEN_SUCCEEDED
        def check_channel_exec_request(self, channel, command): return True
        # No subsystem handler is installed, so SFTP cannot work in this test.

    def serve():
        try:
            connection, _ = listener.accept()
            transport = paramiko.Transport(connection); transports.append(transport); transport.add_server_key(key)
            transport.start_server(server=Server())
            channel = transport.accept(5); channel.sendall(b'BIOPIPE_REMOTE_READY 1\n')
            decoder = Decoder('Q')
            for line in channel.makefile('r'):
                request = decoder.feed(line.decode() if isinstance(line, bytes) else line)
                if decoder.ack: channel.sendall(decoder.ack.encode())
                if request is None: continue
                try:
                    if request['method'] == 'handshake':
                        from biopipe.remote.handshake import CAPABILITIES
                        result = {'protocol_version': 1, 'catalog': {'operators': [], 'readers': []},
                                  'handshake': {'version': 1, 'operator_protocol': 3,
                                                'capabilities': list(CAPABILITIES), 'catalog_digest': 'test'}}
                    else:
                        result = store.dispatch(request['method'], request['params'])
                    response = {'id': request['id'], 'ok': True, 'value': result}
                except Exception as exc:
                    response = {'id': request['id'], 'ok': False, 'error': str(exc)}
                for frame in frames(response, 'R'): channel.sendall(frame.encode())
        except (EOFError, OSError): pass
        except Exception as exc: errors.append(exc)

    worker = threading.Thread(target=serve, daemon=True); worker.start()
    profile = {'name': 'Synthetic loopback', 'host': '127.0.0.1', 'port': listener.getsockname()[1],
               'username': 'test', 'auth': 'password', 'key_path': '', 'python': 'python3',
               'app_dir': '/synthetic', 'workspace': '/synthetic', 'mode': 'exec',
               'host_key': {'type': key.get_name(), 'base64': key.get_base64()}}
    connection = None
    try:
        connection = SSHConnection(profile, {'password': 'synthetic'})
        client = TransferClient(connection.call, tmp_path/'client', chunk_bytes=1024)
        source = tmp_path/'input.pairs.gz'; source.write_bytes(bytes(range(256))*19)
        uploaded = client.upload(source)
        downloaded = client.download(uploaded, 'output.pairs.gz')
        assert Path(downloaded['path']).read_bytes() == source.read_bytes()
        assert client.upload(source)['reused']
    finally:
        if connection: connection.close()
        for transport in transports: transport.close()
        listener.close(); worker.join(10)
    assert not errors

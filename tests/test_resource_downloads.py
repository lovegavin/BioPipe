"""Model downloads must not publish corrupt resumed or staged artifacts."""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading

import pytest

from src.resources.provision import download, ProvisionError, provision_one


@pytest.mark.parametrize('mode', ['resume', 'ignored', 'wrong_range', 'truncated'])
def test_real_http_resume_and_atomic_publication(tmp_path, mode):
    payload = b'synthetic model weights' * 100
    seen = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            seen.append(self.headers.get('Range'))
            offset = 17
            part = payload[offset:] if mode in ('resume', 'wrong_range') else payload
            self.send_response(206 if mode in ('resume', 'wrong_range') else 200)
            if mode in ('resume', 'wrong_range'):
                start = offset if mode == 'resume' else offset + 1
                self.send_header('Content-Range', f'bytes {start}-{len(payload)-1}/{len(payload)}')
            self.send_header('Content-Length', str(len(part)))
            self.end_headers()
            self.wfile.write(part[:-1] if mode == 'truncated' else part)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    target = tmp_path / 'weights.bin'
    target.with_suffix('.bin.part').write_bytes(payload[:17])
    try:
        if mode in ('resume', 'ignored'):
            download(f'http://127.0.0.1:{server.server_port}/weights', target,
                     sha256=hashlib.sha256(payload).hexdigest(), size=len(payload), retries=1)
            assert target.read_bytes() == payload
            assert not target.with_suffix('.bin.part').exists()
        else:
            with pytest.raises(ProvisionError):
                download(f'http://127.0.0.1:{server.server_port}/weights', target, retries=1)
            assert not target.exists()
        assert seen == ['bytes=17-']
    finally:
        server.shutdown(); server.server_close(); thread.join()


def test_wrong_size_local_staging_is_not_published(tmp_path):
    source = tmp_path / 'source'; source.mkdir()
    (source / 'weights').write_bytes(b'too short')
    result = provision_one(tmp_path / 'target', {'id': 'example', 'files': ['weights'],
                           'sizes': {'weights': 100}}, source_dir=source)
    assert result.failed and not result.copied
    assert not (tmp_path / 'target/weights').exists()

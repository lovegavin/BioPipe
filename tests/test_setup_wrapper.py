import hashlib
import json
import struct
import zipfile

import pytest

from scripts.build_setup import append_payload, payload_spec, MAGIC


def archive(tmp_path, *, full=True, extra=False):
    payload = tmp_path / 'payload.zip'
    with zipfile.ZipFile(payload, 'w') as z:
        z.writestr('Operon Studio/example.txt', b'hello')
        z.writestr('Operon Studio/package-manifest.json', json.dumps({'version': '3.0.0', 'python_bundled': full,
            'files': [{'path': 'example.txt', 'bytes': 5, 'sha256': hashlib.sha256(b'hello').hexdigest()}]}))
        if extra:
            z.writestr('Operon Studio/unlisted.py', 'unexpected')
    return payload


def test_wrapper_preserves_executable_and_exact_verified_payload(tmp_path):
    payload = archive(tmp_path)
    spec = payload_spec(payload)
    host = tmp_path / 'host.exe'; host.write_bytes(b'MZ' + b'prefix' * 100)
    output = tmp_path / 'setup.exe'
    append_payload(host, payload, output)
    raw = output.read_bytes()
    magic, offset, length = struct.unpack('<16sqq', raw[-32:])
    assert magic == MAGIC and raw[:offset] == host.read_bytes()
    assert raw[offset:offset+length] == payload.read_bytes()
    assert spec['bytes'] == length and spec['files'] == 2
    assert hashlib.sha256(raw[offset:-32]).hexdigest() == spec['sha256']


@pytest.mark.parametrize('full,extra', [(False, False), (True, True)])
def test_incomplete_or_unlisted_runtime_is_rejected(tmp_path, full, extra):
    with pytest.raises(ValueError):
        payload_spec(archive(tmp_path, full=full, extra=extra))

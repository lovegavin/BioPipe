"""Wrap a verified Full payload in the single, offline-capable Windows Setup."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import zipfile


MAGIC = b'BIOPIPE-SETUP-V1'


def payload_spec(path):
    with zipfile.ZipFile(path) as archive:
        entries = [e for e in archive.infolist() if not e.is_dir()]
        if len({e.filename.casefold() for e in entries}) != len(entries):
            raise ValueError('Duplicate payload paths')
        if any(not e.filename.startswith('Operon Studio/') for e in entries):
            raise ValueError('Expected an Operon Studio release archive')
        manifest = json.loads(archive.read('Operon Studio/package-manifest.json'))
        if not manifest.get('python_bundled'):
            raise ValueError('Setup requires a Full runtime, never a Lite archive')
        expected = {'Operon Studio/' + item['path'] for item in manifest['files']}
        actual = {e.filename for e in entries} - {'Operon Studio/package-manifest.json'}
        if expected != actual:
            raise ValueError('Payload and package manifest differ')
        for item in manifest['files']:
            entry = archive.getinfo('Operon Studio/' + item['path'])
            with archive.open(entry) as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            if digest != item['sha256'] or entry.file_size != item['bytes']:
                raise ValueError('Payload checksum mismatch: ' + item['path'])
        total = sum(e.file_size for e in entries)
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'version': manifest['version'], 'sha256': digest, 'bytes': path.stat().st_size,
            'unpackedBytes': total, 'files': len(entries)}


def append_payload(host, payload, destination):
    temporary = destination.with_suffix('.building')
    try:
        with temporary.open('xb') as output:
            with host.open('rb') as source:
                shutil.copyfileobj(source, output, 1024 * 1024)
            offset = output.tell()
            with payload.open('rb') as source:
                shutil.copyfileobj(source, output, 1024 * 1024)
            output.write(struct.pack('<16sqq', MAGIC, offset, payload.stat().st_size))
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--payload', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--build-dir', type=Path, required=True)
    parser.add_argument('--no-restore', action='store_true', help='Use previously restored native build assets')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    payload, output, build = args.payload.resolve(), args.output.resolve(), args.build_dir.resolve()
    if output.exists():
        parser.error('Output already exists; use a new candidate path')
    build.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    spec = payload_spec(payload)
    manifest = build / 'payload.json'
    manifest.write_text(json.dumps(spec, indent=2) + '\n', encoding='utf-8')
    subprocess.run(['dotnet', 'publish', str(root / 'installer/BioPipeSetup.csproj'), '-c', 'Release',
                    '-p:PayloadManifest=' + str(manifest), '-p:Version=' + spec['version'],
                    '-o', str(build / 'host'), *(['--no-restore'] if args.no_restore else [])], check=True, cwd=root)
    append_payload(build / 'host/Operon_Setup.exe', payload, output)
    with output.open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
    output.with_suffix('.exe.sha256').write_text(digest + '  ' + output.name + '\n', encoding='ascii')
    print(json.dumps({'setup': str(output), 'sha256': digest, 'bytes': output.stat().st_size, 'payload': spec}))


if __name__ == '__main__':
    main()

"""Stable server installation document, independent of any desktop revision.

Only explicit registration/installation writes this document. Routine connection
reads this one file and starts the registered bridge over authenticated SSH.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path, PurePosixPath
import sys
import uuid

SCHEMA_VERSION = 1
MAX_RECEIPT_BYTES = 65536


def validate(value):
    if not isinstance(value, dict) or value.get('schema_version') != SCHEMA_VERSION:
        raise ValueError('Unsupported BioPipe server installation document')
    if not isinstance(value.get('server_id'), str) or not value['server_id']:
        raise ValueError('Server installation identity is missing')
    for name in ('app_dir', 'python', 'workspace'):
        path = value.get(name)
        if (not isinstance(path, str) or not path.startswith('/') or
                '..' in PurePosixPath(path).parts or any(ord(c) < 32 for c in path)):
            raise ValueError(f'Invalid server {name} in installation document')
    return value


def register(base, *, app_dir, python, workspace, source_sha256=None):
    """Publish a complete pointer atomically; never move code or user data."""
    from src.web.storage import FileLock, atomic_json
    from biopipe import __version__
    base = Path(base).expanduser().resolve()
    base.mkdir(parents=True, exist_ok=True)
    destination = base / 'server.json'
    with FileLock(base / '.server-registration.lock'):
        previous = {}
        if destination.exists():
            if destination.stat().st_size > MAX_RECEIPT_BYTES:
                raise ValueError('Server installation document is too large')
            previous = validate(json.loads(destination.read_text(encoding='utf-8')))
        value = validate({'schema_version': SCHEMA_VERSION,
                          'server_id': previous.get('server_id') or uuid.uuid4().hex,
                          'version': __version__, 'app_dir': str(Path(app_dir).resolve()),
                          # A venv's executable may be a symlink to base Python;
                          # resolving it would discard the selected environment.
                          'python': str(Path(python).expanduser().absolute()), 'workspace': str(Path(workspace).resolve()),
                          'source_sha256': source_sha256,
                          'registered_at': datetime.now(timezone.utc).isoformat()})
        atomic_json(destination, value)
        destination.chmod(0o600)
        return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['register'])
    parser.add_argument('--base', type=Path, default=Path.home()/'.local/share/biopipe')
    parser.add_argument('--app-dir', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--source-sha256')
    args = parser.parse_args()
    if not (args.app_dir/'scripts/run.py').is_file():
        parser.error('The server application directory must contain scripts/run.py')
    print(json.dumps(register(args.base, app_dir=args.app_dir, python=args.python,
                              workspace=args.workspace, source_sha256=args.source_sha256)))


if __name__ == '__main__':
    main()

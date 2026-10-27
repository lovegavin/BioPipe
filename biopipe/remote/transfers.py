"""Bounded, resumable file transport over the existing SSH control channel.

Only content-verified objects are exposed to readers. Partial bytes and their
acknowledged offset survive daemon restarts; hash state deliberately does not.
All expensive scans/copies advance in bounded RPC steps, including cache hits.
"""
from contextlib import contextmanager
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import threading
import time
import uuid

from src.web.storage import FileLock, atomic_json

CHUNK_BYTES = 256 * 1024
MAX_CHUNK_BYTES = 1024 * 1024
SCAN_BYTES = 4 * 1024 * 1024


def digest(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{64}', value):
        raise ValueError('Invalid SHA-256 identity')
    return value


def number(value, label='size'):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'Invalid transfer {label}')
    return value


def basename(value):
    if (not isinstance(value, str) or not value or value in ('.', '..')
            or len(value.encode('utf-8')) > 240 or any(c in value for c in '/\\:\x00<>"|?*')
            or any(ord(c) < 32 for c in value) or value.endswith((' ', '.'))):
        raise ValueError('Transfer names must be plain file basenames')
    # These are device paths on Windows even when followed by an extension.
    if value.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *('COM'+str(i) for i in range(1, 10)),
                                     *('LPT'+str(i) for i in range(1, 10))}:
        raise ValueError('Reserved transfer filename')
    return value


def no_symlinks(path):
    """Check lexical components before resolve(), including Windows junctions."""
    path = Path(os.path.abspath(path))
    for item in (path, *path.parents):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Symlinks and junctions are not allowed in transfer paths')
    return path


def signature(path):
    no_symlinks(path)
    info = Path(path).stat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError('Transfers require regular files')
    return [info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_dev, info.st_ino]


def content_signature(value):
    # Link creation changes ctime without changing any file content.
    return value[:2] + value[3:]


@contextmanager
def open_file(path, mode='rb'):
    no_symlinks(path)
    flags = os.O_RDONLY if mode == 'rb' else os.O_RDWR | os.O_CREAT
    flags |= getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(path, flags, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('Transfers require regular files')
        with os.fdopen(fd, mode) as handle:
            fd = None
            yield handle
    finally:
        if fd is not None:
            os.close(fd)


def sync_directory(path):
    if os.name != 'nt':
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


class TransferStore:
    def __init__(self, root, *, resolve_input=None, quota_bytes=None, min_free_bytes=0,
                 chunk_bytes=MAX_CHUNK_BYTES, scan_bytes=SCAN_BYTES):
        self.root = no_symlinks(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        for name in ('objects', 'groups'):
            self.owned(self.root/name).mkdir(exist_ok=True, mode=0o700)
        self.resolve_input = resolve_input
        self.quota_bytes = None if quota_bytes is None else number(quota_bytes, 'quota')
        self.min_free_bytes = number(min_free_bytes, 'reserved space')
        self.chunk_bytes = min(MAX_CHUNK_BYTES, max(1, number(chunk_bytes)))
        self.scan_bytes = max(1, number(scan_bytes))
        self.mutex = threading.RLock()
        self.tokens = {}

    def owned(self, path):
        path = no_symlinks(path)
        if not path.is_relative_to(self.root):
            raise ValueError('Transfer path is outside the owned cache')
        return path

    @contextmanager
    def locked(self):
        with self.mutex:
            lock = self.owned(self.root/'.lock')
            with FileLock(lock):
                yield

    def object(self, sha):
        path = self.owned(self.root/'objects'/digest(sha))
        path.mkdir(exist_ok=True, mode=0o700)
        return path

    def read_json(self, path):
        self.owned(path)
        with open_file(path) as handle:
            # Receipts are small metadata, never file payloads.
            value = handle.read(1024 * 1024 + 1)
        if len(value) > 1024 * 1024:
            raise ValueError('Invalid oversized transfer receipt')
        return json.loads(value)

    def write_json(self, path, value):
        self.owned(path)
        atomic_json(path, value)
        sync_directory(path.parent)

    def capacity(self, new_size=0, writing=0):
        reserved = remaining = 0
        inodes, copies = set(), []
        for folder in (self.root/'objects').iterdir():
            self.owned(folder)
            receipt = folder/'receipt.json'
            if receipt.exists():
                item = self.read_json(receipt)
                size = number(item['bytes'])
                reserved += size
                remaining += max(0, size - number(item.get('offset', size)))
                if self.quota_bytes is not None:
                    blob = folder/'blob'
                    if blob.exists():
                        stamp = signature(blob)
                        inodes.add(tuple(stamp[3:]))
                    aliases = self.owned(folder/'files')
                    if aliases.exists():
                        copies.extend(aliases.iterdir())
        if self.quota_bytes is not None:
            for group in (self.root/'groups').iterdir():
                self.owned(group)
                if group.is_dir():
                    copies.extend(group.iterdir())
            # A filesystem without hardlinks creates real extra copies. Charge
            # those bytes to the same quota, including unpublished copy tails.
            for path in copies:
                stamp = signature(self.owned(path)); inode = tuple(stamp[3:])
                if inode not in inodes:
                    reserved += stamp[0]; inodes.add(inode)
        if self.quota_bytes is not None and reserved + new_size > self.quota_bytes:
            raise OSError('Transfer cache quota exceeded')
        if shutil.disk_usage(self.root).free < max(remaining + new_size, writing) + self.min_free_bytes:
            raise OSError('Insufficient free disk space for transfer reservations')

    def begin(self, sha256, bytes, name):
        sha, size, name = digest(sha256), number(bytes), basename(name)
        with self.locked():
            folder = self.object(sha)
            receipt = folder/'receipt.json'
            blob, part = folder/'blob', folder/'partial'
            self.owned(blob); self.owned(part)
            if receipt.exists():
                record = self.read_json(receipt)
                if record['sha256'] != sha or record['bytes'] != size:
                    raise ValueError('Transfer identity conflicts with an existing receipt')
            else:
                self.capacity(new_size=size)
                record = {'sha256': sha, 'bytes': size, 'offset': 0, 'complete': False}
                self.write_json(receipt, record)
            if blob.exists():
                if signature(blob)[0] != size:
                    raise ValueError('Cached content size differs from its identity')
                offset = size
            else:
                if record.get('complete'):
                    raise ValueError('Verified transfer object is missing')
                offset = number(record['offset'])
                if not part.exists() and offset:
                    raise ValueError('Acknowledged transfer prefix is missing')
                with open_file(part, 'r+b') as handle:
                    if os.fstat(handle.fileno()).st_size < offset:
                        raise ValueError('Acknowledged transfer prefix was truncated')
                    if os.fstat(handle.fileno()).st_size != offset:
                        handle.truncate(offset)
                        handle.flush(); os.fsync(handle.fileno())
            return {'sha256': sha, 'bytes': size, 'name': name, 'offset': offset,
                    'complete': blob.exists(), 'chunk_bytes': self.chunk_bytes}

    def chunk(self, sha256, offset, base64_data, chunk_sha256):
        sha, offset = digest(sha256), number(offset, 'offset')
        if not isinstance(base64_data, str) or len(base64_data) > 4 * ((self.chunk_bytes + 2)//3):
            raise ValueError('Transfer chunk exceeds the negotiated limit')
        try:
            data = base64.b64decode(base64_data, validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError('Invalid transfer chunk encoding') from exc
        if len(data) > self.chunk_bytes:
            raise ValueError('Transfer chunk exceeds the negotiated limit')
        if not data or hashlib.sha256(data).hexdigest() != digest(chunk_sha256):
            raise ValueError('Transfer chunk checksum mismatch')
        with self.locked():
            folder = self.object(sha)
            record = self.read_json(folder/'receipt.json')
            expected = number(record['offset'])
            if offset > expected or offset + len(data) > record['bytes']:
                raise ValueError('Transfer chunk is outside the acknowledged range')
            path = folder/('blob' if (folder/'blob').exists() else 'partial')
            if offset < expected:
                if offset + len(data) > expected:
                    raise ValueError('Transfer chunk overlaps the acknowledged boundary')
                with open_file(path) as handle:
                    handle.seek(offset)
                    if handle.read(len(data)) != data:
                        raise ValueError('Retried transfer chunk differs from acknowledged content')
                return {'offset': expected}
            if record.get('complete'):
                raise ValueError('Cannot append to a published transfer')
            self.capacity(writing=len(data))
            with open_file(path, 'r+b') as handle:
                handle.seek(offset); handle.write(data); handle.flush(); os.fsync(handle.fileno())
            record['offset'] = offset + len(data)
            self.write_json(folder/'receipt.json', record)
            return {'offset': record['offset']}

    def token(self, state):
        now = time.monotonic()
        expired = [key for key, value in self.tokens.items() if now-value['touched'] > 300]
        for key in expired:
            self.tokens.pop(key, None)
        if len(self.tokens) >= 128:
            raise RuntimeError('Too many simultaneous transfer verifications')
        key = uuid.uuid4().hex
        state['touched'] = now
        self.tokens[key] = state
        return key

    def scan(self, *, token=None, sha256=None, prefix_bytes=None, name=None, path=None, snapshot=None):
        """Hash at most scan_bytes per call. Publish only after the final digest."""
        with self.locked():
            if token is not None and self.tokens.get(token, {}).get('kind') == 'alias':
                return self.copy_alias(token)
            if token is None:
                if sha256 is not None:
                    sha = digest(sha256)
                    folder = self.object(sha)
                    record = self.read_json(folder/'receipt.json')
                    target = folder/('blob' if (folder/'blob').exists() else 'partial')
                    count = record['bytes'] if prefix_bytes is None else number(prefix_bytes)
                    if count > record['offset'] or count > record['bytes']:
                        raise ValueError('Cannot verify an unacknowledged prefix')
                    publish = prefix_bytes is None
                    if publish and record['offset'] != record['bytes']:
                        raise ValueError('Transfer is incomplete')
                    state = {'kind': 'upload', 'sha256': sha, 'name': basename(name or 'data'),
                             'publish': publish, 'reused': target.name == 'blob'}
                else:
                    if self.resolve_input is None:
                        raise ValueError('Server file exports are disabled')
                    # Reject symlinks before the caller's allowlist resolver canonicalizes them.
                    no_symlinks(path)
                    target = Path(self.resolve_input(path))
                    no_symlinks(target)
                    count = signature(target)[0] if prefix_bytes is None else number(prefix_bytes)
                    if count > signature(target)[0]:
                        raise ValueError('Requested prefix exceeds file size')
                    state = {'kind': 'export', 'publish': False}
                sig = signature(target)
                if snapshot is not None and sig != snapshot:
                    raise ValueError('Transfer source changed')
                state.update(path=target, snapshot=sig, total=count, offset=0, hasher=hashlib.sha256())
                token = self.token(state)
            state = self.tokens.get(token)
            if state is None or 'hasher' not in state:
                raise ValueError('Transfer verification expired; restart verification')
            state['touched'] = time.monotonic()
            # Another sender may have atomically published this same inode.
            if state['kind'] == 'upload' and not state['path'].exists():
                published = self.object(state['sha256'])/'blob'
                if published.exists():
                    state['path'] = published
                    state['reused'] = True
            if content_signature(signature(state['path'])) != content_signature(state['snapshot']):
                self.tokens.pop(token, None)
                raise ValueError('Transfer source changed during verification')
            amount = min(self.scan_bytes, state['total']-state['offset'])
            with open_file(state['path']) as handle:
                handle.seek(state['offset'])
                remaining = amount
                while remaining:
                    block = handle.read(min(self.chunk_bytes, remaining))
                    if not block:
                        raise ValueError('Transfer source truncated during verification')
                    state['hasher'].update(block); remaining -= len(block)
                    state['offset'] += len(block)
            if content_signature(signature(state['path'])) != content_signature(state['snapshot']):
                self.tokens.pop(token, None)
                raise ValueError('Transfer source changed during verification')
            result = {'token': token, 'offset': state['offset'], 'bytes': state['total'],
                      'done': state['offset'] == state['total']}
            if not result['done']:
                return result
            actual = state['hasher'].hexdigest()
            self.tokens.pop(token, None)
            result.update(path=str(state['path']), sha256=actual, snapshot=state['snapshot'])
            if state['publish']:
                if actual != state['sha256']:
                    raise ValueError('Full transfer checksum mismatch; object was not published')
                folder = self.object(actual)
                blob = folder/'blob'
                if not state['reused']:
                    self.owned(blob)
                    os.replace(state['path'], blob)
                    sync_directory(folder)
                record = self.read_json(folder/'receipt.json')
                record.update(sha256=actual, bytes=state['total'], offset=state['total'],
                              complete=True, snapshot=signature(blob))
                self.write_json(folder/'receipt.json', record)
                # Preserve Reader extension inference without duplicating content.
                files = self.owned(folder/'files')
                files.mkdir(exist_ok=True, mode=0o700)
                alias = self.owned(files/state['name'])
                if alias.exists():
                    if not os.path.samefile(alias, blob) and signature(alias) != record.get('aliases', {}).get(state['name']):
                        raise ValueError('Transfer alias checksum identity changed')
                else:
                    try:
                        os.link(blob, alias)
                    except OSError:
                        self.capacity(writing=state['total'])
                        token = self.token({'kind': 'alias', 'source': blob, 'snapshot': signature(blob),
                            'path': alias, 'temporary': self.owned(files/('.partial-'+uuid.uuid4().hex)),
                            'offset': 0, 'total': state['total'], 'sha256': actual,
                            'hasher': hashlib.sha256(), 'reused': state['reused']})
                        return self.copy_alias(token)
                    # Link count updates ctime; keep the receipt current.
                    record['snapshot'] = signature(blob)
                    self.write_json(folder/'receipt.json', record)
                result.update(path=str(alias), snapshot=signature(alias), reused=state['reused'])
            return result

    def copy_alias(self, token):
        state = self.tokens[token]
        state['touched'] = time.monotonic()
        if content_signature(signature(state['source'])) != content_signature(state['snapshot']):
            raise ValueError('Verified content changed during filename materialization')
        remaining = min(self.scan_bytes, state['total']-state['offset'])
        self.capacity(new_size=remaining, writing=remaining)
        with open_file(state['source']) as src, open_file(state['temporary'], 'r+b') as out:
            src.seek(state['offset']); out.seek(state['offset'])
            while remaining:
                block = src.read(min(self.chunk_bytes, remaining))
                if not block:
                    raise ValueError('Verified content was truncated')
                out.write(block); state['hasher'].update(block)
                remaining -= len(block); state['offset'] += len(block)
            out.flush(); os.fsync(out.fileno())
        result = {'token': token, 'offset': state['offset'], 'bytes': state['total'],
                  'done': state['offset'] == state['total']}
        if not result['done']:
            return result
        if state['hasher'].hexdigest() != state['sha256']:
            raise ValueError('Filename materialization checksum mismatch')
        alias, folder = state['path'], state['source'].parent
        record = self.read_json(folder/'receipt.json')
        if alias.exists():
            if signature(alias) != record.get('aliases', {}).get(alias.name):
                raise ValueError('Transfer alias changed during publication')
            state['temporary'].unlink()
        else:
            os.replace(state['temporary'], alias); sync_directory(alias.parent)
            record.setdefault('aliases', {})[alias.name] = signature(alias)
            self.write_json(folder/'receipt.json', record)
        self.tokens.pop(token, None)
        return {**result, 'path': str(alias), 'sha256': state['sha256'],
                'snapshot': signature(alias), 'reused': state['reused']}

    def read(self, path, snapshot, offset, length):
        if self.resolve_input is None:
            raise ValueError('Server file exports are disabled')
        no_symlinks(path)
        path = Path(self.resolve_input(path))
        offset, length = number(offset, 'offset'), number(length, 'length')
        if not length or length > self.chunk_bytes:
            raise ValueError('Transfer read exceeds the negotiated chunk limit')
        if signature(path) != snapshot or offset > snapshot[0]:
            raise ValueError('Transfer source changed')
        with open_file(path) as handle:
            handle.seek(offset); data = handle.read(length)
        if signature(path) != snapshot:
            raise ValueError('Transfer source changed during read')
        return {'base64_data': base64.b64encode(data).decode('ascii'), 'bytes': len(data),
                'sha256': hashlib.sha256(data).hexdigest(), 'offset': offset+len(data)}

    def reference(self, value):
        sha = digest(value['sha256'])
        size = number(value['bytes'])
        folder = self.object(sha)
        blob = folder/'blob'
        record = self.read_json(folder/'receipt.json')
        supplied = self.owned(value['path'])
        same_content = os.path.samefile(supplied, blob) or (
            supplied.parent == folder/'files' and signature(supplied) == record.get('aliases', {}).get(supplied.name))
        if (not supplied.is_relative_to(folder) or not record.get('complete')
                or record['bytes'] != size or not same_content
                or signature(blob) != record['snapshot']):
            raise ValueError('Companion reference is not a verified cache object')
        return blob

    def materialize(self, files=None, token=None):
        """Publish an adjacent companion directory; fallback copies are bounded."""
        with self.locked():
            if token is None:
                if not isinstance(files, list) or not files or len(files) > 1024:
                    raise ValueError('A companion group requires between 1 and 1024 files')
                names, entries = set(), []
                for item in files:
                    name = basename(item['name'])
                    if name.casefold() in names:
                        raise ValueError('Duplicate companion filename')
                    names.add(name.casefold())
                    ref = item['reference']
                    source = self.reference(ref)
                    entries.append({'name': name, 'sha256': ref['sha256'], 'bytes': ref['bytes'],
                                    'source': str(source), 'snapshot': signature(source)})
                entries.sort(key=lambda item: item['name'])
                key = hashlib.sha256(json.dumps([{k: e[k] for k in ('name', 'sha256', 'bytes')}
                                                for e in entries], sort_keys=True).encode()).hexdigest()
                target = self.owned(self.root/'groups'/key)
                if target.exists():
                    receipt = self.read_json(target.with_suffix('.json'))
                    if any(content_signature(signature(target/e['name'])) !=
                           content_signature(receipt['snapshots'].get(e['name'], [])) for e in entries):
                        raise ValueError('Published companion content changed')
                    return {'done': True, 'path': str(target), 'paths': {e['name']: str(target/e['name']) for e in entries},
                            'reused': True}
                temporary = self.owned(self.root/'groups'/('.partial-'+uuid.uuid4().hex))
                temporary.mkdir(mode=0o700)
                token = self.token({'kind': 'group', 'entries': entries, 'index': 0, 'offset': 0,
                                    'target': target, 'temporary': temporary})
            state = self.tokens.get(token)
            if state is None or state['kind'] != 'group':
                raise ValueError('Companion materialization expired; retry')
            state['touched'] = time.monotonic()
            budget = self.scan_bytes
            while state['index'] < len(state['entries']) and budget > 0:
                item = state['entries'][state['index']]
                source = Path(item['source']); dest = self.owned(state['temporary']/item['name'])
                # ctime can change when a concurrent group adds a hardlink.
                sig = signature(source)
                if sig[:2] + sig[3:] != item['snapshot'][:2] + item['snapshot'][3:]:
                    raise ValueError('Companion source changed')
                if not dest.exists():
                    try:
                        os.link(source, dest)
                    except OSError:
                        self.capacity(writing=item['bytes'])
                    else:
                        folder = source.parent
                        receipt = self.read_json(folder/'receipt.json')
                        receipt['snapshot'] = signature(source)
                        self.write_json(folder/'receipt.json', receipt)
                        state['index'] += 1
                        continue
                amount = min(budget, item['bytes']-state['offset'])
                self.capacity(new_size=amount, writing=amount)
                hasher = state.setdefault('copy_hasher', hashlib.sha256())
                with open_file(source) as src, open_file(dest, 'r+b') as out:
                    src.seek(state['offset']); out.seek(state['offset'])
                    remaining = amount
                    while remaining:
                        block = src.read(min(self.chunk_bytes, remaining))
                        if not block:
                            raise ValueError('Companion source was truncated')
                        out.write(block); hasher.update(block); remaining -= len(block)
                    out.flush(); os.fsync(out.fileno())
                state['offset'] += amount; budget -= amount
                if state['offset'] == item['bytes']:
                    if hasher.hexdigest() != item['sha256']:
                        raise ValueError('Companion copy checksum mismatch')
                    state.pop('copy_hasher', None)
                    state['index'] += 1; state['offset'] = 0
            done = state['index'] == len(state['entries'])
            result = {'token': token, 'done': done, 'completed': state['index'], 'total': len(state['entries'])}
            if done:
                temporary, target = state['temporary'], state['target']
                snapshots = {e['name']: signature(temporary/e['name']) for e in state['entries']}
                if not target.exists():
                    os.replace(temporary, target); sync_directory(target.parent)
                    self.write_json(target.with_suffix('.json'), {'snapshots': snapshots})
                else:
                    receipt = self.read_json(target.with_suffix('.json'))
                    if any(content_signature(signature(target/e['name'])) !=
                           content_signature(receipt['snapshots'].get(e['name'], [])) for e in state['entries']):
                        raise ValueError('Published companion content changed')
                    for item in temporary.iterdir():
                        self.owned(item).unlink()
                    temporary.rmdir()
                self.tokens.pop(token, None)
                result.update(path=str(target), paths={e['name']: str(target/e['name']) for e in state['entries']}, reused=False)
            return result

    def dispatch(self, method, params):
        methods = {'transfer_begin': self.begin, 'transfer_chunk': self.chunk,
                   'transfer_scan': self.scan, 'transfer_read': self.read,
                   'transfer_materialize': self.materialize}
        if method not in methods:
            raise ValueError('Unknown transfer operation')
        return methods[method](**params)

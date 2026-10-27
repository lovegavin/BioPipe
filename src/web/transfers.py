"""File movement for execution orchestration, independent of SSH authentication.

``rpc`` is normally SSHConnection.call. No lock is retained between calls, and
payloads are bounded by chunk_bytes. Repeating upload/download after a failed
connection verifies and resumes the durable prefix instead of retransmitting it.
"""
import base64
import hashlib
import os
from pathlib import Path

from biopipe.remote.transfers import (CHUNK_BYTES, MAX_CHUNK_BYTES, basename, digest,
                                      no_symlinks, number, open_file, signature, sync_directory)
from src.web.storage import FileLock, atomic_json


class TransferCancelled(RuntimeError):
    pass


def check_cancel(cancel):
    if cancel is not None and (cancel() if callable(cancel) else cancel.is_set()):
        raise TransferCancelled('File transfer cancelled; acknowledged data is retained for resumption')


class TransferClient:
    def __init__(self, rpc, cache_dir, *, chunk_bytes=CHUNK_BYTES):
        self.rpc = rpc
        self.cache_dir = no_symlinks(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.chunk_bytes = min(MAX_CHUNK_BYTES, max(1, number(chunk_bytes)))
        # Raw bytes, base64, JSON/frame construction and compression overlap.
        # Orchestration reserves this headroom alongside worker allocations.
        self.buffer_budget_bytes = self.chunk_bytes * 12

    def owned(self, path):
        path = Path(path)
        if not path.is_absolute():
            path = self.cache_dir/path
        path = no_symlinks(path)
        if not path.is_relative_to(self.cache_dir):
            raise ValueError('Download destination must be inside the owned cache')
        return path

    @staticmethod
    def report(progress, phase, done, total, current, **extra):
        if progress:
            progress({'phase': phase, 'bytes_done': done, 'bytes_total': total,
                      'current': str(current), **extra})

    def hash_file(self, path, *, limit=None, cancel=None, progress=None, phase='hashing'):
        before = signature(path)
        total = before[0] if limit is None else number(limit)
        if total > before[0]:
            raise ValueError('Transfer prefix is missing')
        result, offset = hashlib.sha256(), 0
        self.report(progress, phase, 0, total, path)
        with open_file(path) as handle:
            while offset < total:
                check_cancel(cancel)
                block = handle.read(min(self.chunk_bytes, total-offset))
                if not block:
                    raise ValueError('Transfer source was truncated')
                result.update(block); offset += len(block)
                self.report(progress, phase, offset, total, path)
        if signature(path) != before:
            raise ValueError('Transfer source changed while hashing')
        check_cancel(cancel)
        return result.hexdigest(), before

    def scan(self, params, *, cancel=None, progress=None, current=''):
        while True:
            check_cancel(cancel)
            result = self.rpc('transfer_scan', params)
            self.report(progress, 'verifying', result['offset'], result['bytes'], current)
            if result['done']:
                check_cancel(cancel)
                return result
            params = {'token': result['token']}

    def upload(self, path, *, cancel=None, progress=None, name=None):
        path = no_symlinks(Path(path).expanduser())
        name = basename(name or path.name)
        sha, snapshot = self.hash_file(path, cancel=cancel, progress=progress)
        size = snapshot[0]
        check_cancel(cancel)
        state = self.rpc('transfer_begin', {'sha256': sha, 'bytes': size, 'name': name})
        offset = number(state['offset'])
        chunk_bytes = min(self.chunk_bytes, number(state['chunk_bytes']))
        if offset > size or not chunk_bytes:
            raise ValueError('Invalid server transfer offset/limit')
        if offset and not state['complete']:
            prefix = sha if offset == size else self.hash_file(path, limit=offset, cancel=cancel,
                                                              progress=progress, phase='verifying')[0]
            checked = self.scan({'sha256': sha, 'prefix_bytes': offset}, cancel=cancel,
                                progress=progress, current=path)
            if checked['sha256'] != prefix:
                raise ValueError('Cached transfer prefix checksum mismatch; refusing unsafe resumption')
            self.report(progress, 'resumed', offset, size, path, reused=state['complete'])
        if signature(path) != snapshot:
            raise ValueError('Transfer source changed before upload')
        with open_file(path) as handle:
            handle.seek(offset)
            self.report(progress, 'uploading', offset, size, path)
            while offset < size:
                check_cancel(cancel)
                if signature(path) != snapshot:
                    raise ValueError('Transfer source changed during upload')
                data = handle.read(min(chunk_bytes, size-offset))
                if not data:
                    raise ValueError('Transfer source truncated during upload')
                response = self.rpc('transfer_chunk', {'sha256': sha, 'offset': offset,
                    'base64_data': base64.b64encode(data).decode('ascii'),
                    'chunk_sha256': hashlib.sha256(data).hexdigest()})
                # Another concurrent sender may have acknowledged additional identical content.
                next_offset = number(response['offset'])
                if next_offset < offset+len(data) or next_offset > size:
                    raise ValueError('Invalid acknowledged transfer offset')
                offset = next_offset; handle.seek(offset)
                self.report(progress, 'uploading', offset, size, path)
        if signature(path) != snapshot:
            raise ValueError('Transfer source changed during upload')
        result = self.scan({'sha256': sha, 'name': name}, cancel=cancel, progress=progress, current=path)
        if result['sha256'] != sha or result['bytes'] != size:
            raise ValueError('Published transfer checksum mismatch')
        return {key: result[key] for key in ('path', 'sha256', 'bytes', 'reused', 'snapshot')}

    def describe(self, reference, *, cancel=None, progress=None):
        path = reference['path'] if isinstance(reference, dict) else str(reference)
        result = self.scan({'path': path}, cancel=cancel, progress=progress, current=path)
        if isinstance(reference, dict) and ((reference.get('sha256') and reference['sha256'] != result['sha256'])
                or ('bytes' in reference and reference['bytes'] != result['bytes'])):
            raise ValueError('Remote reference content changed')
        return {key: result[key] for key in ('path', 'sha256', 'bytes', 'snapshot')}

    def download(self, reference, destination, *, cancel=None, progress=None):
        import json
        path = self.owned(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        basename(path.name)
        check_cancel(cancel)
        ref = self.describe(reference, cancel=cancel, progress=progress)
        sha, size = digest(ref['sha256']), number(ref['bytes'])
        partial = self.owned(path.parent/(path.name+'.biopipe-part'))
        receipt = self.owned(path.parent/(path.name+'.biopipe-receipt.json'))
        lock = self.owned(path.parent/(path.name+'.biopipe-transfer.lock'))
        with FileLock(lock):
            if path.exists():
                actual, _ = self.hash_file(path, cancel=cancel, progress=progress, phase='verifying')
                if actual != sha:
                    raise ValueError('Download destination already contains different content')
                self.report(progress, 'resumed', size, size, path, reused=True)
                return {'path': str(path), 'sha256': sha, 'bytes': size, 'reused': True}
            record = {'sha256': sha, 'bytes': size, 'offset': 0}
            if receipt.exists():
                with open_file(receipt) as handle:
                    payload = handle.read(65537)
                if len(payload) > 65536:
                    raise ValueError('Invalid download receipt')
                record = json.loads(payload)
                if record.get('sha256') != sha or record.get('bytes') != size:
                    raise ValueError('Download receipt belongs to different content')
            offset = number(record['offset'])
            if offset > size or (offset and not partial.exists()):
                raise ValueError('Acknowledged download prefix is missing')
            with open_file(partial, 'r+b') as handle:
                if os.fstat(handle.fileno()).st_size < offset:
                    raise ValueError('Acknowledged download prefix was truncated')
                handle.truncate(offset)
                handle.flush(); os.fsync(handle.fileno())
            if offset:
                actual, _ = self.hash_file(partial, limit=offset, cancel=cancel, progress=progress, phase='verifying')
                remote = self.scan({'path': ref['path'], 'snapshot': ref['snapshot'], 'prefix_bytes': offset},
                                   cancel=cancel, progress=progress, current=path)
                if actual != remote['sha256']:
                    raise ValueError('Cached download prefix checksum mismatch')
                self.report(progress, 'resumed', offset, size, path)
            atomic_json(receipt, record); sync_directory(receipt.parent)
            with open_file(partial, 'r+b') as handle:
                handle.seek(offset)
                self.report(progress, 'downloading', offset, size, path)
                while offset < size:
                    check_cancel(cancel)
                    length = min(self.chunk_bytes, size-offset)
                    response = self.rpc('transfer_read', {'path': ref['path'], 'snapshot': ref['snapshot'],
                                                        'offset': offset, 'length': length})
                    encoded = response['base64_data']
                    if not isinstance(encoded, str) or len(encoded) > 4*((length+2)//3):
                        raise ValueError('Download chunk exceeds requested size')
                    data = base64.b64decode(encoded, validate=True)
                    if (not data or len(data) != response['bytes'] or len(data) > length
                            or response['offset'] != offset+len(data)
                            or hashlib.sha256(data).hexdigest() != response['sha256']):
                        raise ValueError('Download chunk checksum mismatch')
                    handle.write(data); handle.flush(); os.fsync(handle.fileno())
                    offset += len(data); record['offset'] = offset
                    atomic_json(receipt, record); sync_directory(receipt.parent)
                    self.report(progress, 'downloading', offset, size, path)
            actual, _ = self.hash_file(partial, cancel=cancel, progress=progress, phase='verifying')
            if actual != sha:
                raise ValueError('Full download checksum mismatch; file was not published')
            check_cancel(cancel)
            os.replace(partial, path); sync_directory(path.parent)
            receipt.unlink(missing_ok=True)
            return {'path': str(path), 'sha256': sha, 'bytes': size, 'reused': False}

    def materialize(self, files, *, cancel=None, progress=None):
        # A complete hash check protects against tampered/stale cache receipts.
        for item in files:
            self.describe(item['reference'], cancel=cancel, progress=progress)
        params = {'files': files}
        while True:
            check_cancel(cancel)
            result = self.rpc('transfer_materialize', params)
            if result['done']:
                return {key: result[key] for key in ('path', 'paths', 'reused')}
            params = {'token': result['token']}

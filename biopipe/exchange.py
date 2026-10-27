"""Portable execution-stage handoffs: tagged JSON, NPY and owned file blobs.

This is an explicit runtime source, never a Reader inferred from an extension.
No pickle is accepted from another job or machine. Run-private spill metadata
may be read through ArtifactStore's trusted-local accessor during export.
"""
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import uuid

import numpy as np

from biopipe.remote.transfers import basename, no_symlinks, open_file, signature, sync_directory
from biopipe.wire import Wire
from src.core import Form
from src.core.files import FileArtifact
from src.web.storage import atomic_json

VERSION = 1


@dataclass(frozen=True)
class _FileRef:
    name: str


class ExchangeWire(Wire):
    def __init__(self, directory, **kwargs):
        no_symlinks(directory)
        super().__init__(directory, **kwargs)
        self.external = {}
        self.audit = {}
        self.allowed_files = None

    def path(self, name):
        basename(name)
        path = no_symlinks(self.directory/name)
        if path.parent != self.directory:
            raise ValueError('Exchange reference escaped its owned directory')
        return path

    def external_file(self, value):
        source = no_symlinks(Path(value).expanduser())
        before = signature(source)
        key = str(source)
        if key in self.external:
            name, original = self.external[key]
            if before != original:
                raise ValueError('Referenced file changed during exchange export')
            return _FileRef(name)
        name = 'blob-'+uuid.uuid4().hex[:16]+'-'+source.name[-100:]
        target = self.path(name)
        self.admit(before[0])
        hasher = hashlib.sha256()
        with open_file(source) as src, target.open('xb') as out:
            while True:
                block = src.read(self.buffer_bytes)
                if not block:
                    break
                out.write(block); hasher.update(block)
            out.flush(); os.fsync(out.fileno())
        if signature(source) != before:
            raise ValueError('Referenced file changed during exchange export')
        self.external[key] = (name, before)
        self.audit[name] = {'source': str(source), 'fingerprint': {'size': before[0], 'mtime_ns': before[1]},
                            'sha256': hasher.hexdigest()}
        return _FileRef(name)

    def encode(self, value):
        if isinstance(value, _FileRef):
            return {'type': 'exchange_file', 'file': value.name}
        if isinstance(value, FileArtifact):
            value.validate()
            payload = {'format': value.format, 'files': {role: self.external_file(path) for role, path in value.files.items()},
                       'info': value.info, 'fingerprints': {}}
            return {'type': 'file_artifact', 'value': self.encode(payload)}
        if isinstance(value, Form):
            info = dict(value.info)
            if info.get('hic_files'):
                ref = FileArtifact('hic', info['hic_files'], fingerprints=info.get('hic_fingerprints', {}))
                ref.validate()
                info['hic_files'] = {role: self.external_file(path) for role, path in ref.files.items()}
                info.pop('hic_fingerprints', None)
            payload = {key: getattr(value, key) for key in ('data', 'dims', 'labels', 'axis_info')}
            payload['info'] = info
            return {'type': 'form', 'value': self.encode(payload)}
        return super().encode(value)

    def decode(self, value, *, mmap=False):
        if isinstance(value, dict) and value.get('type') == 'exchange_file':
            path = self.path(value['file'])
            signature(path)
            return str(path)
        if isinstance(value, dict) and value.get('type') == 'file_artifact':
            payload = self.decode(value['value'], mmap=mmap)
            self.check_files(payload['files'])
            if payload.get('fingerprints'):
                raise ValueError('Portable files must regenerate their local fingerprints')
            result = FileArtifact(**payload)
            result.validate()
            return result
        # Ordinary Path metadata can name an old output directory or an audit
        # location. Preserve it as metadata without stat/open/copy operations.
        # Only explicit FileArtifact/hic_files references carry file payloads.
        result = super().decode(value, mmap=mmap)
        if isinstance(result, Form) and result.info.get('hic_files'):
            self.check_files(result.info['hic_files'])
            result.info['hic_fingerprints'] = FileArtifact('hic', result.info['hic_files']).fingerprints
        return result

    def check_files(self, files):
        if not isinstance(files, dict) or not files:
            raise ValueError('Invalid portable file-role mapping')
        for value in files.values():
            path = no_symlinks(value)
            if path.parent != self.directory or self.allowed_files is None or path not in self.allowed_files:
                raise ValueError('File reference is outside the verified exchange packet')


def _export_value(ctx, name):
    if not ctx.memory:
        return ctx[name]
    store = ctx.memory.store
    with store.lock:
        entry = store.entry(name)
        if entry.form is not None:
            return entry.form
        store.stage_source(entry)
        if entry.disk is not None:
            if entry.kind == 'file':
                return FileArtifact(**json.loads((entry.disk/'files.json').read_text(encoding='utf-8')))
            data = np.load(entry.disk/'data.npy', allow_pickle=False, mmap_mode='r')
            if data.shape != entry.shape or data.dtype != entry.dtype:
                raise ValueError('Run-local cache descriptor/header mismatch')
            return Form(data, **store.read_metadata(entry, mmap=True))
        # File readers are metadata-only; other non-streaming readers retain
        # their existing full-mode admission before any materialization.
        return store[name]


def export_outputs(ctx):
    names = ctx.manifest.get('runtime', {}).get('exchange_outputs', [])
    if not names:
        return {}
    if not isinstance(names, list) or any(not isinstance(name, str) or not name for name in names):
        raise ValueError('runtime.exchange_outputs must contain artifact names')
    root = no_symlinks(ctx.out_dir/'exchange')
    root.mkdir(parents=True, exist_ok=True)
    config = ctx.memory.config if ctx.memory else None
    chunk = min(config.io_buffer_bytes, max(1, config.budget_bytes//16)) if config else 65536
    if ctx.memory:
        ctx.memory.store.ensure(chunk*4, 'stage_export_buffers')
    exported = {}
    for name in dict.fromkeys(names):
        value = _export_value(ctx, name)
        value.validate()
        temporary = root/('.partial-'+uuid.uuid4().hex[:16])
        temporary.mkdir(mode=0o700)
        allocated = 0
        def admit(count):
            nonlocal allocated
            count = int(count)
            if shutil.disk_usage(root).free < count:
                raise OSError('Insufficient disk space for stage exchange')
            if ctx.memory:
                from src.task.memory.config import DiskBudgetError
                store = ctx.memory.store
                with store.lock:
                    if config.disk_limit_bytes is not None and store.disk_bytes + store.transport_disk_bytes + count > config.disk_limit_bytes:
                        raise DiskBudgetError('Stage exchange exceeds the run disk quota')
                    store.transport_disk_bytes += count
            allocated += count
        try:
            wire = ExchangeWire(temporary, buffer_bytes=chunk, admit=admit)
            encoded = wire.encode(value)
            from src.core.contracts import describe_form
            contract = describe_form(value)
            packet = {'version': VERSION, 'value': encoded, 'contract': contract, 'audit': wire.audit}
            payload = json.dumps(packet, ensure_ascii=False, allow_nan=False).encode('utf-8')
            admit(len(payload))
            with wire.path('value.bpform').open('xb') as output:
                output.write(payload); output.flush(); os.fsync(output.fileno())
            final = root/uuid.uuid4().hex[:16]
            os.replace(temporary, final); sync_directory(root)
            files = [{'name': p.name, 'path': str(p), 'bytes': p.stat().st_size}
                     for p in sorted(final.iterdir())]
            exported[name] = {'path': str(final/'value.bpform'), 'files': files, 'contract': contract}
            ctx.event('exchange_exported', name=name, bytes=sum(item['bytes'] for item in files), path=exported[name]['path'])
        except BaseException:
            if ctx.memory:
                ctx.memory.store.transport_disk_bytes = max(0, ctx.memory.store.transport_disk_bytes-allocated)
            if temporary.exists():
                for item in temporary.iterdir():
                    no_symlinks(item).unlink()
                temporary.rmdir()
            raise
    aliases = ctx.manifest.get('runtime', {}).get('exchange_aliases', {})
    if not isinstance(aliases, dict) or any(not isinstance(key, str) or not isinstance(value, str)
                                          for key, value in aliases.items()):
        raise ValueError('runtime.exchange_aliases must map public names to expanded artifact names')
    for alias, actual in aliases.items():
        if actual in exported:
            if alias in exported and exported[alias] != exported[actual]:
                raise ValueError('Stage exchange alias conflicts with an explicit output')
            exported[alias] = exported[actual]
    atomic_json(ctx.out_dir/'exchange.json', exported)
    return exported


def _array_header(path):
    with open_file(path) as handle:
        version = np.lib.format.read_magic(handle)
        if version == (1, 0):
            shape, fortran, dtype = np.lib.format.read_array_header_1_0(handle)
        elif version == (2, 0):
            shape, fortran, dtype = np.lib.format.read_array_header_2_0(handle)
        else:
            raise ValueError('Unsupported stage array encoding')
        if dtype.hasobject or dtype.kind not in 'biufcSU':
            raise ValueError('Object or unsupported arrays cannot cross execution environments')
        size = math.prod(shape)*dtype.itemsize
        if handle.tell()+size != path.stat().st_size:
            raise ValueError('Stage array header and file size differ')
        return {'shape': shape, 'dtype': dtype, 'fortran': fortran, 'offset': handle.tell(), 'bytes': size}


def _packet(ctx, path):
    path = no_symlinks(path)
    wire = ExchangeWire(path.parent)
    wire.path(path.name)
    size = signature(path)[0]
    if ctx.memory:
        # JSON creates Python objects; admit a conservative parse expansion.
        ctx.memory.store.ensure(max(8192, size*8), 'stage_metadata_parse')
    with open_file(path) as handle:
        packet = json.load(handle)
    if packet.get('version') != VERSION or not isinstance(packet.get('value'), dict):
        raise ValueError('Unsupported execution exchange packet')
    arrays, files = {}, {}
    def inspect(node):
        if not isinstance(node, dict):
            return
        kind = node.get('type')
        if kind in ('array', 'exchange_file'):
            reference = wire.path(node['file'])
            files[reference] = signature(reference)
            if kind == 'array':
                arrays[reference] = _array_header(reference)
        elif kind == 'file_artifact':
            # Validate after portable paths are rebased and fingerprints regenerated.
            inspect(node['value'])
        elif kind in ('dict', 'tuple', 'list', 'set'):
            for child in node['items']:
                if kind == 'dict':
                    if not isinstance(child, list) or len(child) != 2:
                        raise ValueError('Invalid exchange dictionary item')
                    inspect(child[0]); inspect(child[1])
                else:
                    inspect(child)
        elif kind in ('form', 'labelencoder'):
            inspect(node['value'])
        elif kind not in ('path', 'float'):
            raise ValueError('Unknown exchange metadata tag')
    inspect(packet['value'])
    files[path] = signature(path)
    wire.allowed_files = set(files)
    return wire, packet, arrays, files


def register_source(ctx, name, path):
    """Register a portable artifact with the ordinary managed source machinery."""
    path = no_symlinks(path)
    wire, packet, arrays, files = _packet(ctx, path)
    kind = packet['value'].get('type')
    if kind not in ('form', 'file_artifact'):
        raise ValueError('Stage exchange must contain a Form or FileArtifact')
    data_path = header = None
    if kind == 'form':
        payload = packet['value'].get('value', {})
        if payload.get('type') != 'dict':
            raise ValueError('Invalid stage Form payload')
        matches = [v for k, v in payload['items'] if k == 'data']
        if len(matches) != 1 or not isinstance(matches[0], dict) or matches[0].get('type') != 'array':
            raise ValueError('Stage Form requires one numeric array payload')
        data_path = wire.path(matches[0]['file'])
        header = arrays[data_path]
    # Do not retain parsed labels/metadata for every pending stage input.
    del packet, wire

    def unchanged():
        if any(signature(file) != stamp for file, stamp in files.items()):
            raise ValueError('Stage exchange files changed after registration')

    total_arrays = sum(header['bytes'] for header in arrays.values())
    metadata_bytes = Path(path).stat().st_size*8 + 8192
    def loader():
        unchanged()
        if ctx.memory:
            ctx.memory.store.ensure(total_arrays+metadata_bytes, 'stage_full_mode_admission')
        current_wire, current_packet, _, _ = _packet(ctx, path)
        result = current_wire.decode(current_packet['value'], mmap=False)
        result.validate(); unchanged()
        return result

    if not ctx.memory:
        ctx[name] = loader()
        return
    probe = {'file_bytes': sum(stamp[0] for stamp in files.values()), 'dense_bytes': total_arrays+metadata_bytes}
    disk_loader = None
    if kind == 'form' and len(header['shape']) == 2 and header['dtype'].kind in 'biuf':
        probe.update(shape=list(header['shape']), dtype=str(header['dtype']), dense_bytes=header['bytes'],
                     preparation_bytes=header['bytes'])
        def disk_loader(writer, chunk):
            unchanged()
            ctx.memory.store.ensure(total_arrays-header['bytes']+metadata_bytes+chunk*2, 'stage_stream_metadata')
            current_wire, current_packet, _, _ = _packet(ctx, path)
            mapped = current_wire.decode(current_packet['value'], mmap=True)
            mapped.validate()
            metadata = {key: getattr(mapped, key) for key in ('dims', 'labels', 'info', 'axis_info')}
            width = max(1, chunk//max(1, header['dtype'].itemsize))
            if header['fortran']:
                for row in range(writer.shape[0]):
                    for col in range(0, writer.shape[1], width):
                        writer.write(row, col, mapped.data[row, col:col+width])
            else:
                with open_file(data_path) as source:
                    source.seek(header['offset'])
                    for row in range(writer.shape[0]):
                        for col in range(0, writer.shape[1], width):
                            count = min(width, writer.shape[1]-col)
                            values = np.fromfile(source, dtype=writer.dtype, count=count)
                            if values.size != count:
                                raise ValueError('Stage array was truncated')
                            writer.write(row, col, values)
            unchanged()
            return metadata
    ctx.forms.register_source(name, loader, Path(path), probe, disk_loader)
    if kind == 'file_artifact':
        ctx.forms.entry(name).kind = 'file'
    ctx.event('exchange_source_registered', name=name, path=str(path), streaming=disk_loader is not None)

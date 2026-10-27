"""Server-owned jobs, reached through SSH and a private Unix socket only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import time

from .protocol import Decoder, VERSION, transmit


def receive(sock, size):
    chunks = bytearray()
    while len(chunks) < size:
        block = sock.recv(min(size-len(chunks), 65536))
        if not block:
            raise ConnectionError('Remote control connection closed')
        chunks.extend(block)
    return bytes(chunks)


def send_message(sock, value):
    data = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
    sock.sendall(struct.pack('!Q', len(data)) + data)


def read_message(sock):
    size = struct.unpack('!Q', receive(sock, 8))[0]
    if size > 128 * 1024**2:
        raise ValueError('Control metadata exceeds 128 MiB; input data must stay in server files')
    return json.loads(receive(sock, size))


def socket_path(workspace):
    if not hasattr(os, 'getuid') or not hasattr(socket, 'AF_UNIX'):
        raise RuntimeError('The remote job service requires a Linux/Unix Python runtime')
    directory = Path(tempfile.gettempdir()) / f'biopipe-ssh-{os.getuid()}'
    directory.mkdir(mode=0o700, exist_ok=True)
    info = directory.lstat()
    if stat.S_ISLNK(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise RuntimeError('Remote control directory must be owned by this user with mode 0700')
    key = hashlib.sha256(str(Path(workspace).resolve()).encode()).hexdigest()[:24]
    return directory / (key + '.sock')


class RemoteService:
    def __init__(self, workspace, input_roots=None):
        from src.web.service import JobService, Settings
        from src.web.operator_catalog import catalog_from_descriptors
        from src.task.memory.config import MemoryConfig, AUTO_BUDGET_FRACTION
        workspace = Path(workspace).expanduser().resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        code = Path(__file__).resolve().parents[2]
        # Explicit interpreter selection must also select its command-line tools.
        os.environ['PATH'] = str(Path(sys.executable).parent) + os.pathsep + os.environ.get('PATH', '')
        self.service = JobService(Settings(workspace, workspace/'.studio', code/'frontend/dist',
                                          code_root=code, input_roots=input_roots or [Path('/')]),
                                  catalog_from_descriptors())
        self.memory = {'automatic_memory_budget_bytes': self.service.admission.capacity,
                       'automatic_memory_fraction': AUTO_BUDGET_FRACTION}
        from .transfers import TransferStore
        self.transfers = TransferStore(workspace/'.studio'/'transfers', resolve_input=self.transfer_path)
        self.transport_leases = {}
        # Generated checkpoints and verified upload groups belong to this
        # service even when external input roots were restricted by the owner.
        if workspace not in self.service.settings.input_roots:
            self.service.settings.input_roots.append(workspace)

    def transfer_path(self, value):
        from .transfers import no_symlinks
        no_symlinks((self.service.root/value).expanduser())
        return self.path(value)

    def graph_catalog(self, graph):
        return self.service.plugins.catalog_for(graph, self.service.base_catalog)

    def path(self, value):
        path = (self.service.root / value).expanduser().resolve()
        if not any(path.is_relative_to(root.resolve()) for root in self.service.settings.input_roots):
            raise ValueError('Path is outside the configured server data roots')
        return path

    def dispatch(self, method, params):
        for lease, expires in list(self.transport_leases.items()):
            if expires < time.monotonic():
                self.service.admission.release(lease)
                del self.transport_leases[lease]
        if method in ('transport_reserve', 'transport_release'):
            key = params['id']
            if not isinstance(key, str) or not __import__('re').fullmatch('transfer-[a-f0-9]{32}', key):
                raise ValueError('Invalid transfer allocation identity')
            if method == 'transport_release':
                self.service.admission.release(key)
                self.transport_leases.pop(key, None)
                return {'released': True}
            # Framing/decoded buffers are bounded by the transport implementation.
            reserved = self.service.admission.reserve(key, {'reserved_bytes': 6*1024**2, 'cpu_threads': 0, 'kind': 'transport'})
            if reserved:
                self.transport_leases[key] = time.monotonic() + 30
            return {'reserved': reserved}
        if method.startswith('transfer_'):
            params = dict(params)
            lease = params.pop('_transport_lease', None)
            if lease:
                if lease not in self.transport_leases:
                    ready = self.dispatch('transport_reserve', {'id': lease})
                    if not ready['reserved']:
                        raise ValueError('Transfer memory is unavailable; retry admission')
                self.transport_leases[lease] = time.monotonic() + 30
            return self.transfers.dispatch(method, params)
        from src.web.models import Graph
        from src.web.service import safe_json
        from src.web.graph import compile_graph, relative_manifest
        from src.web.contracts import analyze_graph
        from src.web.parameters import freeze_graph
        from src.web.routes import prepare_interface
        service = self.service
        if method == 'bootstrap':
            import platform, shutil
            from biopipe import __version__
            service.refresh_catalog()
            tools = sorted({tool for spec in service.catalog['operators'] + service.catalog['readers']
                            for tool in spec.get('resources', {}).get('external_tools', [])})
            return {'protocol_version': VERSION, 'version': __version__, 'system': platform.system().lower(),
                    'python': sys.executable, 'workspace': str(service.root), 'code_root': str(service.settings.code_root),
                    'catalog': service.catalog, 'history': service.history(), 'demo': service.demo,
                    'tools': {name: bool(shutil.which(name)) for name in tools},
                    'dependencies': service.dependencies.snapshot(), 'resources': service.resources(), **self.memory}
        if method == 'resources':
            return service.resources()
        if method == 'pin_compatibility':
            from src.web.execution_pins import validated_pins
            return validated_pins(service, params.get('pins', {}))
        if method == 'file_stat':
            values = params.get('paths', [])
            if not isinstance(values, list) or len(values) > 256:
                raise ValueError('Invalid file metadata request')
            result = []
            for value in values:
                path = self.transfer_path(str(self.path(params.get('base', '.')) / value))
                result.append({'path': str(path), 'exists': path.is_file(),
                               'bytes': path.stat().st_size if path.is_file() else None})
            return result
        if method == 'exchange':
            key = params['job_id']; service.require(key)
            path = service.jobs_dir / key / 'output' / 'exchange.json'
            if not path.is_file():
                raise ValueError('The stage has no committed exchange outputs')
            value = json.loads(path.read_text(encoding='utf-8'))
            return value
        if method == 'preview':
            return service.preview(params['job_id'], params['artifact_id'])
        if method == 'output_file':
            key = params['job_id']; kind = params['kind']
            if kind == 'artifact':
                path, _ = service.artifact(key, params['artifact_id'])
            elif kind == 'artifact_file':
                path = service.artifact_file(key, params['artifact_id'], params['role'])
            elif kind == 'figure':
                path = service.figure_file(key, params['index'])
            elif kind == 'export':
                path = service.export_file(key, params['index'])
            else:
                raise ValueError('Unknown output kind')
            return {'path': str(path), 'bytes': path.stat().st_size, 'name': path.name}
        if method == 'browse':
            folder = self.path(params.get('path') or '.')
            if not folder.is_dir():
                raise ValueError('Choose an existing server directory')
            offset = max(0, int(params.get('offset', 0)))
            entries = []
            with os.scandir(folder) as listing:
                for item in listing:
                    if item.name.startswith('.') and not params.get('hidden', False):
                        continue
                    try:
                        path = self.path(str(folder/item.name))
                        info = item.stat()
                        entries.append({'name': item.name, 'path': str(path), 'directory': item.is_dir(),
                                        'bytes': info.st_size, 'modified': info.st_mtime})
                    except (PermissionError, FileNotFoundError, ValueError):
                        continue
            entries.sort(key=lambda item: (not item['directory'], item['name'].lower()))
            return {'path': str(folder), 'parent': str(folder.parent), 'entries': entries[offset:offset+200],
                    'next_offset': offset+200 if offset+200 < len(entries) else None}
        if method == 'source':
            from biopipe.file_formats import reader_extensions, uncompressed_path
            path = self.path(params['path'])
            if not path.is_file():
                raise ValueError('Choose an existing server file')
            primary = uncompressed_path(path)
            candidates = [r for r in service.catalog['readers']
                          if any(path.name.lower().endswith(ext) for ext in reader_extensions(r))
                          and all(primary.with_suffix(s).exists() for s in r.get('requires_siblings', []))
                          and not any(primary.with_suffix(s).exists() for s in r.get('excludes_siblings', []))]
            if len(candidates) != 1:
                raise ValueError('No unique registered Reader matches this server file')
            reader = candidates[0]; settings = reader.get('file_input', {})
            return {'filename': path.name, 'reader': reader['id'], 'bytes': path.stat().st_size,
                    'source': {'path': str(path), 'dims': settings.get('dims', ['sample', 'feature']),
                               'labels': settings.get('labels', {'sample': 'auto', 'feature': 'builtin'}),
                               'args': reader.get('runtime_defaults', {})}}
        if method in ('validate', 'prepare', 'export', 'run'):
            graph = Graph.model_validate(params['graph'])
            if method == 'run':
                request_id = params['request_id']
                digest = hashlib.sha256(json.dumps(params['graph'], sort_keys=True).encode()).hexdigest()
                if not isinstance(request_id, str) or not __import__('re').fullmatch('[a-f0-9-]{32,36}', request_id):
                    raise ValueError('Invalid submission identity')
                # Reconnect/retry must return the original job, even if the SSH
                # response vanished after the process was spawned.
                for item in service.jobs_dir.glob('*/job.json'):
                    record = json.loads(item.read_text(encoding='utf-8'))
                    if record.get('graph', {}).get('runtime', {}).get('remote_request_id') == request_id:
                        if record['graph']['runtime'].get('remote_request_digest') != digest:
                            raise ValueError('Submission identity was already used with a different graph')
                        return service.details(record['id'])
                graph.runtime['remote_request_id'] = request_id
                graph.runtime['remote_request_digest'] = digest
                return service.launch(graph)
            catalog = self.graph_catalog(graph)
            if method == 'prepare':
                return prepare_interface(freeze_graph(service.plugins.pin(graph), catalog, service.root), catalog,
                                         service.root).model_dump(mode='json')
            manifest, order = compile_graph(graph, catalog, service.root,
                                            require_files=method == 'validate' and params.get('require_files', True), input_roots=service.settings.input_roots)
            if method == 'export':
                import yaml
                return {'yaml': yaml.safe_dump(relative_manifest(manifest, service.root/graph.base_dir, catalog),
                                               allow_unicode=True, sort_keys=False), 'order': order}
            return {'valid': True, 'order': order, 'contracts': analyze_graph(graph, catalog, service.root)}
        if method == 'history':
            return service.history()
        if method == 'console':
            key = params['job_id']; service.require(key)
            path = service.jobs_dir/key/'console.log'
            if not path.is_file():
                _, result = service.console_snapshot(key, service.details(key))
                return {'text': result['console'], 'offset': 0, 'done': True}
            with path.open('rb') as handle:
                handle.seek(max(0, int(params.get('offset', 0))))
                data = handle.read(64 * 1024)
                # Return bytes as base64 so chunk boundaries cannot split UTF-8.
                import base64
                return {'base64': base64.b64encode(data).decode(), 'offset': handle.tell(),
                        'done': not bool(handle.read(1))}
        if method == 'job':
            return service.details(params['job_id'])
        if method == 'cancel':
            return service.cancel(params['job_id'])
        if method == 'poll':
            key = params['job_id']; job = service.details(key)
            offsets = params.get('offsets', {}); result = {}; events = []; eof = True
            for path in service.event_paths(key):
                name = path.relative_to(service.jobs_dir/key).as_posix()
                start = max(0, int(offsets.get(name, 0)))
                with path.open('rb') as handle:
                    handle.seek(min(start, path.stat().st_size))
                    for _ in range(200):
                        position = handle.tell(); line = handle.readline()
                        if not line: break
                        if not line.endswith(b'\n'):
                            handle.seek(position); break
                        try: events.append(json.loads(line))
                        except (ValueError, UnicodeDecodeError): pass
                    result[name] = handle.tell()
                    eof = eof and not bool(handle.read(1))
            _, console = service.console_snapshot(key, job)
            job.pop('graph', None)
            return safe_json({'job': job, 'events': sorted(events, key=lambda e: e.get('time', '')),
                              'offsets': result, 'done': job['status'] not in ('running', 'queued', 'preparing', 'uploading') and job.get('logs_complete', True) and eof,
                              **(console or {})})
        raise ValueError('Unknown remote operation')


def rpc(workspace, request):
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(90)
        client.connect(str(socket_path(workspace)))
        send_message(client, request)
        return read_message(client)


def ensure_daemon(workspace):
    import fcntl
    address = socket_path(workspace)
    with address.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            response = rpc(workspace, {'method': 'bootstrap', 'params': {}})
            if not response.get('ok'):
                raise RuntimeError(response.get('error', 'Remote service is unavailable'))
            if response['value']['code_root'] != str(Path(__file__).resolve().parents[2]):
                raise RuntimeError('This workspace is served by a different BioPipe installation. Use its app directory or a separate workspace.')
            return
        except (ConnectionError, OSError):
            pass
        directory = Path(workspace)/'.studio/remote'
        directory.mkdir(parents=True, exist_ok=True)
        with (directory/'service.log').open('ab') as log:
            subprocess.Popen([sys.executable, '-m', 'biopipe.remote.server', '--serve', '--workspace', str(workspace)],
                             cwd=Path(__file__).resolve().parents[2], stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                             start_new_session=True)
        deadline = time.monotonic()+60
        while time.monotonic() < deadline:
            try:
                rpc(workspace, {'method': 'bootstrap', 'params': {}})
                return
            except (ConnectionError, OSError):
                time.sleep(.15)
        raise RuntimeError('Remote service did not start; inspect .studio/remote/service.log on the server')


def serve(workspace):
    address = socket_path(workspace)
    service = RemoteService(workspace)
    address.unlink(missing_ok=True)
    with socket.socket(socket.AF_UNIX) as listener:
        listener.bind(str(address)); os.chmod(address, 0o600)
        listener.listen(8); listener.settimeout(10)
        last_request = time.monotonic()
        try:
            while True:
                try: connection, _ = listener.accept()
                except socket.timeout:
                    if time.monotonic()-last_request > 300 and not service.service.processes:
                        break
                    continue
                last_request = time.monotonic()
                with connection:
                    connection.settimeout(90)
                    try:
                        request = read_message(connection)
                        value = service.dispatch(request['method'], request.get('params', {}))
                        response = {'ok': True, 'value': value}
                    except Exception as exc:
                        import traceback
                        traceback.print_exc()
                        response = {'ok': False, 'error': str(exc), 'node_id': getattr(exc, 'node_id', None)}
                    try: send_message(connection, response)
                    except (BrokenPipeError, ConnectionError, OSError): pass
        finally:
            address.unlink(missing_ok=True)
            service.service.shutdown()


class TerminalInput:
    """Unbuffered line input so select also observes already received lines."""
    def __init__(self):
        self.buffer = b''

    def line(self, deadline=None):
        import select
        while b'\n' not in self.buffer:
            timeout = None if deadline is None else max(0, deadline-time.monotonic())
            if not select.select([sys.stdin.fileno()], [], [], timeout)[0]:
                raise TimeoutError('SSH peer did not acknowledge the response')
            data = os.read(sys.stdin.fileno(), 65536)
            if not data: raise EOFError('SSH peer disconnected')
            self.buffer += data
        line, self.buffer = self.buffer.split(b'\n', 1)
        return line.decode('utf-8', errors='replace')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--serve', action='store_true')
    args = parser.parse_args()
    workspace = Path(args.workspace).expanduser().resolve()
    if args.serve:
        serve(workspace); return
    ensure_daemon(workspace)
    print('\nBIOPIPE_REMOTE_READY 1', flush=True)
    decoder = Decoder('Q')
    terminal = TerminalInput()
    def write(value):
        sys.stdout.write(value); sys.stdout.flush()
    while True:
        try: line = terminal.line()
        except EOFError: return
        try: request = decoder.feed(line)
        except ValueError: continue
        if decoder.ack: write(decoder.ack)
        if request is None: continue
        try: response = rpc(workspace, request)
        except Exception as exc: response = {'ok': False, 'error': str(exc)}
        response['id'] = request.get('id')
        try: transmit(response, 'R', write, terminal.line)
        except (EOFError, TimeoutError): return


if __name__ == '__main__':
    main()

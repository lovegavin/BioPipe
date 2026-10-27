"""Durable workflow coordinator; scientific work stays in admitted processes.

Each stage uses the ordinary JobService and its frozen parameter and memory
plan. SSH transports verified files; it never transports Python objects. A
route node is kept intact when partitioning the top-level DAG.
"""
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import threading
import time
import uuid

from biopipe.remote.client import RemoteError
from .admission import process_identity, process_alive
from .contracts import analyze_graph
from .execution_plan import ACTIVE, LOCAL, make_plan, target, target_key, settings, source_location, operator_nodes
from .graph import GraphError, compile_graph, project_path
from .models import Graph, GraphNode, Source, Position
from .parameters import freeze_graph, export_bundle
from .routes import prepare_interface, output_names, port_index
from .service import read_json, safe_json
from .storage import atomic_json, FileLock
from .transfers import TransferClient, TransferCancelled


def now():
    return datetime.now(timezone.utc).isoformat()


def execution_progress(job):
    """Count scientific steps, including nested routes, rather than SSH stages."""
    def count(node):
        if node.get('kind') == 'operator':
            return 1
        return sum(count(child) for child in (node.get('route') or {}).get('graph', {}).get('nodes', []))
    weights = {node['id']: count(node) for node in job['graph']['nodes']}
    children = {child['unit_id']: child for child in job['children']}
    completed, total, current = 0, 0, []
    for unit in job['execution_plan']['units']:
        size = sum(weights.get(node, 0) for node in unit['node_ids'])
        total += size
        child = children.get(unit['id'], {})
        progress = child.get('progress') or {}
        done = size if unit['id'] in job['completed_units'] else progress.get('completed', 0)
        completed += max(0, min(size, done))
        if child.get('status') == 'running' and progress.get('current'):
            current.append(str(progress['current']))
    result = {**job.get('progress', {}), 'completed': completed, 'total': total}
    if job['status'] == 'complete':
        result.update(completed=total, percent=100)
    elif 'bytes_total' not in result:
        result['percent'] = round(100 * completed / total, 1) if total else 0
        if current:
            result['current'] = ', '.join(current)
    return result


class ExecutionService:
    def __init__(self, service):
        self.service = service
        self.directory = service.directory / 'executions'
        self.directory.mkdir(exist_ok=True)
        self.cache = service.directory / 'exchange'
        self.cache.mkdir(exist_ok=True)
        self.lock = threading.RLock()
        self.stopping = threading.Event()
        self.threads, self.cancels = {}, {}
        self.progress_stamps = {}
        self.cancel_stamps = {}
        self.owner = process_identity()
        # Another Studio window may own a coordinator; never duplicate it.
        for path in self.directory.glob('exec-*/job.json'):
            with FileLock(path.with_suffix('.lock')):
                record = read_json(path)
                if record and record['status'] in ACTIVE and not process_alive(record.get('owner', {})):
                    record['owner'] = self.owner
                    record['status'] = 'preparing'
                    atomic_json(path, record)
                    self._start(record['id'])

    @staticmethod
    def applies(graph):
        value = graph.runtime.get('execution') or {}
        return bool(isinstance(value, dict) and any(k in value for k in ('mode', 'node_targets', 'file_locations'))
                    or any(n.source and n.source.location for n in graph.nodes)) and not graph.runtime.get('execution_parent_id')

    @staticmethod
    def owns(key):
        return isinstance(key, str) and key.startswith('exec-') and len(key) == 37 and key[5:].isalnum()

    def path(self, key):
        if not self.owns(key):
            raise KeyError('Unknown coordinated task')
        return self.directory / key

    def _read(self, key):
        with FileLock(self.path(key) / 'job.lock'):
            value = read_json(self.path(key) / 'job.json')
        if not value:
            raise KeyError('Unknown coordinated task')
        return value

    def _update(self, key, **values):
        with self.lock, FileLock(self.path(key) / 'job.lock'):
            value = self._read(key)
            value.update(deepcopy(values))
            atomic_json(self.path(key) / 'job.json', safe_json(value))
            return value

    def _event(self, key, event, **fields):
        with self.lock:
            row = {'time': now(), 'event': event, **fields}
            with self.events_path(key).open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
            if fields.get('message'):
                with self.console_path(key).open('a', encoding='utf-8') as stream:
                    stream.write(f"[{row['time']}] {fields['message']}\n")

    def events_path(self, key):
        return self.path(key) / 'events.jsonl'

    def console_path(self, key):
        return self.path(key) / 'console.log'

    def infos(self, *, connected=True, graph=None):
        catalog = self.service.catalog
        names = {tool for spec in catalog['operators'] + catalog['readers'] for tool in spec.get('resources', {}).get('external_tools', [])}
        system = platform.system().lower().replace('darwin', 'macos')
        result = [{'target': LOCAL, 'name': '本机', 'system': system, 'catalog': catalog,
                   'tools': {name: bool(shutil.which(name)) for name in names},
                   'resources': self.service.resources(), 'dependencies': self.service.dependencies.snapshot()}]
        for item in self.service.remotes.status() if self.service.remotes else []:
            if not item.get('info') or (connected and not item['connected']):
                continue
            info = deepcopy(item['info'])
            info.update(target={'kind': 'ssh', 'profile_id': item['profile']['id']}, name=item['profile']['name'])
            result.append(info)
        if graph is not None:
            from biopipe.pins import graphs
            from .execution_pins import validated_pins
            requested = {}
            for part in graphs(graph):
                for key, pin in part.plugin_lock.items():
                    if pin not in requested.setdefault(key, []):
                        requested[key].append(pin)
            for info in result:
                info['validated_pins'] = (validated_pins(self.service, requested) if info['target']['kind'] == 'local'
                                          else self.service.remotes.call(target_key(info['target']), 'pin_compatibility', {'pins': requested}))
        return result

    def catalog(self, graph):
        preferred = target_key(settings(graph))
        infos = self.infos(connected=False)
        infos.sort(key=lambda info: target_key(info['target']) == preferred)
        catalog = deepcopy(infos[0]['catalog'])
        for field in ('operators', 'readers'):
            merged = {}
            for info in infos:
                merged.update({spec['id']: deepcopy(spec) for spec in info['catalog'][field]})
            catalog[field] = list(merged.values())
        return catalog

    def prepare(self, graph):
        settings(graph)
        catalog = self.catalog(graph)
        graph = freeze_graph(graph, catalog, self.service.root)
        # Retain old pins; each selected host resolves them against its immutable
        # installed generations on stage submission. Defaults are already frozen.
        available = {s['id']: s.get('implementation') for s in catalog['operators'] + catalog['readers']}
        from biopipe.pins import graphs
        for part in graphs(graph):
            for node in part.nodes:
                if node.kind == 'operator' and available.get(node.operator):
                    part.plugin_lock.setdefault(node.operator, deepcopy(available[node.operator]))
        return prepare_interface(graph, catalog, self.service.root)

    def _stat(self, location, paths, base='.'):
        if target_key(location) == 'local':
            result = []
            for name in paths:
                path = project_path(self.service.root, name, base)
                if path.is_symlink():
                    raise GraphError('Input symlinks cannot be uploaded')
                result.append({'path': str(path), 'exists': path.is_file(), 'bytes': path.stat().st_size if path.is_file() else None})
            return result
        return self.service.remotes.call(target_key(location), 'file_stat', {'paths': paths, 'base': base})

    def _size(self, location, value, base):
        info = self._stat(location, [value], base)[0]
        if not info['exists']:
            raise ValueError('File does not exist')
        return info['bytes']

    def plan(self, graph):
        graph = self.prepare(graph)
        plan = make_plan(graph, self.infos(graph=graph), stat_file=self._size)
        self._validate_structure(graph)
        return plan

    def _validate_structure(self, graph):
        # Compile using virtual paths solely for topology/parameter/contracts.
        # Real inputs are checked on their owning host during staging, before
        # any scientific child is submitted.
        checked = graph.model_copy(deep=True)
        catalog = self.catalog(graph)
        specs = {s['id']: s for s in catalog['operators']}
        from biopipe.pins import graphs
        from biopipe.file_formats import primary_ext
        checked.base_dir = '.'
        for part in graphs(checked):
            part.base_dir = '.'
            for node in part.nodes:
                if node.source:
                    if not node.source.path:
                        raise GraphError('Choose an input file', node.id)
                    node.source.path = node.id + primary_ext(node.source.path)
                    node.source.location = None
                    for key in list(node.source.args):
                        field = next((r.get('parameters_schema', {}).get('properties', {}).get(key, {}) for r in catalog['readers']
                                      if primary_ext(node.source.path) in r.get('extensions', [])), {})
                        if field.get('x-biopipe-path'):
                            node.source.args[key] = 'reference.dat'
                elif node.kind == 'operator':
                    for key, field in specs[node.operator]['parameters_schema'].get('properties', {}).items():
                        if field.get('x-biopipe-path') and node.params.get(key):
                            node.params[key] = 'reference.dat'
        checked.runtime.pop('execution', None)
        return compile_graph(checked, catalog, self.service.root)

    def validate(self, graph, *, require_files=True):
        graph = self.prepare(graph)
        plan = self.plan(graph)
        _, order = self._validate_structure(graph)
        return {'valid': True, 'order': order, 'contracts': analyze_graph(graph, self.catalog(graph), self.service.root),
                'execution_plan': plan}

    def resources(self):
        result = []
        for info in self.infos():
            value = info.get('resources', {})
            if info['target']['kind'] == 'ssh':
                try:
                    value = self.service.remotes.call(target_key(info['target']), 'resources')
                except RemoteError:
                    continue
            result.append({'target': info['target'], 'name': info['name'], **value})
        return {'targets': result}

    def launch(self, graph):
        graph = self.prepare(graph)
        plan = self.plan(graph)
        key = 'exec-' + uuid.uuid4().hex
        folder = self.path(key); folder.mkdir()
        (folder / 'workflow.biopipe').write_bytes(export_bundle(graph))
        job = {'id': key, 'name': graph.name, 'status': 'preparing', 'created_at': now(), 'finished_at': None,
               'error': None, 'graph': graph.model_dump(mode='json'), 'execution_plan': plan, 'owner': self.owner,
               'children': [], 'completed_units': [], 'receipts': {}, 'logs_complete': False,
               'progress': {'phase': 'preparing', 'completed': 0, 'total': len(plan['units'])}}
        job['order'] = [node for unit in plan['units'] for node in unit['node_ids']]
        atomic_json(folder / 'job.json', job)
        self._event(key, 'execution_queued', message='Execution plan saved; preparing required files')
        self._start(key)
        return self.details(key)

    def _start(self, key):
        self.cancels[key] = threading.Event()
        if self._read(key).get('cancel_requested'):
            self.cancels[key].set()
        thread = self.threads[key] = threading.Thread(target=self._run, args=(key,), name='workflow-' + key, daemon=True)
        thread.start()

    def _check(self, key):
        if self.stopping.is_set():
            raise InterruptedError('Coordinator stopped; saved stages will resume on reopening')
        if self.cancels[key].is_set():
            raise TransferCancelled('Task cancelled')
        if time.monotonic() - self.cancel_stamps.get(key, -1) > .3:
            self.cancel_stamps[key] = time.monotonic()
            if self._read(key).get('cancel_requested'):
                self.cancels[key].set()
                raise TransferCancelled('Task cancelled')

    def _rpc(self, key, profile, method, params=None):
        while True:
            self._check(key)
            try:
                return self.service.remotes.call(profile, method, params)
            except RemoteError as exc:
                if str(exc) == 'Transfer memory is unavailable; retry admission':
                    self._update(key, status='queued', progress={**self._read(key)['progress'], 'phase': 'queued', 'current': 'Waiting for transfer memory'})
                    self.stopping.wait(.3)
                    continue
                if exc.code != 'remote_disconnected':
                    raise
                self._update(key, status='waiting_connection', progress={**self._read(key)['progress'], 'phase': 'waiting_connection'})
                if self.stopping.wait(.5):
                    self._check(key)

    def _client(self, key, profile):
        return TransferClient(lambda method, params=None: self._rpc(key, profile, method, params), self.cache / profile)

    def _progress(self, key, unit, progress):
        self._check(key)
        with self.lock, FileLock(self.path(key) / 'job.lock'):
            signature = (key, unit['id'], progress['phase'], progress.get('current'))
            stamp = time.monotonic()
            if stamp - self.progress_stamps.get(signature, -1) < .2 and progress.get('bytes_done') != progress.get('bytes_total'):
                return
            self.progress_stamps[signature] = stamp
            job = self._read(key)
            job['status'] = 'uploading' if progress['phase'] in ('uploading', 'downloading', 'hashing', 'verifying', 'resumed') else 'running'
            job['progress'] = {**progress, 'stage_id': unit['id'], 'completed': len(job['completed_units']), 'total': len(job['execution_plan']['units'])}
            atomic_json(self.path(key) / 'job.json', safe_json(job))

    @contextmanager
    def _transport_budget(self, key, unit, origin):
        ticket = 'transfer-' + uuid.uuid4().hex
        # Includes both decoded bytes and JSON/base64 framing in this process.
        size = 6 * 1024**2
        if size > self.service.admission.capacity:
            raise GraphError('Available host memory is too small for the bounded transfer buffers')
        allocation = {'reserved_bytes': size, 'cpu_threads': 0, 'kind': 'transport'}
        profiles = {target_key(value) for value in (origin, unit['target']) if value['kind'] == 'ssh'}
        reserved = []
        try:
            while not self.service.admission.reserve(ticket, allocation):
                self._check(key)
                self._progress(key, unit, {'phase': 'queued', 'current': 'Waiting for transfer memory'})
                self.stopping.wait(.2)
            for profile in sorted(profiles):
                while not self._rpc(key, profile, 'transport_reserve', {'id': ticket, 'bytes': size})['reserved']:
                    self._progress(key, unit, {'phase': 'queued', 'current': 'Waiting for server transfer memory'})
                    self.stopping.wait(.2)
                reserved.append(profile)
            yield ticket
        finally:
            self.service.admission.release(ticket)
            for profile in reserved:
                try:
                    self.service.remotes.call(profile, 'transport_release', {'id': ticket})
                except RemoteError:
                    pass  # Short server leases expire after a disconnected client.

    def _move(self, key, unit, files, origin):
        if target_key(origin) == target_key(unit['target']):
            return {item['name']: item['path'] for item in files}
        with self._transport_budget(key, unit, origin) as ticket:
            return self._move_reserved(key, unit, files, origin, ticket)

    def _move_reserved(self, key, unit, files, origin, ticket):
        """Materialize one adjacent file group on the destination, preserving names."""
        destination = unit['target']
        if target_key(origin) == target_key(destination):
            return {item['name']: item['path'] for item in files}
        progress = lambda state: self._progress(key, unit, state)
        cancel = lambda: self.stopping.is_set() or self.cancels[key].is_set()
        local_files = files
        if origin['kind'] == 'ssh':
            client = self._client(key, target_key(origin))
            original_rpc = client.rpc
            client.rpc = lambda method, params=None: original_rpc(method, {**(params or {}), '_transport_lease': ticket})
            # The directory depends on remote identities, not mutable basenames.
            descriptions = [client.describe(item['path'], cancel=cancel, progress=progress) for item in files]
            group = hashlib.sha256(json.dumps([(item['name'], ref['sha256']) for item, ref in zip(files, descriptions)], sort_keys=True).encode()).hexdigest()[:24]
            local_files = []
            for item, reference in zip(files, descriptions):
                downloaded = client.download(reference, client.cache_dir / group / item['name'], cancel=cancel, progress=progress)
                local_files.append({'name': item['name'], 'path': downloaded['path'], 'bytes': downloaded['bytes']})
        if destination['kind'] == 'local':
            return {item['name']: item['path'] for item in local_files}
        client = self._client(key, target_key(destination))
        original_rpc = client.rpc
        client.rpc = lambda method, params=None: original_rpc(method, {**(params or {}), '_transport_lease': ticket})
        references = []
        for item in local_files:
            uploaded = client.upload(item['path'], cancel=cancel, progress=progress, name=item['name'])
            references.append({'name': item['name'], 'reference': uploaded})
        result = client.materialize(references, cancel=cancel, progress=progress)
        self._event(key, 'transfer_group_ready', message=f"{unit['id']}: verified file group ready", files=len(files), target=destination)
        return result['paths']

    def _file_group(self, location, value, base, reader=None):
        info = self._stat(location, [value], base)[0]
        if not info['exists']:
            raise GraphError(f"Missing input file: {value}")
        path_type = Path if location['kind'] == 'local' else PurePosixPath
        path = path_type(info['path'].replace('\\', '/'))
        files = [{'name': path.name, **info}]
        from biopipe.file_formats import uncompressed_path
        # Companions are descriptor-driven, with conventional optional indexes.
        # No directory is recursively uploaded.
        root = uncompressed_path(path)
        required = [root.with_suffix(ext).name for ext in (reader or {}).get('requires_siblings', [])]
        groups = (reader or {}).get('file_input', {}).get('companions', [])
        optional = [path.name + ext for ext in ('.fai', '.gzi', '.tbi', '.csi', '.bai', '.amb', '.ann', '.bwt', '.pac', '.sa')]
        names = list(dict.fromkeys(required + [name for group in groups for name in group] + optional))
        if names:
            entries = {name: row for name, row in zip(names, self._stat(location, names, str(path.parent)))}
            for name in required:
                if not entries[name]['exists']:
                    raise GraphError(f"Missing companion: {name}")
            for group in groups:
                present = [name for name in group if entries[name]['exists']]
                if len(present) != 1:
                    raise GraphError('Choose exactly one companion: ' + ' / '.join(group))
            files.extend({'name': name, **row} for name, row in entries.items() if row['exists'])
        return files

    def _stage_paths(self, key, unit, graph, catalog, original_config):
        config = settings(graph)
        specs = {spec['id']: spec for spec in catalog['operators']}
        for node in graph.nodes:
            self._check(key)
            if node.source and node.id not in graph.runtime.get('exchange_inputs', []):
                location = source_location(node, original_config)
                from biopipe.file_formats import primary_ext
                readers = [r for r in catalog['readers'] if primary_ext(node.source.path) in r.get('extensions', [])]
                # Resolve ambiguous companion formats using the owning host.
                reader = readers[0] if len(readers) == 1 else None
                if len(readers) > 1:
                    for candidate in readers:
                        try:
                            self._file_group(location, node.source.path, graph.base_dir, candidate)
                            if candidate.get('requires_siblings'):
                                reader = candidate; break
                        except GraphError:
                            pass
                    reader = reader or next((r for r in readers if not r.get('requires_siblings')), None)
                files = self._file_group(location, node.source.path, graph.base_dir, reader)
                paths = self._move(key, unit, files, location)
                source_base = str((Path if location['kind'] == 'local' else PurePosixPath)(files[0]['path']).parent)
                node.source.path = paths[files[0]['name']]
                fields = (reader or {}).get('parameters_schema', {}).get('properties', {})
                for name, field in fields.items():
                    if field.get('x-biopipe-path') and node.source.args.get(name):
                        location_key = f'{node.id}.source.args.{name}'
                        where = config['file_locations'].get(location_key, location)
                        reference_base = graph.base_dir if location_key in config['file_locations'] else source_base
                        refs = self._file_group(where, node.source.args[name], reference_base)
                        node.source.args[name] = self._move(key, unit, refs, where)[refs[0]['name']]
                from .models import ExecutionTarget
                node.source.location = ExecutionTarget.model_validate(unit['target'])
            elif node.kind == 'operator':
                for name, field in specs[node.operator]['parameters_schema'].get('properties', {}).items():
                    if field.get('x-biopipe-path') and node.params.get(name):
                        where = config['file_locations'].get(f'{node.id}.params.{name}', target(original_config))
                        refs = self._file_group(where, node.params[name], graph.base_dir)
                        node.params[name] = self._move(key, unit, refs, where)[refs[0]['name']]
            elif node.kind == 'route' and node.route:
                # Route sources are interface placeholders, never input files.
                nested = node.route.graph
                placeholders = [n for n in nested.nodes if n.source]
                nested.nodes = [n for n in nested.nodes if not n.source]
                self._stage_paths(key, unit, nested, catalog, settings(nested) if nested.runtime.get('execution') else original_config)
                nested.nodes = placeholders + nested.nodes

    def _child(self, key, unit):
        return next((c for c in self._read(key)['children'] if c['unit_id'] == unit['id']), None)

    def _child_details(self, key, child):
        if child['target']['kind'] == 'local':
            return self.service.details(child['id'])
        return self._rpc(key, target_key(child['target']), 'job', {'job_id': child['id']})

    def _packet(self, key, child, name):
        if child['target']['kind'] == 'local':
            value = read_json(self.service.jobs_dir / child['id'] / 'output' / 'exchange.json', {})
        else:
            value = self._rpc(key, target_key(child['target']), 'exchange', {'job_id': child['id']})
        # export_outputs publishes only after every payload is ready.
        mapping = value
        if name not in mapping:
            raise GraphError(f"Stage did not publish boundary output {name}")
        return mapping[name]

    def _stage_graph(self, key, unit, graph, plan):
        catalog = self.catalog(graph)
        specs = {s['id']: s for s in catalog['operators']}
        nodes = {n.id: n for n in graph.nodes}
        owners = {node: candidate for candidate in plan['units'] for node in candidate['node_ids']}
        selected = set(unit['node_ids'])
        stage = graph.model_copy(deep=True)
        stage.interface = None
        stage.nodes = [n for n in stage.nodes if n.id in selected]
        stage.edges = []
        stage.runtime['exchange_inputs'] = []
        stage.runtime['exchange_contracts'] = {}
        if isinstance(stage.runtime.get('execution'), dict):
            stage.runtime['execution']['node_targets'] = {k: v for k, v in stage.runtime['execution'].get('node_targets', {}).items() if k in selected}
        replacements, added = {}, set()
        for edge in graph.edges:
            if edge.target not in selected:
                continue
            edge = edge.model_copy(deep=True)
            if edge.source not in selected:
                node = nodes[edge.source]
                if node.kind == 'source':
                    if node.id not in added:
                        stage.nodes.insert(0, node.model_copy(deep=True)); added.add(node.id)
                else:
                    output = output_names(node, specs)[port_index(edge.sourceHandle)]
                    alias = 'handoff_' + hashlib.sha256((node.id + '\0' + output).encode()).hexdigest()[:16]
                    if alias not in added:
                        producer = owners[node.id]
                        child = self._child(key, producer)
                        if not child:
                            raise GraphError('Dependency stage is not ready')
                        packet = self._packet(key, child, output)
                        paths = self._move(key, unit, packet['files'], child['target'])
                        basename = Path(packet['path'].replace('\\', '/')).name
                        contract = packet['contract']
                        stage.nodes.insert(0, GraphNode(id=alias, kind='source', position=Position(x=0, y=0),
                                                       source=Source(path=paths[basename], dims=contract.get('dims') or ['file'], labels={})))
                        stage.runtime['exchange_inputs'].append(alias)
                        stage.runtime['exchange_contracts'][alias] = contract
                        added.add(alias); replacements[output] = alias
                    edge.source, edge.sourceHandle = alias, 'out'
            stage.edges.append(edge)
        from .references import remap_params
        for node in stage.nodes:
            if node.kind == 'operator':
                node.params = remap_params(node.operator, node.params, replacements)
        outgoing = {output_names(nodes[e.source], specs)[port_index(e.sourceHandle)] for e in graph.edges
                    if e.source in selected and e.target not in selected}
        # Keep only names that exist in this stage; boundary outputs cannot be
        # released at last use before their portable checkpoint is written.
        known = {name for n in stage.nodes for name in output_names(n, specs)}
        stage.memory['keep'] = sorted((set(graph.memory.get('keep', [])) & known) | outgoing)
        stage.runtime['exchange_outputs'] = sorted(outgoing)
        self._stage_paths(key, unit, stage, catalog, settings(graph))
        used = {n.operator for node in stage.nodes for n in operator_nodes(node)}
        from biopipe.file_formats import primary_ext
        for node in stage.nodes:
            if node.source:
                used.update(r['id'] for r in catalog['readers'] if primary_ext(node.source.path) in r.get('extensions', []))
        stage.plugin_lock = {name: pin for name, pin in stage.plugin_lock.items() if name in used}
        stage.base_dir = '.'
        config = settings(graph)
        # The destination service is already selected. Prevent a recursive SSH
        # submission and carry the user's concurrency share into host admission.
        stage.runtime['execution'] = {'kind': 'local', 'max_parallel_tasks': config.get('max_parallel_tasks', 2)}
        stage.runtime['execution_parent_id'] = key
        return stage

    def _stage(self, key, unit, graph, plan):
        self._check(key)
        child = self._child(key, unit)
        if not child:
            folder = self.path(key) / unit['id']; folder.mkdir(exist_ok=True)
            saved = read_json(folder / 'graph.json')
            stage = Graph.model_validate(saved) if saved else self._stage_graph(key, unit, graph, plan)
            atomic_json(folder / 'graph.json', stage.model_dump(mode='json'))
            from .routes import expand_routes
            _, owners = expand_routes(stage, self.catalog(graph))
            atomic_json(folder / 'owners.json', owners)
            if unit['target']['kind'] == 'local':
                # Reconcile an interrupted response before starting a new worker.
                prior = next((r for r in self.service.jobs.values() if r.get('graph', {}).get('runtime', {}).get('execution_unit_id') == key + unit['id']), None)
                stage.runtime['execution_unit_id'] = key + unit['id']
                result = self.service.details(prior['id']) if prior else self.service.launch(stage)
            else:
                request_id = hashlib.sha256((key + unit['id']).encode()).hexdigest()[:32]
                result = self._rpc(key, target_key(unit['target']), 'run', {'graph': stage.model_dump(mode='json'), 'request_id': request_id})
            child = {'unit_id': unit['id'], 'id': result['id'], 'target': unit['target'], 'status': result['status']}
            with self.lock, FileLock(self.path(key) / 'job.lock'):
                record = self._read(key); record['children'].append(child)
                atomic_json(self.path(key) / 'job.json', safe_json(record))
            self._event(key, 'stage_submitted', message=f"{unit['id']} submitted", child=child)
        offsets = read_json(self.path(key) / unit['id'] / 'offsets.json', {})
        while True:
            self._check(key)
            result = self._child_details(key, child)
            drained = self._collect_logs(key, unit, child, offsets)
            with FileLock(self.path(key) / 'job.lock'):
                atomic_json(self.path(key) / unit['id'] / 'result.json', safe_json(result))
            with self.lock, FileLock(self.path(key) / 'job.lock'):
                record = self._read(key)
                for entry in record['children']:
                    if entry['unit_id'] == unit['id']:
                        entry.update(status=result['status'], allocation=result.get('allocation'), progress=result.get('progress'))
                record['status'] = 'running' if any(c['status'] == 'running' for c in record['children']) else result['status']
                if record['status'] not in ACTIVE:
                    record['status'] = 'running'
                record['progress'] = {'phase': record['status'], 'completed': len(record['completed_units']), 'total': len(plan['units']), 'stage_id': unit['id']}
                atomic_json(self.path(key) / 'job.json', safe_json(record))
            if result['status'] not in ACTIVE and result.get('logs_complete', True) and drained:
                if result['status'] != 'complete':
                    raise GraphError(result.get('error') or f"{unit['id']}: {result['status']}")
                with self.lock, FileLock(self.path(key) / 'job.lock'):
                    record = self._read(key)
                    if unit['id'] not in record['completed_units']:
                        record['completed_units'].append(unit['id'])
                    atomic_json(self.path(key) / 'job.json', safe_json(record))
                self._event(key, 'stage_completed', message=f"{unit['id']} completed")
                return
            self.stopping.wait(.4)

    def _collect_logs(self, key, unit, child, offsets):
        folder = self.path(key) / unit['id']; folder.mkdir(exist_ok=True)
        drained = True
        if child['target']['kind'] == 'ssh':
            value = self._rpc(key, target_key(child['target']), 'poll', {'job_id': child['id'], 'offsets': offsets.get('events', {})})
            events = value['events']; offsets['events'] = value['offsets']
            drained = value.get('done', False)
            console = self._rpc(key, target_key(child['target']), 'console', {'job_id': child['id'], 'offset': offsets.get('console', 0)})
            import base64
            data = base64.b64decode(console['base64']) if 'base64' in console else console.get('text', '').encode()
            if data and (console.get('offset', 0) or not offsets.get('fallback_console')):
                with (folder / 'console.log').open('ab') as out:
                    out.write(data)
                with self.console_path(key).open('ab') as out:
                    out.write(f"\n[{unit['id']}]\n".encode() + data)
                offsets['fallback_console'] = True
            offsets['console'] = console.get('offset', 0)
            drained = drained and console.get('done', True)
        else:
            events = []
            for path in self.service.event_paths(child['id']):
                name = str(path)
                with path.open('rb') as stream:
                    stream.seek(offsets.get(name, 0))
                    for _ in range(200):
                        start = stream.tell(); line = stream.readline()
                        if not line or not line.endswith(b'\n'):
                            stream.seek(start); break
                        try: events.append(json.loads(line))
                        except ValueError: pass
                    offsets[name] = stream.tell()
                    drained = drained and not bool(stream.read(1))
            source = self.service.jobs_dir / child['id'] / 'console.log'
            if source.is_file():
                with source.open('rb') as stream:
                    stream.seek(offsets.get('console', 0))
                    data = stream.read(65536)
                    offsets['console'] = stream.tell()
                    drained = drained and not bool(stream.read(1))
                if data:
                    with (folder / 'console.log').open('ab') as out:
                        out.write(data)
                    with self.console_path(key).open('ab') as out:
                        out.write(f"\n[{unit['id']}]\n".encode() + data)
        owners = read_json(folder / 'owners.json', {})
        previous_result = read_json(folder / 'result.json', {})
        # The submitted child order is immutable, even while its status changes.
        if not previous_result.get('order'):
            previous_result = self._child_details(key, child)
        order = previous_result.get('order', [])
        for event in events:
            if event.get('event') in ('step_started', 'step_plan', 'step_finished'):
                index = int(event.get('index', 0)) - 1
                if 0 <= index < len(order):
                    owner = owners.get(order[index], order[index])
                    event.update(node_id=owner, node_finished=not any(owners.get(name, name) == owner for name in order[index+1:]))
            self._event(key, event.pop('event', 'stage_event'), **{**event, 'stage_id': unit['id']})
        atomic_json(folder / 'offsets.json', offsets)
        return drained

    def _run(self, key):
        try:
            job = self._read(key); graph = Graph.model_validate(job['graph']); plan = job['execution_plan']
            pending = {unit['id']: unit for unit in plan['units'] if unit['id'] not in job['completed_units']}
            parallel = min(len(plan['units']), settings(graph).get('max_parallel_tasks', 2))
            with ThreadPoolExecutor(max_workers=max(1, parallel), thread_name_prefix='stage') as pool:
                running = {}
                while pending or running:
                    self._check(key)
                    complete = set(self._read(key)['completed_units'])
                    for uid, unit in list(pending.items()):
                        if len(running) >= parallel:
                            break
                        if set(unit['depends_on']) <= complete:
                            running[pool.submit(self._stage, key, unit, graph, plan)] = uid
                            del pending[uid]
                    if not running:
                        raise GraphError('No runnable stage; dependency state is inconsistent')
                    done, _ = wait(running, timeout=.3, return_when=FIRST_COMPLETED)
                    for future in done:
                        del running[future]
                        try:
                            future.result()
                        except Exception:
                            self.cancels[key].set()
                            raise
            self._update(key, status='complete', finished_at=now(), logs_complete=True,
                         progress={'phase': 'complete', 'completed': len(plan['units']), 'total': len(plan['units']), 'percent': 100})
            self._event(key, 'execution_finished', message='All stages completed')
        except InterruptedError:
            self._update(key, owner={}, status='preparing', logs_complete=False)
        except Exception as exc:
            cancelled = self._read(key).get('cancel_requested', False)
            while not self._cancel_children(key):
                self._update(key, status='waiting_connection', cancel_pending=True,
                             progress={**self._read(key)['progress'], 'phase': 'waiting_connection', 'current': 'Cancellation awaits server connection'})
                if self.stopping.wait(.5):
                    self._update(key, owner={})
                    return
            self._update(key, status='cancelled' if cancelled else 'failed', error=None if cancelled else str(exc), finished_at=now(), logs_complete=True)
            self._event(key, 'execution_failed', message=str(exc))

    def _cancel_children(self, key):
        acknowledged = True
        for child in self._read(key)['children']:
            if child.get('status') not in ACTIVE:
                continue
            try:
                if child['target']['kind'] == 'local':
                    result = self.service.cancel(child['id'])
                else:
                    result = self.service.remotes.call(target_key(child['target']), 'cancel', {'job_id': child['id']})
                with self.lock, FileLock(self.path(key) / 'job.lock'):
                    record = self._read(key)
                    for entry in record['children']:
                        if entry['id'] == child['id']:
                            entry['status'] = result['status']
                    atomic_json(self.path(key) / 'job.json', record)
            except (RemoteError, KeyError) as exc:
                acknowledged = False
                if not self._read(key).get('cancel_pending'):
                    self._event(key, 'cancel_pending', message='Server cancellation is pending reconnection: ' + str(exc), child=child)
                    self._update(key, cancel_pending=True)
        if acknowledged and self._read(key).get('cancel_pending'):
            self._update(key, cancel_pending=False)
        return acknowledged

    def details(self, key):
        job = self._read(key)
        job['progress'] = execution_progress(job)
        # Details are a durable snapshot, so an offline server never erases a
        # finished task or blocks the task list. Live stage polling updates it.
        path = self.console_path(key)
        job['console'] = ''
        if path.is_file():
            with path.open('rb') as stream:
                stream.seek(max(0, path.stat().st_size - 65536))
                job['console'] = stream.read(65536).decode('utf-8', errors='replace')
        steps, artifacts, host_reports = [], [], []
        spills = {'planned': 0, 'emergency': 0, 'final': 0, 'correction': 0}
        for child in job['children']:
            with FileLock(self.path(key) / 'job.lock'):
                result = read_json(self.path(key) / child['unit_id'] / 'result.json', {})
            for index, step in enumerate((result.get('summary') or {}).get('steps', [])):
                steps.append({**step, 'stage_id': child['unit_id'], 'child_index': index})
            report = result.get('report') or {}
            if report:
                host_reports.append({'target': child['target'], 'stage_id': child['unit_id'], **{k: v for k, v in report.items() if k != 'artifacts'}})
            for artifact in report.get('artifacts', []):
                artifacts.append({**artifact, 'stage_id': child['unit_id'], 'child_artifact_id': artifact['artifact_id'],
                                  'artifact_id': child['unit_id'] + '-' + artifact['artifact_id']})
            for name, count in (result.get('spill_counts') or {}).items():
                spills[name] = spills.get(name, 0) + count
        job['summary'] = {'status': job['status'], 'steps': steps, 'n_steps': len(steps),
                          'total_elapsed': sum(step.get('elapsed', 0) for step in steps), 'error': job.get('error')}
        job['report'] = {'artifacts': artifacts, 'hosts': host_reports, 'status': job['status'],
                         'budget_bytes': max((r.get('budget_bytes', 0) for r in host_reports), default=0),
                         'managed_peak_bytes': max((r.get('managed_peak_bytes', 0) for r in host_reports), default=0),
                         'sampled_rss_peak_bytes': max((r.get('sampled_rss_peak_bytes', 0) for r in host_reports), default=0)}
        job['spill_counts'] = spills
        return safe_json(job)

    def _artifact_ref(self, key, artifact_id):
        job = self.details(key)
        match = next((a for a in job['report']['artifacts'] if a['artifact_id'] == artifact_id), None)
        if not match:
            raise KeyError('Unknown stage artifact')
        child = next(c for c in job['children'] if c['unit_id'] == match['stage_id'])
        return child, match

    def _fetch_output(self, key, child, kind, **fields):
        profile = target_key(child['target'])
        result = self.service.remotes.call(profile, 'output_file', {'job_id': child['id'], 'kind': kind, **fields})
        client = TransferClient(lambda method, params=None: self.service.remotes.call(profile, method, params), self.cache / profile)
        identity = hashlib.sha256(json.dumps([key, child['unit_id'], kind, fields], sort_keys=True).encode()).hexdigest()[:24]
        downloaded = client.download(result['path'], client.cache_dir / 'results' / identity / result['name'])
        return Path(downloaded['path'])

    def preview(self, key, artifact_id):
        child, match = self._artifact_ref(key, artifact_id)
        if child['target']['kind'] == 'local':
            result = self.service.preview(child['id'], match['child_artifact_id'])
        else:
            result = self.service.remotes.call(target_key(child['target']), 'preview', {'job_id': child['id'], 'artifact_id': match['child_artifact_id']})
        result['descriptor'] = match
        return result

    def artifact(self, key, artifact_id):
        child, match = self._artifact_ref(key, artifact_id)
        path = self.service.artifact(child['id'], match['child_artifact_id'])[0] if child['target']['kind'] == 'local' else self._fetch_output(key, child, 'artifact', artifact_id=match['child_artifact_id'])
        return path, match

    def artifact_file(self, key, artifact_id, role):
        child, match = self._artifact_ref(key, artifact_id)
        return self.service.artifact_file(child['id'], match['child_artifact_id'], role) if child['target']['kind'] == 'local' else self._fetch_output(key, child, 'artifact_file', artifact_id=match['child_artifact_id'], role=role)

    def _export_ref(self, key, index):
        job = self.details(key)
        if not 0 <= index < len(job['summary']['steps']):
            raise KeyError('Unknown stage report')
        step = job['summary']['steps'][index]
        child = next(c for c in job['children'] if c['unit_id'] == step['stage_id'])
        return child, step['child_index']

    def export_file(self, key, index):
        child, index = self._export_ref(key, index)
        return self.service.export_file(child['id'], index) if child['target']['kind'] == 'local' else self._fetch_output(key, child, 'export', index=index)

    def figure_file(self, key, index):
        child, index = self._export_ref(key, index)
        return self.service.figure_file(child['id'], index) if child['target']['kind'] == 'local' else self._fetch_output(key, child, 'figure', index=index)

    def history(self):
        return sorted([self.details(path.parent.name) for path in self.directory.glob('exec-*/job.json')],
                      key=lambda job: job['created_at'], reverse=True)

    def cancel(self, key):
        job = self._read(key)
        if job['status'] not in ACTIVE:
            return self.details(key)
        self._update(key, cancel_requested=True)
        if key in self.cancels:
            self.cancels[key].set()
        self._cancel_children(key)
        return self.details(key)

    def shutdown(self):
        self.stopping.set()
        for thread in self.threads.values():
            thread.join(timeout=3)

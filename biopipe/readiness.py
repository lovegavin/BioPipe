"""Route-scoped, read-only dependency readiness for the selected targets.

Registration never calls this service. A run can validate automatically, but
installing requirements is a separate explicit operation. No payloads are read
to decide which declarations a workflow needs.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import platform
import os
import threading

from .documents import CommandError
from .reader_selection import candidates


def semantic_graph(graph):
    value = graph.model_dump(mode='json') if hasattr(graph, 'model_dump') else deepcopy(graph)
    value.pop('name', None)
    value.pop('interface', None)
    for node in value.get('nodes', []):
        for key in ('position', 'title'):
            node.pop(key, None)
        if node.get('route'):
            node['route']['graph'] = semantic_graph(node['route']['graph'])
            node['route'].pop('name', None)
    value.get('runtime', {}).pop('submission_key', None)
    return value


def required_ids(graph, catalog, node_ids=None, *, include_sources=True):
    """Include direct Readers and nested route operators, never the full library."""
    selected = set(node_ids) if node_ids is not None else {node.id for node in graph.nodes}
    # A stage consumes the original source on its execution target.
    if include_sources:
        selected.update(edge.source for edge in graph.edges if edge.target in selected
                        and any(n.id == edge.source and n.kind == 'source' for n in graph.nodes))
    result = set()
    for node in graph.nodes:
        if node.id not in selected:
            continue
        if node.kind == 'operator':
            result.add(node.operator)
        elif node.kind == 'route' and node.route:
            # Nested source nodes are route interface placeholders.
            inner = [n.id for n in node.route.graph.nodes if n.kind != 'source']
            result.update(required_ids(node.route.graph, catalog, inner, include_sources=False))
        elif include_sources and node.kind == 'source' and node.source:
            result.update(d['id'] for d in candidates(catalog.get('readers', []), node.source.path, node.source.reader))
    return result


def required_scripts(graph, node_ids=None, prefix=''):
    selected = set(node_ids) if node_ids is not None else {node.id for node in graph.nodes}
    result = {}
    for node in graph.nodes:
        if node.id not in selected:
            continue
        if node.kind == 'script':
            result[prefix + node.id] = node.script
        elif node.kind == 'route' and node.route:
            result.update(required_scripts(node.route.graph, prefix=prefix + node.id + '/'))
    return result


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def scoped_pins(graph, ids):
    """A host must resolve only declarations it is actually going to execute."""
    from .pins import graphs
    result = graph.model_copy(deep=True)
    for part in graphs(result):
        part.plugin_lock = {key: pin for key, pin in part.plugin_lock.items() if key in ids}
    return result


def _local_input_metadata(graph):
    from .pins import graphs
    for part in graphs(graph):
        execution = part.runtime.get('execution') or {}
        if execution.get('kind') == 'ssh':
            return False
        if any(value.get('kind') == 'ssh' for value in execution.get('file_locations', {}).values()):
            return False
        if any(node.source and node.source.location and node.source.location.kind == 'ssh' for node in part.nodes):
            return False
    return True


def environment_identity(service, state, ids):
    """Stat named receipts and environment roots; never traverse packages or data."""
    from .remote.handshake import _stamp, runtime_identity
    descriptors = [item for item in state['descriptors'] if item['id'] in ids]
    paths = set(state.get('shared_paths', []))
    for item in descriptors:
        paths.update(item.get('execution', {}).get('paths', []))
    from .dependencies import find_tool
    tools = sorted({tool for item in descriptors for tool in item.get('resources', {}).get('external_tools', [])})
    tool_stamps = {tool: _stamp(path) if (path := find_tool(tool)) else None for tool in tools}
    named = {}
    r_receipts = {}
    for item in descriptors:
        name = item.get('resources', {}).get('environment')
        if name:
            from .environments import resolve
            path = resolve(name)
            named[name] = _stamp(path) if path else None
        r = item.get('resources', {}).get('r')
        if r is not None:
            from .r_runtime import RRuntime
            runtime = RRuntime(service.plugins.directory.parent / 'runtimes/r')
            r_receipts[item['id']] = _stamp(runtime.root / 'receipts' / (runtime.key(r) + '.json'))
    return {'runtime': runtime_identity(), 'path': os.environ.get('PATH', ''),
            'tools': tool_stamps, 'named_environments': named, 'r_receipts': r_receipts,
            'python': _stamp(service.plugins.python_for(state)),
            'targets': [[_stamp(service.plugins.directory / path),
                         _stamp(service.plugins.directory / path / 'biopipe-target.json')] for path in sorted(paths)]}


def inspect_declared_environment(service, ids, *, graph=None, scripts=None, repair=False):
    """Check on the target host, including historical pins and inline scripts."""
    from .platforms import supported_systems
    from .script_operators import inspect_script_environment
    state = service.plugins.snapshot(scoped_pins(graph, ids)) if graph is not None else service.plugins.state()
    current = service.plugins.state()
    descriptors = {item['id']: item for item in state['descriptors']}
    system = {'darwin': 'macos'}.get(platform.system().lower(), platform.system().lower())
    statuses = {}
    eligible = []
    for key in sorted(set(ids)):
        descriptor = descriptors.get(key)
        if descriptor is None:
            statuses[key] = {'id': key, 'status': 'unavailable', 'error': 'Pinned declaration is unavailable'}
        elif system not in supported_systems(descriptor):
            statuses[key] = {'id': key, 'status': 'unsupported', 'error': f'{key} does not support {system}'}
        else:
            eligible.append(key)
    identity = environment_identity(service, state, eligible)
    # Session successes survive parameter edits but not an explicitly replaced
    # interpreter/immutable dependency target. Installation does not run here.
    runtime_keys = {key: _digest(environment_identity(service, state, [key])) for key in eligible}
    previous = getattr(service, '_readiness_runtime_keys', {})
    if state['generation'] == current['generation']:
        service.dependencies.sync(state)
        with service.dependencies.lock:
            for key in eligible:
                if key in previous and previous[key] != runtime_keys[key] and key in service.dependencies.entries:
                    service.dependencies.entries[key].update(status='unchecked', error='')
        if eligible:
            statuses.update(inspect_ids(service, eligible, repair=repair))
        previous.update(runtime_keys)
        service._readiness_runtime_keys = previous
    elif eligible:
        inspected = service.dependencies._inspect(state, [descriptors[key] for key in eligible])
        if repair and any(value.get('status') != 'passed' for value in inspected.values()):
            raise ValueError('Pinned historical environments require explicit migration before repair')
        statuses.update(inspected)
    script_statuses = {}
    for key, snapshot in (scripts or {}).items():
        try:
            script_statuses[key] = inspect_script_environment(snapshot)
        except Exception as exc:
            script_statuses[key] = {'status': 'failed', 'error': str(exc)}
    return {'entries': statuses, 'scripts': script_statuses, 'system': system,
            'generation': state['generation'], 'environment': identity}


def inspect_ids(service, ids, *, repair=False):
    """Used locally and by the SSH daemon; never rewrites system Python."""
    ids = sorted(set(ids))
    snapshot = service.dependencies.check(ids=ids, repair=repair, repair_r=repair)
    entries = {entry['id']: entry for entry in snapshot['entries']}
    return {key: entries.get(key, {'id': key, 'status': 'unchecked', 'error': 'Declaration not checked'}) for key in ids}


class ReadinessService:
    def __init__(self, application):
        self.app = application
        self.lock = threading.RLock()
        self.records = {}

    def _input_stamps(self, graph, catalog):
        from .remote.handshake import _stamp
        from src.web.graph import input_path
        from src.web.source_paths import remote_profile
        records = []
        remote = remote_profile(graph)
        for node in graph.nodes:
            if node.kind != 'source' or not node.source:
                continue
            location = node.source.location
            if (location and location.kind == 'ssh') or (not location and remote):
                # Remote validations are deliberately never served by this cache.
                records.append([node.id, 'remote', node.source.path])
                continue
            records.append([node.id, _stamp(input_path(self.app.service.root, node.source.path, graph.base_dir,
                                                       self.app.service.settings.input_roots))])
            from .file_formats import uncompressed_path
            source = input_path(self.app.service.root, node.source.path, graph.base_dir,
                                self.app.service.settings.input_roots)
            for reader in candidates(catalog.get('readers', []), node.source.path, node.source.reader):
                for suffix in reader.get('requires_siblings', []) + reader.get('excludes_siblings', []):
                    records.append([node.id, _stamp(uncompressed_path(source).with_suffix(suffix))])
        specs = {item['id']: item for item in catalog.get('operators', []) + catalog.get('readers', [])}
        def references(part, prefix=''):
            for node in part.nodes:
                if node.kind == 'route' and node.route:
                    references(node.route.graph, prefix + node.id + '/')
                elif node.kind == 'operator':
                    for name, field in specs.get(node.operator, {}).get('parameters_schema', {}).get('properties', {}).items():
                        if field.get('x-biopipe-path') and isinstance(node.params.get(name), str) and node.params[name]:
                            records.append([prefix + node.id, name, _stamp(input_path(self.app.service.root,
                                node.params[name], part.base_dir, self.app.service.settings.input_roots))])
        if not remote:
            references(graph)
        return records

    def validate(self, graph, structural, *, require_files=False, repair=False):
        service = self.app.service
        catalog = self.app.catalog_for(graph)
        plan = structural.get('execution_plan')
        groups, script_groups = {}, {}
        if plan:
            for unit in plan['units']:
                target = unit['target'].get('profile_id') if unit['target']['kind'] == 'ssh' else 'local'
                groups.setdefault(target, set()).update(required_ids(graph, catalog, unit['node_ids']))
                script_groups.setdefault(target, {}).update(required_scripts(graph, unit['node_ids']))
        else:
            from src.web.source_paths import remote_profile
            target = remote_profile(graph) or 'local'
            groups[target] = required_ids(graph, catalog)
            script_groups[target] = required_scripts(graph)
        local = 'local' in groups
        state = service.plugins.snapshot(scoped_pins(graph, groups['local'])) if local else None
        from .remote.handshake import _stamp
        import shutil
        script_tools = {tool for snapshot in script_groups.get('local', {}).values()
                        for tool in [{'r': 'Rscript', 'c': 'cc', 'cpp': 'c++'}.get(snapshot.get('language'))] if tool}
        local_inputs = _local_input_metadata(graph)
        identity = {'graph': semantic_graph(graph),
                    'inputs': self._input_stamps(graph, catalog) if set(groups) <= {'local'} and local_inputs else [],
                    'script_tools': {tool: _stamp(path) if (path := shutil.which(tool)) else None for tool in script_tools},
                    'generation': state['generation'] if state else None,
                    'environment': environment_identity(service, state, groups['local']) if state else None,
                    'require_files': require_files}
        fingerprint = _digest(identity)
        # A live RPC is mandatory for remote targets, even with a prior success.
        # DependencySession itself avoids repeating passed import probes.
        cacheable = set(groups) <= {'local'} and local_inputs and not repair
        if cacheable:
            with self.lock:
                cached = self.records.get(fingerprint)
                snapshot = service.dependencies.snapshot()
                statuses = {entry['id']: entry.get('status') for entry in snapshot['entries']}
                if cached and cached['status'] == 'ready' and all(statuses.get(key) == 'passed' for key in groups.get('local', [])):
                    return {**deepcopy(cached), 'cached': True}
        checked, blocked = {}, []
        for target, ids in groups.items():
            try:
                if target == 'local':
                    inspected = inspect_declared_environment(service, ids, graph=graph,
                                    scripts=script_groups.get(target), repair=repair)
                else:
                    inspected = service.remotes.call(target, 'validate_environment',
                                {'ids': sorted(ids), 'scripts': script_groups.get(target, {}),
                                 'graph': graph.model_dump(mode='json'), 'repair': repair})
                statuses = inspected['entries']
                checked[target] = {**statuses, **inspected.get('scripts', {})}
                for key in sorted(set(ids) | set(script_groups.get(target, {}))):
                    item = checked[target].get(key, {})
                    if item.get('status') != 'passed':
                        blocked.append({'target': target, 'id': key, 'status': item.get('status', 'unchecked'),
                                        'message': item.get('error') or 'Dependencies have not passed validation'})
            except Exception as exc:
                checked[target] = {}
                blocked.append({'target': target, 'id': None, 'status': 'unavailable', 'message': str(exc)})
        record = {'status': 'blocked' if blocked else 'ready', 'fingerprint': fingerprint,
                  'checked_at': datetime.now(timezone.utc).isoformat(), 'targets': checked,
                  'blocked': blocked, 'require_files': require_files,
                  'cached': False,
                  'policy': 'route-only; explicit preparation; no installation during validation'}
        with self.lock:
            self.records[fingerprint] = record
            while len(self.records) > 128:
                self.records.pop(next(iter(self.records)))
        return record

    @staticmethod
    def require_ready(result):
        readiness = result.get('readiness', {})
        if readiness.get('status') != 'ready':
            raise CommandError('environment_not_ready', 'The selected execution environment is not ready. Prepare dependencies explicitly, then validate again.',
                               409, readiness)

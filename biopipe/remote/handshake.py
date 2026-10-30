"""Document-only remote discovery and durable dependency readiness receipts.

The registry generation and its declared runtime paths are authoritative. No
operator source files or installed distributions are traversed here. Readiness
is invalidated by an entry's dependency/implementation fingerprint, interpreter
identity, environment directory metadata, or selected immutable target receipt.
Out-of-band edits inside existing packages are not detectable without probing;
administrators must request refresh_registry with verify_all=true after changing
such environments. That explicit operation revokes prior installer results.
"""
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import sysconfig
import threading
import uuid

from .protocol import VERSION


HANDSHAKE_VERSION = 1
OPERATOR_PROTOCOL = 3
CAPABILITIES = (
    'manifest_handshake', 'dependency_readiness', 'registry_refresh', 'jobs',
    'execution_pins', 'streaming', 'spill', 'upload',
)


class HandshakeError(ValueError):
    def __init__(self, message, *, code='handshake_incompatible'):
        super().__init__(message)
        self.code = code


def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def validate_request(params):
    for key, expected in (('version', HANDSHAKE_VERSION), ('protocol_version', VERSION),
                          ('operator_protocol', OPERATOR_PROTOCOL)):
        if type(params.get(key)) is not int or params[key] != expected:
            raise HandshakeError(f'Incompatible {key}: server requires {expected}')
    required = params.get('required_capabilities', [])
    if not isinstance(required, list) or any(not isinstance(item, str) for item in required):
        raise HandshakeError('required_capabilities must be a list of capability names')
    missing = sorted(set(required) - set(CAPABILITIES))
    if missing:
        raise HandshakeError('Server lacks required capabilities: ' + ', '.join(missing),
                             code='capability_missing')


def daemon_request():
    return {'method': 'handshake', 'params': {
        'version': HANDSHAKE_VERSION, 'protocol_version': VERSION,
        'operator_protocol': OPERATOR_PROTOCOL, 'required_capabilities': list(CAPABILITIES)}}


def validate_daemon_response(response):
    """A reachable incompatible daemon is never killed or silently replaced."""
    if not response.get('ok'):
        error = response.get('error', 'Remote service is unavailable')
        code = response.get('code', 'handshake_required')
        raise HandshakeError(error + '. Upgrade the installed server and restart it explicitly after active jobs finish.',
                             code=code)
    value = response.get('value', {})
    handshake = value.get('handshake', {})
    if not handshake:
        raise HandshakeError('This server requires a one-time handshake upgrade; restart it explicitly after active jobs finish.',
                             code='handshake_required')
    validate_request({'version': handshake.get('version'), 'protocol_version': value.get('protocol_version'),
                      'operator_protocol': handshake.get('operator_protocol')})
    missing = set(CAPABILITIES) - set(handshake.get('capabilities', []))
    if missing:
        raise HandshakeError('Installed server lacks required capabilities: ' + ', '.join(sorted(missing)),
                             code='capability_missing')
    return value


def _read(path):
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _stamp(path):
    """Inspect only the named runtime document/directory, never its contents."""
    path = Path(path)
    try:
        stat = path.stat()
        return [str(path.resolve()), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns]
    except OSError:
        return [str(path), None]


def _entries(document):
    values = document.get('entries', {})
    return {key: value for key, value in values.items() if isinstance(value, dict)} if isinstance(values, dict) else {}


def runtime_identity():
    paths = sysconfig.get_paths()
    return {
        'python': _stamp(sys.executable), 'version': sys.version,
        'prefix': str(Path(sys.prefix).resolve()),
        'base_prefix': str(Path(sys.base_prefix).resolve()),
        'environment': [_stamp(path) for path in sorted({paths[key] for key in ('purelib', 'platlib') if paths.get(key)})],
        'base_paths': os.environ.get('BIOPIPE_BASE_PATHS', ''),
    }


def _installation_key(entry):
    return digest({'r': entry.get('resources', {}).get('r'), **{key: entry.get(key) for key in
                   ('id', 'kind', 'version', 'entry_point', 'code_sha', 'dependencies', 'dependency_imports')}})


def installation_readiness(entries, results):
    """Attach successful installer probes to biopipe-ready.json without rechecking.

    Only the bundled base runtime may reuse these results. Workspace-specific
    code/dependency targets require their own probes and readiness receipt.
    """
    return {'version': 1, 'runtime': runtime_identity(),
            'entries': {entry['id']: {'declaration_key': _installation_key(entry),
                                      'status': results[entry['id']]['status'],
                                      'error': results[entry['id']].get('error', '')}
                        for entry in entries if entry['id'] in results and entry.get('resources', {}).get('r') is None}}


class ManifestHandshake:
    def __init__(self, service, memory):
        from src.web.storage import atomic_json
        self.service, self.memory = service, memory
        self.lock = threading.RLock()
        self.maintenance = {'running': False, 'error': None, 'result': None}
        self.maintenance_thread = None
        self.maintenance_verify_all = False
        self.directory = service.directory / 'remote'
        self.receipt_path = self.directory / 'readiness.json'
        identity_path = self.directory / 'server.json'
        identity = _read(identity_path)
        self.server_id = identity.get('server_id')
        if not isinstance(self.server_id, str) or not self.server_id:
            self.server_id = uuid.uuid4().hex
            atomic_json(identity_path, {'version': 1, 'server_id': self.server_id})
        self.runtime = runtime_identity()
        self.saved = _read(self.receipt_path)
        if self.saved.get('version') != 1:
            self.saved = {}
        self.installed = _read(Path(sys.prefix) / 'biopipe-ready.json').get('dependency_readiness', {})
        if not isinstance(self.installed, dict) or self.installed.get('version') != 1 or self.installed.get('runtime') != self.runtime:
            self.installed = {}
        self.installation_key = digest(self.installed)
        self.invalidated_installation = self.saved.get('invalidated_installation')
        if self.invalidated_installation == self.installation_key:
            self.installed = {}
        self.generation = None
        self.runtime_keys = {}
        self.catalog_digest = ''
        self.tools = {}
        self.path_environment = os.environ.get('PATH', '')
        if (self.saved.get('path_environment') == self.path_environment and self.saved.get('runtime') == self.runtime
                and isinstance(self.saved.get('tools'), dict)):
            for name, path in self.saved.get('tools', {}).items():
                if path is None or (isinstance(path, str) and Path(path).is_file() and os.access(path, os.X_OK)):
                    self.tools[name] = path
        self.saved_digest = ''
        self.sync()

    def _runtime_key(self, entry, state):
        execution = entry.get('execution', {})
        selected = execution.get('paths', []) if execution.get('mode') == 'isolated' else state.get('shared_paths', [])
        # Immutable targets carry a receipt. Its replacement or removal also
        # invalidates readiness when a path string happened to stay unchanged.
        targets = [self.service.plugins.directory / path for path in selected]
        return digest({'runtime': self.runtime, 'code_paths': state.get('code_paths', []),
                       'targets': [[str(path), path.is_dir(), _stamp(path / 'biopipe-target.json')] for path in targets],
                       'r': entry.get('r'), 'r_receipts': self._r_receipt(entry)})

    def _r_receipt(self, entry):
        if entry.get('r') is None:
            return None
        from biopipe.r_runtime import RRuntime
        runtime = RRuntime(self.service.plugins.directory.parent / 'runtimes/r')
        path = runtime.root / 'receipts' / (runtime.key(entry['r']) + '.json')
        receipt = _read(path)
        return [_stamp(path), Path(receipt.get('executable', '/missing')).is_file(),
                Path(receipt.get('library', '/missing')).is_dir()]

    def sync(self, *, force=False):
        from biopipe.plugins import require_current_state
        from src.web.storage import atomic_json
        manager = self.service.plugins
        state = json.loads(manager.registry.read_text(encoding='utf-8'))
        require_current_state(state)
        if state['generation'] == self.generation and not force:
            return
        state['_runtime_root'] = str(manager.directory.resolve())
        session = self.service.dependencies
        session.sync(state)
        saved_entries = _entries(self.saved)
        descriptors = {entry['id']: entry for entry in state['descriptors']}
        with session.lock:
            keys = {}
            for name, entry in session.entries.items():
                key = self._runtime_key(entry, state)
                keys[name] = key
                if name in self.runtime_keys and self.runtime_keys[name] != key:
                    entry.update(status='unchecked', error='')
                old = saved_entries.get(name, {})
                if (entry['status'] == 'unchecked' and old.get('fingerprint') == entry['fingerprint']
                        and old.get('runtime_key') == key and old.get('status') in ('passed', 'failed')):
                    entry.update(status=old['status'], error=old.get('error', ''))
                descriptor = descriptors[name]
                installed = _entries(self.installed).get(name, {})
                if (entry['status'] == 'unchecked' and descriptor.get('origin') == 'bundled'
                        and self.installed.get('runtime') == self.runtime
                        and not state.get('code_paths') and not state.get('shared_paths')
                        and entry.get('execution', {}).get('mode', 'shared') == 'shared'
                        and installed.get('declaration_key') == _installation_key(descriptor)
                        and installed.get('status') == 'passed'):
                    entry.update(status='passed', error='')
                entry['title'] = descriptor['title']
            self.runtime_keys = keys
        self.service.catalog.update(manager._catalog(state, self.service.base_catalog))
        self.generation = state['generation']
        self.catalog_digest = digest(self.service.catalog)
        atomic_json(self.service.directory / 'operators.json', self.service.catalog)

    def tool_snapshot(self, *, refresh=False):
        names = sorted({name for spec in self.service.catalog['operators'] + self.service.catalog['readers']
                        for name in spec.get('resources', {}).get('external_tools', [])})
        for name in names:
            if refresh or name not in self.tools:
                self.tools[name] = shutil.which(name)
        return {name: bool(self.tools[name]) for name in names}

    def persist(self):
        from src.web.storage import atomic_json
        snapshot = self.service.dependencies.snapshot()
        entries = {entry['id']: {**entry, 'runtime_key': self.runtime_keys[entry['id']]}
                   for entry in snapshot['entries'] if entry['status'] in ('passed', 'failed')}
        value = {'version': 1, 'runtime': self.runtime, 'entries': entries,
                 'invalidated_installation': self.invalidated_installation,
                 'path_environment': self.path_environment, 'tools': self.tools}
        key = digest(value)
        if key != self.saved_digest:
            atomic_json(self.receipt_path, value)
            self.saved, self.saved_digest = deepcopy(value), key
        return snapshot

    def response(self, params, *, legacy=False):
        if not legacy:
            validate_request(params)
        # The dependency checker releases this lock while probing; snapshots
        # stay coherent without waiting for a scan, import or installation.
        with self.lock, self.service.dependencies.lock:
            return self._response(params, legacy=legacy)

    def _response(self, params, *, legacy):
        self.sync()
        from biopipe import __version__
        tools = self.tool_snapshot()
        dependencies = self.persist()
        value = {
            'protocol_version': VERSION, 'version': __version__, 'system': platform.system().lower(),
            'python': sys.executable, 'workspace': str(self.service.root),
            'code_root': str(self.service.settings.code_root),
            'history': self.service.history(), 'demo': self.service.demo,
            'tools': tools, 'dependencies': dependencies, 'resources': self.service.resources(), **self.memory,
            'registry_refresh': deepcopy(self.maintenance),
            'handshake': {'version': HANDSHAKE_VERSION, 'server_id': self.server_id,
                          'catalog_digest': self.catalog_digest,
                          'dependency_revision': digest({'dependencies': dependencies, 'runtime_keys': self.runtime_keys}),
                          'capabilities': list(CAPABILITIES), 'operator_protocol': OPERATOR_PROTOCOL},
        }
        unchanged = not legacy and params.get('known_catalog_digest') == self.catalog_digest
        value['catalog_unchanged'] = unchanged
        if not unchanged:
            value['catalog'] = deepcopy(self.service.catalog)
        return value

    def refresh(self, params):
        verify_all = params.get('verify_all', False)
        if type(verify_all) is not bool:
            raise ValueError('verify_all must be a boolean')
        with self.lock:
            if self.maintenance['running'] and verify_all and not self.maintenance_verify_all:
                raise HandshakeError('A registry refresh is already running; wait before requesting full dependency verification.',
                                     code='maintenance_busy')
            if not self.maintenance['running']:
                self.maintenance = {'running': True, 'error': None, 'result': None}
                self.maintenance_verify_all = verify_all
                self.maintenance_thread = threading.Thread(target=self._refresh, args=(verify_all,),
                                                            name='biopipe-registry-refresh', daemon=True)
                self.maintenance_thread.start()
            return self.response(params, legacy=True)

    def _refresh(self, verify_all):
        from biopipe.plugins import process_context
        process_context.cancel = self.service.dependencies.cancel
        try:
            # Neither operation holds the handshake lock. Other desktops can
            # reconnect, read documents and follow jobs throughout maintenance.
            result = self.service.plugins.refresh()
            with self.lock, self.service.dependencies.lock:
                self.runtime = runtime_identity()
                if verify_all:
                    # This revocation is durable before the probe starts. A
                    # crash cannot reseed stale installer successes on restart.
                    self.invalidated_installation = self.installation_key
                    self.installed = {}
                    self.saved['entries'] = {}
                    for entry in self.service.dependencies.entries.values():
                        entry.update(status='unchecked', error='')
                self.sync(force=True)
                self.persist()
            self.service.dependencies.check(repair=False, repair_r=True)
            with self.lock:
                self.sync()
                self.tool_snapshot(refresh=True)
                self.persist()
                self.maintenance.update(running=False, result=result)
        except Exception as exc:
            with self.lock:
                self.maintenance.update(running=False, error=str(exc))
        finally:
            process_context.cancel = None

    @property
    def maintenance_running(self):
        with self.lock:
            return self.maintenance['running']

    def close(self):
        self.service.dependencies.cancel.set()
        if self.maintenance_thread is not None:
            self.maintenance_thread.join(timeout=5)

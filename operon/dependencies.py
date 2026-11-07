"""Session-scoped dependency readiness. Successful checks never expire by time.

Dependency installation publishes immutable directories, never changes the
running interpreter, and keeps shared versions constrained. Conflicts use a
private target and subprocess with the same Python executable.
Only dependency requirements, implementation code or execution paths invalidate
a successful check. Parameter and presentation edits do not.
"""
from copy import deepcopy
from hashlib import sha256
import importlib
from importlib import metadata
import json
import os
import subprocess
from pathlib import Path
import sys
import threading
from datetime import datetime, timezone

from packaging.requirements import Requirement
from operon.bytecode import io_path


def find_tool(name):
    """Resolve an external tool from PATH or any managed environment bin directory."""
    import shutil
    found = shutil.which(name)
    if found:
        return found
    from pathlib import Path
    import sys
    roots = [Path(sys.prefix) / 'bin', Path(sys.prefix) / 'Scripts']
    managed = Path(sys.prefix).resolve().parent
    roots.extend(sorted(managed.glob('env-*/bin')))
    roots.extend(sorted(managed.glob('env-*/Scripts')))
    for root in roots:
        candidate = root / name
        if candidate.is_file():
            import os
            if os.access(candidate, os.X_OK):
                return str(candidate)
    return None


def scope():
    """Temporarily restrict dependency checks to a declared id list.

    ``OPERON_DEPENDENCY_SCOPE`` (comma separated) wins; otherwise
    ``~/.config/operon/dependency_scope.json`` (list of ids) is used. An empty
    or missing scope means the full library.
    """
    import os
    value = os.environ.get('OPERON_DEPENDENCY_SCOPE', '').strip()
    if value:
        return {item.strip() for item in value.split(',') if item.strip()}
    path = Path(os.path.expanduser('~/.config/operon/dependency_scope.json'))
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            return {str(item) for item in data if str(item).strip()}
        except Exception:
            return set()
    return set()


def probe_environment(entry_id, environment, imports):
    """Check an operator that declares a dedicated interpreter environment."""
    from operon.environments import resolve
    python = resolve(environment)
    if python is None:
        return {'status': 'failed',
                'error': f'isolated environment {environment!r} is not installed; '
                         f'configure OPERON_ENV_{environment.upper()} with its Python executable '
                         'or use Linux server environment repair (docs/agent_environment_repair.md)'}
    names = imports or []
    script = ';'.join(f'import {name}' for name in names) or 'pass'
    result = subprocess.run([str(python), '-c', script], capture_output=True, text=True, timeout=300)
    if result.returncode:
        tail = (result.stderr or result.stdout).strip().splitlines()[-3:] or ['import failed']
        return {'status': 'failed', 'error': f'{environment}: ' + ' | '.join(tail),
                'environment_python': str(python), 'command': f'{python} -c {script!r}',
                'stderr': result.stderr[-2000:]}
    return {'status': 'passed', 'error': '', 'environment': str(python)}


def probe(entries):
    results = {}
    for entry in entries:
        tools = (entry.get('resources') or {}).get('external_tools') or []
        if tools:
            missing = [name for name in tools if find_tool(name) is None]
            results[entry['id']] = {'status': 'failed' if missing else 'passed',
                                    'error': ', '.join(f'{name}: not on PATH' for name in missing)}
            continue
        environment = (entry.get('resources') or {}).get('environment')
        if environment:
            results[entry['id']] = probe_environment(entry['id'], environment,
                                                     entry.get('dependency_imports', []))
            continue
        errors = []
        queue = list(entry.get('dependencies', []))
        seen = set()
        while queue:
            value = queue.pop()
            if value in seen:
                continue
            seen.add(value)
            req = Requirement(value)
            if req.marker and not req.marker.evaluate():
                continue
            try:
                version = metadata.version(req.name)
                if req.specifier and not req.specifier.contains(version, prereleases=True):
                    errors.append(f'{req}: installed {version}')
                # Validate enabled extras and transitive metadata without
                # importing arbitrary parsers in the HTTP process.
                for child in metadata.requires(req.name) or []:
                    dependency = Requirement(child)
                    if not dependency.marker or any(dependency.marker.evaluate({'extra': extra}) for extra in ['', *req.extras]):
                        dependency.marker = None
                        queue.append(str(dependency))
            except metadata.PackageNotFoundError:
                errors.append(f'{req}: not installed')
        if not errors:
            for name in entry.get('dependency_imports', []):
                try:
                    importlib.import_module(name)
                except Exception as exc:
                    errors.append(f'{name}: {type(exc).__name__}: {exc}')
        results[entry['id']] = {'status': 'failed' if errors else 'passed', 'error': '\n'.join(errors)}
    return results


def inspect_environment(python, entries, directory):
    from operon.plugins import run_process
    import tempfile
    directory = io_path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='dependency-', dir=directory) as tmp:
        request, response = Path(tmp) / 'request.json', Path(tmp) / 'response.json'
        request.write_text(json.dumps(entries), encoding='utf-8')
        run_process([python, '-m', 'operon.dependencies', request, response], timeout=180)
        return json.loads(response.read_text(encoding='utf-8'))


class DependencySession:
    def __init__(self, manager, *, inspector=inspect_environment):
        self.manager, self.inspector = manager, inspector
        self.entries = {}
        self.lock = threading.RLock()
        self.running = False
        self.cancel = threading.Event()
        self.log = manager.directory.parent / 'logs/dependencies.jsonl'

    def sync(self, state):
        from operon.plugins import active_descriptors
        with self.lock:
            current = {}
            for descriptor in active_descriptors(state):
                identity = {k: descriptor.get(k) for k in ('id', 'kind', 'version', 'entry_point', 'implementation', 'dependencies', 'dependency_imports', 'execution')}
                identity['implementation'] = {k: v for k, v in (descriptor.get('implementation') or {}).items() if k not in {'declaration_sha', 'sha256'}}
                resources = descriptor.get('resources') or {}
                identity['r'] = resources.get('r')
                identity['resources'] = {key: resources.get(key) for key in ('environment', 'external_tools')}
                fingerprint = sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
                old = self.entries.get(descriptor['id'], {})
                current[descriptor['id']] = old if old.get('fingerprint') == fingerprint else {
                    'id': descriptor['id'], 'title': descriptor['title'], 'fingerprint': fingerprint,
                    'status': 'unchecked', 'error': '', 'execution': descriptor.get('execution', {'mode': 'shared'}),
                    'dependencies': descriptor.get('dependencies', []),
                    'dependency_imports': descriptor.get('dependency_imports', []),
                    'resources': {key: (descriptor.get('resources') or {}).get(key)
                                  for key in ('environment', 'external_tools')},
                    'r': (descriptor.get('resources') or {}).get('r')}
            allowed = scope()
            if allowed:
                current = {key: value for key, value in current.items() if key in allowed}
            self.entries = current

    def snapshot(self):
        with self.lock:
            return {'running': self.running, 'entries': deepcopy(list(self.entries.values()))}

    def _update(self, ids, status, error=''):
        with self.lock:
            for key in ids:
                self.entries[key].update(status=status, error=error)
                record = {**self.entries[key], 'time': datetime.now(timezone.utc).isoformat()}
                io_path(self.log.parent).mkdir(parents=True, exist_ok=True)
                with io_path(self.log).open('a', encoding='utf-8') as output:
                    output.write(json.dumps(record, ensure_ascii=False) + '\n')

    def _inspect(self, state, entries):
        self._log_round(state, entries)
        if state.get('runtime_protocol') == 1:
            from operon.targets import inspect_entries
            return inspect_entries(state, entries, self.manager.directory / 'staging')
        return self.inspector(self.manager.python_for(state), entries, self.manager.directory / 'staging')

    def _log_round(self, state, entries):
        try:
            python = self.manager.python_for(state)
        except Exception:
            python = 'unknown'
        path = io_path(self.log.parent / 'dependency-checks.log')
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps({'time': datetime.now(timezone.utc).isoformat(),
                                     'python': str(python),
                                     'ids': [entry['id'] for entry in entries]}, ensure_ascii=False) + '\n')

    def check(self, *, repair=True, repair_r=None, ids=None):
        # Shared with source/wheel transactions so the runtime cannot change
        # between probing and committing a repair. HTTP reads remain lock-free.
        if self.cancel.is_set():
            return self.snapshot()
        repair_r = repair if repair_r is None else repair_r
        self.manager.state()
        with self.manager.lock:
            if self.cancel.is_set():
                return self.snapshot()
            state = self.manager.state()
            self.sync(state)
            selected = None if ids is None else set(ids)
            if selected is not None and selected - self.entries.keys():
                raise ValueError('Unknown dependency declarations: ' + ', '.join(sorted(selected - self.entries.keys())))
            with self.lock:
                if self.running:
                    return self.snapshot()
                self.running = True
                pending = deepcopy([v for v in self.entries.values()
                                    if v['status'] != 'passed' and (selected is None or v['id'] in selected)])
            from operon.plugins import process_context
            previous_cancel = getattr(process_context, 'cancel', None)
            process_context.cancel = self.cancel
            try:
                if not pending:
                    with self.lock:
                        self.running = False
                    return self.snapshot()
                self._update([v['id'] for v in pending], 'checking')
                results = self._inspect(state, pending)
                failed = [v for v in pending if results[v['id']]['status'] != 'passed']
                for entry in pending:
                    result = results[entry['id']]
                    self._update([entry['id']], **({'status': 'checking', 'error': ''} if entry.get('r') is not None and result['status'] == 'passed' else result))
                if repair:
                    from operon.install_targets import repair_entries
                    for entry in failed:
                        if self.cancel.is_set():
                            raise ValueError('Dependency preparation cancelled: Studio is closing')
                        # A named interpreter has its own Python version and
                        # dependency pins. Shared pip targets cannot repair it.
                        # Retain the probe's actionable environment error.
                        if (entry.get('resources') or {}).get('environment'):
                            continue
                        if not entry['dependencies']:
                            continue
                        self._update([entry['id']], 'installing')
                        try:
                            candidate = repair_entries(self.manager, state, [entry])
                            selected = [d for d in candidate['descriptors'] if d['id'] == entry['id']]
                            checked = self._inspect(candidate, selected)[entry['id']]
                            if checked['status'] != 'passed':
                                raise ValueError(checked['error'])
                            state = self.manager._publish(candidate)
                            self.sync(state)
                            self._update([entry['id']], **checked)
                        except Exception as exc:
                            self._update([entry['id']], 'failed', str(exc))
                from operon.r_runtime import RRuntime
                r_runtime = RRuntime(self.manager.directory.parent / 'runtimes/r')
                for entry in pending:
                    if self.cancel.is_set():
                        raise ValueError('Dependency preparation cancelled: Studio is closing')
                    if entry.get('r') is not None and self.entries[entry['id']]['status'] in ('passed', 'checking'):
                        self._update([entry['id']], 'installing' if repair_r else 'checking')
                        try:
                            r_runtime.ensure(entry['r'], repair=repair_r, verify=True)
                            self._update([entry['id']], 'passed')
                        except Exception as exc:
                            self._update([entry['id']], 'failed', str(exc))
            except Exception as exc:
                self._update([v['id'] for v in pending if self.entries[v['id']]['status'] != 'passed'], 'failed', str(exc))
            finally:
                process_context.cancel = previous_cancel
                with self.lock:
                    self.running = False
            return self.snapshot()


if __name__ == '__main__':
    request, response = map(Path, sys.argv[1:])
    entries = json.loads(request.read_text(encoding='utf-8'))
    results = probe(entries)
    log = io_path(os.environ.get('OPERON_DEPENDENCY_LOG', response.with_suffix('.log')))
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps({'time': datetime.now(timezone.utc).isoformat(),
                                 'python': sys.executable, 'entries': len(entries)}, ensure_ascii=False) + '\n')
        for entry in entries:
            handle.write(json.dumps({'id': entry['id'], **results.get(entry['id'], {})}, ensure_ascii=False) + '\n')
    response.write_text(json.dumps(results, ensure_ascii=False), encoding='utf-8')

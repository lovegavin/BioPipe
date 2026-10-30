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
from pathlib import Path
import sys
import threading
from datetime import datetime, timezone

from packaging.requirements import Requirement


def probe(entries):
    results = {}
    for entry in entries:
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
    from biopipe.plugins import run_process
    import tempfile
    Path(directory).mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='dependency-', dir=directory) as tmp:
        request, response = Path(tmp) / 'request.json', Path(tmp) / 'response.json'
        request.write_text(json.dumps(entries), encoding='utf-8')
        run_process([python, '-m', 'biopipe.dependencies', request, response], timeout=180)
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
        from biopipe.plugins import active_descriptors
        with self.lock:
            current = {}
            for descriptor in active_descriptors(state):
                identity = {k: descriptor.get(k) for k in ('id', 'kind', 'version', 'entry_point', 'implementation', 'dependencies', 'dependency_imports', 'execution')}
                identity['implementation'] = {k: v for k, v in (descriptor.get('implementation') or {}).items() if k not in {'declaration_sha', 'sha256'}}
                identity['r'] = descriptor.get('resources', {}).get('r')
                fingerprint = sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
                old = self.entries.get(descriptor['id'], {})
                current[descriptor['id']] = old if old.get('fingerprint') == fingerprint else {
                    'id': descriptor['id'], 'title': descriptor['title'], 'fingerprint': fingerprint,
                    'status': 'unchecked', 'error': '', 'execution': descriptor.get('execution', {'mode': 'shared'}),
                    'dependencies': descriptor.get('dependencies', []),
                    'dependency_imports': descriptor.get('dependency_imports', []),
                    'r': descriptor.get('resources', {}).get('r')}
            self.entries = current

    def snapshot(self):
        with self.lock:
            return {'running': self.running, 'entries': deepcopy(list(self.entries.values()))}

    def _update(self, ids, status, error=''):
        with self.lock:
            for key in ids:
                self.entries[key].update(status=status, error=error)
                record = {**self.entries[key], 'time': datetime.now(timezone.utc).isoformat()}
                self.log.parent.mkdir(parents=True, exist_ok=True)
                with self.log.open('a', encoding='utf-8') as output:
                    output.write(json.dumps(record, ensure_ascii=False) + '\n')

    def _inspect(self, state, entries):
        if state.get('runtime_protocol') == 1:
            from biopipe.targets import inspect_entries
            return inspect_entries(state, entries, self.manager.directory / 'staging')
        return self.inspector(self.manager.python_for(state), entries, self.manager.directory / 'staging')

    def check(self, *, repair=True, repair_r=None):
        # Shared with source/wheel transactions so the runtime cannot change
        # between probing and committing a repair. HTTP reads remain lock-free.
        repair_r = repair if repair_r is None else repair_r
        self.manager.state()
        with self.manager.lock:
            state = self.manager.state()
            self.sync(state)
            with self.lock:
                if self.running:
                    return self.snapshot()
                self.running = True
                pending = deepcopy([v for v in self.entries.values() if v['status'] != 'passed'])
            from biopipe.plugins import process_context
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
                    from biopipe.install_targets import repair_entries
                    for entry in failed:
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
                from biopipe.r_runtime import RRuntime
                r_runtime = RRuntime(self.manager.directory.parent / 'runtimes/r')
                for entry in pending:
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
    response.write_text(json.dumps(probe(json.loads(request.read_text(encoding='utf-8'))), ensure_ascii=False), encoding='utf-8')

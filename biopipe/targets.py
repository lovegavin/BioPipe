"""Immutable dependency directories, all using the host Python executable."""
from copy import deepcopy
from importlib import metadata
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]


def base_paths():
    if os.environ.get('BIOPIPE_BASE_PATHS'):
        return json.loads(os.environ['BIOPIPE_BASE_PATHS'])
    return list(dict.fromkeys([str(ROOT), *[str(Path(p).resolve()) for p in sys.path if p]]))


def paths_for(state, descriptor=None):
    from biopipe.bytecode import filesystem_path
    root = Path(state['_runtime_root'])
    execution = (descriptor or {}).get('execution', {})
    selected = execution.get('paths', []) if execution.get('mode') == 'isolated' else state.get('shared_paths', [])
    return [filesystem_path(root / p) for p in [*state.get('code_paths', []), *selected]]


def command(paths, module, args, directory):
    from biopipe.bytecode import filesystem_path
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    config = directory / ('paths-' + uuid.uuid4().hex[:10] + '.json')
    config.write_text(json.dumps({'paths': list(dict.fromkeys([str(ROOT), *map(filesystem_path, paths), *base_paths()]))}), encoding='utf-8')
    return [sys.executable, '-I', '-S', str(ROOT / 'biopipe/runtime_bootstrap.py'), str(config), module, *map(str, args)]


def invoke(paths, module, args, directory, *, timeout=180):
    from biopipe.plugins import run_process
    argv = command(paths, module, args, directory)
    try:
        return run_process(argv, timeout=timeout)
    finally:
        Path(argv[4]).unlink(missing_ok=True)


def activate(state):
    if state.get("_runtime_root"):
        os.environ["BIOPIPE_R_HOME"] = str(Path(state["_runtime_root"]).parent / "runtimes/r")
    sys.dont_write_bytecode = True
    # Called before importing numpy/SDK in a fresh pipeline worker.
    if state.get('runtime_protocol') == 1:
        os.environ['BIOPIPE_BASE_PATHS'] = json.dumps(base_paths())
        sys.path[:0] = paths_for(state)


def inspect_entries(state, entries, directory):
    from collections import defaultdict
    groups = defaultdict(list)
    Path(directory).mkdir(parents=True, exist_ok=True)
    for entry in entries:
        groups[tuple(paths_for(state, entry))].append(entry)
    results = {}
    for paths, group in groups.items():
        with tempfile.TemporaryDirectory(prefix='probe-', dir=directory) as tmp:
            request, response = Path(tmp) / 'in.json', Path(tmp) / 'out.json'
            request.write_text(json.dumps(group), encoding='utf-8')
            invoke(paths, 'biopipe.dependencies', [request, response], tmp)
            results.update(json.loads(response.read_text(encoding='utf-8')))
    return results


def versions(paths):
    result = {}
    for dist in metadata.distributions(path=[*map(str, paths), *base_paths()]):
        name = dist.metadata['Name']
        if name:
            result.setdefault(canonicalize_name(name), dist.version)
    return result


class TargetBuilder:
    def __init__(self, manager, state):
        self.manager = manager
        self.state = deepcopy(state)
        self.state.update(runtime_protocol=1, _runtime_root=str(manager.directory.resolve()))
        self.shared = list(state.get('shared_paths', []))
        self.prepared = {}
        self.staging = manager.directory / 'staging'
        self.staging.mkdir(parents=True, exist_ok=True)

    def prepare(self, dependencies):
        from biopipe import __version__ as host_version
        from biopipe_sdk.dependencies import requirements
        deps = requirements(dependencies)
        # Engine code is always supplied by the host; never install a second SDK.
        for value in deps:
            req = Requirement(value)
            active = not req.marker or req.marker.evaluate()
            if (active and canonicalize_name(req.name) == 'biopipe-studio'
                    and not req.specifier.contains(host_version, prereleases=True)):
                raise ValueError(f'Operator requires an incompatible BioPipe SDK: {value}')
        deps = [v for v in deps if canonicalize_name(Requirement(v).name) != 'biopipe-studio']
        key = tuple(deps)
        if key in self.prepared:
            return deepcopy(self.prepared[key])
        shared_paths = [self.manager.directory / p for p in self.shared]
        pinned = versions(shared_paths)
        active = [Requirement(d) for d in deps if not Requirement(d).marker or Requirement(d).marker.evaluate()]
        direct_conflict = any(canonicalize_name(r.name) in pinned and not r.specifier.contains(pinned[canonicalize_name(r.name)], prereleases=True) for r in active)
        try:
            if direct_conflict:
                raise DependencyConflict('Declared version differs from the shared runtime')
            path = self._resolve(deps, shared_paths, pinned)
            if path:
                self.shared.insert(0, path)
            result = {'mode': 'shared'}
        except DependencyConflict as exc:
            path = self._resolve(deps, [], None)
            result = {'mode': 'isolated', 'paths': [path] if path else [], 'reason': str(exc)}
        self.prepared[key] = result
        return deepcopy(result)

    def _resolve(self, deps, paths, pinned):
        if not deps:
            return None
        with tempfile.TemporaryDirectory(prefix='resolve-', dir=self.staging) as tmp:
            tmp = Path(tmp)
            report = tmp / 'resolve.json'
            args = ['install', '--disable-pip-version-check', '--dry-run', '--report', report]
            wheelhouse = Path(sys.executable).resolve().parent / 'wheelhouse'
            if wheelhouse.is_dir():
                args += ['--find-links', wheelhouse]
            if pinned is None:
                args += ['--ignore-installed']
            else:
                constraints = tmp / 'constraints.txt'
                constraints.write_text('\n'.join(f'{k}=={v}' for k, v in sorted(pinned.items())), encoding='utf-8')
                args += ['--constraint', constraints]
            try:
                invoke(paths, 'pip', [*args, *deps], tmp, timeout=600)
            except ValueError as exc:
                # Network/build/Python-version errors are not version conflicts.
                if pinned is not None and ('ResolutionImpossible' in str(exc) or 'conflicting dependencies' in str(exc)):
                    raise DependencyConflict(str(exc)) from exc
                raise
            resolved = json.loads(report.read_text(encoding='utf-8'))['install']
            if not resolved:
                return None
            relative = 'targets/' + uuid.uuid4().hex[:16]
            destination = self.manager.directory / relative
            destination.mkdir(parents=True)
            artifacts = []
            for item in resolved:
                if canonicalize_name(item['metadata']['name']) == 'biopipe-studio':
                    raise ValueError('A dependency attempted to replace the BioPipe engine')
                info = item['download_info']
                url = info['url']
                digest = info.get('archive_info', {}).get('hashes', {}).get('sha256')
                if digest and '#' not in url:
                    url += '#sha256=' + digest
                artifacts.append(url)
            invoke([], 'pip', ['install', '--disable-pip-version-check', '--no-deps', '--no-compile', '--target', destination, *artifacts], tmp, timeout=600)
            from biopipe.bytecode import precompile
            precompile(destination)
            receipt = [{'name': item['metadata']['name'], 'version': item['metadata']['version'],
                        'sha256': item['download_info'].get('archive_info', {}).get('hashes', {}).get('sha256')}
                       for item in resolved]
            (destination / 'biopipe-target.json').write_text(json.dumps({'requirements': deps, 'resolved': receipt}, indent=2), encoding='utf-8')
            return relative

    def finish(self, state):
        state.update(runtime_protocol=1, shared_paths=self.shared, _runtime_root=str(self.manager.directory.resolve()))
        state.pop('python', None)
        return state


class DependencyConflict(ValueError):
    pass

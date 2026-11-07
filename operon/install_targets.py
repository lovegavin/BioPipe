"""Transactional provider installation with per-operator dependency selection."""
from copy import deepcopy
import configparser
from email.parser import BytesParser
import importlib
import inspect
import json
import os
from pathlib import Path
import sys
import tempfile
import zipfile
from urllib.parse import quote

from packaging.utils import canonicalize_name
from operon.targets import TargetBuilder, invoke
from operon.bytecode import filesystem_path


def _wheel_argument(wheel):
    path = Path(filesystem_path(wheel))
    if os.name == 'nt' and len(str(path)) >= 260:
        # pip's native-path -> file-URL conversion removes Windows' extended
        # prefix. Encode it explicitly, leaving the wheel filename recognizable.
        return 'file:' + quote(str(path.parent), safe='') + '/' + quote(path.name)
    return str(path)


def wheel_entries(wheel):
    wheel = Path(filesystem_path(wheel))
    with zipfile.ZipFile(wheel) as archive:
        info = next(n for n in archive.namelist() if n.endswith('.dist-info/METADATA'))
        prefix = info.rsplit('/', 1)[0]
        metadata = BytesParser().parsebytes(archive.read(info))
        dependencies = metadata.get_all('Requires-Dist', [])
        manifest_path = prefix + '/operon.json'
        if manifest_path in archive.namelist():
            from operon_sdk.protocol import PackageDescriptor
            manifest = json.loads(archive.read(manifest_path))
            PackageDescriptor.model_validate(manifest)
            if manifest['name'] != canonicalize_name(metadata['Name']) or manifest['version'] != metadata['Version']:
                raise ValueError('Package manifest identity differs from wheel metadata')
            from operon_sdk.declarations import verify_archive
            verify_archive({n: archive.read(n) for n in archive.namelist()}, manifest['descriptors'])
            return [{'entry': d['entry_point'], 'kind': d['kind'], 'expected': d,
                     'dependencies': sorted(set(dependencies + d.get('dependencies', [])))} for d in manifest['descriptors']]
        raise ValueError(f'{wheel.name}: protocol v3 wheel requires operon.json; build with `operon plugin build`')


def execution_digest(wheel):
    """Fingerprint executable wheel contents separately from Markdown bytes.

    Full archive SHA-256 is retained for transport/integrity. Only declared,
    hash-verified Markdown and parameter sidecars, their descriptor metadata and
    RECORD checksums are excluded here. Concrete parameter values belong to the
    workflow. Code, resource capabilities, native libraries and other assets remain.
    """
    import hashlib
    from operon_sdk.documentation import archive_path
    from operon_sdk.declarations import declaration_hash
    wheel = Path(filesystem_path(wheel))
    records = wheel_entries(wheel)
    with zipfile.ZipFile(wheel) as archive:
        entries = {name: archive.read(name) for name in archive.namelist() if not name.endswith('/')}
    excluded = {archive_path(entries, entry['expected']) for entry in records if entry['expected'].get('documentation')}
    from operon_sdk.localization import archive_path as language_path
    excluded.update(language_path(entries, entry['expected']) for entry in records if entry['expected'].get('localization'))
    import ast
    from pathlib import PurePosixPath
    for record in records:
        descriptor = record['expected']
        module, classname = descriptor['entry_point'].split(':')
        module = module.replace('.', '/')
        source = module + '.py' if module + '.py' in entries else module + '/__init__.py'
        cls = next(node for node in ast.parse(entries[source].decode('utf-8')).body
                   if isinstance(node, ast.ClassDef) and node.name == classname)
        relative = 'parameters.json' if source.endswith('/__init__.py') else PurePosixPath(source).stem + '.parameters.json'
        for node in cls.body:
            targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
            if any(isinstance(target, ast.Name) and target.id == 'parameters_file' for target in targets):
                relative = ast.literal_eval(node.value)
        # wheel_entries already checked containment and exact schema content.
        excluded.add(str(PurePosixPath(source).parent / relative.replace('\\', '/')))
    digest = hashlib.sha256()
    for name, content in sorted(entries.items()):
        if name in excluded or name.endswith(('.dist-info/RECORD', '.dist-info/RECORD.jws', '.dist-info/RECORD.p7s')):
            continue
        if name.endswith('.dist-info/operon.json'):
            value = json.loads(content)
            for descriptor in value['descriptors']:
                descriptor.pop('documentation', None)
                descriptor.pop('localization', None)
                descriptor.pop('protocol_revision', None)
                descriptor.pop('parameters_schema', None)
                descriptor['declaration_sha'] = declaration_hash(descriptor)
            content = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
        digest.update(name.encode('utf-8') + b'\0' + hashlib.sha256(content).digest())
    return digest.hexdigest()


def load_class(descriptor):
    from operon_sdk.declarations import load_class as load
    return load(descriptor)


def probe_entry(request):
    from operon_sdk.protocol import validate_extension, describe_operator, describe_reader
    from src.task.step.base import Step
    from src.reader.base import Reader
    entry = request['entry']
    classes = [(request['kind'], load_class(request['expected']))]
    result = []
    for kind, cls in classes:
        validate_extension(cls, kind)
        if not issubclass(cls, Step if kind == 'operator' else Reader):
            raise ValueError('Invalid extension base class')
        descriptor = describe_operator(cls) if kind == 'operator' else describe_reader(cls())
        if not cls.output_contract or kind == 'operator' and cls.input_contracts is None:
            raise ValueError('Extensions must declare input/output contracts')
        expected = request.get('expected')
        if expected is not None and descriptor != expected:
            raise ValueError(f'Wheel descriptor differs from implementation: {descriptor["id"]}')
        from operon_sdk.dependencies import requirements
        descriptor['dependencies'] = requirements(request['dependencies'] + descriptor.get('dependencies', []))
        from operon_sdk.declarations import declaration_hash
        descriptor['declaration_sha'] = declaration_hash(descriptor)
        result.append(descriptor)
    return result


def _validate_host_requirements(records):
    """Check host API compatibility from metadata, before staging any code."""
    from packaging.requirements import Requirement
    from operon import __version__ as host_version
    for entry in records:
        for text in entry['dependencies']:
            requirement = Requirement(text)
            if canonicalize_name(requirement.name) != 'operon-studio':
                continue
            if requirement.marker and not requirement.marker.evaluate():
                continue
            if requirement.url or not requirement.specifier.contains(host_version, prereleases=True):
                raise ValueError(f'Operator requires an incompatible Operon SDK: {text}')


def install(manager, current, packages, generation, *, dependencies=()):
    # One discovery-policy-aware factory snapshot per transaction. Repeating a
    # filesystem-backed bundled_state() for every entry made large library
    # refreshes scan the same source tree hundreds of times.
    bundled = manager.bundled_state()
    bundled_names = {p['name'] for p in bundled['packages']}
    bundled_owners = {d['id']: d['distribution'] for d in bundled['descriptors']}
    builder = TargetBuilder(manager, current)
    environment = manager.directory / 'environments' / generation
    Path(filesystem_path(environment)).mkdir(parents=True)
    code = environment / 'code'
    wheels = [p for p in packages if p.get('origin') != 'bundled']
    wheel_records = {p['name']: wheel_entries(manager.directory / p['wheel']) for p in wheels}
    for records in wheel_records.values():
        _validate_host_requirements(records)
    if wheels:
        invoke([], 'pip', ['install', '--disable-pip-version-check', '--no-deps', '--no-compile', '--target', filesystem_path(code),
                           *[_wheel_argument(manager.directory / p['wheel']) for p in wheels]], environment, timeout=600)
    descriptors = [deepcopy(d) for d in bundled['descriptors'] if any(p['name'] == d['distribution'] and p.get('origin') == 'bundled' for p in packages)]
    old = {d['id']: d for d in current['descriptors']}
    # Existing successful isolation choices remain pinned. Dependency repair
    # handles bundled declarations individually, not an incompatible union.
    for descriptor in descriptors:
        previous = old.get(descriptor['id'], {})
        if (previous.get('origin') == 'bundled' and previous.get('distribution') == descriptor['distribution']
                and previous.get('code_sha') == descriptor['code_sha']):
            descriptor.clear()
            descriptor.update(deepcopy(previous))
    for package in wheels:
        previous_package = next((p for p in current['packages'] if p['name'] == package['name']), {})
        if (current.get('runtime_protocol') == 1 and previous_package.get('sha256') == package['sha256']):
            descriptors.extend(deepcopy(d) for d in current['descriptors'] if d['distribution'] == package['name'])
            continue
        records = []
        for entry in wheel_records[package['name']]:
            # wheel_entries verifies static declarations, code hashes and
            # sidecars. Importing the implementation here would execute user
            # top-level code and force scientific dependencies at registration.
            descriptor = deepcopy(entry['expected'])
            previous = old.get(descriptor['id'], {})
            from packaging.requirements import Requirement
            declared = {v for v in entry['dependencies'] if canonicalize_name(Requirement(v).name) != 'operon-studio'}
            reuse = bool(previous and previous.get('code_sha') == descriptor['code_sha']
                         and declared == set(previous.get('dependencies', [])))
            execution = deepcopy(previous.get('execution', {'mode': 'shared'})) if reuse else {'mode': 'shared'}
            from operon_sdk.dependencies import requirements
            from operon_sdk.declarations import declaration_hash
            descriptor['dependencies'] = requirements(sorted(declared))
            descriptor['declaration_sha'] = declaration_hash(descriptor)
            if descriptor['id'] in bundled_owners and bundled_owners[descriptor['id']] != package['name']:
                raise ValueError(f'Plugin shadows a built-in: {descriptor["id"]}')
            if '.' not in descriptor['id'] and package['name'] not in bundled_names:
                raise ValueError('Plugin IDs must be namespaced')
            descriptor.update(distribution=package['name'], package_version=package['version'], origin='wheel', execution=execution,
                              implementation={k: package[k] for k in ('version', 'sha256')})
            descriptor['implementation'].update(package=package['name'], code_sha=descriptor['code_sha'], declaration_sha=descriptor['declaration_sha'])
            if package.get('execution_sha'):
                descriptor['implementation']['execution_sha'] = package['execution_sha']
            records.append(descriptor)
        owned = {key for key, owner in bundled_owners.items() if owner == package['name']}
        if not owned <= {d['id'] for d in records}:
            raise ValueError('Replacement package must preserve its bundled IDs')
        if not records:
            raise ValueError(f'No Operon entry points in {package["name"]}')
        descriptors.extend(records)
    ids = [d['id'] for d in descriptors]
    if len(ids) != len(set(ids)):
        raise ValueError('Two packages declare the same ID')
    if wheels:
        # Bytecode compilation parses the installed source without importing it
        # or preparing scientific dependencies. Never leave immutable workers
        # recompiling plugin code on every run.
        from operon.bytecode import precompile
        precompile(code)
    if dependencies:
        # Legacy API: dependency-only installs remain a single request. The
        # session API uses repair_entries for individual operator requirements.
        execution = builder.prepare(list(dependencies))
        if execution['mode'] == 'isolated':
            raise ValueError('Conflicting dependencies require an operator declaration')
    state = builder.finish({**deepcopy(current), 'generation': generation, 'packages': packages, 'descriptors': descriptors,
                            'code_paths': [str(code.relative_to(manager.directory))] if wheels else []})
    return state


def repair_entries(manager, current, entries):
    builder = TargetBuilder(manager, current)
    state = deepcopy(current)
    selected = {e['id'] for e in entries}
    for descriptor in state['descriptors']:
        if descriptor['id'] in selected:
            descriptor['execution'] = builder.prepare(descriptor.get('dependencies', []))
    return builder.finish(state)


if __name__ == '__main__':
    from contextlib import redirect_stdout
    request, response = map(Path, sys.argv[1:])
    with redirect_stdout(sys.stderr):
        value = json.loads(request.read_text(encoding='utf-8'))
        result = [probe_entry(e) for e in value] if isinstance(value, list) else probe_entry(value)
    response.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')

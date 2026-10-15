"""Transactional provider installation with per-operator dependency selection."""
from copy import deepcopy
import configparser
from email.parser import BytesParser
import importlib
import inspect
import json
from pathlib import Path
import sys
import tempfile
import zipfile

from packaging.utils import canonicalize_name
from biopipe.targets import TargetBuilder, invoke


def wheel_entries(wheel):
    from biopipe_sdk.dependencies import source_requirements, source_entries
    with zipfile.ZipFile(wheel) as archive:
        info = next(n for n in archive.namelist() if n.endswith('.dist-info/METADATA'))
        prefix = info.rsplit('/', 1)[0]
        metadata = BytesParser().parsebytes(archive.read(info))
        dependencies = metadata.get_all('Requires-Dist', [])
        if prefix + '/biopipe.entries.json' in archive.namelist():
            from biopipe_sdk.dependencies import requirements
            records = json.loads(archive.read(prefix + '/biopipe.entries.json'))
            for record in records:
                if record['kind'] not in ('operator', 'reader'):
                    raise ValueError('Unknown extension kind')
                record['dependencies'] = requirements(dependencies + record['dependencies'])
            return records
        manifest_path = prefix + '/biopipe.json'
        if manifest_path in archive.namelist():
            from biopipe_sdk.protocol import PackageDescriptor
            manifest = json.loads(archive.read(manifest_path))
            PackageDescriptor.model_validate(manifest)
            if manifest['name'] != canonicalize_name(metadata['Name']) or manifest['version'] != metadata['Version']:
                raise ValueError('Package manifest identity differs from wheel metadata')
            return [{'entry': d['entry_point'], 'kind': d['kind'], 'expected': d,
                     'dependencies': sorted(set(dependencies + d.get('dependencies', [])))} for d in manifest['descriptors']]
        config = configparser.ConfigParser()
        if prefix + '/entry_points.txt' not in archive.namelist():
            raise ValueError(f'{wheel.name}: no BioPipe entry points')
        config.read_string(archive.read(prefix + '/entry_points.txt').decode())
        result = []
        for group, kind in [('biopipe.operators', 'operator'), ('biopipe.readers', 'reader'), ('biopipe.modules', 'module')]:
            for entry in config[group].values() if group in config else []:
                module = entry.split(':')[0].replace('.', '/')
                filename = module + '.py' if module + '.py' in archive.namelist() else module + '/__init__.py'
                content = archive.read(filename) if filename in archive.namelist() else None
                per_class = source_entries(content, entry.split(':')[0]) if content is not None else []
                if kind == 'module' and per_class:
                    result.extend({**record, 'dependencies': sorted(set(dependencies + record['dependencies']))} for record in per_class)
                    continue
                selected = next((record for record in per_class if record['entry'] == entry), None)
                declared = selected['dependencies'] if selected else source_requirements(content) if content is not None else []
                result.append({'entry': entry, 'kind': kind, 'dependencies': sorted(set(dependencies + declared))})
        if not result:
            raise ValueError(f'{wheel.name}: no BioPipe entry points')
        return result


def load_class(descriptor):
    module, name = descriptor['entry_point'].split(':', 1)
    cls = getattr(importlib.import_module(module), name)
    if descriptor.get('legacy_parameters') or '.' not in descriptor['id']:
        cls.parameters_schema = deepcopy(descriptor['parameters_schema'])
        cls.legacy_parameters = bool(descriptor.get('legacy_parameters', False))
        cls._package_descriptor = deepcopy(descriptor)
    return cls


def probe_entry(request):
    from biopipe_sdk.protocol import validate_extension, describe_operator, describe_reader
    from src.task.step.base import Step
    from src.reader.base import Reader
    entry = request['entry']
    if 'expected' in request:
        classes = [(request['kind'], load_class(request['expected']))]
    elif request['kind'] == 'module':
        module = importlib.import_module(entry)
        classes = [('operator' if issubclass(cls, Step) else 'reader', cls) for cls in vars(module).values()
                   if inspect.isclass(cls) and cls.__module__ == module.__name__ and not inspect.isabstract(cls)
                   and issubclass(cls, (Step, Reader))]
    else:
        module, name = entry.split(':', 1)
        classes = [(request['kind'], getattr(importlib.import_module(module), name))]
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
        descriptor['dependencies'] = sorted(set(request['dependencies'] + descriptor.get('dependencies', [])))
        result.append(descriptor)
    return result


def install(manager, current, packages, generation, *, dependencies=()):
    from biopipe.packages import bundled_state, owns_legacy_id
    builder = TargetBuilder(manager, current)
    environment = manager.directory / 'environments' / generation
    environment.mkdir(parents=True)
    code = environment / 'code'
    wheels = [p for p in packages if p.get('origin') != 'bundled']
    if wheels:
        invoke([], 'pip', ['install', '--disable-pip-version-check', '--no-deps', '--no-compile', '--target', code,
                           *[manager.directory / p['wheel'] for p in wheels]], environment, timeout=600)
    descriptors = [deepcopy(d) for d in bundled_state()['descriptors'] if any(p['name'] == d['distribution'] and p.get('origin') == 'bundled' for p in packages)]
    old = {d['id']: d for d in current['descriptors']}
    # Existing successful isolation choices remain pinned. Dependency repair
    # handles bundled declarations individually, not an incompatible union.
    for descriptor in descriptors:
        previous = old.get(descriptor['id'], {})
        if previous.get('implementation') == descriptor['implementation'] and previous.get('execution'):
            descriptor['execution'] = deepcopy(previous['execution'])
    for package in wheels:
        previous_package = next((p for p in current['packages'] if p['name'] == package['name']), {})
        if (current.get('runtime_protocol') == 1 and previous_package.get('sha256') == package['sha256']):
            descriptors.extend(deepcopy(d) for d in current['descriptors'] if d['distribution'] == package['name'])
            continue
        from collections import defaultdict
        groups = defaultdict(list)
        for entry in wheel_entries(manager.directory / package['wheel']):
            expected = entry.get('expected', {})
            previous = old.get(expected.get('id'), {})
            from packaging.requirements import Requirement
            declared = {v for v in entry['dependencies'] if canonicalize_name(Requirement(v).name) != 'biopipe-studio'}
            reuse = bool(previous and declared == set(previous.get('dependencies', [])))
            # An unchanged optional declaration can remain not-ready; repairing
            # that Reader must not block unrelated entries during source refresh.
            execution = deepcopy(previous.get('execution', {'mode': 'shared'})) if reuse else builder.prepare(entry['dependencies'])
            paths = execution.get('paths', []) if execution['mode'] == 'isolated' else builder.shared
            groups[tuple(paths)].append((entry, execution, reuse))
        records = []
        for paths, group in groups.items():
            with tempfile.TemporaryDirectory(prefix='entry-', dir=builder.staging) as tmp:
                request, response = Path(tmp) / 'in.json', Path(tmp) / 'out.json'
                request.write_text(json.dumps([e for e, _, _ in group]), encoding='utf-8')
                invoke([code, *[manager.directory / p for p in paths]], 'biopipe.install_targets', [request, response], tmp)
                found_groups = json.loads(response.read_text(encoding='utf-8'))
            for (_, execution, reuse), found in zip(group, found_groups, strict=True):
                for descriptor in found:
                    if not reuse:
                        execution = builder.prepare(descriptor['dependencies'])
                    bundled_names = {p['name'] for p in bundled_state()['packages']}
                    base_ids = {d['id'] for d in bundled_state()['descriptors']}
                    if descriptor['id'] in base_ids and not owns_legacy_id(package['name'], descriptor['id']):
                        raise ValueError(f'Plugin shadows a built-in: {descriptor["id"]}')
                    if '.' not in descriptor['id'] and package['name'] not in bundled_names:
                        raise ValueError('Plugin IDs must be namespaced')
                    descriptor.update(distribution=package['name'], package_version=package['version'], origin='wheel', execution=execution,
                                      implementation={k: package[k] for k in ('version', 'sha256')})
                    descriptor['implementation']['package'] = package['name']
                    records.append(descriptor)
        owned = {d['id'] for d in bundled_state()['descriptors'] if d['distribution'] == package['name']}
        if not owned <= {d['id'] for d in records}:
            raise ValueError('Replacement package must preserve its legacy IDs')
        if not records:
            raise ValueError(f'No BioPipe entry points in {package["name"]}')
        descriptors.extend(records)
    ids = [d['id'] for d in descriptors]
    if len(ids) != len(set(ids)):
        raise ValueError('Two packages declare the same ID')
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

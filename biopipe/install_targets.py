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
    with zipfile.ZipFile(wheel) as archive:
        info = next(n for n in archive.namelist() if n.endswith('.dist-info/METADATA'))
        prefix = info.rsplit('/', 1)[0]
        metadata = BytesParser().parsebytes(archive.read(info))
        dependencies = metadata.get_all('Requires-Dist', [])
        manifest_path = prefix + '/biopipe.json'
        if manifest_path in archive.namelist():
            from biopipe_sdk.protocol import PackageDescriptor
            manifest = json.loads(archive.read(manifest_path))
            PackageDescriptor.model_validate(manifest)
            if manifest['name'] != canonicalize_name(metadata['Name']) or manifest['version'] != metadata['Version']:
                raise ValueError('Package manifest identity differs from wheel metadata')
            from biopipe_sdk.declarations import verify_archive
            verify_archive({n: archive.read(n) for n in archive.namelist()}, manifest['descriptors'])
            return [{'entry': d['entry_point'], 'kind': d['kind'], 'expected': d,
                     'dependencies': sorted(set(dependencies + d.get('dependencies', [])))} for d in manifest['descriptors']]
        raise ValueError(f'{wheel.name}: protocol v3 wheel requires biopipe.json; build with `biopipe plugin build`')


def load_class(descriptor):
    from biopipe_sdk.declarations import load_class as load
    return load(descriptor)


def probe_entry(request):
    from biopipe_sdk.protocol import validate_extension, describe_operator, describe_reader
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
        from biopipe_sdk.dependencies import requirements
        descriptor['dependencies'] = requirements(request['dependencies'] + descriptor.get('dependencies', []))
        from biopipe_sdk.declarations import declaration_hash
        descriptor['declaration_sha'] = declaration_hash(descriptor)
        result.append(descriptor)
    return result


def install(manager, current, packages, generation, *, dependencies=()):
    from biopipe.packages import bundled_state, owns_builtin_id
    builder = TargetBuilder(manager, current)
    environment = manager.directory / 'environments' / generation
    environment.mkdir(parents=True)
    code = environment / 'code'
    wheels = [p for p in packages if p.get('origin') != 'bundled']
    if wheels:
        invoke([], 'pip', ['install', '--disable-pip-version-check', '--no-deps', '--no-compile', '--target', code,
                           *[manager.directory / p['wheel'] for p in wheels]], environment, timeout=600)
    if wheels:
        from biopipe.bytecode import precompile
        precompile(code)
    descriptors = [deepcopy(d) for d in bundled_state()['descriptors'] if any(p['name'] == d['distribution'] and p.get('origin') == 'bundled' for p in packages)]
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
                    if descriptor['id'] in base_ids and not owns_builtin_id(package['name'], descriptor['id']):
                        raise ValueError(f'Plugin shadows a built-in: {descriptor["id"]}')
                    if '.' not in descriptor['id'] and package['name'] not in bundled_names:
                        raise ValueError('Plugin IDs must be namespaced')
                    descriptor.update(distribution=package['name'], package_version=package['version'], origin='wheel', execution=execution,
                                      implementation={k: package[k] for k in ('version', 'sha256')})
                    descriptor['implementation'].update(package=package['name'], code_sha=descriptor['code_sha'], declaration_sha=descriptor['declaration_sha'])
                    records.append(descriptor)
        owned = {d['id'] for d in bundled_state()['descriptors'] if d['distribution'] == package['name']}
        if not owned <= {d['id'] for d in records}:
            raise ValueError('Replacement package must preserve its bundled IDs')
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

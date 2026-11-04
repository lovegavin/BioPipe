"""Install and exercise a library against the released application, in isolation.

No desktop, editable install, user profile or external scientific tool is used.
External tool adapters are exercised with synthetic outputs, not biological data.
"""
import argparse
import hashlib
import importlib
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys


def application_digest():
    import biopipe
    root = Path(biopipe.__file__).resolve().parent.parent
    digest = hashlib.sha256()
    for folder in ('biopipe', 'biopipe_sdk', 'src'):
        for path in sorted((root / folder).rglob('*')):
            if path.is_file() and path.suffix in {'.py', '.json'}:
                digest.update(path.relative_to(root).as_posix().encode() + b'\0' + path.read_bytes())
    return digest.hexdigest()


def probe(lock, work):
    from biopipe.bytecode import filesystem_path
    from biopipe.targets import activate
    from biopipe.plugins import load_runtime
    state = json.loads(lock.read_text(encoding='utf-8'))
    activate(state)
    load_runtime(state)
    by_id = {d['id']: d for d in state['descriptors']}
    namespace = by_id['resource_preflight']['entry_point'].split('.steps.')[0] + '.steps'
    resources = importlib.import_module(namespace + '._resources_common')
    assert {'rfam', 'amrfinder', 'antismash'} <= set(resources.load_resources())
    profile = Path(filesystem_path(work / 'profile'))
    assert resources.manifest_path().is_relative_to(profile), str(resources.manifest_path())
    # Each wheel gets its own helpers/resources. None may fall back to app data.
    for item in state['packages']:
        if item.get('origin') != 'wheel':
            continue
        module = 'biopipe_library_' + item['name'].replace('-', '_').replace('.', '_')
        helper = importlib.import_module(module + '.steps._resources_common')
        assert helper.manifest_path().is_relative_to(profile), str(helper.manifest_path())
        assert {'rfam', 'amrfinder', 'antismash'} <= set(helper.load_resources())
    import pytest
    fixtures = work / 'cases/fixtures'
    fixtures.mkdir(exist_ok=True)
    shutil.copyfile(Path(__file__).resolve().parents[1] / 'tests/fixtures/backbone_1bc8_c60_75.pdb',
                    fixtures / 'backbone_1bc8_c60_75.pdb')
    status = pytest.main([str(work / 'cases'), '-q', '-k', 'not real_', '--import-mode=importlib',
                          '--basetemp', str(work / 'test-temp')])
    if status:
        raise SystemExit(status)


def verify(source, bundle, work):
    # Load this release helper without making the repository importable.
    import runpy
    helper = runpy.run_path(str(source / 'scripts/release_library.py'))
    config = helper['configuration'](source)
    helper['released_application'](source, config)
    if work.exists():
        raise ValueError('Use a new empty verification directory')
    work.mkdir(parents=True)
    temporary = work / 'temp'
    temporary.mkdir()
    for key in ('TEMP', 'TMP', 'TMPDIR'):
        os.environ[key] = str(temporary)
    import tempfile
    tempfile.tempdir = str(temporary)
    os.environ['BIOPIPE_RUNTIME_CONFIG'] = str(work / 'runtime.json')
    os.environ['BIOPIPE_ADMISSION_DIR'] = str(work / 'admission')
    from biopipe.plugins import PluginManager
    from biopipe.library_bundle import sha256
    from src.web.models import Graph
    before_files = application_digest()
    manager = PluginManager(work / 'profile')
    old = manager.state()
    old_graph = manager.pin(Graph.model_validate({'nodes': [{'id': 'pca', 'kind': 'operator', 'operator': 'pca',
        'position': {'x': 0, 'y': 0}, 'params': {'n_components': 2}}], 'edges': []}))
    manager.manage('biopipe-microbiome', 'disable')
    state = manager.install(bundle)
    assert state['library_release']['version'] == config['version']
    assert manager.source_root.is_relative_to(work / 'profile')
    assert next(p for p in state['packages'] if p['name'] == 'biopipe-microbiome')['enabled'] is False
    assert manager.install(bundle)['generation'] == state['generation']
    historical = manager.snapshot(old_graph)
    pinned_pca = next(d for d in historical['descriptors'] if d['id'] == 'pca')
    assert pinned_pca['implementation'] == old_graph.plugin_lock['pca']
    assert old_graph.nodes[0].params == {'n_components': 2}
    before = {d['id'] for d in old['descriptors']}
    after = {d['id'] for d in state['descriptors']}
    assert before <= after
    assert {'amrfinder_plus', 'antismash_bgc', 'assembly_stats', 'crispr_array_detect',
            'flye_assemble', 'rfam_scan', 'trnascan_se'} <= after
    cases = work / 'cases'
    cases.mkdir()
    namespace = next(d['entry_point'].split('.steps.')[0] + '.steps' for d in state['descriptors']
                     if d['id'] == 'resource_preflight')
    # Reuse the author's parser/adapter tests, but import the INSTALLED wheel.
    # The source checkout and its conftest are deliberately absent from sys.path.
    test_files = [f'test_extension{number}.py' for number in
                  (110, 155, 199, 200, 203, 207, 246, 254, 279, *range(350, 357))]
    for filename in [*test_files, 'test_export_results.py']:
        original = source / 'tests' / filename
        content = original.read_text(encoding='utf-8').replace('src.task.step.steps', namespace)
        (cases / original.name).write_text(content, encoding='utf-8')
    lock = work / 'lock.json'
    lock.write_text(json.dumps(state), encoding='utf-8')
    subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()), '--probe', str(lock),
                    '--work', str(work)], cwd=work, check=True)
    # Real worker + Reader + streaming planner, with the new library lock.
    import yaml
    job = work / 'job'
    job.mkdir()
    data = work / 'input.csv'
    data.write_text('a,b\n1,2\n3,4\n', encoding='utf-8')
    manifest = {'sources': {'X': {'path': str(data), 'dims': ['sample', 'feature'],
                                 'labels': {'feature': 'builtin'}}},
                'steps': [{'name': 'describe', 'inputs': ['X']}],
                'runtime': {'memory': {'enabled': True, 'budget_mb': 4, 'chunk_mb': .01}}}
    (job / 'task.yaml').write_text(yaml.safe_dump(manifest), encoding='utf-8')
    (job / 'plugins.lock.json').write_text(json.dumps(state), encoding='utf-8')
    subprocess.run([sys.executable, '-I', '-m', 'biopipe.worker', str(job)], cwd=work, check=True)
    summary = json.loads((job / 'output/run_summary.json').read_text(encoding='utf-8'))
    memory = json.loads(Path(summary['memory_report']).read_text(encoding='utf-8'))
    assert summary['steps'] and memory['plans'][0]['mode'] == 'stream'
    assert application_digest() == before_files
    report = {'application': config['build_application'], 'library': config['version'],
              'bundle_sha256': sha256(bundle),
              'operators': sum(d['kind'] == 'operator' for d in state['descriptors']),
              'readers': sum(d['kind'] == 'reader' for d in state['descriptors']),
              'added': sorted(after - before), 'application_unchanged': True,
              'old_pin_and_parameters_preserved': True, 'idempotent_install': True,
              'disabled_provider_preserved': True, 'worker_streaming': True,
              'external_tools': 'Synthetic adapters only; real tool/database execution not tested',
              'passed': True}
    (work / 'verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--probe', type=Path)
    args = parser.parse_args()
    if args.probe:
        probe(args.probe.resolve(), args.work.resolve())
    else:
        verify(args.source.resolve(), args.bundle.resolve(), args.work.resolve())

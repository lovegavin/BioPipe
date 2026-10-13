"""Unified provider lifecycle and real wheel execution, including resource modes."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from biopipe.packages import bundled_manifest, bundled_state
from biopipe.plugins import PluginManager, active_descriptors
from biopipe_sdk.protocol import PackageDescriptor, validate_extension
from src.task import STEPS
from src.reader import READERS
from src.task.operator_catalog import build_catalog
from src.web.models import Graph

ROOT = Path(__file__).resolve().parents[1]


def test_builtin_manifest_complete_and_capabilities_valid():
    ids = []
    for package in bundled_manifest()['packages']:
        PackageDescriptor.model_validate(package)
        ids += [d['id'] for d in package['descriptors']]
    assert len(ids) == len(set(ids)) == len(STEPS) + len(READERS)
    for cls in STEPS.values():
        validate_extension(cls, 'operator')
    for reader in READERS:
        validate_extension(type(reader), 'reader')
    descriptors = {d['id']: d for d in bundled_state()['descriptors']}
    assert descriptors['describe']['resources']['stream_protocol'] == 'flat-reduction-v1'
    for name in ['H5adReader', 'MtxReader']:
        # Class naming is part of the old public ID; resolve case-insensitively.
        item = next(d for key, d in descriptors.items() if key.lower() == name.lower())
        assert item['resources']['disk_protocol'] == 'dense-writer-v1'
    live = build_catalog(STEPS)
    groups = next(d for d in live['operators'] if d['id'] == 'compare_groups')
    assert next(p for p in groups['parameters'] if p['key'] == 'group_a')['type'] == 'scalar'


def test_package_disable_remove_restore_and_pinned_graph(tmp_path):
    manager = PluginManager(tmp_path)
    initial = manager.state()
    graph = Graph.model_validate({'nodes': [{'id': 'pca', 'kind': 'operator', 'operator': 'pca',
                                           'position': {'x': 0, 'y': 0}, 'params': {}}], 'edges': []})
    pinned = manager.pin(graph)
    assert pinned.plugin_lock['pca']['package'] == 'biopipe-genetics'
    manager.manage('biopipe-genetics', 'disable')
    assert 'pca' not in {d['id'] for d in active_descriptors(manager.state())}
    assert manager.snapshot(pinned)['generation'] == initial['generation']
    assert 'pca' in {d['id'] for d in manager.catalog_for(pinned, build_catalog(STEPS))['operators']}
    manager.manage('biopipe-genetics', 'enable')
    manager.install(None, remove='biopipe-genetics')
    assert not any(p['name'] == 'biopipe-genetics' for p in manager.state()['packages'])
    assert 'pca' not in {d['id'] for d in manager.extend_catalog(build_catalog(STEPS))['operators']}
    manager.manage('biopipe-genetics', 'restore')
    assert 'pca' in {d['id'] for d in active_descriptors(manager.state())}
    before = manager.state()
    with pytest.raises(ValueError):
        manager.manage('missing', 'enable')
    assert manager.state() == before


def test_pre_package_registry_migrates_without_losing_environment(tmp_path):
    manager = PluginManager(tmp_path)
    manager.directory.mkdir(parents=True)
    manager.registry.write_text(json.dumps({'protocol_version': 1, 'generation': 'old', 'packages': [],
                                           'descriptors': [], 'python': 'environments/old/Scripts/python.exe'}))
    current = manager.state()
    assert len(current['packages']) == len(bundled_manifest()['packages'])
    assert current['python'] == 'environments/old/Scripts/python.exe'
    assert current['package_protocol_version'] == 1


def test_resource_claims_require_real_hooks():
    from biopipe_sdk import Step, Reader, port, reader_contract
    class BrokenStream(Step):
        name = 'test.bad'
        inputs_arity = 1
        parameters_schema = {'type': 'object'}
        input_contracts = [port()]
        output_contract = {'mode': 'report'}
        supports_streaming = True
        stream_protocol = 'flat-reduction-v1'
        def run(self, ctx, inputs): pass
    with pytest.raises(ValueError, match='run_stream'):
        validate_extension(BrokenStream, 'operator')
    class BrokenReader(Reader):
        extensions = ['.test']
        parameters_schema = {'type': 'object'}
        output_contract = reader_contract()
        supports_disk_read = True
        disk_protocol = 'dense-writer-v1'
        def read(self, *args, **kwargs): pass
    with pytest.raises(ValueError, match='probe'):
        validate_extension(BrokenReader, 'reader')
    from biopipe_sdk.resources import validate_probe
    with pytest.raises(ValueError, match='dense_bytes'):
        validate_probe({'shape': [2, 3], 'dtype': 'float32', 'dense_bytes': 4})


@pytest.mark.parametrize('value', [1, 9])
def test_disk_reader_checks_actual_values_before_publishing(tmp_path, monkeypatch, value):
    from examples.resource_plugin.resource_example import NpyReader
    from biopipe_sdk import reader_contract
    from src.task import Context
    class Genotypes(NpyReader):
        output_contract = reader_contract(representation='hard_call', ploidy=2)
        def metadata(self, *args):
            metadata = super().metadata(*args)
            metadata['info'].update(representation='hard_call', ploidy=2)
            return metadata
        def read(self, *args, **kwargs):
            raise AssertionError('Disk mode must not call eager read')
    monkeypatch.setattr('src.reader.READERS', [Genotypes()])
    source = tmp_path / 'data.npy'
    np.save(source, np.array([[value]], dtype=np.float32))
    ctx = Context(tmp_path, {'runtime': {'memory': {'enabled': True, 'budget_mb': 1}}})
    try:
        ctx.register_source('input', {'path': str(source), 'dims': ['sample', 'feature']})
        entry = ctx.forms.entry('input')
        if value == 9:
            with pytest.raises(Exception, match='invalid allele_count'):
                ctx.forms.stage_source(entry)
            assert entry.disk is None and not list(ctx.forms.cache_root.glob('.source-*'))
        else:
            ctx.forms.stage_source(entry)
            assert np.load(entry.disk / 'data.npy')[0, 0] == 1
    finally:
        ctx.finalize()


@pytest.fixture(scope='module')
def builtin_wheels(tmp_path_factory):
    from scripts.build_builtin_packages import build_package
    destination = tmp_path_factory.mktemp('builtin_wheels')
    return {p['name']: build_package(p['name'], destination)['wheels'][0]
            for p in bundled_manifest()['packages']}


def test_every_builtin_package_builds(builtin_wheels):
    assert len(builtin_wheels) == len(bundled_manifest()['packages'])
    import zipfile
    for name, wheel in builtin_wheels.items():
        with zipfile.ZipFile(wheel) as archive:
            path = next(n for n in archive.namelist() if n.endswith('.dist-info/biopipe.json'))
            manifest = json.loads(archive.read(path))
        original = next(p for p in bundled_manifest()['packages'] if p['name'] == name)
        assert {d['id'] for d in manifest['descriptors']} == {d['id'] for d in original['descriptors']}
        assert all(d['entry_point'].startswith(name.replace('-', '_') + '_provider.') for d in manifest['descriptors'])


def run_worker(manager, state, directory, sources, steps):
    import yaml
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'plugins.lock.json').write_text(json.dumps(state), encoding='utf-8')
    manifest = {'sources': sources, 'steps': steps, 'runtime': {'memory': {'enabled': True, 'budget_mb': 4, 'chunk_mb': .01}}}
    (directory / 'task.yaml').write_text(yaml.safe_dump(manifest), encoding='utf-8')
    result = subprocess.run([manager.python_for(state), str(ROOT / 'scripts/run.py'), str(directory)], cwd=ROOT,
                            capture_output=True, text=True, encoding='utf-8', timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads((directory / 'output/run_summary.json').read_text())
    return json.loads(Path(summary['memory_report']).read_text()), summary


def test_hot_builtin_wheels_preserve_disk_and_stream_and_old_lock(tmp_path, builtin_wheels):
    import anndata as ad
    from scipy.sparse import csr_matrix
    manager = PluginManager(tmp_path / 'state')
    old = manager.state()
    manager.install(builtin_wheels['biopipe-core'])
    state = manager.install(builtin_wheels['biopipe-readers'])
    assert len(state['descriptors']) == len(bundled_state()['descriptors'])
    assert sum(p.get('origin') == 'wheel' for p in state['packages']) == 2
    inputs = tmp_path / 'inputs'
    inputs.mkdir()
    (inputs / 'data.mtx').write_text('%%MatrixMarket matrix coordinate real general\n2 3 3\n1 1 2\n2 3 6\n1 1 1\n')
    (inputs / 'features.tsv').write_text('f1\nf2\n')
    (inputs / 'barcodes.tsv').write_text('s1\ns2\ns3\n')
    ad.AnnData(csr_matrix(np.arange(6, dtype=np.float32).reshape(2, 3))).write_h5ad(inputs / 'data.h5ad')
    sources = {name: {'path': str(inputs / ('data.' + ext)), 'dims': ['sample', 'feature'], 'labels': {}}
               for name, ext in [('mtx', 'mtx'), ('h5ad', 'h5ad')]}
    steps = [{'name': 'describe', 'inputs': [name]} for name in sources]
    report, summary = run_worker(manager, state, tmp_path / 'run', sources, steps)
    assert [p['mode'] for p in report['plans']] == ['stream', 'stream']
    assert report['event_counts']['source_prepare_complete'] == 2
    for exported, expected in zip(summary['steps'], [1.5, 2.5]):
        content = json.loads((tmp_path / 'run/output' / exported['export_path']).read_text())
        assert content['global']['mean'] == expected
    manager.manage('biopipe-core', 'disable')
    assert 'describe' not in {d['id'] for d in active_descriptors(manager.state())}
    # A frozen lock is independent of later package changes.
    previous_report, _ = run_worker(manager, old, tmp_path / 'old', sources, steps)
    assert all(p['mode'] == 'stream' for p in previous_report['plans'])
    manager.manage('biopipe-core', 'restore')
    assert next(p for p in manager.state()['packages'] if p['name'] == 'biopipe-core')['origin'] == 'bundled'


def test_hot_microbiome_wheel_runs_with_strict_contracts(tmp_path, builtin_wheels):
    manager = PluginManager(tmp_path / 'state')
    installed = manager.install(builtin_wheels['biopipe-microbiome'])
    descriptor = next(d for d in installed['descriptors'] if d['id'] == 'diversity')
    assert descriptor['origin'] == 'wheel' and not descriptor['legacy_parameters']
    path = tmp_path / 'counts.csv'
    path.write_text('a,b\n1,0\n0,1\n1,1\n2,0\n', encoding='utf-8')
    sources = {'counts': {'path': str(path), 'dims': ['sample', 'species'], 'labels': {'sample': 'auto', 'species': 'builtin'}}}
    steps = [{'name': 'diversity', 'inputs': ['counts'], 'params': {'dim': 'species', 'metrics': ['shannon'], 'output': 'alpha'}},
             {'name': 'describe', 'inputs': ['alpha']}]
    report, summary = run_worker(manager, installed, tmp_path / 'run', sources, steps)
    result = json.loads((tmp_path / 'run/output' / summary['steps'][1]['export_path']).read_text())
    assert result['global']['mean'] == pytest.approx(np.log(2) / 4)
    assert report['plans'][0]['mode'] == 'full' and report['plans'][1]['mode'] == 'stream'


def test_external_sdk_resource_package_runs_compressed_source(tmp_path):
    import gzip
    import shutil
    from biopipe.developer import build
    source = tmp_path / 'resource_plugin'
    shutil.copytree(ROOT / 'examples/resource_plugin', source)
    manager = PluginManager(tmp_path / 'state')
    installed = manager.install(build(source)['wheels'][0])
    data = np.arange(1000, dtype=np.float64).reshape(20, 50)
    path = tmp_path / 'values.npy.gz'
    with gzip.open(path, 'wb') as file:
        np.save(file, data)
    report, summary = run_worker(manager, installed, tmp_path / 'run',
        {'data': {'path': str(path), 'dims': ['sample', 'feature'], 'labels': {}}},
        [{'name': 'example.stream_sum', 'inputs': ['data']}])
    assert report['plans'][0]['mode'] == 'stream'
    assert report['event_counts']['source_prepare_complete'] == 1
    exported = json.loads((tmp_path / 'run/output' / summary['steps'][0]['export_path']).read_text())
    assert exported['sum'] == float(data.sum())

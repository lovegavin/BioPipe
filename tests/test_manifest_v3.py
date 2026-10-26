"""Manifest-first startup, immutable code, and independent declaration snapshots."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def child(code, *args):
    result = subprocess.run([sys.executable, '-c', code, *map(str, args)], cwd=ROOT,
                            capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout.splitlines()[-1])


def test_service_bootstrap_imports_no_implementations(tmp_path):
    value = child('''import sys,time,json,psutil
from pathlib import Path
start=time.perf_counter()
from src.web.api import create_app
from src.web.service import Settings
elapsed=(time.perf_counter()-start)*1000
app=create_app(Settings(Path(sys.argv[1]),Path(sys.argv[1])/'data',Path('frontend/dist'),testing=True))
catalog=app.state.service.catalog
assert not [k for k in sys.modules if k.startswith(('src.task.step.steps.','src.reader.readers.'))]
print(json.dumps({'operators':len(catalog['operators']),'readers':len(catalog['readers']), 'import_ms':elapsed,'rss_mib':psutil.Process().memory_info().rss/2**20}))
app.state.service.shutdown()
''', tmp_path)
    assert (value['operators'], value['readers']) == (64, 15)


def test_worker_imports_only_selected_operators_with_memory_enabled(tmp_path):
    value = child('''import sys,json,numpy as np
from pathlib import Path
from src.core import Form
from src.task import Context,run
steps=[{'name':'pca','inputs':['x'],'params':{'dim':'feature','n_components':2,'output':'pcs'}}, {'name':'describe','inputs':['pcs']}]
ctx=Context(Path(sys.argv[1]),{'runtime':{'memory':{'enabled':True,'budget_mb':32}}})
ctx['x']=Form(np.arange(20,dtype=float).reshape(5,4),['sample','feature'],{'sample':{str(i):i for i in range(5)},'feature':{str(i):i for i in range(4)}},{'missing_code':float('nan')})
try: run(ctx,steps)
finally: ctx.finalize()
names=[k for k in sys.modules if k.startswith('src.task.step.steps.')]
print(json.dumps(names))
''', tmp_path)
    assert len(value) <= 3
    assert 'src.task.step.steps.pca' in value and 'src.task.step.steps.describe' in value


def test_metadata_transaction_keeps_code_and_readiness(tmp_path):
    from biopipe.plugins import PluginManager
    from biopipe.dependencies import DependencySession
    from biopipe_sdk.declarations import bind_class, declaration_hash, load_class
    manager = PluginManager(tmp_path)
    before = manager.state()
    d = next(d for d in before['descriptors'] if d['id'] == 'pca')
    original = load_class(d)
    session = DependencySession(manager)
    session.sync(before)
    session.entries['pca']['status'] = 'passed'
    changed = deepcopy(original._declaration)
    changed['parameters_schema']['properties']['n_components']['x-ui-default'] = 5
    changed['title'] = 'Principal components'
    state = manager.update_declarations({'protocol_version': 3, 'descriptors': [changed]})
    session.sync(state)
    assert session.entries['pca']['status'] == 'passed'
    assert state['generation'] != before['generation']
    assert not (manager.directory / 'environments').exists()
    assert state.get('code_paths') == before.get('code_paths')
    new = next(d for d in state['descriptors'] if d['id'] == 'pca')
    assert new['code_sha'] == d['code_sha'] and new['declaration_sha'] != d['declaration_sha']
    assert load_class(new).parameters_schema['properties']['n_components']['x-ui-default'] == 5
    assert original.parameters_schema['properties']['n_components']['x-ui-default'] == 2
    assert load_class(d).parameters_schema == original.parameters_schema
    changed['resources']['memory_modes'].append('stream')
    with pytest.raises(ValueError, match='resources'):
        manager.update_declarations({'protocol_version': 3, 'descriptors': [changed]})
    assert manager.state()['generation'] == state['generation']
    changed = deepcopy(new)
    changed['version'] = '2.0.0'
    with pytest.raises(ValueError, match='version changed'):
        manager.update_declarations({'protocol_version': 3, 'descriptors': [changed]})
    assert manager.state()['generation'] == state['generation']


def test_static_parameter_drift_and_independent_hashes():
    from biopipe.packages import bundled_manifest
    from biopipe_sdk.drift import check_source
    from biopipe_sdk.declarations import declaration_hash
    d = next(d for p in bundled_manifest()['packages'] for d in p['descriptors'] if d['id'] == 'pca')
    text = (ROOT / 'src/task/step/steps/pca.py').read_text(encoding='utf-8')
    assert not check_source(text, d)[0]
    bad = text.replace('def run(self, ctx:', 'def run(self, ctx:')
    # A fixture with an alias also exercises .get() and dynamic-key warnings.
    bad = "class PCAStep(Step):\n    def run(self, ctx, inputs):\n        p = ctx.step_params\n        value = p.get('undeclared')\n"
    bad = bad.replace('PCAStep', d['entry_point'].split(':')[1])
    assert 'undeclared' in str(check_source(bad, d)[0])
    changed = deepcopy(d)
    changed['title'] += ' edited'
    assert declaration_hash(changed) != d['declaration_sha']
    assert changed['code_sha'] == d['code_sha']


def test_precompiled_cold_imports_never_attempt_bytecode_writes(tmp_path):
    from biopipe.bytecode import precompile
    source = tmp_path / 'example.py'
    source.write_text('VALUE = 42\n')
    assert precompile(tmp_path)['compiled'] == 1
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob('*.pyc')}
    script = '''import sys,json,importlib._bootstrap_external as b
sys.path.insert(0,sys.argv[1])
sys.dont_write_bytecode=True
def forbidden(*a,**k): raise AssertionError('readonly generation write attempted')
b._write_atomic=forbidden
b.SourceLoader.source_to_code=forbidden
import example
print(json.dumps(example.VALUE))
'''
    for _ in range(2):
        assert child(script, tmp_path) == 42
    assert before == {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob('*.pyc')}


def test_scaffold_install_and_demo(tmp_path):
    from biopipe.developer import scaffold, build
    from biopipe.plugins import PluginManager
    project = tmp_path / 'demo_extension'
    scaffold(project)
    wheel = build(project)['wheels'][0]
    manager = PluginManager(tmp_path / 'profile', source_root=None)
    manager.install(wheel)
    state = manager.state()
    descriptor = next(d for d in state['descriptors'] if d['id'] == 'example.demo_extension')
    assert descriptor['protocol_version'] == 3
    code = manager.directory / state['code_paths'][0]
    assert list(code.rglob('*.pyc'))
    value = child('''import sys,json,numpy as np
from biopipe.targets import activate
from biopipe.plugins import load_runtime
from pathlib import Path
state=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')); state['_runtime_root']=str(Path(sys.argv[1]).parent)
activate(state); load_runtime(state)
from src.task import STEPS
from biopipe_sdk import Form
from biopipe_sdk.testing import run_operator
form=Form(np.array([[1.,2.]]),['sample','feature'],{'sample':{'s':0},'feature':{'a':0,'b':1}},{'missing_code':float('nan')})
out=run_operator(STEPS['example.demo_extension'],[form],{'factor':3})
print(json.dumps(out.data.tolist()))
''', manager.registry)
    assert value == [[3., 6.]]


def test_build_rejects_missing_parameter_asset(tmp_path):
    from biopipe.developer import scaffold, check_source, embed_manifest
    from biopipe.dropins import write_wheel
    project = tmp_path / 'asset_example'
    scaffold(project)
    manifest = check_source(project)
    wheel = write_wheel({'asset_example/__init__.py': (project / 'asset_example/__init__.py').read_bytes()},
                        'asset-example', '0.1.0', [], tmp_path)
    with pytest.raises(ValueError, match='Missing parameter JSON in wheel'):
        embed_manifest(wheel, manifest)


def test_folder_parameter_refresh_reuses_code_and_frozen_defaults(tmp_path, monkeypatch):
    from biopipe.developer import scaffold
    from biopipe.plugins import PluginManager
    manager = PluginManager(tmp_path / 'profile', source_root=None)
    manager.state()
    project = manager.inbox / 'fresh_scale'
    scaffold(project)
    manager.refresh()
    before = deepcopy(manager.state())
    snapshot = manager.directory / 'old.json'
    snapshot.write_text(json.dumps(before), encoding='utf-8')
    parameter = project / 'fresh_scale/parameters.json'
    data = json.loads(parameter.read_text(encoding='utf-8'))
    data['properties']['factor']['default'] = 7
    parameter.write_text(json.dumps(data), encoding='utf-8')
    monkeypatch.setattr('biopipe.developer.build', lambda *a, **kw: pytest.fail('parameter edit must not build'))
    monkeypatch.setattr(manager, '_install_many', lambda *a, **kw: pytest.fail('parameter edit must not install'))
    manager.refresh()
    after = manager.state()
    assert after['code_paths'] == before['code_paths']
    assert after.get('shared_paths') == before.get('shared_paths')
    worker = '''import json,sys,numpy as np
from pathlib import Path
from biopipe.targets import activate
from biopipe.plugins import load_runtime
state=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
state['_runtime_root']=str(Path(sys.argv[1]).parent)
activate(state); load_runtime(state)
from src.task import STEPS
from biopipe_sdk import Form
from biopipe_sdk.testing import run_operator
form=Form(np.array([[1.]]),['sample','feature'],{'sample':{'s':0},'feature':{'f':0}},{'missing_code':float('nan')})
print(json.dumps(run_operator(STEPS['example.fresh_scale'],[form],{}).data.tolist()))
'''
    assert child(worker, snapshot) == [[2.]]
    assert child(worker, manager.registry) == [[7.]]
    original = manager.registry.read_bytes()
    data['properties'].pop('factor')
    parameter.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError, match='Undeclared parameter reads'):
        manager.refresh()
    assert manager.registry.read_bytes() == original


def test_source_parameter_refresh_and_unrelated_install_preserve_metadata(tmp_path, monkeypatch):
    import shutil
    from biopipe.plugins import PluginManager
    from biopipe.developer import scaffold, build
    source = tmp_path / 'checkout'
    for folder in ('src/task/step/steps', 'src/reader/readers'):
        shutil.copytree(ROOT / folder, source / folder, ignore=shutil.ignore_patterns('__pycache__'))
    (source / 'biopipe').mkdir()
    shutil.copy2(ROOT / 'biopipe/builtin_packages.json', source / 'biopipe/builtin_packages.json')
    manager = PluginManager(tmp_path / 'profile', source_root=source)
    before = manager.state()
    parameter = source / 'src/task/step/steps/pca.parameters.json'
    data = json.loads(parameter.read_text(encoding='utf-8'))
    data['properties']['n_components']['x-ui-default'] = 6
    parameter.write_text(json.dumps(data), encoding='utf-8')
    with monkeypatch.context() as guard:
        guard.setattr(manager, '_install_many', lambda *a, **kw: pytest.fail('parameter edit must not install'))
        manager.refresh()
    assert not (manager.directory / 'environments').exists()
    changed = next(d for d in manager.state()['descriptors'] if d['id'] == 'pca')
    assert changed['code_sha'] == next(d for d in before['descriptors'] if d['id'] == 'pca')['code_sha']
    project = tmp_path / 'another'
    scaffold(project)
    manager.install(build(project)['wheels'][0])
    retained = next(d for d in manager.state()['descriptors'] if d['id'] == 'pca')
    assert retained['parameters_schema']['properties']['n_components']['x-ui-default'] == 6


def test_metadata_removal_and_dual_hash_checks(tmp_path):
    from biopipe.plugins import PluginManager
    from biopipe_sdk.declarations import load_class, declaration_hash
    manager = PluginManager(tmp_path, source_root=None)
    old = next(d for d in manager.state()['descriptors'] if d['id'] == 'pca')
    update = deepcopy(old)
    update.pop('icon', None)
    update.pop('icon_image', None)
    state = manager.update_declarations({'protocol_version': 3, 'descriptors': [update]})
    new = next(d for d in state['descriptors'] if d['id'] == 'pca')
    assert 'icon' not in new and 'icon_image' not in new
    bad = deepcopy(new)
    bad['title'] = 'tampered'
    with pytest.raises(ValueError, match='Declaration hash mismatch'):
        load_class(bad)
    bad['declaration_sha'] = declaration_hash(bad)
    with pytest.raises(ValueError, match='Runtime identity mismatch'):
        load_class(bad)
    bad['implementation']['declaration_sha'] = bad['declaration_sha']
    bad['code_sha'] = bad['implementation']['code_sha'] = '0' * 64
    with pytest.raises(ValueError, match='Implementation code hash mismatch'):
        load_class(bad)


def test_lazy_txt_reader_rejects_self_delegation():
    from src.reader import READERS
    from src.reader.readers.txt_reader import _find_reader
    from src.core import ReaderError
    proxy = next(r for r in READERS if type(r).__name__ == 'TxtReader')
    with pytest.raises(ReaderError, match='no reader named'):
        _find_reader('txt', exclude=proxy.implementation())


def test_wheel_refresh_rejects_stale_manifest_code_and_missing_parameters(tmp_path):
    import zipfile
    from biopipe.developer import scaffold, build
    from biopipe.install_targets import wheel_entries
    project = tmp_path / 'integrity'
    scaffold(project)
    original = Path(build(project)['wheels'][0])
    with zipfile.ZipFile(original) as archive:
        entries = {n: archive.read(n) for n in archive.namelist()}
    assert len(wheel_entries(original)) == 1
    for changed, message in [({**entries, 'integrity/__init__.py': entries['integrity/__init__.py'] + b'\n# changed code\n'}, 'code hash mismatch'),
                             ({k: v for k, v in entries.items() if k != 'integrity/parameters.json'}, 'Missing parameter JSON')]:
        target = tmp_path / 'changed.whl'
        with zipfile.ZipFile(target, 'w') as archive:
            for name, content in changed.items():
                archive.writestr(name, content)
        with pytest.raises(ValueError, match=message):
            wheel_entries(target)


def test_migration_preserves_existing_v3_snapshot_and_missing_defaults(tmp_path):
    from biopipe.migrate import convert_documents
    from biopipe.packages import bundled_state
    state = bundled_state()
    current = next(d for d in state['descriptors'] if d['id'] == 'pca')
    pin = {**current['implementation'], 'declaration_sha': '0' * 64}
    graph = {'schema_version': 2, 'nodes': [{'id': 'pc', 'kind': 'operator', 'operator': 'pca',
             'position': {'x': 0, 'y': 0}, 'params': {}}], 'edges': [], 'plugin_lock': {'pca': pin}}
    converted = convert_documents(graph, state['descriptors'], implementations={'pca': current['implementation']})
    assert converted['plugin_lock']['pca'] == pin
    assert converted['nodes'][0]['params'] == {}


def test_source_migration_uses_module_specific_sidecars_and_rejects_collision(tmp_path):
    from biopipe.migrate import migrate
    source = 'class Scale:\n    name="lab.scale"\n    def run(self,ctx,inputs): pass\n'
    manifest = tmp_path / 'old.json'
    manifest.write_text(json.dumps({'id': 'lab.scale', 'entry_point': 'old:Scale',
                                   'parameters_schema': {'type': 'object'}}), encoding='utf-8')
    for name in ('first', 'second'):
        path = tmp_path / (name + '.py')
        path.write_text(source, encoding='utf-8')
        migrate(path=path, manifest=manifest, apply=True)
        assert (tmp_path / (name + '.Scale.parameters.json')).is_file()
    path = tmp_path / 'third.py'
    path.write_text(source, encoding='utf-8')
    sidecar = tmp_path / 'third.Scale.parameters.json'
    sidecar.write_text('{"user": "unrelated"}', encoding='utf-8')
    with pytest.raises(ValueError, match='already exists with different content'):
        migrate(path=path, manifest=manifest, apply=True)
    assert path.read_text(encoding='utf-8') == source
    assert json.loads(sidecar.read_text(encoding='utf-8')) == {'user': 'unrelated'}

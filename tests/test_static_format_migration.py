from operon_sdk.format_inference import infer_legacy_formats as _infer
from scripts.migrate_format_declarations import migrate
import pytest


def infer_legacy_formats(declaration, source, name):
    return _infer(declaration, 'from operon_sdk import Form, FileArtifact\n' + source, name)


def test_annotation_and_ambiguity():
    declaration = {'kind': 'reader', 'contracts': {'inputs': [], 'output': {'kind': ['form', 'file']}}}
    result = infer_legacy_formats(declaration, 'class R:\n def read(self) -> Form: return Form()', 'R')
    assert result['data_formats']['outputs'][0]['representations'] == ['form']
    result = infer_legacy_formats(declaration, 'class R:\n def read(self): return helper()', 'R')
    assert result['data_formats'] is None and result['diagnostics']
    result = infer_legacy_formats(declaration, 'class R:\n def read(self):\n  temporary = Form()\n  return helper()', 'R')
    assert result['data_formats'] is None


def test_dry_run_apply_backup_without_imports(tmp_path):
    source = "from operon_sdk import Form\nraise RuntimeError('never import')\nclass R:\n definition = {'id':'R','kind':'reader','protocol_version':3,'contracts':{'inputs':[],'output':{}}}\n def read(self) -> Form: return Form()\n"
    path = tmp_path / 'reader.py'
    path.write_text(source, encoding='utf-8')
    (tmp_path / 'reader.parameters.json').write_text('{"type":"object"}')
    result = migrate(tmp_path)
    assert len(result['proposals']) == 1 and path.read_text() == source
    migrate(tmp_path, True)
    assert '3.7' in path.read_text()
    assert path.with_name('reader.py.pre-sdk37').read_text() == source
    assert not migrate(tmp_path)['changed_files']


@pytest.mark.parametrize('body, expected', [
    ('temporary = Form()\n  return FileArtifact()', 'file_artifact'),
    ('value = Form()\n  alias = value\n  return alias', 'form'),
    ('if flag:\n   return FileArtifact()\n  return Form()', None),
    ('if flag:\n   return helper()\n  return Form()', None),
    ('return external_loader()', None),
    ('return make_form()', 'form'),
])
def test_read_output_flow(body, expected):
    source = 'def make_form():\n return Form()\nclass R:\n def read(self):\n  ' + body
    value = infer_legacy_formats({'kind': 'reader', 'contracts': {'inputs': [], 'output': {'kind': ['form', 'file']}}}, source, 'R')
    if expected is None:
        assert value['data_formats'] is None
    else:
        assert value['data_formats']['outputs'][0]['representations'] == [expected]


def test_context_output_alias_and_report_export():
    declaration = {'kind': 'operator', 'output_parameter': 'output', 'contracts': {'inputs': [{'numeric': True}], 'output': {}}}
    source = 'from operon_sdk import Form as F\nclass S:\n def run(self, ctx, inputs):\n  result = F()\n  ctx["out"] = result\n'
    assert infer_legacy_formats(declaration, source, 'S')['data_formats']['outputs'][0]['representations'] == ['form']
    early = source.replace('  result = F()', '  if flag:\n   return\n  result = F()')
    assert infer_legacy_formats(declaration, early, 'S')['data_formats'] is None
    declaration['contracts']['output'] = {'mode': 'report'}
    assert infer_legacy_formats(declaration, source + ' def export(self, ctx):\n  return Form()', 'S')['data_formats']['outputs'] == []


def test_existing_backup_is_never_overwritten(tmp_path):
    path = tmp_path / 'r.py'
    source = "from operon_sdk import Form\nclass R:\n definition={'id':'R','kind':'reader','protocol_version':3,'contracts':{'inputs':[],'output':{}}}\n def read(self): return Form()\n"
    path.write_text(source)
    (tmp_path / 'r.parameters.json').write_text('{"type":"object"}')
    backup = tmp_path / 'r.py.pre-sdk37'
    backup.write_bytes(b'previous')
    with pytest.raises(ValueError, match='Backup already exists'):
        migrate(tmp_path, True)
    assert path.read_text() == source and backup.read_bytes() == b'previous'


def test_polymorphic_inputs_and_untrusted_names_require_review():
    declaration = {'kind': 'operator', 'output_parameter': 'output', 'contracts': {'inputs': [{'kind': ['form', 'file']}], 'output': {}}}
    assert infer_legacy_formats(declaration, 'class S:\n def run(self,ctx,inputs): ctx["out"]=Form()', 'S')['data_formats'] is None
    reader = {'kind': 'reader', 'contracts': {'inputs': [], 'output': {'kind': ['form', 'file']}}}
    for prefix in ('from unrelated import Form\n', 'class Form: pass\n', '',
                   'from operon_sdk import Form\nfrom unrelated import Form\n'):
        assert _infer(reader, prefix + 'class R:\n def read(self): return Form()', 'R')['data_formats'] is None


def test_file_contract_remains_file_and_conflicting_flow_is_reviewed():
    declaration = {'kind': 'reader', 'contracts': {'inputs': [], 'output': {'kind': 'file', 'numeric': False}}}
    result = infer_legacy_formats(declaration, 'class R:\n def read(self): return read_file_source()', 'R')
    assert result['data_formats']['outputs'][0]['representations'] == ['file_artifact']
    assert infer_legacy_formats(declaration, 'class R:\n def read(self): return Form()', 'R')['data_formats'] is None


def test_publication_failure_rolls_back_previous_sources(tmp_path, monkeypatch):
    import operon.format_migration as migration
    original = {}
    for name in ('a', 'b'):
        path = tmp_path / (name + '.py')
        source = "from operon_sdk import Form\nclass R:\n definition={'id':'R','kind':'reader','protocol_version':3,'contracts':{'inputs':[],'output':{}}}\n def read(self): return Form()\n"
        path.write_text(source)
        original[path] = path.read_bytes()
        path.with_suffix('.parameters.json').write_text('{"type":"object"}')
    replace = migration.os.replace
    def fail_second(source, destination):
        if destination.name == 'b.py' and '.sdk37-restore-' not in source.name:
            raise PermissionError('simulated publication denial')
        return replace(source, destination)
    monkeypatch.setattr(migration.os, 'replace', fail_second)
    with pytest.raises(PermissionError):
        migrate(tmp_path, True)
    for path, data in original.items():
        assert path.read_bytes() == data
        assert path.with_name(path.name + '.pre-sdk37').read_bytes() == data
    assert not list(tmp_path.glob('*.sdk37-*'))


def test_scaffolds_keep_required_formats_with_localization(tmp_path):
    from operon.developer import scaffold, check_source
    for template in ('operator', 'reader'):
        project = tmp_path / template
        scaffold(project, template)
        descriptor = check_source(project)['descriptors'][0]
        assert descriptor['protocol_revision'] == '3.7'
        assert descriptor['data_formats']['outputs'][0]['representations'] == ['form']
        assert len(descriptor['data_formats']['inputs']) == (0 if template == 'reader' else 1)


def test_cli_dry_run_and_review_exit_code(tmp_path):
    import json
    import subprocess
    import sys
    root = tmp_path / 'library'
    root.mkdir()
    (root / 'demo.py').write_text("raise RuntimeError('never import')\nclass S:\n definition={'protocol_version':3,'id':'lab.s','kind':'operator','inputs_arity':1,'output_parameter':'output','contracts':{'inputs':[{'kind':['form','file']}],'output':{}}}\n def run(self,ctx,inputs): ctx['out']=helper()\n")
    (root / 'demo.parameters.json').write_text('{"type":"object"}')
    result = subprocess.run([sys.executable, '-m', 'operon', 'registry', 'formats', str(root)],
                            capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert result.returncode == 2, result.stderr
    report = json.loads(result.stdout)
    assert report['applied'] is False and len(report['review_required']) == 1
    assert not list(root.glob('*.pre-sdk37'))


def test_reader_scaffold_wheel_install_and_read(tmp_path):
    import json
    import subprocess
    import sys
    from operon.developer import scaffold, build
    from operon.plugins import PluginManager
    project = tmp_path / 'reader_example'
    scaffold(project, 'reader')
    wheel = build(project)['wheels'][0]
    manager = PluginManager(tmp_path / 'profile', source_root=None)
    manager.install(wheel)
    descriptor = next(d for d in manager.state()['descriptors'] if d['id'] == 'example.reader_example')
    assert descriptor['protocol_revision'] == '3.7'
    code = '''import json,sys,numpy as np
from pathlib import Path
from operon.targets import activate
from operon.plugins import load_runtime
state=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
state['_runtime_root']=str(Path(sys.argv[1]).parent)
activate(state); load_runtime(state)
from src.reader import read_source
path=Path(sys.argv[2]); np.save(path,np.array([[1.,2.]]))
out=read_source(path,['sample','feature'],{},reader_id='example.reader_example')
print(json.dumps(out.data.tolist()))
'''
    result = subprocess.run([sys.executable, '-c', code, str(manager.registry), str(tmp_path / 'input.npy')],
                            capture_output=True, text=True, encoding='utf-8', timeout=45)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.splitlines()[-1]) == [[1., 2.]]

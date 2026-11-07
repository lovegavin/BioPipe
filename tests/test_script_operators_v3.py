from pathlib import Path
import pytest

from operon.script_operators import inspect_script, extract_parameters, execute_script, parameter_candidates, inspect_script_environment

CODE = '''# input: data file.txt
# output: result file.txt
import argparse
from pathlib import Path
threshold = 3
parser = argparse.ArgumentParser()
parser.add_argument('--in-data')
parser.add_argument('--out-result')
args = parser.parse_args()
Path(args.out_result).write_text(Path(args.in_data).read_text() * threshold)
'''


def test_import_extract_bind_and_run_frozen_value(tmp_path):
    path = tmp_path / 'filter.py'
    path.write_text(CODE)
    snapshot = inspect_script(path)
    assert snapshot['inputs'] == {'data': {'kind': 'file', 'format': 'txt'}}
    assert inspect_script_environment(snapshot)['status'] == 'passed'
    result = extract_parameters(snapshot, ['threshold'])
    assert result['values'] == {'threshold': 3}
    assert result['script']['parameters_schema']['properties']['threshold']['default'] == 3
    editable = tmp_path / 'edited.py'
    editable.write_text(result['script']['code'], encoding='utf-8')
    assert inspect_script(editable)['inputs'] == snapshot['inputs']
    assert inspect_script(editable)['outputs'] == snapshot['outputs']
    source = tmp_path / 'source.txt'
    source.write_text('x')
    run = execute_script(result['script'], {'threshold': 2}, {'data': source}, tmp_path / 'run')
    assert Path(run['files']['result']).read_text() == 'xx'
    assert path.read_text() == CODE


def test_scope_reassignment_and_duplicate_literals_are_not_rewritten(tmp_path):
    assert parameter_candidates('x = 3\nx = 4\n') == []
    assert parameter_candidates('x = 3\ndef f():\n    x = 4\n') == []
    path = tmp_path / 'filter.py'
    path.write_text(CODE + '\nother = 3\n')
    result = extract_parameters(inspect_script(path), ['threshold'])
    assert 'other = 3' in result['script']['code']


def test_missing_output_zero_exit_fails(tmp_path):
    path = tmp_path / 'missing.py'
    path.write_text('# output: result file.txt\n')
    with pytest.raises(ValueError, match='did not create'):
        execute_script(inspect_script(path), {}, {}, tmp_path / 'run')


def test_script_failure_surfaces_bounded_native_log_without_losing_full_file(tmp_path):
    path = tmp_path / 'failure.py'
    path.write_text('# output: result file.txt\nprint("x" * 20000)\nraise RuntimeError("specific-failure")\n')
    with pytest.raises(RuntimeError, match='specific-failure') as error:
        execute_script(inspect_script(path), {}, {}, tmp_path / 'run')
    log = tmp_path / 'run/console.log'
    assert str(log) in str(error.value)
    assert len(str(error.value)) < 9000
    assert log.stat().st_size > 20000


def test_hash_tampering_and_missing_dependency(tmp_path):
    path = tmp_path / 'script.py'
    path.write_text('# output: result file.txt\n')
    snapshot = inspect_script(path)
    snapshot['dependencies'] = ['operon-impossible-missing-package-test==999']
    assert inspect_script_environment(snapshot)['status'] == 'failed'
    snapshot['code'] += 'pass\n'
    with pytest.raises(ValueError, match='hash'):
        execute_script(snapshot, {}, {}, tmp_path / 'run')


def test_cancel_terminates_owned_process(tmp_path):
    path = tmp_path / 'sleep.py'
    path.write_text('# output: result file.txt\nimport time\ntime.sleep(30)\n')
    with pytest.raises(RuntimeError, match='cancelled'):
        execute_script(inspect_script(path), {}, {}, tmp_path / 'run', cancel=lambda: True)


def test_selected_dependency_directory_reaches_child(tmp_path, monkeypatch):
    import sys
    dependency = tmp_path / 'isolated-target'
    dependency.mkdir()
    (dependency / 'v3_selected_library.py').write_text('VALUE = "isolated"\n')
    metadata = dependency / 'v3_selected_library-2.0.dist-info'
    metadata.mkdir()
    (metadata / 'METADATA').write_text('Metadata-Version: 2.1\nName: v3-selected-library\nVersion: 2.0\n')
    monkeypatch.syspath_prepend(str(dependency))
    source = tmp_path / 'script.py'
    source.write_text('''# output: result file.txt
# /// script
# dependencies = ["v3-selected-library==2.0"]
# ///
import argparse
from pathlib import Path
from v3_selected_library import VALUE
p=argparse.ArgumentParser()
p.add_argument('--out-result')
Path(p.parse_args().out_result).write_text(VALUE)
''')
    snapshot = inspect_script(source)
    assert inspect_script_environment(snapshot)['status'] == 'passed'
    result = execute_script(snapshot, {}, {}, tmp_path / 'run')
    assert Path(result['files']['result']).read_text() == 'isolated'


def test_promoted_provider_static_package_and_real_worker(tmp_path, monkeypatch):
    import json
    import subprocess
    import sys
    from operon.script_operators import export_script_package
    from operon.developer import check_source, embed_manifest
    from operon.dropins import write_wheel
    from operon.plugins import PluginManager
    monkeypatch.setenv('TEMP', str(tmp_path))
    monkeypatch.setenv('TMP', str(tmp_path))
    source = tmp_path / 'repeat.py'
    source.write_text(CODE)
    snapshot = extract_parameters(inspect_script(source), ['threshold'])['script']
    project = tmp_path / 'project'
    exported = export_script_package(snapshot, project, operator_id='lab.repeat_text', title='Repeat text', category='data')
    manifest = check_source(project)
    descriptor = manifest['descriptors'][0]
    assert descriptor['id'] == 'lab.repeat_text'
    assert descriptor['protocol_revision'] == '3.7'
    assert descriptor['data_formats'] == {
        'inputs': [{'logical_type': 'file_artifact', 'representations': ['file_artifact']}],
        'outputs': [{'logical_type': 'file_artifact', 'representations': ['file_artifact']}],
    }
    assert descriptor['parameters_schema']['properties']['threshold']['default'] == 3
    assert descriptor['documentation']
    assert exported['module'] not in sys.modules
    # Editing library defaults does not alter code identity or overwrite the
    # independently saved route value (4) used by the actual worker below.
    parameter_file = Path(exported['parameters'])
    schema = json.loads(parameter_file.read_text(encoding='utf-8'))
    schema['properties']['threshold']['default'] = 9
    parameter_file.write_text(json.dumps(schema), encoding='utf-8')
    updated = check_source(project)
    assert updated['descriptors'][0]['code_sha'] == descriptor['code_sha']
    assert updated['descriptors'][0]['declaration_sha'] != descriptor['declaration_sha']
    manifest = updated
    entries = {p.relative_to(project).as_posix(): p.read_bytes() for p in project.rglob('*') if p.is_file() and p.suffix in {'.py', '.json', '.md'}}
    wheel = write_wheel(entries, exported['package'], exported['version'], manifest['dependencies'], tmp_path / 'wheel')
    embed_manifest(wheel, manifest)
    manager = PluginManager(tmp_path / 'profile', source_root=None)
    manager.install(wheel)
    data = tmp_path / 'input.txt'
    data.write_text('x')
    code = '''import sys,json
from pathlib import Path
from operon.targets import activate
from operon.plugins import load_runtime
state=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
state['_runtime_root']=str(Path(sys.argv[1]).parent)
activate(state); load_runtime(state)
from src.task import Context, run
from src.core import FileArtifact
spec={'name':'lab.repeat_text','inputs':['data'],'params':{'threshold':4,'output':'result'}}
ctx=Context(Path(sys.argv[3]),{'sources':{},'steps':[spec]})
ctx['data']=FileArtifact('txt',{'data':sys.argv[2]})
try:
    run(ctx,[spec])
    value=Path(next(iter(ctx['result'].files.values()))).read_text()
    print(json.dumps({'value':value,'params':spec['params']}))
finally:
    ctx.finalize()
'''
    result = subprocess.run([sys.executable, '-c', code, str(manager.registry), str(data), str(tmp_path / 'job')],
                            cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout.splitlines()[-1])['value'] == 'xxxx'

import json
from pathlib import Path
import subprocess
import sys

import pytest

from operon.workflow_spec import compile_spec, export_workflow, init_workflow, load_workflow, parse, format_workflow


def spec():
    return {'format': 'operon.workflow', 'schema_version': 1, 'name': 'Branches',
            'sources': {'matrix': {'path': 'data.csv'}},
            'steps': {'pca.a': {'operator': 'pca', 'inputs': {'in0': 'sources.matrix'}},
                      'pca_b': {'operator': 'pca', 'inputs': {'in0': 'steps.pca.a.out'}}},
            'parameters': {'steps': {'pca.a': {'params': {'n_components': 0, 'flag': False, 'optional': None, 'empty': []}}}},
            'outputs': {'scores': 'steps.pca_b.out'}}


def test_branched_roundtrip_frozen_values_paths(tmp_path):
    source = spec()
    source['steps']['branch'] = {'operator': 'pca', 'inputs': {'in0': 'sources.matrix'}}
    graph = compile_spec(source, tmp_path)
    assert graph['nodes'][0]['source']['path'] == str(tmp_path / 'data.csv')
    output = tmp_path / 'another' / 'project'
    export_workflow(graph, output)
    restored = load_workflow(output / 'workflow.yaml')
    assert restored == graph
    values = json.loads((output / 'parameters.json').read_text())
    assert values['steps']['pca.a']['params'] == {'n_components': 0, 'flag': False, 'optional': None, 'empty': []}
    assert 'n_components' not in (output / 'workflow.yaml').read_text()


@pytest.mark.parametrize('text', ['a: 1\na: 2', 'x: !!python/object/apply:os.system [bad]', 'a: &a [*a]', 'a: &x 1\nb: *x', '3: bad', 'x: .nan'])
def test_safe_yaml_rejects_ambiguous_or_executable_documents(text):
    with pytest.raises((ValueError, TypeError)):
        parse(text)


def test_yaml12_boolean_names_and_duplicate_ports(tmp_path):
    assert parse('on: off\nflag: false') == {'on': 'off', 'flag': False}
    value = spec()
    value['steps']['pca.a']['inputs']['in-0'] = 'sources.matrix'
    with pytest.raises(ValueError, match='Duplicate target port'):
        compile_spec(value, tmp_path)


def test_reject_cycle_unknown_node_field_and_bad_reference(tmp_path):
    value = spec()
    value['steps']['pca.a']['inputs']['in0'] = 'steps.pca_b.out'
    with pytest.raises(ValueError, match='cycle'):
        compile_spec(value, tmp_path)
    value = spec()
    value['steps']['pca.a']['unknown'] = 1
    with pytest.raises(ValueError, match='Unknown'):
        compile_spec(value, tmp_path)
    value = spec()
    value['steps']['pca.a']['inputs']['in0'] = 'steps.nope.out'
    with pytest.raises(ValueError, match='undefined'):
        compile_spec(value, tmp_path)


def test_init_format_and_cli_do_not_start_service(tmp_path):
    project = tmp_path / 'project'
    init_workflow(project)
    document = project / 'workflow.yaml'
    initialized = load_workflow(document)
    assert initialized['nodes'][0]['source']['reader'] == 'CsvReader'
    assert initialized['nodes'][1]['params'] == {'dim': 'feature', 'n_components': 2}
    from src.task.manifest import _validate_sources
    source = initialized['nodes'][0]['source']
    _validate_sources({'matrix': {k: v for k, v in source.items() if k != 'location'}})
    assert initialized['nodes'][0]['source']['labels']['sample'] == {'feature': 0}
    before = (project / 'parameters.json').read_bytes()
    document.write_text(document.read_text() + '\n')
    assert format_workflow(document, check=True)['changed']
    assert format_workflow(document)['changed']
    assert not format_workflow(document, check=True)['changed']
    assert (project / 'parameters.json').read_bytes() == before
    result = subprocess.run([sys.executable, '-m', 'operon', '--profile-dir', str(tmp_path / 'profile'), 'workflow', 'lint', str(document)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['valid']
    assert not (tmp_path / 'profile').exists()


def test_remote_source_namespace_preserved(tmp_path):
    value = spec()
    value['sources']['matrix'] = {'path': '/server/data.csv', 'location': {'kind': 'ssh', 'profile_id': 'server'}}
    assert compile_spec(value, tmp_path)['nodes'][0]['source']['path'] == '/server/data.csv'


def test_export_preserves_existing_directory(tmp_path):
    marker = tmp_path / 'important.txt'
    marker.write_text('keep')
    with pytest.raises(ValueError, match='empty'):
        export_workflow(compile_spec(spec(), tmp_path), tmp_path)
    assert marker.read_text() == 'keep'
@pytest.mark.parametrize('field', ['parameters_file', 'execution_file', 'lock_file', 'ui_file'])
def test_metadata_resources_cannot_escape_project(tmp_path, field):
    from operon.workflow_spec import compile_spec, WorkflowError
    spec = {'format': 'operon.workflow', 'schema_version': 1, 'sources': {}, 'steps': {}, field: '../outside.json'}
    with pytest.raises(WorkflowError, match='escapes'):
        compile_spec(spec, tmp_path)


def test_archive_input_base_and_metadata_containment(tmp_path):
    from io import BytesIO
    from zipfile import ZipFile, ZIP_DEFLATED
    import yaml
    from src.web.models import Graph
    from operon.workflow_archive import export_archive, import_archive
    from operon.workflow_spec import WorkflowError
    original = tmp_path / 'original-project'
    original.mkdir()
    staging = tmp_path / 'staging'
    staging.mkdir()
    graph = Graph.model_validate(compile_spec(spec(), original))
    graph.base_dir = str(original)
    graph.nodes[0].source.path = 'data.csv'
    packed = export_archive(graph, staging)
    restored = import_archive(packed, staging, tmp_path / 'another-project')
    assert restored['nodes'][0]['source']['path'] == str(original / 'data.csv')
    assert str(staging) not in json.dumps(restored)
    with ZipFile(BytesIO(packed)) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    document = yaml.safe_load(files['workflow.yaml'])
    document['parameters_file'] = '../outside.json'
    files['workflow.yaml'] = yaml.safe_dump(document).encode()
    unsafe = BytesIO()
    with ZipFile(unsafe, 'w', ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    with pytest.raises(WorkflowError, match='escapes'):
        import_archive(unsafe.getvalue(), staging, original)

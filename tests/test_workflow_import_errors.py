import json
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from operon.workflow_spec import compile_spec
from src.web.api import create_app
from src.web.service import Settings


def document():
    return {'format': 'operon.workflow', 'schema_version': 1, 'sources': {}, 'steps': {}}


@pytest.mark.parametrize('field', ['parameters_file', 'execution_file', 'lock_file', 'ui_file', 'script'])
def test_missing_project_resource_is_actionable_validation_error(tmp_path, field):
    value = document()
    if field == 'script':
        value['steps']['custom'] = {'script': 'custom.py', 'inputs': {}}
        filename = 'custom.py'
    else:
        filename = field + '.json'
        value[field] = filename
    with pytest.raises(ValueError) as caught:
        compile_spec(value, tmp_path)
    error = caught.value
    assert error.code == 'workflow_resource_error'
    assert error.details['reason'] == 'missing'
    assert error.details['resource'] == filename
    assert error.details['directory'] == str(tmp_path.resolve())
    assert 'base directory' in str(error)


def test_import_error_is_json_and_retry_preserves_frozen_values(tmp_path):
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    app = create_app(Settings(workspace, workspace / '.studio', tmp_path / 'dist',
                              testing=True, builtin_routes=False))
    value = document()
    value['parameters_file'] = 'parameters.json'
    text = yaml.safe_dump(value)
    with TestClient(app, raise_server_exceptions=False) as client:
        client.headers['X-Studio-Token'] = client.get('/api/bootstrap').json()['token']
        missing = client.post('/api/import', json={'text': text, 'base_dir': '.'})
        assert missing.status_code == 422, missing.text
        assert missing.json()['code'] == 'workflow_resource_error'
        assert missing.json()['details']['resource'] == 'parameters.json'
        assert client.get('/health').status_code == 200
        project = workspace / 'project'
        project.mkdir()
        frozen = {'params': {'scale': 3}}
        (project / 'parameters.json').write_text(json.dumps(frozen))
        recovered = client.post('/api/import', json={'text': text, 'base_dir': 'project'})
        assert recovered.status_code == 200, recovered.text
        assert recovered.json()['params'] == {'scale': 3}
        assert json.loads((project / 'parameters.json').read_text()) == frozen


@pytest.mark.parametrize('content,reason', [(b'{"broken":', 'invalid_json'), (b'\xff', 'encoding')])
def test_bad_sidecar_identifies_file_without_exposing_contents(tmp_path, content, reason):
    value = document()
    value['parameters_file'] = 'parameters.json'
    (tmp_path / 'parameters.json').write_bytes(content)
    with pytest.raises(ValueError) as caught:
        compile_spec(value, tmp_path)
    assert caught.value.code == 'workflow_resource_error'
    assert caught.value.details['reason'] == reason
    assert 'parameters.json' in str(caught.value)


def test_directory_in_place_of_sidecar_is_validation_error(tmp_path):
    (tmp_path / 'parameters.json').mkdir()
    value = {**document(), 'parameters_file': 'parameters.json'}
    with pytest.raises(ValueError) as caught:
        compile_spec(value, tmp_path)
    assert caught.value.code == 'workflow_resource_error'
    assert caught.value.details['reason'] == 'not_file'


def test_invalid_script_identifies_source(tmp_path):
    value = document()
    value['steps']['custom'] = {'script': 'custom.py', 'inputs': {}}
    (tmp_path / 'custom.py').write_text('def broken(:\n')
    with pytest.raises(ValueError) as caught:
        compile_spec(value, tmp_path)
    assert caught.value.details['reason'] == 'invalid_script'
    assert caught.value.details['resource'] == 'custom.py'


def test_outside_workspace_import_explains_allowed_base_directory(tmp_path):
    workspace = tmp_path / 'workspace'; workspace.mkdir()
    app = create_app(Settings(workspace, workspace / '.studio', tmp_path / 'dist',
                              testing=True, builtin_routes=False))
    with TestClient(app, raise_server_exceptions=False) as client:
        client.headers['X-Studio-Token'] = client.get('/api/bootstrap').json()['token']
        response = client.post('/api/import', json={'text': yaml.safe_dump(document()), 'base_dir': '..'})
    assert response.status_code == 422
    assert response.json()['code'] == 'invalid_workflow'
    assert 'workspace' in response.json()['message']

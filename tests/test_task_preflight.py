"""Task preflight uses frozen metadata without executing scientific readers."""
from copy import deepcopy
import json

from operon.packages import bundled_state
from src.task.check import check_manifest


def task():
    return {'sources': {'input': {'path': 'data.csv', 'reader': 'CsvReader',
            'dims': ['sample', 'feature'], 'labels': {}, 'args': {'header': True}}},
            'steps': [{'name': 'pca', 'inputs': ['input'],
                       'params': {'dim': 'feature', 'n_components': 2, 'output': 'pcs'}}]}


def test_preflight_uses_metadata_and_keeps_inputs_read_only(tmp_path, monkeypatch):
    import operon_sdk.declarations
    def forbidden(*args, **kwargs):
        raise AssertionError('Preflight must not import scientific implementations')
    monkeypatch.setattr(operon_sdk.declarations, 'load_class', forbidden)
    source = tmp_path / 'data.csv'
    source.write_bytes(b'invalid CSV bytes intentionally never parsed\x00')
    value = task()
    before = deepcopy(value)
    assert check_manifest(tmp_path, value)['ok']
    assert value == before
    assert source.read_bytes() == b'invalid CSV bytes intentionally never parsed\x00'
    assert not (tmp_path / 'output').exists()


def test_preflight_uses_the_tasks_frozen_plugin_catalog(tmp_path):
    (tmp_path / 'data.csv').write_text('x\n1\n')
    value = task()
    value['steps'][0]['name'] = 'saved_custom_pca'
    assert not check_manifest(tmp_path, value)['ok']
    state = deepcopy(bundled_state(manifest_only=True))
    descriptor = next(d for d in state['descriptors'] if d['id'] == 'pca')
    descriptor['id'] = 'saved_custom_pca'
    (tmp_path / 'plugins.lock.json').write_text(json.dumps(state), encoding='utf-8')
    report = check_manifest(tmp_path, value)
    assert report['ok'], report
    assert report['steps'][0]['name'] == 'saved_custom_pca'


def test_preflight_rejects_missing_inputs_bad_parameters_and_unknown_readers(tmp_path):
    value = task()
    missing = check_manifest(tmp_path, value)
    assert not missing['ok'] and missing['errors'][0]['where'] == 'source:input'
    (tmp_path / 'data.csv').write_text('x\n1\n')
    value['steps'][0]['params']['n_components'] = 'two'
    assert not check_manifest(tmp_path, value)['ok']
    value['steps'][0]['params']['n_components'] = 2
    value['sources']['input']['reader'] = 'MissingReader'
    report = check_manifest(tmp_path, value)
    assert not report['ok'] and 'MissingReader' in report['errors'][0]['message']


def test_local_preflight_allows_declared_sibling_input_without_relaxing_studio(tmp_path):
    import pytest
    import yaml
    from src.web.graph import GraphError, import_manifest
    from src.web.operator_catalog import catalog_from_descriptors
    directory = tmp_path / 'task'
    directory.mkdir()
    (tmp_path / 'data.csv').write_text('x\n1\n')
    value = task()
    value['sources']['input']['path'] = '../data.csv'
    assert check_manifest(directory, value)['ok']
    catalog = catalog_from_descriptors(bundled_state(manifest_only=True)['descriptors'])
    with pytest.raises(GraphError):
        import_manifest(yaml.safe_dump(value), '.', catalog, directory)
    (tmp_path / 'data.csv').unlink()
    report = check_manifest(directory, value)
    assert not report['ok'] and report['errors'][0]['where'] == 'source:input'

"""Compatible model defaults do not republish unchanged library routes."""
from copy import deepcopy
import json

from biopipe.packages import bundled_state
from biopipe.registry import build_routes
from biopipe_sdk.protocol import catalog_entry


def route_fixture(tmp_path):
    route = tmp_path / 'routes' / 'example'
    route.mkdir(parents=True)
    task = {
        'name': 'Frozen log transform',
        'sources': {'data': {'path': 'input.csv', 'reader': 'CsvReader',
                             'dims': ['sample', 'feature'], 'labels': {}}},
        'steps': [{'name': 'log_transform', 'inputs': ['data'],
                   'params': {'output': 'logged', 'base': 2, 'pseudocount': 1}}],
    }
    source = route / 'task.yaml'
    source.write_text(json.dumps(task), encoding='utf-8')
    descriptors = bundled_state()['descriptors']
    catalog = {'schema_version': 1,
               'operators': [catalog_entry(d) for d in descriptors if d['id'] == 'log_transform'],
               'readers': [catalog_entry(d) for d in descriptors if d['id'] == 'CsvReader']}
    original, errors = build_routes(tmp_path, catalog, {})
    assert not errors
    old = deepcopy(original)
    old['routes'][0]['version'] = 7
    for node in old['routes'][0]['graph']['nodes']:
        node.pop('script')
    for edge in old['routes'][0]['graph']['edges']:
        edge.pop('adaptation')
    return source, task, catalog, old


def test_new_optional_fields_preserve_old_serialization_and_route_version(tmp_path):
    _, _, catalog, old = route_fixture(tmp_path)
    before = deepcopy(old)
    current, errors = build_routes(tmp_path, catalog, old)
    assert not errors
    assert current == before
    assert old == before


def test_actual_parameter_change_still_publishes_a_new_route_version(tmp_path):
    source, task, catalog, old = route_fixture(tmp_path)
    task['steps'][0]['params']['base'] = 10
    source.write_text(json.dumps(task), encoding='utf-8')
    current, errors = build_routes(tmp_path, catalog, old)
    assert not errors
    assert current['routes'][0]['version'] == 8
    node = next(n for n in current['routes'][0]['graph']['nodes'] if n['kind'] == 'operator')
    assert node['params']['base'] == 10
    original_node = next(n for n in old['routes'][0]['graph']['nodes'] if n['kind'] == 'operator')
    assert original_node['params']['base'] == 2

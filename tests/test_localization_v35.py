"""Language packs are static, optional presentation data, never execution identity."""
from copy import deepcopy
import json
from pathlib import Path
import zipfile

import pytest

from operon.dropins import single_file_wheel, module_assets
from operon.install_targets import execution_digest, wheel_entries
from operon_sdk.declarations import compile_declaration, source_declarations
from operon_sdk.localization import LanguagePack, project, localized_text
from test_operator_docs import extension


def localized(tmp_path, unsafe=False):
    path, _ = extension(tmp_path, unsafe=unsafe)
    path.write_text(path.read_text(encoding='utf-8').replace('class Answer(Step):',
        'class Answer(Step):\n    localization_file = "answer.i18n.json"'), encoding='utf-8')
    pack = {'default_locale': 'en', 'translations': {
        'en': {'title': 'Answer', 'description': 'Original explanation', 'parameters': {'answer': {'title': 'Answer value'}}},
        'zh': {'title': '答案'}, 'zh-CN': {'parameters': {'answer': {'title': '答案取值'}}}}}
    resource = tmp_path / 'answer.i18n.json'
    resource.write_text(json.dumps(pack, ensure_ascii=False), encoding='utf-8')
    return path, resource


def compile_path(path):
    return compile_declaration(source_declarations(path, path.stem)[0], path.parent)


def test_v35_static_discovery_fallback_and_no_semantic_mutations(tmp_path):
    path, resource = localized(tmp_path, unsafe=True)
    before = compile_path(path)  # Top-level code raises if discovery imports it.
    assert before['protocol_version'] == 3 and before['protocol_revision'] == '3.5'
    assert 'answer.i18n.json' in module_assets(path)
    translated = project(before, 'zh-CN')
    assert translated['title'] == '答案'
    assert translated['description'] == 'Original explanation'
    assert translated['parameters_schema']['properties']['answer']['title'] == '答案取值'
    assert translated['parameters_schema']['properties']['answer']['default'] == 7
    assert translated['resources'] == before['resources']
    assert project(before, 'fr')['title'] == 'Answer'
    assert before['title'] == 'lab.documented'
    resource.write_text(resource.read_text(encoding='utf-8').replace('答案', '回答'), encoding='utf-8')
    after = compile_path(path)
    assert after['code_sha'] == before['code_sha']
    assert after['declaration_sha'] != before['declaration_sha']


def test_v3_without_language_pack_is_unchanged(tmp_path):
    path, _ = extension(tmp_path)
    value = compile_path(path)
    assert 'protocol_revision' not in value and 'localization' not in value
    assert project(value, 'en') == value


def test_exact_locale_wins_when_also_the_default():
    value = localized_text({'default_locale': 'zh-CN', 'translations': {
        'zh-CN': {'title': 'Exact'}, 'zh': {'title': 'Base', 'description': 'Shared'}
    }}, 'zh-CN')
    assert value == {'title': 'Exact', 'description': 'Shared'}


@pytest.mark.parametrize('change', ['path', 'parameter', 'default', 'enum', 'locale'])
def test_invalid_packs_fail_before_import(tmp_path, change):
    path, resource = localized(tmp_path, unsafe=True)
    pack = json.loads(resource.read_text(encoding='utf-8'))
    if change == 'path':
        path.write_text(path.read_text(encoding='utf-8').replace('answer.i18n.json', '../escape.json'), encoding='utf-8')
    elif change == 'parameter':
        pack['translations']['en']['parameters']['typo'] = {'title': 'Missing'}
    elif change == 'default':
        pack['translations']['en']['parameters']['answer']['default'] = 999
    elif change == 'enum':
        pack['translations']['en']['parameters']['answer']['enum_labels'] = {'"missing"': 'Invalid'}
    else:
        pack['translations']['EN'] = {}
    resource.write_text(json.dumps(pack), encoding='utf-8')
    with pytest.raises(ValueError): compile_path(path)


def test_wheel_integrity_and_translation_only_execution_identity(tmp_path):
    path, resource = localized(tmp_path)
    first = single_file_wheel(path, tmp_path / 'first')
    identity = execution_digest(first)
    resource.write_text(resource.read_text(encoding='utf-8').replace('答案', '回答'), encoding='utf-8')
    second = single_file_wheel(path, tmp_path / 'second')
    assert first.read_bytes() != second.read_bytes()
    assert execution_digest(second) == identity
    for missing in (False, True):
        damaged = tmp_path / ('missing.whl' if missing else 'damaged.whl')
        with zipfile.ZipFile(first) as original, zipfile.ZipFile(damaged, 'w') as output:
            for name in original.namelist():
                if name.endswith('answer.i18n.json'):
                    if not missing: output.writestr(name, resource.read_bytes())
                else: output.writestr(name, original.read(name))
        with pytest.raises(ValueError, match='[Ll]anguage pack'): wheel_entries(damaged)


def test_translation_refresh_and_fresh_profile_keep_frozen_values(tmp_path, monkeypatch):
    from operon.plugins import PluginManager
    from src.web.models import Graph
    from src.web.parameters import export_bundle, import_bundle, freeze_graph
    from test_packages import run_worker
    from operon.bytecode import io_path
    path, resource = localized(tmp_path)
    first = single_file_wheel(path, tmp_path / 'v1')
    manager = PluginManager(tmp_path / 'profile', source_root=None, manifest_only=True)
    initial = manager.install(first)
    graph = manager.pin(Graph.model_validate({'name': 'frozen', 'nodes': [
        {'id': 'answer', 'kind': 'operator', 'operator': 'lab.documented', 'params': {'answer': 42}, 'position': {'x': 0, 'y': 0}}
    ], 'edges': []}))
    graph = freeze_graph(graph, manager.extend_catalog({'operators': [], 'readers': []}), tmp_path)
    exported = export_bundle(graph)
    resource.write_text(resource.read_text(encoding='utf-8').replace('答案', '回答'), encoding='utf-8')
    second = single_file_wheel(path, tmp_path / 'v2')
    with monkeypatch.context() as guard:
        guard.setattr('operon.install_targets.install', lambda *a, **k: pytest.fail('translation update reinstalled dependencies'))
        updated = manager.install(second)
    assert updated['code_paths'] == initial['code_paths']
    fresh = PluginManager(tmp_path / 'fresh', source_root=None, manifest_only=True)
    fresh.install(second)
    restored = fresh.pin(import_bundle(exported))
    assert restored.nodes[0].params['answer'] == 42
    _, summary = run_worker(fresh, fresh.snapshot(restored), tmp_path / 'run', {},
                           [{'name': 'lab.documented', 'inputs': [], 'params': restored.nodes[0].params}])
    result = json.loads(io_path(tmp_path / 'run/output' / summary['steps'][0]['export_path']).read_text())
    assert result == {'answer': 42}


@pytest.mark.parametrize('kind', ['operator', 'reader'])
def test_sdk_scaffolds_valid_language_pack(tmp_path, kind):
    from operon.developer import scaffold, check_source
    scaffold(tmp_path / kind, kind)
    descriptor = check_source(tmp_path / kind)['descriptors'][0]
    assert descriptor['localization']['minimum_sdk'] == '3.5.0'
    assert project(descriptor, 'zh-CN')['title'] != descriptor['title']


def test_documented_example_runs_with_independent_parameter_values():
    import numpy as np
    from operon_sdk import Form
    from operon_sdk.testing import run_operator
    from examples.localized_operator.scale import Scale
    form = Form(np.array([[1., 2.], [3., 4.]]), ['sample', 'feature'],
                {'sample': {'s1': 0, 's2': 1}, 'feature': {'a': 0, 'b': 1}}, {'missing_code': float('nan')})
    output = run_operator(Scale, [form], {'scale_factor': 3.0})
    np.testing.assert_array_equal(output.data, form.data * 3)
    assert output.dims == form.dims and output.labels == form.labels

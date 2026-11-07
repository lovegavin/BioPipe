"""Documentation is discoverable offline and never changes executable identity."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import zipfile

import pytest

from extension_fixtures import write_extension
from biopipe.dropins import single_file_wheel
from biopipe.install_targets import execution_digest, wheel_entries
from biopipe.operator_docs import OperatorDocs
from biopipe.plugins import PluginManager
from biopipe_sdk.declarations import compile_declaration, source_declarations

SOURCE = '''from biopipe_sdk import Step
class Answer(Step):
    name = "lab.documented"
    description = "Return a configured answer for reproducible tests."
    input_contracts = []
    output_contract = {"mode": "report"}
    parameters_schema = {"type": "object", "additionalProperties": False, "properties": {"answer": {"type": "integer", "default": 7}}}
    def run(self, ctx, inputs): self.answer = ctx.step_params["answer"]
    def export(self, ctx): return {"answer": self.answer}
'''


def extension(tmp_path, *, unsafe=False):
    path = tmp_path / 'answer.py'
    write_extension(path, ('raise AssertionError("must not import")\n' if unsafe else '') + SOURCE)
    markdown = path.with_suffix('.md')
    markdown.write_text('# Answer\n\n## Purpose\n\nReturn a configured answer.\n\n## Examples\n\nUse answer=7.\n', encoding='utf-8')
    return path, markdown


@pytest.mark.parametrize('nested_library', [False, True])
def test_release_history_verifies_the_actual_library_root(tmp_path, nested_library):
    from biopipe.registry import maintain
    from scripts.record_bundled_history import record

    release = tmp_path / 'verified-release'
    seed = release / 'library/seed' if nested_library else release
    operators = seed / 'src/task/step/steps'
    operators.mkdir(parents=True)
    (seed / 'src/reader/readers').mkdir(parents=True)
    implementation, _ = extension(operators, unsafe=True)
    implementation.write_text(implementation.read_text(encoding='utf-8').replace(
        'class Answer(Step):', 'class Answer(Step):\n    provider = "lab-docs"'), encoding='utf-8')
    built = maintain('build', root=seed, scope='packages')
    assert not built['errors'], built
    commit = 'a' * 40  # Synthetic provenance, never a shipped compatibility receipt.
    (release / 'package-manifest.json').write_text(json.dumps({
        'source_commit': commit, 'version': '1.0.0'}), encoding='utf-8')
    history = tmp_path / 'history.json'
    assert record(release, 'v1.0.0', commit, history) == 2
    before = history.read_bytes()
    assert record(release, 'v1.0.0', commit, history) == 2
    assert history.read_bytes() == before
    # An edited release must still fail closed; resolving its nested seed must
    # not turn source verification into trusting only the manifest.
    implementation.write_text(implementation.read_text(encoding='utf-8') + '\nCHANGED = True\n', encoding='utf-8')
    with pytest.raises(ValueError, match='source differs'):
        record(release, 'v1.0.0', commit, history)
    assert history.read_bytes() == before


def test_static_docs_search_lazy_sections_and_validation(tmp_path, monkeypatch):
    path, markdown = extension(tmp_path, unsafe=True)
    descriptor = compile_declaration(source_declarations(path, 'answer')[0], tmp_path)
    assert descriptor['documentation']['sections'] == ['answer', 'purpose', 'examples']
    state = {'generation': 'test', 'packages': [{'name': 'test'}],
             'descriptors': [{**descriptor, 'distribution': 'test'}]}
    class Manager:
        directory = tmp_path / 'profile'
        def state(self): return state
    docs = OperatorDocs(Manager())
    monkeypatch.setattr('biopipe.operator_docs.document_bytes', lambda *args: pytest.fail('search read Markdown'))
    assert docs.search('configured')['items'][0]['id'] == 'lab.documented'
    assert 'content' not in docs.describe(['lab.documented'])['items'][0]['documentation']
    generated = docs.describe(['lab.documented'], sections=['parameters'])
    # Even when asking only for a generated section no Markdown needs loading.
    assert 'answer' in generated['items'][0]['documentation']['content']['parameters']
    with pytest.raises(ValueError, match='limit'):
        docs.search(limit=1000)
    with pytest.raises(ValueError, match='generation'):
        docs.describe(['lab.documented'], generation='../escape')
    raw = source_declarations(path, 'answer')[0]
    raw['documentation'] = {'path': '../escape.md'}
    with pytest.raises(ValueError, match='inside'):
        compile_declaration(raw, tmp_path)
    # Maintenance must apply the same path containment before writing any page.
    from scripts.build_operator_docs import build
    source_dir = tmp_path / 'source/src/task/step/steps'
    source_dir.mkdir(parents=True)
    source, _ = extension(source_dir)
    source.write_text(source.read_text().replace('class Answer(Step):',
        'class Answer(Step):\n    documentation_file = "../escape.md"'), encoding='utf-8')
    result = build(tmp_path / 'source')
    assert result['errors'] and 'inside' in result['errors'][0]['error']
    assert not (source_dir.parent / 'escape.md').exists()


def test_documentation_loads_from_deep_install_without_importing_operator(tmp_path, monkeypatch):
    from biopipe.bytecode import io_path
    from biopipe.operator_docs import document_bytes
    from types import SimpleNamespace
    source, markdown = extension(tmp_path, unsafe=True)
    descriptor = compile_declaration(source_declarations(source, 'answer')[0], tmp_path)
    deep = tmp_path / 'installed'
    while len(str(deep)) < 280:
        deep /= 'documentation' * 3
    io_path(deep).mkdir(parents=True)
    io_path(deep / source.name).write_bytes(source.read_bytes())
    io_path(deep / markdown.name).write_bytes(markdown.read_bytes())
    monkeypatch.setattr('biopipe.library_location.source_root', lambda: deep)
    manager = SimpleNamespace(directory=tmp_path / 'new-profile')
    assert document_bytes(manager, {}, descriptor) == markdown.read_bytes()


def test_documented_wheel_checks_integrity_and_only_docs_are_nonexecuting(tmp_path):
    path, markdown = extension(tmp_path)
    first = single_file_wheel(path, tmp_path / 'first')
    before = execution_digest(first)
    markdown.write_text(markdown.read_text() + '\nMore interpretation.\n', encoding='utf-8')
    second = single_file_wheel(path, tmp_path / 'second')
    assert first.read_bytes() != second.read_bytes()
    assert execution_digest(second) == before
    parameter = next(tmp_path.glob('*.parameters.json'))
    value = json.loads(parameter.read_text())
    value['properties']['answer']['default'] = 9
    parameter.write_text(json.dumps(value))
    assert execution_digest(single_file_wheel(path, tmp_path / 'third')) == before
    path.write_text(path.read_text().replace('return {"answer": self.answer}', 'return {"answer": self.answer + 1}'))
    assert execution_digest(single_file_wheel(path, tmp_path / 'changed-code')) != before
    damaged = tmp_path / first.name
    with zipfile.ZipFile(first) as archive, zipfile.ZipFile(damaged, 'w') as output:
        for name in archive.namelist():
            output.writestr(name, b'corrupt docs' if name.endswith('.md') else archive.read(name))
    with pytest.raises(ValueError, match='Documentation content hash'):
        wheel_entries(damaged)
    with zipfile.ZipFile(first) as archive, zipfile.ZipFile(tmp_path / 'asset.whl', 'w') as output:
        for name in archive.namelist():
            output.writestr(name, archive.read(name))
        output.writestr('answer_model.bin', b'additional runtime resource')
    assert execution_digest(tmp_path / 'asset.whl') != before


def test_markdown_identity_is_newline_independent_and_old_raw_cache_stays_valid(tmp_path):
    import hashlib
    from biopipe.operator_docs import cache_document, document_bytes
    from biopipe_sdk.documentation import verify_content
    path, markdown = extension(tmp_path)
    lf = markdown.read_text(encoding='utf-8').encode('utf-8')
    variants = [lf, lf.replace(b'\n', b'\r\n'), lf.replace(b'\n', b'\r')]
    declarations = []
    for content in variants:
        markdown.write_bytes(content)
        declarations.append(compile_declaration(source_declarations(path, 'answer')[0], tmp_path))
    assert declarations[0] == declarations[1] == declarations[2]
    metadata = declarations[0]['documentation']
    assert metadata['sha256'] == hashlib.sha256(lf).hexdigest()
    for content in variants:
        assert verify_content(content, metadata) == lf.decode('utf-8')
    historical = {**metadata, 'sha256': hashlib.sha256(variants[1]).hexdigest()}
    class Manager:
        directory = tmp_path / 'old-profile'
    cache_document(Manager(), historical, variants[1])
    archived = {**declarations[0], 'documentation': historical}
    assert document_bytes(Manager(), {}, archived) == variants[1]
    assert verify_content(variants[1], historical) == lf.decode('utf-8')
    with pytest.raises(ValueError, match='Documentation content hash'):
        verify_content(variants[1].replace(b'answer=7', b'answer=8'), historical)


def test_generator_writes_lf_and_does_not_rewrite_authored_pages(tmp_path):
    from scripts.build_operator_docs import build
    folder = tmp_path / 'src/task/step/steps'
    folder.mkdir(parents=True)
    _, authored = extension(folder)
    authored.unlink()
    assert not build(tmp_path)['errors']
    generated = folder / 'answer.Answer.md'
    expected = generated.read_bytes()
    assert b'\r' not in expected
    generated.write_bytes(expected.replace(b'\n', b'\r\n'))
    assert build(tmp_path, check=True)['changed']
    build(tmp_path)
    assert generated.read_bytes() == expected
    authored_bytes = b'# Authored\r\n\r\n## Purpose\r\n\r\nA reviewed-by-author guide.\r\n'
    generated.write_bytes(authored_bytes)
    result = build(tmp_path)
    assert result['authored_preserved'] == ['src/task/step/steps/answer.Answer.md']
    assert generated.read_bytes() == authored_bytes


def test_static_compiler_reuses_one_source_identity_and_detects_midbuild_edits(tmp_path, monkeypatch):
    import biopipe_sdk.declarations as declarations
    package = tmp_path / 'example'
    package.mkdir()
    path, _ = extension(package, unsafe=True)
    original_hash = declarations.code_hash
    observed = []
    def counted(entry, root):
        observed.append(entry)
        return original_hash(entry, root)
    monkeypatch.setattr(declarations, 'code_hash', counted)
    compiler = declarations.DeclarationCompiler(tmp_path)
    compiler.capture('example.answer')
    raw = source_declarations(path, 'example.answer')[0]
    for _ in range(25):
        assert compiler.compile(raw)['id'] == 'lab.documented'
    compiler.verify()
    assert len(observed) == 2  # Capture + publication check, not one walk per entry.
    path.write_text(path.read_text(encoding='utf-8') + '\n# edited during build\n', encoding='utf-8')
    with pytest.raises(ValueError, match='changed during registry'):
        compiler.verify()


def test_doc_only_update_reuses_environment_and_fresh_profile_runs_frozen_values(tmp_path, monkeypatch):
    from src.web.models import Graph
    from src.web.parameters import export_bundle, import_bundle, freeze_graph
    from test_packages import run_worker
    path, markdown = extension(tmp_path)
    first_wheel = single_file_wheel(path, tmp_path / 'v1')
    manager = PluginManager(tmp_path / 'profile', source_root=None, manifest_only=True)
    # Installing an extension must honor metadata-first discovery too, not scan
    # every bundled source repeatedly through the global discovery function.
    monkeypatch.setattr('biopipe.packages.bundled_state',
        lambda **kwargs: pytest.fail('install bypassed manager discovery policy'))
    from biopipe import install_targets
    original_install = install_targets.install
    def observed_install(active, *args, **kwargs):
        calls = []
        original_factory = active.bundled_state
        def factory():
            calls.append(True)
            return original_factory()
        with monkeypatch.context() as observation:
            observation.setattr(active, 'bundled_state', factory)
            result = original_install(active, *args, **kwargs)
        assert len(calls) == 1
        return result
    monkeypatch.setattr(install_targets, 'install', observed_install)
    first = manager.install(first_wheel)
    graph = manager.pin(Graph.model_validate({'name': 'frozen', 'nodes': [
        {'id': 'answer', 'kind': 'operator', 'operator': 'lab.documented', 'params': {'answer': 42}, 'position': {'x': 0, 'y': 0}}
    ], 'edges': []}))
    catalog = manager.extend_catalog({'operators': [], 'readers': []})
    graph = freeze_graph(graph, catalog, tmp_path)
    exported = export_bundle(graph)
    old_paths = deepcopy(first['code_paths'])
    old_doc = OperatorDocs(manager).describe(['lab.documented'], sections=['purpose'])['items'][0]['documentation']['content']
    markdown.write_text(markdown.read_text().replace('Return a configured answer.', 'A newer explanation of the same computation.'), encoding='utf-8')
    parameter = next(tmp_path.glob('*.parameters.json'))
    parameters = json.loads(parameter.read_text())
    parameters['properties']['answer']['default'] = 99
    parameter.write_text(json.dumps(parameters))
    second_wheel = single_file_wheel(path, tmp_path / 'v2')
    with monkeypatch.context() as guard:
        guard.setattr('biopipe.install_targets.install', lambda *args, **kwargs: pytest.fail('doc update reinstalled environment'))
        second = manager.install(second_wheel)
    assert second['code_paths'] == old_paths
    assert next(d for d in second['descriptors'] if d['id'] == 'lab.documented')['parameters_schema']['properties']['answer']['default'] == 99
    assert OperatorDocs(manager).describe(['lab.documented'], sections=['purpose'], generation=first['generation'])['items'][0]['documentation']['content'] == old_doc
    assert 'newer' in OperatorDocs(manager).describe(['lab.documented'], sections=['purpose'])['items'][0]['documentation']['content']['purpose']
    fresh = PluginManager(tmp_path / 'fresh', source_root=None, manifest_only=True)
    fresh.install(second_wheel)
    restored = import_bundle(exported)
    pinned = fresh.pin(restored)
    assert pinned.nodes[0].params['answer'] == 42
    state = fresh.snapshot(pinned)
    assert state['generation'] == fresh.state()['generation']
    _, summary = run_worker(fresh, state, tmp_path / 'run', {},
                            [{'name': 'lab.documented', 'inputs': [], 'params': pinned.nodes[0].params}])
    from biopipe.bytecode import io_path
    output = json.loads(io_path(tmp_path / 'run/output' / summary['steps'][0]['export_path']).read_text())
    assert output == {'answer': 42}


def test_sdk_scaffold_ships_markdown_and_testable_example(tmp_path):
    from biopipe.developer import scaffold, check_source
    project = tmp_path / 'scale_example'
    scaffold(project)
    descriptor = check_source(project)['descriptors'][0]
    assert descriptor['documentation']['path'] == '__init__.md'
    assert (project / 'tests/test_plugin.py').is_file()


def test_documented_csv_normalize_pca_example(tmp_path):
    from examples.documented_operators.run_example import run_example
    result = run_example(tmp_path / 'example')
    assert result['shape'] == [4, 2]
    assert result['synthetic'] is True
    assert (tmp_path / 'example/result.json').is_file()


def test_cold_profile_search_and_docs_import_no_implementations(tmp_path):
    import subprocess
    root = Path(__file__).resolve().parents[1]
    code = '''import json,sys
from pathlib import Path
from biopipe.plugins import PluginManager
from biopipe.operator_docs import OperatorDocs
docs=OperatorDocs(PluginManager(Path(sys.argv[1])))
found=docs.search("pca")
assert any(item["id"]=="pca" for item in found["items"])
detail=docs.describe(["pca"],sections=["purpose","parameters"])
assert detail["items"][0]["documentation"]["available"]
assert not [name for name in sys.modules if name.startswith(("src.task.step.steps.","src.reader.readers."))]
assert "numpy" not in sys.modules
print(json.dumps({"ok":True,"generation":found["generation"]}))
'''
    result = subprocess.run([sys.executable, '-c', code, str(tmp_path / 'profile')], cwd=root,
                            capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)['ok']


def test_long_profile_paths_keep_docs_cache_and_source_snapshots_usable(tmp_path):
    import hashlib
    from biopipe.bytecode import filesystem_path
    from biopipe.dropins import snapshot
    from biopipe.operator_docs import cache_document, document_bytes
    deep = tmp_path / ('profile-' + 'a' * 70) / ('revision-' + 'b' * 70)
    def io_path(path):
        return Path(filesystem_path(path, resolve=False))
    source = deep / 'sources'
    io_path(source).mkdir(parents=True)
    filename = 'integrated_discrimination_improvement.IntegratedDiscriminationImprovementStep.parameters.json'
    io_path(source / filename).write_text('{"type":"object"}', encoding='utf-8')
    assert len(str(source / filename)) > 260
    first = snapshot(source, deep / 'staging')
    assert snapshot(deep / 'staging', deep / 'copy') == first
    assert io_path(deep / 'copy' / filename).read_text() == '{"type":"object"}'

    content = b'## Purpose\n\nA long-path documentation fixture.\n'
    metadata = {'path': 'operator.md', 'sha256': hashlib.sha256(content).hexdigest(),
                'summary': 'A long-path documentation fixture.', 'sections': ['purpose'],
                'status': 'authored', 'minimum_sdk': '3.1.0'}
    class Manager:
        directory = deep / 'plugins'
    cache_document(Manager(), metadata, content)
    descriptor = {'id': 'long.path', 'entry_point': 'long.module:Extension', 'documentation': metadata}
    assert document_bytes(Manager(), {}, descriptor) == content
    cache_document(Manager(), metadata, content)  # Existing immutable content remains valid.

    # Library transport must also handle deep destination paths, including its
    # temporary extraction/rebuild tree, without shortening authored filenames.
    from biopipe.library_bundle import build_bundle, unpack_bundle
    seed = tmp_path / 'library-seed'
    operators = seed / 'src/task/step/steps'
    operators.mkdir(parents=True)
    (seed / 'src/reader/readers').mkdir(parents=True)
    (seed / 'biopipe').mkdir()
    (seed / 'biopipe/builtin_packages.json').write_text('{"packages":[]}', encoding='utf-8')
    implementation, _ = extension(operators)
    implementation.write_text(implementation.read_text().replace('class Answer(Step):',
        'class Answer(Step):\n    provider = "lab-docs"'), encoding='utf-8')
    bundle = build_bundle(seed, deep / 'bundles', '1.0.0')['bundle']
    extracted = deep / 'extracted'
    unpack_bundle(Path(bundle), extracted)
    assert io_path(extracted / 'sources/src/task/step/steps/answer.md').is_file()
    from scripts.record_bundled_history import record
    extracted_sources = io_path(extracted / 'sources')
    commit = 'a' * 40  # Synthetic provenance for this fixture only.
    (extracted_sources / 'package-manifest.json').write_text(json.dumps({
        'source_commit': commit, 'version': '1.0.0'}), encoding='utf-8')
    history = io_path(deep / 'history.json')
    assert record(extracted_sources, 'v1.0.0', commit, history) == 2
    assert record(extracted_sources, 'v1.0.0', commit, history) == 2
    with pytest.raises(ValueError, match='provenance'):
        record(extracted_sources, 'v1.0.0', 'b' * 40, history)

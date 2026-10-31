"""The shipped v3 index must describe every source without importing it."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_source_ids_and_parameter_schemas_match_static_manifest():
    from biopipe_sdk.declarations import source_declarations
    from biopipe_sdk.protocol import Descriptor
    manifest = json.loads((ROOT / 'biopipe/builtin_packages.json').read_text(encoding='utf-8'))
    indexed = {d['id']: d for p in manifest['packages'] for d in p['descriptors']}
    found = {}
    for directory in ('src/task/step/steps', 'src/reader/readers'):
        for path in (ROOT / directory).glob('[!_]*.py'):
            for source in source_declarations(path, path.relative_to(ROOT).as_posix()[:-3].replace('/', '.')):
                assert source['id'] not in found
                found[source['id']] = source
    assert found.keys() == indexed.keys()
    for key, source in found.items():
        spec = Descriptor.model_validate(indexed[key])
        assert spec.protocol_version == 3
        assert spec.parameters_schema == source['parameters_schema']
        assert spec.contracts == source['contracts']
        assert spec.title.strip()
        if spec.kind == 'reader':
            assert spec.extensions


def test_reader_platforms_come_from_dependencies_not_editor_os():
    from biopipe_sdk.protocol import catalog_entry
    from biopipe.packages import bundled_entries
    indexed = {d['id']: catalog_entry(d) for _, d in bundled_entries('reader')}
    for key in ('BamReader', 'BcfReader', 'CramReader'):
        assert 'linux' in indexed[key]['supported_systems']
        assert 'windows' not in indexed[key]['supported_systems']
    assert 'windows' in indexed['VcfReader']['supported_systems']

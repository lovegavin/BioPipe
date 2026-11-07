"""Explicit Reader selection is consistent from graph to managed worker."""
import gzip
import numpy as np
import pytest
import yaml

from operon.packages import bundled_state
from operon.plugins import PluginManager
from src.core import ReaderError
from src.reader import pick_reader, read_source
from src.web.assets import plan_input
from src.web.graph import compile_graph, import_manifest
from src.web.models import Graph, SaveWorkflow
from src.web.operator_catalog import catalog_from_descriptors
from src.web.parameters import export_bundle, freeze_graph, import_bundle
from src.web.routes import RouteLibrary


def graph_for(path, reader='BedReader'):
    return Graph.model_validate({'schema_version':2,'name':'Explicit Reader','base_dir':'.',
        'nodes':[{'id':'input','kind':'source','position':{'x':0,'y':0},
                  'source':{'path':path,'reader':reader,'dims':['region','field'],'labels':{'region':'auto','field':'builtin'}}},
                 {'id':'summary','kind':'operator','operator':'describe','position':{'x':300,'y':0},'params':{}}],
        'edges':[{'id':'edge','source':'input','target':'summary','sourceHandle':'out','targetHandle':'in-0'}],
        'memory':{'enabled':True,'budget_mb':8}})


def test_explicit_bed_companions_compression_and_frozen_roundtrip(tmp_path):
    # Filename companions would route auto-selection to the PLINK binary reader.
    path = tmp_path / 'regions.bed.gz'
    path.write_bytes(gzip.compress(b'chr1\t0\t10\nchr2\t10\t30\n'))
    (tmp_path / 'regions.bim').write_text('')
    (tmp_path / 'regions.fam').write_text('')
    with pytest.raises(ReaderError):
        pick_reader(path)
    assert type(pick_reader(path, 'BedReader')).__name__ == 'BedReader'
    catalog = catalog_from_descriptors(bundled_state()['descriptors'])
    graph = freeze_graph(graph_for(path.name), catalog, tmp_path)
    library = RouteLibrary(tmp_path / 'saved', catalog, tmp_path)
    saved = library.save(SaveWorkflow(graph=graph))
    assert library.get(saved['id'])['graph']['nodes'][0]['source']['reader'] == 'BedReader'
    restored = import_bundle(export_bundle(graph))
    assert restored.nodes[0].source.reader == 'BedReader'
    manifest, _ = compile_graph(restored, catalog, tmp_path, require_files=True)
    assert manifest['sources']['input']['reader'] == 'BedReader'
    imported = import_manifest(yaml.safe_dump(manifest), '.', catalog, tmp_path)
    assert imported.nodes[0].source.reader == 'BedReader'
    from src.task import Context
    context = Context(tmp_path, manifest)
    try:
        context.register_source('input', manifest['sources']['input'])
        result = context['input']
        np.testing.assert_array_equal(result.data[:, 1:], [[0,10],[10,30]])
        assert result.labels['field']['chromStart'] == 1
    finally:
        context.finalize()


def test_import_selects_reader_before_reading_payload_and_pins_only_that_id(tmp_path):
    catalog = catalog_from_descriptors(bundled_state()['descriptors'])
    same_suffix = {'readers':[dict(reader, extensions=['.test'], requires_siblings=[], excludes_siblings=[])
                             for reader in catalog['readers'] if reader['id'] in ('BedReader','Plink1Reader')]}
    with pytest.raises(ValueError):
        plan_input(['sample.test'], same_suffix)
    assert plan_input(['sample.test'], same_suffix, 'BedReader')['source']['reader'] == 'BedReader'
    manager = PluginManager(tmp_path / '.studio')
    pinned = manager.pin(graph_for('regions.bed'))
    assert 'BedReader' in pinned.plugin_lock
    assert 'Plink1Reader' not in pinned.plugin_lock
    nested = Graph.model_validate({'nodes': [{'id': 'nested', 'kind': 'route', 'position': {'x':0, 'y':0},
        'route': {'id': 'route_123456abcdef', 'name': 'Nested BED', 'version': 1, 'graph': pinned.model_dump()}}], 'edges': []})
    nested = manager.pin(import_bundle(export_bundle(nested)))
    assert nested.nodes[0].route.graph.nodes[0].source.reader == 'BedReader'
    assert 'BedReader' in nested.nodes[0].route.graph.plugin_lock
    assert 'Plink1Reader' not in nested.nodes[0].route.graph.plugin_lock
    with pytest.raises(ValueError, match='Unknown'):
        plan_input(['sample.test'], same_suffix, 'MissingReader')


def test_explicit_reader_overrides_suffix_without_stealing_txt_delegation(tmp_path):
    path = tmp_path / 'values.tsv'
    path.write_text('a\tb\n1\t2\n3\t4\n')
    result = read_source(path, ['sample','feature'], {'feature':'builtin'}, reader_id='CsvReader', sep='\t')
    np.testing.assert_array_equal(result.data, [[1,2],[3,4]])
    # TxtReader's own `reader` argument remains a parameter, not a global selector.
    text = tmp_path / 'values.txt'
    text.write_bytes(path.read_bytes())
    delegated = read_source(text, ['sample','feature'], {'feature':'builtin'}, reader_id='TxtReader', reader='csv', sep='\t')
    np.testing.assert_array_equal(delegated.data, result.data)
    with pytest.raises(ReaderError, match='compression'):
        pick_reader(tmp_path / 'values.csv.zst', 'CsvReader')
    with pytest.raises(ReaderError, match='companion'):
        pick_reader(tmp_path / 'missing.bed', 'Plink1Reader')

"""Real domain file round trips, semantic rejection, bounded blocks and branching."""
import io
import json
from pathlib import Path

import numpy as np
import pytest

from src.core import FileArtifact, Form, StepError
from src.task.context import Context
from src.task.step.steps.export_results import ExportResultsStep


def contacts():
    info = {'representation': 'contact_window', 'balanced': False, 'resolution': 1000,
            'chrom_sizes': {'chr1': 3000, 'chr2': 1500}, 'assembly': 'synthetic'}
    axis = {}
    for dim in ('bin1', 'bin2'):
        info.update({dim + '_chrom': ['chr1'] * 3, dim + '_start': [0, 1000, 2000], dim + '_end': [1000, 2000, 3000]})
        axis[dim] = [dim + suffix for suffix in ('_chrom', '_start', '_end')]
    return Form(np.array([[2, 3, 0], [3, 4, 1], [0, 1, 2]]), ['bin1', 'bin2'],
                {d: {str(i): i for i in range(3)} for d in axis}, info, axis)


@pytest.fixture
def ctx(tmp_path):
    context = Context(tmp_path / 'task', {})
    yield context
    context.finalize()


def export(ctx, value, format, **params):
    ctx.step_params = {'output': 'saved', 'format': format, 'buffer_mb': .0002, **params}
    ExportResultsStep().run(ctx, [value])
    return ctx['saved']


@pytest.mark.parametrize('format', ['hic', 'cool'])
def test_raw_form_contact_roundtrip(ctx, format):
    hictkpy = pytest.importorskip('hictkpy')
    form = contacts()
    original = form.data.copy()
    result = export(ctx, form, format)
    reader = hictkpy.File(result.files['data'], resolution=1000)
    assert reader.chromosomes() == form.info['chrom_sizes']
    np.testing.assert_array_equal(reader.fetch('chr1').to_numpy(), original)
    np.testing.assert_array_equal(form.data, original)
    assert reader.attributes()['assembly'] == 'synthetic'
    metadata = json.loads(Path(result.files['metadata']).read_text())
    assert 'unobserved' in metadata['coverage']
    assert metadata['normalizations'] == []


def test_cooler_to_hic_preserves_counts_without_window_materialization(ctx, monkeypatch):
    hictkpy = pytest.importorskip('hictkpy')
    cool = export(ctx, contacts(), 'cool')
    # Exercise source discovery on generic exported_files, not only a cool-tagged artifact.
    hic = export(ctx, cool, 'hic')
    np.testing.assert_array_equal(hictkpy.File(hic.files['data'], 1000).fetch('chr1').to_numpy(), contacts().data)
    assert hictkpy.File(hic.files['data'], 1000).attributes()['assembly'] == 'synthetic'
    assert 'unobserved' in hic.info['conversion']['coverage']
    again = export(ctx, hic, 'hic')
    assert list(again.files.values()) == [hic.files['data']]
    assert again.info['reused_roles'] == ['file_1']
    assert again.info['conversion'] == hic.info['conversion']


@pytest.mark.parametrize('change,message', [
    (lambda f: f.info.pop('chrom_sizes'), 'chrom_sizes'),
    (lambda f: f.info.update(balanced=True), 'raw counts'),
    (lambda f: f.info.update(representation='pca'), 'raw counts'),
    (lambda f: f.axis_info.clear(), 'axis_info'),
    (lambda f: f.info['bin1_start'].__setitem__(1, 1200), 'coordinates'),
    (lambda f: f.info['bin2_start'].__setitem__(1, 0), 'coordinates'),
    (lambda f: f.data.__setitem__((0, 1), 7), 'symmetric'),
    (lambda f: f.data.__setitem__((0, 0), -1), 'raw counts'),
])
def test_contact_rejects_missing_or_misleading_semantics(ctx, change, message):
    pytest.importorskip('hictkpy')
    form = contacts(); change(form)
    with pytest.raises(StepError, match=message):
        export(ctx, form, 'hic')
    assert not ctx.has('saved')
    assert not list(ctx.out_dir.rglob('*.part'))
    assert not list(ctx.out_dir.rglob('contact-export-*'))


def test_contact_float_balancing_and_cancel(ctx):
    pytest.importorskip('hictkpy')
    form = contacts(); form.data = form.data.astype(float); form.data[0, 0] = .5
    with pytest.raises(StepError, match='raw counts'):
        export(ctx, form, 'hic')
    (ctx.task_dir / 'cancel.requested').touch()
    with pytest.raises(StepError, match='cancelled'):
        export(ctx, contacts(), 'hic')


def test_genbank_reader_subset_preserves_features_and_topology(ctx, tmp_path):
    from Bio import SeqIO
    from Bio.Seq import Seq
    from Bio.SeqRecord import SeqRecord
    from Bio.SeqFeature import SeqFeature, SimpleLocation, CompoundLocation
    from src.reader.readers.genbank_reader import GenBankReader
    records = []
    for name in ('plasmid_a', 'plasmid_b'):
        r = SeqRecord(Seq('ACGT' * 10), id=name, name=name, description='synthetic')
        r.annotations = {'molecule_type': 'DNA', 'topology': 'circular'}
        r.features = [SeqFeature(CompoundLocation([SimpleLocation(3, 7, strand=-1), SimpleLocation(10, 15, strand=-1)]),
                                type='CDS', qualifiers={'gene': ['example'], 'note': ['do not lose this']})]
        records.append(r)
    original = tmp_path / 'original.gbk'
    SeqIO.write(records, original, 'genbank')
    form = GenBankReader().read(original, ['record', 'field'], {'record': 'auto', 'field': 'builtin'})
    selected = form.subset_axis('record', [1])
    output = export(ctx, selected, 'genbank')
    actual = SeqIO.read(output.files['data'], 'genbank')
    assert actual.id == 'plasmid_b' and actual.annotations['topology'] == 'circular'
    assert str(actual.features[0].location) == str(records[1].features[0].location)
    assert actual.features[0].qualifiers == records[1].features[0].qualifiers
    summary = GenBankReader().read(original, ['record', 'field'], {'record': 'auto', 'field': 'builtin'}, retain_records=False)
    assert 'genbank_records' not in summary.info
    with pytest.raises(StepError, match='axis_info'):
        export(ctx, summary, 'genbank')


def test_genbank_sequences_and_tracks(ctx):
    from Bio import SeqIO
    f = Form(np.array([[4.], [5.]]), ['record', 'value'], {'record': {'a': 0, 'b': 1}, 'value': {'v': 0}},
             {'sequences': ['ACGT', 'TTAA']}, {'record': ['sequences']})
    result = export(ctx, f, 'genbank', topology='circular')
    records = list(SeqIO.parse(result.files['data'], 'genbank'))
    assert len(records) == 2 and records[1].annotations['topology'] == 'circular'
    f.info = {'chrom': ['chr1', 'chr1'], 'start': [0, 10], 'end': [10, 20], 'coordinate_system': '0-based-half-open'}
    f.axis_info = {'record': ['chrom', 'start', 'end']}
    result = export(ctx, f, 'bedgraph')
    assert Path(result.files['data']).read_text() == 'chr1\t0\t10\t4.0\nchr1\t10\t20\t5.0\n'
    f.info['coordinate_system'] = '1-based'
    with pytest.raises(StepError, match='0-based'):
        export(ctx, f, 'bed')


def test_network_and_tree_not_inferred_from_arbitrary_matrix(ctx):
    import xml.etree.ElementTree as ET
    f = Form(np.array([[0., 3.], [3., 0.]]), ['from', 'to'], {d: {'A<&': 0, 'B': 1} for d in ['from', 'to']})
    with pytest.raises(StepError, match='adjacency'):
        export(ctx, f, 'graphml')
    f.info['representation'] = 'adjacency'
    r = export(ctx, f, 'graphml')
    xml = ET.parse(r.files['data']); ns = {'g': 'http://graphml.graphdrawing.org/xmlns'}
    assert len(xml.findall('.//g:edge', ns)) == 1
    assert xml.find('.//g:node/g:data', ns).text == 'A<&'
    with pytest.raises(StepError, match='not a tree'):
        export(ctx, f, 'newick')
    f.info['newick'] = '(A:0.1,B:0.2);'
    assert Path(export(ctx, f, 'newick').files['data']).read_text() == '(A:0.1,B:0.2);\n'


def test_export_preserves_external_index_filenames(ctx, tmp_path):
    bam, bai = tmp_path / 'reads.bam', tmp_path / 'reads.bam.bai'
    bam.write_bytes(b'synthetic'); bai.write_bytes(b'index')
    artifact = export(ctx, FileArtifact('bam', {'data': str(bam), 'index': str(bai)}), 'native')
    assert {Path(p).name for p in artifact.files.values()} == {'reads.bam', 'reads.bam.bai'}


def test_native_contact_reuse_has_no_conversion_memory_reservation(ctx):
    path = ctx.artifact_path('original.hic'); path.write_bytes(b'HIC')
    artifact = FileArtifact('hic', {'data': str(path)})
    workspace, _ = ExportResultsStep.estimate_memory([artifact], {'format': 'hic', 'buffer_mb': .01}, [])
    assert workspace < 1024**2


def test_renaming_native_compressed_files_preserves_type_and_index_pair(ctx, tmp_path):
    main, index = tmp_path / 'sample.vcf.gz', tmp_path / 'sample.vcf.gz.tbi'
    main.write_bytes(b'compressed example'); index.write_bytes(b'index')
    single = export(ctx, FileArtifact('vcf', {'data': str(main)}), 'native', filename='variant')
    assert Path(single.files['file_1']).name == 'variant.vcf.gz'
    bundle = export(ctx, FileArtifact('vcf', {'data': str(main), 'index': str(index)}), 'native', filename='variant')
    assert {Path(p).name for p in bundle.files.values()} == {'variant-sample.vcf.gz', 'variant-sample.vcf.gz.tbi'}

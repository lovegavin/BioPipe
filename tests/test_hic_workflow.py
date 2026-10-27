"""Numerical file-path tests, not substitutes for the Linux tool-chain tests."""
import gzip
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from src.core import ReaderError
from src.task.context import Context
from src.reader.readers._sequencing import fastq_summary, read_file_source
from src.task.step.steps._contact_window import select_window
from src.task.step.steps._hic_tools import canonical_pairs
from biopipe.tool_runner import ToolRunner


def tiny_cool(path):
    import h5py
    with h5py.File(path, 'w') as h:
        h.attrs.update({'bin-size': 10, 'storage-mode': 'symmetric-upper', 'genome-assembly': 'test'})
        values = {'chroms/name': np.array([b'chr1']), 'chroms/length': [40],
                  'bins/chrom': [0]*4, 'bins/start': [0,10,20,30], 'bins/end': [10,20,30,40],
                  'bins/weight': [.5,1,2,3], 'indexes/chrom_offset': [0,4],
                  'indexes/bin1_offset': [0,3,5,6,7], 'pixels/bin1_id': [0,0,0,1,1,2,3],
                  'pixels/bin2_id': [0,1,3,1,2,2,3], 'pixels/count': [2,3,5,7,11,13,17]}
        for k,v in values.items(): h.create_dataset(k,data=v)
    return path


def test_fastq_wrapped_compressed_pairing_and_exact_summary(tmp_path):
    a,b = tmp_path/'r1.fq.gz',tmp_path/'r2.fq'
    with gzip.open(a,'wt') as f: f.write('@x/1\nAC\nGN\n+\nII\n!!\n')
    b.write_text('@x/2\nGGCC\n+\nIIII\n')
    result=fastq_summary({'r1':a,'r2':b},record_bytes=8)
    assert result['r1']['gc'] == .5 and result['r1']['n_ratio'] == .25
    assert result['r1']['mean_quality'] == 20 and result['r1']['q30'] == .5
    assert result['r2']['gc'] == 1
    b.write_text('@y/2\nGGCC\n+\nIIII\n')
    with pytest.raises(ReaderError,match='identifiers'): fastq_summary({'r1':a,'r2':b})
    b.write_text('@x/2\nGGCC\n+\nIII\n')
    with pytest.raises(ReaderError,match='Truncated'): fastq_summary({'r1':b})
    with pytest.raises(ReaderError,match='cancelled'): fastq_summary({'r1':a},cancelled=lambda:True)


def test_cooler_symmetric_rectangle_weights_and_budget(tmp_path):
    path=tiny_cool(tmp_path/'x.cool')
    artifact=read_file_source(path,'cool')
    raw=np.array([[2,3,0,5],[3,7,11,0],[0,11,13,0],[5,0,0,17.]])
    params={'source_type':'contact_matrix','region':'chr1:0-40','balanced':False}
    assert np.array_equal(select_window(artifact,params).data,raw)
    params.update(region='chr1:10-30',region2='chr1:0-20')
    assert np.array_equal(select_window(artifact,params).data,raw[1:3,:2])
    params['balanced']=True
    assert np.array_equal(select_window(artifact,params).data,raw[1:3,:2]*np.array([1,2])[:,None]*[.5,1])
    with pytest.raises(Exception,match='budget'):
        select_window(artifact,params,ctx=SimpleNamespace(memory=SimpleNamespace(config=SimpleNamespace(budget_bytes=100))))
    artifact.validate()


def test_pairs_schema_coordinates_flip_filter_and_missing_mapq(tmp_path):
    source=tmp_path/'a.pairs'; target=tmp_path/'out.pairs'
    source.write_text('#columns: chrom2 pos2 readID chrom1 pos1 strand1 strand2 pair_type mapq1 mapq2\n'
                      'chr1\t1\ta\tchr1\t20\t+\t-\tUU\t60\t60\n'
                      'chr1\t5\tb\tchr1\t10\t+\t-\tUU\t2\t60\n')
    before=source.read_bytes()
    result=canonical_pairs(source,target,{'chr1':100},min_mapq=30)
    assert result=={'input':2,'retained':1,'filtered':1}
    assert target.read_text().splitlines()[-1]=='a\tchr1\t1\tchr1\t20\t-\t+\tUU'
    assert source.read_bytes()==before
    with pytest.raises(ValueError,match='mapq'): canonical_pairs(target,tmp_path/'other',{'chr1':100},min_mapq=30)
    source.write_text(before.decode().replace('\t20\t','\t101\t'))
    with pytest.raises(ValueError,match='coordinate'): canonical_pairs(source,target,{'chr1':100})


def test_tool_runner_real_child_logging_failure_and_timeout(tmp_path):
    ctx=Context(tmp_path,{})
    try:
        runner=ToolRunner(ctx,{'executor':'native','timeout_seconds':2})
        out=runner.run([sys.executable,'-c','import sys; print(sys.argv[1])','space quote " value'])
        assert out.read_text().strip()=='space quote " value'
        with pytest.raises(RuntimeError,match='original failure'):
            runner.run([sys.executable,'-c','import sys; print("original failure",file=sys.stderr); sys.exit(7)'])
        with pytest.raises(RuntimeError,match='timed out'):
            runner.run([sys.executable,'-c','import time; time.sleep(20)'])
        (tmp_path/'cancel.requested').touch()
        with pytest.raises(RuntimeError,match='cancelled'):
            runner.run([sys.executable,'-c','import time; time.sleep(20)'])
        assert len(list(runner.directory.glob('*.stderr.log')))==4
    finally: ctx.finalize()


def test_registry_and_streaming_qc_then_existing_selection(tmp_path):
    from src.reader import read_source
    from src.task.runner import run
    path=tmp_path/'x.fastq';path.write_text('@x\nACGT\n+\nIIII\n')
    artifact=read_source(path,dims=['file'],labels={})
    ctx=Context(tmp_path,{'runtime':{'memory':{'budget_mb':32,'keep':['subset']}}})
    ctx['reads']=artifact
    try:
        run(ctx,[{'name':'sequence_stats','inputs':['reads'],'params':{'fastq_summary':True,'output':'qc'}},
                 {'name':'select','inputs':['qc'],'params':{'dim':'statistic','labels':['gc','q30'],'output':'subset'}}])
        assert np.array_equal(ctx['subset'].data,[[.5,1]])
    finally: ctx.finalize()


@pytest.mark.parametrize('mode', ['fastq','bam','pairs'])
def test_hic_route_parameters_compile_and_export_relative_paths(tmp_path, mode):
    import json
    from src.task import STEPS
    from src.task.operator_catalog import build_catalog
    from src.task.manifest import load_manifest
    from src.web.graph import import_manifest, compile_graph, relative_manifest
    import yaml
    root=Path(__file__).resolve().parents[1]
    raw=load_manifest(root/'routes'/('hic_'+mode)/'task.yaml')
    catalog=build_catalog(STEPS)
    graph=import_manifest(yaml.safe_dump(raw),'.',catalog,tmp_path)
    manifest,_=compile_graph(graph,catalog,tmp_path)
    exported=relative_manifest(manifest,tmp_path,catalog)
    build=next(s for s in exported['steps'] if s['name']=='build_contacts')
    assert build['params']['chromsizes']=='input/chrom.sizes'
    if mode=='fastq':
        assert exported['sources']['reads']['args']['mate_path']=='mate.fastq'
        assert next(s for s in exported['steps'] if s['name']=='align_reads')['params']['reference_fasta']=='input/reference.fa'
    # Concrete values survive without consulting live schema defaults.
    from biopipe.parameter_values import split_task, restore_task
    topology,values=split_task(exported)
    assert restore_task(topology,json.loads(json.dumps(values)))==exported


def test_empty_loop_table_is_a_successful_empty_result(tmp_path):
    from src.task.step.steps._hic_adapter import load_analysis
    table=tmp_path/'loops.tsv';table.write_text('chrom1\tstart1\tend1\tchrom2\tstart2\tend2\n')
    form=load_analysis({'format':'tsv','files':{'table':str(table)},'info':{'representation':'hic_loops'}},None,{'memory_mb':1})
    assert form.data.shape==(0,6) and form.info['empty_result']
    form.validate()


def test_pileup_batches_weight_by_valid_pixels_not_batch_means(tmp_path):
    from src.task.step.steps._hic_tools import _pileup
    features=tmp_path/'features.bedpe'
    features.write_text('first\nsecond\nthird\n')
    scratch=tmp_path/'scratch'; scratch.mkdir()
    stack=np.array([np.full((3,3),1.),np.full((3,3),3.),np.full((3,3),8.)])
    stack[0,0,0]=np.nan
    stack[1,0,0]=np.inf
    stack[:,2,2]=np.nan
    batches=[]
    def command(*args):
        batch=(scratch/'features.bed').read_text().splitlines()
        start=sum(batches); batches.append(len(batch))
        np.savez(scratch/'snips.npz',stack=stack[start:start+len(batch)])
    runner=SimpleNamespace(ctx=SimpleNamespace(task_dir=tmp_path),
                           params={'features':str(features),'flank':10},
                           memory_bytes=2*3*3*64, scratch=scratch,directory=tmp_path,
                           path=str,command=command)
    result=_pileup(runner,'matrix.cool','expected.tsv',[],[],10)
    with np.load(result) as output:
        assert batches==[2,1]
        assert output['pileup'][1,1]==4 and output['valid_counts'][1,1]==3
        assert output['pileup'][0,0]==8 and output['valid_counts'][0,0]==1
        assert np.isnan(output['pileup'][2,2]) and output['valid_counts'][2,2]==0


def test_hic_helper_edits_change_code_identity_without_importing_tools(tmp_path):
    import shutil
    from biopipe_sdk.declarations import code_hash
    root=Path(__file__).resolve().parents[1]
    entry='src.task.step.steps.align_reads:AlignReadsStep'
    for folder in ('src/task/step/steps','src/reader/readers'):
        shutil.copytree(root/folder,tmp_path/folder,ignore=shutil.ignore_patterns('__pycache__'))
    before=code_hash(entry,tmp_path)
    helper=tmp_path/'src/task/step/steps/_hic_tools.py'
    helper.write_text(helper.read_text(encoding='utf-8')+'\n# Algorithm revision\n',encoding='utf-8')
    changed=code_hash(entry,tmp_path)
    assert changed != before
    parameter=tmp_path/'src/task/step/steps/align_reads.parameters.json'
    parameter.write_text(parameter.read_text(encoding='utf-8')+'\n',encoding='utf-8')
    assert code_hash(entry,tmp_path)==changed

"""Linux acceptance: actual tools, synthetic data, no reference downloads.

BIOPIPE_HIC_REAL=1 python -m pytest tests/test_hic_real.py -v
"""
import gzip
import os
from pathlib import Path
import random
import shutil

import numpy as np
import pytest

pytestmark = pytest.mark.skipif(os.environ.get('BIOPIPE_HIC_REAL') != '1', reason='Set BIOPIPE_HIC_REAL=1 in the Linux Hi-C environment')


def require_tools():
    for name in ('bwa','samtools','pairtools','cooler','cooltools'):
        assert shutil.which(name), f'Real acceptance requires {name}'


def fixtures(directory):
    directory.mkdir(parents=True, exist_ok=True)
    chroms=directory/'chrom.sizes';chroms.write_text('chr1\t640000\n')
    view=directory/'view.bed';view.write_text('chr1\t0\t640000\tchr1\n')
    features=directory/'features.bedpe'
    features.write_text('chr1\t100000\t110000\tchr1\t300000\t310000\nchr1\t200000\t210000\tchr1\t400000\t410000\n')
    rng=random.Random(817)
    pairs=directory/'reads.pairs.gz';total=0
    with gzip.open(pairs,'wt') as out:
        out.write('## pairs format v1.0.0\n#chromsize: chr1 640000\n#columns: readID chrom1 pos1 chrom2 pos2 strand1 strand2 pair_type mapq1 mapq2\n')
        for a in range(64):
            for b in range(a,64):
                for k in range(8 + int(80/(1+b-a)) + (8 if a//16==b//16 else 0)):
                    x=a*10000+100+k*11; y=b*10000+500+k*13
                    out.write(f'r{total}\tchr1\t{x}\tchr1\t{y}\t+\t-\tUU\t60\t60\n');total+=1
    return chroms,view,features,pairs,total


def test_real_pairs_to_balanced_analysis_and_existing_heatmap(tmp_path):
    require_tools()
    import cooler
    from src.task.context import Context
    from src.task.runner import run
    from src.reader.readers._sequencing import read_file_source
    chroms,view,features,pairs,total=fixtures(tmp_path/'input')
    ctx=Context(tmp_path,{'runtime':{'memory':{'budget_mb':3072,'keep':['contacts','expected','compartments','insulation','loops','pileup','window']}}})
    ctx['reads']=read_file_source(pairs,'pairs')
    common=dict(executor='native',threads=1,memory_mb=2048,timeout_seconds=180)
    def step(name,inputs,**params):return dict(name=name,inputs=inputs,params=params)
    try:
        steps=[step('build_contacts',['reads'],**common,chromsizes=str(chroms),binsize=10000,min_mapq=30,output='contacts')]
        for method in ('expected','compartments','insulation','loops','pileup'):
            params=dict(common,method=method,view=str(view),windows=[30000,50000],features=str(features),flank=20000,output=method)
            steps.append(step('analyze_contacts',['contacts','expected'] if method in ('loops','pileup') else ['contacts'],**params))
        steps += [step('select',['contacts'],source_type='contact_matrix',region='chr1:100000-300000',output='window'),
                  step('heatmap',['window'],dim='bin1',other_dim='bin2',select='all',cluster_rows=False,cluster_cols=False,filename='hic.png')]
        run(ctx,steps)
        clr=cooler.Cooler(ctx['contacts'].files['data'])
        assert int(clr.pixels()[:]['count'].sum())==total
        assert np.isfinite(clr.bins()[:]['weight']).sum() > 50
        assert ctx['expected'].data.shape[0]==64
        assert ctx['compartments'].info['orientation']=='unoriented'
        assert ctx['insulation'].data.shape[0]==64
        assert ctx['pileup'].data.shape==(5,5)
        assert np.isfinite(ctx['pileup'].data).any()
        assert ctx['window'].data.shape==(20,20)
        assert list(ctx.out_dir.rglob('hic.png'))
    finally: ctx.finalize()


def test_real_fastq_alignment_and_bam_entry(tmp_path):
    require_tools()
    import cooler
    from src.task.context import Context
    from src.task.runner import run
    from src.reader.readers._sequencing import read_file_source
    rng=random.Random(718)
    sequence=''.join(rng.choices('ACGT',k=100000))
    ref=tmp_path/'reference.fa';ref.write_text('>chr1\n'+sequence+'\n')
    chroms=tmp_path/'chrom.sizes';chroms.write_text('chr1\t100000\n')
    a,b=tmp_path/'r1.fastq',tmp_path/'r2.fastq'
    reverse=str.maketrans('ACGT','TGCA')
    with a.open('w') as x,b.open('w') as y:
        for i in range(100):
            s=sequence[100+i*179:250+i*179]
            t=sequence[50000+i*181:50150+i*181].translate(reverse)[::-1]
            x.write(f'@pair{i}/1\n{s}\n+\n'+ 'I'*150+'\n')
            y.write(f'@pair{i}/2\n{t}\n+\n'+ 'I'*150+'\n')
    ctx=Context(tmp_path,{'runtime':{'memory':{'budget_mb':3072,'keep':['qc','bam','contacts']}}})
    ctx['reads']=read_file_source(a,'fastq',mate_path=str(b))
    common=dict(executor='native',memory_mb=2048,timeout_seconds=180)
    try:
        run(ctx,[dict(name='sequence_stats',inputs=['reads'],params={'fastq_summary':True,'output':'qc'}),
                 dict(name='align_reads',inputs=['reads'],params=dict(common,reference_fasta=str(ref),output='bam')),
                 dict(name='build_contacts',inputs=['bam'],params=dict(common,chromsizes=str(chroms),binsize=10000,balance=False,output='contacts'))])
        assert ctx['qc'].data[0,0]==100
        clr=cooler.Cooler(ctx['contacts'].files['data'])
        assert int(clr.pixels()[:]['count'].sum())==100
        assert ref.read_text()=='>chr1\n'+sequence+'\n'
        assert not list(tmp_path.glob('reference.fa.*'))
    finally: ctx.finalize()

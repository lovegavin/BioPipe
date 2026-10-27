"""Synthetic expression/survival routes, numeric results and metadata contracts."""
import gzip
import numpy as np
import pytest

from src.core import Form
from src.reader import read_source
from src.task import Context, STEPS, run
from src.task.operator_catalog import build_catalog
from src.task.memory.planner import full_estimate


def expression():
    rng = np.random.default_rng(26)
    data = rng.uniform(2, 30, (8, 12)).astype(np.float32)
    data[:3, 6:] *= 2
    data[0, 0] = -9
    matrix = Form(data, ['gene','sample'], {'gene':{f'g{i}':i for i in range(8)}, 'sample':{f's{i}':i for i in range(12)}},
                  {'missing_code':-9, 'chrom':['1']*8, 'pos':np.arange(8), 'cohort':['a']*6+['b']*6, 'study':'synthetic'}, {'gene':['chrom','pos'], 'sample':['cohort']})
    meta = Form(np.array([[0.]]*6+[[1.]]*6), ['sample','feature'], {'sample':matrix.labels['sample'], 'feature':{'group':0}}, {'missing_code':np.nan})
    return matrix, meta


def step(name, inputs, **params):
    return {'name':name, 'inputs':inputs, 'params':params}


def test_registry_thirteen_adapted_operators():
    new = set('filter_min normalize log_transform impute compare_groups kaplan_meier logrank_test cox_regression volcano ma_plot heatmap boxplot forest_plot'.split())
    catalog = build_catalog(STEPS)
    assert new <= set(STEPS)
    for item in catalog['operators']:
        if item['name'] not in new: continue
        assert item['parameters'] and item['contracts']['inputs'] and item['contracts']['output']
        assert item['memory_modes'] == ['full'] and not item['supports_cuda']


@pytest.mark.parametrize('method',['cpm','total','median_of_ratios','quantile','zscore'])
def test_normalization_missing_sentinel_and_metadata(tmp_path, method):
    form, _=expression(); ctx=Context(tmp_path,{})
    ctx['x']=form
    run(ctx,[step('normalize',['x'],method=method,dim='sample',output='out')])
    out=ctx['out']
    assert np.isnan(out.data[0,0]) and np.isnan(out.info['missing_code'])
    assert out.axis_info == form.axis_info and out.info['study']=='synthetic'
    assert out.info['representation']=='normalize' and form.info['missing_code']==-9
    if method=='cpm': np.testing.assert_allclose(np.nansum(out.data,axis=0), 1e6,rtol=1e-6)
    if method=='total': np.testing.assert_allclose(np.nansum(out.data,axis=0), 1,rtol=1e-6)
    if method=='zscore': np.testing.assert_allclose(np.nanmean(out.data,axis=0),0,atol=1e-6)


def test_expression_route_branches_reports_and_aligned_annotations(tmp_path):
    matrix,meta=expression()
    ctx=Context(tmp_path,{'runtime':{'memory':{'enabled':True,'budget_mb':128,'keep':['diff','logged']}}})
    ctx['x']=matrix; ctx['meta']=meta
    steps=[step('filter_min',['x'],dim='gene',min_value=1,min_samples=3,output='filtered'),
           step('impute',['filtered'],method='median',dim='gene',output='filled'),
           step('normalize',['filled'],method='quantile',dim='sample',output='normalized'),
           step('log_transform',['normalized'],base=2,pseudocount=1,output='logged'),
           step('compare_groups',['normalized','meta'],dim='gene',group_dim='sample',group_label='group',group_a=0,group_b=1,method='welch',output='diff'),
           step('volcano',['diff'],dim='gene',filename='volcano.png'),
           step('ma_plot',['diff'],dim='gene',filename='ma.png'),
           step('heatmap',['logged'],dim='gene',other_dim='sample',top_n=5,filename='heatmap.png'),
           step('boxplot',['logged','meta'],dim='gene',value_label='g1',group_dim='sample',group_label='group',filename='boxplot.png')]
    try:
        run(ctx,steps)
        diff=ctx['diff']; logged=ctx['logged']
        assert diff.axis_info=={'gene':['chrom','pos']}
        assert 'cohort' not in diff.info and diff.info['study']=='synthetic'
        assert diff.info['representation']=='comparison'
        assert np.isfinite(logged.data).all()
        assert len(list((ctx.memory.run_dir/'figures').glob('*.png')))==4
        assert all(item['export_path'] for item in ctx.artifacts['exports'])
    finally: ctx.memory.close('complete')


def test_survival_route(tmp_path):
    pytest.importorskip('lifelines')
    rng=np.random.default_rng(91); n=100
    age=rng.normal(60,9,n); group=rng.integers(0,2,n)
    times=rng.exponential(50*np.exp(-.03*(age-60)-.4*group))+1
    events=rng.binomial(1,.8,n)
    data=np.column_stack([times,events,group,age]).astype(np.float32)
    form=Form(data,['sample','feature'],{'sample':{str(i):i for i in range(n)},'feature':{'time':0,'event':1,'group':2,'age':3}},
              {'missing_code':np.nan,'study':'synthetic','patient_note':['keep private']*n},{'sample':['patient_note']})
    ctx=Context(tmp_path,{});ctx['clinical']=form
    run(ctx,[step('kaplan_meier',['clinical'],time_label='time',event_label='event',group_label='group',filename='km.png'),
             step('logrank_test',['clinical'],time_label='time',event_label='event',group_label='group',pairwise=True,output='logrank'),
             step('cox_regression',['clinical'],time_label='time',event_label='event',covariates=['age','group'],output='cox'),
             step('forest_plot',['cox'],filename='forest.png')])
    assert ctx['logrank'].dims==['comparison','statistic']
    assert ctx['cox'].dims==['covariate','statistic']
    assert ctx['cox'].info['study']=='synthetic' and 'patient_note' not in ctx['cox'].info
    assert np.isfinite(ctx['cox'].data).all()
    assert len(list((ctx.out_dir/'figures').glob('*.png')))==2


def test_txt_reader_csv_separator_and_compression(tmp_path):
    for filename in ['data.tsv','data.txt.gz']:
        path=tmp_path/filename; content='id\ta\tb\ns0\t1\t2\ns1\t3\t4\n'
        if filename.endswith('.gz'):
            with gzip.open(path,'wt') as stream: stream.write(content)
        else: path.write_text(content)
        form=read_source(path,['sample','feature'],{'sample':{'feature':0},'feature':'builtin'},reader='csv',sep='\t')
        np.testing.assert_array_equal(form.data,[[1,2],[3,4]])
        assert form.labels['sample']=={'s0':0,'s1':1}
    path=tmp_path/'semi.csv';path.write_text('a;b\n1;2\n')
    assert read_source(path,['sample','feature'],{'feature':'builtin'},sep=';').data.shape==(1,2)


def test_full_kernels_reserve_float64_workspaces():
    form,_=expression()
    workspace,output=full_estimate('normalize',[form],{'method':'quantile','dim':'sample'}, {})
    assert workspace >= form.data.size*64 and output >= form.data.nbytes


def test_deseq2_selects_only_two_groups_and_rejects_normalized_counts(tmp_path):
    pytest.importorskip('pydeseq2')
    from src.task.step.steps.compare_groups import _deseq2_test
    from src.core import StepError
    rng=np.random.default_rng(2026)
    counts=rng.negative_binomial(5,.25,(32,15)).astype(float)
    mask_a=np.arange(15)<6; mask_b=(np.arange(15)>=6)&(np.arange(15)<12)
    counts[:,12:]=np.nan  # Unselected samples must not enter group B.
    result,labels=_deseq2_test(counts,mask_a,mask_b)
    assert result.shape==(32,7) and labels=={'Q_VALUE':6}
    assert np.all(result[:,5]==12) and np.isfinite(result[:,4]).any()
    with pytest.raises(StepError,match='raw integer counts'):
        _deseq2_test(counts+.25,mask_a,mask_b)

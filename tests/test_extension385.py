from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps._peak_utils import call_peaks, iter_fragments, pileup
from src.task.step.steps.peak_merge import PeakMergeStep


class Ctx(dict):
    @property
    def step_params(self):
        return self['step_params']


def _ctx(**params):
    return Ctx({'step_params': dict(params)})


def test_pileup_counts_overlapping_fragments():
    depth = pileup([1, 3], [4, 5], 6)
    assert depth.tolist() == [0, 1, 1, 2, 1, 0]


def test_call_peaks_finds_planted_region():
    rng = np.random.default_rng(7)
    length = 30000
    starts = rng.integers(9000, 10000, 400)
    ends = starts + 150
    background_starts = rng.integers(0, 30000, 100)
    fragments = {'chr1': (np.concatenate([starts, background_starts]),
                          np.concatenate([ends, background_starts + 150]))}
    peaks = call_peaks(fragments, {'chr1': length}, qvalue=0.05,
                       total_fragments_bp=float((ends - starts).sum() * 2),
                       genome_bp=length)
    assert peaks
    best = max(peaks, key=lambda item: item['count'])
    assert best['start'] <= 10000 and best['end'] >= 9000
    assert 9000 <= best['summit'] <= 10000
    assert best['fold_enrichment'] > 1.5


def test_call_peaks_respects_qvalue():
    rng = np.random.default_rng(11)
    length = 20000
    starts = rng.integers(0, length, 200)
    fragments = {'chr1': (starts, starts + 100)}
    peaks = call_peaks(fragments, {'chr1': length}, qvalue=1e-12,
                       total_fragments_bp=20000.0, genome_bp=length)
    assert peaks == []


def test_peak_merge_merges_close_and_keeps_distant():
    data = np.asarray([[100, 200], [220, 300], [900, 1000]], dtype=np.float64)
    form = Form(data, dims=['peak', 'field'],
                labels={'peak': {'p0': 0, 'p1': 1, 'p2': 2},
                        'field': {'start': 0, 'end': 1}},
                info={'chrom': ['chr1', 'chr1', 'chr1']})
    ctx = _ctx(max_gap=50, output='merged')
    PeakMergeStep().run(ctx, [form])
    merged = ctx['merged']
    assert merged.data.shape == (2, 4)
    assert merged.data[0, 0] == 100 and merged.data[0, 1] == 300
    assert merged.data[0, 3] == 2
    assert merged.info['n_input'] == 3


def test_peak_merge_requires_start_column():
    form = Form(np.asarray([[1.0, 2.0]]), dims=['peak', 'field'],
                labels={'peak': {'p0': 0}, 'field': {'a': 0, 'b': 1}},
                info={'chrom': ['chr1']})
    with pytest.raises(StepError):
        PeakMergeStep().run(_ctx(output='merged'), [form])


def test_iter_fragments_rejects_non_bam(tmp_path):
    path = tmp_path / 'bad.bam'
    path.write_bytes(b'not a bam')
    with pytest.raises(StepError):
        list(iter_fragments(str(path)))

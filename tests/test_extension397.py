"""Contract tests for PWM operators."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError

from src.task.step.steps.pwm_from_counts import PwmFromCountsStep
from src.task.step.steps.pwm_information import PwmInformationStep
from src.task.step.steps.pwm_scan import PwmScanStep


class Ctx(dict):
    def __init__(self, params, workdir):
        super().__init__()
        self.step_params = params
        self.workdir = workdir


def table(data, row_labels, col_labels):
    return Form(
        np.asarray(data, dtype=np.float32),
        dims=['position', 'base'],
        labels={'position': {name: index for index, name in enumerate(row_labels)},
                'base': {name: index for index, name in enumerate(col_labels)}},
    )


def sequences(texts):
    labels = [f"s{index}" for index in range(len(texts))]
    width = max(len(text) for text in texts)
    data = np.zeros((len(texts), width), dtype=np.float32)
    return Form(
        data,
        dims=['sequence', 'position'],
        labels={'sequence': {name: index for index, name in enumerate(labels)},
                'position': {str(index): index for index in range(width)}},
        info={'sequences': texts, 'alphabet_map': 'ACGT'},
    )


def run_step(step, inputs, params):
    ctx = Ctx(params, None)
    step.name = step.definition['id']
    step.run(ctx, list(inputs))
    return ctx


def test_pwm_from_counts_values():
    step = PwmFromCountsStep()
    counts = table([[2, 0, 0, 0]], ['0'], ['A', 'C', 'G', 'T'])
    ctx = run_step(step, [counts], {'output': 'pwm'})
    pwm = ctx['pwm']
    assert pwm.data[0, 0] == pytest.approx(np.log2(2.5), abs=1e-6)
    assert pwm.data[0, 1] == pytest.approx(np.log2(0.5), abs=1e-6)
    assert pwm.info['consensus'] == 'A'
    assert pwm.info['total_information'] == pytest.approx(0.451205, abs=1e-6)


def test_pwm_information_matches_definition():
    counts = table([[2, 0, 0, 0]], ['0'], ['A', 'C', 'G', 'T'])
    pwm = run_step(PwmFromCountsStep(), [counts], {'output': 'pwm'})['pwm']
    info = run_step(PwmInformationStep(), [pwm], {'output': 'information'})['information']
    assert info.data[0, 0] == pytest.approx(0.451205, abs=1e-5)
    assert info.data[0, 1] == pytest.approx(0.625, abs=1e-6)
    assert info.info['consensus'] == 'A'
    assert info.info['total_information'] == pytest.approx(0.451205, abs=1e-5)


def test_pwm_scan_finds_forward_hit():
    counts = table([[4, 0, 0, 0], [0, 4, 0, 0]], ['0', '1'], ['A', 'C', 'G', 'T'])
    pwm = run_step(PwmFromCountsStep(), [counts], {'output': 'pwm'})['pwm']
    seqs = sequences(['TTACGG'])
    hits = run_step(PwmScanStep(), [seqs, pwm], {'min_score': 3.0, 'both_strands': False, 'output': 'hits'})['hits']
    assert hits.data.shape == (1, 3)
    assert hits.data[0, 0] == pytest.approx(2.0)
    assert hits.data[0, 1] == pytest.approx(1.0)
    assert hits.info['n_hits'] == 1


def test_pwm_scan_reverse_strand_coordinate():
    counts = table([[4, 0, 0, 0], [0, 4, 0, 0]], ['0', '1'], ['A', 'C', 'G', 'T'])
    pwm = run_step(PwmFromCountsStep(), [counts], {'output': 'pwm'})['pwm']
    seqs = sequences(['ACGTAC'])
    hits = run_step(PwmScanStep(), [seqs, pwm], {'min_score': 3.0, 'both_strands': True, 'output': 'hits'})['hits']
    strands = list(hits.data[:, 1])
    assert strands.count(1.0) == 2
    assert strands.count(-1.0) == 1
    reverse_rows = hits.data[hits.data[:, 1] == -1.0]
    assert reverse_rows[0, 0] == pytest.approx(2.0)


def test_pwm_scan_empty_result_and_unknown_bases():
    counts = table([[4, 0, 0, 0]], ['0'], ['A', 'C', 'G', 'T'])
    pwm = run_step(PwmFromCountsStep(), [counts], {'output': 'pwm'})['pwm']
    seqs = sequences(['NNNN'])
    hits = run_step(PwmScanStep(), [seqs, pwm], {'min_score': 0.0, 'both_strands': False, 'output': 'hits'})['hits']
    assert hits.data.shape == (0, 3)
    assert hits.info['n_hits'] == 0


def test_pwm_scan_max_hits():
    counts = table([[4, 0, 0, 0]], ['0'], ['A', 'C', 'G', 'T'])
    pwm = run_step(PwmFromCountsStep(), [counts], {'output': 'pwm'})['pwm']
    seqs = sequences(['AAAAAA'])
    hits = run_step(PwmScanStep(), [seqs, pwm], {'min_score': 1.0, 'both_strands': False, 'max_hits': 2, 'output': 'hits'})['hits']
    assert hits.data.shape[0] == 2


def test_counts_reject_missing_base():
    counts = table([[1, 0, 0]], ['0'], ['A', 'C', 'G'])
    with pytest.raises(StepError, match='missing base'):
        run_step(PwmFromCountsStep(), [counts], {'output': 'pwm'})


def test_background_validation():
    counts = table([[1, 1, 1, 1]], ['0'], ['A', 'C', 'G', 'T'])
    with pytest.raises(StepError, match='four frequencies'):
        run_step(PwmFromCountsStep(), [counts], {'background': '0.25,0.75', 'output': 'pwm'})

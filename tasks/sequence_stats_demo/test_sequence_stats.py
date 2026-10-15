# tasks/sequence_stats_demo/test_sequence_stats.py
import numpy as np

from src.core import Form, StepError
from src.task.step.steps.sequence_stats import SequenceStatsStep
from biopipe_sdk.testing import run_operator
import pytest


_ALPHA_MAP = {"A": 0, "C": 1, "G": 2, "T": 3, "U": 3, "N": 4}
_SEQ_NAMES = ("seqA", "seqB", "seqC", "seqD")


def _form(data, alphabet="dna"):
    data = np.asarray(data, dtype=np.float32)
    n = data.shape[0]
    return Form(
        data=data,
        dims=["sequence", "position"],
        labels={
            "sequence": {_SEQ_NAMES[i]: i for i in range(n)},
            "position": {str(i): i for i in range(data.shape[1])},
        },
        info={
            "missing_code": np.nan,
            "representation": "sequence_codes",
            "alphabet_map": _ALPHA_MAP,
            "unknown_code": 5,
            "alphabet": alphabet,
        },
    )


def test_manual_values():
    # seqA: A C G T N _ -> len=5, gc=2/5, n=1/5, valid=5/6
    # seqB: G G C _ _ _ -> len=3, gc=3/3, n=0,   valid=3/6
    data = np.array([
        [0, 1, 2, 3, 4, np.nan],
        [2, 2, 1, np.nan, np.nan, np.nan],
    ], dtype=np.float32)
    out = run_operator(SequenceStatsStep, [_form(data)], {})
    assert out.dims == ["sequence", "statistic"]
    assert out.labels["statistic"] == {
        "length": 0, "gc": 1, "n_ratio": 2, "valid_ratio": 3,
    }
    np.testing.assert_allclose(out.data[0], [5.0, 0.4, 0.2, 5 / 6])
    np.testing.assert_allclose(out.data[1], [3.0, 1.0, 0.0, 0.5])
    assert out.info["alphabet"] == "dna"
    assert out.info["representation"] == "sequence_stats"


def test_empty_sequence():
    data = np.full((2, 4), np.nan, dtype=np.float32)
    data[1, 0] = 0
    out = run_operator(SequenceStatsStep, [_form(data)], {})
    np.testing.assert_allclose(out.data[0], [0.0, 0.0, 0.0, 0.0])
    np.testing.assert_allclose(out.data[1], [1.0, 0.0, 0.0, 0.25])


def test_protein_rejected():
    data = np.array([[0, 1, 2, 3]], dtype=np.float32)
    with pytest.raises(StepError, match="info.alphabet"):
        run_operator(SequenceStatsStep, [_form(data, alphabet="protein")], {})


def test_missing_alphabet_map_rejected():
    form = _form(np.array([[0, 1, 2, 3]], dtype=np.float32))
    form.info.pop("alphabet_map")
    with pytest.raises(StepError, match="alphabet_map"):
        run_operator(SequenceStatsStep, [form], {})
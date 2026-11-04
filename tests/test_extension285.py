"""sequence_isoelectric_point: net charge and pI."""

import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.sequence_isoelectric_point import isoelectric_point, net_charge


def test_charge_ordering():
    assert net_charge("KKK", 7.0) > 2.0
    assert net_charge("DDD", 7.0) < -2.0
    assert net_charge("KKK", 12.0) < net_charge("KKK", 7.0)


def test_pi_consistency():
    for sequence in ("ACDEFGHIKLMNPQRSTVWY", "GGGKKKDDDGGG", "MKWVTFISLLFLFSSAYS"):
        pI = isoelectric_point(sequence)
        assert 3.0 < pI < 13.0
        assert abs(net_charge(sequence, pI)) < 0.01
    assert isoelectric_point("KKK") > 9.0
    assert isoelectric_point("DDD") < 4.5


def test_run_writes_rows():
    form = encode_sequences(["KKK", "DDD"], "sequence", "position", "protein")
    ctx = Context("/tmp/bp285", {"params": {}})
    ctx["sequence"] = form
    run(ctx, [{"name": "sequence_isoelectric_point", "inputs": ["sequence"], "params": {"output": "isoelectric_point"}}])
    result = ctx["isoelectric_point"]
    assert result.data.shape == (2, 2)
    assert result.info["pI"][0] > result.info["pI"][1]


def test_errors():
    with pytest.raises(StepError, match="no titratable residue"):
        isoelectric_point("GGGGG")
